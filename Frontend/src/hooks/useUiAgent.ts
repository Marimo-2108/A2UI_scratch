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

interface AgentMessage {
  id: string;
  text: string;
}

function describeEvent(event: BaseEvent, messages: A2uiMessage[]): string {
  if (messages.length === 0) return event.type;

  const operations = messages.map((message) =>
    Object.keys(message).find((key) => key !== 'version'),
  );
  return `${event.type} · A2UI ${operations.join(',')}`;
}

export function useUiAgent() {
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState<TraceRow[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [chat, setChat] = useState<AgentMessage[]>([]);
  const [surfaces, setSurfaces] = useState<SurfaceModel<ReactCatalogComponent>[]>([]);
  const [hasConversation, setHasConversation] = useState(false);
  const client = useRef<UiAgentClient | null>(null);
  const processor = useRef<UiProcessor | null>(null);
  const running = useRef(false);
  const traceId = useRef(0);

  function addTrace(dir: TraceRow['dir'], label: string, raw: unknown) {
    const row = { n: ++traceId.current, at: new Date().toLocaleTimeString(), dir, label, raw };
    setTrace((rows) => [...rows, row]);
  }

  function reportError(error: unknown) {
    setErrors((previous) => [...previous, error instanceof Error ? error.message : String(error)]);
  }

  function appendText(messageId: string, delta: string) {
    setChat((messages) => {
      const lastMessage = messages.at(-1);
      if (lastMessage?.id !== messageId) {
        return [...messages, { id: messageId, text: delta }];
      }

      const updatedMessage = { id: messageId, text: lastMessage.text + delta };
      return [...messages.slice(0, -1), updatedMessage];
    });
  }

  function processUiMessages(uiProcessor: UiProcessor, messages: A2uiMessage[]) {
    for (const message of messages) {
      // Follow-ups may recreate a surface that is already on screen.
      if ('createSurface' in message && uiProcessor.getSurface(message.createSurface.surfaceId)) {
        addTrace('in', `ignored duplicate createSurface "${message.createSurface.surfaceId}" (already on screen)`, message);
        continue;
      }
      uiProcessor.processMessages(message);
    }
    setSurfaces(Array.from(uiProcessor.getSurfaces().values()));
  }

  function handleEvent(uiProcessor: UiProcessor, event: BaseEvent) {
    const messages = a2uiMessagesOf(event);
    addTrace('in', describeEvent(event, messages), event);

    switch (event.type) {
      case EventType.RUN_STARTED:
        setHasConversation(true);
        break;
      case EventType.TEXT_MESSAGE_CONTENT: {
        const { messageId, delta } = TextMessageContentEventSchema.parse(event);
        appendText(messageId, delta);
        break;
      }
    }

    if (messages.length > 0) processUiMessages(uiProcessor, messages);
  }

  async function run(uiProcessor: UiProcessor, text: string) {
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
        onRequest: (request) => addTrace('out', 'POST AG-UI run', request),
        onEvent: (event) => handleEvent(uiProcessor, event),
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
    const uiProcessor: UiProcessor = new MessageProcessor<ReactCatalogComponent>(
      [myCatalog],
      (action) => {
        addTrace('out', `action ${action.name} (clicked in UI)`, action);
        void run(uiProcessor, `USER_ACTION ${JSON.stringify(action)}`);
      },
    );
    processor.current = uiProcessor;
    setSurfaces([]);
    void run(uiProcessor, text);
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
