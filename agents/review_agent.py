"""
Review Agent  —  Stage: Under Review
--------------------------------------
Deployed to: Microsoft Foundry Agent Service
Framework:   Microsoft Agent Framework (agent_framework.azure.AzureAIClient)
Port:        8089  (default)

Responsibility:
    Receives a scan verdict (JSON from Scan Agent) plus the original SoW text
    and performs a deep-dive commercial analysis:
    - Designs concrete outcome-based pricing structures for each transformation opportunity
    - Quantifies risk exposure of each pricing model
    - Produces a recommended commercial term sheet outline
    - Estimates analyst hours saved vs. a manual commercial review workshop

Value attribution metric:  hours_saved_review
    Baseline: a commercial/pricing specialist takes 6–16 h to design an outcome model.
    This agent produces a structured pricing proposal in <90 s.
"""

import asyncio
import os

from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity.aio import DefaultAzureCredential
from agent_framework.azure import AzureAIClient
from dotenv import load_dotenv

load_dotenv(override=False)

AGENT_NAME = os.getenv("REVIEW_AGENT_NAME", "review-agent")
MODEL      = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
ENDPOINT   = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
PORT       = int(os.getenv("REVIEW_AGENT_PORT", "8089"))

INSTRUCTIONS = """
You are the Review Agent for Contoso Consulting's Outcome Readiness Review pipeline.

STAGE: Under Review (commercial deep-dive)

You receive the Scan Agent's JSON verdict and the original SoW text.
Your job is to deepen the analysis: design concrete outcome-based pricing structures,
assess commercial risk, and produce a structured pricing proposal that an analyst
can take directly into a client workshop.

Return ONLY a single valid JSON object — no prose, no markdown fences.

{
  "opportunity_id":    "<string — from input>",
  "run_id":            "<uuid-v4 you generate>",
  "engagement_name":   "<string — from input>",
  "agent_name":        "review-agent",
  "pricing_proposals": [
    {
      "element":            "<deliverable/tower — from scan transformation_opportunities>",
      "pricing_model":      "<outcome-share | gainshare | fixed-outcome | SLA-penalty | hybrid>",
      "outcome_metric":     "<the concrete KPI that triggers payment>",
      "baseline_value":     "<current state / baseline to measure improvement against>",
      "target_value":       "<the target that must be achieved for full payment>",
      "payment_structure":  "<e.g. '80% fixed + 20% at-risk linked to outcome_metric'>",
      "risk_level":         "<low | medium | high>",
      "risk_rationale":     "<1–2 sentences on main commercial risk>"
    }
  ],
  "overall_risk":      "<low | medium | high>",
  "recommended_next_step": "<one sentence: what should happen in the client workshop>",
  "hours_saved":       <float 6.0–16.0>,
  "value_attribution": {
    "agent":   "review-agent",
    "metric":  "hours_saved_review",
    "value":   <same float as hours_saved>,
    "unit":    "analyst hours",
    "rationale": "<one sentence: what commercial design work did this agent replace>"
  }
}

Guidance:
- pricing_model types:
    outcome-share  : client pays % of measured value delivered
    gainshare      : client and vendor split savings/uplift above baseline
    fixed-outcome  : fixed fee payable only on verified outcome achievement
    SLA-penalty    : T&M base with penalty/bonus tied to SLA metric
    hybrid         : combination of the above
- Be specific about baseline_value — extract from the SoW if stated; otherwise state "not defined in SoW".
- hours_saved: 10–16 for complex multi-tower engagements; 6–10 for single-tower.
- Keep pricing_proposals aligned with transformation_opportunities from the Scan Agent.

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
