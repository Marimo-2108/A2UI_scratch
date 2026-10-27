import { useState } from 'react';

interface PromptComposerProps {
  busy: boolean;
  hasConversation: boolean;
  onSend: (text: string) => void;
  onFollowUp: (text: string) => void;
}

const examples = [
  { label: 'Signup form', prompt: 'a small signup form' },
  { label: 'Revenue dashboard', prompt: 'a revenue dashboard with three stat cards' },
  { label: 'Feedback survey', prompt: 'a short customer feedback survey' },
];

export function PromptComposer({ busy, hasConversation, onSend, onFollowUp }: PromptComposerProps) {
  const [prompt, setPrompt] = useState(examples[0].prompt);
  const canSend = !busy && prompt.trim().length > 0;

  return (
    <section className="panel composer" aria-labelledby="prompt-label">
      <form onSubmit={(event) => {
        event.preventDefault();
        if (canSend) onSend(prompt);
      }}>
        <div className="composer-heading">
          <label id="prompt-label" htmlFor="agent-prompt">What would you like to build?</label>
          <span className="keyboard-hint">Enter to start a new conversation</span>
        </div>
        <div className="prompt-controls">
          <input
            id="agent-prompt"
            className="prompt-input"
            aria-label="Message to the agent"
            aria-describedby="prompt-help"
            placeholder="Describe an interface you have in mind..."
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
          />
          <button className="studio-button primary-button" type="submit" disabled={!canSend}>
            {busy ? <span className="spinner" aria-hidden="true" /> : <span aria-hidden="true">＋</span>}
            {busy ? 'Generating...' : 'New conversation'}
          </button>
          <button
            className="studio-button secondary-button"
            type="button"
            onClick={() => onFollowUp(prompt)}
            disabled={!canSend || !hasConversation}
            title={hasConversation ? 'Continue with the current interface and history' : 'Start a conversation first'}
          >
            Follow-up <span aria-hidden="true">↗</span>
          </button>
        </div>
        <div className="composer-footer">
          <div className="prompt-examples" aria-label="Example prompts">
            <span>Try an idea</span>
            {examples.map((example) => (
              <button
                type="button"
                className="example-button"
                key={example.label}
                onClick={() => setPrompt(example.prompt)}
              >
                {example.label}
              </button>
            ))}
          </div>
          <p id="prompt-help">Follow-up keeps your current UI and conversation.</p>
        </div>
      </form>
    </section>
  );
}
