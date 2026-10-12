# -*- coding: utf-8 -*-
"""สร้าง site_kit/ukm.js (+ CSS ฝังใน JS) จากต้นแบบ ui_lab (ui.css / ui.js / index.html)
ukm = โมดูล ui_lab ที่ฝังในหน้าเว็บเดิมผ่าน Shadow DOM (สไตล์ไม่ชนกับหน้าเดิม) รัน: python build_ukm.py"""
import os, re, json
D = os.path.dirname(os.path.abspath(__file__))
R = lambda n: open(os.path.join(D, n), encoding='utf8').read()

# ---------- CSS ----------
css = re.sub(r'/\*.*?\*/', '', R('ui.css'), flags=re.S)
def top_blocks(s):
    out, i, n = [], 0, len(s)
    while i < n:
        j = s.find('{', i)
        if j < 0: out.append(('', s[i:].strip(), False)); break
        sel = s[i:j].strip(); depth, k = 1, j + 1
        while k < n and depth: depth += (s[k] == '{') - (s[k] == '}'); k += 1
        out.append((sel, s[j + 1:k - 1], True)); i = k
    return out
DROP = {'body', 'html', ':root', '[data-mode="dark"]', 'html{scroll-behavior:smooth}'}
kept = []
for sel, body, ok in top_blocks(css):
    if not ok or sel in DROP: continue
    if sel.startswith('@media'):
        inner = ''.join(f'{s2}{{{b2}}}' for s2, b2, ok2 in top_blocks(body) if ok2)
        body = inner
    kept.append((sel, body))
def fixsel(s):
    s = s.replace('[data-mode="dark"] ', ':host([data-mode="dark"]) ').replace('html[data-motion="reduce"]', ':host([data-motion="reduce"])')
    s = s.replace('.js .rv', '.rv').replace('.is-loading [data-sk]', ':host(.is-loading) [data-sk]')
    return s
out = []
for sel, body in kept:
    if sel.startswith('@media'): body = ''.join(f'{fixsel(s2)}{{{b2}}}' for s2, b2, ok2 in top_blocks(body) if ok2)
    out.append(f'{fixsel(sel)}{{{body}}}')
VARS = r'''
:host{display:block;--font:"IBM Plex Sans Thai","Sarabun",system-ui,sans-serif;--ease:cubic-bezier(.32,.72,0,1);--ease-out:cubic-bezier(.16,1,.3,1);--r-shell:24px;--r-core:20px;--r-sm:14px;
 --accent:var(--teal-400,#2a9d8f);--accent-2:var(--amber-400,#e0a94f);--ok:#2a9d7f;--warn:#e0a94f;--crit:#d6453d;--rain:#4c5fd5;--up:#d9604f;--down:#2a9d7f;--flat:#6fa8c4;--bank:#8d5f3d;
 --core:var(--surface,#fff);--shell:rgba(var(--bd-rgb,157,201,201),.08);--line:var(--border,rgba(18,52,70,.1));--line-2:var(--border-strong,rgba(18,52,70,.2));--glass:rgba(var(--bg950-rgb,246,249,250),.8);
 --text:var(--text-300);--strong:var(--text-100);--muted:var(--text-500);--faint:var(--text-600);
 --sky-1:color-mix(in srgb,var(--accent) 30%,#fff);--sky-2:color-mix(in srgb,var(--accent) 7%,#fff);--water-1:color-mix(in srgb,var(--accent) 65%,#fff);--water-2:color-mix(in srgb,var(--accent) 100%,#000 18%);
 --hill-far:color-mix(in srgb,var(--accent) 16%,var(--sky-2));--hill-near:color-mix(in srgb,var(--accent) 30%,var(--sky-2));--land:color-mix(in srgb,var(--accent) 28%,#7a8a6a);--land-2:color-mix(in srgb,var(--accent) 22%,#5f6f55);
 --orb:#ffe29a;--orb-glow:rgba(255,214,130,.55);--shadow:rgba(22,66,88,.22);color:var(--text);font-family:var(--font);line-height:1.6}
:host([data-mode="dark"]){--core:color-mix(in srgb,var(--accent) 10%,#0d1e29);--bank:#c9945f;
 --sky-1:color-mix(in srgb,var(--accent) 38%,#050d14);--sky-2:color-mix(in srgb,var(--accent) 14%,#0a1a26);--water-1:var(--accent);--water-2:color-mix(in srgb,var(--accent) 100%,#000 45%);
 --hill-far:color-mix(in srgb,var(--accent) 22%,#07131b);--hill-near:color-mix(in srgb,var(--accent) 30%,#06111a);--land:color-mix(in srgb,var(--accent) 22%,#1c261f);--land-2:color-mix(in srgb,var(--accent) 18%,#141c17);
 --orb:#dfe9ff;--orb-glow:rgba(190,210,255,.35);--shadow:rgba(0,0,0,.5)}
.hero{padding:6px 0 10px!important;overflow:visible!important}.hero h1{font-size:clamp(24px,3.4vw,38px)!important;margin:10px 0 6px!important}.hero p.sub{margin:0 0 10px!important}
.sec{padding:20px 0!important}.wrap{padding:0!important;max-width:none!important}
.card{background:var(--core)}
'''
kf = [f'{s}{{{b}}}' for s, b in kept if s.startswith('@keyframes')]
rest = [f'{s}{{{b}}}' for s, b in kept if not s.startswith('@keyframes')]
rest = [x for x in out if not x.startswith('@keyframes')]
CSSTXT = VARS + '\n'.join(rest) + '\n' + '\n'.join(x for x in out if x.startswith('@keyframes'))

# ---------- templates ----------
H = R('index.html')
def grab(pat): return re.search(pat, H, re.S).group(0)
TPL = {
 'hero': grab(r'<header class="hero" id="top">.*?</header>'),
 'kpi': grab(r'<section class="sec" id="kpi">.*?</section>'),
 'levels': grab(r'<section class="sec" id="levels">.*?</section>'),
 'daily': grab(r'<section class="sec" id="daily">.*?</section>'),
 'forecast': grab(r'<section class="sec" id="forecast">.*?</section>'),
 'stations': grab(r'<section class="sec" id="stations">.*?</section>'),
 'dock': grab(r'<div class="dock" id="dock".*?</div>\s*(?=<script)'),
}
TPL['station'] = r'''<div class="sec">
  <div class="stbar"><div class="seg" id="stSeg"><i class="ind"></i></div><span class="live" id="live"><i></i><span id="liveText" data-sk>กำลังโหลดข้อมูล…</span></span></div>
  <div class="hero-grid stack">
    <div class="scene" id="scene" role="img" aria-label="ภาพจำลองระดับน้ำเทียบสันสปิลเวย์"></div>
    <aside class="readout wide" id="readout">
      <div class="rcol"><small id="roName" data-sk>—</small><div class="big"><span id="roLevel" data-sk>000.000</span><span>ม.รทก.</span></div><div class="delta" id="roDelta" data-sk>—</div><small id="roTrend" data-sk>—</small>
        <div class="capb"><div class="capn" id="roCapNW"><span id="roCapN">0</span><small>% ของความจุ</small></div><div class="captrack"><i class="f" id="roCapF"></i><i class="o" id="roCapO"></i><b class="m" id="roCapM"></b></div><div class="caplbl" id="roCapL">เส้นขีด = 100% (ระดับสันสปิลเวย์)</div></div></div>
      <div class="rcol"><div class="note" id="roNote" data-sk>—</div><div class="tele mini rv" id="teleBox"></div></div>
    </aside>
  </div>
  <div class="card rv" style="margin-top:16px"><h3 id="lvTitle">ระดับน้ำย้อนหลังเทียบสันสปิลเวย์</h3><div class="chart-box" id="lvBox"></div><div class="legend"><span><i style="background:var(--ok)"></i>ต่ำกว่าสัน</span><span><i style="background:var(--warn)"></i>ใกล้สัน (&lt; 0.10 ม.)</span><span><i style="background:var(--crit)"></i>สูงกว่าสัน</span></div></div>
</div>'''
TPL['kwan'] = r'''<div class="sec"><div class="stbar"><span class="live" id="live"><i></i><span id="liveText" data-sk>กำลังโหลดข้อมูล…</span></span><i id="kwanMark" hidden></i></div>
  <div class="hero-grid"><div class="scene" id="scene" role="img" aria-label="ภาพจำลองระดับน้ำกว๊านพะเยาเทียบตลิ่ง"></div>
    <aside class="readout" id="readout"><small id="roName" data-sk>—</small><div class="big"><span id="roLevel" data-sk>000.000</span><span>ม.รทก.</span></div><div class="delta" id="roDelta" data-sk>—</div><small id="roTrend" data-sk>—</small><div class="note" id="roNote" data-sk>—</div></aside></div></div>'''
TPL['resTable'] = r'''<div class="sec" style="padding:4px 0"><div class="card rv tbl-wrap"><table class="st"><thead><tr><th>อ่างเก็บน้ำ</th><th>ระดับ spillway (ม.)</th><th>ความจุที่ spillway</th><th>ระดับน้ำปัจจุบัน (ม.)</th><th>เส้นแนวโน้ม</th><th>6 ชม.</th><th>% ความจุ</th><th>สถานะ</th></tr></thead><tbody id="resBody"></tbody></table></div></div>'''
TPL['month'] = r'''<div class="sec" style="padding:4px 0 22px"><div class="bento" id="mBox">
  <div class="card b w rv" style="--d:.03s"><svg class="waves-bg" viewBox="0 0 800 120" preserveAspectRatio="none" aria-hidden="true"><path d="M0 40 q50 -30 100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0 t100 0"/><path d="M0 80 q60 30 120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0"/></svg>
    <h3 id="mTitle">สรุปน้ำเข้า–น้ำออกของเดือน</h3>
    <div class="trio"><div><div class="num" style="color:var(--accent)"><span id="mIn">0</span></div><div class="cap">น้ำไหลเข้ารวม (ลบ.ม.)</div></div><div><div class="num" style="color:var(--accent-2)"><span id="mOut">0</span></div><div class="cap">ระบายรวม ท่อ+ล้น (ลบ.ม.)</div></div><div><div class="num" id="mNetBox"><span id="mNet">0</span></div><div class="cap">ΔS สุทธิ (ลบ.ม.)</div></div></div>
    <div class="balance"><i class="in" id="mBalIn" style="width:50%"></i><i class="out" id="mBalOut" style="width:50%"></i></div><div class="cap" id="mBalNote">—</div></div>
  <div class="card b rv" style="--d:.1s"><h3>ปริมาตรกักเก็บสิ้นเดือน</h3><div class="flexrow"><svg class="ring" viewBox="0 0 120 120" aria-hidden="true"><circle class="bg" cx="60" cy="60" r="48"/><circle class="fg" id="mRingFg" cx="60" cy="60" r="48" style="--c:0"/><circle class="fg ov" id="mRingOv" cx="60" cy="60" r="48" style="--c:0"/></svg>
    <div><div class="num"><span id="mCapN">0</span><small>%</small></div><div class="cap" id="mCapNote">—</div></div></div></div>
  <div class="card b rv" id="mSpill" style="--d:.05s"><span class="alive-dot"></span><h3>วันที่ล้นสปิลเวย์</h3><div class="num"><span id="mSpD">0</span><small>วัน</small></div>
    <div class="ratio" id="mDays"><i class="r-sp"></i><i class="r-rn"></i><i class="r-flat"></i></div><div class="cap" id="mSpNote">—</div><div class="num sm" style="margin-top:8px"><span id="mSpS">0</span><small>ลบ.ม. น้ำล้นรวม</small></div></div>
  <div class="card b rv" style="--d:.1s"><h3>ฝนสะสมทั้งเดือน</h3><div class="num"><span id="mRain">0</span><small>มม.</small></div><div class="cap" id="mRainNote">—</div></div>
  <div class="card b rv" id="mLvBox" style="--d:.15s"><h3>ระดับน้ำรายวัน (ม.รทก.)</h3><div class="num sm"><span id="mLv1">—</span> → <span id="mLv2">—</span></div><svg id="mSpark" class="spark-big" viewBox="0 0 300 56" preserveAspectRatio="none"></svg><div class="cap" id="mLvNote">—</div></div>
</div></div>'''
TPL['hero'] = re.sub(r'<h1>.*?</h1>', '<h1>อ่างแม่นาเรือตอนนี้ <em id="heroState" data-sk>…</em></h1>', TPL['hero'], flags=re.S)

# ---------- JS body ----------
J = R('ui.js')
body = J[J.index("'use strict';") + len("'use strict';"):J.index('/* =============== BOOT')]
body = body.replace('const D = window.PROTO_DATA;\n', '')
body = re.sub(r'const \$ = .*?\n', '', body); body = re.sub(r'const \$\$ = .*?\n', '', body)
body = re.sub(r'const reduced = .*?\n', '', body)
# ตัดส่วน THEME (เก็บ placeInd)
a = body.index('/* =============== THEME'); b = body.index('/* =============== DATA HELPERS')
theme = body[a:b]; m = re.search(r'function placeInd\(seg\) \{.*?\n\}\n', theme, re.S)
body = body[:a] + m.group(0) + '\n' + body[b:]
boot = r'''
/* =============== BOOT (ukm) =============== */
function prepDraw(root) { $$('.draw', root).forEach(p => { try { p.style.setProperty('--len', Math.ceil(p.getTotalLength()) + 2); } catch (e) {} }); }
function sync() {
  const rt = document.documentElement, mode = rt.dataset.ukMode === 'dark' ? 'dark' : 'light';
  HOSTS.forEach(h => { h.dataset.mode = mode; h.dataset.motion = rt.classList.contains('uk-reduce') ? 'reduce' : 'normal'; });
  $$('.seg').forEach(placeInd);
}
buildScene(); initKPI(); buildLevels(); buildForecast(); buildTable(); buildResTable();
ROOTS.forEach(r => prepDraw(r));
bindTips('#dailyBox', '#dailyTT'); bindTips('#fcBox', '#fcTT');
{
  const st = status(R2.water_level, CREST);
  $('#heroState').textContent = st === 'crit' ? 'ล้นสปิลเวย์' : st === 'warn' ? 'ใกล้ล้น' : 'ปกติ';
  const L = D.ledger[D.ledger.length - 1];
  $('#heroSub').textContent = st === 'crit'
    ? `ระดับน้ำสูงกว่าสันสปิลเวย์ ${(R2.water_level - CREST).toFixed(3)} ม. มีน้ำล้นผ่านสปิลเวย์ ${fmt(L.spill)} ลบ.ม. ในวันที่ ${fmtD(L.date)}`
    : `ระดับน้ำต่ำกว่าสันสปิลเวย์ ${(CREST - R2.water_level).toFixed(3)} ม.`;
}
initDock(); updateLive(); setInterval(updateLive, 30000);
if (has('#stSeg')) initStations();
if (has('#kwanMark')) initKwan();
initMonth();
$('#dailySeg').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  $$('#dailySeg button').forEach(x => x.classList.toggle('on', x === b)); placeInd($('#dailySeg')); renderDaily(b.dataset.k);
});
window.addEventListener('uk-theme', sync); window.addEventListener('resize', () => $$('.seg').forEach(placeInd));
document.fonts && document.fonts.ready.then(() => $$('.seg').forEach(placeInd));
sync();
const finish = () => {
  HOSTS.forEach(h => h.classList.remove('is-loading')); $$('[data-sk]').forEach(n => n.removeAttribute('data-sk'));
  liveReadout(false);
  if (!reduced() && scene.waterG.animate) scene.waterG.animate([{ transform: `translateY(${yOf(ST.water_level) - Y_BASE + 170}px)` }, { transform: `translateY(${yOf(ST.water_level) - Y_BASE}px)` }], { duration: 1900, easing: 'cubic-bezier(.16,1,.3,1)' });
  initReveal(); $$('.seg').forEach(placeInd);
};
setTimeout(finish, reduced() ? 0 : 700);
'''
# initReveal ใช้ .nav (ไม่มีใน ukm) -> ตัดส่วน nav
body = re.sub(r"  const links = \$\$\('\.nav a\.lnk'\).*?secs\.forEach\(s => s && so\.observe\(s\)\);\n", '', body, flags=re.S)

JS = r'''/* ukm.js — โมดูลจาก ui_lab ฝังในหน้าเว็บเดิม (Shadow DOM) · สร้างอัตโนมัติโดย build_ukm.py อย่าแก้ตรงนี้ */
(function () {
'use strict';
var PAGE = location.pathname.split('/').pop() || 'index.html';
var AFTER_HERO = 'main > section.page-hero + section.section';
var CFG = {
  'monitoring.html': { plans: [{ anchor: '#stationGrid', pos: 'before', mods: ['station'], hide: '#stationGrid' },
    { anchor: '.table-card:has(#reservoirTableBody)', pos: 'before', mods: ['resTable'], hide: '.table-card:has(#reservoirTableBody)' },
    { anchor: 'section:has(#stationFilter)', pos: 'none', mods: [], hide: 'section:has(#stationFilter)' },
    { anchor: 'main > section:nth-last-of-type(2)', pos: 'none', mods: [], hide: 'main > section:nth-last-of-type(-n+2)' }], dock: true },
  'water-balance.html': { plans: [{ anchor: AFTER_HERO, pos: 'section-after', mods: ['daily'] }, { anchor: '.filter-bar', pos: 'after', mods: ['month'], hide: '#monthSummary' }] },
  'inflow-forecast.html': { plans: [{ anchor: AFTER_HERO, pos: 'section-after', mods: ['forecast'] }] } };
// หน้าแรก (index.html) และคาดการณ์น้ำท่วม (flood-forecast.html): ยังไม่ฝังโมดูล (ตัดออกตามที่ขอ)
var cfg = CFG[PAGE]; if (!cfg) return;
var CSS = %(css)s;
var TPL = %(tpl)s;
var NULL = new Proxy(function () {}, { get: function (t, k) { return k === Symbol.toPrimitive ? function () { return ''; } : k === 'length' ? 0 : NULL; }, set: function () { return true; }, apply: function () { return NULL; } });
var g = function (n) { return fetch('assets/data/' + n + '.json', { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(n + ' ' + r.status); return r.json(); }); };
function loadData() {
  return Promise.all(['monitoring', 'water_ledger', 'inflow_6h_display', 'latest', 'flood_latest'].map(g)).then(function (a) {
    var mon = a[0], led = a[1], w6 = a[2], lat = a[3], fl = a[4];
    var stations = mon.stations.map(function (s) { var o = {}; ['station_code', 'name_th', 'spillway_msl', 'water_level', 'rainfall_1h', 'measure_datetime', 'storage_m3', 'storage_max_m3', 'capacity_pct', 'name_en', 'temperature', 'humidity', 'pressure', 'solar', 'distance_to_spillway_m'].forEach(function (k) { o[k] = s[k]; }); o.history = (s.history || []); o.rain = (s.rainfall_hourly || []).slice(-72); return o; });
    var ledger = led.rows.slice(-45).map(function (r) { return { date: r.date, level: r.water_level_m, volume: r.water_volume_m3, inflow: r.inflow_m3, release: (r.outlet_release_m3 || 0) + (r.spill_m3 || 0), spill: r.spill_m3 || 0, rain: r.rain_24h_mm || 0 }; });
    var allrows = led.rows.map(function (r) { return { date: r.date, year: r.year, month: r.month, level: r.water_level_m, volume: r.water_volume_m3, inflow: r.inflow_m3, outlet: r.outlet_release_m3 || 0, spill: r.spill_m3 || 0, rain: r.rain_24h_mm || 0, evap: r.evap_m3, infil: r.infiltration_m3, dS: r.delta_s_m3 }; });
    var inf = lat.forecasts.inflow.forecast, base = new Date(inf.as_of_date), day = function (h) { return new Date(base.getTime() + h * 864e5).toISOString().slice(0, 10); };
    var fc = [{ date: day(0), h: 0, v: inf.current_qin_m3_per_day }];
    for (var h = 1; h <= 7; h++) { var p = inf.horizons['h' + h]; if (p) fc.push({ date: day(h), h: h, v: p.prediction_m3_per_day, low: !!p.low_confidence }); }
    return { snapshot: new Date().toISOString(), monitoring_updated: mon.meta.updated, capacity_m3: 1625000, crest: 489.545, max_level_seen: Math.max.apply(null, led.rows.map(function (r) { return r.water_level_m; })),
      stations: stations, reservoirs: mon.reservoirs || [], ledger: ledger, allrows: allrows, windows: w6.windows, forecast: fc,
      kwan: { level: fl.kwan_now.level, change_3d: fl.kwan_now.change_3d, bank: fl.banks.Mae_Main1, bank_ronghai: fl.banks.RongHai, flag: fl.flags.overall, generated_at: fl.generated_at } };
  });
}
function run(D, ROOTS, HOSTS) {
  const $ = (s, r) => { if (r && r.querySelector) return r.querySelector(s) || NULL; for (const x of ROOTS) { const e = x.querySelector(s); if (e) return e; } return NULL; };
  const $$ = (s, r) => r && r.querySelectorAll ? [...r.querySelectorAll(s)] : ROOTS.flatMap(x => [...x.querySelectorAll(s)]);
  const reduced = () => document.documentElement.classList.contains('uk-reduce') || matchMedia('(prefers-reduced-motion: reduce)').matches;
%(body)s
%(boot)s
}
function mount(D) {
  var ROOTS = [], HOSTS = [];
  function host(html, where) {
    var h = document.createElement('div'); h.className = 'ukm-host is-loading'; var sr = h.attachShadow({ mode: 'open' });
    var st = document.createElement('style'); st.textContent = CSS; sr.appendChild(st);
    var box = document.createElement('div'); box.innerHTML = html; while (box.firstChild) sr.appendChild(box.firstChild);
    where(h); ROOTS.push(sr); HOSTS.push(h); return h;
  }
  cfg.plans.forEach(function (p) {
    var anchor = null; try { anchor = document.querySelector(p.anchor); } catch (e) {} if (!anchor) return;
    var html = p.mods.map(function (m) { return TPL[m]; }).join('');
    if (p.hide) { var st = document.createElement('style'); st.textContent = p.hide + '{display:none!important}'; document.head.appendChild(st); }
    if (!p.mods.length) return;
    host(html, function (h) {
      if (p.pos === 'section-after') { var sec = document.createElement('section'); sec.className = 'section'; var w = document.createElement('div'); w.className = 'wrap'; w.appendChild(h); sec.appendChild(w); anchor.parentNode.insertBefore(sec, anchor.nextSibling); }
      else if (p.pos === 'before') anchor.parentNode.insertBefore(h, anchor);
      else anchor.parentNode.insertBefore(h, anchor.nextSibling);
    });
  });
  if (cfg.dock) host(TPL.dock, function (h) { document.body.appendChild(h); });
  if (!ROOTS.length) return;
  try { run(D, ROOTS, HOSTS); } catch (e) { console.error('ukm', e); }
}
function start() { loadData().then(mount).catch(function (e) { console.warn('ukm: โหลดข้อมูลไม่สำเร็จ', e); }); }
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
''' % {'css': json.dumps(CSSTXT, ensure_ascii=False), 'tpl': json.dumps(TPL, ensure_ascii=False), 'body': body, 'boot': boot}
open(os.path.join(D, 'site_kit', 'ukm.js'), 'w', encoding='utf8').write(JS)
print('ukm.js', len(JS))
