import { useRef, useState } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';
import { basicCatalog } from '@a2ui/web_core/v0_9/basic_catalog';
import { A2uiSurface, type ReactCatalogComponent } from '@a2ui/react/v0_9';
import type { ActionPayload } from '@a2ui/web_core/v0_9';
import {
  AGENT_URL,
  A2UI_EXTENSION_URI,
  a2uiMessagesOf,
  streamMessage,
  textOf,
  type A2AEvent,
  type A2APart,
} from '../a2a/client';

interface TraceRow {
  n: number;
  at: string;
  dir: 'out' | 'in';
  label: string;
  raw: unknown;
}

const PROTOCOL_VERSION = 'v0.9.1';

/**
 * Client -> agent: a user action travels as a DataPart with the same MIME type.
 * Shape (spec, client_to_server): { version, action: { name, surfaceId, sourceComponentId, timestamp, context } }
 */
function actionPart(a: ActionPayload): A2APart {
  return {
    kind: 'data',
    data: {
      version: PROTOCOL_VERSION,
      action: {
        name: a.name,
        surfaceId: a.surfaceId,
        sourceComponentId: a.sourceComponentId,
        timestamp: a.timestamp,
        context: a.context,
      },
    },
    metadata: { mimeType: 'application/a2ui+json' },
  };
}
function describe(ev: A2AEvent): string {
  switch (ev.kind) {
    case 'task':
      return `task · ${ev.status.state}`;
    case 'status-update': {
      const a2ui = a2uiMessagesOf(ev).map((m) => Object.keys(m).find((k) => k !== 'version'));
      const text = textOf(ev);
      const what = a2ui.length ? `A2UI ${a2ui.join(',')}` : text.length ? `text "${text[0]}"` : '';
      return `status-update · ${ev.status.state}${ev.final ? ' · final' : ''} · ${what}`;
    }
    default:
      return ev.kind;
  }
}

export default function LiveDemo() {
  const [prompt, setPrompt] = useState('show me the welcome card');
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState<TraceRow[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [chat, setChat] = useState<string[]>([]);
  const [tick, setTick] = useState(0);
  const contextId = useRef<string | undefined>(undefined);
  const seq = useRef(0);

  // The MessageProcessor from Milestone 1. Its 2nd argument is the ACTION HANDLER: the library
  // calls it when the user clicks a Button whose component has an `action.event`.
  // Milestone 3: instead of only logging, we now send the action to the agent.
  const makeProcessor = () => {
    const p: MessageProcessor<ReactCatalogComponent> = new MessageProcessor<ReactCatalogComponent>(
      [basicCatalog],
      (action) => {
        push('out', 'action ' + action.name + ' (clicked in UI)', action);
        void run(p, [actionPart(action)]);
      },
    );
    return p;
  };
  const [processor, setProcessor] = useState(makeProcessor);
  const push = (dir: TraceRow['dir'], label: string, raw: unknown) =>
    setTrace((t) => [...t, { n: ++seq.current, at: new Date().toLocaleTimeString(), dir, label, raw }]);

  /** Send parts to the agent and feed every A2UI message of the reply into processor `p`. */
  const run = async (p: MessageProcessor<ReactCatalogComponent>, parts: A2APart[]) => {
    setBusy(true);
    try {
      for await (const ev of streamMessage({
        parts,
        contextId: contextId.current, // same conversation as before
        // a2uiClientCapabilities: tells the agent which catalogs our renderer can draw.
        capabilities: { [PROTOCOL_VERSION]: { supportedCatalogIds: [basicCatalog.id] } },
        onRequest: (r) => push('out', 'POST message/stream', r),
      })) {
        contextId.current = 'contextId' in ev ? ev.contextId : contextId.current;
        push('in', describe(ev), ev);
        textOf(ev).forEach((t) => setChat((c) => [...c, t]));
        for (const msg of a2uiMessagesOf(ev)) {
          try {
            p.processMessages(msg as never);
          } catch (e) {
            setErrors((x) => [...x, e instanceof Error ? e.message : String(e)]);
          }
        }
        setTick((t) => t + 1);
      }
    } catch (e) {
      setErrors((x) => [...x, e instanceof Error ? e.message : String(e)]);
    } finally {
      setBusy(false);
    }
  };

  /** "Send to agent": starts over with a brand-new processor (so surfaces are recreated). */
  const send = () => {
    setErrors([]);
    setChat([]);
    const p = makeProcessor();
    setProcessor(p);
    void run(p, [{ kind: 'text', text: prompt }]);
  };
  void tick;

  const surfaces = Array.from(processor.model.surfacesMap.values());
  const sel = trace.find((r) => r.n === selected);

  return (
    <div className="layout">
      <header>
        <p>
          Browser → A2A (<code>message/stream</code> over SSE) → Python agent at <code>{AGENT_URL}</code>.
          Extension: <code>{A2UI_EXTENSION_URI}</code>
        </p>
      </header>

      <section className="panel">
        <div className="toolbar">
          <input
            style={{ flex: 1, padding: 6 }}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !busy && send()}
          />
          <button onClick={send} disabled={busy}>
            {busy ? 'Streaming…' : 'Send to agent ▶'}
          </button>
          <button onClick={() => { setTrace([]); setSelected(null); }}>Clear trace</button>
        </div>

        <h2>Wire inspector</h2>
        <ol className="steps">
          {trace.length === 0 && <li className="muted">Nothing yet. Send a message.</li>}
          {trace.map((r) => (
            <li
              key={r.n}
              className={['sent', r.n === selected ? 'sel' : ''].join(' ')}
              onClick={() => setSelected(r.n)}
            >
              <span className="muted">{r.at}</span> {r.dir === 'out' ? '⬆' : '⬇'} {r.label}
            </li>
          ))}
        </ol>
        <pre>{sel ? JSON.stringify(sel.raw, null, 2) : '(click a row to see the raw JSON)'}</pre>
        {errors.map((e, i) => (
          <pre key={i} className="error">{e}</pre>
        ))}
      </section>

      <section className="panel">
        <h2>Agent text</h2>
        <pre>{chat.length ? chat.join('\n') : '(none)'}</pre>
        <h2>Rendered UI</h2>
        <div className="rendered">
          {surfaces.length === 0 && <div className="muted">No surfaces.</div>}
          {surfaces.map((s) => (
            <A2uiSurface key={s.id} surface={s} />
          ))}
        </div>
      </section>
    </div>
  );
}
