import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { createServer } from 'vite';

const vite = await createServer({
  server: { middlewareMode: true, hmr: false },
  appType: 'custom',
});
after(() => vite.close());
const { UiAgentClient, a2uiMessagesOf } = await vite.ssrLoadModule('/src/agui/client.ts');
const { MessageProcessor } = await import('@a2ui/web_core/v0_9');
const { basicCatalog } = await import('@a2ui/web_core/v0_9/basic_catalog');

const uiMessage = {
  version: 'v0.9',
  createSurface: { surfaceId: 'form', catalogId: 'test-catalog' },
};

function toolResult(toolCallId, content) {
  return {
    type: 'TOOL_CALL_RESULT', messageId: `result-${toolCallId}`, toolCallId,
    content: JSON.stringify(content),
  };
}

function responseFor(input, { error = false, truncated = false } = {}) {
  const events = [
    { type: 'RUN_STARTED', threadId: input.threadId, runId: input.runId, protocolVersion: '1.0.0' },
    { type: 'TEXT_MESSAGE_START', messageId: input.runId, role: 'assistant' },
    { type: 'TEXT_MESSAGE_CONTENT', messageId: input.runId, delta: 'Hello \u00e9 \ud83c\udf0d' },
    { type: 'TEXT_MESSAGE_END', messageId: input.runId },
    { type: 'TOOL_CALL_START', toolCallId: 'bad', toolCallName: 'send_a2ui_json_to_client' },
    { type: 'TOOL_CALL_END', toolCallId: 'bad' },
    toolResult('bad', { error: 'Unrecognized component type' }),
    { type: 'TOOL_CALL_START', toolCallId: 'ok', toolCallName: 'send_a2ui_json_to_client' },
    { type: 'TOOL_CALL_END', toolCallId: 'ok' },
    toolResult('ok', { validated_a2ui_json: [uiMessage] }),
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

test('SDK streams A2UI tool results and text, and preserves thread/history', async () => {
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
    text: 'a form',
    onRequest: (request) => traces.push(request),
    onEvent: (event) => events.push(event),
  });
  await client.run({ text: 'USER_ACTION submit', onEvent: () => {} });
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
    client.run({ text: 'hi', onEvent: () => {} }),
    /Model unavailable/,
  );
});

test('truncated streams fail explicitly', async () => {
  const client = new UiAgentClient();
  client.agent.fetch = async (_url, init) => responseFor(JSON.parse(init.body), { truncated: true });
  await assert.rejects(
    client.run({ text: 'hi', onEvent: () => {} }),
    /finished|RUN_FINISHED|terminated|ended|terminal/i,
  );
});

test('HTTP failures and malformed SSE fail explicitly', async () => {
  for (const response of [
    new Response('Invalid input', { status: 422 }),
    new Response('data: {not json}\n\n', { headers: { 'Content-Type': 'text/event-stream' } }),
  ]) {
    const client = new UiAgentClient();
    client.agent.fetch = async () => response;
    await assert.rejects(client.run({ text: 'hi', onEvent: () => {} }));
  }
});

test('A2UI tool results: malformed validated payloads throw; errors and other events are ignored', () => {
  assert.deepEqual(a2uiMessagesOf(toolResult('x', { error: 'invalid' })), []);
  assert.deepEqual(a2uiMessagesOf(toolResult('x', { weather: 'sunny' })), []);
  assert.deepEqual(a2uiMessagesOf({ type: 'CUSTOM', name: 'a2ui', value: uiMessage }), []);
  assert.deepEqual(a2uiMessagesOf({ type: 'RUN_STARTED', threadId: 't', runId: 'r' }), []);
  for (const value of [
    null, [], {}, { version: 'v0.9' }, { ...uiMessage, version: 'v9' },
    { ...uiMessage, version: 'v0.9.1' },
    { version: 'v0.9', createSurface: {} },
    { ...uiMessage, deleteSurface: { surfaceId: 'form' } },
    { version: 'v0.9', updateComponents: { surfaceId: 'form', components: 'invalid' } },
    { version: 'v0.9', updateDataModel: { surfaceId: 123, value: {} } },
    { version: 'v0.9', deleteSurface: {} },
  ]) {
    assert.throws(() => a2uiMessagesOf(toolResult('x', { validated_a2ui_json: [value] })));
  }
});

test('all supported A2UI operations pass through to the real message processor', () => {
  const processor = new MessageProcessor([basicCatalog]);
  const messages = [
    { ...uiMessage, createSurface: { surfaceId: 'form', catalogId: basicCatalog.id } },
    {
      version: 'v0.9',
      updateComponents: {
        surfaceId: 'form',
        components: [{ id: 'root', component: 'Text', text: 'Hello' }],
      },
    },
    { version: 'v0.9', updateDataModel: { surfaceId: 'form', path: '/', value: { count: 1 } } },
  ];
  try {
    const parsed = a2uiMessagesOf(toolResult('x', { validated_a2ui_json: messages }));
    assert.deepEqual(parsed, messages);
    for (const message of parsed) processor.processMessages(message);
    assert.ok(processor.getSurface('form'));

    const deletion = { version: 'v0.9', deleteSurface: { surfaceId: 'form' } };
    const [message] = a2uiMessagesOf(toolResult('delete', { validated_a2ui_json: [deletion] }));
    assert.deepEqual(message, deletion);
    processor.processMessages(message);
    assert.equal(processor.getSurface('form'), undefined);
  } finally {
    processor.dispose();
  }
});

test('renderer callback failures reach the caller', async () => {
  const client = new UiAgentClient();
  client.agent.fetch = async (_url, init) => responseFor(JSON.parse(init.body));
  await assert.rejects(client.run({
    text: 'hi',
    onEvent: (event) => {
      if (event.type === 'TOOL_CALL_RESULT') throw new Error('Invalid renderer payload');
    },
  }), /Invalid renderer payload/);
});

test('request inspector callback failures reach the caller', async () => {
  const client = new UiAgentClient();
  client.agent.fetch = async (_url, init) => responseFor(JSON.parse(init.body));
  await assert.rejects(client.run({
    text: 'hi', onEvent: () => {},
    onRequest: () => { throw new Error('Inspector failed'); },
  }), /Inspector failed/);
});
