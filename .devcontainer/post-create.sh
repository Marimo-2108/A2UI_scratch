#!/usr/bin/env bash
# Runs once after the container is created. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# uv (Python package manager used by this project)
if ! command -v uv >/dev/null 2>&1; then
  pip install --user --no-cache-dir uv
fi
export PATH="$HOME/.local/bin:$PATH"

# Agent deps (two A2UI packages are fetched from GitHub, pinned to a commit)
cd "$ROOT/Backend"
[ -f .env ] || cp .env.example .env
uv sync

# Web deps
cd "$ROOT/Frontend"
npm install

cat <<'EOF'

Ready. Open two terminals:
  Backend:  cd Backend && uv run a2ui-agent             (http://localhost:10010)
  Frontend: cd Frontend && npm run dev -- --host         (http://localhost:5173)

Fill in LLM (Azure deployment + api_key / api_base / api_version)
in Backend/.env; the agent needs it to start.
EOF
