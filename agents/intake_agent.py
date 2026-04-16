"""
Intake Agent
------------
First agent in the Contoso Outcome Readiness pipeline.
Reads the raw SoW and extracts:
  - A clean, short engagement title
  - The engagement manager name (from the SoW text, if present; otherwise infer from context)
  - The total deal size / contract value (€)

Returns a single raw JSON object — no markdown, no prose.

Run:
    agentdev run agents/intake_agent.py
    # or: python agents/intake_agent.py
"""

import asyncio
import json
import os

from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity.aio import DefaultAzureCredential
from agent_framework.azure import AzureAIClient
from dotenv import load_dotenv

load_dotenv(override=False)

AGENT_NAME = os.getenv("INTAKE_AGENT_NAME", "intake-agent")
MODEL      = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
ENDPOINT   = os.getenv("FOUNDRY_PROJECT_ENDPOINT")

INSTRUCTIONS = """
You are the Intake Agent for Contoso's Outcome Readiness Review pipeline.

Your role is to read a raw Statement of Work (SoW) and extract three pieces of information:
  1. A concise engagement title (4–8 words, title-case, no jargon)
  2. The engagement manager's full name as stated in the SoW (look for "Engagement Manager", 
     "Account Manager", "Project Sponsor", "Partner", or similar roles; if not found, return null)
  3. The total contract / deal value in euros (€). 
     - Look for contract value, total fees, project budget, estimated cost, or similar.
     - Convert any non-EUR currency to EUR using approximate market rates.
     - If a range is given, return the midpoint.
     - If no value is stated, estimate based on scope, team size, and duration described.
     - Return as a plain float (no currency symbol, no commas).

You MUST return ONLY a single valid JSON object — no prose, no markdown fences.
Schema:

{
  "opportunity_id":        "<string — the opportunity ID provided in the input>",
  "engagement_title":      "<string — 4–8 word clean title>",
  "engagement_manager":    "<string — full name, or null if not found>",
  "deal_size":             <float — total contract value in EUR>
}

Always respond with the JSON object only.
"""


async def main() -> None:
    credential = DefaultAzureCredential()

    async with AzureAIClient(
        project_endpoint=ENDPOINT,
        model_deployment_name=MODEL,
        credential=credential,
    ).as_agent(name=AGENT_NAME, instructions=INSTRUCTIONS) as agent:

        server = from_agent_framework(agent)
        await server.serve(host="0.0.0.0", port=int(os.getenv("INTAKE_AGENT_PORT", "8087")))


if __name__ == "__main__":
    asyncio.run(main())
