# Build Your Own Agent with Value Attribution

This guide walks you through adapting the two-level pattern in this repository to a different domain. The infrastructure, evaluation pipeline, and dashboard all work unchanged — you only need to update the agent logic and schema.

**Examples of domains this pattern suits:**
- Contract risk scoring (Level 1: risk verdict; Level 2: legal review hours saved)
- Proposal quality review (Level 1: bid/no-bid recommendation; Level 2: bid analyst hours saved)
- GDPR readiness assessment (Level 1: compliance gaps; Level 2: DPO review hours saved)
- Security posture review (Level 1: risk rating; Level 2: security analyst hours saved)

---

## Step 1 — Define both levels for your domain

Before writing any code, answer these two questions:

| Level | Question |
|---|---|
| **Level 1** | What decision or advisory output does the agent produce for the business? |
| **Level 2** | What is the measurable value (time, cost, risk) the agent saves or creates per run? |

The Level 2 metric must be something the agent can estimate from the input document itself — it should not require external data or a separate measurement step.

---

## Step 2 — Update the agent instructions

In `agent.py`, replace `INSTRUCTIONS` with your own prompt. Keep these rules:

1. **Return a single raw JSON object** — no markdown fences, no prose, no preamble.
2. **Include a numeric Level 2 field** (e.g. `hours_saved`, `risk_score`, `days_saved`).
3. **Include a `status` field** defaulting to `"draft"` — this is the human review gate.

Mirror the exact same `INSTRUCTIONS` string in `register_agent.py`.

Example structure for a contract risk agent:
```json
{
  "contract_id":      "CTR-2025-0041",
  "run_id":           "uuid-v4",
  "contract_name":    "...",
  "summary":          "...",
  "detected_risks":   ["..."],
  "severity":         "high | medium | low",
  "missing_clauses":  ["..."],
  "recommendation":   "approve | escalate | reject",
  "status":           "draft",
  "hours_saved":      4.5
}
```

---

## Step 3 — Update the database schema

In `setup_eval.py`, update the `CREATE TABLE` statement to match your new fields:

```python
con.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        run_id          TEXT PRIMARY KEY,
        contract_id     TEXT,
        contract_name   TEXT,
        recommendation  TEXT,
        status          TEXT DEFAULT 'draft',
        hours_saved     REAL,
        created_at      TEXT,
        foundry_conv_id TEXT
    )
""")
```

In `run_demo.py`, update `log_run()` to write the new fields, and update `call_agent()` to build the input payload from your document structure.

---

## Step 4 — Update the input data

Replace `sample_sows.json` with your own input documents. The structure just needs a unique ID, a name, and a text body:

```json
[
  {
    "contract_id":   "CTR-2025-0041",
    "contract_name": "Software Licence Agreement — Retail Client",
    "contract_text": "..."
  }
]
```

Update `run_demo.py` to read the new keys (`contract_id`, `contract_name`, `contract_text`).

---

## Step 5 — Rewrite the Level 2 evaluator

In `setup_eval.py`, update `GRADE_CODE` so `grade()` extracts your Level 2 metric and normalises it to 0–1:

```python
GRADE_CODE = """
import json

MAX_VALUE = 8.0   # adjust to your domain's maximum expected value

def grade(sample: dict, item: dict) -> float:
    def extract_text(d):
        t = d.get("output_text")
        if t:
            return t
        for out in d.get("output", []):
            for c in out.get("content", []):
                if isinstance(c, dict) and c.get("type") == "output_text":
                    return c.get("text", "")
        return ""
    try:
        s = item.get("sample", item)
        raw = extract_text(s) or extract_text(item)
        if not raw:
            return 0.0
        data = json.loads(raw)
        value = float(data.get("hours_saved", 0.0))   # ← change field name here
        return round(min(value / MAX_VALUE, 1.0), 4)
    except Exception:
        return 0.0
"""
```

Also update `EVAL_NAME` and the eval rule `id` to avoid conflicts with the original evaluator.

---

## Step 6 — Adjust the pass threshold

In `create_eval_rule()`, set `pass_threshold` to reflect what a "good" Level 2 score looks like for your domain:

```python
"pass_threshold": 0.25   # e.g. at least 2 h saved out of MAX_VALUE=8
```

---

## Step 7 — Run setup and register

```bash
python setup_eval.py       # creates runs.db + registers new evaluator + eval rule
python register_agent.py   # registers the agent in Foundry
python agent.py            # starts the HTTP server on port 8088
```

The dashboard, KPI CLI, and Foundry continuous evaluation pipeline all work unchanged — they read `hours_saved` and `status` from `runs.db` regardless of the domain.

---

## What stays the same

| Component | Needs changing? |
|---|---|
| Agent server (`agent.py` HTTP layer) | No |
| Foundry conversation creation | No |
| `store: True` + `conversation.id` payload | No |
| Application Insights telemetry | No |
| `ContinuousEvaluationRule` trigger mechanism | No (only `GRADE_CODE` changes) |
| `dashboard.py` | No |
| `portfolio_kpi.py` | No |
| `infra/main.bicep` | No |
