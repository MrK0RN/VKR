#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

echo "→ http://${HOST}:${PORT}/"
exec .venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
