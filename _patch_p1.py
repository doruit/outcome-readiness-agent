import sys

with open("dashboard.py", "r") as f:
    src = f.read()

# ─── PHASE 1: ROI bar — elevate ROI% + Payback as large KPI anchors ──────────
# 1a. Replace the roi-bar CSS (.roi-bar-metric etc.) with new anchor styles
OLD_ROI_CSS = """.roi-bar-metrics{display:flex;align-items:center;gap:0;flex:1;min-width:0}
.roi-bar-metric{
  display:flex;align-items:baseline;gap:.25rem;
  padding:0 .85rem;border-right:1px solid #DDE5EF;white-space:nowrap;
}
.roi-bar-metric:first-child{padding-left:0}
.roi-bar-metric:last-child{border-right:none}
.roi-bar-val{font-size:.9rem;font-weight:700;letter-spacing:-.02em;color:#0E1E38}
.roi-bar-lbl{font-size:.62rem;color:#7A96B0;white-space:nowrap}"""

NEW_ROI_CSS = """.roi-bar-metrics{display:flex;align-items:center;gap:0;flex:1;min-width:0}
/* Legacy small metrics (hidden, kept for compat) */
.roi-bar-metric{display:none}
.roi-bar-val{font-size:.9rem;font-weight:700;letter-spacing:-.02em;color:#0E1E38}
.roi-bar-lbl{font-size:.62rem;color:#7A96B0;white-space:nowrap}
/* Primary KPI anchors */
.roi-anchor{
  display:flex;flex-direction:column;justify-content:center;
  padding:0 1.1rem;border-right:1px solid #DDE5EF;
  min-width:0;flex-shrink:0;
}
.roi-anchor:first-child{padding-left:0}
.roi-anchor-val{
  font-size:1.35rem;font-weight:800;letter-spacing:-.04em;line-height:1.05;
  color:#0E1E38;
}
.roi-anchor-lbl{font-size:.6rem;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:#7A96B0;margin-top:.06rem}
/* Details trigger */
.roi-detail-trigger{
  position:relative;display:flex;align-items:center;margin-left:.6rem;flex-shrink:0;
}
.roi-detail-btn{
  font-size:.61rem;font-weight:600;color:#5A7A96;cursor:pointer;
  background:none;border:1px solid #DDE5EF;border-radius:.25rem;
  padding:.15rem .45rem;white-space:nowrap;transition:all .12s;
  display:flex;align-items:center;gap:.2rem;
}
.roi-detail-btn:hover{background:#F0F4FA;color:#1E3450}
.roi-detail-popover{
  display:none;position:absolute;top:calc(100% + 6px);left:0;
  background:#fff;border:1px solid #DDE5EF;border-radius:.5rem;
  box-shadow:0 8px 24px rgba(14,30,56,.14);
  padding:.7rem .8rem;z-index:200;min-width:240px;
  grid-template-columns:1fr 1fr 1fr;gap:.5rem;
}
.roi-detail-trigger:hover .roi-detail-popover,
.roi-detail-trigger:focus-within .roi-detail-popover{display:grid}
.roi-popover-metric{display:flex;flex-direction:column;gap:.1rem}
.roi-popover-label{font-size:.6rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#3A5470}
.roi-popover-val{font-size:.88rem;font-weight:700;color:#0E1E38;letter-spacing:-.02em}
.roi-popover-sub{font-size:.62rem;color:#6A8AA4;line-height:1.3}"""

if OLD_ROI_CSS not in src:
    print("ERROR: OLD_ROI_CSS not found"); sys.exit(1)
src = src.replace(OLD_ROI_CSS, NEW_ROI_CSS, 1)

# 1b. Widen roi-bar height slightly for anchors
OLD_ROI_BAR_H = """.roi-bar{
  display:flex;align-items:center;gap:0;
  padding:0 1.4rem;height:40px;flex-wrap:nowrap;
}"""
NEW_ROI_BAR_H = """.roi-bar{
  display:flex;align-items:center;gap:0;
  padding:0 1.4rem;height:52px;flex-wrap:nowrap;
}"""
if OLD_ROI_BAR_H not in src:
    print("ERROR: OLD_ROI_BAR_H not found"); sys.exit(1)
src = src.replace(OLD_ROI_BAR_H, NEW_ROI_BAR_H, 1)

# 1c. Replace HTML roi-bar inner content
OLD_ROI_BAR_HTML = """  <div class="roi-bar">
    <span class="roi-bar-label">Indicative ROI</span>
    <div class="roi-bar-metrics" id="roi-bar-metrics"></div>
    <div class="roi-bar-scenarios">
      <button class="roi-bar-scen" id="scen-conservative" onclick="applyScenario('conservative')">Conservative</button>
      <button class="roi-bar-scen active" id="scen-expected" onclick="applyScenario('expected')">Expected</button>
      <button class="roi-bar-scen" id="scen-upside" onclick="applyScenario('upside')">Upside</button>
    </div>
    <button class="roi-expand-btn" onclick="toggleRoi()" id="roi-expand-btn">&#9660;&ensp;Assumptions</button>
  </div>"""

NEW_ROI_BAR_HTML = """  <div class="roi-bar">
    <span class="roi-bar-label">Indicative ROI</span>
    <div class="roi-bar-metrics" id="roi-bar-metrics">
      <div class="roi-anchor" id="roi-anchor-roi">
        <div class="roi-anchor-val" id="roi-anchor-val-roi">—</div>
        <div class="roi-anchor-lbl">ROI</div>
      </div>
      <div class="roi-anchor" id="roi-anchor-payback" style="border-right:none">
        <div class="roi-anchor-val" id="roi-anchor-val-payback">—</div>
        <div class="roi-anchor-lbl">Payback</div>
      </div>
      <div class="roi-detail-trigger" tabindex="0">
        <button class="roi-detail-btn">Details &#9662;</button>
        <div class="roi-detail-popover" id="roi-detail-popover">
          <div class="roi-popover-metric">
            <span class="roi-popover-label">Gross value/yr</span>
            <span class="roi-popover-val" id="pop-gross">—</span>
            <span class="roi-popover-sub" id="pop-gross-sub"></span>
          </div>
          <div class="roi-popover-metric">
            <span class="roi-popover-label">Net (12 mo)</span>
            <span class="roi-popover-val" id="pop-net">—</span>
            <span class="roi-popover-sub" id="pop-net-sub">Gross minus total cost</span>
          </div>
          <div class="roi-popover-metric">
            <span class="roi-popover-label">Annual OpEx</span>
            <span class="roi-popover-val" id="pop-opex">—</span>
            <span class="roi-popover-sub" id="pop-opex-sub">Monthly &#215; 12</span>
          </div>
        </div>
      </div>
    </div>
    <div class="roi-bar-scenarios">
      <button class="roi-bar-scen" id="scen-conservative" onclick="applyScenario('conservative')">Conservative</button>
      <button class="roi-bar-scen active" id="scen-expected" onclick="applyScenario('expected')">Expected</button>
      <button class="roi-bar-scen" id="scen-upside" onclick="applyScenario('upside')">Upside</button>
    </div>
    <button class="roi-expand-btn" onclick="toggleRoi()" id="roi-expand-btn">&#9660;&ensp;Assumptions</button>
  </div>"""

if OLD_ROI_BAR_HTML not in src:
    print("ERROR: OLD_ROI_BAR_HTML not found"); sys.exit(1)
src = src.replace(OLD_ROI_BAR_HTML, NEW_ROI_BAR_HTML, 1)

# 1d. Replace the JS bar update section in updateRoi()
OLD_ROI_JS = """  // Populate the always-visible summary bar
  const barEl = document.getElementById('roi-bar-metrics');
  if (barEl) barEl.innerHTML =
    `<div class="roi-bar-metric"><span class="roi-bar-val">${roiFmt(grossHourValue)}</span><span class="roi-bar-lbl">Gross value/yr</span></div>` +
    `<div class="roi-bar-metric"><span class="roi-bar-val" style="color:${netColor}">${roiFmt(netValue12m)}</span><span class="roi-bar-lbl">Net (12 mo)</span></div>` +
    `<div class="roi-bar-metric" style="border-right:none"><span class="roi-bar-val" style="color:${roiColor}">${roi.toFixed(0)}%</span><span class="roi-bar-lbl">ROI</span></div>`;
}"""

NEW_ROI_JS = """  // Populate KPI anchors
  const setEl = (id, val) => { const e = document.getElementById(id); if(e) e.textContent = val; };
  const setStyle = (id, prop, val) => { const e = document.getElementById(id); if(e) e.style[prop] = val; };
  const paybackTxt = paybackMonths ? (paybackMonths <= 24 ? paybackMonths+'\u2009mo' : '>24\u2009mo') : '\u2014';
  setEl('roi-anchor-val-roi', roi.toFixed(0)+'%');
  setStyle('roi-anchor-val-roi', 'color', roiColor);
  setEl('roi-anchor-val-payback', paybackTxt);
  setStyle('roi-anchor-val-payback', 'color', '#6B42A8');
  // Popover secondary metrics
  setEl('pop-gross', roiFmt(grossHourValue));
  setEl('pop-gross-sub', annualHours+' h \u00d7 \u20ac'+rate+' \u00d7 '+Math.round(util*100)+'%');
  setEl('pop-net', roiFmt(netValue12m));
  setStyle('pop-net', 'color', netColor);
  setEl('pop-opex', roiFmt(annualOpex));
}"""

if OLD_ROI_JS not in src:
    print("ERROR: OLD_ROI_JS not found"); sys.exit(1)
src = src.replace(OLD_ROI_JS, NEW_ROI_JS, 1)

with open("dashboard.py", "w") as f:
    f.write(src)
print("Phase 1 patch applied OK")
