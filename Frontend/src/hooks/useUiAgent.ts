import { useRef, useState } from 'react';
import { MessageProcessor, type A2uiMessage, type SurfaceModel } from '@a2ui/web_core/v0_9';
import type { ReactCatalogComponent } from '@a2ui/react/v0_9';
import { EventType, type BaseEvent } from '@ag-ui/core';
import { TextMessageContentEventSchema } from '@ag-ui/core/schemas';
import { UiAgentClient, a2uiMessagesOf } from '../agui/client';
import { myCatalog } from '../catalog/myCatalog';

export interface TraceRow {
  n: number;
  at: string;
  dir: 'out' | 'in';
  label: string;
  raw: unknown;
}

type UiProcessor = MessageProcessor<ReactCatalogComponent>;

function describe(event: BaseEvent, messages: A2uiMessage[]): string {
  return messages.length
    ? `${event.type} · A2UI ${messages.map((m) => Object.keys(m).find((k) => k !== 'version')).join(',')}`
    : event.type;
}

export function useUiAgent() {
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState<TraceRow[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [chat, setChat] = useState<string[]>([]);
  const [surfaces, setSurfaces] = useState<SurfaceModel<ReactCatalogComponent>[]>([]);
  const [hasConversation, setHasConversation] = useState(false);
  const client = useRef<UiAgentClient | null>(null);
  const processor = useRef<UiProcessor | null>(null);
  const running = useRef(false);
  const seq = useRef(0);

  function push(dir: TraceRow['dir'], label: string, raw: unknown) {
    const row = { n: ++seq.current, at: new Date().toLocaleTimeString(), dir, label, raw };
    setTrace((rows) => [...rows, row]);
  }

  function reportError(error: unknown) {
    setErrors((previous) => [...previous, error instanceof Error ? error.message : String(error)]);
  }

  function makeProcessor(): UiProcessor {
    const next: UiProcessor = new MessageProcessor<ReactCatalogComponent>(
      [myCatalog],
      (action) => {
        push('out', 'action ' + action.name + ' (clicked in UI)', action);
        void run(next, `USER_ACTION ${JSON.stringify(action)}`);
      },
    );
    return next;
  }

  async function run(current: UiProcessor, text: string) {
    if (running.current) {
      reportError('An agent run is already active. Wait before sending another action.');
      return;
    }
    running.current = true;
    setBusy(true);
    try {
      client.current ??= new UiAgentClient();
      await client.current.run({
        text,
        onRequest: (request) => push('out', 'POST AG-UI run', request),
        onEvent: (event) => {
          if (event.type === EventType.RUN_STARTED) setHasConversation(true);
          const messages = a2uiMessagesOf(event);
          push('in', describe(event, messages), event);
          if (event.type === EventType.TEXT_MESSAGE_CONTENT) {
            const { delta } = TextMessageContentEventSchema.parse(event);
            setChat((chunks) => [...chunks, delta]);
          }
          for (const message of messages) {
            // A restarted agent may try to recreate a surface that is already on screen.
            if ('createSurface' in message && current.getSurface(message.createSurface.surfaceId)) {
              push('in', `ignored duplicate createSurface "${message.createSurface.surfaceId}" (already on screen)`, message);
              continue;
            }
            try {
              current.processMessages(message);
            } catch (error) {
              reportError(error);
            }
          }
          if (messages.length) setSurfaces(Array.from(current.getSurfaces().values()));
        },
      });
    } catch (error) {
      reportError(error);
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  function send(text: string) {
    if (running.current) return;
    setErrors([]);
    setChat([]);
    client.current = new UiAgentClient();
    setHasConversation(false);
    const next = makeProcessor();
    processor.current = next;
    setSurfaces([]);
    void run(next, text);
  }

  function followUp(text: string) {
    setErrors([]);
    if (!processor.current) {
      reportError('Start a new conversation before sending a follow-up.');
      return;
    }
    void run(processor.current, text);
  }

  function clearTrace() {
    setTrace([]);
  }

  return { busy, trace, errors, chat, surfaces, hasConversation, send, followUp, clearTrace };
}
