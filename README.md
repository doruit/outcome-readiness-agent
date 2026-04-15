# Outcome Readiness Review — Agent Value Attribution Demo

> A thought-leadership demo showing how to build **outcome-based agentic solutions**: AI agents that not only do work, but make the value they create visible, record it in a governed way, and relate it to investment and operating cost.

Built on **Microsoft Agent Framework** and **Microsoft Foundry**.

**Author:** [Douwe van de Ruit](https://www.linkedin.com/in/dvanderuit/) — Principal AI Solutions Architect

---

## Why this demo exists

Most AI agent demos show that agents *can* do things. This demo shows something harder to build and more important to enterprise buyers: an agentic system that **measures, records, and makes visible the business value it creates** — and relates that value to the cost of building and running it.

The question enterprise decision-makers actually ask is not "can AI do this task?" It is:

> *"If we invest in building and operating this agent, will the value it creates justify that investment — and how will we know?"*

This demo answers that question. It does so using a concrete use case — reviewing Statements of Work for outcome-based pricing feasibility — but the framework it demonstrates applies to any outcome-oriented agentic solution.

---

## The use case: outcome-based pricing at scale

Traditional consulting contracts pay for **effort**: the client pays day-rates regardless of whether the project delivered a measurable result. **Outcome-based pricing** is better — fees tied to real results, shared accountability, stronger delivery incentives.

But outcome-based pricing only works when the Statement of Work contains three things:

| Condition | What it means | What breaks it |
|---|---|---|
| **Defined outcomes** | A measurable business result, not a deliverable | Vague scope like "system go-live" |
| **Measurable KPIs** | Baseline, target, and agreed measurement method | No baseline data, no agreed data source |
| **No structural blockers** | The engagement allows outcome-linked payments | Regulatory constraints, pure T&M scope |

Checking these conditions manually requires 4–8 hours per SoW. Across hundreds of opportunities per year, this is a bottleneck — and a risk that assessments are skipped or done inconsistently.

Three AI agents replace this manual review, at a fraction of the time and cost.

---

## The framework: Agent Value Attribution

This demo introduces **Agent Value Attribution** as a formal framework for measuring and proving the value delivered by AI agents. Four concepts make up the framework:

| Concept | Definition |
|---|---|
| **Agent Value Attribution** | The discipline of linking AI agent activity to a measurable business outcome. Not just "the agent ran" — but "the agent created X hours of analyst value, which translates to £Y at an assumed rate." |
| **Agent Value Ledger** | The operational system of record for all value entries. Every agent run that produces a verdict writes a timestamped entry to the ledger — `agent_name`, `hours_saved`, `opportunity_id`, `run_id`. In this project, `runs.db` is the ledger. |
| **Attributed Value** | The per-run output of the attribution calculation. For each SoW reviewed, the agent records `hours_saved` (1.0–8.0 h). This is the atomic unit of value in the ledger. |
| **Value Realization** | The portfolio-level accumulation of Attributed Value over time — total analyst hours reclaimed, coverage rate, and engagement count cleared for outcome-based pricing. This is what leadership cares about. |

These four concepts form a chain:

```
Agent run → Attributed Value entry → Agent Value Ledger → Value Realization → Indicative ROI
```

The dashboard makes this chain visible at every level: per-run, per-engagement, and across the full portfolio.

---

## The Economic Impact Model

The dashboard includes a lightweight, transparent **Economic Impact Model** — an Indicative ROI layer that translates Attributed Value into financial terms.

Three scenario presets (Conservative / Expected / Upside) let you adjust four key assumptions:

| Assumption | Default (Expected) | What it drives |
|---|---|---|
| Analyst hourly rate | £110/h | Monetary value of hours saved |
| One-time build cost | £120k | Initial investment |
| Monthly operating cost | £6k | Ongoing run cost |
| Utilisation / adoption | 70% | Effective value capture rate |

The model computes: gross Attributed Value, annual operating cost, net value over 12 months, Indicative ROI, and estimated payback period.

**This model is explicitly illustrative** — assumption-driven, scenario-based, and not a contractual estimate. Its purpose is to support internal business case conversations, not to promise a specific return.

---

## The solution: outcome-based logic at two levels

This project demonstrates outcome-based commercial thinking at **two levels simultaneously**.

### Level 1 — SoW feasibility review

A pipeline of **three specialised agents** reads each Statement of Work and assesses whether it can support an outcome-based commercial model:

| Agent | Pipeline stage | What it does |
|---|---|---|
| 🤖 **Scan Agent** | Scanned | First-pass verdict — extracts outcomes, scores KPI completeness, flags T&M risks |
| 🤖 **Review Agent** | Under Review | Commercial deep-dive — designs outcome-based pricing structures, quantifies risk |
| 🤖 **Clarification Agent** | Needs Clarification | Re-scope facilitation — drafts targeted clarification questions and rescope checklist |

Verdicts:

| Verdict | Meaning |
|---|---|
| ✅ `recommend` | Clear, measurable outcomes — proceed to outcome-based pricing |
| ⚠️ `reconsider` | Potential exists but KPI gaps must be resolved — routed to Clarification Agent |
| ❌ `rule_out` | No measurable outcomes or structural blockers — use T&M or fixed-fee |

### Level 2 — Agent Value Attribution

The agents do not just produce verdicts — they are themselves held to outcome-based standards. Each agent reports the analyst hours its automation replaced (`hours_saved`), scored as a 0–1 metric in Microsoft Foundry's continuous evaluation pipeline. The agents earn credit only for value produced, not for effort expended.

This symmetry is the point: the same rigour applied to client SoWs is applied back to the AI system itself.

```mermaid
flowchart TD
    subgraph L1["Level 1 — SoW Feasibility Review"]
        direction LR
        SoW["📄 SoW"] --> Agent["🤖 3 Agents read SoW"]
        Agent --> V{"Verdict"}
        V -->|"≥3 KPIs, clear baseline"| REC["✅ Recommend"]
        V -->|"1–2 KPIs, gaps exist"| RECON["⚠️ Reconsider"]
        V -->|"No outcomes, T&M only"| RO["❌ Rule Out"]
    end

    subgraph L2["Level 2 — Agent Value Attribution"]
        direction LR
        Run["Each agent run"] --> HS["hours_saved entry\nwritten to Agent Value Ledger"]
        HS --> Score["Normalised 0–1 score\nin Microsoft Foundry"]
        Score --> KPI["Value Realization:\ntotal hours reclaimed\nIndicative ROI"]
    end

    L1 -->|"same outcome logic\napplied back to the agent"| L2
```

---

## How it works

```mermaid
flowchart TD
    DT(["👤 Deal Team"])
    UP["📄 Upload SoW\n(dashboard /upload)"]
    DB[("🗄️ Agent Value Ledger\nruns.db")]

    subgraph Foundry["☁️ Microsoft Foundry — Agent Service"]
        SA["🤖 Scan Agent\nport 8088"]
        RA["🤖 Review Agent\nport 8089"]
        CA["🤖 Clarification Agent\nport 8090"]
    end

    subgraph Pipeline["📋 7-Stage Pipeline"]
        S1["1 · Intake"]
        S2["2 · Scanned"]
        S3a["3 · Under Review"]
        S3b["3 · Needs Clarification"]
        S4["4 · Validated"]
        S5["5 · Rejected"]
        S6["6 · Archived"]
    end

    DASH["📊 Dashboard\nlocalhost:5050\n(incl. Economic Impact Model)"]
    KPI["📈 portfolio_kpi.py"]
    EVAL["🔬 Foundry Continuous Eval\nhours_saved → 0–1 score"]

    DT --> UP --> S1
    S1 -->|"/scan"| SA --> S2
    S2 -->|"recommend → /review"| RA --> S3a
    S2 -->|"reconsider → /clarify"| CA --> S3b
    S2 -->|rule_out| S5
    S3a --> S4
    S3b --> S4
    S4 --> S6
    S5 --> S6

    SA -->|"Attributed Value entry\n(hours_saved, agent_name)"| DB
    RA -->|"Attributed Value entry\n(hours_saved, agent_name)"| DB
    CA -->|"Attributed Value entry\n(hours_saved, agent_name)"| DB

    DB --> DASH
    DB --> KPI
    DB --> EVAL
```

---

## Portfolio Dashboard

![](.github/value_attribution_agents.jpeg)

The dashboard (`python dashboard.py` → http://localhost:5050) shows:

- **7-stage Kanban pipeline** — drag cards between stages with human-in-the-loop confirmation for agent actions
- **KPI tiles** — Engagements in scope, Validated coverage, Attributed Value (hours), Value Realization candidates
- **Economic Impact Model** — expandable panel with scenario presets and adjustable assumptions for Indicative ROI
- **Per-engagement detail panel** — Agent Assessment, Detected Outcomes, KPI Gaps, Commercial Direction, Agent Value Ledger entries
- **Agent Value Ledger view** — full run history per engagement with Attributed Value per entry

---

## Quick Start

**Prerequisites:** Python 3.11+, Azure CLI (`az login` done), an Azure subscription.

### Step 1 — Deploy infrastructure

```bash
az group create --name rg-outcome-readiness-agent --location swedencentral

az deployment group create \
  --resource-group rg-outcome-readiness-agent \
  --template-file infra/main.bicep
```

The deployment outputs `projectEndpoint` and `modelDeploymentName` — you need both for `.env`.

```bash
az deployment group show \
  --resource-group rg-outcome-readiness-agent \
  --name main \
  --query properties.outputs
```

### Step 2 — Configure environment

```bash
cp .env.template .env
```

Retrieve the Application Insights connection string (required for continuous evaluation):

```bash
python3 -c "
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
import os; from dotenv import load_dotenv; load_dotenv()
client = AIProjectClient(os.environ['FOUNDRY_PROJECT_ENDPOINT'], DefaultAzureCredential())
print(client.telemetry.get_application_insights_connection_string())
"
```

Paste the output into `.env` as `APPLICATIONINSIGHTS_CONNECTION_STRING`.

### Step 3 — Install and one-time setup

```bash
pip install -r requirements.txt

python setup_eval.py       # creates runs.db (the Agent Value Ledger) + registers Foundry evaluator
python register_agent.py   # registers all 3 agents in Foundry
```

### Step 4 — Start the agent servers

Open three terminals (or use `&` to background them):

```bash
python agents/scan_agent.py          # port 8088
python agents/review_agent.py        # port 8089
python agents/clarification_agent.py # port 8090
```

### Step 5 — Run the demo

```bash
python run_demo.py             # submits all sample SoWs through Scan Agent
python run_demo.py --index 0   # submits one SoW (0-based)
```

### Step 6 — View results

```bash
python portfolio_kpi.py        # CLI Value Realization report
python dashboard.py            # browser dashboard → http://localhost:5050
```

---

## Repository Structure

| File | Purpose |
|---|---|
| `agents/scan_agent.py` | Scan Agent — first-pass verdict, port 8088 |
| `agents/review_agent.py` | Review Agent — commercial deep-dive, port 8089 |
| `agents/clarification_agent.py` | Clarification Agent — re-scope facilitation, port 8090 |
| `agent.py` | Legacy single-agent entry point (superseded by `agents/`) |
| `register_agent.py` | One-time Foundry registration for all 3 agents |
| `setup_eval.py` | One-time: `runs.db` (Agent Value Ledger), Foundry evaluator, ContinuousEvaluationRule |
| `run_demo.py` | Submits SoWs to the Scan Agent, logs Attributed Value entries to `runs.db` |
| `portfolio_kpi.py` | CLI Value Realization report |
| `dashboard.py` | Browser dashboard with pipeline, KPIs, and Economic Impact Model (port 5050) |
| `sample_sows.json` | 26 synthetic SoWs covering all verdicts |
| `infra/main.bicep` | Bicep: Foundry account, project, gpt-4o deployment |
| `docs/` | Architecture, value attribution, contributing, and build-your-own guides |

---

## Further Reading

| Doc | Contents |
|---|---|
| [docs/outcome-based-models.md](docs/outcome-based-models.md) | What outcome-based commercial models are and why they're hard to scale |
| [docs/value-attribution.md](docs/value-attribution.md) | Agent Value Attribution in depth — Ledger, Attributed Value, Value Realization |
| [docs/architecture.md](docs/architecture.md) | System architecture, process flow, agent decision logic |
| [docs/build-your-own.md](docs/build-your-own.md) | Step-by-step guide to adapting this pattern to your own domain |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Contribution guidelines |
| [docs/SECURITY.md](docs/SECURITY.md) | Security policy and vulnerability reporting |
