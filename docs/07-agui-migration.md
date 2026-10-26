# A2A -> AG-UI migration

## Status

The browser/server transport has migrated to AG-UI 1.0 over HTTP/SSE.
A2UI remains the declarative UI format; Google ADK remains the agent runtime.
This is a breaking wire change, with no A2A compatibility endpoint.

| Work | Status |
|---|---|
| Replace A2A HTTP server with validated AG-UI `POST /` | Complete |
| Emit standard AG-UI run and text events | Complete |
| Carry validated A2UI messages through custom events | Complete |
| Replace hand-written browser SSE parser with official `HttpAgent` | Complete |
| Preserve inline catalogs, validation/retry, actions, history and surfaces | Complete |
| Remove application A2A imports, agent card, extension negotiation and task store | Complete |
| Update manual clients, READMEs and learning notes | Complete |
| Fake-model backend regression tests and browser SDK tests | Passing; see verification below |
| Browser rendering/action/follow-up/new-thread and CLI smoke tests | Passed with a stubbed model response |
| Live-provider smoke test | Not performed; requires configured credentials and external LLM access |

## Why this split

AG-UI describes agent/frontend interaction: run identity, messages, events and errors.
A2UI describes what the frontend renders. Neither replaces the other.
The migration does not add CopilotKit, replace the custom catalog, or change model providers.

We use `ag-ui-protocol` 1.0.0 for Python models/encoding and `@ag-ui/client` /
`@ag-ui/core` 1.0.3 in the browser. The application-specific `a2ui` event name and
`forwardedProps` keys below are our explicit contract, not standardized AG-UI fields.

## Current wire contract

### Request: `POST /`

```json
{
  "threadId": "conversation-1",
  "runId": "run-1",
  "protocolVersion": "1.0.0",
  "messages": [
    {"id": "user-1", "role": "user", "content": "a small signup form"}
  ],
  "forwardedProps": {
    "a2uiClientCapabilities": {
      "v0.9": {
        "supportedCatalogIds": [
          "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
        ]
      }
    }
  }
}
```

The browser includes the catalog's inline schema in capabilities, as before.
New conversations generate a new `threadId`; follow-ups reuse it with a fresh `runId`.
The SDK maintains and sends user/assistant message history.

The backend continues its in-memory ADK session using the **latest user turn**, not by
replaying the full list on every run. ADK retains extra internal validation/correction turns
that the browser does not see. Incoming client history is not a session-restoration mechanism.

### Response: `text/event-stream`

```text
data: {"type":"RUN_STARTED","threadId":"conversation-1","runId":"run-1","protocolVersion":"1.0.0"}

data: {"type":"TEXT_MESSAGE_START","messageId":"assistant-1","role":"assistant"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"assistant-1","delta":"Here is your form."}

data: {"type":"TEXT_MESSAGE_END","messageId":"assistant-1"}

data: {"type":"CUSTOM","name":"a2ui","value":{"version":"v0.9","createSurface":{"surfaceId":"form","catalogId":"https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"}}}

data: {"type":"RUN_FINISHED","threadId":"conversation-1","runId":"run-1"}

```

Each A2UI message is one custom event. `updateComponents`, `updateDataModel` and
`deleteSurface` use the same wrapper. Text/progress messages each have their own unique ID and
balanced start/content/end events. The actual run also sends the existing "Thinking..." message.

Successful runs end with `RUN_FINISHED`; subsequent user input starts another run in the same
thread. There is no A2A `input-required` task state, and ordinary button actions do not require
an AG-UI interrupt/resume workflow.

### Actions

Button clicks add the following to `forwardedProps`, alongside capabilities:

```json
{
  "a2uiAction": {
    "version": "v0.9",
    "action": {
      "name": "submit",
      "surfaceId": "form",
      "sourceComponentId": "submit-button",
      "timestamp": "2026-10-26T12:00:00Z",
      "context": {"name": "Ada"}
    }
  }
}
```

The request also includes a user message describing that action. The backend uses the
validated structured action as the model input, preserving the previous `USER_ACTION {...}`
conversion. The existing processor handles bound values and surface updates.

### Errors and concurrency

- Malformed JSON, invalid AG-UI input, missing capabilities, malformed action envelopes,
  empty identifiers or a missing/non-text/empty latest user message return HTTP 422
  **before** streaming starts.
- Unsupported catalogs and model/validation failures are logged and end the stream with
  `RUN_ERROR`. No `RUN_FINISHED` follows a failed run.
- HTTP failures, malformed streams, missing terminal events and renderer/subscriber errors
  surface to the app's error panel, rather than looking like success.
- The browser rejects overlapping actions. The backend also returns HTTP 409 for overlapping
  runs on a thread and releases the thread when the stream finishes, fails or closes.
- CORS permits the configured frontend origins, `POST`, and `Content-Type` / `Accept`.
  No extension header is sent or exposed.

## Changed, removed and preserved

| Area | Before | After |
|---|---|---|
| HTTP input | JSON-RPC `message/stream` | AG-UI `RunAgentInput` |
| Browser client | Hand-written SSE parser in `src/a2a/client.ts` | Official SDK wrapper in [src/agui/client.ts](../Frontend/src/agui/client.ts) |
| UI payload | A2A `DataPart` plus MIME metadata | `CUSTOM`, name `a2ui`, value = one A2UI message |
| Conversation identity | A2A `contextId` | AG-UI `threadId` |
| Work identity | A2A task ID | AG-UI `runId` |
| Lifecycle | Task/status updates and `input-required` | `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR` |
| Catalog input | `message.metadata.a2uiClientCapabilities` | `forwardedProps.a2uiClientCapabilities` |
| Action input | A2A DataPart | `forwardedProps.a2uiAction` |
| Discovery/opt-in | Agent card and `X-A2A-Extensions` | Removed; endpoint configured with `VITE_AGENT_URL` |
| Task persistence | A2A in-memory task store | Removed; ADK sessions remain |
| Runner output | A2A `Part` objects | Transport-independent text or A2UI dictionaries |
| Dependencies | Direct `a2a-sdk[http-server]` | Direct `ag-ui-protocol` and `starlette`; browser AG-UI SDKs |

**Preserved:** A2UI v0.9, React `MessageProcessor` / `A2uiSurface`, basic/custom catalogs,
inline schema negotiation, Gemini/OpenAI selection, model prompts, bounded output validation
and retry, surface repair, ADK memory, follow-ups, button actions, wire inspector, port,
launch command and existing configuration names.

**Dependency caveat:** the pinned `a2ui-agent-sdk` itself requires `a2a-sdk`. That package
therefore remains in the Python lockfile transitively. Application code no longer imports
`a2a` or `a2ui.a2a`. Removing the transitive dependency requires an upstream packaging change
or replacing the A2UI SDK; it is not necessary to remove A2A from the application protocol.

## Verification

Commands from the repository root:

```bash
cd Backend && uv run pytest
cd ../Frontend && npm test
npm run build
npm run lint
```

Verified:

- 28 backend tests: fake-model ADK execution, retry bounds, validation failures, catalog
  negotiation, inline schemas, history, thread isolation, actions, surface repair, AG-UI event
  schemas/identity/order, invalid inputs, legacy request rejection, CORS, overlapping runs
  and recovery after failures.
- 7 browser client tests using the **real AG-UI SDK** against mock HTTP responses:
  byte-fragmented SSE/UTF-8, text/custom events, outgoing capabilities and actions,
  conversation history, new-thread isolation, HTTP errors, `RUN_ERROR`, malformed/truncated
  streams and renderer/request-inspector callback failures.
- Frontend TypeScript check, production build and configured lint command.
- Browser smoke test against the running HTTP server with a stubbed model response:
  initial rendering, a real rendered Button click, the structured action reaching the backend,
  an updated surface, a follow-up on the same thread, and a new conversation on a fresh thread.
  The browser reported no application errors. Temporary test servers were stopped afterward.
- Migrated `tests/manual/try_agent.py --caps` received text, A2UI messages and `RUN_FINISHED`
  from that server.

The SDK logs and swallows subscriber exceptions, so our wrapper captures event-handler
errors and rejects the run promise explicitly. This behavior is covered by a regression test.

The Python encoder writes LF-separated SSE. Testing CRLF-separated, byte-fragmented SSE
exposed a parser limitation in `@ag-ui/client` 1.0.3; this application uses and tests the
encoder's LF framing rather than introducing another handwritten parser.

## Remaining limits / follow-up work

- ADK sessions and surface tracking remain in memory. Restarting the backend loses them;
  start a new conversation after a restart. Durable sessions and history rehydration are not
  part of this transport migration.
- The frontend still waits for model output validation before receiving UI updates. This
  migration does not introduce model-token streaming or incremental unvalidated UI.
- Shared-state synchronization, frontend tool execution, interrupt/resume, authentication,
  multi-worker coordination and replay/idempotency are not implemented by this prototype.
  AG-UI provides relevant protocol building blocks, not those application features automatically.
- Concurrent-run exclusion is process-local, matching the existing in-memory session model.
- The frontend build warns about bundle size. Dependency installation also reports npm
  advisories; unrelated dependency upgrades are not included in this migration.

## Sources and historical notes

- [AG-UI run input](https://docs.ag-ui.com/spec/1.0/basic/run-input)
- [AG-UI run lifecycle](https://docs.ag-ui.com/spec/1.0/events/lifecycle)
- [AG-UI generative UI specifications](https://docs.ag-ui.com/concepts/generative-ui-specs)
- [Historical A2A milestone](./02-a2a-transport.md) (not instructions for the current app)
