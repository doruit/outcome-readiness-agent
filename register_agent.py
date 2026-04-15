"""
register_agent.py — Registers all pipeline agents in Foundry Agent Service
---------------------------------------------------------------------------
Run once (or after deleting agents):
    python register_agent.py

Three agents are registered, each mapped to a pipeline stage:
  scan-agent           → Scanned              (port 8088)
  review-agent         → Under Review         (port 8089)
  clarification-agent  → Needs Clarification  (port 8090)

All agents share the same AIServices account and gpt-4o deployment.
"""
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=False)

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

from agents.scan_agent          import AGENT_NAME as SCAN_NAME,          INSTRUCTIONS as SCAN_INSTRUCTIONS
from agents.review_agent        import AGENT_NAME as REVIEW_NAME,        INSTRUCTIONS as REVIEW_INSTRUCTIONS
from agents.clarification_agent import AGENT_NAME as CLARIFICATION_NAME, INSTRUCTIONS as CLARIFICATION_INSTRUCTIONS

endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
model    = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")

client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

AGENTS = [
    (SCAN_NAME,          SCAN_INSTRUCTIONS,          "First-pass SoW scan: extracts outcomes, scores KPI completeness, flags T&M elements"),
    (REVIEW_NAME,        REVIEW_INSTRUCTIONS,        "Commercial deep-dive: designs outcome-based pricing structures and risk assessment"),
    (CLARIFICATION_NAME, CLARIFICATION_INSTRUCTIONS, "Re-scope facilitation: generates clarification questions and rescope checklist for Reconsider verdicts"),
]

existing_names = {a.name for a in client.agents.list()}

for name, instructions, description in AGENTS:
    if name in existing_names:
        print(f"[register] Agent already exists: {name}")
    else:
        agent = client.agents.create_version(
            agent_name=name,
            definition=PromptAgentDefinition(
                model=model,
                instructions=instructions,
            ),
            description=description,
        )
        print(f"[register] ✓ Registered: {agent.name}")

print("\n[register] All agents registered. Run each agent server:")
print("  python agents/scan_agent.py           # port 8088")
print("  python agents/review_agent.py         # port 8089")
print("  python agents/clarification_agent.py  # port 8090")
