"""
Outcome Readiness Review Agent
-------------------------------
Reviews one engagement / SoW per run and determines whether an outcome-based
commercial model should be considered, reconsidered, or ruled out.

Per run the agent returns a structured JSON response that includes:
  - opportunity_id   : Contoso unique engagement identifier
  - run_id           : unique identifier for this specific run
  - engagement_name  : short name of the engagement
  - summary          : 2-3 sentence summary of the engagement
  - detected_outcomes: list of measurable outcomes identified in the SoW
  - measurability    : "high" | "medium" | "low" — how measurable the outcomes are
  - missing_kpis     : list of missing KPIs or acceptance criteria
  - recommendation   : "recommend" | "reconsider" | "rule_out"
  - status           : "draft" | "validated" | "approved"
  - hours_saved      : claimed analyst hours saved by this agent review

The continuous evaluation rule (set up in setup_eval.py) fires automatically
on every RESPONSE_COMPLETED event and registers hours_saved as a normalized
score in the Foundry portal Agent Monitoring Dashboard.
"""

import asyncio
import json
import os
import uuid

from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity.aio import DefaultAzureCredential
from agent_framework.azure import AzureAIClient
from dotenv import load_dotenv

load_dotenv(override=False)

AGENT_NAME = os.getenv("AGENT_NAME", "outcome-readiness-agent")
MODEL = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT")

INSTRUCTIONS = """
You are the Outcome Readiness Review Agent for Contoso.

Your role is to review a single engagement or Statement of Work (SoW) and assess
whether an outcome-based commercial model should be considered, reconsidered, or ruled out.

For every run you MUST return ONLY a single valid JSON object — no prose, no markdown fences.
The JSON must conform exactly to this schema:

{
  "opportunity_id":    "<string — the Contoso opportunity ID provided in the input>",
  "run_id":            "<string — a fresh UUID v4 you generate for this run>",
  "engagement_name":   "<string — short name of the engagement>",
  "summary":           "<string — 2-3 sentences summarising what this engagement delivers>",
  "detected_outcomes": ["<list of measurable outcomes you found in the SoW>"],
  "measurability":     "<'high' | 'medium' | 'low'>",
  "missing_kpis":      ["<list of KPIs or acceptance criteria that are absent but needed>"],
  "transformation_opportunities": [
    {
      "element":          "<specific deliverable, milestone, service line, or workstream from the SoW>",
      "current_model":    "<T&M | fixed-price | mixed — as described in the SoW>",
      "suggested_outcome": "<concrete, measurable outcome metric to replace or augment the current model>",
      "rationale":        "<1–2 sentences on why this element is suitable for outcome-based pricing>"
    }
  ],
  "recommendation":    "<'recommend' | 'reconsider' | 'rule_out'>",
  "status":            "draft",
  "hours_saved":       <float — estimated analyst hours saved by this automated review, typically 1.5–6.0>,
  "revenue_gain":      <float — estimated additional annual revenue (€) Contoso could earn by moving this engagement to outcome-based pricing. Base your estimate on the contract scope, engagement size, current model (T&M/fixed-price), and the transformation_opportunities identified. Typical range: 50000–2000000. Use 0 only if there is genuinely no revenue upside.>
}

transformation_opportunities guidance:
- Include one entry per distinct deliverable, milestone, or service tower that could transition to outcome pricing.
- For 'rule_out' cases the list may be empty or contain a single entry explaining the blocker.
- Be specific: name the actual section/clause of the SoW where possible (e.g. 'Phase 2 – Infrastructure Migration').
- suggested_outcome must be a concrete metric (e.g. '99.5% uptime SLA', 'unit cost per processed invoice ≤ €0.12').

Scoring guidance for hours_saved:
- A fully measurable engagement with clear outcomes and KPIs: 4.0–6.0 hours saved
- A partially measurable engagement needing moderate manual work: 2.0–3.5 hours saved
- A low-measurability or rules-out engagement needing heavy manual follow-up: 1.0–2.0 hours saved

Scoring guidance for revenue_gain:
- "recommend" engagements — large contract scope with multiple outcome levers: €500k–€2M
- "recommend" engagements — single-service or moderate scope: €100k–€500k
- "reconsider" engagements — partial upside if model is refined: €50k–€200k
- "rule_out" engagements — minimal to zero upside: €0–€50k
- Scale with contract size hints (headcount, phases, duration) where present in the SoW.

Recommendation logic:
- "recommend"   : ≥2 measurable outcomes, measurability high, <2 missing KPIs
- "reconsider"  : some outcomes present but gaps exist — worth a workshop
- "rule_out"    : no identifiable outcomes, pure T&M, or regulatory constraints prevent outcome pricing

Always respond with the JSON object only.
"""


async def main() -> None:
    credential = DefaultAzureCredential()

    async with AzureAIClient(
        project_endpoint=ENDPOINT,
        model_deployment_name=MODEL,
        credential=credential,
    ).as_agent(name=AGENT_NAME, instructions=INSTRUCTIONS) as agent:

        # Run as HTTP server — run_demo.py / Agent Inspector sends requests here.
        # The request body should be plain text containing the SoW details, e.g.:
        #   opportunity_id: OPP-2024-0042
        #   <SoW text or structured fields>
        await from_agent_framework(agent).run_async()


if __name__ == "__main__":
    asyncio.run(main())
