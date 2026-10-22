# A2UI Agent App

A2A agent that streams A2UI (agent-driven UI). The LLM side is a Google ADK `LlmAgent`
(Gemini natively, OpenAI via LiteLLM); the A2A server, catalog negotiation, validation/retry
and surface repair wrap around it.

```
src/a2ui_agent_app/
  _protocol.py            AgentContextProvider: what the agent needs from its host (catalog prompt)
  agents/                 AgentConfig (Pydantic) + UiAgent (ADK LlmAgent)
    ui/                   agent, static instructions (role/rules), dynamic instruction provider
  a2ui_ext/               A2UI-over-A2A: extension URI, negotiation, DataPart builder,
                          repair_surfaces, action_to_text
  server/                 Settings (env / .env), A2A executor, UiBrain (ADK Runner + validate/retry),
                          Starlette app + `main`
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
