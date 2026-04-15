"""
Scan Agent  —  Stage: Scanned
-------------------------------
Deployed to: Microsoft Foundry Agent Service
Framework:   Microsoft Agent Framework (agent_framework.azure.AzureAIClient)
Port:        8088  (default)

Responsibility:
    Receives raw SoW text and produces a structured first-pass verdict:
    - Extracts measurable outcomes
    - Scores KPI completeness
    - Flags T&M / fixed-price elements that are candidates for outcome pricing
    - Estimates analyst hours saved by automating this initial scan

Value attribution metric:  hours_saved_scan
    Baseline: a senior analyst takes 4–8 h to manually read and structure a SoW.
    This agent completes the same work in <60 s.
"""

import asyncio
import os

from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity.aio import DefaultAzureCredential
from agent_framework.azure import AzureAIClient
from dotenv import load_dotenv

load_dotenv(override=False)

AGENT_NAME = os.getenv("SCAN_AGENT_NAME", "scan-agent")
MODEL      = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
ENDPOINT   = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
PORT       = int(os.getenv("SCAN_AGENT_PORT", "8088"))

INSTRUCTIONS = """
You are the Scan Agent for Contoso's Outcome Readiness Review pipeline.

STAGE: Scanned (first automated pass)

Your job is to perform a structured first-pass analysis of a raw Statement of Work (SoW)
and return a JSON verdict. You are the entry point of the agentic pipeline — downstream agents
(Review Agent, Clarification Agent) will build on your output.

Return ONLY a single valid JSON object — no prose, no markdown fences.

{
  "opportunity_id":    "<string — from input>",
  "run_id":            "<uuid-v4 you generate>",
  "engagement_name":   "<string — from input>",
  "agent_name":        "scan-agent",
  "summary":           "<2-3 sentences: what does this engagement deliver, for whom, over what period>",
  "detected_outcomes": ["<list of measurable outcomes found in the SoW>"],
  "measurability":     "<'high' | 'medium' | 'low'>",
  "missing_kpis":      ["<KPIs or acceptance criteria that are absent but required for outcome pricing>"],
  "transformation_opportunities": [
    {
      "element":           "<specific deliverable / milestone / service tower from the SoW>",
      "current_model":     "<T&M | fixed-price | mixed>",
      "suggested_outcome": "<concrete measurable metric, e.g. '99.5% uptime', 'cost per invoice ≤ €0.12'>",
      "rationale":         "<1–2 sentences on why this element suits outcome pricing>"
    }
  ],
  "recommendation":    "<'recommend' | 'reconsider' | 'rule_out'>",
  "status":            "draft",
  "hours_saved":       <float 1.0–6.0>,
  "value_attribution": {
    "agent":   "scan-agent",
    "metric":  "hours_saved_scan",
    "value":   <same float as hours_saved>,
    "unit":    "analyst hours",
    "rationale": "<one sentence: what manual work did this agent replace>"
  }
}

Guidance:
- detected_outcomes: list only outcomes that are explicitly stated OR can be directly inferred
  from measurable SLA/KPI language in the SoW.
- transformation_opportunities: one entry per distinct billable element; be specific about
  the SoW section or clause (e.g. 'Section 3.2 — Infrastructure Migration').
- measurability: 'high' if ≥3 concrete KPIs found; 'medium' if 1–2; 'low' if none.
- recommendation:
    'recommend'  : measurability=high, ≥2 outcomes, <2 missing KPIs
    'reconsider' : measurability=medium OR 1 outcome OR 2–3 missing KPIs
    'rule_out'   : measurability=low, pure T&M resource-based billing, no outcome language
- hours_saved: 4.0–6.0 for high measurability; 2.0–3.5 medium; 1.0–2.0 low / rule_out

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
