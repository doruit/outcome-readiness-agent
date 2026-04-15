# Value Attribution — How the Agent Measures Its Own Value

This document covers **Level 2** of the two-level pattern: how the agent's own performance is tracked, scored, and reported using outcome-based logic.

→ For an explanation of the two levels, see [outcome-based-models.md](outcome-based-models.md).

---

## The Core Idea

The agent is not rewarded for effort. It is scored on the value each run delivers — specifically, the number of analyst hours saved by automating the SoW review. This is the same standard it applies when assessing client engagements: *outcomes, not inputs*.

---

## The `hours_saved` Field

Every agent response includes an `hours_saved` estimate (1.0–6.0 h). This reflects the agent's assessment of how long a human analyst would have spent reviewing this particular SoW:

- Simple, T&M-only engagements with obvious blockers → lower hours (1.0–2.0 h)
- Complex, multi-outcome SoWs requiring careful KPI analysis → higher hours (4.0–6.0 h)

This field is the **primary Level 2 signal** and feeds into both local KPIs and Foundry's continuous evaluation.

---

## Local KPIs — `runs.db` and the Dashboard

Every run is persisted to `runs.db` (SQLite) by `run_demo.py`. `portfolio_kpi.py` and `dashboard.py` read this database to compute:

| KPI | How it's calculated |
|---|---|
| **Total hours saved** | `SUM(hours_saved)` across all runs |
| **Avg hours saved / run** | `AVG(hours_saved)` |
| **Portfolio coverage rate** | % of unique `opportunity_id`s with `status IN ('validated', 'approved')` |

The coverage rate starts at 0% because all new runs have `status: draft`. A human reviewer must promote a run to `validated` or `approved` to count it toward coverage — this is the human-in-the-loop gate.

```bash
# Promote a run after human review
sqlite3 runs.db "UPDATE runs SET status='validated' WHERE opportunity_id='OPP-2024-0112';"
python portfolio_kpi.py
```

The dashboard (`python dashboard.py` → http://localhost:5050) shows all of this visually with bar charts, a recommendation donut, and a timeline.

---

## Foundry Continuous Evaluation

`setup_eval.py` registers two artefacts in Microsoft Foundry:

### 1. Custom code evaluator — `hours_saved_metric`

Extracts `hours_saved` from the agent's JSON response and normalises it to a 0–1 score:

```python
score = round(min(hours_saved / MAX_HOURS_SAVED, 1.0), 4)
```

With `MAX_HOURS_SAVED=8.0`, a run saving 3.3 h scores `0.41`.

### 2. Continuous evaluation rule — `outcome-hours-saved-rule`

Fires automatically on every `RESPONSE_COMPLETED` telemetry event. No manual trigger needed.

- **Pass threshold:** 0.25 (i.e. at least 2 hours saved)
- **Dataset:** Agent responses (live, not batched)
- **Trigger:** Application Insights telemetry → Foundry event bus

Results appear in the Foundry portal under **Agents → your agent → Evaluation**.

> **Requirement:** `APPLICATIONINSIGHTS_CONNECTION_STRING` must be set in `.env`. Without it, `RESPONSE_COMPLETED` events never reach Foundry and the rule never fires. Retrieve the connection string with:
> ```python
> client.telemetry.get_application_insights_connection_string()
> ```

---

## Reading the Foundry Score

The normalised score shown in the portal maps back to real hours:

```
hours = score × MAX_HOURS_SAVED
```

| Portal score | Hours saved | Interpretation |
|---|---|---|
| 0.00–0.24 | < 2 h | Below pass threshold — low-complexity SoW or extraction issue |
| 0.25–0.49 | 2–4 h | Passing — typical reconsider / rule_out engagement |
| 0.50–0.74 | 4–6 h | Good — complex multi-outcome SoW |
| 0.75–1.00 | 6–8 h | Excellent — highest-complexity analysis |

---

## Compounding Value

Because every run is logged and the evaluator fires continuously, the total value accumulates automatically:

```
10 runs  @  avg 3.3 h  =   33 h saved
100 runs @  avg 3.3 h  =  330 h saved  (~2 analyst months)
```

This gives leadership a concrete, auditable answer to "what is the agent actually worth?" — expressed in the same currency the business already understands: analyst time.
