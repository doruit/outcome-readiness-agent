"""
dashboard.py — Outcome Readiness Review · SoW Pipeline Dashboard
-----------------------------------------------------------------
Premium enterprise dashboard for Contoso's Outcome Readiness
Review Agent. Visualises the 7-stage SoW review pipeline with split-view
detail panel, engagement manager ownership, and simulated activation flow.

Usage:
    python dashboard.py
    python dashboard.py --db /path/to/runs.db --port 5050
"""

import argparse
import email
import email.message
import io
import json
import os
import sqlite3
import re
import urllib.request
import uuid as _uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

SOWS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_sows.json")

def load_sows() -> list:
    """Return the list of SoW dicts from sample_sows.json, excluding the _readme entry."""
    try:
        with open(SOWS_PATH, "r", encoding="utf-8") as f:
            return [e for e in json.load(f) if "opportunity_id" in e]
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
CAP_BLUE   = "#0070AD"
CAP_NAVY   = "#0E1E38"
CAP_LIGHT  = "#F4F7FB"
CAP_BORDER = "#DDE5EF"

# ---------------------------------------------------------------------------
# Engagement manager lookup (simulated)
# ---------------------------------------------------------------------------
ENGAGEMENT_MANAGERS = {
    "OPP-2026-0301": {"name": "Sophie Laurens",    "title": "Engagement Director",  "email": "s.laurens@contoso.com"},
    "OPP-2026-0302": {"name": "Markus Brandt",     "title": "Senior Manager",        "email": "m.brandt@contoso.com"},
    "OPP-2026-0303": {"name": "Isabelle Moreau",   "title": "Engagement Director",  "email": "i.moreau@contoso.com"},
    "OPP-2026-0304": {"name": "Tobias Wenger",     "title": "Principal Consultant", "email": "t.wenger@contoso.com"},
    "OPP-2026-0305": {"name": "Priya Nair",        "title": "Senior Manager",        "email": "p.nair@contoso.com"},
    "OPP-2026-0306": {"name": "Charlotte Dubois",  "title": "Engagement Director",  "email": "c.dubois@contoso.com"},
    "OPP-2026-0307": {"name": "James Hartley",     "title": "Principal Consultant", "email": "j.hartley@contoso.com"},
    "OPP-2026-0308": {"name": "Niamh O'Brien",     "title": "Engagement Director",  "email": "n.obrien@contoso.com"},
    "OPP-2026-0309": {"name": "Erik van den Berg",  "title": "Senior Manager",       "email": "e.vandenberg@contoso.com"},
    "OPP-2026-0310": {"name": "Alicia Ferreira",   "title": "Principal Consultant", "email": "a.ferreira@contoso.com"},
    "OPP-2026-0201": {"name": "David Okonkwo",     "title": "Senior Manager",        "email": "d.okonkwo@contoso.com"},
    "OPP-2026-0202": {"name": "Helena Kowalski",   "title": "Principal Consultant", "email": "h.kowalski@contoso.com"},
    "OPP-2026-0203": {"name": "Luca Bernardini",   "title": "Engagement Director",  "email": "l.bernardini@contoso.com"},
    "OPP-2026-0204": {"name": "Ananya Sharma",     "title": "Senior Manager",        "email": "a.sharma@contoso.com"},
    "OPP-2026-0205": {"name": "Tom Verlinden",     "title": "Engagement Director",  "email": "t.verlinden@contoso.com"},
    "OPP-2026-0206": {"name": "Rachel Osei",       "title": "Principal Consultant", "email": "r.osei@contoso.com"},
    "OPP-2026-0207": {"name": "Marco Visser",      "title": "Senior Manager",        "email": "m.visser@contoso.com"},
    "OPP-2026-0208": {"name": "Fiona Gallagher",   "title": "Engagement Director",  "email": "f.gallagher@contoso.com"},
    "OPP-2026-0209": {"name": "Stefan Richter",    "title": "Principal Consultant", "email": "s.richter@contoso.com"},
    "OPP-2026-0210": {"name": "Yuki Tanaka",       "title": "Senior Manager",        "email": "y.tanaka@contoso.com"},
    "OPP-2026-0211": {"name": "Cecile Fontaine",   "title": "Engagement Director",  "email": "c.fontaine@contoso.com"},
    "OPP-2026-0212": {"name": "Ben Adeyemi",       "title": "Principal Consultant", "email": "b.adeyemi@contoso.com"},
    "OPP-2024-0112": {"name": "Laura Schmidt",     "title": "Senior Manager",        "email": "l.schmidt@contoso.com"},
    "OPP-2024-0088": {"name": "Patrick Murray",    "title": "Principal Consultant", "email": "p.murray@contoso.com"},
    "OPP-2025-0034": {"name": "Camille Renard",    "title": "Engagement Director",  "email": "c.renard@contoso.com"},
    "OPP-2025-0071": {"name": "Oliver Braun",      "title": "Senior Manager",        "email": "o.braun@contoso.com"},
}

def get_manager(opportunity_id: str) -> dict:
    if opportunity_id in ENGAGEMENT_MANAGERS:
        return ENGAGEMENT_MANAGERS[opportunity_id]
    pool = list(ENGAGEMENT_MANAGERS.values())
    return pool[hash(opportunity_id) % len(pool)]

# Fictional deal sizes (€) per opportunity
DEAL_SIZES = {
    "OPP-2026-0301": 1_800_000,
    "OPP-2026-0302":   620_000,
    "OPP-2026-0303": 2_400_000,
    "OPP-2026-0304":   450_000,
    "OPP-2026-0305":   980_000,
    "OPP-2026-0306": 1_250_000,
    "OPP-2026-0307":   375_000,
    "OPP-2026-0308": 3_100_000,
    "OPP-2026-0309":   760_000,
    "OPP-2026-0310":   520_000,
    "OPP-2026-0201":   840_000,
    "OPP-2026-0202":   290_000,
    "OPP-2026-0203": 1_600_000,
    "OPP-2026-0204":   710_000,
    "OPP-2026-0205": 2_200_000,
    "OPP-2026-0206":   430_000,
    "OPP-2026-0207":   950_000,
    "OPP-2026-0208": 1_100_000,
    "OPP-2026-0209":   580_000,
    "OPP-2026-0210":   340_000,
    "OPP-2026-0211": 1_750_000,
    "OPP-2026-0212":   670_000,
    "OPP-2024-0112":   490_000,
    "OPP-2024-0088": 1_050_000,
    "OPP-2025-0034":   820_000,
    "OPP-2025-0071": 1_380_000,
}

def get_deal_size(opportunity_id: str) -> float:
    return DEAL_SIZES.get(opportunity_id, 500_000)

# Indicative revenue-gain estimates (outcome-based uplift vs T&M baseline)
# Expressed as absolute €, derived from deal_size × a realistic uplift %
REVENUE_GAINS = {
    "OPP-2026-0301": round(1_800_000 * 0.18),   # 18 %
    "OPP-2026-0302": round(  620_000 * 0.12),   # 12 %
    "OPP-2026-0303": round(2_400_000 * 0.21),   # 21 %
    "OPP-2026-0304": round(  450_000 * 0.09),   #  9 %
    "OPP-2026-0305": round(  980_000 * 0.15),   # 15 %
    "OPP-2026-0306": round(1_250_000 * 0.17),   # 17 %
    "OPP-2026-0307": round(  375_000 * 0.08),   #  8 %
    "OPP-2026-0308": round(3_100_000 * 0.22),   # 22 %
    "OPP-2026-0309": round(  760_000 * 0.13),   # 13 %
    "OPP-2026-0310": round(  520_000 * 0.10),   # 10 %
    "OPP-2026-0201": round(  840_000 * 0.14),   # 14 %
    "OPP-2026-0202": round(  290_000 * 0.08),   #  8 %
    "OPP-2026-0203": round(1_600_000 * 0.19),   # 19 %
    "OPP-2026-0204": round(  710_000 * 0.11),   # 11 %
    "OPP-2026-0205": round(2_200_000 * 0.20),   # 20 %
    "OPP-2026-0206": round(  430_000 * 0.09),   #  9 %
    "OPP-2026-0207": round(  950_000 * 0.16),   # 16 %
    "OPP-2026-0208": round(1_100_000 * 0.18),   # 18 %
    "OPP-2026-0209": round(  580_000 * 0.12),   # 12 %
    "OPP-2026-0210": round(  340_000 * 0.08),   #  8 %
    "OPP-2026-0211": round(1_750_000 * 0.17),   # 17 %
    "OPP-2026-0212": round(  670_000 * 0.13),   # 13 %
    "OPP-2024-0112": round(  490_000 * 0.10),   # 10 %
    "OPP-2024-0088": round(1_050_000 * 0.15),   # 15 %
    "OPP-2025-0034": round(  820_000 * 0.14),   # 14 %
    "OPP-2025-0071": round(1_380_000 * 0.16),   # 16 %
}

def get_revenue_gain(opportunity_id: str) -> float:
    return REVENUE_GAINS.get(opportunity_id, 0)

# ---------------------------------------------------------------------------
# Document text extraction
# ---------------------------------------------------------------------------
def extract_text_from_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    except Exception as e:
        return f"[PDF extraction error: {e}]"

def extract_text_from_docx(data: bytes) -> str:
    try:
        from docx import Document
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs if p.text.strip())
    except Exception as e:
        return f"[DOCX extraction error: {e}]"

def extract_text(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":             return extract_text_from_pdf(data)
    if ext in (".docx", ".doc"): return extract_text_from_docx(data)
    return data.decode("utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Agent calls
# ---------------------------------------------------------------------------
INTAKE_AGENT_PORT        = int(os.getenv("INTAKE_AGENT_PORT",  "8087"))
SCAN_AGENT_PORT          = int(os.getenv("SCAN_AGENT_PORT",   "8088"))
REVIEW_AGENT_PORT        = int(os.getenv("REVIEW_AGENT_PORT",  "8089"))
CLARIFICATION_AGENT_PORT = int(os.getenv("CLARIFICATION_AGENT_PORT", "8090"))

def _call_agent(port: int, input_text: str) -> dict:
    from dotenv import load_dotenv
    load_dotenv(override=False)
    body = json.dumps({
        "model": os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        "input": input_text, "store": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"http://localhost:{port}/runs", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    wrapper = json.loads(raw)
    # Agent server returns HTTP 200 with an error envelope on upstream failures
    if isinstance(wrapper, dict) and "code" in wrapper and "output" not in wrapper:
        raise RuntimeError(f"agent error: {wrapper.get('message') or wrapper['code']}")
    try:
        text = wrapper["output"][0]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return wrapper
    # Models sometimes wrap JSON in a ```json ... ``` fence despite instructions not to
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return wrapper

def call_agent_with_text(opp_id, eng_name, sow_text, deal_size=None, mgr=None, extra_instructions=None):
    deal_hint = f"\ndeal_size_eur: {deal_size}" if deal_size else ""
    mgr_hint  = ""
    if mgr and isinstance(mgr, dict):
        mgr_hint = f"\nengagement_manager_name: {mgr.get('name','')}"
        mgr_hint += f"\nengagement_manager_email: {mgr.get('email','')}"
    instr_hint = ""
    if extra_instructions and str(extra_instructions).strip():
        instr_hint = (f"\n\n==== ADDITIONAL REVIEWER INSTRUCTIONS ====\n"
                      f"{str(extra_instructions).strip()}\n"
                      f"(Apply these instructions when extracting outcomes, KPIs, "
                      f"opportunities and producing the summary. They reflect human feedback "
                      f"and must take precedence over defaults.)\n"
                      f"==========================================")
    return _call_agent(SCAN_AGENT_PORT,
        f"opportunity_id: {opp_id}\nengagement_name: {eng_name}{deal_hint}{mgr_hint}{instr_hint}\n\n{sow_text}")

def call_intake_agent(opp_id: str, sow_text: str) -> dict:
    return _call_agent(INTAKE_AGENT_PORT,
        f"opportunity_id: {opp_id}\n\n{sow_text}")

# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
STAGES = [
    ("intake",          "Intake",              "Awaiting SoW and agent scan"),
    ("scanned",         "Extract Outcomes from SoW", "Automated scan complete — ready for review"),
    ("under_review",    "Human Review",              "Human reviewer assessing AI output"),
    ("generate_report", "Generate Instructions for Engagement Mgr", "Instruction package for the Engagement Manager"),
    ("archived",        "Archived",            "Engagement closed"),
]
STAGE_KEYS = [s[0] for s in STAGES]

ADVANCE_TO = {
    "intake":          "scanned",
    "scanned":         "under_review",
    "under_review":    "generate_report",
    "generate_report": "archived",
}

STAGE_COLOR = {
    "intake":          "#8BAABF",
    "scanned":         CAP_BLUE,
    "under_review":    "#7B52AB",
    "generate_report": "#E8970A",
    "archived":        "#B0B0B0",
}

REC_CONFIG = {
    "recommend":  {"bg": "#E8F7EE", "color": "#1A6B3C", "border": "#A8D5B5", "icon": "✓", "label": "Recommend"},
    "reconsider": {"bg": "#FEF3E2", "color": "#92530C", "border": "#F6C87A", "icon": "◐", "label": "Reconsider"},
    "rule_out":   {"bg": "#FEF3E2", "color": "#92530C", "border": "#F6C87A", "icon": "◐", "label": "Reconsider"},
}

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def ensure_columns(con):
    for col, defn in [
        ("pipeline_status",              "TEXT DEFAULT 'scanned'"),
        ("summary",                      "TEXT"),
        ("detected_outcomes",            "TEXT"),
        ("missing_kpis",                 "TEXT"),
        ("transformation_opportunities", "TEXT"),
        ("agentic_opportunities",       "TEXT"),
        ("kpi_scenarios",               "TEXT"),
        ("value_pool_assessment",       "TEXT"),
        ("value_pool_ranking",          "TEXT"),
        ("value_pool_evidence_gaps",    "TEXT"),
        ("sow_text",                     "TEXT"),
        ("agent_name",                   "TEXT"),
        ("value_attribution",            "TEXT"),
        ("engagement_manager",           "TEXT"),
        ("revenue_gain",               "REAL DEFAULT 0"),
        ("deal_size",                  "REAL DEFAULT 0"),
        ("intake_enriched",            "INTEGER DEFAULT 0"),
        ("reviewer_remarks",           "TEXT"),
        ("reviewer_name",              "TEXT"),
        ("reviewer_role",              "TEXT"),
        ("human_approved",             "INTEGER DEFAULT 0"),
        ("uploaded_documents",         "TEXT"),
    ]:
        try:
            con.execute(f"ALTER TABLE runs ADD COLUMN {col} {defn}")
            con.commit()
        except Exception:
            pass
    # Migrate legacy 'verdict' stage → 'under_review'; 'rule_out' → 'reconsider'
    try:
        con.execute("UPDATE runs SET pipeline_status='under_review' WHERE pipeline_status='verdict'")
        con.execute("UPDATE runs SET recommendation='reconsider' WHERE recommendation='rule_out'")
        con.commit()
    except Exception:
        pass
    # Back-fill deal_size for existing rows that have none
    try:
        rows = con.execute("SELECT DISTINCT opportunity_id FROM runs WHERE deal_size IS NULL OR deal_size = 0").fetchall()
        for (oid,) in rows:
            ds = get_deal_size(oid)
            if ds:
                con.execute("UPDATE runs SET deal_size=? WHERE opportunity_id=?", (ds, oid))
        con.commit()
    except Exception:
        pass
    # Back-fill revenue_gain for existing rows that have none
    try:
        rows = con.execute("SELECT DISTINCT opportunity_id FROM runs WHERE (revenue_gain IS NULL OR revenue_gain = 0) AND pipeline_status != 'intake'").fetchall()
        for (oid,) in rows:
            rg = get_revenue_gain(oid)
            if rg:
                con.execute("UPDATE runs SET revenue_gain=? WHERE opportunity_id=?", (rg, oid))
        con.commit()
    except Exception:
        pass
    # Back-fill human_approved for cards already in generate_report / archived
    try:
        con.execute("UPDATE runs SET human_approved=1 WHERE pipeline_status IN ('generate_report','archived') AND (human_approved IS NULL OR human_approved = 0)")
        con.commit()
    except Exception:
        pass

def log_run(result: dict, db_path: str, pipeline_status: str = "scanned", sow_text: str = "", uploaded_documents: list | None = None) -> None:
    opp_id = result.get("opportunity_id", "")
    mgr    = get_manager(opp_id)
    con    = sqlite3.connect(db_path)
    ensure_columns(con)
    # Preserve reviewer-side state across a re-run so approvals aren't wiped
    prev = con.execute(
        "SELECT reviewer_remarks, reviewer_name, reviewer_role, human_approved "
        "FROM runs WHERE opportunity_id=? ORDER BY created_at DESC LIMIT 1",
        (opp_id,),
    ).fetchone()
    rv_remarks = prev[0] if prev else None
    rv_name    = prev[1] if prev else None
    rv_role    = prev[2] if prev else None
    rv_appr    = prev[3] if prev else 0
    con.execute("""
      INSERT OR REPLACE INTO runs
        (run_id, opportunity_id, engagement_name, recommendation,
         status, pipeline_status, hours_saved, created_at,
         summary, detected_outcomes, missing_kpis, transformation_opportunities, agentic_opportunities,
         kpi_scenarios, value_pool_assessment, value_pool_ranking, value_pool_evidence_gaps,
         sow_text, uploaded_documents, agent_name, value_attribution, engagement_manager, revenue_gain,
         deal_size, intake_enriched,
         reviewer_remarks, reviewer_name, reviewer_role, human_approved)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
      result.get("run_id"), opp_id, result.get("engagement_name"),
      result.get("recommendation"), result.get("status", "draft"),
      pipeline_status, result.get("hours_saved"),
      datetime.now(timezone.utc).isoformat(),
      result.get("summary"),
      json.dumps(result.get("detected_outcomes") or []),
      json.dumps(result.get("missing_kpis") or []),
      json.dumps(result.get("transformation_opportunities") or []),
      json.dumps(result.get("agentic_opportunities") or []),
      json.dumps(result.get("kpi_scenarios") or []),
      json.dumps(result.get("value_pool_assessment") or []),
      json.dumps(result.get("value_pool_ranking") or []),
      json.dumps(result.get("value_pool_evidence_gaps") or []),
      sow_text or "",
      (json.dumps(uploaded_documents) if uploaded_documents is not None else None),
      result.get("agent_name", ""),
      json.dumps(result.get("value_attribution") or {}),
      json.dumps(mgr),
      result.get("revenue_gain") or 0,
      result.get("deal_size") or 0,
      1 if result.get("deal_size") else 0,
      rv_remarks, rv_name, rv_role, rv_appr,
    ))
    con.commit()
    con.close()

# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------
def load_data(db_path: str) -> dict:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ensure_columns(con)

    latest = con.execute("""
        SELECT r.* FROM runs r
        INNER JOIN (
            SELECT opportunity_id, MAX(created_at) AS max_ts
            FROM runs GROUP BY opportunity_id
        ) m ON r.opportunity_id = m.opportunity_id AND r.created_at = m.max_ts
        ORDER BY r.created_at DESC
    """).fetchall()
    latest = [dict(r) for r in latest]

    for row in latest:
      for col in ("detected_outcomes", "missing_kpis", "transformation_opportunities", "agentic_opportunities", "kpi_scenarios", "value_pool_assessment", "value_pool_ranking", "value_pool_evidence_gaps", "uploaded_documents"):
        raw = row.get(col)
        if isinstance(raw, str):
          try:
            row[col] = json.loads(raw)
          except:
            row[col] = []
        elif raw is None:
          row[col] = []

      for col in ("value_attribution", "engagement_manager"):
        raw = row.get(col)
        if isinstance(raw, str):
          try:
            row[col] = json.loads(raw)
          except:
            row[col] = {}
        elif raw is None:
          row[col] = {}

      if not row.get("pipeline_status"):
        row["pipeline_status"] = "scanned"
      if not row.get("engagement_manager"):
        row["engagement_manager"] = get_manager(row.get("opportunity_id", ""))
      if not row.get("deal_size"):
        row["deal_size"] = get_deal_size(row.get("opportunity_id", ""))

    buckets = {s: [] for s in STAGE_KEYS}
    for row in latest:
        stage = row.get("pipeline_status", "scanned")
        if stage not in buckets: stage = "scanned"
        buckets[stage].append(row)

    total_runs    = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0] or 0
    total_opps    = len(latest)
    HOURS_PER_COL = 5  # hours saved per engagement per AI column
    # Col-2 savings realised when card has moved past 'scanned' (i.e. stage != intake)
    COL2_REALIZED_STAGES = {'scanned', 'under_review', 'generate_report', 'archived'}
    # Col-4 savings realised when card has moved into or past 'generate_report'
    COL4_REALIZED_STAGES = {'generate_report', 'archived'}
    col2_realized = sum(1 for r in latest if r.get('pipeline_status') in COL2_REALIZED_STAGES)
    col4_realized = sum(1 for r in latest if r.get('pipeline_status') in COL4_REALIZED_STAGES)
    total_hours   = round((col2_realized + col4_realized) * HOURS_PER_COL, 1)
    avg_hours     = round(total_hours / total_opps, 1) if total_opps else 0
    col2_remaining = total_opps - col2_realized
    col4_remaining = total_opps - col4_realized
    potential_remaining = round((col2_remaining + col4_remaining) * HOURS_PER_COL, 1)
    validated_cnt = len(buckets.get("generate_report", [])) + len(buckets.get("archived", []))
    coverage_pct  = round(validated_cnt / total_opps * 100) if total_opps else 0
    outcome_ready = len([r for r in latest if r.get("recommendation") == "recommend"])
    n_recommend  = len([r for r in latest if r.get("recommendation") == "recommend"])
    n_reconsider = len([r for r in latest if r.get("recommendation") == "reconsider"])
    n_rule_out   = len([r for r in latest if r.get("recommendation") == "rule_out"])

    total_revenue_gain = round(sum(r.get("revenue_gain") or 0 for r in latest), 0)
    avg_revenue_gain   = round(total_revenue_gain / total_opps, 0) if total_opps else 0
    recommend_revenue  = round(sum(r.get("revenue_gain") or 0 for r in latest if r.get("recommendation") == "recommend"), 0)

    # Run history per opportunity
    run_history: dict = {}
    for r in con.execute("""
        SELECT run_id, opportunity_id, agent_name, recommendation,
               hours_saved, created_at, pipeline_status
        FROM runs ORDER BY created_at DESC
    """).fetchall():
        oid = r[1]
        if oid not in run_history: run_history[oid] = []
        run_history[oid].append({
            "run_id": r[0], "agent_name": r[2], "recommendation": r[3],
            "hours_saved": r[4], "created_at": r[5], "pipeline_status": r[6],
        })

    con.close()
    return {
        "buckets": buckets, "total_runs": total_runs,
        "total_hours": total_hours, "avg_hours": avg_hours,
        "total_opps": total_opps, "validated_cnt": validated_cnt,
        "coverage_pct": coverage_pct, "outcome_ready": outcome_ready,
        "run_history": run_history,
        "n_recommend": n_recommend, "n_reconsider": n_reconsider, "n_rule_out": n_rule_out,
        "potential_remaining": potential_remaining,
        "total_revenue_gain": total_revenue_gain,
        "avg_revenue_gain": avg_revenue_gain,
        "recommend_revenue": recommend_revenue,
    }

# ---------------------------------------------------------------------------
# Card HTML
# ---------------------------------------------------------------------------
def initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()

def card_html(row: dict) -> str:
    rec     = row.get("recommendation", "")
    hours   = row.get("hours_saved") or 0
    opp     = row.get("opportunity_id", "")
    name    = row.get("engagement_name", "")
    stage   = row.get("pipeline_status", "")
    mgr     = row.get("engagement_manager") or get_manager(opp)
    summary = (row.get("summary") or "").strip()
    summary_short = summary[:85] + "…" if len(summary) > 85 else summary
    missing_kpis  = row.get("missing_kpis") or []
    kpi_count     = len(missing_kpis)
    next_s        = ADVANCE_TO.get(stage, "")
    is_intake     = stage == "intake"
    cfg           = REC_CONFIG.get(rec, {})

    advance_btn = ""
    extra_btn = ""

    mgr_ini = initials(mgr.get("name", "??"))

    has_sow = bool((row.get("sow_text") or "").strip())
    deal_size       = row.get("deal_size") or 0
    intake_enriched = bool(row.get("intake_enriched"))
    revenue_gain    = row.get("revenue_gain") or 0
    deal_pill = ""
    if deal_size:
        ds = deal_size
        if ds >= 1_000_000: ds_str = f"\u20ac{ds/1_000_000:.1f}M"
        elif ds >= 1_000:   ds_str = f"\u20ac{int(ds)//1_000:,}k"
        else:               ds_str = f"\u20ac{int(ds):,}"
        deal_pill = f'<span class="deal-pill">{ds_str} deal</span>'

    revenue_pill = ""
    if stage != "intake" and revenue_gain and deal_size:
        pct = round((revenue_gain / deal_size) * 100)
        revenue_pill = f'<span class="rev-pill" data-base-pct="{pct}">&#8599;&#8202;{pct}% revenue uplift</span>'

    if is_intake:
        sow_pill = ('<span class="sow-status sow-attached">&#10003;&ensp;SoW attached</span>'
                    if has_sow else
                    '<span class="sow-status sow-missing">&#9711;&ensp;No SoW attached</span>')
        action = ('' if has_sow else
                  f'<button onclick="event.stopPropagation();openDetail(\'{opp}\')" class="card-btn btn-outline">Attach SoW \u2192</button>')
        return f'''<div class="eng-card stage-intake" draggable="true" onclick="openDetail('{opp}')" id="card-{opp}" data-opp="{opp}" data-stage="intake" data-has-sow="{'1' if has_sow else '0'}">
  <button onclick="removeCard(event,'{opp}')" class="btn-remove" title="Remove">🗑</button>
  <div class="card-opp">{opp}</div>
  <div class="card-name">{name}</div>
  <div class="card-mgr"><span class="mgr-avatar">{mgr_ini}</span>{mgr.get("name","")}</div>
  {deal_pill}
  {sow_pill}
  {'<div class="card-actions" onclick="event.stopPropagation()">'+action+'</div>' if action else ''}
</div>'''


    approved = row.get("human_approved") or 0
    return f'''<div class="eng-card stage-{stage.replace("_","-")}" draggable="true" onclick="openDetail('{opp}')" id="card-{opp}" data-opp="{opp}" data-stage="{stage}" data-approved="{'1' if approved else '0'}">
  <button onclick="removeCard(event,'{opp}')" class="btn-remove" title="Remove">🗑</button>
  <div class="card-opp">{opp}</div>
  <div class="card-name">{name}</div>
  <div class="card-pills">{deal_pill}{revenue_pill}</div>
  <div class="card-verdict-row">
    <div class="card-mgr" style="margin-bottom:0"><span class="mgr-avatar">{mgr_ini}</span>{mgr.get("name","")}</div>
  </div>
</div>'''

# ---------------------------------------------------------------------------
# Detail payload
# ---------------------------------------------------------------------------
def _parse_json_list(val) -> list:
    """Safely coerce a DB value (JSON string or list) into a Python list."""
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        try:
            result = json.loads(val)
            return result if isinstance(result, list) else []
        except Exception:
            return []
    return []


def _parse_json_dict(val) -> dict:
    """Safely coerce a DB value (JSON string or dict) into a Python dict."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            result = json.loads(val)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}
    return {}


def build_detail_payload(row: dict, run_history: dict) -> dict:
    opp   = row.get("opportunity_id", "")
    mgr   = row.get("engagement_manager") or get_manager(opp)
    rec   = row.get("recommendation", "")
    stage = row.get("pipeline_status", "")
    cfg   = REC_CONFIG.get(rec, {"label": rec or "—", "icon": "·"})

    if rec == "recommend":
        direction = ("Proceed with outcome-based commercial model. KPIs are measurable, "
                     "baselines are confirmed, and the engagement structure supports "
                     "performance-linked fees.")
    elif rec == "reconsider":
        direction = ("Outcome-based pricing is feasible in principle, but KPI gaps must be "
                     "resolved before contract execution. Engage the client to define missing "
                     "baselines and measurement methodology.")
    elif not rec:
        direction = ("⚠ The Outcome Extraction Agent has not produced an assessment for this engagement yet. "
                     "Move the card back to Intake and drag it to column 2 to run the AI review.")
    else:
        direction = ("Outcome-based pricing is not viable in its current form. The contract "
                     "should remain T&M or fixed-fee unless the scope is restructured.")

    mgr_first = (mgr.get("name") or "the engagement manager").split()[0]
    approved = bool(row.get("human_approved"))
    remarks = (row.get("reviewer_remarks") or "").strip()
    reviewer_name = (row.get("reviewer_name") or "").strip()
    reviewer_role = (row.get("reviewer_role") or "").strip()
    reviewer_label = (f"{reviewer_name} — {reviewer_role}" if reviewer_name and reviewer_role
                      else (reviewer_name or reviewer_role or "Strategy / Bid Office"))
    action_label = "Next Action"

    if stage == "scanned":
        next_action = ("Outcomes extracted from SoW. Human review required — a Strategy or Bid Office "
                       "reviewer must validate the extracted outcomes, KPI gaps, and transformation "
                       "opportunities, then approve the engagement to generate the report.")
    elif stage == "under_review":
        if approved:
            action_label = "Human Review Log"
            if remarks:
                next_action = (f"✓ Approved by {reviewer_label} with remarks: “{remarks}” — "
                               "drag the card to column 4 to generate the report for the Engagement Manager.")
            else:
                next_action = (f"✓ Approved by {reviewer_label} without further remarks — "
                               "drag the card to column 4 to generate the report for the Engagement Manager.")
        else:
            next_action = ("Awaiting human review by a Strategy or Bid Office reviewer. Open the card "
                           "and approve the engagement (with or without remarks) to unlock report generation.")
    elif stage == "generate_report":
        action_label = "Human Review Log" if approved else "Next Action"
        if approved and remarks:
            next_action = (f"✓ Approved by {reviewer_label} with remarks: “{remarks}”. "
                           f"Report ready — send it to Engagement Manager {mgr_first} to drive the "
                           "final commercial decision with the client.")
        elif approved:
            next_action = (f"✓ Approved by {reviewer_label} without further remarks. "
                           f"Report ready — send it to Engagement Manager {mgr_first} to drive the "
                           "final commercial decision with the client.")
        else:
            next_action = ("Report generated. Send it to the Engagement Manager — it summarises the "
                           "extracted outcomes, KPI gaps, and recommended next steps so they can "
                           "make the final commercial decision with the client.")
    elif stage == "archived":
        next_action = ("Engagement archived. Drag back to Intake to restart the process "
                       "with a new or revised SoW.")
    else:
        next_action = "Review pending."

    return {
        "opportunity_id":            opp,
        "engagement_name":           row.get("engagement_name", ""),
        "stage":                     stage,
        "has_sow":                   bool((row.get("sow_text") or "").strip()),
        "recommendation":            rec,
        "rec_label":                 cfg["label"],
        "rec_icon":                  cfg["icon"],
        "summary":                   row.get("summary") or "",
        "detected_outcomes":         _parse_json_list(row.get("detected_outcomes")),
        "missing_kpis":              _parse_json_list(row.get("missing_kpis")),
        "transformation_opportunities": _parse_json_list(row.get("transformation_opportunities")),
        "agentic_opportunities": _parse_json_list(row.get("agentic_opportunities")),
        "kpi_scenarios":         _parse_json_list(row.get("kpi_scenarios")),
        "value_pool_assessment":     _parse_json_list(row.get("value_pool_assessment")),
        "value_pool_ranking":        _parse_json_list(row.get("value_pool_ranking")),
        "value_pool_evidence_gaps":  _parse_json_list(row.get("value_pool_evidence_gaps")),
        "hours_saved":               row.get("hours_saved") or 0,
        "deal_size":                 row.get("deal_size") or get_deal_size(opp),
        "revenue_gain":              row.get("revenue_gain") or 0,
        "value_attribution":         _parse_json_dict(row.get("value_attribution")),
        "commercial_direction":      direction,
        "next_action":               next_action,
        "action_label":              action_label,
        "manager":                   mgr,
        "uploaded_documents":        _parse_json_list(row.get("uploaded_documents")),
        "reviewer_remarks":           row.get("reviewer_remarks") or "",
        "reviewer_name":              row.get("reviewer_name") or "",
        "reviewer_role":              row.get("reviewer_role") or "",
        "human_approved":            bool(row.get("human_approved")),
        "run_history":               run_history.get(opp, [])[:10],
    }

# ---------------------------------------------------------------------------
# Board HTML
# ---------------------------------------------------------------------------
LANE_AGENT_BADGE = {
    "intake":          ("ai",    "\U0001f916", "Intake Agent"),
    "scanned":         ("ai",    "\U0001f916", "Outcome Extraction Agent"),
    "under_review":    ("human", "\U0001f464", "Human-in-the-Loop Review"),
    "generate_report": ("ai",    "\U0001f916", "Outcome Instructions Agent"),
}

def build_board(buckets: dict) -> str:
    parts = []
    for key, label, hint in STAGES:
        cards  = buckets.get(key, [])
        color  = STAGE_COLOR.get(key, CAP_BLUE)
        ghost = '<div class="ghost-intake-card" onclick="openIntakeModal()">&#43; Submit New Opportunity</div>' if key == "intake" else ""
        c_html = ghost + ("".join(card_html(c) for c in cards) or '<div class="lane-empty">No engagements</div>')
        badge = LANE_AGENT_BADGE.get(key)
        if badge:
            kind, icon, text = badge
            chip_cls = "lane-plugin-chip" + (" is-human" if kind == "human" else "")
            agent_html = (f'<div class="lane-plugin-wrap">'
                          f'<div class="{chip_cls}" title="{text}">'
                          f'<span class="lp-icon">{icon}</span>'
                          f'<span class="lp-text">{text}</span>'
                          f'</div>'
                          f'<div class="lane-plugin-connector"></div>'
                          f'</div>')
        else:
            agent_html = ""
        parts.append(f'''<div class="lane lane-{key.replace("_","-")}" style="--lane-color:{color}" data-lane="{key}">
  <div class="lane-header">
    <span class="lane-dot" style="background:{color}"></span>
    <span class="lane-title">{label}</span>
    <span class="lane-count">{len(cards)}</span>
  </div>
  <div class="lane-hint">{hint}</div>
  {agent_html}
  <div class="lane-cards" data-lane="{key}">{c_html}</div>
</div>''')
    return "\n".join(parts)

# ---------------------------------------------------------------------------
# Page render
# ---------------------------------------------------------------------------
def _fmt_eur(v: float) -> str:
    v = int(v or 0)
    if v >= 1_000_000: return f"€{v/1_000_000:.1f}M"
    if v >= 1_000:     return f"€{v//1_000:,}k"
    return f"€{v:,}"

def render(db_path: str) -> str:
    d          = load_data(db_path)
    board_html = build_board(d["buckets"])
    generated  = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    all_details = {}
    for rows in d["buckets"].values():
        for row in rows:
            opp = row.get("opportunity_id", "")
            all_details[opp] = build_detail_payload(row, d["run_history"])

    coverage_color = "#2D9E6B" if d["coverage_pct"] >= 50 else ("#E8970A" if d["coverage_pct"] > 0 else "#D94040")
    details_json   = json.dumps(all_details)

    html = HTML_TEMPLATE
    replacements = {
        "%%GENERATED%%":     generated,
        "%%TOTAL_OPPS%%":    str(d["total_opps"]),
        "%%TOTAL_HOURS%%":   str(d["total_hours"]),
        "%%AVG_HOURS%%":     str(d["avg_hours"]),
        "%%TOTAL_RUNS%%":    str(d["total_runs"]),
        "%%COVERAGE_PCT%%":  str(d["coverage_pct"]),
        "%%COVERAGE_COLOR%%": coverage_color,
        "%%VALIDATED_CNT%%": str(d["validated_cnt"]),
        "%%OUTCOME_READY%%": str(d["outcome_ready"]),
        "%%N_RECOMMEND%%":       str(d["n_recommend"]),
        "%%N_RECONSIDER%%":      str(d["n_reconsider"]),
        "%%N_RULE_OUT%%":        str(d["n_rule_out"]),
        "%%POTENTIAL_REMAINING%%": str(d["potential_remaining"]),
        "%%TOTAL_REVENUE_GAIN%%":  _fmt_eur(d["total_revenue_gain"]),
        "%%RECOMMEND_REVENUE%%":   _fmt_eur(d["recommend_revenue"]),
        "%%AVG_REVENUE_GAIN%%":    _fmt_eur(d["avg_revenue_gain"]),
        "%%TOTAL_REVENUE_RAW%%":   str(int(d["total_revenue_gain"])),
        "%%RECOMMEND_REVENUE_RAW%%": str(int(d["recommend_revenue"])),
        "%%N_RECOMMEND_ACTIVE%%": str(len([r for rows in d["buckets"].values() for r in rows if r.get("recommendation") == "recommend" and r.get("pipeline_status") != "archived"])),
        "%%BOARD_HTML%%":    board_html,
        "%%DETAILS_JSON%%":  details_json,
        "%%BLUE%%":          CAP_BLUE,
        "%%NAVY%%":          CAP_NAVY,
        "%%LIGHT%%":         CAP_LIGHT,
        "%%BORDER%%":        CAP_BORDER,
        "%%TOTAL_HOURS_RAW%%": str(d["total_hours"]),
    }
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Outcome Readiness Review · Contoso</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{
  font-family:'Segoe UI',Inter,system-ui,Arial,sans-serif;
  background:#E8EDF5;
  color:""" + CAP_NAVY + r""";
  min-height:100vh;
  font-size:15px;
  line-height:1.6;
  -webkit-font-smoothing:antialiased;
}

/* ─── Topbar ─────────────────────────────────────────────────────── */
.topbar{
  background:#fff;
  padding:.85rem 2rem .7rem;
  display:flex;align-items:flex-start;justify-content:space-between;
  border-bottom:1px solid """ + CAP_BORDER + r""";
  position:sticky;top:0;z-index:100;
}
.topbar-left{display:flex;flex-direction:column;gap:.15rem}
.topbar-brand{
  font-size:.88rem;font-weight:800;letter-spacing:.01em;
  color:""" + CAP_NAVY + r""";
}
.topbar-desc{font-size:.72rem;color:#5A7A96;line-height:1.5;max-width:54rem}
.topbar-right{font-size:.72rem;color:#7A96B0;display:flex;align-items:center;gap:.75rem;padding-top:.15rem}
.topbar-right a{color:""" + CAP_BLUE + r""";text-decoration:none;font-weight:600;transition:color .15s}
.topbar-right a:hover{color:#004E7A}
.topbar-action-btn{background:none;border:1.5px solid #C8D4E0;border-radius:6px;color:#4A6580;font-size:.72rem;font-weight:600;padding:.25rem .7rem;cursor:pointer;transition:background .15s,color .15s}
.topbar-action-btn:hover{background:#EEF4FB;color:#0070AD;border-color:#0070AD}
.topbar-reset-btn{border-color:#E8B4B4;color:#8C3030}
.topbar-reset-btn:hover{background:#FDECEA;color:#8C1818;border-color:#D94040}
.demo-badge{
  background:#EDF4FA;
  color:""" + CAP_BLUE + r""";
  border:1px solid #C0D8EA;
  border-radius:.25rem;
  padding:.1rem .45rem;
  font-size:.62rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
}

/* ─── Page ───────────────────────────────────────────────────────── */
.page{padding:1rem 0 4rem;width:100%}

/* ─── Cockpit header ─────────────────────────────────────────────── */
.cockpit-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:.7rem 1.4rem;border-bottom:1px solid #0A1628;
  background:linear-gradient(90deg,""" + CAP_NAVY + r""" 0%,#12355B 100%);
  box-shadow:0 1px 3px rgba(14,30,56,.18);
}
.cockpit-title{
  font-size:.82rem;font-weight:800;letter-spacing:.12em;
  text-transform:uppercase;color:#FFFFFF;
}
.cockpit-controls{display:flex;align-items:center;gap:.35rem}
.cockpit-tabs{display:flex;gap:.6rem;margin-left:auto}
.cockpit-tab{
  padding:.42rem 1.1rem;border-radius:.4rem;
  font-size:.82rem;font-weight:700;cursor:pointer;
  border:1.5px solid rgba(255,255,255,.35);background:transparent;color:#DCE8F4;
  transition:all .15s;letter-spacing:.01em;white-space:nowrap;
}
.cockpit-tab.active{background:#FFFFFF;border-color:#FFFFFF;color:""" + CAP_NAVY + r""";box-shadow:0 2px 8px rgba(0,0,0,.25)}
.cockpit-tab:hover:not(.active){background:rgba(255,255,255,.12);border-color:#FFFFFF;color:#FFFFFF}
.cockpit-scen-label{
  font-size:.6rem;font-weight:600;letter-spacing:.06em;
  text-transform:uppercase;color:#B8CCDE;margin-right:.25rem;
}

/* ─── KPI row ────────────────────────────────────────────────────── */
.kpi-row{display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border-bottom:1px solid #DDE5EF}
.kpi-tile{padding:.75rem 1.2rem .7rem;position:relative;overflow:hidden;border-right:1px solid #DDE5EF}
.kpi-tile:last-child{border-right:none}
.kpi-tile::after{
  content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:var(--kpi-accent,""" + CAP_BLUE + r""");
}
.kpi-label{font-size:.6rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#5A7A96;margin-bottom:.22rem}
.kpi-value{font-size:1.5rem;font-weight:800;line-height:1;color:var(--kpi-accent,""" + CAP_NAVY + r""");letter-spacing:-.02em}
.kpi-sub{font-size:.65rem;color:#607A94;margin-top:.2rem;line-height:1.4}

/* ─── Verdict mix (inside KPI tile) ──────────────────────────────── */
.verdict-mix-row{display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem}
.vm-chip{font-size:.82rem;font-weight:800;letter-spacing:-.01em;display:flex;align-items:center;gap:.15rem}
.vm-recommend{color:#1A6B3C}
.vm-reconsider{color:#92530C}
.vm-ruleout{color:#9B1C1C}
.verdict-mix-bar{
  height:4px;border-radius:2px;
  display:flex;overflow:hidden;gap:2px;
}
.osb-seg{height:100%;border-radius:2px;min-width:3px}
.osb-recommend{background:#2D9E6B}
.osb-reconsider{background:#E8970A}
.osb-ruleout{background:#D94040}

/* ─── Section header ─────────────────────────────────────────────── */
.section-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:.7rem 1.4rem;margin-bottom:0;
  background:linear-gradient(90deg,""" + CAP_NAVY + r""" 0%,#12355B 100%);
  border-bottom:1px solid #0A1628;
  box-shadow:0 1px 3px rgba(14,30,56,.18);
}
.section-title{
  font-size:.82rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.12em;color:#FFFFFF;
}

/* ─── Intake panel ───────────────────────────────────────────────── */
.intake-panel{
  padding:0 1.4rem;height:48px;
  border-top:1px solid #DDE5EF;
  display:flex;align-items:center;gap:.7rem;
  flex-wrap:nowrap;
}
.intake-label{
  font-size:.62rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  color:#5A7A96;white-space:nowrap;flex-shrink:0;
  padding-right:.9rem;border-right:1px solid #DDE5EF;margin-right:.3rem;
}
.intake-form{display:contents}
.intake-field{flex:0 0 auto;min-width:0}
.intake-field label{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#4A6A84}
.intake-field input[type=text]{
  height:30px;padding:0 .65rem;
  border:1px solid """ + CAP_BORDER + r""";
  border-radius:.35rem;font-size:.82rem;color:""" + CAP_NAVY + r""";
  background:#fff;outline:none;transition:border-color .15s,box-shadow .15s;
}
.intake-field input[type=text]:focus{
  border-color:""" + CAP_BLUE + r""";box-shadow:0 0 0 3px rgba(0,112,173,.1);
}
.intake-field input[type=text]::placeholder{color:#A8C0CF}
.drop-zone{
  flex:1;min-width:0;height:30px;
  border:1.5px dashed """ + CAP_BORDER + r""";
  border-radius:.35rem;
  display:flex;align-items:center;padding:0 .75rem;
  font-size:.78rem;color:#8BAABF;cursor:pointer;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  transition:border-color .15s,background .15s;
}
.drop-zone.drag-over{border-color:""" + CAP_BLUE + r""";background:#EDF5FF;color:""" + CAP_BLUE + r"""}
.drop-zone input[type=file]{display:none}
/* --- Intake modal --- */
.intake-modal-overlay{
  display:none;position:fixed;inset:0;z-index:500;
  background:rgba(14,30,56,.38);backdrop-filter:blur(3px);
  align-items:center;justify-content:center;
}
.intake-modal-overlay.open{display:flex}
.intake-modal{
  background:#fff;border-radius:.7rem;
  box-shadow:0 16px 48px rgba(14,30,56,.22);
  width:min(520px,92vw);padding:1.6rem 1.8rem 1.4rem;
  display:flex;flex-direction:column;gap:1rem;
  animation:slideUp .2s ease;
}
@keyframes slideUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.intake-modal-header{display:flex;align-items:flex-start;justify-content:space-between}
.intake-modal-title{font-size:1rem;font-weight:700;color:#0E1E38;letter-spacing:-.02em}
.intake-modal-sub{font-size:.73rem;color:#5A7A96;margin-top:.2rem}
.intake-modal-close{
  background:none;border:none;font-size:1.2rem;cursor:pointer;
  color:#7A96B0;line-height:1;padding:.1rem .25rem;
  border-radius:.25rem;transition:all .12s;
}
.intake-modal-close:hover{background:#F0F4FA;color:#1E3450}
.intake-modal-fields{display:flex;flex-direction:column;gap:.6rem}
.intake-modal-field input[type=text]{
  width:100%;box-sizing:border-box;
  padding:.5rem .7rem;border:1px solid #DDE5EF;border-radius:.35rem;
  font-size:.82rem;color:#0E1E38;background:#FAFCFE;
  transition:border-color .12s;outline:none;
}
.intake-modal-field input[type=text]:focus{border-color:#0070AD;background:#fff}
.intake-modal-dropzone{
  border:1.5px dashed #C8D8E8;border-radius:.45rem;
  padding:1.1rem;text-align:center;cursor:pointer;
  font-size:.78rem;color:#5A7A96;transition:all .14s;background:#FAFCFE;
}
.intake-modal-dropzone:hover,.intake-modal-dropzone.drag-over{
  border-color:#0070AD;background:#EDF5FF;color:#0070AD;
}
.intake-modal-dropzone input[type=file]{display:none}
.intake-modal-actions{display:flex;align-items:center;gap:.6rem;justify-content:flex-end}
.ghost-intake-card{
  border:1.5px dashed #B8CCD8;border-radius:.45rem;
  padding:.65rem .7rem;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  gap:.35rem;font-size:.78rem;font-weight:600;color:#5A8FB0;
  background:#F7FBFF;transition:all .15s;margin-bottom:.4rem;
}
.ghost-intake-card:hover{border-color:#0070AD;color:#0070AD;background:#EDF5FF}
.btn-scan{
  flex-shrink:0;height:30px;padding:0 1.1rem;
  background:""" + CAP_NAVY + r""";color:#fff;border:none;border-radius:.35rem;
  font-size:.8rem;font-weight:600;cursor:pointer;white-space:nowrap;
  transition:background .15s;
}
.btn-scan:hover{background:#1A3050}
.btn-scan:disabled{background:#B6C8D8;cursor:not-allowed}
.intake-status{font-size:.8rem;margin-top:.65rem;min-height:1.3em;color:#607A96}
.intake-status.error{color:#C93030}
.intake-status.ok{color:#1E9160}

/* ─── Layout ─────────────────────────────────────────────────────── */
.combined-panel{
  background:#fff;
  border:1px solid rgba(0,0,0,.08);
  border-radius:.7rem;
  box-shadow:0 2px 8px rgba(14,30,56,.07),0 8px 28px rgba(14,30,56,.05);
  overflow:hidden;
  margin:0 1.5rem;
}
.board-section{
  margin-top:.5rem;
  border:1px solid #DDE5EF;
  border-radius:.55rem;
  overflow:hidden;
  margin-left:1.5rem;margin-right:1.5rem;
}
.board-scroll{overflow-x:auto;padding:.2rem 0 .75rem}
.pipeline{
  display:grid;
  grid-template-columns:repeat(5,minmax(160px,1fr));
  gap:.75rem;min-width:800px;
  padding:0;
}

/* ─── Lane ───────────────────────────────────────────────────────── */
.lane{
  background:#F8FAFE;
  border:1px solid rgba(0,0,0,.07);
  border-radius:.55rem;
  padding:.7rem .7rem .85rem;
  box-shadow:0 1px 3px rgba(14,30,56,.05);
  min-width:0;
  border-top:3px solid var(--lane-color,""" + CAP_BLUE + r""");
}
.lane-header{display:flex;align-items:flex-start;gap:.35rem;margin-bottom:.2rem;min-height:2.6rem}
.lane-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;background:var(--lane-color,""" + CAP_BLUE + r""");margin-top:.42rem}
.lane-title{
  font-size:.84rem;font-weight:700;
  color:""" + CAP_NAVY + r""";flex:1;
  letter-spacing:.01em;min-width:0;
  white-space:normal;line-height:1.25;
}
.lane-count{
  background:rgba(0,0,0,.09);
  color:#3A5A78;
  border-radius:9999px;
  font-size:.68rem;font-weight:700;
  padding:.07rem .45rem;
  flex-shrink:0;
}
.lane-hint{font-size:.72rem;color:#6A8AA4;margin-bottom:.65rem;line-height:1.45;min-height:2.1rem}
.lane-cards{display:flex;flex-direction:column;gap:.5rem}
.lane-empty{
  font-size:.76rem;color:#7A9AB8;
  font-style:italic;
  padding:.55rem .3rem;
  border:1px dashed #C8D8E8;
  border-radius:.35rem;
  text-align:center;
}

/* ─── Engagement card ────────────────────────────────────────────── */
.eng-card{
  background:#fff;
  border:1.5px solid """ + CAP_BORDER + r""";
  border-radius:.45rem;
  padding:.6rem .7rem .55rem;
  cursor:pointer;
  box-shadow:0 1px 3px rgba(14,30,56,.06);
  transition:box-shadow .18s,border-color .18s,transform .15s;
  position:relative;
}
.eng-card:hover{
  box-shadow:0 5px 16px rgba(14,30,56,.13);
  border-color:var(--lane-color,""" + CAP_BLUE + r""");
  transform:translateY(-2px);
}
.eng-card.selected{
  border-color:""" + CAP_BLUE + r""";
  box-shadow:0 0 0 3px rgba(0,112,173,.15),0 4px 12px rgba(14,30,56,.1);
}
.card-opp{
  font-size:.67rem;color:#6A8AA4;
  letter-spacing:.04em;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;
  margin-bottom:.15rem;
  font-variant-numeric:tabular-nums;
  padding-right:3rem;
}
.card-name{
  font-size:.88rem;font-weight:600;
  color:""" + CAP_NAVY + r""";line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;
  word-break:break-word;
  margin-bottom:.2rem;
}
.card-verdict-row{
  display:flex;align-items:center;
  gap:.3rem;
  margin-top:.3rem;
  min-width:0;
}
/* Hours badge — absolute top-right */
.card-hours{
  position:absolute;top:.45rem;right:.55rem;
  font-size:.64rem;color:#fff;white-space:nowrap;
  font-variant-numeric:tabular-nums;
  background:#3B6EA0;border-radius:9999px;
  padding:.1rem .38rem;line-height:1.4;
  font-weight:600;letter-spacing:-.01em;
}
/* Icon-only verdict badge */
.badge-rec{
  display:inline-flex;align-items:center;justify-content:center;
  width:1.3rem;height:1.3rem;border-radius:50%;
  font-size:.75rem;font-weight:700;
  line-height:1;flex-shrink:0;
  cursor:default;
}
.card-summary{
  font-size:.76rem;color:#3A5470;line-height:1.5;
  margin-bottom:.3rem;
  display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;
}
.card-kpi-gap{
  font-size:.69rem;color:#7A3E05;
  background:#FDF4E7;border:1px solid #F0C87A;
  border-radius:.25rem;padding:.12rem .38rem;
  display:inline-flex;align-items:center;gap:.25rem;
  margin-bottom:.3rem;
}
.lane-plugin-wrap{
  display:flex;flex-direction:column;align-items:stretch;
  margin:.35rem .1rem 0;
  padding-bottom:0;
}
.lane-plugin-chip{
  display:flex;align-items:center;justify-content:center;gap:.4rem;
  font-size:.64rem;font-weight:700;
  color:#2A4E6C;
  background:#fff;
  border:1.5px solid #B8D4EE;
  border-radius:.55rem;
  padding:0 .6rem;
  height:30px;
  box-sizing:border-box;
  box-shadow:0 2px 8px rgba(0,112,173,.10),0 1px 2px rgba(0,0,0,.06);
  letter-spacing:.03em;
  white-space:nowrap;
  overflow:hidden;
  position:relative;
  z-index:1;
  text-transform:uppercase;
}
.lane-plugin-chip .lp-icon{
  width:18px;height:18px;border-radius:50%;
  display:inline-flex;align-items:center;justify-content:center;
  background:#E8F2FC;color:#1E3450;
  font-size:.72rem;flex-shrink:0;
}
.lane-plugin-chip.is-human .lp-icon{background:#FFF1D6;color:#8A5A00}
.lane-plugin-chip.is-human{border-color:#F2C679}
.lane-plugin-chip .lp-text{
  overflow:hidden;text-overflow:ellipsis;
}
.lane-plugin-connector{
  width:2px;
  height:12px;
  background:linear-gradient(to bottom,#B8D4EE,transparent);
  margin:0 auto;
}
.card-mgr{
  display:flex;align-items:center;gap:.35rem;
  font-size:.72rem;color:#4A6A84;
  min-width:0;flex:1;
  overflow:hidden;white-space:nowrap;
}
.mgr-avatar{
  width:20px;height:20px;border-radius:50%;
  background:""" + CAP_BLUE + r""";color:#fff;
  font-size:.55rem;font-weight:700;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  letter-spacing:0;
}
.card-actions{display:flex;flex-direction:column;gap:.3rem;margin-top:.1rem}
/* SoW status pill on intake cards */
.sow-status{
  display:inline-flex;align-items:center;
  font-size:.67rem;font-weight:600;border-radius:.28rem;
  padding:.18rem .5rem;margin-bottom:.25rem;
}
.sow-attached{background:#E8F7EE;color:#1A6B3C;border:1px solid #A8D5B5}
.sow-missing{background:#F4F7FB;color:#7A96B0;border:1px solid #C8D8E8}
.deal-pill{
  display:inline-flex;align-items:center;
  font-size:.67rem;font-weight:700;border-radius:.28rem;
  padding:.18rem .55rem;margin-bottom:.22rem;
  background:#EEF5FF;color:#0054A3;border:1px solid #B8D0EF;
  letter-spacing:.01em;
}
.card-pills{display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.22rem;}
.card-pills .deal-pill,.card-pills .rev-pill{margin-bottom:0;}
.rev-pill{
  display:inline-flex;align-items:center;
  font-size:.67rem;font-weight:700;border-radius:.28rem;
  padding:.18rem .55rem;
  background:#EDFBF3;color:#1A6B3C;border:1px solid #A2D9B8;
  letter-spacing:.01em;
}
/* Outline CTA for attach SoW */
.btn-outline{
  background:#fff;color:#0070AD;
  border:1.5px solid #0070AD;border-radius:.35rem;
  font-size:.74rem;font-weight:600;padding:.3rem .7rem;cursor:pointer;
  transition:all .13s;text-align:center;
}
.btn-outline:hover{background:#EDF5FF}
.card-pending{
  font-size:.68rem;color:#AAC0D0;
  background:#F4F7FB;border:1.5px dashed #D0DCE8;
  border-radius:.3rem;padding:.25rem .5rem;
  text-align:center;
}

/* Card state coloring */
.stage-generate-report{background:#FEF8EC;border-color:#F0C860}
.stage-archived{opacity:.58;pointer-events:auto}

/* Card buttons */
.card-btn{
  width:100%;padding:.3rem .45rem;
  border-radius:.3rem;
  font-size:.74rem;font-weight:600;
  cursor:pointer;border:1.5px solid transparent;
  text-align:center;
  transition:background .12s,border-color .12s,box-shadow .12s,transform .1s;
  letter-spacing:.01em;
}
.card-btn:hover{transform:translateY(-1px);box-shadow:0 2px 6px rgba(0,0,0,.12)}
.card-btn:active{transform:none}
.btn-primary{background:""" + CAP_BLUE + r""";color:#fff;border-color:""" + CAP_BLUE + r"""}
.btn-primary:hover{background:#005C8F;border-color:#005C8F}
.btn-ghost{background:#EEF2F8;color:#5A7A99;border-color:#D4DDE8}
.btn-ghost:hover{background:#E4EBF4;border-color:#C0CDD8}
.btn-amber{background:#FEF3E0;color:#8A4D0A;border-color:#EDD080}
.btn-amber:hover{background:#FAEACA;border-color:#D4A840}
.btn-remove{
  position:absolute;bottom:.38rem;right:.42rem;
  background:none;border:none;cursor:pointer;
  font-size:.8rem;line-height:1;padding:.15rem;
  border-radius:.25rem;color:#B0BEC5;
  opacity:0;pointer-events:none;
  transition:color .12s,background .12s,opacity .12s;
  z-index:2;
}
.eng-card:hover .btn-remove{opacity:1;pointer-events:auto}
.btn-remove:hover{color:#9B3030;background:#FDECEA}

/* ─── Detail panel ───────────────────────────────────────────────── */
.detail-panel{display:none}/* replaced by popup */

/* ─── Detail popup overlay ─────────────────────────────────────── */
.detail-overlay{
  display:none;position:fixed;inset:0;
  background:rgba(8,18,38,.52);
  backdrop-filter:blur(3px);
  z-index:900;align-items:flex-start;justify-content:center;
  padding:calc(3.1rem + 1.25rem) 1.5rem 1.5rem;
  box-sizing:border-box;
}
.detail-overlay.open{display:flex}
.detail-popup{
  background:#fff;
  border:1px solid rgba(0,0,0,.09);
  border-radius:.7rem;
  box-shadow:0 8px 40px rgba(8,18,38,.22);
  width:min(620px,94vw);
  max-height:calc(100vh - 3.1rem - 2.5rem);
  overflow-y:auto;
  display:flex;flex-direction:column;
  animation:modal-in .2s ease;
}
.detail-popup-close{
  position:sticky;top:0;z-index:1;
  display:flex;justify-content:flex-end;
  padding:.4rem .5rem .1rem;
  background:#fff;
}
.detail-popup-close button{
  background:none;border:none;cursor:pointer;
  font-size:1.25rem;color:#AABFCC;line-height:1;
  padding:.15rem .3rem;border-radius:.3rem;
  transition:color .12s,background .12s;
}
.detail-popup-close button:hover{color:#1E3450;background:#F0F4FA}
.detail-empty{
  flex:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  padding:3.5rem 2rem;text-align:center;color:#AABFCC;
  min-height:320px;
}
.detail-empty-icon{font-size:2.8rem;margin-bottom:.85rem;opacity:.35}
.detail-empty-text{font-size:.9rem;line-height:1.65;color:#6A8AA4}

/* Detail panel inner content */
.detail-top{
  padding:1.3rem 1.4rem 1rem;
  border-bottom:1.5px solid """ + CAP_BORDER + r""";
  background:linear-gradient(to bottom,#FAFCFE,#fff);
  border-radius:.6rem .6rem 0 0;
}
.detail-opp{
  font-size:.70rem;color:#5A7A94;
  letter-spacing:.05em;margin-bottom:.28rem;
  text-transform:uppercase;font-weight:700;
}
.detail-name{
  font-size:1.08rem;font-weight:700;
  color:""" + CAP_NAVY + r""";line-height:1.35;
  margin-bottom:.65rem;
  letter-spacing:-.01em;
  word-break:break-word;
}
.detail-verdict-row{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap}

/* Detail verdict badge — larger than card badge */
.detail-verdict-badge{
  display:inline-flex;align-items:center;gap:.3rem;
  padding:.3rem .85rem;border-radius:.35rem;
  font-size:.82rem;font-weight:700;letter-spacing:.02em;
}
.detail-hours-badge{
  display:inline-flex;align-items:center;gap:.3rem;
  background:#EEF5FF;border:1.5px solid #C2D9F0;
  border-radius:.3rem;padding:.22rem .6rem;
  font-size:.76rem;font-weight:600;color:""" + CAP_BLUE + r""";
}
.detail-rev-row{
  display:flex;justify-content:space-between;align-items:center;
  padding:.28rem 0;border-bottom:1px solid #EEF3F8;
  font-size:.76rem;
}
.detail-rev-label{color:#6A8AA0;font-weight:500}
.detail-rev-val{font-weight:700;color:#1A3050}
.detail-body-wrap{padding:1.1rem 1.4rem 1.4rem;display:flex;flex-direction:column;gap:1.15rem}

/* Individual detail sections */
.ds{display:flex;flex-direction:column;gap:.45rem}
.ds-label{
  font-size:.70rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:#4A6A84;
}

/* Summary — hero block */
.ds-summary{
  font-size:.88rem;color:#1E3450;
  line-height:1.7;
}

/* Outcome / KPI list items */
.detail-list{display:flex;flex-direction:column;gap:.35rem}
.detail-list-item{
  font-size:.78rem;color:#2C4260;
  background:#F4F7FB;border:1px solid """ + CAP_BORDER + r""";
  border-radius:.35rem;padding:.35rem .55rem;
  line-height:1.45;display:flex;align-items:baseline;gap:.4rem;
}
.detail-list-item::before{content:'✓';color:#1E9160;flex-shrink:0;font-size:.72rem}
.detail-kpi-item{
  font-size:.82rem;color:#6A3005;
  background:#FDF4E7;border:1px solid #ECCF80;
  border-radius:.35rem;padding:.38rem .6rem;
  line-height:1.5;display:flex;align-items:baseline;gap:.4rem;
}
.detail-kpi-item::before{content:'⚠';flex-shrink:0;font-size:.75rem}

/* Commercial direction block */
.detail-direction{
  font-size:.85rem;color:#1E3450;line-height:1.7;
  background:#F0F5FA;
  border-left:3.5px solid """ + CAP_BLUE + r""";
  border-radius:0 .4rem .4rem 0;
  padding:.7rem 1rem;
}

/* Next action — prominent highlight */
.detail-action-box{
  background:linear-gradient(135deg,#F0FAF4,#E8F7F0);
  border:1.5px solid #8ED4AC;
  border-radius:.4rem;
  padding:.7rem 1rem;
  font-size:.85rem;color:#0D4A28;
  line-height:1.65;
  font-weight:500;
}

/* Manager card */
.mgr-card{
  display:flex;align-items:center;gap:.85rem;
  background:#F4F7FB;border:1px solid """ + CAP_BORDER + r""";
  border-radius:.45rem;padding:.65rem .85rem;
}
.mgr-avatar-lg{
  width:38px;height:38px;border-radius:50%;
  background:""" + CAP_NAVY + r""";color:#fff;
  font-size:.78rem;font-weight:700;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  letter-spacing:0;
  box-shadow:0 2px 6px rgba(14,30,56,.25);
}
.mgr-info{flex:1;min-width:0}
.mgr-name{font-size:.88rem;font-weight:600;color:""" + CAP_NAVY + r""";margin-bottom:.1rem}
.mgr-role{font-size:.75rem;color:#3A5A78}
.mgr-email{font-size:.72rem;color:#5A7A94;margin-top:.05rem}

/* Activate CTA */
.btn-activate{
  width:100%;
  padding:.65rem .9rem;
  background:""" + CAP_BLUE + r""";
  color:#fff;border:none;
  border-radius:.45rem;
  font-size:.84rem;font-weight:700;
  cursor:pointer;
  display:flex;align-items:center;justify-content:center;gap:.45rem;
  transition:background .15s,box-shadow .15s,transform .12s;
  margin-top:.75rem;
  letter-spacing:.01em;
}
.btn-activate:hover{
  background:#005C8F;
  box-shadow:0 4px 14px rgba(0,92,143,.35);
  transform:translateY(-1px);
}

/* Run history */
.run-history-item{
  display:flex;align-items:center;gap:.55rem;
  font-size:.78rem;color:#2C4260;
  padding:.38rem 0;border-bottom:1px solid #EEF2F8;
  min-width:0;
}
.run-history-item:last-child{border-bottom:none}
.run-ts{color:#5A7A94;font-size:.72rem;font-variant-numeric:tabular-nums;flex-shrink:0}

/* ─── Modal ──────────────────────────────────────────────────────── */
.modal-overlay{
  display:none;position:fixed;inset:0;
  background:rgba(8,18,38,.6);
  backdrop-filter:blur(4px);
  z-index:1000;align-items:center;justify-content:center;
}
.modal-overlay.open{display:flex}
.modal{
  background:#fff;border-radius:.75rem;
  box-shadow:0 24px 72px rgba(8,18,38,.35);
  width:min(700px,96vw);max-height:92vh;
  overflow-y:auto;padding:2.1rem;
  animation:modal-in .22s ease;
}
@keyframes modal-in{
  from{opacity:0;transform:translateY(-14px) scale(.97)}
  to{opacity:1;transform:none}
}
.modal-header{
  display:flex;align-items:flex-start;justify-content:space-between;
  margin-bottom:1.4rem;padding-bottom:1.1rem;
  border-bottom:1.5px solid """ + CAP_BORDER + r""";
}
.modal-title{font-size:1.08rem;font-weight:700;color:""" + CAP_NAVY + r""";line-height:1.3}
.modal-subtitle{font-size:.8rem;color:#8BAABF;margin-top:.2rem}
.modal-close{
  background:none;border:none;cursor:pointer;
  font-size:1.4rem;color:#AABFCC;line-height:1;
  padding:.1rem .2rem;
  transition:color .15s;
}
.modal-close:hover{color:""" + CAP_NAVY + r"""}
.modal-section{margin-bottom:1.3rem}
.modal-section-title{
  font-size:.72rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:#4A6A84;margin-bottom:.55rem;
}
.modal-body{
  font-size:.86rem;color:#1E3450;line-height:1.7;
  background:#F4F7FB;border-radius:.4rem;
  padding:.75rem .95rem;
}
.modal-body p{margin-bottom:.55rem}
.modal-body p:last-child{margin-bottom:0}
.modal-body ul{padding-left:1.2rem;display:flex;flex-direction:column;gap:.3rem}
.modal-actions{
  display:flex;gap:.8rem;flex-wrap:wrap;
  padding-top:1.1rem;border-top:1.5px solid """ + CAP_BORDER + r""";
  margin-top:1rem;
}
.btn-send{
  flex:1;padding:.6rem 1rem;
  background:""" + CAP_BLUE + r""";color:#fff;
  border:none;border-radius:.4rem;
  font-size:.84rem;font-weight:700;cursor:pointer;
  transition:background .15s,box-shadow .15s;
  letter-spacing:.01em;
}
.btn-send:hover{background:#005C8F;box-shadow:0 3px 10px rgba(0,92,143,.3)}
.btn-modal-ghost{
  flex:1;padding:.6rem 1rem;
  background:#F4F7FB;color:#607A96;
  border:1.5px solid """ + CAP_BORDER + r""";
  border-radius:.4rem;font-size:.84rem;font-weight:600;cursor:pointer;
  transition:background .12s;
}
.btn-modal-ghost:hover{background:#E8EDF5}

/* ─── Toast ──────────────────────────────────────────────────────── */
.toast{
  position:fixed;bottom:1.75rem;left:50%;
  transform:translateX(-50%) translateY(1.2rem);
  background:""" + CAP_NAVY + r""";color:#fff;
  border-radius:.45rem;
  padding:.65rem 1.4rem;
  font-size:.84rem;font-weight:500;
  box-shadow:0 6px 20px rgba(8,18,38,.35);
  opacity:0;transition:opacity .28s,transform .28s;
  pointer-events:none;white-space:nowrap;z-index:2000;
}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

/* ─── Misc ───────────────────────────────────────────────────────── */
a{color:""" + CAP_BLUE + r""";text-decoration:none}
a:hover{text-decoration:underline}
code{
  background:#EEF2F8;border:1px solid """ + CAP_BORDER + r""";
  padding:.1rem .35rem;border-radius:.25rem;
  font-size:.77rem;color:#334E68;
}
.footer{margin-top:3rem;text-align:center;font-size:.74rem;color:#AAC0CC}

/* ─── ROI panel (always-visible sliders) ─────────────────── */
.roi-assumptions{
  display:grid;grid-template-columns:repeat(5,1fr);gap:0;
  background:#FAFCFE;border-top:1px solid #DDE5EF;
  padding:.7rem 1.4rem .8rem;
}
.roi-bar-scen{
  padding:.18rem .55rem;border-radius:9999px;
  font-size:.6rem;font-weight:600;cursor:pointer;
  border:1px solid #C0D8EA;background:transparent;color:#5A7A96;
  transition:all .13s;letter-spacing:.01em;
}
.roi-bar-scen.active{background:""" + CAP_NAVY + r""";border-color:""" + CAP_NAVY + r""";color:#fff}
.roi-bar-scen:hover:not(.active){background:#EDF4FA}
.roi-expand-btn{
  font-size:.6rem;font-weight:600;color:#5A7A96;
  background:none;border:1px solid #C0D8EA;
  border-radius:.3rem;padding:.18rem .55rem;
  cursor:pointer;white-space:nowrap;flex-shrink:0;
  margin-left:.4rem;transition:all .12s;
}
.roi-expand-btn:hover{background:#EDF4FA;color:""" + CAP_NAVY + r"""}

/* ─── Financial Outlook section ──────────────────────────── */
.fin-section{
  border-bottom:1px solid #DDE5EF;
}
.fin-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:.55rem 1.4rem;border-bottom:1px solid #DDE5EF;
  background:""" + CAP_LIGHT + r""";
}
.fin-title{
  font-size:.68rem;font-weight:700;letter-spacing:.07em;
  text-transform:uppercase;color:#3A5A78;
}
.fin-tabs{display:flex;align-items:center;gap:.35rem}
.fin-tab{
  padding:.22rem .65rem;border-radius:9999px;
  font-size:.62rem;font-weight:600;cursor:pointer;
  border:1px solid #C0D8EA;background:transparent;color:#5A7A96;
  transition:all .13s;
}
.fin-tab.active{background:""" + CAP_NAVY + r""";border-color:""" + CAP_NAVY + r""";color:#fff}
.fin-tab:hover:not(.active){background:#EDF4FA}
.fin-metrics{
  display:grid;grid-template-columns:repeat(6,1fr);
  padding:0;background:#fff;
}
.fin-metric{
  padding:.65rem 1rem .6rem;
  border-right:1px solid #DDE5EF;
}
.fin-metric:last-child{border-right:none}
.fin-metric-label{
  font-size:.58rem;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;color:#5A7A96;margin-bottom:.18rem;
}
.fin-metric-value{
  font-size:1.2rem;font-weight:800;line-height:1;
  color:var(--fin-accent,""" + CAP_NAVY + r""");letter-spacing:-.02em;
}
.fin-metric-sub{font-size:.6rem;color:#7A96B0;margin-top:.15rem}
.roi-assumptions{
  display:grid;grid-template-columns:repeat(5,1fr);
  gap:.55rem;
  padding:.7rem 1.4rem .8rem;
  background:#FAFCFE;
  border-top:1px solid #DDE5EF;
}
.roi-assumption{display:flex;flex-direction:column;gap:.18rem}
.roi-assumption label{
  font-size:.63rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.06em;color:#2C4A64;
}
.roi-assumption-val{display:flex;align-items:center;gap:.4rem}
.roi-assumption input[type=range]{flex:1;height:4px;accent-color:#0070AD;cursor:pointer;min-width:0}
.roi-assumption span{
  font-size:.72rem;font-weight:700;color:#0E1E38;
  min-width:3rem;text-align:right;font-variant-numeric:tabular-nums;flex-shrink:0;
}
.roi-results{display:grid;grid-template-columns:repeat(6,1fr);gap:.55rem}
.roi-metric{
  padding:.45rem .65rem .4rem;
  border-bottom:2px solid var(--roi-accent,#0070AD);
}
.roi-metric-label{
  font-size:.61rem;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;color:#2C4A64;margin-bottom:.25rem;
}
.roi-metric-value{
  font-size:1rem;font-weight:700;line-height:1;
  color:var(--roi-accent,#0E1E38);letter-spacing:-.02em;
}
.roi-metric-sub{font-size:.65rem;color:#3A5470;margin-top:.18rem;line-height:1.3}
.roi-disclaimer{display:none}
@media(max-width:1199px){
  .roi-assumptions{grid-template-columns:repeat(3,1fr)}
  .roi-results{grid-template-columns:repeat(3,1fr)}
}
@media(max-width:599px){
  .roi-assumptions{grid-template-columns:repeat(2,1fr)}
  .roi-results{grid-template-columns:repeat(2,1fr)}
}

/* ─── Drag and drop ─────────────────────────────────────────────── */

/* Card being dragged */
.eng-card[draggable=true]{cursor:grab}
.eng-card[draggable=true]:active{cursor:grabbing}
.eng-card.dragging{
  opacity:.35;
  transform:scale(.97);
  box-shadow:none!important;
  pointer-events:none;
}

/* Drag ghost clone */
#drag-ghost{
  position:fixed;
  pointer-events:none;
  z-index:9000;
  opacity:.92;
  transform:rotate(2deg) scale(1.03);
  box-shadow:0 12px 32px rgba(14,30,56,.22);
  border-radius:.45rem;
  transition:none;
  width:var(--ghost-w,200px);
  background:#fff;
  border:1.5px solid """ + CAP_BLUE + r""";
  padding:.6rem .7rem .55rem;
  font-family:'Segoe UI',Inter,system-ui,Arial,sans-serif;
  font-size:15px;
}

/* Drop-target lane highlight */
.lane.drop-target{
  background:rgba(0,112,173,.06);
  border-color:""" + CAP_BLUE + r""";
  box-shadow:0 0 0 2px rgba(0,112,173,.2);
}
.lane.drop-target .lane-cards{
  outline:2px dashed rgba(0,112,173,.35);
  outline-offset:3px;
  border-radius:.35rem;
  min-height:48px;
}
.lane.drop-blocked{
  background:rgba(180,30,30,.04);
  border-color:#D94040;
  box-shadow:0 0 0 2px rgba(217,64,64,.18);
}
.lane.drop-blocked .lane-cards{
  outline:2px dashed rgba(217,64,64,.3);
  outline-offset:3px;
  border-radius:.35rem;
}
/* SoW-missing block: amber tone + inline hint */
.lane.drop-blocked-sow{
  background:rgba(180,110,0,.05);
  border-color:#C97B00;
  box-shadow:0 0 0 2px rgba(201,123,0,.22);
}
.lane.drop-blocked-sow .lane-cards{
  outline:2px dashed rgba(201,123,0,.35);
  outline-offset:3px;
  border-radius:.35rem;
}
.lane.drop-blocked-sow .lane-header::after{
  content:'\00a0\2014 attach a SoW first';
  font-size:.68rem;font-weight:400;
  color:#C97B00;letter-spacing:.01em;
}
/* Drop indicator line inside lane */
.drop-indicator{
  height:3px;background:""" + CAP_BLUE + r""";
  border-radius:2px;margin:.2rem 0;
  animation:pulse-indicator .8s ease-in-out infinite;
}
@keyframes pulse-indicator{0%,100%{opacity:.6}50%{opacity:1}}

/* ─── Card processing state ──────────────────────────────────────── */
.eng-card.processing{
  pointer-events:none;
  border-color:""" + CAP_BLUE + r"""!important;
  box-shadow:0 0 0 2px rgba(0,112,173,.18)!important;
  background:#EEF6FF!important;
}
.card-processing-overlay{
  display:flex;align-items:center;gap:.5rem;
  background:rgba(238,246,255,.92);
  border-radius:.35rem;
  padding:.4rem .55rem;
  margin-top:.35rem;
  font-size:.74rem;font-weight:600;color:""" + CAP_BLUE + r""";
}
.spinner{
  width:14px;height:14px;flex-shrink:0;
  border:2px solid rgba(0,112,173,.25);
  border-top-color:""" + CAP_BLUE + r""";
  border-radius:50%;
  animation:spin .75s linear infinite;
}
@keyframes spin{to{transform:rotate(360deg)}}
.processing-steps{
  display:flex;flex-direction:column;gap:.1rem;
  margin-top:.25rem;
  padding-left:.55rem;
}
.processing-step{
  font-size:.67rem;color:#7AA8CC;
  display:flex;align-items:center;gap:.3rem;
}
.processing-step.done{color:#1E9160}
.processing-step.active{color:""" + CAP_BLUE + r""";font-weight:600}

/* ─── Card completion / result-ready state ───────────────────────── */
.eng-card.result-ready{
  border-color:#1E9160!important;
  box-shadow:0 0 0 2px rgba(30,145,96,.2),0 4px 14px rgba(30,145,96,.12)!important;
  animation:result-pulse 2s ease-in-out 3;
}
@keyframes result-pulse{
  0%,100%{box-shadow:0 0 0 2px rgba(30,145,96,.2),0 4px 14px rgba(30,145,96,.12)}
  50%{box-shadow:0 0 0 4px rgba(30,145,96,.3),0 6px 20px rgba(30,145,96,.2)}
}
.card-result-cta{
  display:flex;align-items:center;justify-content:space-between;
  background:linear-gradient(135deg,#E8F7EE,#D4F0E2);
  border:1.5px solid #8ED4AC;
  border-radius:.35rem;
  padding:.32rem .5rem;
  margin-top:.3rem;
  font-size:.73rem;font-weight:700;color:#145E32;
  cursor:pointer;
  gap:.3rem;
}
.card-result-cta:hover{background:linear-gradient(135deg,#D4F0E2,#C0E8D4)}
.result-dot{
  width:7px;height:7px;border-radius:50%;
  background:#1E9160;flex-shrink:0;
  animation:blink-dot 1.4s ease-in-out 6;
}
@keyframes blink-dot{0%,100%{opacity:1}50%{opacity:.25}}

/* ─── HITL confirm modal ─────────────────────────────────────────── */
.hitl-overlay{
  display:none;position:fixed;inset:0;
  background:rgba(8,18,38,.55);
  backdrop-filter:blur(4px);
  z-index:1100;
  align-items:center;justify-content:center;
}
.hitl-overlay.open{display:flex}
.hitl-modal{
  background:#fff;
  border-radius:.7rem;
  box-shadow:0 20px 60px rgba(8,18,38,.3);
  width:min(520px,96vw);
  padding:0;
  animation:modal-in .2s ease;
  overflow:hidden;
}
.hitl-header{
  padding:1.25rem 1.4rem .9rem;
  border-bottom:1.5px solid """ + CAP_BORDER + r""";
  display:flex;align-items:flex-start;gap:.9rem;
}
.hitl-agent-icon{
  width:40px;height:40px;border-radius:.45rem;
  display:flex;align-items:center;justify-content:center;
  font-size:1.2rem;flex-shrink:0;
  background:""" + CAP_LIGHT + r""";
  border:1.5px solid """ + CAP_BORDER + r""";
}
.hitl-header-text{flex:1}
.hitl-title{font-size:.95rem;font-weight:700;color:""" + CAP_NAVY + r""";margin-bottom:.15rem}
.hitl-subtitle{font-size:.80rem;color:#3A5A78;line-height:1.5}
.hitl-body{padding:1rem 1.4rem}
.hitl-engagement{
  background:#F4F7FB;border:1px solid """ + CAP_BORDER + r""";
  border-radius:.4rem;padding:.65rem .85rem;margin-bottom:.9rem;
}
.hitl-eng-id{font-size:.68rem;color:#5A7A94;letter-spacing:.04em;text-transform:uppercase;margin-bottom:.18rem}
.hitl-eng-name{font-size:.9rem;font-weight:600;color:""" + CAP_NAVY + r"""}
.hitl-desc{font-size:.85rem;color:#1E3450;line-height:1.65;margin-bottom:1rem}
.hitl-what{
  background:#EEF5FF;border:1.5px solid #C2D9F0;
  border-radius:.4rem;padding:.55rem .8rem;
  margin-bottom:1.1rem;
}
.hitl-what-label{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#3A5A78;margin-bottom:.3rem}
.hitl-what-steps{display:flex;flex-direction:column;gap:.22rem}
.hitl-what-step{font-size:.82rem;color:#1E3450;display:flex;align-items:baseline;gap:.4rem}
.hitl-what-step::before{content:'→';color:""" + CAP_BLUE + r""";font-size:.7rem;flex-shrink:0}
.hitl-actions{
  display:flex;gap:.75rem;
  padding:.9rem 1.4rem 1.1rem;
  border-top:1.5px solid """ + CAP_BORDER + r""";
}
.btn-hitl-confirm{
  flex:1;padding:.6rem .9rem;
  background:""" + CAP_BLUE + r""";color:#fff;
  border:none;border-radius:.4rem;
  font-size:.84rem;font-weight:700;cursor:pointer;
  display:flex;align-items:center;justify-content:center;gap:.4rem;
  transition:background .15s,box-shadow .15s,transform .1s;
  letter-spacing:.01em;
}
.btn-hitl-confirm:hover{
  background:#005C8F;
  box-shadow:0 3px 10px rgba(0,92,143,.3);
  transform:translateY(-1px);
}
.btn-hitl-cancel{
  padding:.6rem 1rem;
  background:#F4F7FB;color:#607A96;
  border:1.5px solid """ + CAP_BORDER + r""";
  border-radius:.4rem;
  font-size:.84rem;font-weight:600;cursor:pointer;
  transition:background .12s;
}
.btn-hitl-cancel:hover{background:#E8EDF5}

/* ─── Responsiveness ──────────────────────────────────────────────── */

/* Wide — 1400 px + : give board more room */
@media(min-width:1400px){
  .pipeline{grid-template-columns:repeat(5,minmax(190px,1fr))}
}

/* Medium — below 1200px */
@media(max-width:1199px){
  .combined-panel{margin:0 .75rem}
  .board-section{margin-top:.75rem}
  .kpi-row{grid-template-columns:repeat(2,1fr)}
}

/* Tablet — below 900px */
@media(max-width:899px){
  .page{padding:1.25rem 0 4rem}
  .kpi-row{grid-template-columns:repeat(2,1fr)}
  .pipeline{grid-template-columns:repeat(5,minmax(150px,1fr));min-width:750px}
}

/* Small — below 600px */
@media(max-width:599px){
  .topbar{padding:.6rem 1rem}
  .topbar-desc{display:none}
  .fin-metrics{grid-template-columns:repeat(3,1fr)}
  .page{padding:1rem 0 4rem}
  .kpi-row{grid-template-columns:repeat(2,1fr);gap:.65rem}
  .kpi-value{font-size:1.75rem}
  .intake-form{flex-direction:column}
  .drop-zone{min-width:0}
  .board-scroll{padding:0 .75rem .75rem}
  .pipeline{grid-template-columns:repeat(5,minmax(138px,1fr));min-width:690px}
  .detail-name{font-size:.95rem}
}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <span class="topbar-brand">Contoso &middot; Agentic Outcome-Based Modelling in Practice</span>
    <span class="topbar-desc">An AI agent reviews Statements of Work, assesses measurability of proposed outcomes, and attributes indicative value &mdash; helping steering committees decide whether to pursue an outcome-based commercial model.</span>
  </div>
  <div class="topbar-right">
    <span class="demo-badge">Demo</span>
    <span>%%GENERATED%%</span>
    <button onclick="scanMissing()" class="topbar-action-btn" id="btn-scan-missing" title="Re-run extraction agent on all col 2+ cards that are missing AI data">&#9881;&ensp;Scan Missing</button>
    <button onclick="confirmResetDemo()" class="topbar-action-btn topbar-reset-btn" title="Reset all data and return all cards to Intake">&#8635;&ensp;Reset Demo</button>
    <a href="/docs" target="_blank" title="Intro to outcome-based models, value attribution, and how this solution applies the pattern">&#128218;&ensp;Docs &amp; About</a>
    <a href="https://blue-desert-08c52270f.6.azurestaticapps.net/deal" target="_blank" rel="noopener" title="Outcome-Based Maturity Assessment">&#127919;&ensp;Outcome Based Maturity Assessment</a>
    <a href="/">&#8635; Refresh</a>
  </div>
</div>

<div class="page">

<div class="combined-panel">

<!-- ─── Cockpit title bar ─────────────────────────────── -->
<div class="cockpit-header">
  <span class="cockpit-title">Value Steering Cockpit</span>
  <div class="cockpit-tabs">
    <button class="cockpit-tab" id="tab-efficiency" onclick="switchCockpit('efficiency')">&#129302;&ensp;AI Based SoW Analysis</button>
    <button class="cockpit-tab active" id="tab-revenue" onclick="switchCockpit('revenue')">&#128200;&ensp;Outcome Based Revenue Uplift Potential</button>
  </div>
</div>

<!-- ─── KPI tiles ─────────────────────────────────────── -->
<div class="kpi-row" id="kpi-efficiency" style="display:none">
  <div class="kpi-tile" style="--kpi-accent:%%BLUE%%">
    <div class="kpi-label">Pipeline</div>
    <div class="kpi-value">%%TOTAL_OPPS%%</div>
    <div class="kpi-sub">%%VALIDATED_CNT%% of %%TOTAL_OPPS%% through review (%%COVERAGE_PCT%%%)</div>
  </div>

  <div class="kpi-tile" style="--kpi-accent:#7B52AB">
    <div class="kpi-label">Potential Cost Saving Remaining</div>
    <div class="kpi-value" style="color:#7B52AB">%%POTENTIAL_REMAINING%%&thinsp;h</div>
    <div class="kpi-sub">%%N_RECOMMEND_ACTIVE%% recommended engagement(s) not yet closed &mdash; value still in pipeline</div>
  </div>

  <div class="kpi-tile" style="--kpi-accent:#1E9160">
    <div class="kpi-label">Agent Attributed Value (ledger)</div>
    <div class="kpi-value" style="color:#1E9160">%%TOTAL_HOURS%%&thinsp;h</div>
    <div class="kpi-sub">%%AVG_HOURS%% h avg &middot; %%TOTAL_RUNS%% agent runs</div>
  </div>
</div>

<!-- ─── Revenue Potential KPI row ────────────────────── -->
<div class="kpi-row" id="kpi-revenue">
  <div class="kpi-tile" style="--kpi-accent:#0070AD">
    <div class="kpi-label">Total Revenue Gain Identified</div>
    <div class="kpi-value" id="kpi-rev-total" style="color:#0070AD">%%TOTAL_REVENUE_GAIN%%</div>
    <div class="kpi-sub" id="kpi-rev-total-sub">Estimated uplift across all %%TOTAL_OPPS%% engagements</div>
  </div>

  <div class="kpi-tile" style="--kpi-accent:#1E9160">
    <div class="kpi-label">Recommend &rarr; Outcome Based</div>
    <div class="kpi-value" id="kpi-rev-recommend" style="color:#1E9160">%%RECOMMEND_REVENUE%%</div>
    <div class="kpi-sub">Revenue potential for engagements rated &lsquo;Recommend&rsquo;</div>
  </div>

  <div class="kpi-tile" style="--kpi-accent:#E8970A">
    <div class="kpi-label">Avg Revenue Gain / Engagement</div>
    <div class="kpi-value" id="kpi-rev-avg" style="color:#E8970A">%%AVG_REVENUE_GAIN%%</div>
    <div class="kpi-sub">Average uplift per engagement based on agent estimates</div>
  </div>
</div>

<!-- ─── Financial Outlook ─────────────────────────────── -->
<div class="fin-section" id="fin-efficiency-section" style="display:none">
  <div class="fin-header">
    <span class="fin-title">Financial Outlook &mdash; AI Efficiency</span>
    <div class="fin-tabs">
      <button class="fin-tab" id="fin-conservative" onclick="applyScenario('conservative')">&#9660; Conservative</button>
      <button class="fin-tab active" id="fin-expected" onclick="applyScenario('expected')">&#9679; Expected</button>
      <button class="fin-tab" id="fin-upside" onclick="applyScenario('upside')">&#9650; Upside</button>
    </div>
  </div>
  <div class="fin-metrics">
    <div class="fin-metric" style="--fin-accent:#0070AD"><div class="fin-metric-label">Gross Value / yr</div><div class="fin-metric-value" id="fin-gross">&mdash;</div><div class="fin-metric-sub" id="fin-gross-sub">&mdash;</div></div>
    <div class="fin-metric" style="--fin-accent:#8BAABF"><div class="fin-metric-label">Build Cost</div><div class="fin-metric-value" id="fin-build">&mdash;</div><div class="fin-metric-sub">Initial investment</div></div>
    <div class="fin-metric" style="--fin-accent:#8BAABF"><div class="fin-metric-label">Annual OpEx</div><div class="fin-metric-value" id="fin-opex">&mdash;</div><div class="fin-metric-sub" id="fin-opex-sub">&mdash;</div></div>
    <div class="fin-metric" style="--fin-accent:#1E9160"><div class="fin-metric-label">Net Value</div><div class="fin-metric-value" id="fin-net">&mdash;</div><div class="fin-metric-sub">12-month net</div></div>
    <div class="fin-metric" style="--fin-accent:#7B52AB"><div class="fin-metric-label">Indicative ROI</div><div class="fin-metric-value" id="fin-roi">&mdash;</div><div class="fin-metric-sub">Net &divide; total cost</div></div>
    <div class="fin-metric" style="--fin-accent:#6B42A8"><div class="fin-metric-label">Payback</div><div class="fin-metric-value" id="fin-payback">&mdash;</div><div class="fin-metric-sub">Months to recover</div></div>
  </div>
</div>

<!-- ─── Assumptions sliders ─────────────────────────────── -->
<div class="roi-assumptions" id="roi-assumptions" style="display:none">
      <div class="roi-assumption">
        <label>Analyst rate (&#8364;/h)</label>
        <div class="roi-assumption-val">
          <input type="range" id="ra-rate" min="60" max="200" step="5" value="110" oninput="updateRoi()">
          <span id="ra-rate-val">&#8364;110</span>
        </div>
      </div>
      <div class="roi-assumption">
        <label>Build cost (&#8364;k)</label>
        <div class="roi-assumption-val">
          <input type="range" id="ra-build" min="20" max="400" step="10" value="120" oninput="updateRoi()">
          <span id="ra-build-val">&#8364;120k</span>
        </div>
      </div>
      <div class="roi-assumption">
        <label>Monthly opex (&#8364;k)</label>
        <div class="roi-assumption-val">
          <input type="range" id="ra-opex" min="1" max="30" step="1" value="6" oninput="updateRoi()">
          <span id="ra-opex-val">&#8364;6k</span>
        </div>
      </div>
      <div class="roi-assumption">
        <label>Utilisation (%)</label>
        <div class="roi-assumption-val">
          <input type="range" id="ra-util" min="10" max="100" step="5" value="70" oninput="updateRoi()">
          <span id="ra-util-val">70%</span>
        </div>
      </div>
      <div class="roi-assumption">
        <label>Annual throughput</label>
        <div class="roi-assumption-val">
          <input type="range" id="ra-hours" min="100" max="2000" step="50" value="600" oninput="updateRoi()">
          <span id="ra-hours-val">600 h</span>
        </div>
      </div>
</div>

<!-- ─── Revenue Potential Financial Outlook ──────────────────── -->
<div class="fin-section" id="fin-revenue-section">
  <div class="fin-header">
    <span class="fin-title">Revenue Outlook &mdash; Outcome Based Pricing</span>
    <div class="fin-tabs">
      <button class="fin-tab" id="rev-conservative" onclick="applyRevenueScenario('conservative')">&#9660; Conservative</button>
      <button class="fin-tab active" id="rev-expected" onclick="applyRevenueScenario('expected')">&#9679; Expected</button>
      <button class="fin-tab" id="rev-upside" onclick="applyRevenueScenario('upside')">&#9650; Upside</button>
    </div>
  </div>
  <div class="fin-metrics">
    <div class="fin-metric" style="--fin-accent:#0070AD"><div class="fin-metric-label">Year-1 Revenue</div><div class="fin-metric-value" id="rev-year1">&mdash;</div><div class="fin-metric-sub" id="rev-year1-sub">&mdash;</div></div>
    <div class="fin-metric" style="--fin-accent:#1E9160"><div class="fin-metric-label">Steady-State / yr</div><div class="fin-metric-value" id="rev-steady">&mdash;</div><div class="fin-metric-sub" id="rev-steady-sub">&mdash;</div></div>
    <div class="fin-metric" style="--fin-accent:#7B52AB"><div class="fin-metric-label">3-Year Revenue</div><div class="fin-metric-value" id="rev-3yr">&mdash;</div><div class="fin-metric-sub">Cumulative incl. renewals</div></div>
    <div class="fin-metric" style="--fin-accent:#E8970A"><div class="fin-metric-label">Revenue at Risk</div><div class="fin-metric-value" id="rev-risk">&mdash;</div><div class="fin-metric-sub">Identified potential not yet captured</div></div>
    <div class="fin-metric" style="--fin-accent:#0070AD"><div class="fin-metric-label">Conversion Rate</div><div class="fin-metric-value" id="rev-conv">&mdash;</div><div class="fin-metric-sub" id="rev-conv-sub">&mdash;</div></div>
    <div class="fin-metric" style="--fin-accent:#6B42A8"><div class="fin-metric-label">Revenue / Deal</div><div class="fin-metric-value" id="rev-deal">&mdash;</div><div class="fin-metric-sub">Avg converted engagement</div></div>
  </div>
</div>

<!-- ─── Revenue Assumptions sliders ──────────────────────────── -->
<div class="roi-assumptions" id="roi-revenue-assumptions">
  <div class="roi-assumption">
    <label>Conversion rate (%)</label>
    <div class="roi-assumption-val">
      <input type="range" id="rr-conv" min="10" max="100" step="5" value="60" oninput="updateRevenueRoi()">
      <span id="rr-conv-val">60%</span>
    </div>
  </div>
  <div class="roi-assumption">
    <label>Revenue realisation (%)</label>
    <div class="roi-assumption-val">
      <input type="range" id="rr-real" min="20" max="100" step="5" value="65" oninput="updateRevenueRoi()">
      <span id="rr-real-val">65%</span>
    </div>
  </div>
  <div class="roi-assumption">
    <label>Ramp-up (months)</label>
    <div class="roi-assumption-val">
      <input type="range" id="rr-ramp" min="1" max="24" step="1" value="9" oninput="updateRevenueRoi()">
      <span id="rr-ramp-val">9 mo</span>
    </div>
  </div>
  <div class="roi-assumption">
    <label>Deal tenure (years)</label>
    <div class="roi-assumption-val">
      <input type="range" id="rr-tenure" min="1" max="5" step="1" value="3" oninput="updateRevenueRoi()">
      <span id="rr-tenure-val">3 yr</span>
    </div>
  </div>
  <div class="roi-assumption">
    <label>Renewal rate (%)</label>
    <div class="roi-assumption-val">
      <input type="range" id="rr-renew" min="20" max="100" step="5" value="75" oninput="updateRevenueRoi()">
      <span id="rr-renew-val">75%</span>
    </div>
  </div>
</div>

</div><!-- /combined-panel -->

<!-- ─── Detail popup overlay ───────────────────────────────── -->
<div class="detail-overlay" id="detail-overlay" onclick="closeDetail(event)">
  <div class="detail-popup" id="detail-popup" onclick="event.stopPropagation()">
    <div class="detail-popup-close"><button onclick="closeDetail()">&times;</button></div>
    <div id="detail-content" style="display:flex;flex:1;flex-direction:column"></div>
  </div>
</div>

<!-- Intake modal -->
<div class="intake-modal-overlay" id="intake-modal-overlay" onclick="closeIntakeModal(event)">
  <div class="intake-modal" onclick="event.stopPropagation()">
    <div class="intake-modal-header">
      <div>
        <div class="intake-modal-title" id="intake-modal-title">Submit New Opportunity</div>
        <div class="intake-modal-sub" id="intake-modal-sub">Upload a Statement of Work for AI review</div>
      </div>
      <button class="intake-modal-close" onclick="closeIntakeModal()">&times;</button>
    </div>

    <!-- Step 1: upload -->
    <div id="intake-step-upload">
      <div class="intake-modal-fields">
        <div class="intake-modal-field">
          <input type="text" id="opp-id" placeholder="Opportunity ID (e.g. OPP-2025-042)"/>
        </div>
        <div class="intake-modal-field-hint" style="font-size:.7rem;color:#5A7A96;padding:.1rem .2rem .2rem">
          &#129504;&ensp;Engagement name, manager and deal size will be extracted automatically &mdash; you'll confirm them in the next step.
        </div>
      </div>
      <div class="intake-modal-dropzone" id="modal-drop-zone"
           onclick="document.getElementById('file-input').click()"
           ondragover="event.preventDefault();this.classList.add('drag-over')"
           ondragleave="this.classList.remove('drag-over')"
           ondrop="handleModalDrop(event)">
        <input type="file" id="file-input" accept=".pdf,.docx,.doc,.txt" onchange="onFileChosen(this)" multiple />
        <span id="drop-label">&#128196;&ensp;Drop or click to browse &mdash; PDF, DOCX or TXT &nbsp;<span style="background:#EEF5FF;color:#0070AD;border:1px solid #C2D9F0;border-radius:.25rem;padding:.05rem .38rem;font-size:.72rem;font-weight:700">up to 4 files</span></span>
      </div>
      <div id="selected-files-list" style="margin-top:0.45rem;font-size:.84rem;color:#28405A;min-height:1.2em"></div>
      <div class="intake-modal-actions">
        <div class="intake-status" id="upload-status" style="flex:1;font-size:.74rem;color:#5A7A96"></div>
        <button class="btn-modal-ghost" onclick="closeIntakeModal()">Cancel</button>
        <button class="btn-scan" id="upload-btn" onclick="submitUpload()" disabled>Intake the SoW &rarr;</button>
      </div>
    </div>

    <!-- Step 2: confirm extracted values -->
    <div id="intake-step-confirm" style="display:none">
      <div style="font-size:.78rem;color:#5A7A96;padding:.2rem .2rem .8rem;line-height:1.45">
        The Intake Agent extracted the values below from the SoW. Please verify &mdash; especially the
        <strong>engagement manager</strong> (must be a Contoso employee, not a client contact) and the
        <strong>deal size</strong>. Override any field that looks wrong before running the outcome scan.
      </div>
      <div class="intake-modal-fields" style="grid-template-columns:1fr">
        <div class="intake-modal-field">
          <label style="font-size:.65rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#5A7A96;display:block;margin-bottom:.25rem">Engagement name</label>
          <input type="text" id="confirm-eng-name" placeholder="e.g. Claims Automation &mdash; Vanguard Insurance"/>
        </div>
        <div class="intake-modal-field">
          <label style="font-size:.65rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#5A7A96;display:block;margin-bottom:.25rem">Engagement manager <span style="color:#9B1C1C;font-weight:500">(Contoso-side)</span></label>
          <input type="text" id="confirm-mgr-name" placeholder="Full name"/>
        </div>
        <div class="intake-modal-field">
          <label style="font-size:.65rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#5A7A96;display:block;margin-bottom:.25rem">Deal size (&euro;)</label>
          <input type="number" id="confirm-deal-size" placeholder="0" min="0" step="1000"/>
        </div>
      </div>
      <div class="intake-modal-actions">
        <div class="intake-status" id="confirm-status" style="flex:1;font-size:.74rem;color:#5A7A96"></div>
        <button class="btn-modal-ghost" onclick="closeIntakeModal()">Cancel</button>
        <button class="btn-scan" id="confirm-btn" onclick="submitConfirmedIntake()">&#9989;&ensp;Confirm &amp; run AI review</button>
      </div>
    </div>
  </div>
</div>

<div class="board-section">
  <div class="section-header">
    <span class="section-title">Engagement Pipeline</span>
    <span style="font-size:.72rem;font-weight:500;color:#3A5A78;background:#EDF4FA;border:1px solid #C8D8E8;border-radius:.35rem;padding:.15rem .65rem">&#128065;&ensp;Click any card to open detail view</span>
  </div>
  <div class="board-scroll">
    <div class="pipeline">%%BOARD_HTML%%</div>
  </div>
</div>

<p class="footer">
</p>

</div>

<div class="modal-overlay" id="modal-overlay" onclick="closeModal(event)">
  <div class="modal" id="modal" onclick="event.stopPropagation()">
    <div class="modal-header">
      <div>
        <div class="modal-title" id="modal-title">Instruction Package</div>
        <div class="modal-subtitle" id="modal-subtitle"></div>
      </div>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div id="modal-body"></div>
    <div class="modal-actions">
      <button class="btn-send" onclick="simulateSend()">&#9993;&ensp;Send to Engagement Manager</button>
      <button class="btn-modal-ghost" onclick="copyReport()" id="copy-report-btn">&#128203;&ensp;Copy report</button>
      <button class="btn-modal-ghost" onclick="closeModal()">Close</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<!-- Human-in-the-Loop Review Modal -->
<div class="hitl-overlay" id="hr-overlay">
  <div class="hitl-modal" id="hr-modal" style="max-width:540px">
    <div class="hitl-header">
      <div class="hitl-agent-icon" id="hr-icon">&#x1F464;</div>
      <div class="hitl-header-text">
        <div class="hitl-title">Human in the Loop Review</div>
        <div class="hitl-subtitle" id="hr-subtitle">Strategy / Bid Office review — validate the AI-extracted outcomes on behalf of the Engagement Manager before the report is generated.</div>
      </div>
    </div>
    <div class="hitl-body">
      <div class="hitl-engagement">
        <div class="hitl-eng-id" id="hr-eng-id"></div>
        <div class="hitl-eng-name" id="hr-eng-name"></div>
      </div>
      <div style="margin:12px 0 6px;font-size:.78rem;font-weight:700;color:#444;letter-spacing:.05em;text-transform:uppercase">Reviewer Identity</div>
      <div style="display:flex;gap:10px;margin-bottom:10px">
        <input id="hr-reviewer-name" type="text" placeholder="Your full name" oninput="hrUpdateReady()"
               style="flex:1;padding:8px 10px;border:1.5px solid #c8d6e2;border-radius:7px;font-size:.84rem;font-family:inherit;color:#1a2a3a;background:#f9fbfd;box-sizing:border-box">
        <select id="hr-reviewer-role" onchange="hrUpdateReady()"
                style="flex:1;padding:8px 10px;border:1.5px solid #c8d6e2;border-radius:7px;font-size:.84rem;font-family:inherit;color:#1a2a3a;background:#f9fbfd;box-sizing:border-box">
          <option value="">Select role…</option>
          <option value="Strategy Lead">Strategy Lead</option>
          <option value="Bid Office Manager">Bid Office Manager</option>
          <option value="Commercial Director">Commercial Director</option>
          <option value="Portfolio Manager">Portfolio Manager</option>
        </select>
      </div>
      <div style="font-size:.72rem;color:#6A839B;margin-bottom:12px">Reviews are performed by the Strategy or Bid Office — not by the Engagement Manager, who receives the final report.</div>
      <div style="margin:12px 0 6px;font-size:.78rem;font-weight:700;color:#444;letter-spacing:.05em;text-transform:uppercase">AI-Extracted Outcomes</div>
      <ul id="hr-outcomes" style="margin:0 0 14px 0;padding-left:1.3em;font-size:.85rem;color:#1a2a3a;line-height:1.7"></ul>
      <div style="margin:0 0 8px;font-size:.83rem;color:#555">Do you agree with these extracted outcomes?</div>
      <div style="display:flex;gap:10px;margin-bottom:14px">
        <button id="hr-agree-btn" onclick="hrSetAgree(true)" class="btn-hitl-confirm" style="flex:1;padding:8px 0;font-size:.84rem">&#10003;&ensp;Yes, I agree</button>
        <button id="hr-disagree-btn" onclick="hrSetAgree(false)" class="btn-hitl-cancel" style="flex:1;padding:8px 0;font-size:.84rem">&#10005;&ensp;No, I have remarks</button>
      </div>
      <div id="hr-remarks-wrap" style="display:none">
        <label style="font-size:.78rem;font-weight:700;color:#444;text-transform:uppercase;letter-spacing:.05em">Additional remarks for the Report Agent</label>
        <textarea id="hr-remarks" placeholder="Describe what was missed, incorrect, or should be taken into account…" style="width:100%;margin-top:6px;padding:9px 11px;border:1.5px solid #c8d6e2;border-radius:7px;font-size:.84rem;resize:vertical;min-height:80px;font-family:inherit;color:#1a2a3a;background:#f9fbfd;box-sizing:border-box"></textarea>
      </div>
    </div>
    <div class="hitl-actions">
      <button class="btn-hitl-confirm" id="hr-confirm-btn" onclick="hrConfirm()" disabled>&#9654;&ensp;Approve &amp; Proceed</button>
      <button class="btn-hitl-cancel" onclick="hrCancel()">Cancel</button>
    </div>
  </div>
</div>

<!-- HITL Confirmation Modal -->
<div class="hitl-overlay" id="hitl-overlay">
  <div class="hitl-modal" id="hitl-modal">
    <div class="hitl-header">
      <div class="hitl-agent-icon" id="hitl-agent-icon">🤖</div>
      <div class="hitl-header-text">
        <div class="hitl-title" id="hitl-title">Confirm Agent Action</div>
        <div class="hitl-subtitle" id="hitl-subtitle">Review the action below before the agent proceeds.</div>
      </div>
    </div>
    <div class="hitl-body">
      <div class="hitl-engagement">
        <div class="hitl-eng-id" id="hitl-eng-id"></div>
        <div class="hitl-eng-name" id="hitl-eng-name"></div>
      </div>
      <div class="hitl-desc" id="hitl-desc"></div>
      <div class="hitl-what">
        <div class="hitl-what-label">What the agent will do</div>
        <div class="hitl-what-steps" id="hitl-what-steps"></div>
      </div>
    </div>
    <div class="hitl-actions">
      <button class="btn-hitl-confirm" id="hitl-confirm-btn">&#9654;&ensp;Approve &amp; Run Agent</button>
      <button class="btn-hitl-cancel" id="hitl-cancel-btn">Cancel</button>
    </div>
  </div>
</div>

<script>
const DETAILS = %%DETAILS_JSON%%;
const REC_CFG = {
  recommend:  {bg:'#E6F6ED',color:'#145E32',border:'#8ED4AC',icon:'✓',label:'Recommend'},
  reconsider: {bg:'#FEF4E2',color:'#8A4D0A',border:'#EDD080',icon:'◐',label:'Reconsider'},
  rule_out:   {bg:'#FEF4E2',color:'#8A4D0A',border:'#EDD080',icon:'◐',label:'Reconsider'},
};
let activeOpp = null;

// ─── Lane interaction model ──────────────────────────────────────────────────
// behavior:
//   'direct'       – move card immediately, no agent, no confirm
//   'confirm'      – ask user to confirm, no agent call
//   'restart'      – HITL confirm → /advance to intake (clears AI data server-side)
//   'agent-scan'   – HITL confirm → call /scan endpoint → real agent processing
//   'agent-review' – HITL confirm → move to under_review → simulated processing
//   'agent-report' – HITL confirm → move to generate_report → simulated processing
//   'blocked'      – cannot drop here
const LANE_CONFIG = {
  intake:          { behavior:'restart',      accepts: ['archived'] },
  scanned:         { behavior:'agent-scan',   accepts: ['intake'] },
  under_review:    { behavior:'human-review', accepts: ['scanned'] },
  generate_report: { behavior:'human-gate', accepts: ['under_review'] },
  archived:        { behavior:'direct',       accepts: ['generate_report'] },
};

const AGENT_INFO = {
  'agent-scan': {
    icon: '🔍',
    title: 'Authorise Extraction Agent',
    subtitle: 'The Extraction Agent will read the SoW and return a structured outcome-readiness assessment.',
    desc: (engName) => `The SoW for <strong>${engName}</strong> will be submitted to the Extraction Agent for automated outcome-readiness analysis. This will take approximately 30–60 seconds.`,
    steps: [
      'Parse and index the Statement of Work',
      'Identify measurable outcomes and KPIs',
      'Assess commercial model suitability',
      'Return a structured outcome-readiness assessment',
    ],
    confirmLabel: '🔍  Run Extraction Agent',
    processingLabel: 'Scanning SoW…',
    processingSteps: ['Reading SoW…','Identifying outcomes…','Assessing KPIs…','Compiling assessment…'],
    resultLabel: 'Assessment ready',
  },
  'agent-review': {
    icon: '📋',
    title: 'Authorise Human Review',
    subtitle: 'Move to Human Review so an analyst can validate the AI assessment.',
    desc: (engName) => `The engagement <strong>${engName}</strong> will be moved to Human Review. An analyst will validate the AI assessment and approve it for report generation.`,
    steps: [
      'Transfer AI assessment to human reviewer',
      'Analyst validates detected outcomes and KPI gaps',
      'Analyst approves the engagement (or flags it for rescope)',
    ],
    confirmLabel: '📋  Start Human Review',
    processingLabel: 'Transferring to Human Review…',
    processingSteps: ['Loading AI assessment…','Preparing reviewer briefing…','Notifying analyst…'],
    resultLabel: 'Ready for human review',
  },
  'agent-report': {
    icon: '📄',
    title: 'Generate Report for Engagement Mgr',
    subtitle: 'The agent will produce a tailored outcome-readiness report for the Engagement Manager.',
    desc: (engName) => `The agent will generate a concise outcome-readiness report for <strong>${engName}</strong> based on the human-reviewed outcomes and KPI gaps. This saves the Engagement Manager up to 5 hours of preparation.`,
    steps: [
      'Compile reviewed outcomes and KPI gaps',
      'Draft action items and next steps for the Engagement Manager',
      'Summarise KPI gaps and resolution recommendations',
      'Produce ready-to-send outcome-readiness report',
    ],
    confirmLabel: '📄  Generate Report',
    processingLabel: 'Generating report…',
    processingSteps: ['Loading reviewed assessment…','Drafting action items…','Summarising KPI gaps…','Finalising report…'],
    resultLabel: 'Report ready',
  },
  'human-review': {
    icon: '\u{1F464}',
    title: 'Human in the Loop Review',
    subtitle: 'Review and validate the AI-extracted outcomes before proceeding.',
    desc: (engName) => `Validate the extracted outcomes for <strong>${engName}</strong> before the report is generated for the Engagement Manager.`,
    steps: [
      'Review AI-extracted outcomes and assessment',
      'Confirm or flag discrepancies with additional remarks',
      'Remarks are passed to the Report Agent in column 4',
    ],
    confirmLabel: '\u{1F464}\u2002Open Human Review',
    processingLabel: null,
    processingSteps: [],
    resultLabel: null,
  },
  'confirm': {
    icon: '✓',
    title: 'Confirm Stage Change',
    subtitle: 'No agent will run — this is a manual pipeline decision.',
    desc: (engName, targetLabel) => `You are about to move <strong>${engName}</strong> to <strong>${targetLabel}</strong>. This is a human decision — no agent will run automatically.`,
    steps: [
      'Record stage change in the pipeline',
      'Update engagement status for portfolio reporting',
    ],
    confirmLabel: '✓  Confirm Move',
    processingLabel: null,
    processingSteps: [],
    resultLabel: null,
  },
  'restart': {
    icon: '🔄',
    title: 'Restart Engagement',
    subtitle: 'This will clear all AI analysis and return the card to Intake.',
    desc: (engName) => `<strong>${engName}</strong> will be returned to <strong>Intake</strong>. All AI assessment data, recommendation, and attributed value will be cleared. The engagement can then be re-scanned with a new or revised SoW.`,
    steps: [
      'Clear AI assessment, recommendation, and attributed value',
      'Reset engagement to Intake stage',
      'SoW attachment preserved — re-run AI review to restart',
    ],
    confirmLabel: '🔄  Restart from Intake',
    processingLabel: null,
    processingSteps: [],
    resultLabel: null,
  },
};

// ─── Drag state ─────────────────────────────────────────────────────────────
let dragState = null; // { opp, fromLane, card, ghostEl }

function createGhost(card) {
  const rect = card.getBoundingClientRect();
  const ghost = document.createElement('div');
  ghost.id = 'drag-ghost';
  ghost.style.setProperty('--ghost-w', rect.width + 'px');
  // Copy inner content
  ghost.innerHTML = card.innerHTML;
  // Remove action buttons from ghost
  const acts = ghost.querySelector('.card-actions');
  if (acts) acts.remove();
  document.body.appendChild(ghost);
  return ghost;
}

document.addEventListener('dragstart', e => {
  const card = e.target.closest('.eng-card[data-opp]');
  if (!card) return;
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', card.dataset.opp);
  // Tiny transparent drag image so we control the ghost entirely
  const blank = document.createElement('canvas');
  blank.width = blank.height = 1;
  e.dataTransfer.setDragImage(blank, 0, 0);
  dragState = { opp: card.dataset.opp, fromLane: card.dataset.stage, card, startX: e.clientX, startY: e.clientY, didDrag: false };
  // Defer so the browser captures the original state first
  requestAnimationFrame(() => card.classList.add('dragging'));
  // Create floating ghost
  const ghost = createGhost(card);
  ghost.style.left = (e.clientX - 10) + 'px';
  ghost.style.top  = (e.clientY - 14) + 'px';
  dragState.ghostEl = ghost;
});

document.addEventListener('dragover', e => {
  e.preventDefault();
  if (!dragState) return;
  // Detect real drag movement
  const dx = Math.abs(e.clientX - (dragState.startX||0));
  const dy = Math.abs(e.clientY - (dragState.startY||0));
  if (dx > 5 || dy > 5) dragState.didDrag = true;
  // Move ghost
  if (dragState.ghostEl) {
    dragState.ghostEl.style.left = (e.clientX - 10) + 'px';
    dragState.ghostEl.style.top  = (e.clientY - 14) + 'px';
  }
  // Highlight target lane
  const targetLane = e.target.closest('[data-lane]');
  document.querySelectorAll('.lane').forEach(l => l.classList.remove('drop-target','drop-blocked','drop-blocked-sow'));
  if (!targetLane) return;
  const laneName = targetLane.dataset.lane;
  if (laneName === dragState.fromLane) return;
  const cfg = LANE_CONFIG[laneName];
  const lane = targetLane.closest('.lane') || targetLane;
  // Special guard: Intake → Scanned requires a SoW to be attached
  const sowMissing = dragState.fromLane === 'intake' && laneName === 'scanned'
    && dragState.card && dragState.card.dataset.hasSow !== '1';
  if (sowMissing) {
    lane.classList.add('drop-blocked', 'drop-blocked-sow');
    e.dataTransfer.dropEffect = 'none';
  } else if (cfg && cfg.accepts.includes(dragState.fromLane)) {
    lane.classList.add('drop-target');
    e.dataTransfer.dropEffect = 'move';
  } else {
    lane.classList.add('drop-blocked');
    e.dataTransfer.dropEffect = 'none';
  }
});

document.addEventListener('dragleave', e => {
  const related = e.relatedTarget;
  if (!related || !related.closest('.pipeline')) {
    document.querySelectorAll('.lane').forEach(l => l.classList.remove('drop-target','drop-blocked','drop-blocked-sow'));
  }
});

document.addEventListener('dragend', e => {
  if (!dragState) return;
  dragState.card.classList.remove('dragging');
  if (dragState.ghostEl) dragState.ghostEl.remove();
  document.querySelectorAll('.lane').forEach(l => l.classList.remove('drop-target','drop-blocked','drop-blocked-sow'));
  // If no real drag happened, fire the click manually
  if (!dragState.didDrag) {
    const opp = dragState.opp;
    dragState = null;
    openDetail(opp);
    return;
  }
  dragState = null;
});

document.addEventListener('drop', e => {
  e.preventDefault();
  if (!dragState) return;
  const targetLane = e.target.closest('[data-lane]');
  if (!targetLane) return;
  const toLane = targetLane.dataset.lane;
  if (toLane === dragState.fromLane) return;
  const cfg = LANE_CONFIG[toLane];
  if (!cfg || !cfg.accepts.includes(dragState.fromLane)) {
    showToast('⚠ Cannot move to that lane from here');
    return;
  }
  const { opp, fromLane } = dragState;
  handleDrop(opp, fromLane, toLane, cfg.behavior);
});

// ─── Drop routing ────────────────────────────────────────────────────────────
const LANE_LABELS = {
  intake:'Intake', scanned:'Extract Outcomes from SoW', under_review:'Human Review',
  generate_report:'Generate Instructions for Engagement Mgr', archived:'Archived',
};

function handleDrop(opp, fromLane, toLane, behavior) {
  const d = DETAILS[opp] || {};
  const engName = d.engagement_name || opp;
  // Guard: Intake → Scanned requires a SoW
  if (fromLane === 'intake' && toLane === 'scanned') {
    const card = document.getElementById('card-' + opp);
    const hasSow = card && card.dataset.hasSow === '1';
    if (!hasSow) {
      showToast('📎 Attach a SoW before sending this engagement to AI review.');
      return;
    }
  }
  if (behavior === 'direct') {
    doAdvance(opp, toLane, null);
  } else if (behavior === 'restart') {
    // Archived → Intake: confirm then clear AI data server-side
    openHitl(opp, fromLane, toLane, behavior, engName);
  } else if (behavior === 'human-review') {
    openHumanReview(opp, fromLane, toLane, engName);
  } else if (behavior === 'human-gate') {
    // col 3 → col 4: require prior human approval
    const card = document.getElementById('card-' + opp);
    const approved = card && card.dataset.approved === '1';
    if (!approved) {
      showToast('⚠ Complete the Human Review first — open the card in column 3 and approve the assessment.');
      return;
    }
    openHitl(opp, fromLane, toLane, 'agent-report', engName);
  } else if (behavior === 'agent-scan' || behavior === 'agent-review' || behavior === 'agent-report' || behavior === 'confirm') {
    openHitl(opp, fromLane, toLane, behavior, engName);
  }
}

// ─── HITL Modal ──────────────────────────────────────────────────────────────
let hitlPending = null;

function openHitl(opp, fromLane, toLane, behavior, engName) {
  hitlPending = { opp, fromLane, toLane, behavior };
  const info = (behavior === 'confirm' || behavior === 'restart')
    ? { ...AGENT_INFO[behavior],
        desc: () => AGENT_INFO[behavior].desc(engName, LANE_LABELS[toLane]),
        steps: AGENT_INFO[behavior].steps }
    : AGENT_INFO[behavior];

  document.getElementById('hitl-agent-icon').textContent = info.icon;
  document.getElementById('hitl-title').textContent = info.title;
  document.getElementById('hitl-subtitle').textContent = info.subtitle;
  document.getElementById('hitl-eng-id').textContent = opp;
  document.getElementById('hitl-eng-name').textContent = engName;
  document.getElementById('hitl-desc').innerHTML = info.desc(engName, LANE_LABELS[toLane]);
  document.getElementById('hitl-what-steps').innerHTML =
    info.steps.map(s=>`<div class="hitl-what-step">${s}</div>`).join('');
  const confirmBtn = document.getElementById('hitl-confirm-btn');
  confirmBtn.innerHTML = `${info.confirmLabel}`;
  document.getElementById('hitl-overlay').classList.add('open');
}

document.getElementById('hitl-confirm-btn').addEventListener('click', () => {
  if (!hitlPending) return;
  document.getElementById('hitl-overlay').classList.remove('open');
  const { opp, fromLane, toLane, behavior } = hitlPending;
  hitlPending = null;
  executeApprovedAction(opp, fromLane, toLane, behavior);
});

document.getElementById('hitl-cancel-btn').addEventListener('click', () => {
  document.getElementById('hitl-overlay').classList.remove('open');
  hitlPending = null;
  showToast('↩ Move cancelled — card stays in current lane');
});

document.getElementById('hitl-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('hitl-overlay')) {
    document.getElementById('hitl-cancel-btn').click();
  }
});

// ─── Human Review Modal ──────────────────────────────────────────────────────
let hrPending = null;
let hrAgreed  = null;

function openHumanReview(opp, fromLane, toLane, engName) {
  hrPending = { opp, fromLane, toLane };
  hrAgreed  = null;
  const d = DETAILS[opp] || {};
  let outcomes = [];
  try {
    outcomes = Array.isArray(d.detected_outcomes) ? d.detected_outcomes
      : (typeof d.detected_outcomes === 'string' ? JSON.parse(d.detected_outcomes || '[]') : []);
  } catch(e) { outcomes = []; }

  document.getElementById('hr-eng-id').textContent   = opp;
  document.getElementById('hr-eng-name').textContent = engName;
  const ul = document.getElementById('hr-outcomes');
  ul.innerHTML = outcomes.length
    ? outcomes.map(o => `<li>${o}</li>`).join('')
    : '<li style="color:#888;font-style:italic">No outcomes extracted yet — scan the SoW first.</li>';
  // Prefill reviewer identity from localStorage so it persists across reviews
  try {
    document.getElementById('hr-reviewer-name').value = localStorage.getItem('reviewerName') || '';
    document.getElementById('hr-reviewer-role').value = localStorage.getItem('reviewerRole') || '';
  } catch(_) {}
  document.getElementById('hr-remarks').value = '';
  document.getElementById('hr-remarks-wrap').style.display = 'none';
  document.getElementById('hr-confirm-btn').disabled = true;
  document.getElementById('hr-agree-btn').classList.remove('active-choice');
  document.getElementById('hr-disagree-btn').classList.remove('active-choice');
  document.getElementById('hr-overlay').classList.add('open');
}

function hrUpdateReady() {
  const name = (document.getElementById('hr-reviewer-name').value || '').trim();
  const role = document.getElementById('hr-reviewer-role').value;
  const btn = document.getElementById('hr-confirm-btn');
  btn.disabled = !(name && role && hrAgreed !== null);
}

function hrSetAgree(agreed) {
  hrAgreed = agreed;
  document.getElementById('hr-remarks-wrap').style.display = agreed ? 'none' : 'block';
  document.getElementById('hr-agree-btn').style.background    = agreed ? '#1E9160' : '';
  document.getElementById('hr-agree-btn').style.borderColor   = agreed ? '#1E9160' : '';
  document.getElementById('hr-disagree-btn').style.background = !agreed ? '#D94040' : '';
  document.getElementById('hr-disagree-btn').style.borderColor= !agreed ? '#D94040' : '';
  document.getElementById('hr-disagree-btn').style.color      = !agreed ? '#fff' : '';
  hrUpdateReady();
}

function hrConfirm() {
  if (!hrPending || hrAgreed === null) return;
  const name = (document.getElementById('hr-reviewer-name').value || '').trim();
  const role = document.getElementById('hr-reviewer-role').value;
  if (!name || !role) return;
  try {
    localStorage.setItem('reviewerName', name);
    localStorage.setItem('reviewerRole', role);
  } catch(_) {}
  const remarks = hrAgreed ? '' : (document.getElementById('hr-remarks').value.trim());
  document.getElementById('hr-overlay').classList.remove('open');
  const { opp, toLane } = hrPending;
  hrPending = null;
  // Save remarks to DB, then move the card
  fetch('/save-remarks', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ opportunity_id: opp, reviewer_remarks: remarks, agreed: hrAgreed, reviewer_name: name, reviewer_role: role })
  }).then(() => {
    // Mark card as approved in the DOM so the human-gate check works immediately
    const card = document.getElementById('card-' + opp);
    if (card) card.dataset.approved = '1';
    if (DETAILS[opp]) DETAILS[opp].human_approved = true;
  }).finally(() => {
    doAdvance(opp, 'under_review', null);
  });
}

function hrCancel() {
  document.getElementById('hr-overlay').classList.remove('open');
  hrPending = null;
  showToast('\u21A9 Review cancelled \u2014 card stays in current lane');
}

// ─── Reset Demo ──────────────────────────────────────────────────────────────
function confirmResetDemo() {
  if (!confirm('Reset the demo?\n\nThis will clear ALL agent output and reviewer remarks, and return every card to the Intake column so you can start a fresh demo run.')) return;
  const btn = document.getElementById('btn-scan-missing');
  showToast('\u231B Resetting demo\u2026 page will reload');
  fetch('/reset-demo', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(r => { if (!r.ok) throw new Error('Reset failed'); })
    .then(() => { setTimeout(() => location.reload(), 600); })
    .catch(err => showToast('\u26A0 Reset failed: ' + err.message));
}

// ─── Scan Missing ────────────────────────────────────────────────────────────
function scanMissing() {
  // Collect all OPP IDs in col 2+ that have no detected_outcomes
  const missing = Object.entries(DETAILS)
    .filter(([opp, d]) => d.stage !== 'intake' && (!d.detected_outcomes || !d.detected_outcomes.length))
    .map(([opp]) => opp);
  if (!missing.length) { showToast('\u2705 All cards already have agent data'); return; }
  const btn = document.getElementById('btn-scan-missing');
  btn.disabled = true;
  btn.textContent = '\u231B Scanning ' + missing.length + '\u2026';
  fetch('/batch-scan', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_ids: missing})})
    .then(r => r.json())
    .then(data => {
      btn.disabled = false; btn.innerHTML = '&#9881;&ensp;Scan Missing';
      showToast('\u2705 Scanned ' + (data.ok||0) + ' cards, ' + (data.failed||0) + ' failed — reloading\u2026');
      setTimeout(() => location.reload(), 1200);
    })
    .catch(err => {
      btn.disabled = false; btn.innerHTML = '&#9881;&ensp;Scan Missing';
      showToast('\u26A0 Batch scan failed: ' + err.message);
    });
}

document.getElementById('hr-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('hr-overlay')) hrCancel();
});

// ─── Execute approved action ─────────────────────────────────────────────────
function executeApprovedAction(opp, fromLane, toLane, behavior) {
  if (behavior === 'confirm' || behavior === 'restart') {
    doAdvance(opp, toLane, null);
    return;
  }
  if (behavior === 'agent-scan') {
    // Run the real scan FIRST; only advance the card if the agent succeeds.
    startAgentProcessing(opp, 'agent-scan', () => {
      doScanCall(opp);
    });
  } else if (behavior === 'agent-review' || behavior === 'human-review') {
    doAdvance(opp, 'under_review', null, /*silent*/ true);
  } else if (behavior === 'agent-report') {
    doAdvance(opp, 'generate_report', null, /*silent*/ true);
    startAgentProcessing(opp, 'agent-report', null, /*simulate*/true);
  }
}

// ─── Agent processing simulation ─────────────────────────────────────────────
function startAgentProcessing(opp, agentType, realCallback, simulate) {
  const card = document.getElementById('card-' + opp);
  if (!card) return;
  const info = AGENT_INFO[agentType];
  if (!info || !info.processingLabel) return;

  // Lock card
  card.classList.add('processing');
  // Remove old actions
  const acts = card.querySelector('.card-actions');
  if (acts) acts.innerHTML = '';

  // Build processing overlay
  const overlay = document.createElement('div');
  overlay.className = 'card-processing-overlay';
  overlay.innerHTML = `<div class="spinner"></div><span id="proc-label-${opp}">${info.processingLabel}</span>`;
  card.appendChild(overlay);

  // Step indicators
  if (info.processingSteps && info.processingSteps.length) {
    const stepsEl = document.createElement('div');
    stepsEl.className = 'processing-steps';
    stepsEl.id = 'proc-steps-' + opp;
    info.processingSteps.forEach((s, i) => {
      stepsEl.innerHTML += `<div class="processing-step" id="proc-step-${opp}-${i}">${s}</div>`;
    });
    card.appendChild(stepsEl);
  }

  // Animate steps
  const steps = info.processingSteps || [];
  const totalMs = simulate ? (2200 + steps.length * 800) : (steps.length * 900 + 1200);
  const perStep = Math.floor(totalMs / Math.max(steps.length, 1));
  steps.forEach((_, i) => {
    setTimeout(() => {
      document.querySelectorAll(`#proc-steps-${opp} .processing-step`).forEach((el, j) => {
        el.classList.remove('active','done');
        if (j < i) el.classList.add('done'), el.textContent = '✓ ' + steps[j];
        if (j === i) el.classList.add('active');
      });
    }, i * perStep);
  });

  // Complete
  setTimeout(() => {
    if (realCallback) {
      realCallback();
    } else {
      onAgentComplete(opp, agentType, simulate);
    }
  }, totalMs);
}

function onAgentComplete(opp, agentType, simulate) {
  const card = document.getElementById('card-' + opp);
  if (!card) return;
  const info = AGENT_INFO[agentType];
  // Remove processing UI
  const overlay = card.querySelector('.card-processing-overlay');
  if (overlay) overlay.remove();
  const stepsEl = document.getElementById('proc-steps-' + opp);
  if (stepsEl) stepsEl.remove();
  card.classList.remove('processing');

  if (info && info.resultLabel) {
    card.classList.add('result-ready');
    // Inject result CTA
    const cta = document.createElement('div');
    cta.className = 'card-result-cta';
    cta.innerHTML = `<div class="result-dot"></div><span>${info.resultLabel}</span><span style="font-size:.65rem;opacity:.7">→ View</span>`;
    cta.onclick = (e) => { e.stopPropagation(); openDetail(opp); };
    const acts = card.querySelector('.card-actions');
    if (acts) acts.prepend(cta);
    else card.appendChild(cta);
    showToast(`✓ ${info.resultLabel} for ${opp}`);
    // Full refresh after short delay to pull in new DB data
    setTimeout(() => location.reload(), 3500);
  }
}

function doScanCall(opp) {
  fetch('/scan', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_id:opp})})
    .then(r => r.ok ? r.json() : r.text().then(t=>{throw new Error(t);}))
    .then(() => {
      // Agent succeeded — now advance the card to 'scanned' and refresh
      fetch('/advance', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_id:opp, pipeline_status:'scanned'})})
        .finally(() => onAgentComplete(opp, 'agent-scan', false));
    })
    .catch(err => {
      console.error('Scan call failed:', err);
      const card = document.getElementById('card-' + opp);
      if (card) {
        card.classList.remove('processing');
        const ov = card.querySelector('.card-processing-overlay');
        if (ov) ov.remove();
      }
      showToast('\u26A0 AI Review failed — is the extraction agent running on port 8088? ' + String(err).slice(0,140));
    });
}

// ─── Advance helper ──────────────────────────────────────────────────────────
function doAdvance(opp, stage, btn, silent) {
  if (btn) { btn.disabled = true; btn.textContent = 'Moving…'; }
  fetch('/advance', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_id:opp,pipeline_status:stage})})
    .then(r => {
      if (r.ok) {
        if (!silent) location.reload();
      } else {
        if (btn) { btn.disabled = false; btn.textContent = 'Error — retry'; }
      }
    });
}

// ─── Upload ──────────────────────────────────────────────────────────────────
const dropZone  = document.getElementById('modal-drop-zone') || document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const statusEl  = document.getElementById('upload-status');
let chosenFiles  = [];
function fmtFileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
function renderSelectedFilesList(targetId, files) {
  const wrap = document.getElementById(targetId);
  if (!wrap) return;
  if (!files || !files.length) { wrap.innerHTML = ''; return; }
  const items = files.map((f, i) => {
    const sz = f.size ? ' <span style="color:#7A96B4;font-weight:500">' + fmtFileSize(f.size) + '</span>' : '';
    return `<div style="display:flex;align-items:center;gap:.35rem;padding:.22rem .5rem;background:#F0F5FB;border:1px solid #D0DCE8;border-radius:.3rem;font-size:.77rem;color:#1E3450;margin-bottom:.22rem">`
      + `<span style="font-size:.72rem;flex-shrink:0">&#128196;</span>`
      + `<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${f.name}${sz}</span>`
      + `<span style="font-size:.62rem;background:#DDE5EF;border-radius:.25rem;padding:.05rem .35rem;color:#4A6A84;flex-shrink:0">` + (i+1) + `/` + files.length + `</span>`
      + `</div>`;
  }).join('');
  const hint = files.length > 1
    ? `<div style="font-size:.7rem;color:#5A7A96;margin-top:.1rem">&#8505;&nbsp; ${files.length} documents will be concatenated and reviewed as one SoW</div>`
    : '';
  wrap.innerHTML = items + hint;
}
function onFileChosen(input) {
  const fileList = input && input.files ? Array.from(input.files) : [];
  // enforce max 4 files
  chosenFiles = fileList.slice(0, 4);
  const lbl = document.getElementById('drop-label');
  if (chosenFiles.length === 1) {
    if (lbl) lbl.textContent = '✓ ' + chosenFiles[0].name;
    uploadBtn.disabled = false;
  } else if (chosenFiles.length > 1) {
    if (lbl) lbl.textContent = '✓ ' + chosenFiles.length + (chosenFiles.length > 1 ? ' files selected' : ' file selected');
    uploadBtn.disabled = false;
  } else {
    if (lbl) lbl.innerHTML = '\uD83D\uDCC4\u2002Drop or click to browse PDF / DOCX / TXT';
    uploadBtn.disabled = true;
  }
  renderSelectedFilesList('selected-files-list', chosenFiles);
}
if (dropZone) {
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault(); dropZone.classList.remove('drag-over');
    const files = e.dataTransfer && e.dataTransfer.files ? e.dataTransfer.files : null;
    if (files && files.length) { fileInput.files = files; onFileChosen(fileInput); }
  });
}
function setStatus(msg, cls) { statusEl.textContent = msg; statusEl.className = 'intake-status' + (cls ? ' ' + cls : ''); }
let pendingOppId = null;
function submitUpload() {
  const oppId = document.getElementById('opp-id').value.trim();
  if (!oppId)      { setStatus('Please enter an Opportunity ID.', 'error'); return; }
  if (!chosenFiles || !chosenFiles.length) { setStatus('Please choose at least one file.', 'error'); return; }
  uploadBtn.disabled = true; setStatus('⏳ Extracting engagement details with AI agent… (30–60 s)');
  const fd = new FormData();
  // Append all selected files (server accepts multiple parts named 'file')
  chosenFiles.forEach(f => fd.append('file', f));
  fd.append('opportunity_id', oppId); fd.append('engagement_name', '');
  fetch('/upload', {method:'POST',body:fd})
    .then(async r => {
      const txt = await r.text();
      if (!r.ok) { setStatus('Error: '+txt,'error'); uploadBtn.disabled=false; return; }
      let data = {};
      try { data = JSON.parse(txt); } catch(_) {}
      pendingOppId = data.opportunity_id || oppId;
      // Populate and switch to the confirmation step
      document.getElementById('confirm-eng-name').value = data.engagement_title || '';
      document.getElementById('confirm-mgr-name').value = data.engagement_manager || '';
      document.getElementById('confirm-deal-size').value = data.deal_size ? Math.round(data.deal_size) : '';
      document.getElementById('intake-modal-title').textContent = 'Confirm extracted details';
      document.getElementById('intake-modal-sub').textContent  = 'Opportunity ' + pendingOppId + ' — verify and override if needed';
      document.getElementById('intake-step-upload').style.display  = 'none';
      document.getElementById('intake-step-confirm').style.display = 'block';
      const cs = document.getElementById('confirm-status');
      if (data.intake_error) { cs.textContent = '⚠ Intake agent offline — please fill manually. ('+data.intake_error+')'; cs.className='intake-status error'; }
      else { cs.textContent = '✓ Values extracted by Intake Agent — edit any incorrect entry.'; cs.className='intake-status ok'; }
    })
    .catch(e => { setStatus('Network error: '+e,'error'); uploadBtn.disabled=false; });
}
function submitConfirmedIntake() {
  const engName = document.getElementById('confirm-eng-name').value.trim();
  const mgrName = document.getElementById('confirm-mgr-name').value.trim();
  const dealStr = document.getElementById('confirm-deal-size').value.trim();
  const deal    = parseFloat(dealStr) || 0;
  const cs = document.getElementById('confirm-status');
  if (!engName) { cs.textContent = 'Engagement name is required.'; cs.className='intake-status error'; return; }
  if (!mgrName) { cs.textContent = 'Engagement manager is required.'; cs.className='intake-status error'; return; }
  if (!deal)    { cs.textContent = 'Deal size is required.'; cs.className='intake-status error'; return; }
  const btn = document.getElementById('confirm-btn');
  btn.disabled = true;
  cs.textContent = '⏳ Running Outcomes Extraction scan… (30–60 s)';
  cs.className = 'intake-status';
  fetch('/apply-intake', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      opportunity_id:     pendingOppId,
      engagement_name:    engName,
      engagement_manager: mgrName,
      deal_size:          deal,
    })
  })
    .then(async r => {
      const txt = await r.text();
      if (r.ok) {
        let rec=''; try{rec=JSON.parse(txt).recommendation;}catch(_){}
        cs.textContent = '✓ Assessment: '+(rec||'see pipeline')+'. Refreshing…';
        cs.className = 'intake-status ok';
        setTimeout(()=>location.reload(),1400);
      } else {
        cs.textContent = 'Error: '+txt; cs.className = 'intake-status error'; btn.disabled = false;
      }
    })
    .catch(e => { cs.textContent = 'Network error: '+e; cs.className = 'intake-status error'; btn.disabled = false; });
}

// ─── Board button actions (kept for backwards compat with card buttons) ──────
function scan(e, opp) {
  e.stopPropagation();
  const card = document.getElementById('card-'+opp);
  const btn = card ? card.querySelector('.btn-primary') : null;
  if (btn) { btn.disabled=true; btn.textContent='\u23F3 Intake Agent\u2026'; }
  // Step 1: run Intake Agent to extract title, manager, deal size
  fetch('/intake-scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_id:opp})})
    .then(r => r.ok ? r.json() : Promise.reject('Intake agent unavailable'))
    .catch(() => ({}))  // if intake agent is offline, continue without it
    .then(() => {
      if (btn) btn.textContent='\u23F3 Extracting outcomes\u2026';
      // Step 2: run Outcomes Extraction Agent
      return fetch('/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_id:opp})});
    })
    .then(r=>r.ok?r.json():r.text().then(t=>{throw new Error(t);}))
    .then(()=>location.reload())
    .catch(err=>{alert('Scan failed: '+err.message);if(btn){btn.disabled=false;btn.textContent='Run AI Review \u2192';}});
}
function advance(e, oppId, nextStage) {
  e.stopPropagation();
  const btn = e.target; btn.disabled=true; btn.textContent='Moving…';
  fetch('/advance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_id:oppId,pipeline_status:nextStage})})
    .then(r=>{ if(r.ok) location.reload(); else{btn.disabled=false;btn.textContent='Error — retry';} });
}

// ─── Detail panel ─────────────────────────────────────────────────────────────
function openDetail(opp) {
  activeOpp = opp;
  const d = DETAILS[opp]; if (!d) return;
  document.querySelectorAll('.eng-card').forEach(c=>c.classList.remove('selected'));
  const card = document.getElementById('card-'+opp); if(card) card.classList.add('selected');
  const dc = document.getElementById('detail-content');
  dc.style.display = 'flex';

  // ── Intake: pre-analysis upload panel ──────────────────────────────
  if (d.stage === 'intake') {
    const mgr = d.manager || {};
    const ini = mgr.name ? mgr.name.split(' ').filter(Boolean).map(p=>p[0]).join('').slice(0,2).toUpperCase() : '??';
    const sowBadge = d.has_sow
      ? '<span style="background:#E8F7EE;color:#1A6B3C;border:1px solid #A8D5B5;padding:.15rem .5rem;border-radius:.28rem;font-size:.7rem;font-weight:600">&#10003; SoW attached</span>'
      : '<span style="background:#FEF3E2;color:#92530C;border:1px solid #F6C87A;padding:.15rem .5rem;border-radius:.28rem;font-size:.7rem;font-weight:600">&#9711; No SoW attached</span>';
    const scanBtn = d.has_sow
      ? `<button class="card-btn btn-primary" style="margin-top:.8rem" onclick="scan(event,'${opp}')">&#9654;&ensp;Run AI Review</button>`
      : '';
    dc.innerHTML = `
      <div class="detail-top">
        <div class="detail-opp">${d.opportunity_id}</div>
        <div class="detail-name">${d.engagement_name}</div>
        <div style="margin-top:.4rem">${sowBadge}</div>
      </div>
      <div class="detail-body-wrap">
        <div class="ds">
          <div class="ds-label">Attach / Replace SoW</div>
          <div style="font-size:.74rem;color:#5A7A96;margin-bottom:.7rem">Upload the Statement of Work to enable AI review. Accepted formats: PDF, DOCX, TXT.</div>
          <div class="intake-modal-dropzone" id="detail-drop-zone" style="margin-bottom:.5rem"
               onclick="document.getElementById('detail-file-input').click()"
               ondragover="event.preventDefault();this.classList.add('drag-over')"
               ondragleave="this.classList.remove('drag-over')"
               ondrop="handleDetailDrop(event,'${opp}')">
            <input type="file" id="detail-file-input" accept=".pdf,.docx,.doc,.txt" onchange="onDetailFileChosen(this,'${opp}')" multiple />
            <span id="detail-drop-label">${d.has_sow ? '&#128196;&ensp;Drop to replace &mdash; up to 4 files (PDF, DOCX, TXT)' : '&#128196;&ensp;Drop or click to browse &mdash; PDF, DOCX or TXT &nbsp;<span style="background:#EEF5FF;color:#0070AD;border:1px solid #C2D9F0;border-radius:.25rem;padding:.05rem .38rem;font-size:.72rem;font-weight:700">up to 4 files</span>'}</span>
          </div>
          <div id="detail-selected-files-list" style="margin-top:.35rem;font-size:.82rem;color:#28405A;min-height:1.1em"></div>
          <div id="detail-upload-status" style="font-size:.74rem;color:#5A7A96;min-height:1.2em"></div>
          <div id="detail-upload-actions" style="display:flex;gap:.5rem;margin-top:.5rem;flex-wrap:wrap">
            <button id="detail-upload-btn" class="card-btn btn-primary" disabled onclick="submitDetailUpload('${opp}')">Upload &amp; Run AI Review &#8594;</button>
          </div>
          ${scanBtn}
        </div>
        <div class="ds">
          <div class="ds-label">Engagement Manager</div>
          <div class="mgr-card">
            <div class="mgr-avatar-lg">${ini}</div>
            <div class="mgr-info">
              <div class="mgr-name">${mgr.name||'—'}</div>
              <div class="mgr-role">${mgr.title||''}</div>
              <div class="mgr-email">${mgr.email||''}</div>
            </div>
          </div>
        </div>
        <div class="ds" style="opacity:.5;pointer-events:none">
          <div class="ds-label">Agent Assessment</div>
          <div style="font-size:.75rem;color:#AAC0CC;font-style:italic">Available after AI review is complete.</div>
        </div>
      </div>`;
    document.getElementById('detail-overlay').classList.add('open');
    document.body.style.overflow = 'hidden';
    return;
  }

  // ── Post-analysis stages ─────────────────────────────────────────
  const cfg = REC_CFG[d.recommendation] || {bg:'#EEF2F8',color:'#607A96',border:'#C8D4E0',icon:'·',label:d.rec_label||'—'};
  const mgr = d.manager || {};
  const ini = mgr.name ? mgr.name.split(' ').filter(Boolean).map(p=>p[0]).join('').slice(0,2).toUpperCase() : '??';

  const outHtml = (d.detected_outcomes && d.detected_outcomes.length)
    ? d.detected_outcomes.map(o=>`<div class="detail-list-item">${o}</div>`).join('')
    : '<div style="font-size:.78rem;color:#AABFCC;padding:.2rem 0">None detected</div>';

  const kpiHtml = (d.missing_kpis && d.missing_kpis.length)
    ? d.missing_kpis.map(k=>`<div class="detail-kpi-item">${k}</div>`).join('')
    : '<div style="font-size:.78rem;color:#1E9160;padding:.2rem 0">No gaps identified ✓</div>';

  const agenticHtml = (d.agentic_opportunities && d.agentic_opportunities.length)
    ? d.agentic_opportunities.map(a=>{
        const task = (typeof a==='string') ? a : (a.task||'—');
        const owner = a.current_owner ? `<span style="font-size:.66rem;color:#607A96">owner: ${a.current_owner}</span>` : '';
        const pat = a.agent_pattern ? `<span style="font-size:.66rem;color:#1A6B8E;background:#E8F2F8;border:1px solid #C8DDE8;border-radius:.22rem;padding:.04rem .3rem">${a.agent_pattern}</span>` : '';
        const feas = a.feasibility ? `<span style="font-size:.66rem;color:#666;background:#F0F4FA;border:1px solid #DDE5EF;border-radius:.22rem;padding:.04rem .3rem">feasibility: ${a.feasibility}</span>` : '';
        const hrs = (a.estimated_hours_saved_per_month != null) ? `<span style="font-size:.66rem;color:#1E9160;font-variant-numeric:tabular-nums">~${(+a.estimated_hours_saved_per_month).toFixed(1)} h/mo</span>` : '';
        const rat = a.rationale ? `<div style="font-size:.72rem;color:#5A6B7A;margin-top:.2rem">${a.rationale}</div>` : '';
        return `<div class="detail-list-item" style="padding:.45rem .55rem"><div style="font-weight:600;font-size:.78rem;color:#1A2B3A">${task}</div><div style="display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.25rem">${pat}${feas}${hrs}${owner}</div>${rat}</div>`;
      }).join('')
    : '<div style="font-size:.78rem;color:#AABFCC;padding:.2rem 0">No agentic delivery opportunities identified</div>';

  const kpiScenariosHtml = buildKpiScenariosHtml(d.kpi_scenarios, opp);
  const valuePoolRowsHtml = buildValuePoolHtml(d.value_pool_assessment, d.value_pool_ranking, d.value_pool_evidence_gaps, true);

  const STAGE_LABELS_SHORT = {
    intake: 'Intake', scanned: 'Extract Outcomes', under_review: 'Human Review',
    generate_report: 'Gen. Instructions', archived: 'Archived',
  };
  const histHtml = (d.run_history && d.run_history.length) ? d.run_history.map(r=>{
    const rc = REC_CFG[r.recommendation]||{};
    const badge = r.recommendation?`<span style="background:${rc.bg||'#eee'};color:${rc.color||'#666'};border:1px solid ${rc.border||'#ccc'};padding:.06rem .35rem;border-radius:.25rem;font-size:.64rem;font-weight:700">${rc.icon||'·'} ${rc.label||r.recommendation}</span>`:'';
    const ts = r.created_at?r.created_at.slice(0,16).replace('T',' '):'';
    const hrs = r.hours_saved?`<span style="font-size:.68rem;color:#8BAABF;font-variant-numeric:tabular-nums">${r.hours_saved.toFixed(1)} h attributed</span>`:'';
    const stageLabel = r.pipeline_status ? `<span style="font-size:.62rem;color:#8BAABF;background:#F0F4FA;border:1px solid #DDE5EF;border-radius:.22rem;padding:.04rem .3rem">${STAGE_LABELS_SHORT[r.pipeline_status]||r.pipeline_status}</span>` : '';
    return `<div class="run-history-item">${badge}${stageLabel}<span style="font-size:.64rem;color:#AABFCC">${r.agent_name||''}</span><span style="flex:1"></span>${hrs}<span class="run-ts">${ts}</span></div>`;
  }).join('') : '<div style="font-size:.74rem;color:#AABFCC">No run history</div>';

  dc.innerHTML = `
    <div class="detail-top">
      <div class="detail-opp">${d.opportunity_id}</div>
      <div class="detail-name">${d.engagement_name}</div>
      <div class="detail-verdict-row">
        <span class="detail-verdict-badge" style="background:${cfg.bg};color:${cfg.color};border:1.5px solid ${cfg.border}">${cfg.icon}&ensp;${cfg.label}</span>
      </div>
    </div>
    <div class="detail-body-wrap">
      <div class="ds">
        <div class="ds-label">Agent Assessment</div>
        <div class="ds-summary">${d.summary||'No summary available.'}</div>
      </div>
      <div class="ds">
        <div class="ds-label">Detected Outcomes</div>
        <div class="detail-list">${outHtml}</div>
      </div>
      <div class="ds">
        <div class="ds-label">KPI &amp; Measurement Gaps</div>
        <div style="font-size:.71rem;color:#AABFCC;margin-bottom:.3rem">Gaps that block Value Realization &mdash; must be resolved before outcome-based pricing</div>
        <div class="detail-list">${kpiHtml}</div>
      </div>
      <div class="ds">
        <div class="ds-label">&#128202;&ensp;KPI Scenario Analysis</div>
        <div style="font-size:.71rem;color:#AABFCC;margin-bottom:.45rem">3 distinct scenarios to build a compelling outcome-based contract &mdash; pick one or mix elements for the client conversation</div>
        ${kpiScenariosHtml}
      </div>
      ${valuePoolRowsHtml ? `<div class="ds">
        <div class="ds-label">\u{1F3AF}&ensp;AI Value Pool Assessment</div>
        <div style="font-size:.71rem;color:#AABFCC;margin-bottom:.45rem">Which of Capgemini's five AI value pools this engagement touches, ranked by opportunity</div>
        ${valuePoolRowsHtml}
      </div>` : ''}
      <div class="ds">
        <div class="ds-label">Agentic Delivery Opportunities</div>
        <div style="font-size:.71rem;color:#AABFCC;margin-bottom:.3rem">Tasks inside delivery where AI agents could automate or augment work &mdash; independent from the commercial pricing decision</div>
        <div class="detail-list">${agenticHtml}</div>
      </div>
      <div class="ds">
        <div class="ds-label">Recommended Commercial Direction</div>
        <div style="font-size:.71rem;color:#AABFCC;margin-bottom:.3rem">Based on outcome readiness assessment &mdash; feeds into Agent Value Attribution</div>
        <div class="detail-direction">${d.commercial_direction}</div>
      </div>
      <div class="ds">
        <div class="ds-label">${d.action_label||'Next Action'}</div>
        <div class="detail-action-box">${d.next_action}</div>
      </div>
      ${(() => {
        const rerunCfg = {
          scanned:         { title:'Re-run Extraction Agent',
                             desc:'Not happy with the extracted outcomes or the assessment? Provide steering instructions and re-run the <strong>Outcome Extraction Agent</strong>.',
                             placeholder:'e.g. Treat call-handling time reduction as the primary outcome. Ignore training hours as a KPI.',
                             btn:'Re-run Extraction Agent',
                             doing:'Calling the Outcome Extraction Agent with your instructions…' },
          under_review:    { title:'Re-run Extraction Agent',
                             desc:'Not satisfied with the AI assessment being reviewed? Provide steering instructions and re-run the <strong>Outcome Extraction Agent</strong>. Your reviewer identity, remarks, and approval are preserved.',
                             placeholder:'e.g. Re-weight outcomes toward customer retention. Flag the revenue baseline as unverified.',
                             btn:'Re-run Extraction Agent',
                             doing:'Calling the Outcome Extraction Agent with your instructions…' },
          generate_report: { title:'Re-run Report Agent',
                             desc:'Want a different angle on the report? Provide steering instructions and re-run the <strong>Report Agent</strong>. The underlying extraction, reviewer approval, and remarks are preserved.',
                             placeholder:'e.g. Emphasise the client-side value range. Frame the commercial direction as a 3-phase rollout.',
                             btn:'Re-run Report Agent',
                             doing:'Regenerating the report with your instructions…' },
        }[d.stage];
        if (!rerunCfg) return '';
        return `
      <div class="ds">
        <div class="ds-label">${rerunCfg.title}</div>
        <div style="font-size:.71rem;color:#5A7A94;margin-bottom:.45rem">${rerunCfg.desc}</div>
        <textarea id="rerun-instr-${opp}" placeholder="${rerunCfg.placeholder}"
                  style="width:100%;box-sizing:border-box;min-height:72px;padding:8px 10px;border:1.5px solid #c8d6e2;border-radius:7px;font-size:.82rem;font-family:inherit;color:#1a2a3a;background:#f9fbfd;resize:vertical"></textarea>
        <button id="rerun-btn-${opp}" onclick="rerunAgent('${opp}','${d.stage}')" class="card-btn btn-primary" style="margin-top:.6rem" data-label="${rerunCfg.btn}" data-doing="${rerunCfg.doing}">&#8635;&ensp;${rerunCfg.btn}</button>
        <div id="rerun-status-${opp}" style="font-size:.72rem;color:#5A7A94;margin-top:.4rem;min-height:1em"></div>
      </div>`;
      })()}
      <div class="ds">
        <div class="ds-label">Engagement Manager</div>
        <div class="mgr-card">
          <div class="mgr-avatar-lg">${ini}</div>
          <div class="mgr-info">
            <div class="mgr-name">${mgr.name||'—'}</div>
            <div class="mgr-role">${mgr.title||''}</div>
            <div class="mgr-email">${mgr.email||''}</div>
          </div>
        </div>
        ${d.stage === 'generate_report' ? `<button class="btn-activate" onclick="openModal('${opp}')">&#9993;&ensp;Send Instructions to ${(mgr.name||'').split(' ')[0]||'Manager'}</button>` : ''}
      </div>
      ${(d.deal_size || d.revenue_gain) ? `<div class="ds">
        <div class="ds-label">Revenue Potential</div>
        ${d.deal_size ? `<div class="detail-rev-row"><span class="detail-rev-label">Deal Size</span><span class="detail-rev-val">${fmtEur(d.deal_size)}</span></div>` : ''}
        ${d.revenue_gain > 0 ? `<div class="detail-rev-row"><span class="detail-rev-label">Estimated Revenue Gain (Outcome Model)</span><span class="detail-rev-val" style="color:#1E9160">${fmtEur(d.revenue_gain)}</span></div>
        <div class="detail-rev-row"><span class="detail-rev-label">Revenue Uplift %</span><span class="detail-rev-val" style="color:#E8970A">${d.deal_size > 0 ? ((d.revenue_gain / d.deal_size) * 100).toFixed(1) + '%' : '—'}</span></div>
        <div style="font-size:.69rem;color:#8BAABF;margin-top:.35rem">Estimated by the Outcome Extraction Agent — based on deal scope, contract model, and transformation opportunities identified in the SoW.</div>` : `<div style="font-size:.72rem;color:#AABFCC;font-style:italic">Revenue uplift estimate available after Outcome Extraction Agent runs.</div>`}
      </div>` : ''}
    </div>`;

  document.getElementById('detail-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}
function buildKpiScenariosHtml(scenarios, opp) {
  if (!scenarios || !scenarios.length) return '<div style="font-size:.78rem;color:#AABFCC;padding:.2rem 0">No KPI scenarios generated yet \u2014 re-scan to produce.</div>';
  var TYPE_CFG = {
    'delivery-performance': {color:'#1A7A4A',bg:'#E8F7EE',border:'#A8D5B5',badge:'Safest \u00b7 most contractable'},
    'commercial-outcome':   {color:'#5B3FA6',bg:'#F3EFFF',border:'#C5B5EF',badge:'Highest upside \u00b7 highest risk'},
    'quality-gated-hybrid': {color:'#B87A00',bg:'#FEF8EC',border:'#F0D080',badge:'\u2605 Most defensible in practice'},
  };
  var DFLT_TYPES = ['delivery-performance','commercial-outcome','quality-gated-hybrid'];
  var tabs = scenarios.map(function(s,i){
    var active = i===0;
    var t = s.scenario_type || DFLT_TYPES[i] || 'delivery-performance';
    var c = TYPE_CFG[t] || TYPE_CFG['delivery-performance'];
    return '<button onclick="switchKpiScenario(\''+opp+'\','+i+')" id="kst-'+opp+'-'+i+'" style="flex:1;padding:.32rem .5rem;font-size:.69rem;font-weight:700;border-radius:6px;cursor:pointer;text-align:left;line-height:1.3;transition:all .14s;border:1.5px solid '+(active?c.color:'#C8D8E8')+';background:'+(active?c.bg:'#F8FAFE')+';color:'+(active?c.color:'#607A94')+'">'
      +(s.scenario_name || c.badge.split('\u00b7')[0].trim())
      +'<div style="font-size:.61rem;font-weight:500;margin-top:.07rem;opacity:.75">'+c.badge+'</div>'
      +'</button>';
  }).join('');
  var panels = scenarios.map(function(s,i){
    var active = i===0;
    var t = s.scenario_type || DFLT_TYPES[i];
    var c = TYPE_CFG[t] || TYPE_CFG['delivery-performance'];
    function indBadge(label,val,invert){
      var lvl=(val||'medium').toLowerCase();
      var hi=invert?'low':'high', lo=invert?'high':'low';
      var clr=lvl===hi?'#1A7A4A':lvl===lo?'#9B1C1C':'#B87A00';
      var bg =lvl===hi?'#E8F7EE':lvl===lo?'#FEF3F2':'#FEF8EC';
      return '<span style="font-size:.62rem;font-weight:600;padding:.1rem .38rem;border-radius:99px;background:'+bg+';color:'+clr+'">'+label+': '+lvl+'</span>';
    }
    var badges = '<div style="display:flex;gap:.3rem;flex-wrap:wrap;margin:.45rem 0 .4rem">'
      +indBadge('Contractability',s.contractability,false)
      +indBadge('Governance burden',s.governance_burden,true)
      +indBadge('Data dependency',s.data_dependency,true)
      +'</div>';
    var kpiRows = (s.proposed_kpis||[]).map(function(k){
      if(typeof k==='string') return '<div style="display:flex;align-items:baseline;gap:.35rem;margin-bottom:.2rem"><span style="color:#1E9160;font-size:.72rem;flex-shrink:0">\u2713</span><span style="font-size:.76rem;color:#1E3450">'+k+'</span></div>';
      var aColor={'direct':'#1A7A4A','shared':'#B87A00','indirect':'#607A94'}[k.attribution_strength||'shared']||'#607A94';
      var aBg   ={'direct':'#E8F7EE','shared':'#FEF8EC','indirect':'#F0F4FA'}[k.attribution_strength||'shared']||'#F0F4FA';
      return '<div style="margin-bottom:.4rem;padding:.32rem .45rem;background:#F8FAFE;border:1px solid #E0E8F0;border-radius:.35rem">'
        +'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.5rem">'
        +'<span style="font-size:.75rem;font-weight:600;color:#1E3450;flex:1">'+k.kpi+'</span>'
        +'<span style="font-size:.61rem;font-weight:600;padding:.08rem .35rem;border-radius:99px;background:'+aBg+';color:'+aColor+';flex-shrink:0;white-space:nowrap">'+(k.attribution_strength||'shared')+'</span>'
        +'</div>'
        +(k.baseline_required?'<div style="font-size:.67rem;color:#7A96B0;margin-top:.15rem">Baseline: '+k.baseline_required+'</div>':'')
        +(k.measurement_source?'<div style="font-size:.67rem;color:#5A7A94;margin-top:.06rem">Source: <em>'+k.measurement_source+'</em></div>':'')
        +'</div>';
    }).join('');
    var upliftHtml='';
    if(s.uplift_range&&typeof s.uplift_range==='object'){
      var confClr={'high':'#1A7A4A','medium':'#B87A00','low':'#9B1C1C'}[s.uplift_range.confidence||'medium']||'#607A94';
      var confBg ={'high':'#E8F7EE','medium':'#FEF8EC','low':'#FEF3F2'}[s.uplift_range.confidence||'medium']||'#F0F4FA';
      upliftHtml='<div style="margin-top:.35rem;display:flex;align-items:center;gap:.45rem;flex-wrap:wrap">'
        +'<span style="font-size:.78rem;font-weight:700;color:#0F172A">'+s.uplift_range.min+'\u2013'+s.uplift_range.max+'% of deal size</span>'
        +'<span style="font-size:.63rem;color:#607A94">indicative uplift range</span>'
        +'<span style="font-size:.63rem;font-weight:600;padding:.09rem .38rem;border-radius:99px;color:'+confClr+';background:'+confBg+'">'+(s.uplift_range.confidence||'medium')+' confidence</span>'
        +'</div>';
    }else if(s.estimated_revenue_uplift_pct!=null){
      upliftHtml='<div style="margin-top:.35rem"><span style="font-size:.72rem;font-weight:700;color:#1E9160;background:#ECFDF5;border:1px solid #A7F3D0;padding:.18rem .5rem;border-radius:99px">\u2191\u2009+'+( +s.estimated_revenue_uplift_pct).toFixed(1)+'% uplift (indicative)</span></div>';
    }
    var nextHtml=s.next_action?'<div style="margin-top:.55rem;padding:.4rem .55rem;background:#F0F4FA;border-left:3px solid '+c.color+';border-radius:0 .3rem .3rem 0;font-size:.72rem;color:#1E3450"><strong>Next step:</strong> '+s.next_action+'</div>':'';
    var implHtml='';
    var impl=s.operational_implementation;
    if(impl&&typeof impl==='object'){
      var icClr={'low':'#1A7A4A','medium':'#B87A00','high':'#9B1C1C'}[impl.implementation_complexity||'medium']||'#607A94';
      var icBg ={'low':'#E8F7EE','medium':'#FEF8EC','high':'#FEF3F2'}[impl.implementation_complexity||'medium']||'#F0F4FA';
      implHtml='<div style="margin-top:.45rem">'
        +'<button onclick="toggleImpl(\''+opp+'-'+i+'\')" style="background:none;border:none;cursor:pointer;font-size:.71rem;font-weight:600;color:#0070AD;padding:.12rem 0;display:flex;align-items:center;gap:.28rem">'
        +'<span id="impl-arrow-'+opp+'-'+i+'" style="font-size:.65rem">\u25b6</span> View implementation method'
        +'</button>'
        +'<div id="impl-panel-'+opp+'-'+i+'" style="display:none;margin-top:.35rem;padding:.5rem .6rem;background:#F8FAFE;border:1px solid #DDE5EF;border-radius:.4rem">'
        +'<div style="display:flex;justify-content:flex-end;margin-bottom:.3rem"><span style="font-size:.62rem;font-weight:600;padding:.08rem .35rem;border-radius:99px;background:'+icBg+';color:'+icClr+'">Complexity: '+(impl.implementation_complexity||'medium')+'</span></div>'
        +(impl.delivery_pattern?'<div style="margin-bottom:.28rem"><div style="font-size:.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#4A6A84;margin-bottom:.1rem">Delivery pattern</div><div style="font-size:.73rem;color:#1E3450">'+impl.delivery_pattern+'</div></div>':'')
        +(impl.agentic_support?'<div style="margin-bottom:.28rem"><div style="font-size:.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#4A6A84;margin-bottom:.1rem">Agentic support</div><div style="font-size:.73rem;color:#1E3450">'+impl.agentic_support+'</div></div>':'')
        +(impl.measurement_infrastructure?'<div style="margin-bottom:.28rem"><div style="font-size:.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#4A6A84;margin-bottom:.1rem">Measurement infrastructure</div><div style="font-size:.73rem;color:#1E3450">'+impl.measurement_infrastructure+'</div></div>':'')
        +(impl.hitl_governance?'<div><div style="font-size:.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#4A6A84;margin-bottom:.1rem">Human governance</div><div style="font-size:.73rem;color:#1E3450">'+impl.hitl_governance+'</div></div>':'')
        +'</div></div>';
    }
    return '<div id="ksp-'+opp+'-'+i+'" style="display:'+(active?'block':'none')+'">'
      +(s.commercial_logic?'<div style="font-size:.73rem;color:#3A5470;font-style:italic;margin-bottom:.4rem;padding:.32rem .5rem;background:'+c.bg+';border-left:3px solid '+c.border+';border-radius:0 .3rem .3rem 0">'+s.commercial_logic+'</div>':'')
      +(s.target_outcome?'<div style="font-size:.72rem;color:#3A5470;margin-bottom:.35rem">\u25b6 '+s.target_outcome+'</div>':'')
      +'<div style="font-size:.64rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#4A6A84;margin-bottom:.25rem">Proposed KPIs</div>'
      +kpiRows
      +badges
      +upliftHtml
      +nextHtml
      +implHtml
      +'</div>';
  }).join('');
  return '<div style="display:flex;gap:.35rem;margin-bottom:.5rem">'+tabs+'</div>'+panels;
}
function toggleImpl(id){
  var p=document.getElementById('impl-panel-'+id);
  var a=document.getElementById('impl-arrow-'+id);
  if(!p) return;
  var open=p.style.display==='block';
  p.style.display=open?'none':'block';
  if(a) a.textContent=open?'\u25b6':'\u25bc';
}
function switchKpiScenario(opp,idx){
  var scenarios=(typeof DETAILS!=='undefined'&&DETAILS[opp])?(DETAILS[opp].kpi_scenarios||[]):[];
  var DFLT=['delivery-performance','commercial-outcome','quality-gated-hybrid'];
  var TYPE_CFG={'delivery-performance':{color:'#1A7A4A',bg:'#E8F7EE'},'commercial-outcome':{color:'#5B3FA6',bg:'#F3EFFF'},'quality-gated-hybrid':{color:'#B87A00',bg:'#FEF8EC'}};
  [0,1,2].forEach(function(i){
    var tab=document.getElementById('kst-'+opp+'-'+i);
    var panel=document.getElementById('ksp-'+opp+'-'+i);
    if(!tab||!panel) return;
    var active=i===idx;
    var t=(scenarios[i]&&scenarios[i].scenario_type)||DFLT[i];
    var c=TYPE_CFG[t]||TYPE_CFG['delivery-performance'];
    tab.style.borderColor=active?c.color:'#C8D8E8';
    tab.style.background =active?c.bg:'#F8FAFE';
    tab.style.color      =active?c.color:'#607A94';
    panel.style.display  =active?'block':'none';
  });
}
function buildBestScenarioHtml(scenarios){
  if(!scenarios||!scenarios.length) return '';
  var best=scenarios.find(function(s){return s.scenario_type==='quality-gated-hybrid';});
  if(!best) best=scenarios.reduce(function(a,b){
    var aU=a.uplift_range?((+a.uplift_range.min+(+a.uplift_range.max))/2):(+a.estimated_revenue_uplift_pct||0);
    var bU=b.uplift_range?((+b.uplift_range.min+(+b.uplift_range.max))/2):(+b.estimated_revenue_uplift_pct||0);
    return aU>=bU?a:b;
  });
  var kpis=(best.proposed_kpis||[]).map(function(k){
    if(typeof k==='string') return '<li>'+k+'</li>';
    var meta=k.attribution_strength?' <em style="color:#7A96B4;font-size:.8rem">\u00b7 attribution: '+k.attribution_strength+'</em>':'';
    return '<li>'+k.kpi+meta+(k.measurement_source?' <em style="color:#7A96B4;font-size:.8rem">\u00b7 source: '+k.measurement_source+'</em>':'')+'</li>';
  }).join('');
  var upliftTxt=(best.uplift_range&&typeof best.uplift_range==='object')
    ?best.uplift_range.min+'\u2013'+best.uplift_range.max+'% of deal size ('+(best.uplift_range.confidence||'medium')+' confidence)'
    :(best.estimated_revenue_uplift_pct!=null?'+'+(+best.estimated_revenue_uplift_pct).toFixed(1)+'% (indicative)':'');
  return '<div class="modal-section"><div class="modal-section-title">\u26a1\u2009Recommended commercial scenario for the client conversation</div><div class="modal-body">'
    +'<p style="margin-bottom:.35rem"><strong>'+(best.scenario_name||'')+'</strong>'+(best.contract_mechanism?' <span style="font-size:.76rem;font-weight:600;padding:.09rem .38rem;border-radius:99px;background:#F0F4FA;color:#4A6A84">\u00b7 '+best.contract_mechanism+'</span>':'')+'</p>'
    +(best.commercial_logic?'<p style="font-style:italic;color:#5A7A94;margin-bottom:.45rem;font-size:.82rem">'+best.commercial_logic+'</p>':'')
    +(best.target_outcome?'<p style="margin-bottom:.4rem"><strong>Target:</strong> '+best.target_outcome+'</p>':'')
    +'<ul style="margin-bottom:.5rem">'+kpis+'</ul>'
    +(best.next_action?'<p style="margin:.4rem 0;padding:.38rem .55rem;background:#F0F4FA;border-left:3px solid #0070AD;border-radius:0 .3rem .3rem 0;font-size:.82rem"><strong>Next step:</strong> '+best.next_action+'</p>':'')
    +(upliftTxt?'<p style="margin-top:.35rem;font-weight:700;color:#1E9160">Indicative uplift range: '+upliftTxt+'</p>':'')
    +'</div></div>';
}
// ─── Activation modal ────────────────────────────────────────────────────────
function buildValuePoolHtml(pools, ranking, gaps, bare){
  if(!pools || !pools.length) return '';
  function capgeminiValuePoolName(pool){
    const names = {
      VP1: 'Accumulated Debt: Enterprise Technology Modernization',
      VP2: 'New Agentic Technology Stack',
      VP3: 'New Agentic Control Plane',
      VP4: 'New Agentic Products & Services',
      VP5: 'New Agentic Enterprise Processes'
    };
    return names[pool.pool_id] || pool.pool_name || '';
  }
  var rankMap = {};
  (ranking||[]).forEach(function(r){ rankMap[r.pool_id] = r; });
  var sorted = pools.slice().sort(function(a,b){
    var ra = rankMap[a.pool_id] ? rankMap[a.pool_id].rank : 99;
    var rb = rankMap[b.pool_id] ? rankMap[b.pool_id].rank : 99;
    return ra - rb;
  });
  function bar(val){
    val = Math.max(0, Math.min(5, +val||0));
    return '<span style="letter-spacing:1px;color:#0070AD">'+'\u25a0'.repeat(val)+'</span><span style="letter-spacing:1px;color:#D0DCE8">'+'\u25a1'.repeat(5-val)+'</span>';
  }
  function confColor(c){
    return {'high':'#1A7A4A','medium':'#B87A00','low':'#9B1C1C'}[(c||'medium').toLowerCase()] || '#607A94';
  }
  var rows = sorted.map(function(p){
    var rk = rankMap[p.pool_id];
    var poolName = capgeminiValuePoolName(p);
    var evid = (p.evidence||[]).slice(0,2).map(function(e){return '<div style="font-size:.71rem;color:#5A7A94;margin-top:.12rem">\u201c'+e+'\u201d</div>';}).join('');
    return '<div style="padding:.5rem .6rem;margin-bottom:.4rem;background:#F8FAFE;border:1px solid #E0E8F0;border-radius:.4rem">'
      +'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:.5rem;flex-wrap:wrap">'
      +'<span style="font-weight:700;font-size:.8rem;color:#1E3450">'+(rk?('#'+rk.rank+'\u2009\u00b7\u2009'):'')+(p.pool_id||'')+' \u2014 '+poolName+'</span>'
      +'<span style="font-size:.63rem;font-weight:600;padding:.08rem .35rem;border-radius:99px;background:#F0F4FA;color:'+confColor(p.confidence)+'">'+(p.confidence||'\u2014')+' confidence</span>'
      +'</div>'
      +'<div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:.3rem;font-size:.72rem;color:#4A6A84">'
      +'<span>Relevance '+bar(p.relevance)+'</span>'
      +'<span>Opportunity '+bar(p.opportunity_size)+'</span>'
      +'<span style="text-transform:capitalize">Evidence: '+(p.evidence_strength||'\u2014')+'</span>'
      +'</div>'
      +(p.verdict?'<div style="font-size:.76rem;color:#1E3450;margin-top:.3rem">'+p.verdict+'</div>':'')
      +(p.opportunity?'<div style="font-size:.74rem;color:#1A6B3C;margin-top:.2rem"><strong>Opportunity:</strong> '+p.opportunity+'</div>':'')
      +evid
      +(rk&&rk.rationale?'<div style="font-size:.71rem;color:#5A7A94;margin-top:.25rem;font-style:italic">'+rk.rationale+'</div>':'')
      +'</div>';
  }).join('');
  var gapsHtml = (gaps&&gaps.length) ? '<div style="margin-top:.5rem"><div style="font-size:.63rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#4A6A84;margin-bottom:.2rem">Evidence gaps</div><ul style="margin:0;padding-left:1.1rem">'+gaps.map(function(g){return '<li style="font-size:.74rem;color:#5A7A94">'+g+'</li>';}).join('')+'</ul></div>' : '';
  var inner = rows+gapsHtml;
  if(bare) return inner;
  return '<div class="modal-section"><div class="modal-section-title">\ud83c\udfaf\u2009AI value pool assessment</div><div class="modal-body">'
    +'<p style="font-size:.78rem;color:#5A7A94;margin-bottom:.5rem">Which of Capgemini\u2019s five AI value pools this engagement touches, ranked by opportunity.</p>'
    +inner+'</div></div>';
}
function openModal(opp) {
  const d = DETAILS[opp]; if (!d) return;
  const mgr = d.manager || {};
  const cfg = REC_CFG[d.recommendation] || {};
  // Pick up any steering instructions from a prior Report Agent re-run
  let reportInstr = (d.report_instructions || '').trim();
  if (!reportInstr) {
    try { reportInstr = (sessionStorage.getItem('reportInstr:' + opp) || '').trim(); } catch(_) {}
  }
  const reportInstrSection = reportInstr ? `
    <div class="modal-section">
      <div class="modal-section-title">Reviewer steering &mdash; applied to this report</div>
      <div class="modal-body">
        <p style="padding:.55rem .7rem;background:#FFF7E0;border-left:3px solid #E8970A;border-radius:4px;color:#6A4A00">${reportInstr}</p>
      </div>
    </div>` : '';
  document.getElementById('modal-title').textContent = `Instruction Package \u00b7 ${mgr.name||'Engagement Manager'}`;
  document.getElementById('modal-subtitle').textContent = `${d.engagement_name} \u00b7 ${d.opportunity_id}`;
  const kpiList = (d.missing_kpis && d.missing_kpis.length)
    ? '<ul>'+d.missing_kpis.map(k=>`<li>${k}</li>`).join('')+'</ul>'
    : '<p>No KPI gaps identified — the SoW has sufficient measurement detail.</p>';
  const outList = (d.detected_outcomes && d.detected_outcomes.length)
    ? '<ul>'+d.detected_outcomes.map(o=>`<li>${o}</li>`).join('')+'</ul>'
    : '<p>No specific outcomes were detected.</p>';
  const agenticItems = (d.agentic_opportunities || []);
  const agenticList = agenticItems.length
    ? '<ul>'+agenticItems.map(a=>{
        if (typeof a === 'string') return `<li>${a}</li>`;
        const task = a.task || '—';
        const meta = [];
        if (a.agent_pattern) meta.push(`pattern: <strong>${a.agent_pattern}</strong>`);
        if (a.feasibility) meta.push(`feasibility: <strong>${a.feasibility}</strong>`);
        if (a.estimated_hours_saved_per_month != null) meta.push(`~<strong>${(+a.estimated_hours_saved_per_month).toFixed(1)} h/mo</strong>`);
        if (a.current_owner) meta.push(`owner: ${a.current_owner}`);
        const metaLine = meta.length ? `<div style="font-size:.78rem;color:#5A7A94;margin-top:.15rem">${meta.join(' · ')}</div>` : '';
        const rat = a.rationale ? `<div style="font-size:.78rem;color:#3A5A78;margin-top:.15rem">${a.rationale}</div>` : '';
        return `<li><strong>${task}</strong>${metaLine}${rat}</li>`;
      }).join('')+'</ul>'
    : '<p>No agentic delivery opportunities were identified for this engagement.</p>';
  const bestScenarioSection = buildBestScenarioHtml(d.kpi_scenarios);
  const valuePoolSection = buildValuePoolHtml(d.value_pool_assessment, d.value_pool_ranking, d.value_pool_evidence_gaps);
  const isActionable = d.recommendation==='reconsider'||d.recommendation==='recommend';
  // ─── Potential value section (for both parties) ──────────────────────────
  const deal = Number(d.deal_size) || 0;
  const uplift = Number(d.revenue_gain) || 0;
  const upliftPct = deal > 0 ? (uplift / deal) * 100 : 0;
  // Indicative client value: industry benchmark — in well-structured outcome-based
  // engagements the client captures roughly 5–8× the consulting-side uplift as
  // realised business value (top-line, cost-avoidance, retention, productivity).
  const clientLow  = uplift * 5;
  const clientHigh = uplift * 8;
  const valueSection = (deal > 0 || uplift > 0) ? `
    <div class="modal-section">
      <div class="modal-section-title">Potential value &mdash; Contoso &amp; ${d.engagement_name.split('—').pop().trim() || 'the client'}</div>
      <div class="modal-body">
        <p style="margin-bottom:.6rem">Moving this engagement from T&amp;M to an outcome-based structure creates measurable upside for both parties:</p>
        <table style="width:100%;border-collapse:collapse;font-size:.82rem;margin-bottom:.7rem">
          <thead>
            <tr style="background:#F1F5FA">
              <th style="text-align:left;padding:.45rem .6rem;border:1px solid #D7E2EE;font-weight:700;color:#0E1E38">Dimension</th>
              <th style="text-align:left;padding:.45rem .6rem;border:1px solid #D7E2EE;font-weight:700;color:#0E1E38">Contoso upside</th>
              <th style="text-align:left;padding:.45rem .6rem;border:1px solid #D7E2EE;font-weight:700;color:#0E1E38">Client upside</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#0E1E38">Baseline contract value</td>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#0E1E38">${fmtEur(deal)}</td>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#0E1E38">Same scope, budgeted spend</td>
            </tr>
            <tr>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#0E1E38">Uplift from outcome model</td>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#1E9160;font-weight:600">${uplift > 0 ? fmtEur(uplift) + ` (+${upliftPct.toFixed(1)}%)` : '—'}</td>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#1E9160;font-weight:600">${uplift > 0 ? `${fmtEur(clientLow)} – ${fmtEur(clientHigh)}` : '—'}</td>
            </tr>
            <tr>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#0E1E38">Mechanism</td>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#3A5A78">Performance bonus on top of fixed build fee; margin on outcome achievement</td>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#3A5A78">Revenue lift, cost avoidance, retention, productivity gains driven by the outcomes delivered</td>
            </tr>
            <tr>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#0E1E38">Risk / downside</td>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#B95A00">Portion of fee at-risk if targets are missed</td>
              <td style="padding:.45rem .6rem;border:1px solid #D7E2EE;color:#B95A00">None — pays only when measurable value is delivered</td>
            </tr>
          </tbody>
        </table>
        <div style="font-size:.72rem;color:#5A7A94;font-style:italic">Client upside is an indicative range based on an industry benchmark of 5–8× multiplier on consulting-side uplift for well-structured outcome engagements. Final numbers to be validated with the client during KPI baselining (see to-do list below).</div>
      </div>
    </div>` : '';
  document.getElementById('modal-body').innerHTML = `
    ${reportInstrSection}
    <div class="modal-section">
      <div class="modal-section-title">Agent Value Attribution &mdash; assessment summary</div>
      <div class="modal-body">
        <p>The Outcome Readiness Review Agent assessed <strong>${d.engagement_name}</strong> and returned an assessment of <strong>${cfg.icon||''} ${cfg.label||d.recommendation}</strong>.</p>
        <p>${d.summary||'The agent completed its analysis of the SoW.'}</p>
      </div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">Detected outcomes</div>
      <div class="modal-body">${outList}</div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">KPI and measurement gaps</div>
      <div class="modal-body">${kpiList}</div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">Recommended commercial direction</div>
      <div class="modal-body"><p>${d.commercial_direction}</p></div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">Agentic delivery opportunities</div>
      <div class="modal-body">
        <p style="font-size:.82rem;color:#5A7A94;margin-bottom:.5rem">Tasks inside delivery where AI agents could automate or augment work. Independent of the commercial-model decision &mdash; these can be pursued in parallel.</p>
        ${agenticList}
      </div>
    </div>
    ${bestScenarioSection}
    ${valuePoolSection}
    ${valueSection}
    <div class="modal-section">
      <div class="modal-section-title">What ${mgr.name||'you'} needs to do next</div>
      <div class="modal-body">
        ${isActionable ? `<ul>
          <li>Run an <a href="https://blue-desert-08c52270f.6.azurestaticapps.net/deal" target="_blank" rel="noopener"><strong>OutcomeIQ</strong></a> maturity assessment to verify every element required for an outcome-based model is in place</li>
          <li>Contact the client to request missing KPI baselines</li>
          <li>Propose a measurement methodology and agree a control group design</li>
          <li>Engage Contoso's commercial team to model the outcome-linked fee structure</li>
          <li>Update the SoW to reflect agreed KPIs, baselines, targets, and payment triggers</li>
          <li>Return the updated SoW for a re-scan before contract execution</li>
          ${agenticItems.length ? '<li>Review the <strong>agentic delivery opportunities</strong> above with your delivery lead &mdash; these are independent of the commercial-model decision and can be pursued in parallel</li>' : ''}
        </ul>` : `<ul>
          <li>Run an <a href="https://blue-desert-08c52270f.6.azurestaticapps.net/deal" target="_blank" rel="noopener"><strong>OutcomeIQ</strong></a> maturity assessment to confirm which outcome-based readiness elements are missing</li>
          <li>Log the rationale for ruling out outcome-based pricing</li>
          <li>Schedule a re-scoping conversation if the client relationship allows</li>
          <li>Flag for re-review at the next contract renewal or scope change</li>
          ${agenticItems.length ? '<li>Even without an outcome-based commercial model, review the <strong>agentic delivery opportunities</strong> above with your delivery lead to capture margin gains</li>' : ''}
        </ul>`}
      </div>
    </div>`;
  const sendBtn = document.querySelector('#modal .btn-send');
  if (sendBtn) sendBtn.innerHTML = `\u2709&ensp;Send to EM: ${mgr.name||'Engagement Manager'}`;
  document.getElementById('modal-overlay').classList.add('open');
}
function closeModal(e) {
  if (!e || e.target===document.getElementById('modal-overlay'))
    document.getElementById('modal-overlay').classList.remove('open');
}
function simulateSend() {
  document.getElementById('modal-overlay').classList.remove('open');
  const d = DETAILS[activeOpp]||{}; const mgr = d.manager||{};
  showToast('✓ Instructions sent to ' + (mgr.name||'Engagement Manager'));
}
function rerunAgent(opp, stage) {
  const ta  = document.getElementById('rerun-instr-' + opp);
  const btn = document.getElementById('rerun-btn-' + opp);
  const st  = document.getElementById('rerun-status-' + opp);
  const instr = (ta && ta.value || '').trim();
  if (!instr) { if (st) st.textContent = 'Please add at least one instruction before re-running.'; return; }
  const doingLabel = btn ? btn.getAttribute('data-doing') : 'Re-running\u2026';
  const baseLabel  = btn ? btn.getAttribute('data-label') : 'Re-run';
  if (btn) { btn.disabled = true; btn.innerHTML = '&#8635;&ensp;' + baseLabel + '\u2026'; }
  if (st)  { st.textContent = doingLabel; st.style.color = '#5A7A94'; }

  if (stage === 'generate_report') {
    // Report Agent path: persist instructions for this engagement and regenerate
    // the report view without touching the underlying extraction. A full server-
    // side Report Agent would be wired here — for the demo we fold the steering
    // instructions into the client-rendered report modal.
    try { sessionStorage.setItem('reportInstr:' + opp, instr); } catch(_) {}
    if (DETAILS[opp]) DETAILS[opp].report_instructions = instr;
    setTimeout(() => {
      if (st) { st.textContent = '\u2713 Report regenerated with your steering instructions. Opening updated report\u2026'; st.style.color = '#1E9160'; }
      if (btn) { btn.disabled = false; btn.innerHTML = '&#8635;&ensp;' + baseLabel; }
      openModal(opp);
    }, 650);
    return;
  }

  // Extraction Agent path: real server call
  fetch('/scan', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ opportunity_id: opp, extra_instructions: instr })
  }).then(async r => {
    const txt = await r.text();
    if (!r.ok) throw new Error(txt || ('HTTP ' + r.status));
    if (st) { st.textContent = '\u2713 Re-run complete. Refreshing\u2026'; st.style.color = '#1E9160'; }
    setTimeout(() => location.reload(), 1100);
  }).catch(err => {
    if (st) { st.textContent = '\u2715 Re-run failed: ' + String(err).slice(0, 200); st.style.color = '#B33030'; }
    if (btn) { btn.disabled = false; btn.innerHTML = '&#8635;&ensp;' + baseLabel; }
  });
}
function copyReport() {
  const body = document.getElementById('modal-body');
  const title = document.getElementById('modal-title');
  const subtitle = document.getElementById('modal-subtitle');
  if (!body) return;
  const titleTxt = title ? title.textContent : '';
  const subTxt   = subtitle ? subtitle.textContent : '';
  // Rich HTML — inline the most important styles so they survive paste into Outlook/Word/Docs
  const html = `<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#0E1E38;line-height:1.55;max-width:780px">
  ${titleTxt ? `<h2 style="margin:0 0 4px;font-size:18px;color:#0E1E38">${titleTxt}</h2>` : ''}
  ${subTxt ? `<div style="margin:0 0 16px;font-size:12px;color:#5A7A94">${subTxt}</div>` : ''}
  ${body.innerHTML}
</div>`;
  // Plain-text fallback (keeps bullet dashes + blank lines between sections)
  const text = (titleTxt ? titleTxt + '\n' : '') + (subTxt ? subTxt + '\n\n' : '\n') +
               body.innerText.replace(/\n{3,}/g, '\n\n').trim();
  const btn = document.getElementById('copy-report-btn');
  const done = (ok) => {
    if (!btn) return;
    const original = btn.innerHTML;
    btn.innerHTML = ok ? '\u2713&ensp;Copied' : '\u2715&ensp;Copy failed';
    setTimeout(() => { btn.innerHTML = original; }, 1600);
  };
  // Prefer the async Clipboard API with ClipboardItem — allows both HTML and plain text
  const writeRich = () => {
    if (!(navigator.clipboard && window.ClipboardItem)) return Promise.reject();
    const item = new ClipboardItem({
      'text/html':  new Blob([html], { type: 'text/html' }),
      'text/plain': new Blob([text], { type: 'text/plain' }),
    });
    return navigator.clipboard.write([item]);
  };
  writeRich()
    .then(() => done(true))
    .catch(() => {
      // Fallback 1: execCommand copy on a live, selected element preserves HTML on most browsers
      try {
        const container = document.createElement('div');
        container.setAttribute('contenteditable', 'true');
        container.style.position = 'fixed';
        container.style.left = '-9999px';
        container.style.top = '0';
        container.innerHTML = html;
        document.body.appendChild(container);
        const range = document.createRange(); range.selectNodeContents(container);
        const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
        const ok = document.execCommand('copy');
        sel.removeAllRanges();
        document.body.removeChild(container);
        if (ok) { done(true); return; }
      } catch (_) {}
      // Fallback 2: plain text only
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => done(true)).catch(() => done(false));
      } else {
        done(false);
      }
    });
}

// ─── Economic Impact Model ────────────────────────────────────────────────────
const TOTAL_HOURS_RAW = %%TOTAL_HOURS_RAW%%;

const SCENARIOS = {
  //  rate  build  opex  util  annualHours (projected full-year throughput at scale)
  conservative: { rate:90,  build:80,  opex:4,  util:55, hours:500  },
  expected:     { rate:110, build:60,  opex:3,  util:70, hours:800  },
  upside:       { rate:135, build:40,  opex:2,  util:85, hours:1200 },
};

function applyScenario(name) {
  const s = SCENARIOS[name];
  if (!s) return;
  document.getElementById('ra-rate').value  = s.rate;
  document.getElementById('ra-build').value = s.build;
  document.getElementById('ra-opex').value  = s.opex;
  document.getElementById('ra-util').value  = s.util;
  document.getElementById('ra-hours').value = s.hours;
  // Update label spans
  document.getElementById('ra-rate-val').textContent  = '\u20ac' + s.rate;
  document.getElementById('ra-build-val').textContent = '\u20ac' + s.build + 'k';
  document.getElementById('ra-opex-val').textContent  = '\u20ac' + s.opex + 'k';
  document.getElementById('ra-util-val').textContent  = s.util + '%';
  document.getElementById('ra-hours-val').textContent = s.hours + ' h';
  document.querySelectorAll('#fin-efficiency-section .fin-tab, #roi-assumptions .fin-tab').forEach(b => b.classList.remove('active'));
  const effBtn = document.getElementById('fin-'+name);
  if (effBtn) effBtn.classList.add('active');
  try{ localStorage.setItem('cockpit.scenario.efficiency', name); }catch(_){ }
  updateRoi();
}

function roiFmt(n, prefix='\u20ac') {
  if (Math.abs(n) >= 1000000) return prefix + (n/1000000).toFixed(1)+'M';
  if (Math.abs(n) >= 1000)    return prefix + (n/1000).toFixed(1)+'k';
  return prefix + Math.round(n).toLocaleString();
}
function fmtEur(v) {
  if (!v) return '\u20ac0';
  if (v >= 1000000) return '\u20ac' + (v/1000000).toFixed(1) + 'M';
  if (v >= 1000)    return '\u20ac' + Math.round(v/1000).toLocaleString() + 'k';
  return '\u20ac' + Math.round(v).toLocaleString();
}
function fmtEur(v) {
  if (!v) return '\u20ac0';
  if (v >= 1000000) return '\u20ac' + (v/1000000).toFixed(1) + 'M';
  if (v >= 1000)    return '\u20ac' + Math.round(v/1000).toLocaleString() + 'k';
  return '\u20ac' + Math.round(v).toLocaleString();
}

function updateRoi() {
  const rate  = +document.getElementById('ra-rate').value;
  const build = +document.getElementById('ra-build').value * 1000;
  const opex  = +document.getElementById('ra-opex').value  * 1000;
  const util  = +document.getElementById('ra-util').value  / 100;
  const annualHours = +document.getElementById('ra-hours').value;

  document.getElementById('ra-rate-val').textContent  = '\u20ac' + rate;
  document.getElementById('ra-build-val').textContent = '\u20ac' + (build/1000).toFixed(0) + 'k';
  document.getElementById('ra-opex-val').textContent  = '\u20ac' + (opex/1000).toFixed(0) + 'k';
  document.getElementById('ra-util-val').textContent  = Math.round(util*100) + '%';
  document.getElementById('ra-hours-val').textContent = annualHours + ' h';

  // Use projected annual hours (scenario throughput) for the economic model;
  // actual DB hours_saved is shown as context in the KPI tile above.
  const grossHourValue = annualHours * rate * util;
  const annualOpex     = opex * 12;
  const totalCost12m   = build + annualOpex;
  const netValue12m    = grossHourValue - totalCost12m;
  const roi            = totalCost12m > 0 ? (netValue12m / totalCost12m) * 100 : 0;
  const paybackMonths  = (grossHourValue / 12) > 0
    ? Math.ceil((build + opex) / (grossHourValue / 12))
    : null;

  const roiColor = roi >= 100 ? '#1E9160' : (roi >= 0 ? '#E8970A' : '#D94040');
  const netColor = netValue12m >= 0 ? '#1E9160' : '#D94040';

  const metrics = [
    { label:'Attributed Value (gross)',  value: roiFmt(grossHourValue),
      sub: annualHours+' h/yr \u00d7 \u20ac'+rate+' \u00d7 '+Math.round(util*100)+'% util',
      accent:'#0070AD' },
    { label:'One-time build cost',       value: roiFmt(build),
      sub: 'Initial investment', accent:'#8BAABF' },
    { label:'Annual operating cost',     value: roiFmt(annualOpex),
      sub: '\u20ac'+(opex/1000).toFixed(0)+'k\u2009/\u2009month \u00d7 12', accent:'#8BAABF' },
    { label:'Net value (12 months)',     value: roiFmt(netValue12m),
      sub: 'Gross value minus total cost', accent: netColor },
    { label:'Indicative ROI',            value: roi.toFixed(0)+'%',
      sub: 'Net \u00f7 total 12m investment', accent: roiColor },
    { label:'Est. payback period',
      value: paybackMonths ? (paybackMonths <= 24 ? paybackMonths+'\u2009mo' : '> 24\u2009mo') : '\u2014',
      sub: 'Months to recover build cost', accent:'#6B42A8' },
  ];

  // Populate Financial Outlook metrics
  const setEl = (id, val) => { const e = document.getElementById(id); if(e) e.textContent = val; };
  const setStyle = (id, prop, val) => { const e = document.getElementById(id); if(e) e.style[prop] = val; };
  const paybackTxt = paybackMonths ? (paybackMonths <= 24 ? paybackMonths+'\u2009mo' : '>\u200924\u2009mo') : '\u2014';
  setEl('fin-gross', roiFmt(grossHourValue));
  setEl('fin-gross-sub', annualHours+' h/yr \u00d7 \u20ac'+rate+' \u00d7 '+Math.round(util*100)+'% util');
  setEl('fin-build', roiFmt(build));
  setEl('fin-opex', roiFmt(annualOpex));
  setEl('fin-opex-sub', '\u20ac'+(opex/1000).toFixed(0)+'k/mo \u00d7 12');
  setEl('fin-net', roiFmt(netValue12m));
  setStyle('fin-net', 'color', netColor);
  setEl('fin-roi', roi.toFixed(0)+'%');
  setStyle('fin-roi', 'color', roiColor);
  setEl('fin-payback', paybackTxt);
  setStyle('fin-payback', 'color', '#6B42A8');
}

function closeDetail(e) {
  if (e && e.target !== document.getElementById('detail-overlay')) return;
  document.getElementById('detail-overlay').classList.remove('open');
  document.body.style.overflow = '';
  document.querySelectorAll('.eng-card').forEach(c=>c.classList.remove('selected'));
  activeOpp = null;
}

document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  // Close detail popup
  if (document.getElementById('detail-overlay').classList.contains('open')) {
    closeDetail(); return;
  }
  // Close HR overlay
  if (document.getElementById('hr-overlay').classList.contains('open')) {
    hrCancel(); return;
  }
  // Close HITL overlay
  if (document.getElementById('hitl-overlay').classList.contains('open')) {
    document.getElementById('hitl-cancel-btn').click(); return;
  }
});

// ─── Intake detail upload ─────────────────────────────────────────────────
let detailChosenFiles = [];
function onDetailFileChosen(input, opp) {
  const fileList = input && input.files ? Array.from(input.files) : [];
  detailChosenFiles = fileList.slice(0, 4);
  const lbl = document.getElementById('detail-drop-label');
  if (lbl) {
    if (detailChosenFiles.length === 1) lbl.textContent = '\uD83D\uDCC4\u2002' + detailChosenFiles[0].name;
    else if (detailChosenFiles.length > 1) lbl.textContent = '\uD83D\uDCC4\u2002' + detailChosenFiles.length + ' files selected';
    else lbl.innerHTML = '\uD83D\uDCC4\u2002Drop or click to browse PDF / DOCX / TXT';
  }
  renderSelectedFilesList('detail-selected-files-list', detailChosenFiles);
  const btn = document.getElementById('detail-upload-btn');
  if (btn) btn.disabled = !(detailChosenFiles && detailChosenFiles.length);
}
function handleDetailDrop(e, opp) {
  e.preventDefault();
  const zone = document.getElementById('detail-drop-zone');
  if (zone) zone.classList.remove('drag-over');
  const files = e.dataTransfer && e.dataTransfer.files ? e.dataTransfer.files : null;
  if (files && files.length) onDetailFileChosen({files: files}, opp);
}
function submitDetailUpload(opp) {
  const d = DETAILS[opp];
  if (!detailChosenFiles || !detailChosenFiles.length || !d) return;
  const btn = document.getElementById('detail-upload-btn');
  const st  = document.getElementById('detail-upload-status');
  if (btn) btn.disabled = true;
  if (st)  st.textContent = '\u23F3 Uploading and running AI review\u2026 (30\u201360\u2009s)';
  const fd = new FormData();
  detailChosenFiles.forEach(f => fd.append('file', f));
  fd.append('opportunity_id', d.opportunity_id);
  fd.append('engagement_name', d.engagement_name);
  fetch('/upload', {method:'POST', body:fd})
    .then(async r => {
      const txt = await r.text();
      if (!r.ok) {
        if (st) st.textContent = 'Error: ' + txt;
        if (btn) btn.disabled = false;
        return;
      }
      // /upload now returns intake preview — chain /apply-intake with extracted values
      let data = {}; try { data = JSON.parse(txt); } catch(_) {}
      if (st) st.textContent = '\u23F3 Running Outcomes Extraction scan\u2026';
      return fetch('/apply-intake', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          opportunity_id:     data.opportunity_id || d.opportunity_id,
          engagement_name:    data.engagement_title || d.engagement_name,
          engagement_manager: data.engagement_manager || '',
          deal_size:          data.deal_size || 0,
        })
      }).then(async r2 => {
        const txt2 = await r2.text();
        if (r2.ok) {
          let rec = ''; try { rec = JSON.parse(txt2).recommendation; } catch(_) {}
          if (st) st.textContent = '\u2713 Assessment: ' + (rec || 'see pipeline') + '. Refreshing\u2026';
          setTimeout(() => location.reload(), 1400);
        } else {
          if (st) st.textContent = 'Error: ' + txt2;
          if (btn) btn.disabled = false;
        }
      });
    })
    .catch(err => { if (st) st.textContent = 'Network error: ' + err; if (btn) btn.disabled = false; });
}

function openIntakeModal() {
  // Reset to step 1 each time the modal opens
  document.getElementById('intake-step-upload').style.display  = 'block';
  document.getElementById('intake-step-confirm').style.display = 'none';
  document.getElementById('intake-modal-title').textContent = 'Submit New Opportunity';
  document.getElementById('intake-modal-sub').textContent   = 'Upload a Statement of Work for AI review';
  const us = document.getElementById('upload-status'); if (us) { us.textContent = ''; us.className = 'intake-status'; }
  const cs = document.getElementById('confirm-status'); if (cs) { cs.textContent = ''; cs.className = 'intake-status'; }
  const oppEl = document.getElementById('opp-id'); if (oppEl) oppEl.value = '';
  const lbl = document.getElementById('drop-label');
  if (lbl) lbl.innerHTML = '&#128196;&ensp;Drop or click to browse &mdash; PDF, DOCX or TXT &nbsp;<span style="background:#EEF5FF;color:#0070AD;border:1px solid #C2D9F0;border-radius:.25rem;padding:.05rem .38rem;font-size:.72rem;font-weight:700">up to 4 files</span>';
  chosenFiles = []; pendingOppId = null;
  if (uploadBtn) { uploadBtn.disabled = true; uploadBtn.textContent = 'Intake the SoW →'; }
  const cbtn = document.getElementById('confirm-btn'); if (cbtn) cbtn.disabled = false;
  document.getElementById('intake-modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  setTimeout(()=>{ const el = document.getElementById('opp-id'); if (el) el.focus(); }, 100);
}
function closeIntakeModal(e) {
  if (e && e.target !== document.getElementById('intake-modal-overlay')) return;
  document.getElementById('intake-modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
}
function handleModalDrop(e) {
  e.preventDefault();
  const zone = document.getElementById('modal-drop-zone');
  zone.classList.remove('drag-over');
  const dt = e.dataTransfer;
  if (dt && dt.files && dt.files.length > 0) {
    onFileChosen({files: dt.files});
  }
}

// ─── Remove card ─────────────────────────────────────────────────────────────
function removeCard(e, opp) {
  e.stopPropagation();
  if (!confirm('Remove ' + opp + ' from the pipeline entirely? This cannot be undone.')) return;
  fetch('/remove', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({opportunity_id:opp})})
    .then(r => {
      if (r.ok) {
        const card = document.getElementById('card-' + opp);
        if (card) card.remove();
        if (activeOpp === opp) {
          document.getElementById('detail-overlay').classList.remove('open');
          document.body.style.overflow = '';
          activeOpp = null;
        }
        delete DETAILS[opp];
        showToast('\u2713 ' + opp + ' removed from pipeline');
      } else {
        showToast('\u26a0 Remove failed — please try again');
      }
    })
    .catch(() => showToast('\u26a0 Network error — remove failed'));
}

// ─── Toast ───────────────────────────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById('toast'); t.textContent = msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),3500);
}

// ─── Revenue data from server ────────────────────────────────────────────────
const TOTAL_REVENUE_RAW    = %%TOTAL_REVENUE_RAW%%;
const RECOMMEND_REVENUE_RAW = %%RECOMMEND_REVENUE_RAW%%;

// ─── Revenue scenarios ───────────────────────────────────────────────────────
const REVENUE_SCENARIOS = {
  conservative: { conv: 40, real: 50, ramp: 12, tenure: 2, renew: 55 },
  expected:     { conv: 60, real: 65, ramp:  9, tenure: 3, renew: 75 },
  upside:       { conv: 80, real: 85, ramp:  5, tenure: 4, renew: 90 },
};

function applyRevenueScenario(name) {
  const s = REVENUE_SCENARIOS[name];
  if (!s) return;
  document.getElementById('rr-conv').value   = s.conv;
  document.getElementById('rr-real').value   = s.real;
  document.getElementById('rr-ramp').value   = s.ramp;
  document.getElementById('rr-tenure').value = s.tenure;
  document.getElementById('rr-renew').value  = s.renew;
  document.getElementById('rr-conv-val').textContent   = s.conv + '%';
  document.getElementById('rr-real-val').textContent   = s.real + '%';
  document.getElementById('rr-ramp-val').textContent   = s.ramp + ' mo';
  document.getElementById('rr-tenure-val').textContent = s.tenure + ' yr';
  document.getElementById('rr-renew-val').textContent  = s.renew + '%';
  document.querySelectorAll('#fin-revenue-section .fin-tab').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('rev-' + name);
  if (btn) btn.classList.add('active');
  try{ localStorage.setItem('cockpit.scenario.revenue', name); }catch(_){ }
  updateRevenueRoi();
}

function updateRevenueRoi() {
  const conv   = +document.getElementById('rr-conv').value   / 100;
  const real   = +document.getElementById('rr-real').value   / 100;
  const ramp   = +document.getElementById('rr-ramp').value;
  const tenure = +document.getElementById('rr-tenure').value;
  const renew  = +document.getElementById('rr-renew').value  / 100;
  document.getElementById('rr-conv-val').textContent   = Math.round(conv*100) + '%';
  document.getElementById('rr-real-val').textContent   = Math.round(real*100) + '%';
  document.getElementById('rr-ramp-val').textContent   = ramp + ' mo';
  // Rescale rev-pill badges on all cards: real / 0.65 (expected baseline)
  const realFactor = real / 0.65;
  document.querySelectorAll('.rev-pill[data-base-pct]').forEach(el => {
    const base = parseFloat(el.dataset.basePct);
    const scaled = Math.round(base * realFactor);
    el.textContent = '\u2197\u200A' + scaled + '% revenue uplift';
  });
  document.getElementById('rr-tenure-val').textContent = tenure + ' yr';
  document.getElementById('rr-renew-val').textContent  = Math.round(renew*100) + '%';
  // Year-1: recommend pipeline × conv × real × ramp-adjusted fraction of year
  const rampFactor = 1 - (ramp / 24);
  const year1 = RECOMMEND_REVENUE_RAW * conv * real * rampFactor;
  // Steady-state: full pipeline × conv × real
  const steady = TOTAL_REVENUE_RAW * conv * real;
  // 3-year: Y1 + Y2 + Y3 with renewal decay
  const year2  = steady * renew;
  const year3  = steady * renew * renew;
  const rev3yr = year1 + year2 + year3;
  // At risk = recommend pool not yet converted
  const revRisk = RECOMMEND_REVENUE_RAW - (RECOMMEND_REVENUE_RAW * conv * real);
  // Avg per converted deal
  const nDeals = RECOMMEND_REVENUE_RAW > 0 ? Math.max(1, Math.round(RECOMMEND_REVENUE_RAW / 300000)) : 1;
  const perDeal = year1 > 0 ? (year1 / (nDeals * conv || 1)) : 0;
  const setEl = (id, v) => { const e = document.getElementById(id); if(e) e.textContent = v; };
  const setStyle = (id, prop, v) => { const e = document.getElementById(id); if(e) e.style[prop] = v; };
  setEl('rev-year1',     roiFmt(year1));
  setEl('rev-year1-sub', Math.round(conv*100)+'% conv \u00d7 '+Math.round(real*100)+'% realised, '+ramp+' mo ramp');
  setEl('rev-steady',    roiFmt(steady));
  setEl('rev-steady-sub', 'Full pipeline at '+Math.round(conv*100)+'% conversion');
  setEl('rev-3yr',       roiFmt(rev3yr));
  setEl('rev-risk',      roiFmt(Math.max(0, revRisk)));
  setStyle('rev-risk', 'color', revRisk > 0 ? '#E8970A' : '#1E9160');
  setEl('rev-conv',      Math.round(conv*100)+'%');
  setEl('rev-conv-sub',  Math.round(real*100)+'% of identified gain captured per deal');
  setEl('rev-deal',      roiFmt(perDeal));
  // Update top KPI tiles to reflect scenario
  const adjTotal     = TOTAL_REVENUE_RAW     * conv * real;
  const adjRecommend = RECOMMEND_REVENUE_RAW * conv * real;
  const nOpps = %%TOTAL_OPPS%%;
  const adjAvg = nOpps > 0 ? adjTotal / nOpps : 0;
  setEl('kpi-rev-total',     roiFmt(adjTotal));
  setEl('kpi-rev-total-sub', Math.round(conv*100)+'% conv \u00d7 '+Math.round(real*100)+'% realised \u2014 '+nOpps+' engagements');
  setEl('kpi-rev-recommend', roiFmt(adjRecommend));
  setEl('kpi-rev-avg',       roiFmt(adjAvg));
}

// ─── Init ────────────────────────────────────────────────────────────────────
function switchCockpit(tab) {
  document.getElementById('kpi-efficiency').style.display    = tab === 'efficiency' ? '' : 'none';
  document.getElementById('kpi-revenue').style.display       = tab === 'revenue'    ? '' : 'none';
  document.getElementById('fin-efficiency-section').style.display = tab === 'efficiency' ? '' : 'none';
  document.getElementById('roi-assumptions').style.display        = tab === 'efficiency' ? '' : 'none';
  document.getElementById('fin-revenue-section').style.display    = tab === 'revenue'    ? '' : 'none';
  document.getElementById('roi-revenue-assumptions').style.display = tab === 'revenue'   ? '' : 'none';
  document.querySelectorAll('.cockpit-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  try{ localStorage.setItem('cockpit.tab', tab); }catch(_){ }
}
window.addEventListener('load', () => {
  let savedTab = 'revenue';
  let savedEff = 'expected';
  let savedRev = 'expected';
  try {
    savedTab = localStorage.getItem('cockpit.tab') || 'revenue';
    savedEff = localStorage.getItem('cockpit.scenario.efficiency') || 'expected';
    savedRev = localStorage.getItem('cockpit.scenario.revenue') || 'expected';
  } catch(_){ }
  applyScenario(savedEff);
  applyRevenueScenario(savedRev);
  if (savedTab !== 'revenue') switchCockpit(savedTab);
});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", "runs.db")

def render_docs() -> str:
    """Standalone 'Docs & About' page: intro to outcome-based models, value
    attribution, how this solution applies the pattern, and author info."""
    return """<!DOCTYPE html>
<html lang=\"en\"><head><meta charset=\"utf-8\">
<title>Docs &amp; About &middot; Outcome Readiness Agent</title>
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<style>
  :root{--blue:#0070AD;--ink:#0C2340;--muted:#5A7A96;--line:#E5ECF3;--bg:#F7FAFD}
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:var(--ink);background:var(--bg);line-height:1.6}
  .wrap{max-width:860px;margin:0 auto;padding:2.5rem 1.5rem 4rem}
  .back{display:inline-block;margin-bottom:1.5rem;color:var(--blue);text-decoration:none;font-size:.85rem;font-weight:600}
  .back:hover{text-decoration:underline}
  h1{font-size:1.8rem;margin:.2rem 0 .4rem;letter-spacing:-.01em}
  h2{font-size:1.2rem;margin:2.2rem 0 .6rem;padding-bottom:.3rem;border-bottom:1px solid var(--line);color:var(--blue)}
  h3{font-size:.95rem;margin:1.4rem 0 .4rem;color:var(--ink)}
  p,li{font-size:.92rem;color:#28405A}
  .lede{font-size:1rem;color:var(--muted);margin:.2rem 0 1.8rem}
  .card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:1.1rem 1.3rem;margin:.9rem 0}
  .author{display:flex;gap:1rem;align-items:center;background:#fff;border:1px solid var(--line);border-radius:10px;padding:1.1rem 1.3rem;margin-top:1rem}
  .avatar{width:54px;height:54px;border-radius:50%;background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.25rem;flex-shrink:0}
  .author-meta{flex:1}
  .author-name{font-weight:700;font-size:1rem}
  .author-role{color:var(--muted);font-size:.85rem;margin-top:.1rem}
  .author-links{margin-top:.4rem;font-size:.85rem}
  .author-links a{color:var(--blue);text-decoration:none;margin-right:1rem;font-weight:600}
  .author-links a:hover{text-decoration:underline}
  table{width:100%;border-collapse:collapse;margin:.6rem 0;font-size:.88rem}
  th,td{text-align:left;padding:.5rem .7rem;border-bottom:1px solid var(--line);vertical-align:top}
  th{background:#EEF4FB;font-weight:600;color:var(--ink)}
  code{background:#EEF4FB;padding:.1rem .35rem;border-radius:4px;font-size:.85em;font-family:ui-monospace,Menlo,monospace}
  .pill{display:inline-block;background:#EEF4FB;color:var(--blue);padding:.1rem .55rem;border-radius:12px;font-size:.75rem;font-weight:600;margin-right:.3rem}
  .disclaimer{font-size:.78rem;color:var(--muted);margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line)}
</style></head><body>
<div class=\"wrap\">
  <a href=\"/\" class=\"back\">&larr; Back to dashboard</a>
  <h1>Docs &amp; About</h1>
  <p class=\"lede\">An introduction to outcome-based commercial models, value attribution, and how this solution applies both ideas &mdash; at the engagement level and to the agent itself.</p>

  <h2>1. Outcome-Based Commercial Models</h2>
  <p>Traditional IT services contracts price on <b>effort</b>: the client pays for time and materials consumed, regardless of business impact. The supplier is rewarded for showing up, not for delivering results.</p>
  <p><b>Outcome-based commercial models</b> flip this relationship. The supplier's fee is tied &mdash; wholly or partially &mdash; to measurable business results. If the result is achieved, the supplier earns more. If not, they earn less (or nothing).</p>
  <p>Illustrative outcome KPIs that make this model work:</p>
  <ul>
    <li>A double-digit percentage reduction in supply chain holding costs</li>
    <li>Claims processing time cut from multiple weeks to a few days</li>
    <li>Customer satisfaction score above a defined threshold</li>
    <li>A significant reduction in manual processing touchpoints</li>
  </ul>

  <h3>Why it's hard to scale</h3>
  <p>Outcome-based models only work when three conditions are met:</p>
  <table>
    <tr><th>Condition</th><th>What it means</th><th>What breaks it</th></tr>
    <tr><td><b>Defined outcomes</b></td><td>The SoW explicitly describes the business result</td><td>Vague deliverables like &ldquo;system go-live&rdquo;</td></tr>
    <tr><td><b>Measurable KPIs</b></td><td>Each outcome has a baseline, target, and agreed measurement method</td><td>No baseline data, no agreed source</td></tr>
    <tr><td><b>No structural blockers</b></td><td>Engagement structure allows outcome-linked payments</td><td>Regulatory constraints, pure T&amp;M scope, data-access issues</td></tr>
  </table>
  <p>Assessing these conditions requires reading the entire SoW carefully and applying commercial judgement &mdash; typically <b>4&ndash;8 hours per engagement</b>. Across hundreds of opportunities per year, this is a serious bottleneck and a risk that assessments are skipped or done inconsistently.</p>

  <h2>2. Value Attribution</h2>
  <p>&ldquo;Value attribution&rdquo; is the discipline of linking a specific intervention &mdash; an agent run, a consultant recommendation, an automation &mdash; to a measurable unit of business value. Without it, AI investments drift into anecdote.</p>
  <p>For this agent, the unit of value is <b>analyst hours saved per run</b>. Every response includes an <code>hours_saved</code> estimate (1.0&ndash;6.0&thinsp;h) reflecting how long a human analyst would have spent on that particular SoW. This field feeds:</p>
  <ul>
    <li><b>Local KPIs</b> &mdash; totals, averages, and portfolio coverage in the dashboard</li>
    <li><b>Foundry continuous evaluation</b> &mdash; a custom code evaluator normalises <code>hours_saved</code> against <code>MAX_HOURS_SAVED</code> to a 0&ndash;1 score, fired on every <code>RESPONSE_COMPLETED</code> event</li>
  </ul>
  <p>Because every run is logged and scored, the total value compounds automatically and is auditable in the same currency the business already understands: <i>analyst time</i>.</p>

  <h2>3. How This Solution Applies the Pattern</h2>
  <p>This repository demonstrates a <b>two-level agent pattern</b> where outcome-based logic is applied twice:</p>

  <div class=\"card\">
    <h3 style=\"margin-top:0\"><span class=\"pill\">Level 1</span> Business advisory &mdash; <i>what the agent assesses</i></h3>
    <p style=\"margin-bottom:0\">The agent reads a SoW and determines whether the <i>client engagement</i> can be structured as an outcome-based commercial model. It identifies measurable outcomes, flags missing KPIs, and returns a <code>recommend</code> / <code>reconsider</code> / <code>rule_out</code> verdict &mdash; replacing or augmenting the human analyst review.</p>
  </div>

  <div class=\"card\">
    <h3 style=\"margin-top:0\"><span class=\"pill\">Level 2</span> Agent accountability &mdash; <i>how the agent is measured</i></h3>
    <p style=\"margin-bottom:0\">The agent's own performance is tracked using the same outcome-based logic it applies to SoWs. It is not rewarded for tokens processed or response time (inputs); it earns credit only for the <code>hours_saved</code> it delivers per run (outcome). <b>The symmetry is intentional</b> &mdash; the agent is held to the same standard it recommends for client engagements.</p>
  </div>

  <p>The dashboard you just came from is the operational surface for both levels: a Kanban of engagements (Level 1) with portfolio KPIs and continuous evaluation signals (Level 2) layered on top.</p>

  <h2>4. About the Author</h2>
  <div class=\"author\">
    <div class=\"avatar\">DR</div>
    <div class=\"author-meta\">
      <div class=\"author-name\">Douwe van de Ruit</div>
      <div class=\"author-role\">Principal AI Solutions Architect &middot; Capgemini</div>
      <div class=\"author-links\">
        <a href=\"https://www.linkedin.com/in/dvanderuit/\" target=\"_blank\" rel=\"noopener\">LinkedIn</a>
        <a href=\"mailto:douwe.vande.ruit@capgemini.com\">douwe.vande.ruit@capgemini.com</a>
        <a href=\"https://github.com/doruit/outcome-readiness-agents\" target=\"_blank\" rel=\"noopener\">GitHub repo</a>
      </div>
    </div>
  </div>

  <p class=\"disclaimer\">&ldquo;Contoso&rdquo; is a fictional firm used purely for demonstration. This solution is a reference implementation built on the Microsoft Agent Framework and Microsoft Foundry; it is not a Capgemini product or official offering.</p>
</div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
        if self.path == "/docs":
            body = render_docs().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path != "/":
            self.send_response(404); self.end_headers(); return
        body = render(DB_PATH).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _respond(self, code, text):
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_respond(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/upload":       self._handle_upload();       return
        if self.path == "/apply-intake": self._handle_apply_intake(); return
        if self.path == "/intake-scan":  self._handle_intake_scan();  return
        if self.path == "/scan":         self._handle_scan();         return
        if self.path == "/advance":      self._handle_advance();      return
        if self.path == "/save-remarks":  self._handle_save_remarks(); return
        if self.path == "/remove":       self._handle_remove();       return
        if self.path == "/reset-demo":   self._handle_reset_demo();   return
        if self.path == "/batch-scan":   self._handle_batch_scan();   return
        self.send_response(404); self.end_headers()

    def _handle_upload(self):
      content_type = self.headers.get("Content-Type", "")
      content_length = int(self.headers.get("Content-Length", 0))
      raw_body = self.rfile.read(content_length)

      fields = {}
      files = []

      def _params(hv):
        m = email.message.Message()
        m["content-disposition"] = hv
        return {
          "name": m.get_param("name", header="content-disposition") or "",
          "filename": m.get_param("filename", header="content-disposition") or "",
        }

      _ct = email.message.Message()
      _ct["content-type"] = content_type
      boundary = _ct.get_param("boundary")
      if boundary:
        parts = raw_body.split(("--" + boundary).encode())[1:]
        for chunk in parts:
          if chunk.strip() in (b"", b"--", b"--\r\n", b"--\n"):
            continue
          sep = (
            b"\r\n\r\n"
            if b"\r\n\r\n" in chunk
            else (b"\n\n" if b"\n\n" in chunk else None)
          )
          if not sep:
            continue
          hdr_raw, body_chunk = chunk.split(sep, 1)
          body_chunk = body_chunk.rstrip(b"\r\n")
          ph = {}
          for line in hdr_raw.decode("utf-8", errors="replace").strip().splitlines():
            if ":" in line:
              k, _, v = line.partition(":")
              ph[k.strip().lower()] = v.strip()
          p = _params(ph.get("content-disposition", ""))
          if p["name"] and p["name"].startswith("file"):
            files.append((p["filename"] or "upload.txt", body_chunk))
          elif p["name"]:
            fields[p["name"]] = body_chunk.decode("utf-8", errors="replace")

      opp_id = fields.get("opportunity_id", "").strip()
      eng_name = fields.get("engagement_name", "").strip()
      if not opp_id:
        self._respond(400, "opportunity_id required")
        return
      if not eng_name:
        eng_name = "(pending intake)"
      if not files:
        self._respond(400, "No file received")
        return

      # Extract text from up to the first 4 uploaded files and concatenate them.
      texts = []
      for fn, data in files[:4]:
        try:
          txt = extract_text(fn, data)
        except Exception:
          txt = ''
        if txt and txt.strip():
          header = f"\n\n---- File: {fn} ----\n\n"
          texts.append(header + txt.strip())
      if not texts:
        self._respond(400, "Could not extract text from uploaded files")
        return
      sow_text = "\n\n".join(texts)

      # Build uploaded_documents metadata (limit to first 4 files)
      uploaded_documents = []
      for fn, data in files[:4]:
        try:
          uploaded_documents.append({"filename": fn, "size": len(data)})
        except Exception:
          uploaded_documents.append({"filename": fn})

      stub = {
        "run_id": str(_uuid.uuid4()),
        "opportunity_id": opp_id,
        "engagement_name": eng_name,
        "recommendation": None,
        "status": "draft",
      }

      # Record the intake run including uploaded_documents metadata
      log_run(
        stub,
        DB_PATH,
        pipeline_status="intake",
        sow_text=sow_text,
        uploaded_documents=uploaded_documents,
      )

      # Run Intake Agent to extract title/manager/deal_size so the user can confirm
      # or override before we run the expensive Outcomes Extraction scan.
      extracted_title = ""
      extracted_mgr = ""
      deal_size = 0
      try:
        intake_result = call_intake_agent(opp_id, sow_text)
        deal_size = intake_result.get("deal_size") or 0
        extracted_title = (intake_result.get("engagement_title") or "").strip()
        extracted_mgr = (intake_result.get("engagement_manager") or "").strip()
        con2 = sqlite3.connect(DB_PATH)
        ensure_columns(con2)
        mgr_obj = get_manager(opp_id)
        if extracted_mgr:
          mgr_obj["name"] = extracted_mgr
        con2.execute(
          """
          UPDATE runs
             SET engagement_name    = CASE WHEN ? != '' THEN ? ELSE engagement_name END,
               deal_size          = ?,
               intake_enriched    = 1,
               engagement_manager = ?
           WHERE opportunity_id = ?
        """,
          (extracted_title, extracted_title, deal_size, json.dumps(mgr_obj), opp_id),
        )
        con2.commit()
        con2.close()
      except Exception as e:
        # Intake agent offline — return empty values so the user can fill them in.
        self._json_respond(
          200,
          {
            "opportunity_id": opp_id,
            "engagement_title": "",
            "engagement_manager": "",
            "deal_size": 0,
            "intake_error": str(e),
          },
        )
        return

      # Return the intake values for user confirmation. The frontend will POST
      # back to /apply-intake with the (possibly overridden) values.
      self._json_respond(
        200,
        {
          "opportunity_id": opp_id,
          "engagement_title": extracted_title,
          "engagement_manager": extracted_mgr,
          "deal_size": deal_size,
        },
      )

    def _handle_apply_intake(self):
        """Save user-confirmed intake fields, then run the Outcomes Extraction scan."""
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        opp_id    = (payload.get("opportunity_id") or "").strip()
        eng_name  = (payload.get("engagement_name") or "").strip()
        mgr_name  = (payload.get("engagement_manager") or "").strip()
        try:    deal_size = float(payload.get("deal_size") or 0)
        except Exception: deal_size = 0
        if not opp_id: self._respond(400, "opportunity_id required"); return
        con = sqlite3.connect(DB_PATH)
        ensure_columns(con)
        row = con.execute(
            "SELECT sow_text FROM runs WHERE opportunity_id=? ORDER BY created_at DESC LIMIT 1",
            (opp_id,)).fetchone()
        if not row or not (row[0] or "").strip():
            con.close(); self._respond(400, "No SoW text stored"); return
        sow_text = row[0]
        mgr_obj = get_manager(opp_id)
        if mgr_name: mgr_obj["name"] = mgr_name
        con.execute("""
            UPDATE runs
               SET engagement_name    = CASE WHEN ? != '' THEN ? ELSE engagement_name END,
                   deal_size          = ?,
                   intake_enriched    = 1,
                   engagement_manager = ?
             WHERE opportunity_id = ?
        """, (eng_name, eng_name, deal_size, json.dumps(mgr_obj), opp_id))
        con.commit(); con.close()
        try:    result = call_agent_with_text(opp_id, eng_name, sow_text, deal_size=deal_size or None, mgr=mgr_obj)
        except Exception as e: self._respond(500, f"Agent failed: {e}"); return
        if not result.get("deal_size"):
            result["deal_size"] = deal_size or get_deal_size(opp_id)
        if not result.get("revenue_gain"):
            result["revenue_gain"] = get_revenue_gain(opp_id)
        try:    log_run(result, DB_PATH, pipeline_status="scanned", sow_text=sow_text)
        except Exception as e: self._respond(500, f"DB write failed: {e}"); return
        self._json_respond(200, result)

    def _handle_intake_scan(self):
        """Run the Intake Agent: extracts title, manager, deal_size from stored SoW."""
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        opp_id  = payload.get("opportunity_id", "").strip()
        if not opp_id:
            self._respond(400, "opportunity_id required"); return
        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT sow_text FROM runs WHERE opportunity_id=? ORDER BY created_at DESC LIMIT 1",
            (opp_id,)).fetchone()
        con.close()
        if not row or not (row[0] or "").strip():
            self._respond(400, "No SoW text stored"); return
        sow_text = row[0]
        try:
            result = call_intake_agent(opp_id, sow_text)
        except Exception as e:
            self._respond(500, f"Intake agent failed: {e}"); return
        new_title = (result.get("engagement_title") or "").strip()
        mgr_name  = (result.get("engagement_manager") or "").strip()
        deal_size = result.get("deal_size") or 0
        con = sqlite3.connect(DB_PATH)
        ensure_columns(con)
        existing_row = con.execute(
            "SELECT engagement_manager FROM runs WHERE opportunity_id=? ORDER BY created_at DESC LIMIT 1",
            (opp_id,)).fetchone()
        existing_mgr = {}
        if existing_row and existing_row[0]:
            try: existing_mgr = json.loads(existing_row[0])
            except: pass
        if mgr_name:
            existing_mgr["name"] = mgr_name
        con.execute("""
            UPDATE runs
               SET engagement_name    = CASE WHEN ? != '' THEN ? ELSE engagement_name END,
                   deal_size          = ?,
                   intake_enriched    = 1,
                   engagement_manager = ?
             WHERE opportunity_id = ?
        """, (new_title, new_title, deal_size, json.dumps(existing_mgr), opp_id))
        con.commit(); con.close()
        self._json_respond(200, {
            "engagement_title":   new_title,
            "engagement_manager": mgr_name,
            "deal_size":          deal_size,
        })

    def _handle_scan(self):
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        opp_id  = payload.get("opportunity_id", "").strip()
        extra_instructions = (payload.get("extra_instructions") or "").strip()
        if not opp_id: self._respond(400, "opportunity_id required"); return
        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT engagement_name, sow_text, deal_size FROM runs WHERE opportunity_id=? ORDER BY created_at DESC LIMIT 1",
            (opp_id,)).fetchone()
        con.close()
        if not row or not (row[1] or "").strip():
            self._respond(400, "No SoW text stored — upload via the form"); return
        eng_name, sow_text, deal_size = row[0], row[1], (row[2] or 0)
        mgr = get_manager(opp_id)
        try:    result = call_agent_with_text(opp_id, eng_name, sow_text, deal_size=deal_size or None, mgr=mgr, extra_instructions=extra_instructions or None)
        except Exception as e: self._respond(500, f"Agent failed: {e}"); return
        # Validate that the agent actually produced meaningful output
        summary_ok = bool((result.get("summary") or "").strip())
        rec_ok     = result.get("recommendation") in ("recommend", "reconsider")
        if not (summary_ok and rec_ok):
            self._respond(502, f"Agent returned incomplete result: summary_present={summary_ok} recommendation={result.get('recommendation')!r}"); return
        # Ensure deal_size and revenue_gain are set so the revenue uplift % badge is computed
        if not result.get("deal_size"):
            result["deal_size"] = deal_size or get_deal_size(opp_id)
        if not result.get("revenue_gain"):
            result["revenue_gain"] = get_revenue_gain(opp_id)
        # Preserve the card's current stage when re-running from columns 3 / 4
        con = sqlite3.connect(DB_PATH)
        cur_row = con.execute(
            "SELECT pipeline_status FROM runs WHERE opportunity_id=? ORDER BY created_at DESC LIMIT 1",
            (opp_id,)).fetchone()
        con.close()
        cur_stage = (cur_row[0] if cur_row else "scanned") or "scanned"
        target_stage = cur_stage if cur_stage in ("under_review", "generate_report", "archived") else "scanned"
        try:    log_run(result, DB_PATH, pipeline_status=target_stage, sow_text=sow_text)
        except Exception as e: self._respond(500, f"DB write failed: {e}"); return
        self._json_respond(200, result)

    def _handle_save_remarks(self):
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        opp_id  = payload.get("opportunity_id")
        remarks = payload.get("reviewer_remarks", "")
        rv_name = (payload.get("reviewer_name") or "").strip()
        rv_role = (payload.get("reviewer_role") or "").strip()
        if opp_id:
            con = sqlite3.connect(DB_PATH)
            ensure_columns(con)
            con.execute("UPDATE runs SET reviewer_remarks=?, reviewer_name=?, reviewer_role=?, human_approved=1 WHERE opportunity_id=?",
                        (remarks, rv_name, rv_role, opp_id))
            con.commit(); con.close()
            self.send_response(200); self.end_headers()
        else:
            self.send_response(400); self.end_headers()

    def _handle_advance(self):
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        opp_id  = payload.get("opportunity_id")
        stage   = payload.get("pipeline_status")
        if opp_id and stage in STAGE_KEYS:
            con = sqlite3.connect(DB_PATH)
            if stage == "intake":
                # Restart: clear all AI-generated analysis so the card is clean
                con.execute("""
                    UPDATE runs SET pipeline_status='intake',
                        recommendation=NULL, hours_saved=NULL, summary=NULL,
                        detected_outcomes=NULL, missing_kpis=NULL,
                        transformation_opportunities=NULL, agentic_opportunities=NULL, kpi_scenarios=NULL, value_attribution=NULL,
                        value_pool_assessment=NULL, value_pool_ranking=NULL, value_pool_evidence_gaps=NULL
                    WHERE opportunity_id=?
                """, (opp_id,))
            else:
                con.execute("UPDATE runs SET pipeline_status=? WHERE opportunity_id=?", (stage, opp_id))
            con.commit(); con.close()
            self.send_response(200); self.end_headers()
        else:
            self.send_response(400); self.end_headers()

    def _handle_remove(self):
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        # Accept empty-string opportunity_id too (orphan rows from failed uploads).
        if "opportunity_id" not in payload:
            self.send_response(400); self.end_headers(); return
        opp_id = payload.get("opportunity_id") or ""
        con = sqlite3.connect(DB_PATH)
        con.execute("DELETE FROM runs WHERE COALESCE(opportunity_id,'')=?", (opp_id,))
        con.commit(); con.close()
        self.send_response(200); self.end_headers()

    def _handle_reset_demo(self):
        """Delete all runs and re-seed the DB from sample_sows.json at intake stage."""
        sows = load_sows()
        con  = sqlite3.connect(DB_PATH)
        ensure_columns(con)
        con.execute("DELETE FROM runs")
        now = datetime.now(timezone.utc).isoformat()
        for sow in sows:
            opp_id   = sow.get("opportunity_id", "").strip()
            eng_name = sow.get("engagement_name", "")
            sow_text = sow.get("sow_text", "")
            deal_size = sow.get("deal_size") or get_deal_size(opp_id)
            mgr = get_manager(opp_id)
            con.execute("""
                INSERT INTO runs
                  (run_id, opportunity_id, engagement_name, pipeline_status,
                   sow_text, uploaded_documents, deal_size, engagement_manager, status, created_at,
                     recommendation, hours_saved, summary, detected_outcomes,
                     missing_kpis, transformation_opportunities, agentic_opportunities, kpi_scenarios, value_attribution,
                     value_pool_assessment, value_pool_ranking, value_pool_evidence_gaps,
                     revenue_gain, intake_enriched, reviewer_remarks, human_approved)
                VALUES (?,?,?,'intake',?,NULL,?,?,'draft',?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL,0)
              """, (_uuid.uuid4().hex, opp_id, eng_name, sow_text, deal_size,
                  json.dumps(mgr), now))
        con.commit(); con.close()
        self._json_respond(200, {"ok": True, "seeded": len(sows)})

    def _handle_batch_scan(self):
        """Run the extraction agent on every listed OPP ID that is missing outcomes."""
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        opp_ids = payload.get("opportunity_ids", [])
        ok_count = 0; failed_count = 0
        con = sqlite3.connect(DB_PATH)
        ensure_columns(con)
        for opp_id in opp_ids:
            row = con.execute(
                "SELECT engagement_name, sow_text, deal_size, pipeline_status FROM runs "
                "WHERE opportunity_id=? ORDER BY created_at DESC LIMIT 1",
                (opp_id,)).fetchone()
            if not row or not (row[1] or "").strip():
                failed_count += 1; continue
            eng_name, sow_text, deal_size, cur_stage = row[0], row[1], (row[2] or 0), row[3]
            try:
                mgr = get_manager(opp_id)
                result = call_agent_with_text(opp_id, eng_name, sow_text, deal_size=deal_size or None, mgr=mgr)
            except Exception:
                failed_count += 1; continue
            if not result.get("deal_size"):   result["deal_size"]   = deal_size or get_deal_size(opp_id)
            if not result.get("revenue_gain"): result["revenue_gain"] = get_revenue_gain(opp_id)
            # Keep the card in its current stage (don't regress it to 'scanned')
            log_run(result, DB_PATH, pipeline_status=cur_stage, sow_text=sow_text)
            ok_count += 1
        con.close()
        self._json_respond(200, {"ok": ok_count, "failed": failed_count})

    def log_message(self, fmt, *args): pass


def main():
    global DB_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",   default=os.getenv("DB_PATH", "runs.db"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5050")))
    parser.add_argument("--host", default=os.getenv("HOST", "localhost"))
    args    = parser.parse_args()
    DB_PATH = args.db
    server  = HTTPServer((args.host, args.port), Handler)
    print(f"Outcome Readiness Dashboard  →  http://{args.host}:{args.port}")
    print("Press Ctrl-C to stop.")
    try:    server.serve_forever()
    except KeyboardInterrupt: print("\nStopped.")

if __name__ == "__main__":
    main()
