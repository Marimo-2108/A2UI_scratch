import { HttpAgent, type AgentSubscriber } from '@ag-ui/client';
import { EventType, type BaseEvent } from '@ag-ui/core';
import { CustomEventSchema } from '@ag-ui/core/schemas';
import type { ActionPayload } from '@a2ui/web_core/v0_9';
import { z } from 'zod';

export const AGENT_URL = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:10010/';
export const A2UI_EVENT_NAME = 'a2ui';
export const PROTOCOL_VERSION = 'v0.9';

export interface ActionEnvelope {
  version: typeof PROTOCOL_VERSION;
  action: ActionPayload;
}

export interface RunOptions {
  text: string;
  capabilities: Record<string, unknown>;
  action?: ActionEnvelope;
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
    await this.agent.runAgent({
      runId: crypto.randomUUID(),
      forwardedProps: {
        a2uiClientCapabilities: options.capabilities,
        ...(options.action ? { a2uiAction: options.action } : {}),
      },
    }, subscriber);
    if (callbackError) throw callbackError;
    if (runError) throw runError;
    if (!terminal) throw new Error('AG-UI stream ended before the run finished.');
  }
}

export function a2uiMessagesOf(event: BaseEvent): Record<string, unknown>[] {
  if (event.type !== EventType.CUSTOM) return [];
  const custom = CustomEventSchema.parse(event);
  if (custom.name !== A2UI_EVENT_NAME) return [];
  return [a2uiMessage.parse(custom.value)];
}
