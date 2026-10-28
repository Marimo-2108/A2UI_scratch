import { useState } from 'react';
import type { TraceRow } from '../hooks/useUiAgent';
import { Button } from './Button';
import { PanelHeading } from './PanelHeading';

interface WireInspectorProps {
  trace: TraceRow[];
  onClear: () => void;
}

type EventKind = 'request' | 'action' | 'error' | 'ui' | 'run' | 'text' | 'tool' | 'state' | 'other';

const KIND_LABELS: Record<EventKind, string> = {
  request: 'Request', action: 'Action', error: 'Error', ui: 'UI', run: 'Run',
  text: 'Text', tool: 'Tool', state: 'State', other: 'Event',
};

function kindOf(row: TraceRow): EventKind {
  if (row.dir === 'out') return row.label.startsWith('action ') ? 'action' : 'request';
  if (row.label.startsWith('RUN_ERROR')) return 'error';
  if (row.label.includes('A2UI') || row.label.includes('createSurface')) return 'ui';
  const prefix = row.label.split('_')[0];
  if (prefix === 'RUN') return 'run';
  if (prefix === 'TEXT') return 'text';
  if (prefix === 'TOOL') return 'tool';
  if (prefix === 'STATE' || prefix === 'MESSAGES') return 'state';
  return 'other';
}

export function WireInspector({ trace, onClear }: WireInspectorProps) {
  const [selected, setSelected] = useState<TraceRow | null>(null);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const raw = selected ? JSON.stringify(selected.raw, null, 2) : '// Select an event above to inspect its payload.';

  function select(row: TraceRow | null) {
    setSelected(row);
    setCopyState('idle');
  }

  function clear() {
    select(null);
    onClear();
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(raw);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  }

  return (
    <>
      <PanelHeading
        eyebrow="BEHIND THE SCENES"
        title={<>Wire inspector <span className="count-badge">{trace.length}</span></>}
      >
        <Button variant="text" onClick={clear} disabled={!trace.length}>Clear trace</Button>
      </PanelHeading>
      <div className="trace-content">
        {trace.length === 0 ? (
          <div className="trace-empty">
            <span className="trace-empty-icon" aria-hidden="true">{'{ }'}</span>
            <h3>A clear view of every event</h3>
            <p>Requests and streamed events appear here when you send a prompt.</p>
          </div>
        ) : (
          <ol className="steps" aria-label="Requests and events">
            {trace.map((row) => {
              const kind = kindOf(row);
              return (
                <li key={row.n}>
                  <button
                    type="button"
                    className={`trace-row kind-${kind}${row.n === selected?.n ? ' sel' : ''}`}
                    aria-pressed={row.n === selected?.n}
                    title={row.label}
                    onClick={() => select(row)}
                  >
                    <span className={`trace-direction ${row.dir === 'out' ? 'outbound' : 'inbound'}`} aria-label={row.dir === 'out' ? 'Outgoing' : 'Incoming'}>
                      {row.dir === 'out' ? '↑' : '↓'}
                    </span>
                    <span className="trace-kind">{KIND_LABELS[kind]}</span>
                    <span className="trace-label">{row.label}</span>
                    <span className="trace-time">{row.at}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>
      <div className="payload-panel">
        <div className="payload-heading">
          <span>EVENT PAYLOAD{selected ? ` · #${selected.n}` : ''}</span>
          <button type="button" className="copy-button" onClick={copy} disabled={!selected}>
            {copyState === 'copied' ? 'Copied ✓' : copyState === 'failed' ? 'Copy failed' : 'Copy JSON'}
          </button>
        </div>
        <pre className="json-preview" tabIndex={0} aria-label="Selected event JSON">{raw}</pre>
      </div>
    </>
  );
}
