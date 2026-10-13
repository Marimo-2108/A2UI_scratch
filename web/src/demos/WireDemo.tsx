import { useCallback, useEffect, useMemo, useState } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';
import { basicCatalog } from '@a2ui/web_core/v0_9/basic_catalog';
import { A2uiSurface, type ReactCatalogComponent } from '@a2ui/react/v0_9';
import { wire } from '../wire/messages';

type ActionLog = { at: string; action: unknown };

export default function WireDemo() {
  const [applied, setApplied] = useState(0); // how many wire steps have been fed in
  const [selected, setSelected] = useState(0); // which step's JSON is displayed
  const [errors, setErrors] = useState<string[]>([]);
  const [actions, setActions] = useState<ActionLog[]>([]);
  const [tick, setTick] = useState(0); // forces re-render when surfaces change
  const [session, setSession] = useState(0); // bump to get a brand-new processor (Reset)

  // The processor is the heart of the client: it ingests messages and owns surface state.
  // The second argument is the global action handler: user actions leave the client here.
  const processor = useMemo(
    () =>
      new MessageProcessor<ReactCatalogComponent>([basicCatalog], (action) => {
        setActions((a) => [{ at: new Date().toLocaleTimeString(), action }, ...a]);
      }),
    [session],
  );

  useEffect(() => {
    const bump = () => setTick((t) => t + 1);
    const a = processor.onSurfaceCreated(bump);
    const b = processor.onSurfaceDeleted(bump);
    return () => {
      a.unsubscribe();
      b.unsubscribe();
    };
  }, [processor]);

  const next = useCallback(() => {
    if (applied >= wire.length) return;
    try {
      processor.processMessages(wire[applied].message as never);
      setErrors([]);
    } catch (e) {
      setErrors([e instanceof Error ? e.message : String(e)]);
    }
    setSelected(applied);
    setApplied(applied + 1);
    setTick((t) => t + 1);
  }, [applied, processor]);

  const reset = () => {
    setSession((s) => s + 1);
    setApplied(0);
    setSelected(0);
    setErrors([]);
    setActions([]);
  };

  const surfaces = Array.from(processor.model.surfacesMap.values());
  void tick;

  return (
    <div className="layout">
      <header>
        <h1>A2UI from scratch · Milestone 1: the wire</h1>
        <p>
          No agent, no AI. We hand-feed A2UI JSON messages into the real{' '}
          <code>MessageProcessor</code> one at a time.
        </p>
      </header>

      <section className="panel">
        <div className="toolbar">
          <button onClick={next} disabled={applied >= wire.length}>
            Send next message ▶
          </button>
          <button onClick={reset}>Reset</button>
          <span className="muted">
            {applied}/{wire.length} sent
          </span>
        </div>
        <ol className="steps">
          {wire.map((s, i) => (
            <li
              key={i}
              className={[i < applied ? 'sent' : '', i === selected ? 'sel' : ''].join(' ')}
              onClick={() => setSelected(i)}
            >
              {s.title}
            </li>
          ))}
        </ol>
        <p className="explain">{wire[selected].explain}</p>
        <pre>{JSON.stringify(wire[selected].message, null, 2)}</pre>
        {errors.map((e, i) => (
          <pre key={i} className="error">
            {e}
          </pre>
        ))}
      </section>

      <section className="panel">
        <h2>Rendered UI</h2>
        <div className="rendered">
          {surfaces.length === 0 && <div className="muted">No surfaces.</div>}
          {surfaces.map((s) => (
            <A2uiSurface key={s.id} surface={s} />
          ))}
        </div>

        <h2>Client → agent (user actions)</h2>
        <p className="muted">
          Pressing the button fires the action handler. In Milestone 3 this will go to the agent.
        </p>
        <pre>{actions.length ? JSON.stringify(actions, null, 2) : '(none yet)'}</pre>
      </section>
    </div>
  );
}
