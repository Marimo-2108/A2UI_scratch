import type { ReactNode } from 'react';

interface PanelHeadingProps {
  title: ReactNode;
  eyebrow: string;
  id?: string;
  children?: ReactNode;
}

export function PanelHeading({ title, eyebrow, id, children }: PanelHeadingProps) {
  return (
    <div className="panel-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={id}>{title}</h2>
      </div>
      {children}
    </div>
  );
}
