"""
Clarification Agent  —  Stage: Needs Clarification
----------------------------------------------------
Deployed to: Microsoft Foundry Agent Service
Framework:   Microsoft Agent Framework (agent_framework.azure.AzureAIClient)
Port:        8090  (default)

Responsibility:
    Receives a scan verdict where recommendation='reconsider' and the original SoW text.
    Generates a structured set of clarification questions and a re-scope checklist
    that an analyst sends back to the client to unlock outcome-based pricing.

Value attribution metric:  hours_saved_clarification
    Baseline: a senior analyst takes 3–6 h to read a vague SoW and draft targeted
    clarification questions and a re-scope brief.
    This agent produces a ready-to-send clarification pack in <60 s.
"""

import asyncio
import os

from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity.aio import DefaultAzureCredential
from agent_framework.azure import AzureAIClient
from dotenv import load_dotenv

load_dotenv(override=False)

AGENT_NAME = os.getenv("CLARIFICATION_AGENT_NAME", "clarification-agent")
MODEL      = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
ENDPOINT   = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
PORT       = int(os.getenv("CLARIFICATION_AGENT_PORT", "8090"))

INSTRUCTIONS = """
You are the Clarification Agent for Contoso's Outcome Readiness Review pipeline.

STAGE: Needs Clarification (re-scope facilitation)

You receive a Scan Agent verdict (recommendation='reconsider') and the original SoW text.
Your job is to produce a structured clarification pack that an analyst can send directly
to the client to fill the gaps preventing outcome-based pricing.

Return ONLY a single valid JSON object — no prose, no markdown fences.

{
  "opportunity_id":    "<string — from input>",
  "run_id":            "<uuid-v4 you generate>",
  "engagement_name":   "<string — from input>",
  "agent_name":        "clarification-agent",
  "gap_summary":       "<2-3 sentences: why this SoW cannot yet support outcome pricing>",
  "clarification_questions": [
    {
      "area":      "<the SoW section or commercial area this question targets>",
      "question":  "<specific, answerable question for the client>",
      "why":       "<why this answer is required for outcome pricing>",
      "priority":  "<high | medium | low>"
    }
  ],
  "rescope_checklist": [
    "<actionable item the client/vendor must add or revise in the SoW>"
  ],
  "unlock_potential": "<'recommend' | 'reconsider'> — verdict if all clarifications are addressed",
  "hours_saved":       <float 3.0–6.0>,
  "value_attribution": {
    "agent":   "clarification-agent",
    "metric":  "hours_saved_clarification",
    "value":   <same float as hours_saved>,
    "unit":    "analyst hours",
    "rationale": "<one sentence: what re-scope preparation work did this agent replace>"
  }
}

Guidance:
- clarification_questions: 3–7 questions; prioritise 'high' questions that are direct blockers.
- rescope_checklist: concrete SoW edits — e.g. 'Add a baseline uptime metric for the managed
  infrastructure service', 'Define acceptance criteria for Phase 2 deliverables'.
- unlock_potential: set to 'recommend' only if addressing all high-priority questions would
  make the engagement fully outcome-ready; otherwise 'reconsider'.
- hours_saved: 4.0–6.0 for complex engagements with many gaps; 3.0–4.0 for simpler cases.

Always respond with the JSON object only.
"""


async def main() -> None:
    credential = DefaultAzureCredential()
    async with AzureAIClient(
        project_endpoint=ENDPOINT,
        model_deployment_name=MODEL,
        credential=credential,
    ).as_agent(name=AGENT_NAME, instructions=INSTRUCTIONS) as agent:
        await from_agent_framework(agent).run_async(port=PORT)


if __name__ == "__main__":
    asyncio.run(main())
