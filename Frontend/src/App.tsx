import { AgentNotes } from './components/AgentNotes';
import { AppHeader } from './components/AppHeader';
import { LivePreview } from './components/LivePreview';
import { PromptComposer } from './components/PromptComposer';
import { WireInspector } from './components/WireInspector';
import { useUiAgent } from './hooks/useUiAgent';
import './App.css';

export default function App() {
  const { busy, trace, errors, chat, surfaces, hasConversation, send, followUp, clearTrace } = useUiAgent();

  return (
    <div className="layout">
      <AppHeader />

      <PromptComposer busy={busy} hasConversation={hasConversation} onSend={send} onFollowUp={followUp} />

      {errors.length > 0 && (
        <section className="error-panel" role="alert" aria-label="Agent errors">
          <h2>Something needs your attention</h2>
          {errors.map((error, index) => <pre key={index} className="error">{error}</pre>)}
        </section>
      )}

      <main className="workspace">
        <section className="panel inspector-panel" aria-label="Wire inspector">
          <WireInspector trace={trace} onClear={clearTrace} />
        </section>
        <div className="preview-column">
          <LivePreview busy={busy} surfaces={surfaces} />
          <AgentNotes busy={busy} text={chat.map((message) => message.text).join('\n')} />
        </div>
      </main>
    </div>
  );
}
