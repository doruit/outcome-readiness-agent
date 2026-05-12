"""
setup_eval.py — One-time setup script
--------------------------------------
Run this ONCE before the first agent run. It:

1. Registers a custom code-based evaluator in your Foundry project that reads
   `hours_saved` from the agent's JSON output and normalises it to a 0.0–1.0 score.

2. Creates a Foundry Evaluation wired to the azure_ai_source/responses data source
   so it can read every agent response automatically.

3. Creates a ContinuousEvaluationRule that fires on RESPONSE_COMPLETED for the
   agent, triggering the evaluator after every run with zero per-run code.

4. Creates a local SQLite database (runs.db) that stores every run's
   opportunity_id and status so portfolio_kpi.py can compute coverage.

Usage:
    python setup_eval.py
"""

import os
import sqlite3

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import (
    EvaluationRule,
    ContinuousEvaluationRuleAction,
    EvaluationRuleFilter,
    EvaluationRuleEventType,
)
from dotenv import load_dotenv

load_dotenv(override=False)

ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
AGENT_NAME = os.getenv("AGENT_NAME", "outcome-readiness-agent")
MODEL = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
MAX_HOURS = float(os.getenv("MAX_HOURS_SAVED", "8.0"))

EVALUATOR_NAME = "hours_saved_metric"
EVAL_RULE_ID = "outcome-hours-saved-rule"

# ---------------------------------------------------------------------------
# grade() source — this runs inside Foundry's sandboxed evaluator environment.
# It reads the agent's JSON output, extracts hours_saved, and normalises to 0–1.
# ---------------------------------------------------------------------------
GRADE_CODE = f"""
import json

MAX_HOURS = {MAX_HOURS}

def grade(sample: dict, item: dict) -> float:
    \"\"\"
    Extract hours_saved from the agent's JSON output and normalise to 0-1.

    Foundry passes the stored response in `item['sample']`. The agent stores
    its output as a message in the conversation; the text lands in different
    places depending on SDK version:
      - item['sample']['output_text']   (Responses API, when output is stored)
      - item['sample']['output'][0]['content'][0]['text']  (OpenAI response object)
      - item['output_text']             (legacy flat schema)
    \"\"\"
    def extract_text(d):
        # Try output_text directly
        t = d.get("output_text")
        if t:
            return t
        # Try nested OpenAI Responses shape: output[].content[].text
        for out in d.get("output", []):
            for c in out.get("content", []):
                if isinstance(c, dict) and c.get("type") == "output_text":
                    return c.get("text", "")
        return ""

    try:
        s = item.get("sample", item)  # fall back to item itself
        raw = extract_text(s) or extract_text(item)
        if not raw:
            return 0.0
        data = json.loads(raw)
        hours = float(data.get("hours_saved", 0.0))
        return round(min(hours / MAX_HOURS, 1.0), 4)
    except Exception:
        return 0.0
"""

# ---------------------------------------------------------------------------
# 1. Initialise local SQLite run tracker
# ---------------------------------------------------------------------------
def init_run_tracker(db_path: str = "runs.db") -> None:
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id                      TEXT PRIMARY KEY,
            opportunity_id              TEXT NOT NULL,
            engagement_name             TEXT,
            recommendation              TEXT,
            status                      TEXT NOT NULL DEFAULT 'draft',
            pipeline_status             TEXT NOT NULL DEFAULT 'scanned',
            hours_saved                 REAL,
            summary                     TEXT,
            detected_outcomes           TEXT,
            missing_kpis                TEXT,
            transformation_opportunities TEXT,
            agentic_opportunities       TEXT,
            created_at                  TEXT DEFAULT (datetime('now'))
        )
    """)
    con.commit()
    con.close()
    print(f"[setup] ✓ Local run tracker initialised at {db_path}")


# ---------------------------------------------------------------------------
# 2. Register custom evaluator in Foundry
# ---------------------------------------------------------------------------
def register_evaluator(client: AIProjectClient) -> str:
    resp = client.beta.evaluators.create_version(
        name=EVALUATOR_NAME,
        evaluator_version={
            "name": EVALUATOR_NAME,
            "categories": ["quality"],
            "display_name": "Hours Saved (Outcome Review)",
            "description": (
                "Extracts hours_saved from the agent's JSON response and normalises "
                f"it to a 0–1 score against a max of {MAX_HOURS} hours."
            ),
            "definition": {
                "type": "code",
                "code_text": GRADE_CODE,
                "init_parameters": {
                    "type": "object",
                    "properties": {
                        "deployment_name": {"type": "string"},
                        "pass_threshold": {"type": "number"},
                    },
                    "required": ["deployment_name", "pass_threshold"],
                },
                "metrics": {
                    "result": {
                        "type": "continuous",
                        "desirable_direction": "increase",
                        "min_value": 0.0,
                        "max_value": 1.0,
                    }
                },
                "data_schema": {
                    "type": "object",
                    "required": ["item"],
                    "properties": {"item": {"type": "object"}},
                },
            },
        },
    )
    print(f"[setup] ✓ Evaluator registered: {resp.name}")
    return resp.name


# ---------------------------------------------------------------------------
# 3. Create Foundry Evaluation + ContinuousEvaluationRule
# ---------------------------------------------------------------------------
def create_eval_rule(client: AIProjectClient) -> None:
    openai_client = client.get_openai_client()

    # Check for an existing eval with the same name to avoid duplicates
    existing_evals = list(openai_client.evals.list())
    EVAL_NAME = "Outcome Readiness — Hours Saved"
    existing = next((e for e in existing_evals if e.name == EVAL_NAME), None)

    if existing:
        eval_id = existing.id
        print(f"[setup] ✓ Evaluation already exists: {eval_id} — skipping creation")
    else:
        eval_obj = openai_client.evals.create(
            name=EVAL_NAME,
            data_source_config={
                "type": "azure_ai_source",
                "scenario": "responses",
            },
            testing_criteria=[
                {
                    "type": "azure_ai_evaluator",
                    "name": EVALUATOR_NAME,
                    "evaluator_name": EVALUATOR_NAME,
                    "initialization_parameters": {
                        "deployment_name": MODEL,
                        "pass_threshold": 0.25,  # ~2 hours saved = passing
                    },
                }
            ],
        )
        eval_id = eval_obj.id
        print(f"[setup] ✓ Evaluation created: {eval_id}")

    client.evaluation_rules.create_or_update(
        id=EVAL_RULE_ID,
        evaluation_rule=EvaluationRule(
            display_name="Outcome Review — Hours Saved (continuous)",
            action=ContinuousEvaluationRuleAction(
                eval_id=eval_id,
                max_hourly_runs=200,
            ),
            event_type=EvaluationRuleEventType.RESPONSE_COMPLETED,
            filter=EvaluationRuleFilter(agent_name=AGENT_NAME),
            enabled=True,
        ),
    )
    print(f"[setup] ✓ ContinuousEvaluationRule created: {EVAL_RULE_ID}")
    print(
        "[setup]   → The Foundry portal will now auto-score every agent run under\n"
        "           Agents > Monitor > Evaluation Metrics (hours_saved_metric chart)."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Outcome Readiness Review Agent — One-Time Setup ===\n")

    init_run_tracker()

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=ENDPOINT, credential=credential)

    register_evaluator(project_client)
    create_eval_rule(project_client)

    print("\n[setup] ✓ All done. Start agent servers with:")
    print("  python agents/scan_agent.py           # port 8088")
    print("  python agents/review_agent.py         # port 8089")
    print("  python agents/clarification_agent.py  # port 8090")
