import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

const vite = await createServer({
  server: { middlewareMode: true, hmr: false },
  appType: 'custom',
});
after(() => vite.close());
const { PromptComposer } = await vite.ssrLoadModule('/src/components/PromptComposer.tsx');
const { WireInspector } = await vite.ssrLoadModule('/src/components/WireInspector.tsx');
const { AppHeader } = await vite.ssrLoadModule('/src/components/AppHeader.tsx');
const { PreviewIllustration } = await vite.ssrLoadModule('/src/components/Icons.tsx');
const { AgentNotes } = await vite.ssrLoadModule('/src/components/AgentNotes.tsx');
const { Button } = await vite.ssrLoadModule('/src/components/Button.tsx');
const { PanelHeading } = await vite.ssrLoadModule('/src/components/PanelHeading.tsx');

function composer(props = {}) {
  return renderToStaticMarkup(createElement(PromptComposer, {
    busy: false, hasConversation: false, onSend: () => {}, onFollowUp: () => {}, ...props,
  }));
}

function button(markup, label) {
  const found = markup.match(/<button\b[^>]*>[\s\S]*?<\/button>/g)?.find((value) => value.includes(label));
  assert.ok(found, `Missing button: ${label}`);
  return found;
}

test('composer labels its prompt and separates new, follow-up and example actions', () => {
  const markup = composer();
  assert.match(markup, /aria-label="Message to the agent"/);
  assert.match(markup, /aria-describedby="prompt-help"/);
  assert.match(button(markup, 'New conversation'), /type="submit"/);
  assert.doesNotMatch(button(markup, 'New conversation'), /disabled/);
  assert.match(button(markup, 'Follow-up'), /disabled/);
  for (const label of ['Signup form', 'Revenue dashboard', 'Feedback survey']) {
    assert.match(button(markup, label), /type="button"/);
  }
});

test('composer enables follow-up for an active conversation and disables sends while busy', () => {
  assert.doesNotMatch(button(composer({ hasConversation: true }), 'Follow-up'), /disabled/);
  const busy = composer({ busy: true, hasConversation: true });
  assert.match(button(busy, 'Generating...'), /disabled/);
  assert.match(button(busy, 'Follow-up'), /disabled/);
});

test('empty inspector explains its state and disables clearing', () => {
  const markup = renderToStaticMarkup(createElement(WireInspector, { trace: [], onClear: () => {} }));
  assert.match(markup, /A clear view of every event/);
  assert.match(button(markup, 'Clear trace'), /disabled/);
  assert.match(markup, /aria-label="Selected event JSON"/);
});

test('inspector renders keyboard-accessible event buttons and both event directions', () => {
  const trace = [
    { n: 1, at: '10:00:00', dir: 'out', label: 'POST AG-UI run', raw: { text: 'a form' } },
    { n: 2, at: '10:00:01', dir: 'in', label: 'RUN_STARTED', raw: { type: 'RUN_STARTED' } },
  ];
  const markup = renderToStaticMarkup(createElement(WireInspector, { trace, onClear: () => {} }));
  assert.doesNotMatch(button(markup, 'Clear trace'), /disabled/);
  assert.equal((markup.match(/aria-pressed="false"/g) ?? []).length, trace.length);
  assert.match(button(markup, 'RUN_STARTED'), /type="button"/);
  assert.match(markup, /aria-label="Outgoing"/);
  assert.match(markup, /aria-label="Incoming"/);
  assert.match(markup, /kind-request/);
  assert.match(markup, /kind-run/);
  assert.match(button(markup, 'Copy JSON'), /disabled/);
});

test('shared buttons preserve native attributes and default to non-submit actions', () => {
  const action = renderToStaticMarkup(createElement(Button, { disabled: true }, 'Action'));
  assert.match(action, /type="button"/);
  assert.match(action, /secondary-button/);
  assert.match(action, /disabled/);

  const submit = renderToStaticMarkup(createElement(Button, {
    type: 'submit', variant: 'primary', 'aria-label': 'Send prompt',
  }, 'Send'));
  assert.match(submit, /type="submit"/);
  assert.match(submit, /primary-button/);
  assert.match(submit, /aria-label="Send prompt"/);
});

test('shared panel headings preserve titles, labels and actions', () => {
  const markup = renderToStaticMarkup(createElement(PanelHeading, {
    id: 'preview-title', title: 'Live preview', eyebrow: 'THE RESULT',
  }, createElement('span', null, '0 surfaces')));
  assert.match(markup, /<h2 id="preview-title">Live preview<\/h2>/);
  assert.match(markup, /THE RESULT/);
  assert.match(markup, /0 surfaces/);
});

test('header preserves the original branding, artwork and run states', () => {
  for (const [busy, hasConversation, status] of [
    [false, false, 'Ready to create'],
    [false, true, 'Conversation active'],
    [true, true, 'Generating interface'],
  ]) {
    const markup = renderToStaticMarkup(createElement(AppHeader, { busy, hasConversation }));
    assert.match(markup, /A2UI <strong>Studio<\/strong>/);
    assert.match(markup, /Turn an idea into an interface/);
    assert.match(markup, /viewBox="0 0 24 24"/);
    assert.ok(markup.includes(status));
  }
});

test('preview artwork remains a decorative SVG', () => {
  const markup = renderToStaticMarkup(createElement(PreviewIllustration));
  assert.match(markup, /viewBox="0 0 160 112"/);
  assert.match(markup, /aria-hidden="true"/);
});

test('agent notes retain their placeholder and render complete streamed text as text', () => {
  const empty = renderToStaticMarkup(createElement(AgentNotes, { busy: false, text: '' }));
  assert.match(empty, /A little context from your agent/);

  const text = renderToStaticMarkup(createElement(AgentNotes, {
    busy: true, text: 'Here is a form.\n<script>not HTML</script>',
  }));
  assert.match(text, /Responding\.\.\./);
  assert.match(text, /Here is a form\.\n&lt;script&gt;not HTML&lt;\/script&gt;/);
});
