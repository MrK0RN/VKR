#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

.venv/bin/pytest tests/test_smoke.py tests/test_petri_engine.py tests/test_hodgkin_scenarios.py -v --tb=short
echo "Smoke tests passed."
