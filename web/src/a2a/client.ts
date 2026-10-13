/**
 * A minimal A2A client written by hand (no @a2a-js/sdk), so every byte is visible.
 *
 * A2A (JSON-RPC binding, protocol 0.3):
 *   POST <agent url>   body: { jsonrpc: "2.0", id, method: "message/stream", params: { message } }
 *   response:          text/event-stream, each `data:` line is a JSON-RPC response whose
 *                      `result` is a Task | Message | TaskStatusUpdateEvent | TaskArtifactUpdateEvent
 */

export const AGENT_URL = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:10010/';

/** The A2UI extension URI the client opts in to (the version is part of the URI). */
export const A2UI_EXTENSION_URI = 'https://a2ui.org/a2a-extension/a2ui/v0.9.1';
export const A2UI_MIME_TYPES = ['application/a2ui+json', 'application/json+a2ui'];

export type A2APart =
  | { kind: 'text'; text: string; metadata?: Record<string, unknown> }
  | { kind: 'data'; data: Record<string, unknown>; metadata?: Record<string, unknown> };

export interface A2AMessage {
  kind: 'message';
  messageId: string;
  role: 'user' | 'agent';
  parts: A2APart[];
  contextId?: string;
  taskId?: string;
  metadata?: Record<string, unknown>;
}

/** Union of what the stream can carry in `result` (only the fields we use). */
export type A2AEvent =
  | { kind: 'task'; id: string; contextId: string; status: { state: string; message?: A2AMessage } }
  | { kind: 'message' } & A2AMessage
  | {
      kind: 'status-update';
      taskId: string;
      contextId: string;
      final: boolean;
      status: { state: string; message?: A2AMessage };
    }
  | { kind: 'artifact-update'; taskId: string; contextId: string };

export interface StreamOptions {
  /** One or more parts to send as the user message. */
  parts: A2APart[];
  /** Reuse to keep the same A2A session (all surfaces of a conversation share it). */
  contextId?: string;
  /** a2uiClientCapabilities, placed in message.metadata (spec: extension specification). */
  capabilities: Record<string, unknown>;
  signal?: AbortSignal;
  /** Called with the raw request, for the inspector. */
  onRequest?: (info: { url: string; headers: Record<string, string>; body: unknown }) => void;
}

export async function* streamMessage(opts: StreamOptions): AsyncGenerator<A2AEvent> {
  const body = {
    jsonrpc: '2.0',
    id: crypto.randomUUID(),
    method: 'message/stream',
    params: {
      message: {
        kind: 'message',
        messageId: crypto.randomUUID(),
        role: 'user',
        parts: opts.parts,
        ...(opts.contextId ? { contextId: opts.contextId } : {}),
        metadata: { a2uiClientCapabilities: opts.capabilities },
      },
    },
  };
  const headers = {
    'Content-Type': 'application/json',
    // Opts in to the A2UI extension. A custom header => the browser sends a CORS preflight.
    'X-A2A-Extensions': A2UI_EXTENSION_URI,
  };
  opts.onRequest?.({ url: AGENT_URL, headers, body });

  const res = await fetch(AGENT_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: opts.signal,
  });
  if (!res.ok || !res.body) throw new Error(`A2A request failed: HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // SSE events are separated by a blank line.
    const events = buf.split(/\r?\n\r?\n/);
    buf = events.pop() ?? '';
    for (const ev of events) {
      const data = ev
        .split(/\r?\n/)
        .filter((l) => l.startsWith('data:'))
        .map((l) => l.slice(5).trimStart())
        .join('\n');
      if (!data) continue;
      const rpc = JSON.parse(data);
      if (rpc.error) throw new Error(`A2A error ${rpc.error.code}: ${rpc.error.message}`);
      yield rpc.result as A2AEvent;
    }
  }
}

/** Parts of an event that carry A2UI messages (DataParts with the A2UI MIME type). */
export function a2uiMessagesOf(ev: A2AEvent): Record<string, unknown>[] {
  const parts =
    ev.kind === 'status-update' || ev.kind === 'task' ? ev.status.message?.parts : ev.kind === 'message' ? ev.parts : undefined;
  return (parts ?? [])
    .filter(
      (p): p is Extract<A2APart, { kind: 'data' }> =>
        p.kind === 'data' && A2UI_MIME_TYPES.includes(String(p.metadata?.mimeType)),
    )
    .map((p) => p.data);
}

export function textOf(ev: A2AEvent): string[] {
  const parts =
    ev.kind === 'status-update' || ev.kind === 'task' ? ev.status.message?.parts : ev.kind === 'message' ? ev.parts : undefined;
  return (parts ?? []).filter((p) => p.kind === 'text').map((p) => (p as { text: string }).text);
}
