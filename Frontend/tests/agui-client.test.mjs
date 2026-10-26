import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { createServer } from 'vite';

const vite = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
});
after(() => vite.close());
const { UiAgentClient, a2uiMessagesOf } = await vite.ssrLoadModule('/src/agui/client.ts');

const capabilities = {
  'v0.9': {
    supportedCatalogIds: ['test-catalog'],
    inlineCatalogs: [{ catalogId: 'test-catalog', components: {} }],
  },
};
const uiMessage = {
  version: 'v0.9',
  createSurface: { surfaceId: 'form', catalogId: 'test-catalog' },
};

function responseFor(input, { error = false, truncated = false } = {}) {
  const events = [
    { type: 'RUN_STARTED', threadId: input.threadId, runId: input.runId, protocolVersion: '1.0.0' },
    { type: 'TEXT_MESSAGE_START', messageId: input.runId, role: 'assistant' },
    { type: 'TEXT_MESSAGE_CONTENT', messageId: input.runId, delta: 'Hello \u00e9 \ud83c\udf0d' },
    { type: 'TEXT_MESSAGE_END', messageId: input.runId },
    { type: 'CUSTOM', name: 'a2ui', value: uiMessage },
  ];
  if (!truncated) {
    events.push(error
      ? { type: 'RUN_ERROR', message: 'Model unavailable', code: 'AGENT_ERROR' }
      : { type: 'RUN_FINISHED', threadId: input.threadId, runId: input.runId });
  }
  const bytes = new TextEncoder().encode(
    events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
  );
  let offset = 0;
  return new Response(new ReadableStream({
    pull(controller) {
      if (offset === bytes.length) return controller.close();
      // Exercise split SSE delimiters and split UTF-8 sequences through the real SDK.
      controller.enqueue(bytes.slice(offset, offset + 1));
      offset++;
    },
  }), { headers: { 'Content-Type': 'text/event-stream' } });
}

test('SDK streams A2UI and text, sends capabilities/actions, and preserves thread/history', async () => {
  const client = new UiAgentClient('http://example.test/');
  const requests = [];
  const events = [];
  client.agent.fetch = async (url, init) => {
    assert.equal(url, 'http://example.test/');
    assert.equal(init.headers.Accept, 'text/event-stream');
    const input = JSON.parse(init.body);
    requests.push(input);
    return responseFor(input);
  };
  const traces = [];
  await client.run({
    text: 'a form', capabilities,
    onRequest: (request) => traces.push(request),
    onEvent: (event) => events.push(event),
  });
  const action = {
    version: 'v0.9',
    action: {
      name: 'submit', surfaceId: 'form', sourceComponentId: 'submit',
      timestamp: '2026-10-26T00:00:00Z', context: { name: 'Ada' },
    },
  };
  await client.run({
    text: 'USER_ACTION submit', capabilities, action, onEvent: () => {},
  });
  assert.deepEqual(requests[0].forwardedProps, { a2uiClientCapabilities: capabilities });
  assert.deepEqual(requests[1].forwardedProps.a2uiAction, action);
  assert.equal(requests[0].threadId, requests[1].threadId);
  assert.notEqual(requests[0].runId, requests[1].runId);
  assert.equal(requests[1].messages[0].content, 'a form');
  assert.equal(requests[1].messages.at(-1).content, 'USER_ACTION submit');
  assert.ok(requests[1].messages.some((message) => message.role === 'assistant'));
  assert.equal(traces[0].body.runId, requests[0].runId);
  assert.ok(!('jsonrpc' in requests[0]));
  assert.equal(events.find((event) => event.type === 'TEXT_MESSAGE_CONTENT').delta, 'Hello \u00e9 \ud83c\udf0d');
  assert.deepEqual(events.flatMap(a2uiMessagesOf), [uiMessage]);
  const other = new UiAgentClient();
  assert.notEqual(other.agent.threadId, client.agent.threadId);
  assert.deepEqual(other.agent.messages, []);
});

test('RUN_ERROR reaches the caller rather than reporting success', async () => {
  const client = new UiAgentClient();
  client.agent.fetch = async (_url, init) => responseFor(JSON.parse(init.body), { error: true });
  await assert.rejects(
    client.run({ text: 'hi', capabilities, onEvent: () => {} }),
    /Model unavailable/,
  );
});

test('truncated streams fail explicitly', async () => {
  const client = new UiAgentClient();
  client.agent.fetch = async (_url, init) => responseFor(JSON.parse(init.body), { truncated: true });
  await assert.rejects(
    client.run({ text: 'hi', capabilities, onEvent: () => {} }),
    /finished|RUN_FINISHED|terminated|ended|terminal/i,
  );
});

test('HTTP failures and malformed SSE fail explicitly', async () => {
  for (const response of [
    new Response('Invalid capabilities', { status: 422 }),
    new Response('data: {not json}\n\n', { headers: { 'Content-Type': 'text/event-stream' } }),
  ]) {
    const client = new UiAgentClient();
    client.agent.fetch = async () => response;
    await assert.rejects(client.run({ text: 'hi', capabilities, onEvent: () => {} }));
  }
});

test('A2UI custom payload validation rejects malformed messages and ignores other extensions', () => {
  assert.deepEqual(a2uiMessagesOf({ type: 'CUSTOM', name: 'another-extension', value: null }), []);
  assert.deepEqual(a2uiMessagesOf({ type: 'RUN_STARTED', threadId: 't', runId: 'r' }), []);
  for (const value of [null, [], {}, { version: 'v0.9' }, { ...uiMessage, version: 'v9' }]) {
    assert.throws(() => a2uiMessagesOf({ type: 'CUSTOM', name: 'a2ui', value }));
  }
});

test('renderer callback failures reach the caller', async () => {
  const client = new UiAgentClient();
  client.agent.fetch = async (_url, init) => responseFor(JSON.parse(init.body));
  await assert.rejects(client.run({
    text: 'hi', capabilities,
    onEvent: (event) => {
      if (event.type === 'CUSTOM') throw new Error('Invalid renderer payload');
    },
  }), /Invalid renderer payload/);
});

test('request inspector callback failures reach the caller', async () => {
  const client = new UiAgentClient();
  client.agent.fetch = async (_url, init) => responseFor(JSON.parse(init.body));
  await assert.rejects(client.run({
    text: 'hi', capabilities, onEvent: () => {},
    onRequest: () => { throw new Error('Inspector failed'); },
  }), /Inspector failed/);
});
