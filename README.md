# A2UI Scratch

A learning/prototyping project for [A2UI](https://a2ui.org) (agent-to-UI). An AI agent streams declarative UI over the A2A protocol, and a React app renders it with a custom component catalog.

- [Backend/](./Backend/README.md) – Python A2A server. A Google ADK agent (Gemini or OpenAI) decides the UI.
- [Frontend/](./Frontend/README.md) – React + Vite client with a wire inspector and a custom catalog.
- [docs/](./docs/) – Learning notes and historical experiments; start with the current workflow below.

## Follow the workflow

```text
React prompt
  -> A2A request (including the client's component catalog)
  -> ADK agent + system prompt + catalog schema
  -> model returns A2UI JSON
  -> validate, retry if needed, repair surface messages
  -> A2A response stream
  -> React MessageProcessor -> rendered UI
  -> button action -> another request in the same conversation
```

Read the files in this order:

1. [Frontend/src/App.tsx](./Frontend/src/App.tsx): prompt, conversation and rendered surfaces.
2. [Frontend/src/a2a/client.ts](./Frontend/src/a2a/client.ts): send a request and read the SSE response.
3. [Backend/server.py](./Backend/src/a2ui_agent_app/server.py): backend entry point and HTTP app.
4. [Backend/executor.py](./Backend/src/a2ui_agent_app/executor.py): incoming request to outgoing task updates.
5. [Backend/runner.py](./Backend/src/a2ui_agent_app/runner.py): catalog negotiation, ADK sessions and validation/retry.
6. [agents/agent.py](./Backend/src/a2ui_agent_app/agents/agent.py) and
   [system-prompt.txt](./Backend/src/a2ui_agent_app/agents/system-prompt.txt): model selection and instructions.
7. [Backend/a2ui.py](./Backend/src/a2ui_agent_app/a2ui.py): protocol helpers and surface repair.

For a custom-component example, follow
[myCatalog.ts](./Frontend/src/catalog/myCatalog.ts) to [StatCard.tsx](./Frontend/src/catalog/StatCard.tsx).
The browser sends the catalog schema inline so the backend can generate and validate that component.

## Quick start (dev container, recommended)

Only [Docker](https://www.docker.com/) and VS Code/Cursor with the Dev Containers extension are needed. No local Python, uv or Node.

1. Open this folder and run **Dev Containers: Reopen in Container**. First build installs everything (`.devcontainer/post-create.sh`) and creates `Backend/.env` from the example.
2. Edit `Backend/.env` and set an API key (`GEMINI_API_KEY`, or `OPENAI_API_KEY` + `OPENAI_MODEL` with `LLM_PROVIDER=openai`).
3. In two terminals: `cd Backend && uv run a2ui-agent` and `cd Frontend && npm run dev`.
4. Open http://localhost:5173 (ports 10010 and 5173 are forwarded automatically).

The container keeps `.venv` and `node_modules` in Docker volumes, so a host-side Windows install won't conflict.

## Prerequisites (manual setup, without the dev container)

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Git (the agent installs two A2UI Python packages from GitHub, pinned to a commit). On Windows, if install fails with "Filename too long", run `git config --global core.longpaths true`.

## Run it

### 1. Agent

```
cd Backend
copy .env.example .env     # macOS/Linux: cp .env.example .env
uv sync
uv run a2ui-agent         # listens on http://localhost:10010
```

In `.env`, set `GEMINI_API_KEY` (or `OPENAI_API_KEY`, `OPENAI_MODEL` and `LLM_PROVIDER=openai`). An API key is required. Never commit `.env`.

Quick check without a browser:

```
uv run python tests/manual/try_agent.py "a small signup form"
```

### 2. Web

```
cd Frontend
npm install
npm run dev                # http://localhost:5173
```

Open the app and start a new conversation.

If you change the custom catalog, regenerate the capabilities fixture the agent uses with `npm run export:caps` (in `Frontend/`).

## Tests

```
cd Backend
uv run pytest
```

See `docs/` for how it all works, starting with `00-glossary.md`.
