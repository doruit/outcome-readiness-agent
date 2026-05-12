"""
run_demo.py — Demo runner
--------------------------
Sends one SoW from sample_sows.json to the agent HTTP server, parses the
structured JSON response, logs the run to runs.db, and prints a summary.

Usage:
    # Run with all sample SoWs:
    python run_demo.py

    # Run with a specific SoW index (0-based):
    python run_demo.py --index 0

    # Run the same opportunity twice (demonstrates run_id uniqueness + no double coverage):
    python run_demo.py --index 0
    python run_demo.py --index 0

Prerequisites:
    - Agent server must be running:  python agent.py
    - runs.db must exist:            python setup_eval.py
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(override=False)

AGENT_URL = "http://localhost:8088/runs"
DB_PATH = "runs.db"
SOWS_FILE = "sample_sows.json"


def load_sows() -> list:
    with open(SOWS_FILE) as f:
        return json.load(f)


def ensure_schema() -> None:
    """Idempotent migrations — add columns introduced after initial schema."""
    con = sqlite3.connect(DB_PATH)
    for col, definition in [
        ("foundry_conv_id",              "TEXT"),
        ("pipeline_status",              "TEXT DEFAULT 'scanned'"),
        ("summary",                      "TEXT"),
        ("detected_outcomes",            "TEXT"),
        ("missing_kpis",                 "TEXT"),
        ("transformation_opportunities", "TEXT"),
        ("agentic_opportunities",       "TEXT"),
        ("sow_text",                     "TEXT"),
        ("agent_name",                   "TEXT"),
        ("value_attribution",            "TEXT"),
    ]:
        try:
            con.execute(f"ALTER TABLE runs ADD COLUMN {col} {definition}")
            con.commit()
        except Exception:
            pass
    con.close()


MAX_RUNS_PER_ENGAGEMENT = 3


def check_run_limit(opportunity_id: str) -> None:
    """Warn (but don't block) if this engagement already has MAX_RUNS_PER_ENGAGEMENT runs."""
    con = sqlite3.connect(DB_PATH)
    count = con.execute(
        "SELECT COUNT(*) FROM runs WHERE opportunity_id = ?", (opportunity_id,)
    ).fetchone()[0]
    con.close()
    if count >= MAX_RUNS_PER_ENGAGEMENT:
        print(
            f"  ⚠️  {opportunity_id} already has {count} run(s). "
            f"Consider whether a re-run is needed (e.g. SoW was revised). "
            f"Proceeding anyway."
        )


def get_or_create_conversation(opportunity_id: str) -> str:
    """Return the Foundry conversation ID for this opportunity, creating it if needed."""
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT foundry_conv_id FROM runs WHERE opportunity_id=? AND foundry_conv_id IS NOT NULL LIMIT 1",
        (opportunity_id,)
    ).fetchone()
    con.close()
    if row:
        return row[0]

    # No existing conversation — create one in Foundry
    client = AIProjectClient(
        endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
        credential=DefaultAzureCredential(),
    )
    oc = client.get_openai_client()
    conv = oc.conversations.create()
    return conv.id


def call_agent(sow: dict) -> dict:
    """Send the SoW to the running agent and return the parsed JSON response."""
    input_text = (
        f"opportunity_id: {sow['opportunity_id']}\n"
        f"engagement_name: {sow['engagement_name']}\n\n"
        f"{sow['sow_text']}"
    )
    # /runs expects the OpenAI Responses API shape.
    # store=True + conversation.id are BOTH required for Foundry to persist the
    # response and trigger the ContinuousEvaluationRule.
    # Re-use the same Foundry conversation per opportunity so re-runs of the same
    # SoW are grouped in one thread without duplicating coverage.
    conv_id = get_or_create_conversation(sow["opportunity_id"])
    sow["_foundry_conv_id"] = conv_id  # pass through to log_run
    body = json.dumps({
        "model": os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        "input": input_text,
        "store": True,
        "conversation": {"id": conv_id},
    }).encode("utf-8")
    req = urllib.request.Request(
        AGENT_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")

    # The agent returns the response wrapped in an OpenAI Response object.
    # Extract the text content from output[0].content[0].text, then parse as JSON.
    try:
        wrapper = json.loads(raw)
        # OpenAI Responses API shape: output[].content[].text
        output_text = wrapper["output"][0]["content"][0]["text"]
        return json.loads(output_text)
    except (KeyError, IndexError, json.JSONDecodeError):
        # Fallback: try parsing the raw response directly
        return json.loads(raw)


def log_run(result: dict, sow: dict | None = None) -> None:
    """Write the run result to the local SQLite tracker."""
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        INSERT OR REPLACE INTO runs
            (run_id, opportunity_id, engagement_name, recommendation,
             status, pipeline_status, hours_saved, created_at, foundry_conv_id,
             summary, detected_outcomes, missing_kpis, transformation_opportunities, agentic_opportunities,
             agent_name, value_attribution)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.get("run_id"),
            result.get("opportunity_id"),
            result.get("engagement_name"),
            result.get("recommendation"),
            result.get("status", "draft"),
            "scanned",
            result.get("hours_saved"),
            datetime.now(datetime.UTC).isoformat() if hasattr(datetime, 'UTC') else datetime.utcnow().isoformat(),
            sow.get("_foundry_conv_id") if sow else None,
            result.get("summary"),
            json.dumps(result.get("detected_outcomes") or []),
            json.dumps(result.get("missing_kpis") or []),
            json.dumps(result.get("transformation_opportunities") or []),
            json.dumps(result.get("agentic_opportunities") or []),
            result.get("agent_name", "scan-agent"),
            json.dumps(result.get("value_attribution") or {}),
        ),
    )
    con.commit()
    con.close()


def print_result(result: dict) -> None:
    print(f"\n{'='*58}")
    print(f"  Outcome Readiness Review Result")
    print(f"{'='*58}")
    print(f"  opportunity_id  : {result.get('opportunity_id')}")
    print(f"  run_id          : {result.get('run_id')}")
    print(f"  engagement_name : {result.get('engagement_name')}")
    print(f"  summary         : {result.get('summary')}")
    print(f"  measurability   : {result.get('measurability')}")
    print(f"  recommendation  : {result.get('recommendation')}")
    print(f"  status          : {result.get('status')}")
    print(f"  hours_saved     : {result.get('hours_saved')}")
    outcomes = result.get("detected_outcomes", [])
    print(f"  detected_outcomes ({len(outcomes)}):")
    for o in outcomes:
        print(f"    • {o}")
    missing = result.get("missing_kpis", [])
    if missing:
        print(f"  missing_kpis ({len(missing)}):")
        for k in missing:
            print(f"    • {k}")
    transforms = result.get("transformation_opportunities", [])
    if transforms:
        print(f"  transformation_opportunities ({len(transforms)}):")
        for t in transforms:
            print(f"    ► {t.get('element')}")
            print(f"      {t.get('current_model')} → {t.get('suggested_outcome')}")
    print()


def run_sow(sow: dict) -> None:
    print(f"\n→ Sending SoW: [{sow['opportunity_id']}] {sow['engagement_name']}")
    check_run_limit(sow["opportunity_id"])
    result = call_agent(sow)
    log_run(result, sow)
    print_result(result)
    print(
        f"  ✓ Run logged to runs.db\n"
        f"  ✓ Foundry portal will auto-score this run via the continuous\n"
        f"    evaluation rule (visible under Agents > Monitor > Evaluation Metrics)\n"
    )


def main() -> None:
    ensure_schema()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--index", type=int, default=None,
        help="Index of the SoW in sample_sows.json to run (0-based). Omit to run all."
    )
    args = parser.parse_args()

    sows = load_sows()
    # Skip the synthetic data disclaimer entry (_readme key)
    sows = [s for s in sows if "opportunity_id" in s]

    if args.index is not None:
        if args.index >= len(sows):
            print(f"Error: index {args.index} out of range (0–{len(sows)-1})")
            sys.exit(1)
        run_sow(sows[args.index])
    else:
        for sow in sows:
            run_sow(sow)

    print("\nRun  python portfolio_kpi.py  to see updated portfolio coverage.\n")


if __name__ == "__main__":
    main()
