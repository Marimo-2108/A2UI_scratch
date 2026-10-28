export function StudioIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m12 3 9 5-9 5-9-5 9-5Z" fill="currentColor" />
      <path d="m3 12 9 5 9-5M3 16l9 5 9-5" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

export function PreviewIllustration() {
  return (
    <svg viewBox="0 0 160 112" fill="none" aria-hidden="true">
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
  );
}
