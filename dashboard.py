"""
dashboard.py — Outcome Readiness Review · SoW Pipeline Dashboard
-----------------------------------------------------------------
Premium enterprise dashboard for Contoso Consulting's Outcome Readiness
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
import urllib.request
import uuid as _uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
CAP_BLUE   = "#0070AD"
CAP_NAVY   = "#12284C"
CAP_LIGHT  = "#F0F4F8"
CAP_BORDER = "#D1DCE8"

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
SCAN_AGENT_PORT          = int(os.getenv("SCAN_AGENT_PORT", "8088"))
REVIEW_AGENT_PORT        = int(os.getenv("REVIEW_AGENT_PORT", "8089"))
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
    try:
        wrapper = json.loads(raw)
        return json.loads(wrapper["output"][0]["content"][0]["text"])
    except (KeyError, IndexError, json.JSONDecodeError):
        return json.loads(raw)

def call_agent_with_text(opp_id, eng_name, sow_text):
    return _call_agent(SCAN_AGENT_PORT,
        f"opportunity_id: {opp_id}\nengagement_name: {eng_name}\n\n{sow_text}")

# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
STAGES = [
    ("intake",              "Intake",               "Awaiting agent scan"),
    ("scanned",             "Scanned",              "Verdict ready — pending review"),
    ("under_review",        "Under Review",         "Analyst reviewing verdict"),
    ("needs_clarification", "Needs Clarification",  "Re-scoping in progress"),
    ("validated",           "Validated",            "Confirmed — counts toward coverage"),
    ("rejected",            "Rejected",             "Not suitable — re-scope required"),
    ("archived",            "Archived",             "Engagement closed"),
]
STAGE_KEYS = [s[0] for s in STAGES]

ADVANCE_TO = {
    "intake":              "scanned",
    "scanned":             "under_review",
    "under_review":        "validated",
    "needs_clarification": "intake",
    "validated":           "archived",
    "rejected":            "archived",
}

STAGE_COLOR = {
    "intake":              "#8BAABF",
    "scanned":             CAP_BLUE,
    "under_review":        "#7B52AB",
    "needs_clarification": "#E8970A",
    "validated":           "#2D9E6B",
    "rejected":            "#D94040",
    "archived":            "#B0B0B0",
}

REC_CONFIG = {
    "recommend":  {"bg": "#E8F7EE", "color": "#1A6B3C", "border": "#A8D5B5", "icon": "✓", "label": "Recommend"},
    "reconsider": {"bg": "#FEF3E2", "color": "#92530C", "border": "#F6C87A", "icon": "◐", "label": "Reconsider"},
    "rule_out":   {"bg": "#FDECEA", "color": "#9B1C1C", "border": "#F5AAAA", "icon": "✕", "label": "Rule Out"},
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
        ("sow_text",                     "TEXT"),
        ("agent_name",                   "TEXT"),
        ("value_attribution",            "TEXT"),
        ("engagement_manager",           "TEXT"),
    ]:
        try:
            con.execute(f"ALTER TABLE runs ADD COLUMN {col} {defn}")
            con.commit()
        except Exception:
            pass

def log_run(result: dict, db_path: str, pipeline_status: str = "scanned", sow_text: str = "") -> None:
    opp_id = result.get("opportunity_id", "")
    mgr    = get_manager(opp_id)
    con    = sqlite3.connect(db_path)
    ensure_columns(con)
    con.execute("""
        INSERT OR REPLACE INTO runs
            (run_id, opportunity_id, engagement_name, recommendation,
             status, pipeline_status, hours_saved, created_at,
             summary, detected_outcomes, missing_kpis, transformation_opportunities,
             sow_text, agent_name, value_attribution, engagement_manager)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        result.get("run_id"), opp_id, result.get("engagement_name"),
        result.get("recommendation"), result.get("status", "draft"),
        pipeline_status, result.get("hours_saved"),
        datetime.now(timezone.utc).isoformat(),
        result.get("summary"),
        json.dumps(result.get("detected_outcomes") or []),
        json.dumps(result.get("missing_kpis") or []),
        json.dumps(result.get("transformation_opportunities") or []),
        sow_text or "", result.get("agent_name", ""),
        json.dumps(result.get("value_attribution") or {}),
        json.dumps(mgr),
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
        for col in ("detected_outcomes", "missing_kpis", "transformation_opportunities"):
            raw = row.get(col)
            if isinstance(raw, str):
                try:    row[col] = json.loads(raw)
                except: row[col] = []
            elif raw is None:
                row[col] = []
        for col in ("value_attribution", "engagement_manager"):
            raw = row.get(col)
            if isinstance(raw, str):
                try:    row[col] = json.loads(raw)
                except: row[col] = {}
            elif raw is None:
                row[col] = {}
        if not row.get("pipeline_status"):
            row["pipeline_status"] = "scanned"
        if not row.get("engagement_manager"):
            row["engagement_manager"] = get_manager(row.get("opportunity_id", ""))

    buckets = {s: [] for s in STAGE_KEYS}
    for row in latest:
        stage = row.get("pipeline_status", "scanned")
        if stage not in buckets: stage = "scanned"
        buckets[stage].append(row)

    total_runs    = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0] or 0
    total_hours   = round(sum(r.get("hours_saved") or 0 for r in latest), 1)
    avg_hours     = round(total_hours / len(latest), 1) if latest else 0
    total_opps    = len(latest)
    validated_cnt = len(buckets.get("validated", []))
    coverage_pct  = round(validated_cnt / total_opps * 100) if total_opps else 0
    outcome_ready = len([r for r in latest if r.get("recommendation") == "recommend"])

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

    advance_label = {
        "scanned":             "Start Review",
        "under_review":        "Validate",
        "needs_clarification": "Return for Re-scope",
        "validated":           "Archive",
        "rejected":            "Archive",
    }.get(stage, "")

    advance_btn = ""
    if next_s and advance_label:
        btn_cls = "btn-ghost" if next_s == "archived" else ("btn-amber" if next_s == "intake" else "btn-primary")
        advance_btn = (f'<button onclick="advance(event,\'{opp}\',\'{next_s}\')" '
                       f'class="card-btn {btn_cls}">{advance_label} →</button>')

    extra_btn = ""
    if stage == "under_review" and rec == "reconsider":
        extra_btn = (f'<button onclick="advance(event,\'{opp}\',\'needs_clarification\')" '
                     f'class="card-btn btn-amber">Flag for Clarification</button>')

    mgr_ini = initials(mgr.get("name", "??"))

    if is_intake:
        has_sow = bool((row.get("sow_text") or "").strip())
        action  = (f'<button onclick="scan(event,\'{opp}\')" class="card-btn btn-primary">Run AI Review →</button>'
                   if has_sow else
                   '<div class="card-pending">⏳ Upload SoW to scan</div>')
        return f'''<div class="eng-card stage-intake" onclick="openDetail('{opp}')" id="card-{opp}">
  <div class="card-opp">{opp}</div>
  <div class="card-name">{name}</div>
  <div class="card-mgr"><span class="mgr-avatar">{mgr_ini}</span>{mgr.get("name","")}</div>
  <div class="card-actions" onclick="event.stopPropagation()">{action}</div>
</div>'''

    rec_badge = ""
    if cfg:
        rec_badge = (f'<span class="badge-rec" style="background:{cfg["bg"]};color:{cfg["color"]};'
                     f'border:1px solid {cfg["border"]}">{cfg["icon"]} {cfg["label"]}</span>')

    return f'''<div class="eng-card stage-{stage.replace("_","-")}" onclick="openDetail('{opp}')" id="card-{opp}">
  <div class="card-opp">{opp}</div>
  <div class="card-name">{name}</div>
  <div class="card-verdict-row">
    {rec_badge}
    <span class="card-hours">{hours:.1f} h ⏱</span>
  </div>
  {('<div class="card-summary">'+summary_short+'</div>') if summary_short else ""}
  {'<div class="card-kpi-gap">⚠ ' + str(kpi_count) + ' KPI gap' + ('s' if kpi_count!=1 else '') + '</div>' if kpi_count else ""}
  <div class="card-mgr"><span class="mgr-avatar">{mgr_ini}</span>{mgr.get("name","")}</div>
  <div class="card-actions" onclick="event.stopPropagation()">{advance_btn}{extra_btn}</div>
</div>'''

# ---------------------------------------------------------------------------
# Detail payload
# ---------------------------------------------------------------------------
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
    else:
        direction = ("Outcome-based pricing is not viable in its current form. The contract "
                     "should remain T&M or fixed-fee unless the scope is restructured.")

    mgr_first = (mgr.get("name") or "the engagement manager").split()[0]
    if stage in ("scanned", "under_review"):
        next_action = ("Analyst review required. Validate the agent verdict, review detected "
                       "outcomes, and either approve or flag for clarification.")
    elif stage == "needs_clarification":
        next_action = (f"Contact {mgr_first} to facilitate client re-scoping. Draft targeted "
                       "KPI questions using the gaps identified below.")
    elif stage == "validated":
        next_action = ("Verdict validated. Engagement counts toward portfolio coverage. "
                       f"Consider activating {mgr_first} with detailed transformation instructions.")
    elif stage == "rejected":
        next_action = ("Engagement ruled out. Log rationale and schedule a re-scoping "
                       f"conversation with {mgr_first} if the client relationship allows.")
    else:
        next_action = "Review pending."

    return {
        "opportunity_id":            opp,
        "engagement_name":           row.get("engagement_name", ""),
        "stage":                     stage,
        "recommendation":            rec,
        "rec_label":                 cfg["label"],
        "rec_icon":                  cfg["icon"],
        "summary":                   row.get("summary") or "",
        "detected_outcomes":         row.get("detected_outcomes") or [],
        "missing_kpis":              row.get("missing_kpis") or [],
        "transformation_opportunities": row.get("transformation_opportunities") or [],
        "hours_saved":               row.get("hours_saved") or 0,
        "value_attribution":         row.get("value_attribution") or {},
        "commercial_direction":      direction,
        "next_action":               next_action,
        "manager":                   mgr,
        "run_history":               run_history.get(opp, [])[:10],
    }

# ---------------------------------------------------------------------------
# Board HTML
# ---------------------------------------------------------------------------
def build_board(buckets: dict) -> str:
    parts = []
    for key, label, hint in STAGES:
        cards  = buckets.get(key, [])
        color  = STAGE_COLOR.get(key, CAP_BLUE)
        c_html = "".join(card_html(c) for c in cards) or '<div class="lane-empty">No engagements</div>'
        parts.append(f'''<div class="lane lane-{key.replace("_","-")}" style="--lane-color:{color}">
  <div class="lane-header">
    <span class="lane-dot" style="background:{color}"></span>
    <span class="lane-title">{label}</span>
    <span class="lane-count">{len(cards)}</span>
  </div>
  <div class="lane-hint">{hint}</div>
  <div class="lane-cards">{c_html}</div>
</div>''')
    return "\n".join(parts)

# ---------------------------------------------------------------------------
# Page render
# ---------------------------------------------------------------------------
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
        "%%BOARD_HTML%%":    board_html,
        "%%DETAILS_JSON%%":  details_json,
        "%%BLUE%%":          CAP_BLUE,
        "%%NAVY%%":          CAP_NAVY,
        "%%LIGHT%%":         CAP_LIGHT,
        "%%BORDER%%":        CAP_BORDER,
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
<title>Outcome Readiness Review · Contoso Consulting</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Inter,Arial,sans-serif;background:#EDF1F7;color:""" + CAP_NAVY + r""";min-height:100vh;font-size:14px;line-height:1.5}

/* Topbar */
.topbar{background:""" + CAP_NAVY + r""";padding:.65rem 2rem;display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid #1C3A60}
.topbar-left{display:flex;align-items:center;gap:.75rem}
.topbar-brand{font-size:.85rem;font-weight:800;letter-spacing:.05em;color:""" + CAP_BLUE + r""";text-transform:uppercase}
.topbar-sep{color:#2E4E6E;font-size:1.1rem}
.topbar-title{font-size:.85rem;color:#A8C0D8;font-weight:400}
.topbar-right{font-size:.72rem;color:#4A6A88;display:flex;align-items:center;gap:.75rem}
.topbar-right a{color:#6A8CAA;text-decoration:none}
.topbar-right a:hover{color:#A8C0D8}
.demo-badge{background:#1C3A60;color:#6AB4E0;border:1px solid #2E527A;border-radius:.25rem;padding:.1rem .45rem;font-size:.65rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase}

/* Page */
.page{padding:1.5rem 1.75rem 4rem;max-width:1600px;margin:0 auto}

/* KPI row */
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1.5rem}
.kpi-tile{background:#fff;border:1px solid """ + CAP_BORDER + r""";border-radius:.6rem;padding:1.1rem 1.25rem;box-shadow:0 1px 3px rgba(18,40,76,.06);position:relative;overflow:hidden}
.kpi-tile::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--kpi-accent,""" + CAP_BLUE + r""")}
.kpi-label{font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#7A96B0;margin-bottom:.35rem}
.kpi-value{font-size:1.9rem;font-weight:700;line-height:1;color:var(--kpi-accent,""" + CAP_BLUE + r""")}
.kpi-sub{font-size:.72rem;color:#9AAFBF;margin-top:.3rem}

/* Section header */
.section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem}
.section-title{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#7A96B0}

/* Intake panel */
.intake-panel{background:#fff;border:1px solid """ + CAP_BORDER + r""";border-radius:.6rem;padding:1rem 1.25rem 1.1rem;box-shadow:0 1px 3px rgba(18,40,76,.06);margin-bottom:1.5rem}
.intake-form{display:flex;gap:.75rem;flex-wrap:wrap;align-items:flex-end}
.intake-field{display:flex;flex-direction:column;gap:.3rem;flex:1;min-width:160px}
.intake-field label{font-size:.67rem;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:#7A96B0}
.intake-field input[type=text]{border:1px solid """ + CAP_BORDER + r""";border-radius:.35rem;padding:.45rem .65rem;font-size:.82rem;color:""" + CAP_NAVY + r""";background:#F8FAFB;transition:border-color .15s,box-shadow .15s}
.intake-field input:focus{outline:none;border-color:""" + CAP_BLUE + r""";box-shadow:0 0 0 3px rgba(0,112,173,.1)}
.drop-zone{flex:2;min-width:220px;border:2px dashed """ + CAP_BORDER + r""";border-radius:.4rem;padding:.5rem .9rem;font-size:.8rem;color:#8BAABF;cursor:pointer;background:#F8FAFB;display:flex;align-items:center;gap:.5rem;transition:border-color .15s,background .15s}
.drop-zone.drag-over{border-color:""" + CAP_BLUE + r""";background:#EEF7FF;color:""" + CAP_BLUE + r"""}
.drop-zone input[type=file]{display:none}
.btn-scan{background:""" + CAP_BLUE + r""";color:#fff;border:none;border-radius:.35rem;padding:.5rem 1.1rem;font-size:.8rem;font-weight:600;cursor:pointer;white-space:nowrap;align-self:flex-end;transition:background .15s,box-shadow .15s}
.btn-scan:hover{background:#005E94;box-shadow:0 2px 6px rgba(0,112,173,.25)}
.btn-scan:disabled{background:#B0C4D8;cursor:not-allowed}
.intake-status{font-size:.78rem;margin-top:.6rem;min-height:1.2em;color:#5A7A99}
.intake-status.error{color:#D94040}
.intake-status.ok{color:#2D9E6B}

/* Workspace */
.workspace{display:grid;grid-template-columns:1fr 390px;gap:1.25rem;align-items:start}
.board-col{min-width:0}
.board-scroll{overflow-x:auto;padding-bottom:.5rem}
.pipeline{display:grid;grid-template-columns:repeat(7,minmax(155px,1fr));gap:.75rem;min-width:1085px}

/* Lane */
.lane{background:#fff;border:1px solid """ + CAP_BORDER + r""";border-top:3px solid var(--lane-color,""" + CAP_BLUE + r""");border-radius:.5rem;padding:.65rem .65rem .75rem;box-shadow:0 1px 3px rgba(18,40,76,.05);min-width:0}
.lane-header{display:flex;align-items:center;gap:.3rem;margin-bottom:.2rem}
.lane-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.lane-title{font-size:.75rem;font-weight:700;color:""" + CAP_NAVY + r""";flex:1}
.lane-count{background:#EEF2F7;color:#5A7A99;border-radius:9999px;font-size:.62rem;font-weight:700;padding:.05rem .38rem}
.lane-hint{font-size:.63rem;color:#9AAFBF;margin-bottom:.5rem;line-height:1.35}
.lane-cards{display:flex;flex-direction:column;gap:.4rem}
.lane-empty{font-size:.72rem;color:#C0D0DF;font-style:italic;padding:.2rem 0}

/* Engagement card */
.eng-card{background:#F8FAFB;border:1px solid """ + CAP_BORDER + r""";border-radius:.4rem;padding:.5rem .6rem .45rem;cursor:pointer;transition:box-shadow .15s,border-color .15s,transform .1s}
.eng-card:hover{box-shadow:0 4px 12px rgba(18,40,76,.12);border-color:var(--lane-color,""" + CAP_BLUE + r""");transform:translateY(-1px)}
.eng-card.selected{border-color:""" + CAP_BLUE + r""";box-shadow:0 0 0 2px rgba(0,112,173,.2)}
.card-opp{font-size:.6rem;color:#9AAFBF;letter-spacing:.03em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:.1rem}
.card-name{font-size:.75rem;font-weight:600;color:""" + CAP_NAVY + r""";line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:.3rem}
.card-verdict-row{display:flex;align-items:center;justify-content:space-between;gap:.25rem;margin-bottom:.25rem}
.card-hours{font-size:.63rem;color:#7A96B0;white-space:nowrap}
.badge-rec{padding:.15rem .45rem;border-radius:.25rem;font-size:.67rem;font-weight:700;letter-spacing:.02em;white-space:nowrap}
.card-summary{font-size:.65rem;color:#5A7A99;line-height:1.35;margin-bottom:.25rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-kpi-gap{font-size:.62rem;color:#92530C;background:#FEF9EE;border:1px solid #F6C87A;border-radius:.2rem;padding:.1rem .3rem;display:inline-block;margin-bottom:.25rem}
.card-mgr{display:flex;align-items:center;gap:.3rem;font-size:.63rem;color:#7A96B0;margin-bottom:.3rem}
.mgr-avatar{width:18px;height:18px;border-radius:50%;background:""" + CAP_BLUE + r""";color:#fff;font-size:.52rem;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.card-actions{display:flex;flex-direction:column;gap:.25rem}
.card-pending{font-size:.65rem;color:#9AAFBF;background:""" + CAP_LIGHT + r""";border:1px dashed """ + CAP_BORDER + r""";border-radius:.25rem;padding:.2rem .4rem;margin-bottom:.25rem}
.stage-needs-clarification{background:#FEF9EE;border-color:#F6C87A}
.stage-validated{background:#F0FAF4;border-color:#A8D5B5}
.stage-rejected{background:#FFF5F5;border-color:#F5AAAA}
.stage-archived{opacity:.65}
.card-btn{width:100%;padding:.27rem .4rem;border-radius:.25rem;font-size:.67rem;font-weight:600;cursor:pointer;border:1px solid transparent;text-align:center;transition:opacity .15s}
.card-btn:hover{opacity:.85}
.btn-primary{background:""" + CAP_BLUE + r""";color:#fff;border-color:""" + CAP_BLUE + r"""}
.btn-ghost{background:""" + CAP_LIGHT + r""";color:#5A7A99;border-color:""" + CAP_BORDER + r"""}
.btn-amber{background:#FEF3E2;color:#92530C;border-color:#F6C87A}

/* Detail panel */
.detail-panel{background:#fff;border:1px solid """ + CAP_BORDER + r""";border-radius:.6rem;box-shadow:0 2px 12px rgba(18,40,76,.08);position:sticky;top:1.25rem;max-height:calc(100vh - 2.5rem);overflow-y:auto;display:flex;flex-direction:column}
.detail-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:3rem 2rem;text-align:center;color:#9AAFBF}
.detail-empty-icon{font-size:2.5rem;margin-bottom:.75rem;opacity:.4}
.detail-empty-text{font-size:.82rem;line-height:1.5}
.detail-content{padding:1.25rem;flex:1}
.detail-header{margin-bottom:1rem;padding-bottom:.75rem;border-bottom:1px solid """ + CAP_BORDER + r"""}
.detail-opp{font-size:.67rem;color:#9AAFBF;letter-spacing:.03em;margin-bottom:.2rem}
.detail-name{font-size:1rem;font-weight:700;color:""" + CAP_NAVY + r""";line-height:1.3;margin-bottom:.5rem}
.detail-verdict-row{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
.detail-section{margin-bottom:1rem}
.detail-section-title{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#9AAFBF;margin-bottom:.4rem}
.detail-body{font-size:.78rem;color:#334E68;line-height:1.55}
.detail-list{display:flex;flex-direction:column;gap:.3rem}
.detail-list-item{font-size:.75rem;color:#334E68;background:""" + CAP_LIGHT + r""";border:1px solid """ + CAP_BORDER + r""";border-radius:.3rem;padding:.3rem .5rem;line-height:1.4}
.detail-kpi-item{font-size:.75rem;color:#92530C;background:#FEF9EE;border:1px solid #F6C87A;border-radius:.3rem;padding:.3rem .5rem}
.detail-hours-badge{display:inline-flex;align-items:center;gap:.3rem;background:#EEF6FF;border:1px solid #C5DEFA;border-radius:.3rem;padding:.2rem .55rem;font-size:.72rem;font-weight:600;color:""" + CAP_BLUE + r"""}
.detail-direction{font-size:.78rem;color:#334E68;line-height:1.55;background:""" + CAP_LIGHT + r""";border-left:3px solid """ + CAP_BLUE + r""";border-radius:0 .3rem .3rem 0;padding:.5rem .75rem}
.detail-action-box{background:#F0FAF4;border:1px solid #A8D5B5;border-radius:.35rem;padding:.5rem .75rem;font-size:.78rem;color:#1A6B3C;line-height:1.5}
.run-history-item{display:flex;align-items:center;gap:.5rem;font-size:.7rem;color:#5A7A99;padding:.2rem 0;border-bottom:1px solid """ + CAP_BORDER + r"""}
.run-history-item:last-child{border-bottom:none}
.run-ts{color:#9AAFBF;font-size:.65rem}
.mgr-card{display:flex;align-items:center;gap:.75rem;background:""" + CAP_LIGHT + r""";border:1px solid """ + CAP_BORDER + r""";border-radius:.4rem;padding:.55rem .75rem}
.mgr-avatar-lg{width:34px;height:34px;border-radius:50%;background:""" + CAP_BLUE + r""";color:#fff;font-size:.75rem;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.mgr-info{flex:1;min-width:0}
.mgr-name{font-size:.78rem;font-weight:600;color:""" + CAP_NAVY + r"""}
.mgr-role{font-size:.67rem;color:#7A96B0}
.mgr-email{font-size:.65rem;color:#9AAFBF}
.btn-activate{width:100%;padding:.55rem .75rem;background:""" + CAP_NAVY + r""";color:#fff;border:none;border-radius:.4rem;font-size:.8rem;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.4rem;transition:background .15s,box-shadow .15s;margin-top:.75rem}
.btn-activate:hover{background:#0A1E3C;box-shadow:0 3px 8px rgba(18,40,76,.25)}

/* Modal */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(12,28,52,.55);backdrop-filter:blur(3px);z-index:1000;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:#fff;border-radius:.75rem;box-shadow:0 20px 60px rgba(12,28,52,.3);width:min(680px,95vw);max-height:90vh;overflow-y:auto;padding:2rem;animation:modal-in .2s ease}
@keyframes modal-in{from{opacity:0;transform:translateY(-12px) scale(.97)}to{opacity:1;transform:none}}
.modal-header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1.25rem;padding-bottom:1rem;border-bottom:1px solid """ + CAP_BORDER + r"""}
.modal-title{font-size:1.05rem;font-weight:700;color:""" + CAP_NAVY + r""";line-height:1.3}
.modal-subtitle{font-size:.78rem;color:#7A96B0;margin-top:.2rem}
.modal-close{background:none;border:none;cursor:pointer;font-size:1.3rem;color:#9AAFBF;line-height:1;padding:.1rem}
.modal-close:hover{color:""" + CAP_NAVY + r"""}
.modal-section{margin-bottom:1.25rem}
.modal-section-title{font-size:.67rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#9AAFBF;margin-bottom:.45rem}
.modal-body{font-size:.82rem;color:#334E68;line-height:1.6;background:""" + CAP_LIGHT + r""";border-radius:.35rem;padding:.65rem .85rem}
.modal-body p{margin-bottom:.5rem}
.modal-body p:last-child{margin-bottom:0}
.modal-body ul{padding-left:1.1rem;display:flex;flex-direction:column;gap:.25rem}
.modal-actions{display:flex;gap:.75rem;flex-wrap:wrap;padding-top:1rem;border-top:1px solid """ + CAP_BORDER + r""";margin-top:1rem}
.btn-send{flex:1;padding:.55rem .9rem;background:""" + CAP_BLUE + r""";color:#fff;border:none;border-radius:.35rem;font-size:.82rem;font-weight:700;cursor:pointer;transition:background .15s}
.btn-send:hover{background:#005E94}
.btn-modal-ghost{flex:1;padding:.55rem .9rem;background:""" + CAP_LIGHT + r""";color:#5A7A99;border:1px solid """ + CAP_BORDER + r""";border-radius:.35rem;font-size:.82rem;font-weight:600;cursor:pointer}
.toast{position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%) translateY(1rem);background:""" + CAP_NAVY + r""";color:#fff;border-radius:.4rem;padding:.6rem 1.25rem;font-size:.82rem;font-weight:500;box-shadow:0 4px 16px rgba(12,28,52,.3);opacity:0;transition:opacity .3s,transform .3s;pointer-events:none;white-space:nowrap;z-index:2000}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
a{color:""" + CAP_BLUE + r""";text-decoration:none}
a:hover{text-decoration:underline}
code{background:""" + CAP_LIGHT + r""";border:1px solid """ + CAP_BORDER + r""";padding:.1rem .3rem;border-radius:.2rem;font-size:.75rem;color:#334E68}
.footer{margin-top:2.5rem;text-align:center;font-size:.72rem;color:#9AAFBF}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <span class="topbar-brand">Contoso Consulting</span>
    <span class="topbar-sep">|</span>
    <span class="topbar-title">Outcome Readiness Review &middot; SoW Pipeline</span>
  </div>
  <div class="topbar-right">
    <span class="demo-badge">Demo</span>
    <span>%%GENERATED%%</span>
    <a href="/">&#8635; Refresh</a>
  </div>
</div>

<div class="page">

<div class="kpi-row">
  <div class="kpi-tile" style="--kpi-accent:%%BLUE%%">
    <div class="kpi-label">Engagements in scope</div>
    <div class="kpi-value">%%TOTAL_OPPS%%</div>
    <div class="kpi-sub">unique SoWs in the pipeline</div>
  </div>
  <div class="kpi-tile" style="--kpi-accent:%%COVERAGE_COLOR%%">
    <div class="kpi-label">Validated review coverage</div>
    <div class="kpi-value" style="color:%%COVERAGE_COLOR%%">%%COVERAGE_PCT%%%</div>
    <div class="kpi-sub">%%VALIDATED_CNT%% of %%TOTAL_OPPS%% engagements validated</div>
  </div>
  <div class="kpi-tile" style="--kpi-accent:#2D9E6B">
    <div class="kpi-label">Analyst hours saved</div>
    <div class="kpi-value" style="color:#2D9E6B">%%TOTAL_HOURS%%&thinsp;h</div>
    <div class="kpi-sub">across %%TOTAL_RUNS%% agent runs</div>
  </div>
  <div class="kpi-tile" style="--kpi-accent:#7B52AB">
    <div class="kpi-label">Outcome-ready candidates</div>
    <div class="kpi-value" style="color:#7B52AB">%%OUTCOME_READY%%</div>
    <div class="kpi-sub">engagements with Recommend verdict</div>
  </div>
</div>

<div class="intake-panel">
  <div class="section-header" style="margin-bottom:.65rem">
    <span class="section-title">Submit a SoW for AI Review</span>
  </div>
  <div class="intake-form">
    <div class="intake-field">
      <label>Opportunity ID</label>
      <input type="text" id="opp-id" placeholder="e.g. OPP-2026-0400"/>
    </div>
    <div class="intake-field">
      <label>Engagement Name</label>
      <input type="text" id="eng-name" placeholder="Client &middot; Topic"/>
    </div>
    <div class="drop-zone" id="drop-zone" onclick="document.getElementById('file-input').click()">
      <input type="file" id="file-input" accept=".pdf,.docx,.doc,.txt" onchange="onFileChosen(this)"/>
      <span id="drop-label">&#128196; Drop PDF / DOCX / TXT, or click to browse</span>
    </div>
    <button class="btn-scan" id="upload-btn" onclick="submitUpload()" disabled>Run AI Review &rarr;</button>
  </div>
  <div class="intake-status" id="upload-status"></div>
</div>

<div class="workspace">
  <div class="board-col">
    <div class="section-header">
      <span class="section-title">Review Pipeline</span>
      <span style="font-size:.72rem;color:#9AAFBF">Click any card to open detail &rarr;</span>
    </div>
    <div class="board-scroll">
      <div class="pipeline">%%BOARD_HTML%%</div>
    </div>
  </div>

  <div class="detail-panel" id="detail-panel">
    <div class="detail-empty" id="detail-empty">
      <div class="detail-empty-icon">&#128269;</div>
      <div class="detail-empty-text">Select an engagement card<br>to view the full assessment</div>
    </div>
    <div class="detail-content" id="detail-content" style="display:none"></div>
  </div>
</div>

<p class="footer">
  Advance stages via card buttons &nbsp;&middot;&nbsp;
  <code>sqlite3 runs.db "UPDATE runs SET pipeline_status='under_review' WHERE opportunity_id='OPP-...'"</code>
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
      <button class="btn-send" onclick="simulateSend()">&#9993; Send to Engagement Manager</button>
      <button class="btn-modal-ghost" onclick="closeModal()">Close</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const DETAILS = %%DETAILS_JSON%%;
const REC_CFG = {
  recommend:  {bg:'#E8F7EE',color:'#1A6B3C',border:'#A8D5B5',icon:'✓',label:'Recommend'},
  reconsider: {bg:'#FEF3E2',color:'#92530C',border:'#F6C87A',icon:'◐',label:'Reconsider'},
  rule_out:   {bg:'#FDECEA',color:'#9B1C1C',border:'#F5AAAA',icon:'✕',label:'Rule Out'},
};
let activeOpp = null;

// Upload
const dropZone  = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const statusEl  = document.getElementById('upload-status');
let chosenFile  = null;
function onFileChosen(input) {
  chosenFile = input.files[0];
  if (chosenFile) { document.getElementById('drop-label').textContent = '✓ ' + chosenFile.name; uploadBtn.disabled = false; }
}
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) { fileInput.files = e.dataTransfer.files; onFileChosen(fileInput); }
});
function setStatus(msg, cls) { statusEl.textContent = msg; statusEl.className = 'intake-status' + (cls ? ' ' + cls : ''); }
function submitUpload() {
  const oppId = document.getElementById('opp-id').value.trim();
  const engName = document.getElementById('eng-name').value.trim();
  if (!oppId)   { setStatus('Please enter an Opportunity ID.', 'error'); return; }
  if (!engName) { setStatus('Please enter an Engagement name.', 'error'); return; }
  if (!chosenFile) { setStatus('Please choose a file.', 'error'); return; }
  uploadBtn.disabled = true; setStatus('⏳ Scanning with AI agent… (30–60 s)');
  const fd = new FormData();
  fd.append('file', chosenFile); fd.append('opportunity_id', oppId); fd.append('engagement_name', engName);
  fetch('/upload', {method:'POST',body:fd})
    .then(async r => {
      const txt = await r.text();
      if (r.ok) { let rec=''; try{rec=JSON.parse(txt).recommendation;}catch(_){} setStatus('✓ Verdict: '+(rec||'see pipeline')+'. Refreshing…','ok'); setTimeout(()=>location.reload(),1400); }
      else { setStatus('Error: '+txt,'error'); uploadBtn.disabled=false; }
    })
    .catch(e => { setStatus('Network error: '+e,'error'); uploadBtn.disabled=false; });
}

// Board actions
function scan(e, opp) {
  e.stopPropagation();
  const card = document.getElementById('card-'+opp);
  const btn = card ? card.querySelector('.btn-primary') : null;
  if (btn) { btn.disabled=true; btn.textContent='⏳ Scanning…'; }
  fetch('/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_id:opp})})
    .then(r=>r.ok?r.json():r.text().then(t=>{throw new Error(t);}))
    .then(()=>location.reload())
    .catch(e=>{alert('Scan failed: '+e.message);if(btn){btn.disabled=false;btn.textContent='Run AI Review →';}});
}
function advance(e, oppId, nextStage) {
  e.stopPropagation();
  const btn = e.target; btn.disabled=true; btn.textContent='Moving…';
  fetch('/advance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({opportunity_id:oppId,pipeline_status:nextStage})})
    .then(r=>{ if(r.ok) location.reload(); else{btn.disabled=false;btn.textContent='Error — retry';} });
}

// Detail panel
function openDetail(opp) {
  activeOpp = opp;
  const d = DETAILS[opp]; if (!d) return;
  document.querySelectorAll('.eng-card').forEach(c=>c.classList.remove('selected'));
  const card = document.getElementById('card-'+opp); if(card) card.classList.add('selected');
  document.getElementById('detail-empty').style.display = 'none';
  document.getElementById('detail-content').style.display = 'block';

  const cfg = REC_CFG[d.recommendation] || {bg:'#F0F4F8',color:'#5A7A99',border:'#D1DCE8',icon:'·',label:d.rec_label||'—'};
  const mgr = d.manager || {};
  const ini = mgr.name ? mgr.name.split(' ').map(p=>p[0]).join('').slice(0,2).toUpperCase() : '??';

  const outHtml = (d.detected_outcomes && d.detected_outcomes.length)
    ? d.detected_outcomes.map(o=>`<div class="detail-list-item">✓ ${o}</div>`).join('')
    : '<div style="font-size:.75rem;color:#9AAFBF">None detected</div>';

  const kpiHtml = (d.missing_kpis && d.missing_kpis.length)
    ? d.missing_kpis.map(k=>`<div class="detail-kpi-item">⚠ ${k}</div>`).join('')
    : '<div style="font-size:.75rem;color:#2D9E6B">No gaps identified ✓</div>';

  const histHtml = (d.run_history && d.run_history.length) ? d.run_history.map(r=>{
    const rc = REC_CFG[r.recommendation]||{};
    const badge = r.recommendation?`<span style="background:${rc.bg||'#eee'};color:${rc.color||'#666'};border:1px solid ${rc.border||'#ccc'};padding:.05rem .3rem;border-radius:.2rem;font-size:.62rem;font-weight:700">${rc.icon||'·'} ${rc.label||r.recommendation}</span>`:'';
    const ts = r.created_at?r.created_at.slice(0,16).replace('T',' '):'';
    const hrs = r.hours_saved?r.hours_saved.toFixed(1)+' h':'';
    return `<div class="run-history-item">${badge}<span style="font-size:.62rem;color:#9AAFBF">${r.agent_name||''}</span><span style="flex:1"></span>${hrs?`<span class="card-hours">${hrs}</span>`:''}<span class="run-ts">${ts}</span></div>`;
  }).join('') : '<div style="font-size:.7rem;color:#9AAFBF">No run history</div>';

  document.getElementById('detail-content').innerHTML = `
    <div class="detail-header">
      <div class="detail-opp">${d.opportunity_id}</div>
      <div class="detail-name">${d.engagement_name}</div>
      <div class="detail-verdict-row">
        <span style="background:${cfg.bg};color:${cfg.color};border:1px solid ${cfg.border};padding:.22rem .65rem;border-radius:.3rem;font-size:.75rem;font-weight:700">${cfg.icon} ${cfg.label}</span>
        <span class="detail-hours-badge">⏱ ${(d.hours_saved||0).toFixed(1)} h saved</span>
      </div>
    </div>
    <div class="detail-section">
      <div class="detail-section-title">Executive Summary</div>
      <div class="detail-body">${d.summary||'No summary available.'}</div>
    </div>
    <div class="detail-section">
      <div class="detail-section-title">Detected Outcomes</div>
      <div class="detail-list">${outHtml}</div>
    </div>
    <div class="detail-section">
      <div class="detail-section-title">KPI / Measurement Gaps</div>
      <div class="detail-list">${kpiHtml}</div>
    </div>
    <div class="detail-section">
      <div class="detail-section-title">Recommended Commercial Direction</div>
      <div class="detail-direction">${d.commercial_direction}</div>
    </div>
    <div class="detail-section">
      <div class="detail-section-title">Next Action</div>
      <div class="detail-action-box">${d.next_action}</div>
    </div>
    <div class="detail-section">
      <div class="detail-section-title">Engagement Manager</div>
      <div class="mgr-card">
        <div class="mgr-avatar-lg">${ini}</div>
        <div class="mgr-info">
          <div class="mgr-name">${mgr.name||'—'}</div>
          <div class="mgr-role">${mgr.title||''}</div>
          <div class="mgr-email">${mgr.email||''}</div>
        </div>
      </div>
      <button class="btn-activate" onclick="openModal('${opp}')">&#9993; Send Instructions to ${(mgr.name||'').split(' ')[0]||'Manager'}</button>
    </div>
    <div class="detail-section">
      <div class="detail-section-title">Run History</div>
      ${histHtml}
    </div>`;
}

// Activation modal
function openModal(opp) {
  const d = DETAILS[opp]; if (!d) return;
  const mgr = d.manager || {};
  const cfg = REC_CFG[d.recommendation] || {};
  document.getElementById('modal-title').textContent = `Instruction Package · ${mgr.name||'Engagement Manager'}`;
  document.getElementById('modal-subtitle').textContent = `${d.engagement_name} · ${d.opportunity_id}`;
  const kpiList = (d.missing_kpis && d.missing_kpis.length)
    ? '<ul>'+d.missing_kpis.map(k=>`<li>${k}</li>`).join('')+'</ul>'
    : '<p>No KPI gaps identified — the SoW has sufficient measurement detail.</p>';
  const outList = (d.detected_outcomes && d.detected_outcomes.length)
    ? '<ul>'+d.detected_outcomes.map(o=>`<li>${o}</li>`).join('')+'</ul>'
    : '<p>No specific outcomes were detected.</p>';
  const isActionable = d.recommendation==='reconsider'||d.recommendation==='recommend';
  document.getElementById('modal-body').innerHTML = `
    <div class="modal-section">
      <div class="modal-section-title">Why this engagement was flagged</div>
      <div class="modal-body">
        <p>The Outcome Readiness Review Agent assessed <strong>${d.engagement_name}</strong> and returned a verdict of <strong>${cfg.icon||''} ${cfg.label||d.recommendation}</strong>.</p>
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
      <div class="modal-section-title">What ${mgr.name||'you'} needs to do next</div>
      <div class="modal-body">
        <p>${d.next_action}</p>
        ${isActionable ? `<ul>
          <li>Contact the client to request missing KPI baselines</li>
          <li>Propose a measurement methodology and agree a control group design</li>
          <li>Engage Contoso Consulting's commercial team to model the outcome-linked fee structure</li>
          <li>Update the SoW to reflect agreed KPIs, baselines, targets, and payment triggers</li>
          <li>Return the updated SoW for a re-scan before contract execution</li>
        </ul>` : `<ul>
          <li>Log the rationale for ruling out outcome-based pricing</li>
          <li>Schedule a re-scoping conversation if the client relationship allows</li>
          <li>Flag for re-review at the next contract renewal or scope change</li>
        </ul>`}
      </div>
    </div>`;
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
function showToast(msg) {
  const t = document.getElementById('toast'); t.textContent = msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),3500);
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
DB_PATH = "runs.db"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
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
        if self.path == "/upload":  self._handle_upload();  return
        if self.path == "/scan":    self._handle_scan();    return
        if self.path == "/advance": self._handle_advance(); return
        self.send_response(404); self.end_headers()

    def _handle_upload(self):
        content_type   = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        fields: dict = {}; file_data: bytes = b""; filename = "upload.txt"

        def _params(hv):
            m = email.message.Message(); m["content-disposition"] = hv
            return {"name": m.get_param("name", header="content-disposition") or "",
                    "filename": m.get_param("filename", header="content-disposition") or ""}

        _ct = email.message.Message(); _ct["content-type"] = content_type
        boundary = _ct.get_param("boundary")
        if boundary:
            for chunk in raw_body.split(("--" + boundary).encode())[1:]:
                if chunk.strip() in (b"", b"--", b"--\r\n", b"--\n"): continue
                sep = b"\r\n\r\n" if b"\r\n\r\n" in chunk else (b"\n\n" if b"\n\n" in chunk else None)
                if not sep: continue
                hdr_raw, body_chunk = chunk.split(sep, 1)
                body_chunk = body_chunk.rstrip(b"\r\n")
                ph = {}
                for line in hdr_raw.decode("utf-8", errors="replace").strip().splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":"); ph[k.strip().lower()] = v.strip()
                p = _params(ph.get("content-disposition", ""))
                if p["name"] == "file": file_data = body_chunk; filename = p["filename"] or "upload.txt"
                elif p["name"]: fields[p["name"]] = body_chunk.decode("utf-8", errors="replace")

        opp_id   = fields.get("opportunity_id", "").strip()
        eng_name = fields.get("engagement_name", "").strip()
        if not opp_id or not eng_name:
            self._respond(400, "opportunity_id and engagement_name required"); return
        if not file_data:
            self._respond(400, "No file received"); return
        try:    sow_text = extract_text(filename, file_data)
        except Exception as e: self._respond(500, f"Extraction failed: {e}"); return
        if not sow_text.strip():
            self._respond(400, "Could not extract text"); return

        stub = {"run_id": str(_uuid.uuid4()), "opportunity_id": opp_id,
                "engagement_name": eng_name, "recommendation": None, "status": "draft"}
        log_run(stub, DB_PATH, pipeline_status="intake", sow_text=sow_text)
        try:    result = call_agent_with_text(opp_id, eng_name, sow_text)
        except Exception as e: self._respond(500, f"Agent failed: {e}"); return
        try:    log_run(result, DB_PATH, pipeline_status="scanned", sow_text=sow_text)
        except Exception as e: self._respond(500, f"DB write failed: {e}"); return
        self._json_respond(200, result)

    def _handle_scan(self):
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        opp_id  = payload.get("opportunity_id", "").strip()
        if not opp_id: self._respond(400, "opportunity_id required"); return
        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT engagement_name, sow_text FROM runs WHERE opportunity_id=? ORDER BY created_at DESC LIMIT 1",
            (opp_id,)).fetchone()
        con.close()
        if not row or not (row[1] or "").strip():
            self._respond(400, "No SoW text stored — upload via the form"); return
        eng_name, sow_text = row
        try:    result = call_agent_with_text(opp_id, eng_name, sow_text)
        except Exception as e: self._respond(500, f"Agent failed: {e}"); return
        try:    log_run(result, DB_PATH, pipeline_status="scanned", sow_text=sow_text)
        except Exception as e: self._respond(500, f"DB write failed: {e}"); return
        self._json_respond(200, result)

    def _handle_advance(self):
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        opp_id  = payload.get("opportunity_id")
        stage   = payload.get("pipeline_status")
        if opp_id and stage in STAGE_KEYS:
            con = sqlite3.connect(DB_PATH)
            con.execute("UPDATE runs SET pipeline_status=? WHERE opportunity_id=?", (stage, opp_id))
            con.commit(); con.close()
            self.send_response(200); self.end_headers()
        else:
            self.send_response(400); self.end_headers()

    def log_message(self, fmt, *args): pass


def main():
    global DB_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",   default="runs.db")
    parser.add_argument("--port", type=int, default=5050)
    args    = parser.parse_args()
    DB_PATH = args.db
    server  = HTTPServer(("localhost", args.port), Handler)
    print(f"Outcome Readiness Dashboard  →  http://localhost:{args.port}")
    print("Press Ctrl-C to stop.")
    try:    server.serve_forever()
    except KeyboardInterrupt: print("\nStopped.")

if __name__ == "__main__":
    main()
