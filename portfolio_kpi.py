"""
portfolio_kpi.py — Portfolio Coverage Calculator
--------------------------------------------------
Reads the local runs.db (written by the agent and/or manually updated)
and computes the two core KPIs:

  1. Per-run value attribution  — total claimed hours saved across all runs
  2. Outcome-Based Reconsideration Rate — % of unique opportunities that
     have at least one run with status 'validated' or 'approved'

Rule: multiple runs for the same opportunity_id count as ONE for coverage.
      Coverage only increases when a new (distinct) opportunity_id is reviewed.

Usage:
    python portfolio_kpi.py
    python portfolio_kpi.py --db /path/to/runs.db
"""

import argparse
import sqlite3
from datetime import datetime


def compute_kpis(db_path: str = "runs.db") -> None:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # -----------------------------------------------------------------------
    # All runs
    # -----------------------------------------------------------------------
    runs = con.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()

    if not runs:
        print("No runs recorded yet. Run the agent first.")
        con.close()
        return

    # -----------------------------------------------------------------------
    # KPI 1: Per-run value attribution
    # -----------------------------------------------------------------------
    total_runs = len(runs)
    total_hours = sum(r["hours_saved"] or 0.0 for r in runs)

    # -----------------------------------------------------------------------
    # KPI 2: Portfolio coverage
    # Unique opportunities in scope = all distinct opportunity_ids ever seen
    # Covered = those with at least one run where status IN ('validated','approved')
    # -----------------------------------------------------------------------
    all_opps = con.execute(
        "SELECT DISTINCT opportunity_id FROM runs"
    ).fetchall()

    covered_opps = con.execute(
        """
        SELECT DISTINCT opportunity_id
        FROM runs
        WHERE pipeline_status IN ('validated', 'approved')
        """
    ).fetchall()

    total_unique_opps = len(all_opps)
    covered_unique_opps = len(covered_opps)
    coverage_rate = (
        covered_unique_opps / total_unique_opps * 100
        if total_unique_opps > 0
        else 0.0
    )

    # -----------------------------------------------------------------------
    # KPI 3: Pipeline stage counts
    # -----------------------------------------------------------------------
    STAGES = ["intake", "scanned", "under_review", "validated", "rejected", "archived"]
    stage_counts = {s: 0 for s in STAGES}
    rows_by_stage = con.execute(
        """
        SELECT pipeline_status, COUNT(DISTINCT opportunity_id)
        FROM (
            SELECT opportunity_id, pipeline_status,
                   ROW_NUMBER() OVER (PARTITION BY opportunity_id ORDER BY created_at DESC) AS rn
            FROM runs
        ) WHERE rn = 1
        GROUP BY pipeline_status
        """
    ).fetchall()
    for stage, cnt in rows_by_stage:
        if stage in stage_counts:
            stage_counts[stage] = cnt

    # -----------------------------------------------------------------------
    # KPI 3: Per-engagement breakdown (latest run per opportunity)
    # -----------------------------------------------------------------------
    per_engagement = con.execute(
        """
        SELECT
            opportunity_id,
            engagement_name,
            recommendation,
            pipeline_status,
            SUM(hours_saved)  AS total_hours,
            COUNT(*)          AS run_count,
            MAX(hours_saved)  AS latest_hours
        FROM runs
        GROUP BY opportunity_id
        ORDER BY total_hours DESC
        """
    ).fetchall()

    # -----------------------------------------------------------------------
    # KPI 4: Recommendation distribution (latest run per opp)
    # -----------------------------------------------------------------------
    rec_dist = con.execute(
        """
        SELECT recommendation, COUNT(DISTINCT opportunity_id) AS opps
        FROM (
            SELECT opportunity_id, recommendation,
                   ROW_NUMBER() OVER (PARTITION BY opportunity_id ORDER BY created_at DESC) AS rn
            FROM runs
        )
        WHERE rn = 1
        GROUP BY recommendation
        ORDER BY opps DESC
        """
    ).fetchall()

    con.close()

    # -----------------------------------------------------------------------
    # Print report
    # -----------------------------------------------------------------------
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*58}")
    print(f"  Outcome Readiness Review — Portfolio KPI Report")
    print(f"  Generated: {now}")
    print(f"{'='*58}\n")

    print("── PER-RUN VALUE ATTRIBUTION ──────────────────────────")
    print(f"  Total agent runs          : {total_runs}")
    print(f"  Total hours saved (claimed): {total_hours:.1f} h")
    print(f"  Avg hours saved / run      : {total_hours / total_runs:.1f} h\n")

    print("── PIPELINE STAGES ─────────────────────────────────────")
    stage_line = "  "
    arrows = ["intake", "scanned", "under_review", "validated", "rejected", "archived"]
    for s in arrows:
        cnt = stage_counts.get(s, 0)
        marker = f"[{cnt}]" if cnt else " · "
        stage_line += f"{s} {marker}  →  "
    print(stage_line.rstrip("  →  "))
    print()

    print("── PER-ENGAGEMENT BREAKDOWN ───────────────────────────")
    eng_header = (
        f"  {'Opportunity':<16}{'Engagement':<32}"
        f"{'Runs':>5}{'Hours':>8}{'Recommendation':<16}{'Stage':<14}"
    )
    print(eng_header)
    print("  " + "-" * 91)
    for row in per_engagement:
        opp    = (row["opportunity_id"] or "—")[:14]
        name   = (row["engagement_name"] or "—")[:30]
        runs_n = row["run_count"]
        hours  = f"{row['total_hours']:.1f} h"
        rec    = (row["recommendation"] or "—")[:14]
        stage  = (row["pipeline_status"] or "scanned")[:12]
        print(f"  {opp:<16}{name:<32}{runs_n:>5}{hours:>8}  {rec:<16}{stage:<14}")
    print()

    print("── RECOMMENDATION DISTRIBUTION (latest run / engagement) ─")
    for row in rec_dist:
        rec  = row["recommendation"] or "—"
        opps = row["opps"]
        bar  = "█" * opps
        print(f"  {rec:<12}  {bar}  {opps}")
    print()

    print("── PORTFOLIO COVERAGE ─────────────────────────────────")
    print(f"  Unique engagements in scope : {total_unique_opps}")
    print(f"  Covered (validated/approved): {covered_unique_opps}")
    print(
        f"  Outcome-Based Reconsideration Rate: "
        f"{coverage_rate:.1f}%  ({covered_unique_opps}/{total_unique_opps})\n"
    )

    print("── HOW TO ADVANCE A STAGE ─────────────────────────────")
    print("  After reviewing an agent verdict, promote the engagement:")
    print("  sqlite3 runs.db \"UPDATE runs SET pipeline_status='under_review'")
    print("                   WHERE opportunity_id='OPP-...' AND pipeline_status='scanned';\"")
    print("  Valid stages: intake → scanned → under_review → validated → rejected → archived\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute portfolio KPIs from runs.db")
    parser.add_argument("--db", default="runs.db", help="Path to SQLite run tracker")
    args = parser.parse_args()
    compute_kpis(args.db)
