# Outcome-Based Commercial Models

## What they are

Traditional IT services contracts price on **effort**: the client pays for the time and materials consumed, regardless of business impact. The supplier is rewarded for showing up, not for delivering results.

**Outcome-based commercial models** flip this relationship. The supplier's fee is tied — wholly or partially — to measurable business results. If the result is achieved, the supplier earns more. If not, they earn less (or nothing).

Examples from Contoso Consulting engagements:
- A 15% reduction in supply chain holding costs
- Claims processing time reduced from 14 days to 5 days
- Customer satisfaction score above 4.2 / 5.0
- A 60% reduction in manual touchpoints

This creates stronger alignment, shared accountability, and better incentives for delivery quality. It also forces both sides to agree upfront on what "success" looks like — which is often the most valuable conversation of the deal.

---

## Why it's hard to scale

Outcome-based models only work when three conditions are met:

| Condition | What it means | What breaks it |
|---|---|---|
| **Defined outcomes** | The SoW explicitly describes what business result will be achieved | Vague deliverables like "system go-live" or "data migration complete" |
| **Measurable KPIs** | Each outcome has a baseline, a target, and an agreed measurement method | No baseline data, no agreed data source, or KPIs defined too late |
| **No structural blockers** | The engagement structure allows outcome-linked payments | Regulatory constraints, pure T&M scope, client-side data access issues |

Assessing these three conditions requires reading the entire SoW carefully and applying commercial judgement. A trained analyst typically takes **4–8 hours per engagement**. Across a portfolio of hundreds of opportunities per year, this is a serious bottleneck — and a risk that assessments are skipped or done inconsistently.

---

## The two-level agent pattern

This repository demonstrates a pattern where an AI agent operates on two levels simultaneously:

### Level 1 — Business advisory (what the agent assesses)

The agent reads a SoW and determines whether the *client engagement* can be structured as an outcome-based commercial model. It identifies measurable outcomes, flags missing KPIs, and returns a `recommend / reconsider / rule_out` verdict.

This is the primary use case: replacing or augmenting the human analyst review.

### Level 2 — Agent accountability (how the agent is measured)

The agent's own performance is tracked using the same outcome-based logic it applies to SoWs. Rather than measuring it by tokens processed or response time (inputs), it is scored by the `hours_saved` it delivers per run (outcome).

**The symmetry is intentional.** The agent is held to the same standard it recommends for client engagements. It is not rewarded for effort; it earns credit only for the value it produces. This makes the agent's contribution auditable, compounding, and honest.

```
One run    →   3–5 hours saved
100 runs   →   300–500 hours saved
1,000 runs →   a full analyst year reclaimed
```

→ See [value-attribution.md](value-attribution.md) for how Level 2 is implemented technically.
