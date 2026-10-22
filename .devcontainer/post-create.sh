#!/usr/bin/env bash
# Runs once after the container is created. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Named volumes are created root-owned; hand them to the dev user.
sudo chown -R "$(id -u):$(id -g)" "$ROOT/agent/.venv" "$ROOT/web/node_modules"

# uv (Python package manager used by this project)
if ! command -v uv >/dev/null 2>&1; then
  pip install --user --no-cache-dir uv
fi
export PATH="$HOME/.local/bin:$PATH"

# Agent deps (two A2UI packages are fetched from GitHub, pinned to a commit)
cd "$ROOT/agent"
[ -f .env ] || cp .env.example .env
uv sync

# Web deps
cd "$ROOT/web"
npm install

cat <<'EOF'

Ready. Open two terminals:
  agent:  cd agent && uv run a2ui-agent             (http://localhost:10010)
  web:    cd web && npm run dev -- --host         (http://localhost:5173)

Set GEMINI_API_KEY (or LLM_PROVIDER=openai + OPENAI_API_KEY / OPENAI_MODEL)
in agent/.env; the agent needs an API key to start.
EOF
