/* page-kit.js — เอฟเฟกต์ระดับ DOM ของตาราง + เกจความแม่นยำ (drop-in, ไม่แก้โค้ดหน้าเดิม) */
(function () {
'use strict';
var root = document.documentElement;
var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
var reduced = function () { return root.classList.contains('uk-reduce') || matchMedia('(prefers-reduced-motion: reduce)').matches; };
var num = function (t) { var m = String(t || '').replace(/,/g, '').match(/-?\d+(?:\.\d+)?/); return m ? parseFloat(m[0]) : NaN; };
var GREEN = '42,157,127', AMBER = '224,169,79', RED = '217,96,79';
var errCol = function (v) { return v < 25 ? GREEN : v < 60 ? AMBER : RED; };

/* ---------- ตาราง: แถบข้อมูลในเซลล์ + แถวเข้าทีละแถว ---------- */
// รูปแบบคอลัมน์ -> วิธีทำแถบ  (pct = เปอร์เซ็นต์ตรงๆ, err = % คลาดเคลื่อน แดง/เหลือง/เขียว, rel = สัดส่วนต่อค่าสูงสุดของคอลัมน์)
var COLS = [
  [/%\s*ผิดพลาด|% error/i, 'err'],
  [/%\s*ความจุ/i, 'pct'],
  [/^Prob\./i, 'prob'],
  [/น้ำไหลเข้า|ค่าพยากรณ์สุดท้าย|^พยากรณ์ \(/i, 'rel']
];
function modeOf(h) { for (var i = 0; i < COLS.length; i++) if (COLS[i][0].test(h)) return COLS[i][1]; return null; }
function enhance(tbl) {
  var heads = $$('thead th', tbl).map(function (t) { return (t.textContent || '').trim(); });
  var rows = $$('tbody tr', tbl);
  rows.forEach(function (tr, i) { if (!tr.hasAttribute('data-uk-i')) { tr.setAttribute('data-uk-i', 1); tr.style.setProperty('--i', Math.min(i, 14)); } });
  heads.forEach(function (h, ci) {
    var mode = modeOf(h); if (!mode) return;
    var cells = rows.map(function (tr) { return tr.children[ci]; }).filter(Boolean);
    var vals = cells.map(function (td) { return /^\s*[—–-]?\s*$/.test(td.textContent) ? NaN : num(td.textContent); });
    var mx = Math.max.apply(null, vals.filter(isFinite).concat([1e-9]));
    cells.forEach(function (td, k) {
      if (td.hasAttribute('data-uk-b')) return; td.setAttribute('data-uk-b', 1);
      var v = vals[k]; if (!isFinite(v)) return;
      var b, c = '69,194,173';
      if (mode === 'pct') b = v; else if (mode === 'err') { b = Math.min(100, Math.abs(v)); c = errCol(Math.abs(v)); }
      else if (mode === 'prob') b = /%/.test(td.textContent) ? v : v <= 1 ? v * 100 : v; else b = Math.max(0, v) / mx * 100;
      b = Math.max(0, Math.min(100, b)); if (b < 1.5) return;
      td.classList.add('uk-bar'); td.style.setProperty('--b', b.toFixed(1)); td.style.setProperty('--bc', mode === 'pct' || mode === 'prob' || mode === 'rel' ? 'var(--t4-rgb)' : c);
    });
  });
}
function accuracyGauge(tbl) {
  var kg = document.getElementById('kpiGrid'); if (!kg || !tbl.classList.contains('acc-table')) return;
  var heads = $$('thead th', tbl).map(function (t) { return (t.textContent || '').trim(); }), ci = -1;
  heads.forEach(function (h, i) { if (/%\s*ผิดพลาด/.test(h)) ci = i; }); if (ci < 0) return;
  var n = 0, ok = 0;
  $$('tbody tr', tbl).forEach(function (tr) { var v = num(tr.children[ci] && tr.children[ci].textContent); if (!isFinite(v)) return; n++; if (Math.abs(v) <= 25) ok++; });
  if (!n) return;
  var pct = ok / n * 100, col = pct >= 60 ? GREEN : pct >= 35 ? AMBER : RED;
  var card = document.getElementById('ukGauge');
  if (!card) {
    card = document.createElement('div'); card.id = 'ukGauge'; card.className = 'kpi uk-gauge';
    card.innerHTML = '<div class="label">สัดส่วนที่คลาดเคลื่อน ≤ 25%</div>' +
      '<div class="uk-g"><svg viewBox="0 0 120 70" aria-hidden="true"><path class="uk-g-bg" d="M10 62 A50 50 0 0 1 110 62" pathLength="100"/><path class="uk-g-fg" d="M10 62 A50 50 0 0 1 110 62" pathLength="100"/></svg>' +
      '<div class="uk-g-v num"><span id="ukGv">0</span><small>%</small></div></div><div class="sub" id="ukGsub"></div>';
    kg.appendChild(card);
  }
  var fg = card.querySelector('.uk-g-fg'); fg.style.stroke = 'rgb(' + col + ')'; card.style.setProperty('--gc', col);
  document.getElementById('ukGsub').textContent = ok + ' จาก ' + n + ' คู่ที่มีค่าจริง';
  var from = card._v || 0, to = pct, t0 = performance.now(), el = document.getElementById('ukGv');
  card._v = to;
  if (reduced()) { fg.style.strokeDashoffset = 100 - to; el.textContent = to.toFixed(0); return; }
  (function f(t) { var p = Math.min(1, (t - t0) / 1400), e = 1 - Math.pow(1 - p, 4), v = from + (to - from) * e; fg.style.strokeDashoffset = 100 - v; el.textContent = v.toFixed(0); if (p < 1) requestAnimationFrame(f); })(t0);
}
var queued = false;
function scan() {
  queued = false;
  $$('table.acc-table').forEach(function (t) { accuracyGauge(t); }); /* แถบข้อมูล/แอนิเมชันแถวในตารางถูกปิดตามคำขอ (enhance() ไม่ถูกเรียก) */
}
function queue() { if (queued) return; queued = true; requestAnimationFrame(scan); }
/* ---------- แถบความคืบหน้าการเลื่อน + เงาหัวเว็บ ---------- */
function scrollFx() {
  var bar = document.createElement('div'); bar.id = 'uk-prog'; document.body.appendChild(bar);
  var hd = document.querySelector('header.site-header'), tick = false;
  function upd() {
    tick = false; var h = document.documentElement, mx = h.scrollHeight - innerHeight, y = window.pageYOffset || h.scrollTop || 0;
    bar.style.transform = 'scaleX(' + (mx > 0 ? Math.min(1, y / mx) : 0) + ')'; if (hd) hd.classList.toggle('uk-scrolled', y > 8);
  }
  addEventListener('scroll', function () { if (!tick) { tick = true; requestAnimationFrame(upd); } }, { passive: true }); upd();
}

/* ---------- แผนที่ (gis-map): ธีมตามสี + ping อ่างเก็บน้ำ + ฝายหายใจ + คลองวาดเข้า ---------- */
function mapFx() {
  var M = null, tries = 0;
  var cssv = function (n) { return getComputedStyle(root).getPropertyValue(n).trim(); };
  var THEME = { '#e0a94f': '--amber-400', '#45c2ad': '--teal-400', '#c4d6d3': '--teal-500' };
  function getMap() { try { return Function('return typeof map!=="undefined"&&typeof L!=="undefined"?map:null')(); } catch (e) { return null; } }
  function feats() { var a = []; M.eachLayer(function (l) { if (l.feature) a.push(l); }); return a; }
  var pings = null;
  function restyle() {
    feats().forEach(function (l) {
      if (!l.setStyle || !l.options) return; var o = l._ukO || (l._ukO = { c: l.options.color, f: l.options.fillColor }), s = {}, c = THEME[o.c], f = THEME[o.f];
      if (c && cssv(c)) s.color = cssv(c); if (f && cssv(f)) s.fillColor = cssv(f); if (s.color || s.fillColor) l.setStyle(s);
    });
  }
  function deco(l) {
    var p = l._path, o = l.options || {}; if (!p || !l.feature) return;
    var oc = (l._ukO && l._ukO.c) || o.color, fc = (l._ukO && l._ukO.f) || o.fillColor;
    if (fc === '#22c55e' && !p.classList.contains('uk-breath')) { p.classList.add('uk-breath'); p.style.animationDelay = ((l._leaflet_id % 9) * .27) + 's'; }
    if (oc === '#0ea5e9' && !fc && p.getTotalLength && !reduced() && !l._ukDrawn) {
      var len = 0; try { len = p.getTotalLength(); } catch (e) {} if (len > 0) { l._ukDrawn = 1; p.style.setProperty('--len', len.toFixed(0)); p.classList.add('uk-draw'); p.addEventListener('animationend', function () { p.classList.remove('uk-draw'); }, { once: true }); }
    }
  }
  function build() {
    restyle(); feats().forEach(deco);
    pings = L.layerGroup();
    feats().forEach(function (l) {
      var fc = (l._ukO && l._ukO.f) || (l.options && l.options.fillColor); if (fc !== '#3b82f6' || !l.getBounds) return;
      var ic = L.divIcon({ className: 'uk-ping2', html: '<i></i><i></i><b></b>', iconSize: [0, 0] });
      L.marker(l.getBounds().getCenter(), { icon: ic, interactive: false, keyboard: false, zIndexOffset: -100 }).addTo(pings);
    });
    if (!reduced()) pings.addTo(M);
    M.on('layeradd', function (e) { if (e.layer && e.layer.feature) deco(e.layer); });
    var tg = document.getElementById('toggle-res');
    if (tg) tg.addEventListener('change', function (e) { if (reduced()) return; if (e.target.checked) pings.addTo(M); else M.removeLayer(pings); });
    window.addEventListener('uk-theme', restyle);
  }
  var iv = setInterval(function () {
    M = M || getMap(); tries++;
    if (M && feats().length >= 20) { clearInterval(iv); build(); } else if (tries > 60) clearInterval(iv);
  }, 400);
}

/* ---------- ซ่อนส่วน "การเข้าถึงข้อมูล" (access-grid) ทุกหน้า ---------- */
function hideAccess() { $$('.access-grid').forEach(function (g) { var s = g.closest('section'); if (s) s.style.display = 'none'; }); }

/* ---------- หน้าแรก: ตัวชี้วัดสำคัญ แบบ bento (อ่านค่าจากการ์ดเดิม ไม่ hardcode) ---------- */
function indexKpi() {
  var grid = document.querySelector('.kpi-grid'), cards = grid ? grid.querySelectorAll('.kpi-card') : [];
  if (!grid || cards.length < 3 || !document.getElementById('capacityKpiValue') || document.getElementById('ukKb')) return;
  var txt = function (el) { return (el && el.textContent || '').trim(); };
  var kvEl = cards[0].querySelector('.kpi-value'), area = num(kvEl && kvEl._ukKey ? kvEl._ukKey : txt(kvEl)), /* ใช้ค่าตั้งต้นก่อนที่ count-up จะนับจาก 0 */ rai = (txt(cards[0].querySelector('.kpi-note')).match(/([\d,]+)\s*ไร่/) || [])[1];
  var rows = $$('.kpi-mini-row', cards[1]).map(function (r) { return { n: txt(r.querySelector('.name')), v: num(txt(r.querySelector('.val'))) }; });
  var za = rows[0] ? rows[0].v : NaN, zb = rows[1] ? rows[1].v : NaN; if (!(area > 0) || !isFinite(za) || !isFinite(zb)) return;
  var other = Math.max(0, area - za - zb), P = function (v) { return Math.round(v / area * 100); };
  var row = function (c, n, v) { return '<div class="kb-row"><i class="dm ' + c + '"></i><span class="nm">' + n + '<em>' + P(v) + '% ของพื้นที่</em></span><b class="num" data-to="' + v + '" data-d="1">0</b><small>ตร.กม.</small></div>'; };
  var wrap = document.createElement('div'); wrap.id = 'ukKb'; wrap.className = 'uk-kb';
  wrap.innerHTML =
    '<div class="kb-l"><div class="kb-hero"><div class="kb-num num"><b data-to="' + area + '" data-d="1">0</b></div><div class="kb-cap"><div class="t">ตร.กม.</div><div class="s">ขอบเขตตำบลแม่นาเรือ' + (rai ? '<br>' + rai + ' ไร่' : '') + '</div></div></div>' +
    '<div class="kb-list">' + row('a', rows[0].n, za) + row('b', rows[1].n, zb) + '</div></div>' +
    '<div class="kb-r"><div class="kb-rh" id="ukTankNote"></div><div class="kb-cards" id="ukTanks"></div></div>';
  grid.style.display = 'none'; grid.parentNode.insertBefore(wrap, grid.nextSibling);
  var on = false;
  function tween(el) {
    var to = parseFloat(el.getAttribute('data-to')), d = +el.getAttribute('data-d') || 0, fmt = function (v) { return v.toFixed(d); };
    if (!isFinite(to)) return; if (reduced()) { el.textContent = fmt(to); return; }
    var t0 = performance.now(); (function f(t) { var p = Math.min(1, (t - t0) / 1500); el.textContent = fmt(to * (1 - Math.pow(1 - p, 4))); if (p < 1) requestAnimationFrame(f); })(t0);
  }
  function go() { if (on) return; on = true; wrap.classList.add('uk-on'); $$('b[data-to]', wrap).forEach(tween); }
  function note() { var n = txt(document.getElementById('capacityKpiNote')); document.getElementById('ukTankNote').textContent = 'อ่างเก็บน้ำ 5 อ่าง เรียงจาก % ความจุมากสุด' + (n ? ' · ' + n.replace(/^อัปเดตล่าสุด:\s*/, 'ข้อมูล ณ ') : ''); }
  function res() {
    var box = document.getElementById('ukTanks'), rs = $$('#capacityKpiValue .kpi-mini-row'); note();
    if (!rs.length) { box.innerHTML = '<div class="kb-rh">กำลังโหลด…</div>'; return; }
    var L = rs.map(function (r) { var vt = txt(r.querySelector('.val')), v = num(vt); return { n: txt(r.querySelector('.name')), v: v, has: /%/.test(vt) && isFinite(v) }; });
    L.sort(function (x, y) { return (y.has ? y.v : -1) - (x.has ? x.v : -1); });
    box.innerHTML = L.map(function (r, k) {
      var over = r.has && r.v > 100, chip = !r.has ? 'ไม่มีสถานีโทรมาตร' : over ? 'สูงกว่าสันสปิลเวย์' : 'ต่ำกว่าสันสปิลเวย์';
      return '<div class="kc' + (over ? ' over' : '') + (r.has ? '' : ' off') + '" style="--h:' + (r.has ? Math.min(100, r.v) : 0) + ';--k:' + k + '"><div class="bar"><i></i></div>' +
        '<div class="kt"><span class="chip">' + chip + '</span><div class="nm">' + r.n + '</div><div class="sb">' + (r.has ? '% ของความจุที่สันสปิลเวย์' : 'ยังไม่ติดตั้งสถานีโทรมาตร') + '</div></div>' +
        '<div class="kv num">' + (r.has ? '<b data-to="' + r.v + '" data-d="1">' + (on ? r.v.toFixed(1) : '0') + '</b><small>%</small>' : '<b>—</b>') + '</div></div>';
    }).join('');
    if (on) $$('#ukTanks b[data-to]').forEach(tween);
  }
  res(); new MutationObserver(res).observe(document.getElementById('capacityKpiValue'), { childList: true });
  new MutationObserver(note).observe(document.getElementById('capacityKpiNote'), { childList: true, characterData: true, subtree: true });
  if ('IntersectionObserver' in window) { var io = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { go(); io.disconnect(); } }, { threshold: .2 }); io.observe(wrap); } else go();
}

function init() {
  scrollFx(); hideAccess(); if (document.getElementById('map')) mapFx(); indexKpi();
  scan();
  new MutationObserver(function (ms) { // ไม่นับการเปลี่ยนแปลงภายในเกจเอง (กันวนซ้ำ)
    for (var i = 0; i < ms.length; i++) { var t = ms[i].target; if (!(t.closest && t.closest('#ukGauge')) && !(t.nodeType === 3)) { queue(); return; } }
  }).observe(document.body, { childList: true, subtree: true });
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
