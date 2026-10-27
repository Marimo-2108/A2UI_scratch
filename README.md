# A2UI Scratch

A learning/prototyping project for [A2UI](https://a2ui.org) (agent-to-UI). An AI agent streams declarative UI over [AG-UI](https://docs.ag-ui.com), and a React app renders it with a custom component catalog.

- [Backend/](./Backend/README.md) – Python AG-UI server. A Google ADK agent (Azure-hosted model via LiteLLM) decides the UI.
- [Frontend/](./Frontend/README.md) – React + Vite client with a wire inspector and a custom catalog.
- [docs/](./docs/) – Learning notes and historical experiments; start with the current workflow below.

## Follow the workflow

```text
React prompt
  -> AG-UI RunAgentInput (POST /)
  -> ag_ui_adk -> ADK agent + system prompt + catalog schema (fixed on the backend)
  -> model calls send_a2ui_json_to_client with A2UI JSON
  -> the A2UI SDK tool validates it (the model retries on error)
  -> AG-UI SSE events (text + TOOL_CALL_RESULT carrying the validated A2UI messages)
  -> React MessageProcessor -> rendered UI
  -> button action -> "USER_ACTION {...}" message in the same conversation
```

Read the files in this order:

1. [Frontend/src/App.tsx](./Frontend/src/App.tsx): prompt, conversation and rendered surfaces.
2. [Frontend/src/agui/client.ts](./Frontend/src/agui/client.ts): official AG-UI HTTP client; reads A2UI from tool results.
3. [Backend/main.py](./Backend/src/a2ui_agent_app/main.py) and [Backend/_config.py](./Backend/src/a2ui_agent_app/_config.py): entry point and settings.
4. [Backend/_app.py](./Backend/src/a2ui_agent_app/_app.py): the FastAPI app, model and agent setup.
5. [agents/_ui_agent.py](./Backend/src/a2ui_agent_app/agents/_ui_agent.py) and
   [system-prompt.txt](./Backend/src/a2ui_agent_app/agents/system-prompt.txt): the agent and its instructions.
6. [api/_ui_agent.py](./Backend/src/a2ui_agent_app/api/_ui_agent.py): the AG-UI route.

For a custom-component example, follow
[myCatalog.ts](./Frontend/src/catalog/myCatalog.ts) to [StatCard.tsx](./Frontend/src/catalog/StatCard.tsx).
The backend's catalog file is generated from it with `npm run export:caps`.

## Quick start (dev container, recommended)

Only [Docker](https://www.docker.com/) and VS Code/Cursor with the Dev Containers extension are needed. No local Python, uv or Node.

The [Dockerfile](.devcontainer/Dockerfile) installs the organization's Cloudflare Gateway CA into the system trust store during the image build, before editor extensions or dependency installation run. Before the first build, place your IT-approved PEM-encoded CA certificate at `.devcontainer/cloudflare-root.crt`. This local file is Git-ignored and required by the build; use your organization's certificate, not one copied from another repository. Node uses the additional CA, and `UV_SYSTEM_CERTS=true` enables system certificate trust for uv. There is no `SSL_CERT_FILE` override; Python libraries that use their own CA bundles may need library-specific configuration.

1. Open this folder and run **Dev Containers: Reopen in Container**. First build installs everything (`.devcontainer/post-create.sh`) and creates `Backend/.env` from the example.
2. Edit `Backend/.env` and fill in `LLM` (Azure deployment as `azure/<deployment>`, plus `api_key`, `api_base`, `api_version` in `provider_args`).
3. In two terminals: `cd Backend && uv run a2ui-agent` and `cd Frontend && npm run dev`.
4. Open http://localhost:5173. VS Code detects listening server processes and forwards their ports automatically; check the Ports panel for the actual local addresses if a port is already occupied. Set `VITE_AGENT_URL` to the backend's forwarded address if it is not localhost:10010, then restart Vite.

VS Code mounts the project folder automatically; no explicit dependency mounts are needed. Dependencies are installed into `Backend/.venv` and `Frontend/node_modules` in that folder. Avoid sharing these directories with a Windows install. After switching from the old named volumes, the post-create script installs dependencies in the workspace; the old Docker volumes are no longer used and are not deleted automatically. Ports use VS Code's default labels and browser-opening behavior.

After changing the certificate or dev container configuration, run **Dev Containers: Rebuild and Reopen in Container** (or **Rebuild Container** if already attached). Reopening a terminal alone does not rebuild the image or restart all extension processes with the new certificate settings. The post-create script installs application dependencies; it no longer modifies certificate trust.

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

In `.env`, set `LLM` to a LiteLLM config for your Azure deployment, e.g.
`LLM={"model_name": "azure/<deployment>", "provider_args": {"api_key": "...", "api_base": "https://<resource>.openai.azure.com/", "api_version": "2025-04-01-preview"}}`.
`api_key`, `api_base` and `api_version` are required. Never commit `.env`.

Quick check without a browser: `curl http://localhost:10010/health`.

### 2. Web

```
cd Frontend
npm install
npm run dev                # http://localhost:5173
```

Open the app and start a new conversation.

If you change the custom catalog, regenerate the backend's catalog with `npm run export:caps` (in `Frontend/`, needs Node 22.6+), then restart the agent.

## Tests

```
cd Backend
uv run pytest
```

```bash
cd Frontend
npm test
npm run build
npm run lint
```

Tests use a fake LLM or mock HTTP streams; they do not need API keys.
See [the glossary](./docs/00-glossary.md) and [Backend/README.md](./Backend/README.md) for the current flow.
Milestone notes in `docs/` are historical where marked.
