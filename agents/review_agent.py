"""
Review Agent  —  Stage: Under Review
--------------------------------------
Deployed to: Microsoft Foundry Agent Service
Framework:   Microsoft Agent Framework (agent_framework.azure.AzureAIClient)
Port:        8089  (default)

Responsibility:
    Receives a scan verdict (JSON from Scan Agent) plus the original SoW text
    and performs a deeper commercial analysis:
    - Designs illustrative outcome-based pricing structures for each transformation opportunity
    - Assesses commercial risk exposure
    - Produces a recommended commercial term sheet outline
    - Estimates analyst hours saved vs. a manual commercial review workshop

Value attribution metric:  hours_saved_review
    Baseline: a commercial specialist may spend several hours designing an outcome model.
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
You are the Review Agent for Contoso's Outcome Readiness Review pipeline.

STAGE: Under Review (commercial deep-dive)

You receive the Scan Agent's JSON verdict and the original SoW text.
Your job is to deepen the analysis: design illustrative outcome-based pricing structures,
assess commercial risk, and produce a structured pricing proposal that an analyst
can use as input to a client conversation.

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
      "payment_structure":  "<illustrative description, e.g. 'fixed component + at-risk component linked to outcome_metric'>",
      "risk_level":         "<low | medium | high>",
      "risk_rationale":     "<1–2 sentences on main commercial risk>"
    }
  ],
  "overall_risk":      "<low | medium | high>",
  "recommended_next_step": "<one sentence: what should happen in the client conversation>",
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
- pricing_model types (illustrative):
    outcome-share  : fee linked to a percentage of measured value delivered
    gainshare      : client and vendor share savings/uplift above baseline
    fixed-outcome  : fixed fee payable only on verified outcome achievement
    SLA-penalty    : base fee with penalty/bonus tied to a service level metric
    hybrid         : combination of the above
- Be specific about baseline_value — extract from the SoW if stated; otherwise note "not defined in SoW".
- hours_saved: higher for complex multi-tower engagements; lower for single-tower.
- Keep pricing_proposals aligned with transformation_opportunities from the Scan Agent.

Always respond with the JSON object only.
"""


async def main() -> None:
    credential = DefaultAzureCredential()
    async with AzureAIClient(
        project_endpoint=ENDPOINT,
        model_deployment_name=MODEL,
        credential=credential,
        use_latest_version=True,
    ).as_agent(name=AGENT_NAME, instructions=INSTRUCTIONS) as agent:
        await from_agent_framework(agent).run_async(port=PORT)


if __name__ == "__main__":
    asyncio.run(main())
