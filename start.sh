#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-5050}"
SCAN_PORT="${SCAN_AGENT_PORT:-8088}"
INTAKE_PORT="${INTAKE_AGENT_PORT:-8087}"

# Activate virtual environment if present
if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

# Clean up any agents from a previous run on the same ports
pkill -f "python.*agent.py"               2>/dev/null || true
pkill -f "python.*agents/intake_agent.py" 2>/dev/null || true

cleanup() {
  echo ""
  echo "Stopping agents..."
  kill $SCAN_PID $INTAKE_PID 2>/dev/null || true
  wait $SCAN_PID $INTAKE_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting Outcome Extraction Agent on http://localhost:${SCAN_PORT}"
python agent.py &
SCAN_PID=$!

echo "Starting Intake Agent on http://localhost:${INTAKE_PORT}"
python agents/intake_agent.py &
INTAKE_PID=$!

# Give the agents a moment to bind their ports
sleep 3

echo "Starting Outcome Readiness Dashboard on http://localhost:${PORT}"
python dashboard.py --port "$PORT"
