# A2UI Scratch

A learning/prototyping project for [A2UI](https://a2ui.org) (agent-to-UI). An AI agent streams declarative UI over the A2A protocol, and a React app renders it with a custom component catalog.

- `agent/` – Python A2A server. Runs in `scripted` mode (fixed UI, no key needed) or `llm` mode (Gemini or OpenAI decides the UI).
- `web/` – React + Vite client using `@a2ui/react`, with demos and a custom catalog.
- `docs/` – Step-by-step notes (wire format, A2A transport, actions, Gemini, custom components, catalog scaling).

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Git (the agent installs two A2UI Python packages from GitHub, pinned to a commit). On Windows, if install fails with "Filename too long", run `git config --global core.longpaths true`.

## Run it

### 1. Agent

```
cd agent
copy .env.example .env     # macOS/Linux: cp .env.example .env
uv sync
uv run python server.py    # listens on http://localhost:10010
```

In `.env`, set `AGENT_MODE=scripted` to try it without an API key, or `AGENT_MODE=llm` with `GEMINI_API_KEY` (or `OPENAI_API_KEY` and `LLM_PROVIDER=openai`). Never commit `.env`.

Quick check without a browser:

```
uv run python try_agent.py "a small signup form"
```

### 2. Web

```
cd web
npm install
npm run dev                # http://localhost:5173
```

Open the live agent demo tab and start a new conversation.

If you change the custom catalog, regenerate the capabilities fixture the agent uses with `npm run export:caps` (in `web/`).

## Tests

```
cd agent
uv run --with pytest pytest
```

See `docs/` for how it all works, starting with `00-glossary.md`.
