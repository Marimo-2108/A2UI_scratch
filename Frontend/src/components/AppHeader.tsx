import { PROTOCOL_VERSION } from '../agui/client';
import { StudioIcon } from './Icons';

export function AppHeader() {
  return (
    <>
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><StudioIcon /></span>
          <span>A2UI <strong>Studio</strong></span>
          <span className="header-divider" aria-hidden="true" />
          <span className="workspace-label">Playground</span>
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
    </>
  );
}
