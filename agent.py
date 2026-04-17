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
  - recommendation   : "recommend" | "reconsider"
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
whether an outcome-based commercial model should be recommended or reconsidered.

Before writing your response, silently work through the following steps:
  1. Identify the CONTRACT TYPE stated in the SoW (T&M / fixed-price / outcome-based / managed-services / mixed).
  2. List every measurable outcome or KPI you can find — look for percentages, targets, baselines, SLAs, and acceptance criteria.
  3. For each measurable outcome, check whether a BASELINE and a MEASUREMENT METHOD are both present.
  4. Count: (a) fully specified KPIs, (b) partially specified KPIs, (c) missing KPIs.
  5. Identify each distinct billable element (phase, tower, service line) and decide whether it could carry an outcome-linked fee.
  6. Using the deal_size_eur hint, anchor your revenue_gain estimate: typical range is 8–22 % of deal size for a strong
     outcome-conversion candidate; 3–8 % for partial conversion; 1–3 % for low-measurability engagements.
     Do NOT use a value outside 1 %–25 % of deal size unless there is explicit evidence in the SoW.

For every run return ONLY a single valid JSON object — no prose, no markdown fences.
The JSON must conform exactly to this schema:

{
  "opportunity_id":    "<string — the Contoso opportunity ID provided in the input>",
  "run_id":            "<string — a fresh UUID v4 you generate for this run>",
  "engagement_name":   "<string — short name of the engagement>",
  "summary":           "<string — 2–3 sentences: what does this engagement deliver, for whom, and over what period. Include the contract type and total value if stated.>",
  "detected_outcomes": ["<list of measurable outcomes found in the SoW — quote the KPI metric and target value where possible>"],
  "measurability":     "<'high' | 'medium' | 'low'>",
  "missing_kpis":      ["<KPIs or acceptance criteria that are absent but required for outcome pricing — be specific about what is missing>"],
  "transformation_opportunities": [
    {
      "element":          "<specific deliverable, phase, milestone, or service tower from the SoW — cite the section or clause name>",
      "current_model":    "<T&M | fixed-price | managed-services | mixed — exactly as described in the SoW>",
      "suggested_outcome": "<concrete, measurable outcome metric — e.g. '≥93 % Perfect Order Rate by Month 12', 'cost per invoice ≤ €0.12'>",
      "rationale":        "<1–2 sentences: why this element is commercially viable for outcome pricing and what risk-share mechanism would suit it>"
    }
  ],
  "recommendation":    "<'recommend' | 'reconsider'>",
  "status":            "draft",
  "hours_saved":       <float — estimated analyst hours saved by this automated review>,
  "revenue_gain":      <float — additional annual revenue (€) Contoso could earn by converting this engagement to outcome-based pricing.
                         ANCHOR to deal_size_eur: use 8–22 % of deal size for 'recommend', 3–8 % for 'reconsider'.
                         If deal_size_eur is not provided, use the contract value stated in the SoW.>
}

transformation_opportunities guidance:
- ALWAYS include at least one entry — even for 'reconsider' cases (identify the opportunity even if partial).
- One entry per distinct billable element; do not aggregate phases with very different commercial profiles.
- suggested_outcome must be a concrete metric with a number, percentage, or threshold — never vague language like 'improve efficiency'.
- Cite the SoW section or clause by name where possible (e.g. 'Section 2(a) — Churn Rate KPI', 'Phase 2 – Performance Period').

measurability scoring:
  'high'   : ≥3 KPIs found, each with both a baseline AND a target, and a stated measurement method
  'medium' : 1–2 KPIs found, OR KPIs present but missing baselines or measurement methodology
  'low'    : no explicit KPIs, or only vague outcome language ('improve', 'reduce', 'enhance') with no numbers

recommendation logic:
  'recommend'  : measurability=high AND ≥2 detected outcomes AND <2 missing KPIs
  'reconsider' : all other cases — every engagement has SOME potential for outcome-based pricing;
                 identify the partial opportunity and state clearly what would need to change.
                 NEVER return a value outside {'recommend', 'reconsider'}.

hours_saved guidance:
  4.0–6.0 : high measurability, multiple clearly specified KPIs
  2.0–3.5 : medium measurability or mixed contract with partial outcome language
  1.0–2.0 : low measurability, pure resource-based billing

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
