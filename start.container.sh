#!/usr/bin/env bash
# Container entrypoint: runs the 2 agent servers + dashboard in one container.
set -euo pipefail

APP_DIR="${APP_DIR:-$(pwd)}"
cd "$APP_DIR"
PYTHON_EXEC="${PYTHON_EXEC:-${PYTHON:-python3}}"

PORT="${PORT:-5050}"
HOST="${HOST:-0.0.0.0}"
SCAN_PORT="${SCAN_AGENT_PORT:-8088}"
INTAKE_PORT="${INTAKE_AGENT_PORT:-8087}"
DB_PATH="${DB_PATH:-/data/runs.db}"

mkdir -p "$(dirname "$DB_PATH")"

# Always initialise schema (CREATE TABLE IF NOT EXISTS is idempotent).
echo "[init] ensuring schema in $DB_PATH"
${PYTHON_EXEC} - <<PY
import sqlite3, os
db = os.environ["DB_PATH"]
con = sqlite3.connect(db)
con.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        run_id                       TEXT PRIMARY KEY,
        opportunity_id               TEXT NOT NULL,
        engagement_name              TEXT,
        recommendation               TEXT,
        status                       TEXT NOT NULL DEFAULT 'draft',
        pipeline_status              TEXT NOT NULL DEFAULT 'scanned',
        hours_saved                  REAL,
        summary                      TEXT,
        detected_outcomes            TEXT,
        missing_kpis                 TEXT,
        transformation_opportunities TEXT,
        agentic_opportunities        TEXT,
        created_at                   TEXT DEFAULT (datetime('now'))
    )
""")
con.commit()
con.close()
print(f"[init] schema ok: {db}")
PY

# Seed from sample_sows.json if the runs table is empty (fresh revision).
echo "[seed] checking if sample SoWs need to be loaded"
${PYTHON_EXEC} - <<'PY'
import sqlite3, json, os, uuid
from datetime import datetime, timezone

db        = os.environ["DB_PATH"]
sows_path = f"{os.environ.get('APP_DIR', '') or '/app'}/sample_sows.json"

con = sqlite3.connect(db)
count = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
if count > 0:
    print(f"[seed] skip — {count} rows already present")
    con.close()
    raise SystemExit(0)

if not os.path.exists(sows_path):
    print(f"[seed] skip — {sows_path} not found")
    con.close()
    raise SystemExit(0)

with open(sows_path, "r", encoding="utf-8") as f:
    entries = json.load(f)
sows = [e for e in entries if "opportunity_id" in e]

# Make sure columns the dashboard expects exist (older schema may be narrower).
existing = {r[1] for r in con.execute("PRAGMA table_info(runs)").fetchall()}
needed = {
    "sow_text":            "TEXT",
    "deal_size":           "REAL",
    "engagement_manager":  "TEXT",
    "value_attribution":   "TEXT",
    "revenue_gain":        "REAL",
    "intake_enriched":     "INTEGER DEFAULT 0",
    "reviewer_remarks":    "TEXT",
    "reviewer_name":       "TEXT",
    "reviewer_role":       "TEXT",
    "human_approved":      "INTEGER DEFAULT 0",
    "agent_name":          "TEXT",
    "agentic_opportunities":"TEXT",
}
for col, ddl in needed.items():
    if col not in existing:
        con.execute(f"ALTER TABLE runs ADD COLUMN {col} {ddl}")

now = datetime.now(timezone.utc).isoformat()
seeded = 0
for sow in sows:
    opp_id   = (sow.get("opportunity_id") or "").strip()
    if not opp_id:
        continue
    con.execute(
        """INSERT INTO runs (run_id, opportunity_id, engagement_name,
               pipeline_status, status, created_at, sow_text, deal_size)
           VALUES (?,?,?, 'intake', 'draft', ?, ?, ?)""",
        (uuid.uuid4().hex, opp_id, sow.get("engagement_name", ""),
         now, sow.get("sow_text", ""), sow.get("deal_size") or 0),
    )
    seeded += 1
con.commit()
con.close()
print(f"[seed] ✓ loaded {seeded} sample SoWs into {db}")
PY

term() {
  echo "[stop] forwarding signal"
  kill "$SCAN_PID" "$INTAKE_PID" 2>/dev/null || true
  wait "$SCAN_PID" "$INTAKE_PID" 2>/dev/null || true
  exit 0
}
trap term INT TERM

echo "[run] scan agent   → :${SCAN_PORT}"
${PYTHON_EXEC} agent.py &
SCAN_PID=$!

echo "[run] intake agent → :${INTAKE_PORT}"
${PYTHON_EXEC} agents/intake_agent.py &
INTAKE_PID=$!

# brief wait so the agents bind before the dashboard starts accepting traffic
sleep 3

echo "[run] dashboard    → http://${HOST}:${PORT}"
exec ${PYTHON_EXEC} dashboard.py --port "$PORT" --host "$HOST" --db "$DB_PATH"
