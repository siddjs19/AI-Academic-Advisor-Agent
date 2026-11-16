#!/usr/bin/env bash
# One command: install deps, build the UI if missing, serve API + SPA on :8000.
set -euo pipefail
cd "$(dirname "$0")"

if ! python -c "import fastapi" >/dev/null 2>&1; then
  echo "→ installing python deps"
  pip install -r backend/requirements.txt
fi

if [ ! -f frontend/dist/index.html ]; then
  echo "→ building the UI"
  npm --prefix frontend install --no-audit --no-fund
  npm --prefix frontend run build
fi

echo "→ http://127.0.0.1:8000   (demo: demo@preppilot.app / demo1234)"
cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
