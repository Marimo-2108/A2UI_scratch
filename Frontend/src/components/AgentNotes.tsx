interface AgentNotesProps {
  busy: boolean;
  text: string;
}

export function AgentNotes({ busy, text }: AgentNotesProps) {
  return (
    <section className="panel agent-panel" aria-labelledby="agent-title">
      <div className="agent-heading">
        <span className="agent-avatar" aria-hidden="true">✦</span>
        <h2 id="agent-title">Agent notes</h2>
        <span className="muted">{busy ? 'Responding...' : 'Assistant'}</span>
      </div>
      {text
        ? <pre className="agent-text">{text}</pre>
        : <p className="agent-placeholder">A little context from your agent will show up here.</p>}
    </section>
  );
}
