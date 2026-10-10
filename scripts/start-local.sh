#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
python3 scripts/configure.py
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm ci)
(cd backend && "$ROOT/.venv/bin/alembic" upgrade head && "$ROOT/.venv/bin/python" -m app.seed)
(cd backend && exec "$ROOT/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT INT TERM
cd frontend
npm run build
npm run start -- --hostname 127.0.0.1
