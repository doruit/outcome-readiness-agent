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
import urllib.request
import uuid as _uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

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
    ("scanned",             "AI Assessment",        "Automated scan complete — verdict ready"),
    ("under_review",        "Analyst Review",       "Human analyst reviewing AI assessment"),
    ("needs_clarification", "Clarification Required","Returned — SoW needs more information"),
    ("validated",           "Approved",             "Analyst confirmed — counts toward coverage"),
    ("rejected",            "Ruled Out",            "Not suitable for outcome-based model"),
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
    n_recommend  = len([r for r in latest if r.get("recommendation") == "recommend"])
    n_reconsider = len([r for r in latest if r.get("recommendation") == "reconsider"])
    n_rule_out   = len([r for r in latest if r.get("recommendation") == "rule_out"])

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
        "scanned":             "Send to Analyst",
        "under_review":        "Approve",
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

    has_sow = bool((row.get("sow_text") or "").strip())

    if is_intake:
        action  = (f'<button onclick="scan(event,\'{opp}\')" class="card-btn btn-primary">Run AI Review →</button>'
                   if has_sow else
                   '<div class="card-pending">⏳ Upload SoW to scan</div>')
        return f'''<div class="eng-card stage-intake" draggable="true" onclick="openDetail('{opp}')" id="card-{opp}" data-opp="{opp}" data-stage="intake" data-has-sow="{'1' if has_sow else '0'}">
  <div class="card-opp">{opp}</div>
  <div class="card-name">{name}</div>
  <div class="card-mgr"><span class="mgr-avatar">{mgr_ini}</span>{mgr.get("name","")}</div>
  <div class="card-actions" onclick="event.stopPropagation()">{action}</div>
</div>'''

    rec_badge = ""
    if cfg:
        rec_badge = (f'<span class="badge-rec" style="background:{cfg["bg"]};color:{cfg["color"]};'
                     f'border:1px solid {cfg["border"]}">{cfg["icon"]} {cfg["label"]}</span>')

    return f'''<div class="eng-card stage-{stage.replace("_","-")}" draggable="true" onclick="openDetail('{opp}')" id="card-{opp}" data-opp="{opp}" data-stage="{stage}">
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
        parts.append(f'''<div class="lane lane-{key.replace("_","-")}" style="--lane-color:{color}" data-lane="{key}">
  <div class="lane-header">
    <span class="lane-dot" style="background:{color}"></span>
    <span class="lane-title">{label}</span>
    <span class="lane-count">{len(cards)}</span>
  </div>
  <div class="lane-hint">{hint}</div>
  <div class="lane-cards" data-lane="{key}">{c_html}</div>
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
        "%%N_RECOMMEND%%":   str(d["n_recommend"]),
        "%%N_RECONSIDER%%":  str(d["n_reconsider"]),
        "%%N_RULE_OUT%%":    str(d["n_rule_out"]),
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
  background:""" + CAP_NAVY + r""";
  padding:.7rem 2rem;
  display:flex;align-items:center;justify-content:space-between;
  border-bottom:3px solid """ + CAP_BLUE + r""";
  position:sticky;top:0;z-index:100;
}
.topbar-left{display:flex;align-items:center;gap:.9rem}
.topbar-brand{
  font-size:.82rem;font-weight:800;letter-spacing:.09em;
  color:#fff;text-transform:uppercase;
}
.topbar-sep{color:#2A4060;font-size:1.2rem;font-weight:300}
.topbar-title{font-size:.88rem;color:#8DAFC8;font-weight:400;letter-spacing:.01em}
.topbar-right{font-size:.75rem;color:#516A80;display:flex;align-items:center;gap:.9rem}
.topbar-right a{color:#7BA4C0;text-decoration:none;transition:color .15s}
.topbar-right a:hover{color:#B8D4E8}
.demo-badge{
  background:rgba(0,112,173,.25);
  color:#5AC0F5;
  border:1px solid rgba(0,112,173,.4);
  border-radius:.2rem;
  padding:.12rem .5rem;
  font-size:.66rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
}

/* ─── Page ───────────────────────────────────────────────────────── */
.page{padding:1.75rem 2rem 5rem;max-width:1680px;margin:0 auto}

/* ─── Topbar model taxonomy ───────────────────────────────── */
.topbar-model{
  background:#0A1829;
  border-bottom:1px solid #152236;
  padding:0 2rem;
  display:flex;align-items:center;height:28px;
}
.tm-pill{
  display:flex;align-items:center;gap:.38rem;
  padding:0 1rem;height:100%;
  border-right:1px solid #1A2E48;
}
.tm-pill:first-child{padding-left:0}
.tm-pill:last-child{border-right:none}
.tm-role{font-size:.59rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#3A5A78}
.tm-name{font-size:.68rem;font-weight:500;color:#6A8AA4}
.tm-sep{font-size:.6rem;color:#1E3450}

/* ─── KPI row ────────────────────────────────────────────────────── */
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);background:#fff;border-bottom:1px solid #DDE5EF}
.kpi-tile{padding:.9rem 1.4rem .8rem;position:relative;overflow:hidden;border-right:1px solid #DDE5EF}
.kpi-tile:last-child{border-right:none}
.kpi-tile::after{
  content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:var(--kpi-accent,""" + CAP_BLUE + r""");
}
.kpi-label{font-size:.64rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#5A7A96;margin-bottom:.28rem}
.kpi-value{font-size:1.6rem;font-weight:800;line-height:1;color:var(--kpi-accent,""" + CAP_NAVY + r""");letter-spacing:-.02em}
.kpi-sub{font-size:.68rem;color:#607A94;margin-top:.25rem;line-height:1.4}

/* ─── Outcome verdict strip ──────────────────────────────────────── */
.outcome-strip{
  display:flex;align-items:center;gap:0;
  padding:0 1.4rem;height:38px;
  border-bottom:1px solid #DDE5EF;background:#FAFCFE;
}
.outcome-strip-label{
  font-size:.62rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  color:#5A7A96;white-space:nowrap;flex-shrink:0;
  padding-right:.9rem;border-right:1px solid #DDE5EF;margin-right:1.2rem;
}
.outcome-strip-verdicts{display:flex;align-items:center;gap:0;flex-shrink:0}
.osv{
  display:flex;align-items:center;gap:.3rem;
  padding:0 1rem;border-right:1px solid #DDE5EF;height:38px;
}
.osv:last-child{border-right:none}
.osv-icon{font-size:.7rem;font-weight:700;flex-shrink:0}
.osv-count{font-size:.92rem;font-weight:800;letter-spacing:-.01em;line-height:1}
.osv-label{font-size:.63rem;color:#7A96B0;margin-left:.1rem}
.osv-recommend .osv-icon,.osv-recommend .osv-count{color:#1A6B3C}
.osv-reconsider .osv-icon,.osv-reconsider .osv-count{color:#92530C}
.osv-ruleout .osv-icon,.osv-ruleout .osv-count{color:#9B1C1C}
.outcome-strip-bar{
  flex:1;height:4px;border-radius:2px;
  display:flex;overflow:hidden;gap:2px;margin-left:1.2rem;
}
.osb-seg{height:100%;border-radius:2px;min-width:3px}
.osb-recommend{background:#2D9E6B}
.osb-reconsider{background:#E8970A}
.osb-ruleout{background:#D94040}

/* ─── Section header ─────────────────────────────────────────────── */
.section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:.85rem}
.section-title{font-size:.76rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#3A5A78}

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
  margin-top:1.4rem;
}
.left-col{min-width:0;display:flex;flex-direction:column}
.board-section{margin-top:1.4rem}
.board-scroll{overflow-x:auto;padding-bottom:.75rem}
.pipeline{
  display:grid;
  grid-template-columns:repeat(7,minmax(160px,1fr));
  gap:.8rem;min-width:1120px;
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
.lane-header{display:flex;align-items:center;gap:.35rem;margin-bottom:.2rem}
.lane-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;background:var(--lane-color,""" + CAP_BLUE + r""")}
.lane-title{
  font-size:.84rem;font-weight:700;
  color:""" + CAP_NAVY + r""";flex:1;
  letter-spacing:.01em;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.lane-count{
  background:rgba(0,0,0,.09);
  color:#3A5A78;
  border-radius:9999px;
  font-size:.68rem;font-weight:700;
  padding:.07rem .45rem;
  flex-shrink:0;
}
.lane-hint{font-size:.72rem;color:#6A8AA4;margin-bottom:.65rem;line-height:1.45}
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
}
.card-name{
  font-size:.88rem;font-weight:600;
  color:""" + CAP_NAVY + r""";line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;
  word-break:break-word;
  margin-bottom:.45rem;
}
.card-verdict-row{
  display:flex;align-items:center;
  justify-content:space-between;gap:.3rem;
  margin-bottom:.35rem;
  min-width:0;
}
.card-hours{
  font-size:.72rem;color:#4A6A84;white-space:nowrap;
  font-variant-numeric:tabular-nums;
  flex-shrink:0;
}
.badge-rec{
  display:inline-flex;align-items:center;gap:.2rem;
  padding:.18rem .5rem;border-radius:.28rem;
  font-size:.68rem;font-weight:700;
  letter-spacing:.02em;white-space:nowrap;
  line-height:1.2;
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
.card-mgr{
  display:flex;align-items:center;gap:.35rem;
  font-size:.72rem;color:#4A6A84;
  margin-bottom:.35rem;
  min-width:0;
}
.mgr-avatar{
  width:20px;height:20px;border-radius:50%;
  background:""" + CAP_BLUE + r""";color:#fff;
  font-size:.55rem;font-weight:700;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  letter-spacing:0;
}
.card-actions{display:flex;flex-direction:column;gap:.3rem;margin-top:.1rem}
.card-pending{
  font-size:.68rem;color:#AAC0D0;
  background:#F4F7FB;border:1.5px dashed #D0DCE8;
  border-radius:.3rem;padding:.25rem .5rem;
  text-align:center;
}

/* Card state coloring */
.stage-needs-clarification{background:#FEFBF3;border-color:#EDD080}
.stage-validated{background:#F3FCF7;border-color:#9ED5B2}
.stage-rejected{background:#FEF5F5;border-color:#ECAAAA}
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

/* ─── Detail panel ───────────────────────────────────────────────── */
.detail-panel{display:none}/* replaced by popup */

/* ─── Detail popup overlay ─────────────────────────────────────── */
.detail-overlay{
  display:none;position:fixed;inset:0;
  background:rgba(8,18,38,.52);
  backdrop-filter:blur(3px);
  z-index:900;align-items:flex-start;justify-content:flex-end;
  padding:calc(3.1rem + .75rem) 1.5rem 1.5rem;
  box-sizing:border-box;
}
.detail-overlay.open{display:flex}
.detail-popup{
  background:#fff;
  border:1px solid rgba(0,0,0,.09);
  border-radius:.7rem;
  box-shadow:0 8px 40px rgba(8,18,38,.22);
  width:min(500px,94vw);
  max-height:calc(100vh - 3.1rem - 2rem);
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

/* ─── ROI summary bar ────────────────────────────────────── */
.roi-panel{border-bottom:1px solid #DDE5EF}
.roi-bar{
  display:flex;align-items:center;gap:0;
  padding:0 1.4rem;height:40px;flex-wrap:nowrap;
}
.roi-bar-label{
  font-size:.62rem;font-weight:700;letter-spacing:.07em;
  text-transform:uppercase;color:#5A7A96;
  white-space:nowrap;flex-shrink:0;
  padding-right:.9rem;border-right:1px solid #DDE5EF;margin-right:1rem;
}
.roi-bar-metrics{display:flex;align-items:center;gap:0;flex:1;min-width:0}
.roi-bar-metric{
  display:flex;align-items:baseline;gap:.25rem;
  padding:0 .85rem;border-right:1px solid #DDE5EF;white-space:nowrap;
}
.roi-bar-metric:first-child{padding-left:0}
.roi-bar-metric:last-child{border-right:none}
.roi-bar-val{font-size:.9rem;font-weight:700;letter-spacing:-.02em;color:#0E1E38}
.roi-bar-lbl{font-size:.62rem;color:#7A96B0;white-space:nowrap}
.roi-bar-scenarios{display:flex;align-items:center;gap:.25rem;margin-left:auto;padding-left:1rem;flex-shrink:0}
.roi-bar-scen{
  padding:.15rem .5rem;border-radius:9999px;
  font-size:.62rem;font-weight:600;cursor:pointer;
  border:1px solid #C8D4E0;background:transparent;color:#607A96;
  transition:all .13s;letter-spacing:.01em;
}
.roi-bar-scen.active{background:#0E1E38;border-color:#0E1E38;color:#fff}
.roi-bar-scen:hover:not(.active){background:#F0F4FA}
.roi-expand-btn{
  font-size:.62rem;font-weight:600;color:#5A7A96;
  background:none;border:1px solid #DDE5EF;
  border-radius:.3rem;padding:.15rem .5rem;
  cursor:pointer;white-space:nowrap;flex-shrink:0;
  margin-left:.5rem;transition:all .12s;
}
.roi-expand-btn:hover{background:#F0F4FA;color:#1E3450}
.roi-body{
  padding:.8rem 1.4rem .9rem;
  border-top:1px solid #DDE5EF;
  background:#FAFCFE;
}
.roi-body.collapsed{display:none}
.roi-assumptions{
  display:grid;grid-template-columns:repeat(5,1fr);
  gap:.55rem;margin-bottom:.75rem;
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
  .pipeline{grid-template-columns:repeat(7,minmax(170px,1fr))}
}

/* Medium — below 1200px */
@media(max-width:1199px){
  .combined-panel{margin-top:1rem}
  .board-section{margin-top:1rem}
  .kpi-row{grid-template-columns:repeat(2,1fr)}
}

/* Tablet — below 900px */
@media(max-width:899px){
  .page{padding:1.25rem 1.25rem 4rem}
  .kpi-row{grid-template-columns:repeat(2,1fr)}
  .pipeline{grid-template-columns:repeat(7,minmax(150px,1fr));min-width:1050px}
}

/* Small — below 600px */
@media(max-width:599px){
  .topbar{padding:.6rem 1rem}
  .topbar-title{display:none}
  .page{padding:1rem 1rem 4rem}
  .kpi-row{grid-template-columns:repeat(2,1fr);gap:.65rem}
  .kpi-value{font-size:1.75rem}
  .intake-form{flex-direction:column}
  .drop-zone{min-width:0}
  .board-scroll{margin:0 -1rem;padding:0 1rem .75rem}
  .pipeline{grid-template-columns:repeat(7,minmax(138px,1fr));min-width:966px}
  .detail-name{font-size:.95rem}
}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <span class="topbar-brand">Contoso</span>
    <span class="topbar-sep">·</span>
    <span class="topbar-title">Outcome Readiness Review &mdash; Agent Value Attribution Pipeline</span>
  </div>
  <div class="topbar-right">
    <span class="demo-badge">Demo</span>
    <span>%%GENERATED%%</span>
    <a href="/">&#8635; Refresh</a>
  </div>
</div>

<div class="topbar-model">
  <div class="tm-pill"><span class="tm-role">Framework</span><span class="tm-sep">/</span><span class="tm-name">Agent Value Attribution</span></div>
  <div class="tm-pill"><span class="tm-role">Ledger</span><span class="tm-sep">/</span><span class="tm-name">Agent Value Ledger</span></div>
  <div class="tm-pill"><span class="tm-role">Metric</span><span class="tm-sep">/</span><span class="tm-name">Indicative ROI</span></div>
  <div class="tm-pill"><span class="tm-role">Model</span><span class="tm-sep">/</span><span class="tm-name">Economic Impact</span></div>
</div>

<div class="page">

<div class="combined-panel">

<div class="left-col">

<div class="kpi-row">
  <div class="kpi-tile" style="--kpi-accent:%%BLUE%%">
    <div class="kpi-label">Engagements in scope</div>
    <div class="kpi-value">%%TOTAL_OPPS%%</div>
    <div class="kpi-sub">Unique SoWs assessed</div>
  </div>
  <div class="kpi-tile" style="--kpi-accent:%%COVERAGE_COLOR%%">
    <div class="kpi-label">Validated coverage</div>
    <div class="kpi-value" style="color:%%COVERAGE_COLOR%%">%%COVERAGE_PCT%%%</div>
    <div class="kpi-sub">%%VALIDATED_CNT%% of %%TOTAL_OPPS%% with confirmed verdict</div>
  </div>
  <div class="kpi-tile" style="--kpi-accent:#1E9160">
    <div class="kpi-label">Attributed Value</div>
    <div class="kpi-value" style="color:#1E9160">%%TOTAL_HOURS%%&thinsp;h</div>
    <div class="kpi-sub">Across %%TOTAL_RUNS%% agent runs</div>
  </div>
  </div>
</div>

<!-- ─── Outcome verdict strip ────────────────────────── -->
<div class="outcome-strip">
  <span class="outcome-strip-label">Commercial Outcome Readiness</span>
  <div class="outcome-strip-verdicts">
    <div class="osv osv-recommend">
      <span class="osv-icon">&#10003;</span>
      <span class="osv-count">%%N_RECOMMEND%%</span>
      <span class="osv-label">Recommend</span>
    </div>
    <div class="osv osv-reconsider">
      <span class="osv-icon">&#9680;</span>
      <span class="osv-count">%%N_RECONSIDER%%</span>
      <span class="osv-label">Reconsider</span>
    </div>
    <div class="osv osv-ruleout">
      <span class="osv-icon">&times;</span>
      <span class="osv-count">%%N_RULE_OUT%%</span>
      <span class="osv-label">Rule Out</span>
    </div>
  </div>
  <div class="outcome-strip-bar">
    <div class="osb-seg osb-recommend" style="flex:%%N_RECOMMEND%%"></div>
    <div class="osb-seg osb-reconsider" style="flex:%%N_RECONSIDER%%"></div>
    <div class="osb-seg osb-ruleout" style="flex:%%N_RULE_OUT%%"></div>
  </div>
</div>

<div class="roi-panel">
  <div class="roi-bar">
    <span class="roi-bar-label">Indicative ROI</span>
    <div class="roi-bar-metrics" id="roi-bar-metrics"></div>
    <div class="roi-bar-scenarios">
      <button class="roi-bar-scen" id="scen-conservative" onclick="applyScenario('conservative')">Conservative</button>
      <button class="roi-bar-scen active" id="scen-expected" onclick="applyScenario('expected')">Expected</button>
      <button class="roi-bar-scen" id="scen-upside" onclick="applyScenario('upside')">Upside</button>
    </div>
    <button class="roi-expand-btn" onclick="toggleRoi()" id="roi-expand-btn">&#9660;&ensp;Assumptions</button>
  </div>
  <div class="roi-body collapsed" id="roi-body">
    <div class="roi-assumptions">
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
    <div class="roi-results" id="roi-results"></div>
  </div>
</div>

<div class="intake-panel">
  <span class="intake-label">Submit a SoW</span>
  <div class="intake-field">
    <input type="text" id="opp-id" placeholder="Opportunity ID" style="width:140px"/>
  </div>
  <div class="intake-field">
    <input type="text" id="eng-name" placeholder="Engagement name" style="width:180px"/>
  </div>
  <div class="drop-zone" id="drop-zone" onclick="document.getElementById('file-input').click()">
    <input type="file" id="file-input" accept=".pdf,.docx,.doc,.txt" onchange="onFileChosen(this)"/>
    <span id="drop-label">&#128196;&ensp;Drop or browse PDF / DOCX / TXT</span>
  </div>
  <button class="btn-scan" id="upload-btn" onclick="submitUpload()" disabled>Run AI Review &rarr;</button>
  <div class="intake-status" id="upload-status"></div>
</div>

</div><!-- /left-col -->

</div><!-- /combined-panel -->

<!-- ─── Detail popup overlay ───────────────────────────────── -->
<div class="detail-overlay" id="detail-overlay" onclick="closeDetail(event)">
  <div class="detail-popup" id="detail-popup" onclick="event.stopPropagation()">
    <div class="detail-popup-close"><button onclick="closeDetail()">&times;</button></div>
    <div id="detail-content" style="display:flex;flex:1;flex-direction:column"></div>
  </div>
</div>

<div class="board-section">
  <div class="section-header">
    <span class="section-title">Agent Value Attribution Pipeline</span>
    <span style="font-size:.72rem;color:#AAC0CC">Click any card to open the detail view &rarr;</span>
  </div>
  <div class="board-scroll">
    <div class="pipeline">%%BOARD_HTML%%</div>
  </div>
</div>

<p class="footer">
  Agent Value Ledger stored in <code>runs.db</code> &nbsp;&middot;&nbsp;
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
      <button class="btn-send" onclick="simulateSend()">&#9993;&ensp;Send to Engagement Manager</button>
      <button class="btn-modal-ghost" onclick="closeModal()">Close</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

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
  rule_out:   {bg:'#FDECEA',color:'#8C1818',border:'#ECA8A8',icon:'✕',label:'Rule Out'},
};
let activeOpp = null;

// ─── Lane interaction model ──────────────────────────────────────────────────
// behavior:
//   'direct'       – move card immediately, no agent, no confirm
//   'confirm'      – ask user to confirm, no agent call
//   'agent-scan'   – HITL confirm → call /scan endpoint → simulated processing
//   'agent-review' – HITL confirm → call /advance to under_review → simulated review
//   'blocked'      – cannot drop here
const LANE_CONFIG = {
  intake:              { behavior:'direct',       accepts: ['needs_clarification','rejected'] },
  scanned:             { behavior:'agent-scan',   accepts: ['intake','under_review','needs_clarification'] },
  under_review:        { behavior:'agent-review', accepts: ['scanned','needs_clarification'] },
  needs_clarification: { behavior:'direct',       accepts: ['under_review','scanned'] },
  validated:           { behavior:'confirm',      accepts: ['under_review','scanned'] },
  rejected:            { behavior:'confirm',      accepts: ['under_review','scanned','needs_clarification'] },
  archived:            { behavior:'direct',       accepts: ['validated','rejected'] },
};

const AGENT_INFO = {
  'agent-scan': {
    icon: '🔍',
    title: 'Authorise Scan Agent',
    subtitle: 'The Scan Agent will read the SoW and return a structured verdict.',
    desc: (engName) => `The SoW for <strong>${engName}</strong> will be submitted to the Scan Agent for automated outcome-readiness analysis. This will take approximately 30–60 seconds.`,
    steps: [
      'Parse and index the Statement of Work',
      'Identify measurable outcomes and KPIs',
      'Assess commercial model suitability',
      'Return a structured recommendation verdict',
    ],
    confirmLabel: '🔍  Run Scan Agent',
    processingLabel: 'Scanning SoW…',
    processingSteps: ['Reading SoW…','Identifying outcomes…','Assessing KPIs…','Generating verdict…'],
    resultLabel: 'Assessment ready',
  },
  'agent-review': {
    icon: '📋',
    title: 'Authorise Review Agent',
    subtitle: 'The Review Agent will perform a deep commercial analysis.',
    desc: (engName) => `The engagement <strong>${engName}</strong> will be moved to Analyst Review and the AI Review Agent will conduct a detailed commercial assessment.`,
    steps: [
      'Review prior scan verdict and evidence',
      'Assess commercial model viability in depth',
      'Evaluate KPI measurability and baseline availability',
      'Produce a reviewed recommendation and next-action plan',
    ],
    confirmLabel: '📋  Start Review Agent',
    processingLabel: 'Reviewing engagement…',
    processingSteps: ['Loading scan results…','Assessing commercial model…','Evaluating KPI gaps…','Writing recommendation…'],
    resultLabel: 'Review ready',
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
  dragState = { opp: card.dataset.opp, fromLane: card.dataset.stage, card };
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
  // Move ghost
  if (dragState.ghostEl) {
    dragState.ghostEl.style.left = (e.clientX - 10) + 'px';
    dragState.ghostEl.style.top  = (e.clientY - 14) + 'px';
  }
  // Highlight target lane
  const targetLane = e.target.closest('[data-lane]');
  document.querySelectorAll('.lane').forEach(l => {
    l.classList.remove('drop-target','drop-blocked');
  });
  if (targetLane) {
    const laneName = targetLane.dataset.lane;
    if (laneName === dragState.fromLane) return;
    const cfg = LANE_CONFIG[laneName];
    const lane = targetLane.closest('.lane') || targetLane;
    if (cfg && cfg.accepts.includes(dragState.fromLane)) {
      lane.classList.add('drop-target');
      e.dataTransfer.dropEffect = 'move';
    } else {
      lane.classList.add('drop-blocked');
      e.dataTransfer.dropEffect = 'none';
    }
  }
});

document.addEventListener('dragleave', e => {
  // Only clear if we've left the pipeline entirely
  const related = e.relatedTarget;
  if (!related || !related.closest('.pipeline')) {
    document.querySelectorAll('.lane').forEach(l => l.classList.remove('drop-target','drop-blocked'));
  }
});

document.addEventListener('dragend', e => {
  if (!dragState) return;
  dragState.card.classList.remove('dragging');
  if (dragState.ghostEl) dragState.ghostEl.remove();
  document.querySelectorAll('.lane').forEach(l => l.classList.remove('drop-target','drop-blocked'));
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
  intake:'Intake', scanned:'AI Assessment', under_review:'Analyst Review',
  needs_clarification:'Clarification Required', validated:'Approved',
  rejected:'Ruled Out', archived:'Archived',
};

function handleDrop(opp, fromLane, toLane, behavior) {
  const d = DETAILS[opp] || {};
  const engName = d.engagement_name || opp;
  if (behavior === 'direct') {
    doAdvance(opp, toLane, null);
  } else if (behavior === 'agent-scan' || behavior === 'agent-review' || behavior === 'confirm') {
    openHitl(opp, fromLane, toLane, behavior, engName);
  }
}

// ─── HITL Modal ──────────────────────────────────────────────────────────────
let hitlPending = null;

function openHitl(opp, fromLane, toLane, behavior, engName) {
  hitlPending = { opp, fromLane, toLane, behavior };
  const info = behavior === 'confirm'
    ? { ...AGENT_INFO.confirm,
        desc: () => AGENT_INFO.confirm.desc(engName, LANE_LABELS[toLane]),
        steps: AGENT_INFO.confirm.steps }
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

// ─── Execute approved action ─────────────────────────────────────────────────
function executeApprovedAction(opp, fromLane, toLane, behavior) {
  if (behavior === 'confirm') {
    doAdvance(opp, toLane, null);
    return;
  }
  if (behavior === 'agent-scan') {
    // Move to scanned first (so card appears in lane), then simulate agent
    doAdvance(opp, 'scanned', null, /*silent*/ true);
    // Check if there's SoW text
    const card = document.getElementById('card-' + opp);
    const hasSow = card && card.dataset.hasSow === '1';
    if (hasSow) {
      startAgentProcessing(opp, 'agent-scan', () => {
        doScanCall(opp);
      });
    } else {
      startAgentProcessing(opp, 'agent-scan', null, /*simulate*/true);
    }
  } else if (behavior === 'agent-review') {
    doAdvance(opp, 'under_review', null, /*silent*/ true);
    startAgentProcessing(opp, 'agent-review', null, /*simulate*/true);
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
    .then(() => onAgentComplete(opp, 'agent-scan', false))
    .catch(err => {
      // Fall back to simulation completion
      console.warn('Scan call failed, simulating:', err);
      onAgentComplete(opp, 'agent-scan', true);
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
  if (!oppId)      { setStatus('Please enter an Opportunity ID.', 'error'); return; }
  if (!engName)    { setStatus('Please enter an Engagement name.', 'error'); return; }
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

// ─── Board button actions (kept for backwards compat with card buttons) ──────
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

// ─── Detail panel ─────────────────────────────────────────────────────────────
function openDetail(opp) {
  activeOpp = opp;
  const d = DETAILS[opp]; if (!d) return;
  document.querySelectorAll('.eng-card').forEach(c=>c.classList.remove('selected'));
  const card = document.getElementById('card-'+opp); if(card) card.classList.add('selected');
  const dc = document.getElementById('detail-content');
  dc.style.display = 'flex';

  const cfg = REC_CFG[d.recommendation] || {bg:'#EEF2F8',color:'#607A96',border:'#C8D4E0',icon:'·',label:d.rec_label||'—'};
  const mgr = d.manager || {};
  const ini = mgr.name ? mgr.name.split(' ').filter(Boolean).map(p=>p[0]).join('').slice(0,2).toUpperCase() : '??';

  const outHtml = (d.detected_outcomes && d.detected_outcomes.length)
    ? d.detected_outcomes.map(o=>`<div class="detail-list-item">${o}</div>`).join('')
    : '<div style="font-size:.78rem;color:#AABFCC;padding:.2rem 0">None detected</div>';

  const kpiHtml = (d.missing_kpis && d.missing_kpis.length)
    ? d.missing_kpis.map(k=>`<div class="detail-kpi-item">${k}</div>`).join('')
    : '<div style="font-size:.78rem;color:#1E9160;padding:.2rem 0">No gaps identified ✓</div>';

  const histHtml = (d.run_history && d.run_history.length) ? d.run_history.map(r=>{
    const rc = REC_CFG[r.recommendation]||{};
    const badge = r.recommendation?`<span style="background:${rc.bg||'#eee'};color:${rc.color||'#666'};border:1px solid ${rc.border||'#ccc'};padding:.06rem .35rem;border-radius:.25rem;font-size:.64rem;font-weight:700">${rc.icon||'·'} ${rc.label||r.recommendation}</span>`:'';
    const ts = r.created_at?r.created_at.slice(0,16).replace('T',' '):'';
    const hrs = r.hours_saved?`<span style="font-size:.68rem;color:#8BAABF;font-variant-numeric:tabular-nums">${r.hours_saved.toFixed(1)} h attributed</span>`:'';
    return `<div class="run-history-item">${badge}<span style="font-size:.64rem;color:#AABFCC">${r.agent_name||''}</span><span style="flex:1"></span>${hrs}<span class="run-ts">${ts}</span></div>`;
  }).join('') : '<div style="font-size:.74rem;color:#AABFCC">No run history</div>';

  dc.innerHTML = `
    <div class="detail-top">
      <div class="detail-opp">${d.opportunity_id}</div>
      <div class="detail-name">${d.engagement_name}</div>
      <div class="detail-verdict-row">
        <span class="detail-verdict-badge" style="background:${cfg.bg};color:${cfg.color};border:1.5px solid ${cfg.border}">${cfg.icon}&ensp;${cfg.label}</span>
        <span class="detail-hours-badge">&#9203;&ensp;${(d.hours_saved||0).toFixed(1)}&thinsp;h Attributed Value</span>
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
        <div class="ds-label">Recommended Commercial Direction</div>
        <div style="font-size:.71rem;color:#AABFCC;margin-bottom:.3rem">Based on outcome readiness assessment &mdash; feeds into Agent Value Attribution</div>
        <div class="detail-direction">${d.commercial_direction}</div>
      </div>
      <div class="ds">
        <div class="ds-label">Next Action</div>
        <div class="detail-action-box">${d.next_action}</div>
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
        <button class="btn-activate" onclick="openModal('${opp}')">&#9993;&ensp;Send Instructions to ${(mgr.name||'').split(' ')[0]||'Manager'}</button>
      </div>
      <div class="ds">
        <div class="ds-label">Agent Value Ledger</div>
        <div style="font-size:.72rem;color:#AAC0CC;margin-bottom:.4rem">Attributed Value entries recorded for this engagement</div>
        ${histHtml}
      </div>
    </div>`;

  document.getElementById('detail-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

// ─── Activation modal ────────────────────────────────────────────────────────
function openModal(opp) {
  const d = DETAILS[opp]; if (!d) return;
  const mgr = d.manager || {};
  const cfg = REC_CFG[d.recommendation] || {};
  document.getElementById('modal-title').textContent = `Instruction Package \u00b7 ${mgr.name||'Engagement Manager'}`;
  document.getElementById('modal-subtitle').textContent = `${d.engagement_name} \u00b7 ${d.opportunity_id}`;
  const kpiList = (d.missing_kpis && d.missing_kpis.length)
    ? '<ul>'+d.missing_kpis.map(k=>`<li>${k}</li>`).join('')+'</ul>'
    : '<p>No KPI gaps identified — the SoW has sufficient measurement detail.</p>';
  const outList = (d.detected_outcomes && d.detected_outcomes.length)
    ? '<ul>'+d.detected_outcomes.map(o=>`<li>${o}</li>`).join('')+'</ul>'
    : '<p>No specific outcomes were detected.</p>';
  const isActionable = d.recommendation==='reconsider'||d.recommendation==='recommend';
  document.getElementById('modal-body').innerHTML = `
    <div class="modal-section">
      <div class="modal-section-title">Agent Value Attribution &mdash; assessment summary</div>
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
          <li>Engage Contoso's commercial team to model the outcome-linked fee structure</li>
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
  document.querySelectorAll('.roi-bar-scen').forEach(b => b.classList.remove('active'));
  document.getElementById('scen-'+name).classList.add('active');
  updateRoi();
}

function roiFmt(n, prefix='\u20ac') {
  if (Math.abs(n) >= 1000000) return prefix + (n/1000000).toFixed(1)+'M';
  if (Math.abs(n) >= 1000)    return prefix + (n/1000).toFixed(1)+'k';
  return prefix + Math.round(n).toLocaleString();
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

  document.getElementById('roi-results').innerHTML = metrics.map(m => `
    <div class="roi-metric" style="--roi-accent:${m.accent}">
      <div class="roi-metric-label">${m.label}</div>
      <div class="roi-metric-value" style="color:${m.accent}">${m.value}</div>
      <div class="roi-metric-sub">${m.sub}</div>
    </div>`).join('');

  // Populate the always-visible summary bar
  const barEl = document.getElementById('roi-bar-metrics');
  if (barEl) barEl.innerHTML =
    `<div class="roi-bar-metric"><span class="roi-bar-val">${roiFmt(grossHourValue)}</span><span class="roi-bar-lbl">Gross value/yr</span></div>` +
    `<div class="roi-bar-metric"><span class="roi-bar-val" style="color:${netColor}">${roiFmt(netValue12m)}</span><span class="roi-bar-lbl">Net (12 mo)</span></div>` +
    `<div class="roi-bar-metric" style="border-right:none"><span class="roi-bar-val" style="color:${roiColor}">${roi.toFixed(0)}%</span><span class="roi-bar-lbl">ROI</span></div>`;
}

function closeDetail(e) {
  if (e && e.target !== document.getElementById('detail-overlay')) return;
  document.getElementById('detail-overlay').classList.remove('open');
  document.body.style.overflow = '';
  document.querySelectorAll('.eng-card').forEach(c=>c.classList.remove('selected'));
  activeOpp = null;
}

function toggleRoi() {
  const body = document.getElementById('roi-body');
  const btn  = document.getElementById('roi-expand-btn');
  const collapsed = body.classList.toggle('collapsed');
  btn.innerHTML = collapsed ? '&#9660;&ensp;Assumptions' : '&#9650;&ensp;Assumptions';
  if (!collapsed) updateRoi();
}

// ─── Toast ───────────────────────────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById('toast'); t.textContent = msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),3500);
}

// ─── Init ────────────────────────────────────────────────────────────────────
applyScenario('expected');
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
