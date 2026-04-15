# Contributing

Thank you for your interest in this project. This guide covers how to set up the environment, work with secrets, and run the demo locally.

---

## Prerequisites

- Python 3.11+
- An [Microsoft Foundry](https://ai.azure.com) project with a `gpt-4o` deployment
- Azure CLI installed and authenticated: `az login`

---

## 1. Clone and install

```bash
git clone https://github.com/<your-org>/outcome-readiness-agent.git
cd outcome-readiness-agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 2. Configure environment variables

**Never commit `.env`.** It is listed in `.gitignore` and contains secrets.

```bash
cp .env.template .env
```

Then open `.env` and fill in each value. The template has inline instructions for every variable. The key ones:

| Variable | Where to find it |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Azure portal → AI Foundry → your project → Overview → Endpoint |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME` | AI Foundry → Deployments tab — use the deployment name, not the model name |
| `AGENT_NAME` | Any string; must match across `agent.py`, `register_agent.py`, and `.env` |
| `MAX_HOURS_SAVED` | Leave as `8.0` unless your engagements are consistently larger or smaller |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Run the retrieval command in `.env.template` after the other vars are set |

### Retrieving the App Insights connection string

After filling in `FOUNDRY_PROJECT_ENDPOINT`, run:

```bash
python -c "
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
import os; from dotenv import load_dotenv; load_dotenv()
client = AIProjectClient(endpoint=os.getenv('FOUNDRY_PROJECT_ENDPOINT'), credential=DefaultAzureCredential())
print(client.telemetry.get_application_insights_connection_string())
"
```

Paste the output as the value of `APPLICATIONINSIGHTS_CONNECTION_STRING` in `.env`.

> This connection string is **required** for eval runs to appear in the Foundry portal. Without it the agent still works, but the continuous evaluation rule never fires.

---

## 3. One-time setup

```bash
python setup_eval.py       # creates runs.db + registers Foundry evaluator + eval rule
python register_agent.py   # registers the agent in Foundry
```

Both scripts are idempotent — safe to re-run. They check for existing resources before creating new ones.

---

## 4. Run the demo

```bash
# Terminal 1 — start the agent server
python agent.py

# Terminal 2 — submit SoWs
python run_demo.py             # all 4 sample SoWs
python run_demo.py --index 0   # one SoW (0-based)

# View results
python portfolio_kpi.py        # CLI report
python dashboard.py            # browser dashboard → http://localhost:5050
```

---

## 5. What NOT to commit

| File / folder | Why |
|---|---|
| `.env` | Contains secrets and personal endpoint URLs |
| `runs.db` | Runtime state — generated locally, not shareable |
| `.venv/` | Python virtual environment — recreated from `requirements.txt` |
| `__pycache__/` | Compiled bytecode |
| `.DS_Store` | macOS metadata |

All of the above are in `.gitignore`.

---

## 6. Changing the agent instructions

The `INSTRUCTIONS` string in `agent.py` defines the agent's behaviour and output schema. If you change it:

1. Update the identical copy in `register_agent.py`
2. Re-run `python register_agent.py` to push the update to Foundry
3. The agent server must be restarted to pick up the new instructions

---

## 7. Deploying the infrastructure

The Bicep template in `infra/main.bicep` provisions the Foundry account, project, and model deployment:

```bash
az deployment group create \
  --resource-group rg-outcome-readiness-agent \
  --template-file infra/main.bicep
```

The resource group and Application Insights resource must already exist before running this.
