# Outcome Readiness Review Agent — Copilot Instructions

## Project Overview
A multi-agent pipeline for Contoso Consulting that reviews Statements of Work (SoWs) and determines whether an outcome-based commercial model should be `recommend`ed, `reconsider`ed, or `rule_out`ed. Three specialised agents handle different pipeline stages. Built on the **Microsoft Agent Framework** and deployed to **Microsoft Foundry**.

## Architecture

```
agent.py          ← Agent definition + HTTP server entry point (agentdev run agent.py)
register_agent.py ← One-time Foundry agent registration (azure.ai.projects SDK)
setup_eval.py     ← One-time: creates runs.db, Foundry evaluator, ContinuousEvaluationRule
run_demo.py       ← Demo: POSTs SoWs from sample_sows.json to the agent, logs to runs.db
portfolio_kpi.py  ← Reads runs.db and computes KPIs; standalone CLI tool
infra/main.bicep  ← Bicep for Foundry AIServices account, project, and gpt-4o deployment
```

## Developer Workflow

**One-time setup (in order):**
```bash
pip install -r requirements.txt
python setup_eval.py       # creates runs.db + registers Foundry evaluator + eval rule
python register_agent.py   # registers the agent in Foundry (skip if already registered)
```

**Run the agent server:**
```bash
python agent.py      # starts HTTP server on localhost:8088
```
The server reads `APPLICATIONINSIGHTS_CONNECTION_STRING` from `.env` on startup. Without it, the `ContinuousEvaluationRule` will not fire (responses are processed but not scored in Foundry).

**Send SoWs to the running agent:**
```bash
python run_demo.py             # runs all sample SoWs
python run_demo.py --index 0   # runs one SoW (0-based index into sample_sows.json)
```

**Check portfolio KPIs:**
```bash
python portfolio_kpi.py
python portfolio_kpi.py --db /path/to/runs.db
```

## Required Environment Variables (`.env`)
```
FOUNDRY_PROJECT_ENDPOINT=https://<account>.cognitiveservices.azure.com/api/projects/<project>
FOUNDRY_MODEL_DEPLOYMENT_NAME=gpt-4o
AGENT_NAME=outcome-readiness-agent
MAX_HOURS_SAVED=8.0          # denominator for the 0–1 normalised evaluator score
APPLICATIONINSIGHTS_CONNECTION_STRING=<from: python -c "from azure.ai.projects import AIProjectClient; ...client.telemetry.get_application_insights_connection_string()">
```
The App Insights connection string is required for the `ContinuousEvaluationRule` to fire. Retrieve it with `client.telemetry.get_application_insights_connection_string()` — see `.env.template` for the one-liner.

## Agent Response Contract
The agent **always returns a single raw JSON object** — no markdown fences, no prose. Any change to `INSTRUCTIONS` in `agent.py` must maintain this contract. The canonical schema:
- `opportunity_id`, `run_id` (uuid-v4), `engagement_name`, `summary`
- `detected_outcomes` (list), `measurability` (`high`/`medium`/`low`), `missing_kpis` (list)
- `recommendation` (`recommend`/`reconsider`/`rule_out`), `status` (`draft` always on new runs)
- `hours_saved` (float 1.0–6.0) — also used as the continuous evaluation metric

The same `INSTRUCTIONS` string is duplicated in `register_agent.py` — keep them in sync when editing.

## Data Persistence (`runs.db`)
SQLite file written by `run_demo.py` (via `log_run()`). Schema created in `setup_eval.py`:
- Primary key: `run_id` — re-running the same SoW replaces the row (`INSERT OR REPLACE`)
- **Coverage KPI counts only distinct `opportunity_id`s** with `status IN ('validated', 'approved')`; manually promote `status` from `draft` to `validated`/`approved` to affect the rate

## Continuous Evaluation (Foundry)
`setup_eval.py` registers a `ContinuousEvaluationRule` (id: `outcome-hours-saved-rule`) that fires on every `RESPONSE_COMPLETED` event. The custom code evaluator (`hours_saved_metric`) normalises `hours_saved` against `MAX_HOURS_SAVED` to a 0–1 score. Results appear in Foundry portal under **Agents > Monitor > Evaluation Metrics**.

## Infrastructure
`infra/main.bicep` targets the existing resource group `rg-outcome-readiness-agent` (Sweden Central). It does **not** create Application Insights — `appi-outcome-readiness` was created separately. The `projectEndpoint` output format is: `https://<account>.cognitiveservices.azure.com/api/projects/<project>`.

## Key SDK Packages
| Package | Role |
|---|---|
| `agent-framework-azure-ai` / `agent-framework-core` | Agent loop, `AzureAIClient`, `as_agent()` |
| `azure-ai-agentserver-agentframework` | `from_agent_framework()` HTTP server adapter |
| `azure-ai-projects` | Foundry `AIProjectClient`, eval rules, agent registration |
| `azure-identity` | `DefaultAzureCredential` (used everywhere) |
