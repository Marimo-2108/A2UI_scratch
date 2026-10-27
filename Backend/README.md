# A2UI Agent App

AG-UI server that streams A2UI (agent-driven UI). Same shape as
[adk-openui-example](https://github.com/ksachdeva/adk-openui-example), with A2UI instead of OpenUI:
a server config, an agent config, the agent, and one route.

```
src/a2ui_agent_app/
  main.py                 Entry point: load config (clear error if invalid), start uvicorn
  _config.py              BackendConfig: server settings + LLM config, read from .env
  _app.py                 App(FastAPI): CORS, /health, load catalog, build LiteLlm + UiAgent, register route
  agents/
    _config.py            LiteLlmConfig: model_name + provider_args (Azure)
    _ui_agent.py          UiAgent: ADK LlmAgent + the A2UI SDK's send_a2ui_json_to_client tool
    system-prompt.txt     Role and rules for generating A2UI
  api/
    _health.py            GET /health
    _ui_agent.py          POST /: the agent over AG-UI (ag_ui_adk)
tests/test_app.py         end-to-end tests with a fake LLM (no credentials or network)
fixtures/stats-v1.catalog.json   the component catalog (basic components + StatCard)
```

```bash
cp .env.example .env                          # then fill in LLM (Azure)
uv sync
uv run a2ui-agent                             # http://localhost:10010
uv run pytest
```

Run these commands from `Backend/` so `.env` and `fixtures/` are found.
`LLM` mirrors the reference repo: `LiteLlm(model=model_name, **provider_args)`, where `model_name`
is `azure/<deployment>` and `provider_args` holds `api_key`, `api_base`, `api_version` (plus
optional `timeout` (default 60), `num_retries` (default 3), `reasoning_effort`).
For GPT-5.4+ deployments set `"reasoning_effort": "none"`: otherwise LiteLLM switches to Azure's
Responses API (needs `api_version` 2025-03-01-preview or later) and returns the text and the A2UI
tool call as separate choices; ADK reads only the first, so the UI is silently dropped.

## Follow one request

1. The browser sends an AG-UI `RunAgentInput` to `POST /`.
2. `ag_ui_adk` maps the `threadId` to an in-memory ADK session and runs `UiAgent` with the new user message.
3. The A2UI toolset adds the catalog's JSON schema to the system prompt. The model replies with a
   short sentence and calls `send_a2ui_json_to_client` with the A2UI messages.
4. The tool validates the JSON against the catalog. If it is invalid, the tool returns `{"error": ...}`
   and the model fixes it and calls again. If it is valid, the tool returns `{"validated_a2ui_json": [...]}`
   and the turn ends.
5. `ag_ui_adk` streams AG-UI events: `RUN_STARTED`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`,
   `TOOL_CALL_RESULT` (the tool result, which the browser renders), `RUN_FINISHED`.
   Any failure ends with `RUN_ERROR` and nothing after it.

Button clicks arrive as normal user messages: `USER_ACTION {...}`.
History lives in memory per `threadId` and is lost when the server restarts.

The catalog is fixed on the backend. After changing the frontend catalog, regenerate it with
`npm run export:caps` in `Frontend/` (needs Node 22.6+).

## Errors

- Bad or missing `.env` values: `uv run a2ui-agent` exits with a message naming the field.
- LLM failures (bad key, wrong deployment, network): the run ends with `RUN_ERROR` and the UI shows it.
- `... returned 'Blocked by Cloudflare Gateway' ...`: the company network blocks the Azure endpoint.
  This is not a code problem; ask IT to approve the endpoint.
