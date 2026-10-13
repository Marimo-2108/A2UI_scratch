import { useState } from 'react';
import WireDemo from './demos/WireDemo';
import LiveDemo from './demos/LiveDemo';
import './App.css';

const tabs = [
  { id: 'wire', label: 'M1 · Static wire', el: <WireDemo /> },
  { id: 'live', label: 'M2 · Live agent (A2A)', el: <LiveDemo /> },
] as const;

export default function App() {
  const [tab, setTab] = useState<(typeof tabs)[number]['id']>('live');
  return (
    <>
      <nav className="tabs">
        <strong>A2UI from scratch</strong>
        {tabs.map((t) => (
          <button key={t.id} className={t.id === tab ? 'on' : ''} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      {tabs.find((t) => t.id === tab)!.el}
    </>
  );
}
