# A2UI Agent App

A2A agent that streams A2UI (agent-driven UI). The LLM side is a Google ADK `LlmAgent`
(Gemini natively, OpenAI via LiteLLM); the A2A server, catalog negotiation, validation/retry
and surface repair wrap around it.

```
src/a2ui_agent_app/
  agents/
    agent.py              create_agent(): ADK LlmAgent + Gemini or OpenAI model
    config.py             AgentConfig: model, keys and generation settings from .env
    system-prompt.txt     Role and rules for generating A2UI
  server.py               Entry point: agent card, HTTP app and CORS
  settings.py             Server settings, extending AgentConfig (no config translation layer)
  executor.py             A2A request -> user text/action -> UiRunner -> streamed task updates
  runner.py               ADK sessions, per-request catalog prompt, validation/retry loop
  a2ui.py                 Catalog negotiation, A2A DataParts, actions and surface repair
tests/                    unit tests (pytest)
tests/manual/             try_agent / repro_kpi / list_models CLIs, `ui_agent` for `adk web`
fixtures/                 catalogs exported from the web app (`npm run export:caps`)
```

```bash
cp .env.example .env                          # then set LLM_PROVIDER / API key
uv sync
uv run a2ui-agent                             # http://localhost:10010
uv run pytest
uv run python tests/manual/try_agent.py "a small signup form"
uv run adk web tests/manual                   # the bare ADK agent in ADK's dev UI
```

Run these commands from `Backend/` so settings can read `.env`. The server always uses an LLM;
an API key is required. The tests use a fake model and need neither credentials nor network access.

## Follow one request

1. `server.main()` loads settings and builds the HTTP app with an A2A `UiExecutor`.
2. `UiExecutor.execute()` receives a message, checks the A2UI extension and extracts text or a
   button action. Actions become `USER_ACTION {...}` text.
3. `UiRunner.respond()` negotiates the client's catalog using the A2UI SDK.
4. The ADK runner calls the agent with the system prompt and negotiated catalog schema.
   The schema is passed through invocation-local `temp:` state, without a custom provider layer.
5. The model returns text and an `<a2ui-json>` block. The A2UI SDK parses and validates it.
   Invalid output gets a bounded retry with the validation error.
6. Surface repair reconciles valid messages with the client's screen, logging any changes.
   The executor streams each A2UI message back as an A2A DataPart.

ADK conversation history is keyed by A2A `contextId`. A follow-up or button click uses the same
context; a new conversation gets a new context. History and known surfaces are in memory only.
Rejected model attempts and correction messages remain in the history.
