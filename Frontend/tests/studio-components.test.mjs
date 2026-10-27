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
