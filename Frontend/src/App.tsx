import { A2uiSurface } from '@a2ui/react/v0_9';
import { PROTOCOL_VERSION } from './agui/client';
import { PromptComposer } from './components/PromptComposer';
import { WireInspector } from './components/WireInspector';
import { useUiAgent } from './hooks/useUiAgent';
import './App.css';

export default function App() {
  const { busy, trace, errors, chat, surfaces, hasConversation, send, followUp, clearTrace } = useUiAgent();

  return (
    <div className="layout">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="m12 3 9 5-9 5-9-5 9-5Z" fill="currentColor" />
              <path d="m3 12 9 5 9-5M3 16l9 5 9-5" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
            </svg>
          </span>
          <span>A2UI <strong>Studio</strong></span>
          <span className="header-divider" aria-hidden="true" />
          <span className="workspace-label">Playground</span>
        </div>
        <div className={`status-badge${busy ? ' is-busy' : ''}`} role="status">
          <span className="status-dot" aria-hidden="true" />
          {busy ? 'Generating interface' : hasConversation ? 'Conversation active' : 'Ready to create'}
        </div>
      </header>

      <section className="intro" aria-labelledby="page-title">
        <div>
          <p className="eyebrow">YOUR AGENT. YOUR INTERFACE.</p>
          <h1 id="page-title">Turn an idea into an interface.</h1>
          <p className="intro-copy">Describe it, watch it take shape, and explore every message along the way.</p>
        </div>
        <div className="protocol-badge">AG-UI <span aria-hidden="true">/</span> A2UI {PROTOCOL_VERSION}</div>
      </section>

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
          <section className="panel preview-panel" aria-labelledby="preview-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">THE RESULT</p>
                <h2 id="preview-title">Live preview</h2>
              </div>
              <span className="count-badge">{surfaces.length} {surfaces.length === 1 ? 'surface' : 'surfaces'}</span>
            </div>
            <div className="rendered" aria-busy={busy}>
              {surfaces.length === 0 && (
                <div className="preview-empty">
                  <div className="preview-illustration" aria-hidden="true">
                    <svg viewBox="0 0 160 112" fill="none">
                      <rect x="22" y="12" width="116" height="88" rx="10" fill="var(--panel)" stroke="var(--border)" />
                      <path d="M22 34h116" stroke="var(--border)" />
                      <circle cx="34" cy="24" r="3" fill="var(--accent)" />
                      <circle cx="44" cy="24" r="3" fill="var(--border)" />
                      <circle cx="54" cy="24" r="3" fill="var(--border)" />
                      <rect x="34" y="46" width="38" height="42" rx="5" fill="var(--accent-soft)" />
                      <rect x="82" y="48" width="42" height="5" rx="2.5" fill="var(--border)" />
                      <rect x="82" y="60" width="32" height="5" rx="2.5" fill="var(--border)" />
                      <rect x="82" y="76" width="26" height="12" rx="4" fill="var(--accent)" />
                    </svg>
                  </div>
                  <h3>{busy ? 'Bringing your idea to life' : 'Your next interface starts here'}</h3>
                  <p>{busy ? 'The agent is working. Incoming UI will appear here.' : 'Send a prompt above. Your agent-generated UI will appear in this space, ready to interact with.'}</p>
                  <span className="preview-empty-caption">PROMPT → GENERATE → INTERACT</span>
                </div>
              )}
              {surfaces.map((surface) => (
                <div className="surface-frame" key={surface.id}>
                  <div className="surface-label"><span className="status-dot" aria-hidden="true" />{surface.id}</div>
                  <A2uiSurface surface={surface} />
                </div>
              ))}
            </div>
          </section>

          <section className="panel agent-panel" aria-labelledby="agent-title">
            <div className="agent-heading">
              <span className="agent-avatar" aria-hidden="true">✦</span>
              <h2 id="agent-title">Agent notes</h2>
              <span className="muted">{busy ? 'Responding...' : 'Assistant'}</span>
            </div>
            {chat.length
              ? <pre className="agent-text">{chat.join('\n')}</pre>
              : <p className="agent-placeholder">A little context from your agent will show up here.</p>}
          </section>
        </div>
      </main>
    </div>
  );
}
