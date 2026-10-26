# A2UI Agent App

AG-UI server that streams A2UI (agent-driven UI). The LLM side is a Google ADK `LlmAgent`
(Azure-hosted model via LiteLLM); the AG-UI server, catalog negotiation, validation/retry
and surface repair wrap around it.

```
src/a2ui_agent_app/
  agents/
    agent.py              create_agent(): ADK LlmAgent + LiteLlm (Azure)
    config.py             AgentConfig: LiteLLM config (LLM), GENERATE_CONTENT from .env
    system-prompt.txt     Role and rules for generating A2UI
  server.py               Entry point: POST run endpoint, input validation, SSE and CORS
  settings.py             Server settings, extending AgentConfig (no config translation layer)
  executor.py             AG-UI run -> user text/action -> UiRunner -> run/text/custom events
  runner.py               ADK sessions, per-request catalog prompt, validation/retry loop
  a2ui.py                 Transport-independent catalog setup, actions and surface repair
tests/                    unit tests (pytest)
tests/manual/             try_agent / repro_kpi / list_models CLIs, `ui_agent` for `adk web`
fixtures/                 catalogs exported from the web app (`npm run export:caps`)
```

```bash
cp .env.example .env                          # then fill in LLM (Azure)
uv sync
uv run a2ui-agent                             # http://localhost:10010
uv run pytest
uv run python tests/manual/try_agent.py "a small signup form"
uv run adk web tests/manual                   # the bare ADK agent in ADK's dev UI
```

Run these commands from `Backend/` so settings can read `.env`. The server always uses an LLM;
`LLM` must be set in `.env`. It mirrors the
[adk-openui-example](https://github.com/ksachdeva/adk-openui-example) config:
`LiteLlm(model=model_name, **provider_args)`, where `model_name` is `azure/<deployment>` and
`provider_args` holds `api_key`, `api_base`, `api_version` (plus optional `timeout`, `num_retries`,
`reasoning_effort`). Only Azure models are accepted. The tests use a fake model and need neither credentials nor network access.

## Follow one request

1. `server.main()` loads settings and builds the HTTP app with an AG-UI `UiExecutor`.
2. `POST /` validates a standard AG-UI `RunAgentInput` and our `forwardedProps` contract:
   required `a2uiClientCapabilities` and optional structured `a2uiAction`.
   The last message must be a non-empty text user message. Invalid input returns HTTP 422.
   Overlapping runs on the same thread return HTTP 409.
3. `UiExecutor.execute()` emits `RUN_STARTED` and extracts text or a button action.
   Actions become `USER_ACTION {...}` text for the model.
4. `UiRunner.respond()` negotiates the client's catalog using the A2UI SDK.
5. The ADK runner calls the agent with the system prompt and negotiated catalog schema.
   The schema is passed through invocation-local `temp:` state, without a custom provider layer.
6. The model returns text and an `<a2ui-json>` block. The A2UI SDK parses and validates it.
   Invalid output gets a bounded retry with the validation error.
7. Surface repair reconciles valid messages with the client's screen, logging any changes.
   The executor sends each A2UI message as `CUSTOM {name: "a2ui", value: <message>}`.
   Text uses `TEXT_MESSAGE_START/CONTENT/END`. Success ends with `RUN_FINISHED`;
   failures are logged and end with `RUN_ERROR`, never a success event.

The ADK event stream is explicitly closed in the consuming task, including on errors and
cancellation, so tracing context cleanup does not get deferred to a different async context.
An Azure request returning HTML titled "Blocked by Cloudflare Gateway" is a network-policy
failure, not a model context-window error; ask IT to approve the Azure endpoint.

ADK conversation history is keyed by AG-UI `threadId`. A follow-up or button click uses the same
thread and a new `runId`; a new conversation gets a new thread. History and known surfaces are in memory only.
Rejected model attempts and correction messages remain in the history.
The server advances its existing ADK session with the latest user turn; it does not replay the
client's full message list or restore a lost session after a restart.

There is no agent-card endpoint, JSON-RPC envelope or extension header.
The pinned A2UI SDK still brings `a2a-sdk` as a transitive dependency, but application code
does not import or serve A2A. See [the migration record](../docs/07-agui-migration.md).
