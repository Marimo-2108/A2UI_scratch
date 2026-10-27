import { HttpAgent, type AgentSubscriber } from '@ag-ui/client';
import { EventType, type BaseEvent } from '@ag-ui/core';
import { ToolCallResultEventSchema } from '@ag-ui/core/schemas';
import { z } from 'zod';

export const AGENT_URL = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:10010/';
export const PROTOCOL_VERSION = 'v0.9';
/** The A2UI SDK tool the agent calls to send UI; its validated result carries the messages. */
export const A2UI_TOOL_NAME = 'send_a2ui_json_to_client';

export interface RunOptions {
  text: string;
  onRequest?: (info: { url: string; headers: Record<string, string>; body: unknown }) => void;
  onEvent: (event: BaseEvent) => void;
}

const a2uiMessage = z.object({
  version: z.literal(PROTOCOL_VERSION),
}).passthrough().refine(
  (value) => ['createSurface', 'updateComponents', 'updateDataModel', 'deleteSurface']
    .filter((key) => key in value).length === 1,
  'Expected exactly one A2UI message operation',
);
const a2uiToolResult = z.object({ validated_a2ui_json: z.array(a2uiMessage) });

/** The SDK owns SSE decoding, event validation, and conversation message history. */
export class UiAgentClient {
  readonly agent: HttpAgent;

  constructor(url = AGENT_URL) {
    this.agent = new HttpAgent({ url, threadId: crypto.randomUUID() });
  }

  async run(options: RunOptions): Promise<void> {
    if (this.agent.isRunning) throw new Error('A run is already active for this conversation.');
    this.agent.messages.push({ id: crypto.randomUUID(), role: 'user', content: options.text });
    let terminal = false;
    let runError: Error | undefined;
    let callbackError: Error | undefined;
    // The SDK logs and swallows subscriber exceptions. Preserve them for the caller.
    const notify = (callback: () => void) => {
      if (callbackError) return;
      try {
        callback();
      } catch (error) {
        callbackError = error instanceof Error ? error : new Error(String(error));
      }
    };
    const subscriber: AgentSubscriber = {
      onRunInitialized: ({ input }) => {
        notify(() => options.onRequest?.({
          url: this.agent.url,
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
          body: input,
        }));
      },
      onEvent: ({ event }) => {
        if (event.type === EventType.RUN_FINISHED || event.type === EventType.RUN_ERROR) {
          terminal = true;
        }
        notify(() => options.onEvent(event));
      },
      onRunErrorEvent: ({ event }) => {
        runError = new Error(event.message);
      },
    };
    await this.agent.runAgent({ runId: crypto.randomUUID() }, subscriber);
    if (callbackError) throw callbackError;
    if (runError) throw runError;
    if (!terminal) throw new Error('AG-UI stream ended before the run finished.');
  }
}

/**
 * A2UI messages carried by a TOOL_CALL_RESULT of the A2UI tool. A result with `error` instead
 * means the backend rejected the JSON and the model is retrying; nothing is rendered for it.
 */
export function a2uiMessagesOf(event: BaseEvent): Record<string, unknown>[] {
  if (event.type !== EventType.TOOL_CALL_RESULT) return [];
  const { content } = ToolCallResultEventSchema.parse(event);
  if (typeof content !== 'string') return [];
  const parsed: unknown = JSON.parse(content);
  if (!parsed || typeof parsed !== 'object' || !('validated_a2ui_json' in parsed)) return [];
  return a2uiToolResult.parse(parsed).validated_a2ui_json;
}
