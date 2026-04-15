# Architecture

## System Overview

```mermaid
graph TB
    subgraph Input
        SOW[Statement of Work<br/>sample_sows.json]
    end

    subgraph Agent Server ["Agent Server — localhost:8088"]
        API[POST /runs]
        AGENT[Outcome Readiness<br/>Review Agent — gpt-4o]
    end

    subgraph Persistence
        DB[(runs.db — SQLite)]
        FOUNDRY_STORE[Foundry Response Store]
    end

    subgraph Evaluation ["Microsoft Foundry — Continuous Evaluation (Level 2)"]
        APPI[Application Insights]
        RULE[ContinuousEvaluationRule]
        GRADE[hours_saved_metric]
        PORTAL[Evaluation Tab]
    end

    subgraph KPIs ["KPI Layer (Level 2)"]
        CLI[portfolio_kpi.py]
        DASH[dashboard.py — localhost:5050]
    end

    SOW -->|POST JSON — Level 1 input| API
    API --> AGENT
    AGENT -->|JSON verdict — Level 1 output| API
    API -->|store=True + conv_id| FOUNDRY_STORE
    API -->|log_run| DB
    AGENT -->|RESPONSE_COMPLETED event| APPI
    APPI --> RULE
    RULE --> GRADE
    GRADE --> PORTAL
    DB --> CLI
    DB --> DASH
```

---

## Per-SoW Process Flow

```mermaid
sequenceDiagram
    participant Demo as run_demo.py
    participant Server as Agent Server :8088
    participant Agent as gpt-4o Agent
    participant DB as runs.db
    participant Foundry as Microsoft Foundry
    participant APPI as App Insights

    Demo->>Server: POST /runs {model, input, store:true, conversation:{id}}
    Server->>Agent: SoW text + INSTRUCTIONS
    Agent-->>Server: Raw JSON verdict (Level 1)
    Server-->>Demo: 200 OK
    Demo->>DB: INSERT OR REPLACE run
    Server->>Foundry: Store response (conv_id)
    Server->>APPI: RESPONSE_COMPLETED event
    APPI->>Foundry: ContinuousEvaluationRule fires (Level 2)
    Foundry->>Foundry: grade() → hours_saved_metric (0–1)
```

---

## Agent Decision Logic (Level 1)

```mermaid
flowchart TD
    A[Read SoW text] --> B{Identify measurable outcomes}
    B -- None found --> C[rule_out]
    B -- Some found --> D{Check measurability}
    D -- Missing KPIs / vague --> E{Structural blockers?}
    D -- High measurability --> F[recommend]
    E -- Yes: regulatory / T&M-only --> C
    E -- No: fixable gaps --> G[reconsider]
    F --> H[Return JSON verdict + hours_saved]
    G --> H
    C --> H
```

---

## Key Components

| Component | File | Role |
|---|---|---|
| Agent definition | `agent.py` | `INSTRUCTIONS` prompt + `AzureAIClient.as_agent()` |
| HTTP server | `agent.py` | `from_agent_framework(agent).run_async()` on port 8088 |
| Demo runner | `run_demo.py` | Builds payload, POSTs to `/runs`, parses response, logs to `runs.db` |
| Eval setup | `setup_eval.py` | Registers `hours_saved_metric` evaluator + `ContinuousEvaluationRule` |
| Persistence | `runs.db` | SQLite — `run_id`, `opportunity_id`, `engagement_name`, `recommendation`, `status`, `hours_saved`, `created_at`, `foundry_conv_id` |
| KPI CLI | `portfolio_kpi.py` | Reads `runs.db`, prints per-engagement breakdown + coverage rate |
| KPI dashboard | `dashboard.py` | Self-contained HTTP server, renders live HTML from `runs.db` |
| Infra | `infra/main.bicep` | AIServices account, Foundry project, gpt-4o deployment |

---

## API Contract

The agent server accepts the OpenAI Responses API shape on `POST /runs`:

```json
{
  "model": "gpt-4o",
  "input": "<full SoW text>",
  "store": true,
  "conversation": { "id": "conv_<foundry-id>" }
}
```

Response shape parsed by `run_demo.py`:
```
wrapper["output"][0]["content"][0]["text"]  →  JSON string  →  dict
```

The agent always returns a **single raw JSON object** — no markdown fences, no prose.
