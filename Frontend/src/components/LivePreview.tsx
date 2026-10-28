import { A2uiSurface, type ReactCatalogComponent } from '@a2ui/react/v0_9';
import type { SurfaceModel } from '@a2ui/web_core/v0_9';
import { PreviewIllustration } from './Icons';
import { PanelHeading } from './PanelHeading';

interface LivePreviewProps {
  busy: boolean;
  surfaces: SurfaceModel<ReactCatalogComponent>[];
}

export function LivePreview({ busy, surfaces }: LivePreviewProps) {
  return (
    <section className="panel preview-panel" aria-labelledby="preview-title">
      <PanelHeading id="preview-title" title="Live preview" eyebrow="THE RESULT">
        <span className="count-badge">{surfaces.length} {surfaces.length === 1 ? 'surface' : 'surfaces'}</span>
      </PanelHeading>
      <div className="rendered" aria-busy={busy}>
        {surfaces.length === 0 && (
          <div className="preview-empty">
            <div className="preview-illustration"><PreviewIllustration /></div>
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
  );
}
