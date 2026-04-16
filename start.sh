#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-5050}"

# Activate virtual environment if present
if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

echo "Starting Outcome Readiness Dashboard on http://localhost:${PORT}"
python dashboard.py --port "$PORT"
