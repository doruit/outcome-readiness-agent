import sys

with open("dashboard.py", "r") as f:
    src = f.read()

errors = []

# ════════════════════════════════════════════════════════════════════════════
# PHASE 2: Compact Kanban cards
# ════════════════════════════════════════════════════════════════════════════

OLD_CARD_CSS = """.card-verdict-row{
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
}"""

NEW_CARD_CSS = """.card-verdict-row{
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
}"""

if OLD_CARD_CSS not in src:
    errors.append("ERROR: OLD_CARD_CSS not found")
else:
    src = src.replace(OLD_CARD_CSS, NEW_CARD_CSS, 1)
    print("2a card CSS OK")

# 2b. Python card_html() non-intake path
OLD_CARD_HTML_PY = """    rec_badge = ""
    if cfg:
        rec_badge = (f'<span class="badge-rec" style="background:{cfg["bg"]};color:{cfg["color"]};'
                     f'border:1px solid {cfg["border"]}">{cfg["icon"]} {cfg["label"]}</span>')

    return f\'\'\'<div class="eng-card stage-{stage.replace("_","-")}" draggable="true" onclick="openDetail(\'{opp}\')" id="card-{opp}" data-opp="{opp}" data-stage="{stage}">
  <div class="card-opp">{opp}</div>
  <div class="card-name">{name}</div>
  <div class="card-verdict-row">
    {rec_badge}
    <span class="card-hours">{hours:.1f} h ⏱</span>
  </div>
  {(\'<div class="card-summary">\'+summary_short+\'</div>\') if summary_short else ""}
  {\'<div class="card-kpi-gap">⚠ \' + str(kpi_count) + \' KPI gap\' + (\'s\' if kpi_count!=1 else \'\') + \'</div>\' if kpi_count else ""}
  <div class="card-mgr"><span class="mgr-avatar">{mgr_ini}</span>{mgr.get("name","")}</div>
  <div class="card-actions" onclick="event.stopPropagation()">{advance_btn}{extra_btn}</div>
</div>\'\'\'"""

NEW_CARD_HTML_PY = """    rec_badge = ""
    if cfg:
        rec_badge = (f'<span class="badge-rec" style="background:{cfg["bg"]};color:{cfg["color"]};'
                     f'border:1px solid {cfg["border"]}" title="{cfg["label"]}">{cfg["icon"]}</span>')

    return f\'\'\'<div class="eng-card stage-{stage.replace("_","-")}" draggable="true" onclick="openDetail(\'{opp}\')" id="card-{opp}" data-opp="{opp}" data-stage="{stage}">
  <span class="card-hours">{hours:.1f}\u202fh</span>
  <div class="card-opp">{opp}</div>
  <div class="card-name">{name}</div>
  {(\'<div class="card-summary">\'+summary_short+\'</div>\') if summary_short else ""}
  {\'<div class="card-kpi-gap">⚠ \' + str(kpi_count) + \' KPI gap\' + (\'s\' if kpi_count!=1 else \'\') + \'</div>\' if kpi_count else ""}
  <div class="card-verdict-row">
    {rec_badge}
    <div class="card-mgr" style="margin-bottom:0"><span class="mgr-avatar">{mgr_ini}</span>{mgr.get("name","")}</div>
  </div>
  <div class="card-actions" onclick="event.stopPropagation()">{advance_btn}{extra_btn}</div>
</div>\'\'\'"""

if OLD_CARD_HTML_PY not in src:
    errors.append("ERROR: OLD_CARD_HTML_PY not found — trying simpler search")
    # Try to locate the block
    needle = '    rec_badge = ""\n    if cfg:'
    idx = src.find(needle)
    print(f"  needle idx={idx}")
    if idx > 0:
        print(repr(src[idx:idx+400]))
else:
    src = src.replace(OLD_CARD_HTML_PY, NEW_CARD_HTML_PY, 1)
    print("2b card_html() OK")

# ════════════════════════════════════════════════════════════════════════════
# PHASE 3
# ════════════════════════════════════════════════════════════════════════════

# 3a. Add intake-modal CSS
OLD_INTAKE_CSS_ANCHOR = ".drop-zone input[type=file]{display:none}"

NEW_INTAKE_CSS_ANCHOR = """.drop-zone input[type=file]{display:none}
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
.ghost-intake-card:hover{border-color:#0070AD;color:#0070AD;background:#EDF5FF}"""

if OLD_INTAKE_CSS_ANCHOR not in src:
    errors.append("ERROR: OLD_INTAKE_CSS_ANCHOR not found")
else:
    src = src.replace(OLD_INTAKE_CSS_ANCHOR, NEW_INTAKE_CSS_ANCHOR, 1)
    print("3a intake modal CSS OK")

# 3b. Remove the inline intake-panel HTML
# Find it dynamically
INTAKE_START = '<div class="intake-panel">'
INTAKE_END = '</div><!-- /left-col -->'
i_start = src.find(INTAKE_START)
i_end = src.find(INTAKE_END)
if i_start == -1 or i_end == -1 or i_start > i_end:
    errors.append(f"ERROR: intake-panel block not found (start={i_start}, end={i_end})")
else:
    src = src[:i_start] + src[i_end:]
    print("3b intake panel removed OK")

# 3c. Intake modal HTML — insert before board-section
BOARD_ANCHOR = '<div class="board-section">'
b_idx = src.find(BOARD_ANCHOR)
if b_idx == -1:
    errors.append("ERROR: board-section anchor not found")
else:
    MODAL_HTML = '''<!-- Intake modal -->
<div class="intake-modal-overlay" id="intake-modal-overlay" onclick="closeIntakeModal(event)">
  <div class="intake-modal" onclick="event.stopPropagation()">
    <div class="intake-modal-header">
      <div>
        <div class="intake-modal-title">Submit New Opportunity</div>
        <div class="intake-modal-sub">Upload a Statement of Work for AI review</div>
      </div>
      <button class="intake-modal-close" onclick="closeIntakeModal()">&times;</button>
    </div>
    <div class="intake-modal-fields">
      <div class="intake-modal-field">
        <input type="text" id="opp-id" placeholder="Opportunity ID (e.g. OPP-2025-042)"/>
      </div>
      <div class="intake-modal-field">
        <input type="text" id="eng-name" placeholder="Engagement name"/>
      </div>
    </div>
    <div class="intake-modal-dropzone" id="modal-drop-zone"
         onclick="document.getElementById(\'file-input\').click()"
         ondragover="event.preventDefault();this.classList.add(\'drag-over\')"
         ondragleave="this.classList.remove(\'drag-over\')"
         ondrop="handleModalDrop(event)">
      <input type="file" id="file-input" accept=".pdf,.docx,.doc,.txt" onchange="onFileChosen(this)"/>
      <span id="drop-label">&#128196;&ensp;Drop or click to browse PDF / DOCX / TXT</span>
    </div>
    <div class="intake-modal-actions">
      <div class="intake-status" id="upload-status" style="flex:1;font-size:.74rem;color:#5A7A96"></div>
      <button class="btn-modal-ghost" onclick="closeIntakeModal()">Cancel</button>
      <button class="btn-scan" id="upload-btn" onclick="submitUpload()" disabled>Run AI Review &rarr;</button>
    </div>
  </div>
</div>

'''
    src = src[:b_idx] + MODAL_HTML + src[b_idx:]
    print("3c intake modal HTML added OK")

# 3d. Ghost card in intake lane
OLD_BUILD_BOARD = '    c_html = "".join(card_html(c) for c in cards) or \'<div class="lane-empty">No engagements</div>\'\n        parts.append(f\'\'\'<div class="lane lane-{key.replace("_","-")}" style="--lane-color:{color}" data-lane="{key}">'

NEW_BUILD_BOARD = '''    ghost = \'<div class="ghost-intake-card" onclick="openIntakeModal()">&#43; Submit New Opportunity</div>\' if key == "intake" else ""
        c_html = ghost + ("".join(card_html(c) for c in cards) or \'<div class="lane-empty">No engagements</div>\')
        parts.append(f\'\'\'<div class="lane lane-{key.replace("_","-")}" style="--lane-color:{color}" data-lane="{key}">'''

if OLD_BUILD_BOARD not in src:
    errors.append("ERROR: OLD_BUILD_BOARD not found — trying fallback")
    idx2 = src.find('c_html = "".join(card_html(c) for c in cards)')
    print(f"  fallback idx={idx2}")
    if idx2 > 0:
        print(repr(src[idx2:idx2+200]))
else:
    src = src.replace(OLD_BUILD_BOARD, NEW_BUILD_BOARD, 1)
    print("3d ghost card in lane OK")

# 3e. Add modal JS functions after closeDetail
OLD_JS = """function closeDetail(e) {
  if (e && e.target !== document.getElementById('detail-overlay')) return;
  document.getElementById('detail-overlay').classList.remove('open');
  document.body.style.overflow = '';
  document.querySelectorAll('.eng-card').forEach(c=>c.classList.remove('selected'));
  activeOpp = null;
}"""

NEW_JS = """function closeDetail(e) {
  if (e && e.target !== document.getElementById('detail-overlay')) return;
  document.getElementById('detail-overlay').classList.remove('open');
  document.body.style.overflow = '';
  document.querySelectorAll('.eng-card').forEach(c=>c.classList.remove('selected'));
  activeOpp = null;
}

function openIntakeModal() {
  document.getElementById('intake-modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  setTimeout(()=>document.getElementById('opp-id').focus(), 100);
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
    document.getElementById('drop-label').textContent = '\\uD83D\\uDCC4\\u2002' + dt.files[0].name;
  }
}"""

if OLD_JS not in src:
    errors.append("ERROR: OLD_JS_CLOSE_DETAIL not found")
else:
    src = src.replace(OLD_JS, NEW_JS, 1)
    print("3e intake modal JS OK")

# Report
if errors:
    for e in errors:
        print(e)
    sys.exit(1)

with open("dashboard.py", "w") as f:
    f.write(src)
print("\nAll Phase 2+3 patches applied OK")
