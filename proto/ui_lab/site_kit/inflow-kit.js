/* inflow-kit.js — ปรับส่วน "ตัวชี้วัดของโมเดล (CatBoost) + น้ำไหลเข้าอ่างสุทธิ" ของ inflow-forecast.html (ไม่แก้ไฟล์หน้าเดิม)
   1) แทนที่ drawSparkline(): กราฟระดับน้ำรายชั่วโมงแบบวาดเข้า + พื้นไล่เฉด + แท่งฝนห้อยจากด้านบน + แกนเวลา + hover
   2) การ์ด KPI 3 ใบ: แท่งพยากรณ์ 7 วัน / แถบความจุอ่างตอนนี้ / จุดสถานะ 7 horizon (อ่านจากข้อมูลจริงในหน้า)
   3) ตัวเลขใหญ่ในแผงนับขึ้นเมื่อค่าเปลี่ยน */
(function () {
'use strict';
if (!document.getElementById('pipSparkSvg')) return;
var NS = 'http://www.w3.org/2000/svg', root = document.documentElement;
var $ = function (id) { return document.getElementById(id); };
var reduced = function () { return root.classList.contains('uk-reduce') || matchMedia('(prefers-reduced-motion: reduce)').matches; };
var clamp = function (v, a, b) { return Math.min(b, Math.max(a, v)); };
var el = function (tag, a, p) { var e = document.createElementNS(NS, tag); for (var k in a) e.setAttribute(k, a[k]); if (p) p.appendChild(e); return e; };
var cssv = function (n) { return getComputedStyle(root).getPropertyValue(n).trim(); };

/* ---------- ข้อมูลโทรมาตร RES002 (ฝนรายชั่วโมง + ความจุ) จาก monitoring.json ---------- */
var monP = null;
function mon() { if (!monP) monP = fetch('assets/data/monitoring.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (j) { return j && (j.stations || []).filter(function (s) { return s.station_code === 'RES002'; })[0]; }).catch(function () { return null; }); return monP; }
setInterval(function () { monP = null; }, 5 * 60 * 1000);

/* ---------- 1) กราฟระดับน้ำรายชั่วโมง ---------- */
var token = 0, TH = 'Asia/Bangkok';
var hhmm = function (t) { return new Date(t).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: TH }); };
var dmy = function (t) { return new Date(t).toLocaleDateString('th-TH', { day: 'numeric', month: 'short', timeZone: TH }); };
window.drawSparkline = function (levelPts, peak, startLevel, peakTimeStr) {
  var svg = $('pipSparkSvg'), peakLabel = $('pipSparkPeakLabel'); if (!svg || !levelPts || levelPts.length < 2) return;
  var my = ++token, rect = svg.getBoundingClientRect(), W = rect.width > 0 ? rect.width : 640, H = 176, padX = 14, rainH = 36, yTop = 52, yBot = 132;
  svg.setAttribute('viewBox', '0 0 ' + W.toFixed(1) + ' ' + H); svg.style.height = H + 'px'; svg.innerHTML = '';
  var t0 = levelPts[0].t, t1 = levelPts[levelPts.length - 1].t, lv = levelPts.map(function (p) { return p.level; });
  var lo = Math.min.apply(null, lv), hi = Math.max.apply(null, lv), rg = (hi - lo) || 0.01; lo -= rg * .08; hi += rg * .12; rg = hi - lo;
  var X = function (t) { return padX + (W - 2 * padX) * (t - t0) / ((t1 - t0) || 1); }, Y = function (v) { return yBot - (yBot - yTop) * (v - lo) / rg; };
  var defs = el('defs', {}, svg), g = el('linearGradient', { id: 'ukSg', x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
  el('stop', { offset: '0%', class: 'uks-s0' }, g); el('stop', { offset: '100%', class: 'uks-s1' }, g);
  // กริด + ป้ายระดับ
  [lo + rg * .1, lo + rg * .5, lo + rg * .9].forEach(function (v) { el('line', { x1: padX, x2: W - padX, y1: Y(v).toFixed(1), y2: Y(v).toFixed(1), class: 'uks-grid' }, svg); var t = el('text', { x: W - padX, y: (Y(v) - 4).toFixed(1), class: 'uks-lbl', 'text-anchor': 'end' }, svg); t.textContent = v.toFixed(3); });
  // เส้นระดับเริ่มต้น
  var by = Y(startLevel); el('line', { x1: padX, x2: W - padX, y1: by.toFixed(1), y2: by.toFixed(1), class: 'uks-base' }, svg);
  var bl = el('text', { x: padX + 2, y: (by - 5).toFixed(1), class: 'uks-lbl b' }, svg); bl.textContent = 'ระดับเริ่มต้น ' + startLevel.toFixed(3);
  // แกนเวลา: ทุก 6 ชม.
  var tickG = el('g', {}, svg), d0 = new Date(t0), first = new Date(t0); first.setMinutes(0, 0, 0);
  for (var tt = first.getTime(); tt <= t1; tt += 3600 * 1000) {
    var hr = +new Date(tt).toLocaleString('en-GB', { hour: '2-digit', hour12: false, timeZone: TH }) % 24; if (hr % 6 !== 0 || tt < t0) continue;
    var x = X(tt); el('line', { x1: x.toFixed(1), x2: x.toFixed(1), y1: yBot + 2, y2: yBot + 7, class: 'uks-tick' }, tickG);
    var tx = el('text', { x: x.toFixed(1), y: H - 22, class: 'uks-lbl', 'text-anchor': 'middle' }, tickG); tx.textContent = hhmm(tt);
    if (hr === 0) { var dx = el('text', { x: x.toFixed(1), y: H - 9, class: 'uks-lbl d', 'text-anchor': 'middle' }, tickG); dx.textContent = dmy(tt); }
  }
  var d1 = el('text', { x: padX, y: H - 9, class: 'uks-lbl d' }, svg); d1.textContent = dmy(t0);
  // พื้นที่ + เส้นระดับ (เรียบแบบ monotone ง่ายๆ ด้วย Catmull-Rom → Bezier)
  var P = levelPts.map(function (p) { return [X(p.t), Y(p.level)]; });
  var path = 'M' + P[0][0].toFixed(1) + ',' + P[0][1].toFixed(1);
  for (var i = 0; i < P.length - 1; i++) {
    var p0 = P[i - 1] || P[i], p1 = P[i], p2 = P[i + 1], p3 = P[i + 2] || p2, k = 0.18;
    path += ' C' + (p1[0] + (p2[0] - p0[0]) * k).toFixed(1) + ',' + (p1[1] + (p2[1] - p0[1]) * k).toFixed(1) + ' ' + (p2[0] - (p3[0] - p1[0]) * k).toFixed(1) + ',' + (p2[1] - (p3[1] - p1[1]) * k).toFixed(1) + ' ' + p2[0].toFixed(1) + ',' + p2[1].toFixed(1);
  }
  var area = el('path', { d: path + ' L' + P[P.length - 1][0].toFixed(1) + ',' + yBot + ' L' + P[0][0].toFixed(1) + ',' + yBot + ' Z', class: 'uks-area' }, svg);
  var line = el('path', { d: path, class: 'uks-line', pathLength: 1 }, svg);
  // จุดสูงสุด + จุดล่าสุด
  var pk = P[levelPts.indexOf(peak)] || P[0], last = P[P.length - 1];
  var pg = el('g', { class: 'uks-pk' }, svg); el('circle', { cx: pk[0].toFixed(1), cy: pk[1].toFixed(1), r: 12, class: 'uks-ring' }, pg); el('circle', { cx: pk[0].toFixed(1), cy: pk[1].toFixed(1), r: 5.5, class: 'uks-pkd' }, pg);
  var lg = el('g', { class: 'uks-pk' }, svg); el('circle', { cx: last[0].toFixed(1), cy: last[1].toFixed(1), r: 5, class: 'uks-end' }, lg);
  // ตัวชี้ (hover)
  var hv = el('g', { class: 'uks-hv', style: 'display:none' }, svg), hl = el('line', { y1: rainH, y2: yBot, class: 'uks-hl' }, hv), hd = el('circle', { r: 5.5, class: 'uks-hd' }, hv);
  var tip = $('ukSparkTip'); if (!tip) { tip = document.createElement('div'); tip.id = 'ukSparkTip'; tip.className = 'uks-tip'; svg.parentNode.appendChild(tip); }
  var cap = el('rect', { x: 0, y: 0, width: W, height: H, fill: 'transparent' }, svg);
  cap.addEventListener('mousemove', function (e) {
    var r = svg.getBoundingClientRect(), mx = (e.clientX - r.left) * (W / r.width), best = 0, bd = 1e9;
    P.forEach(function (q, i) { var d = Math.abs(q[0] - mx); if (d < bd) { bd = d; best = i; } });
    var q = P[best], pt = levelPts[best]; hv.style.display = ''; hl.setAttribute('x1', q[0]); hl.setAttribute('x2', q[0]); hd.setAttribute('cx', q[0]); hd.setAttribute('cy', q[1]);
    var dcm = (pt.level - startLevel) * 100;
    tip.innerHTML = '<b>' + dmy(pt.t) + ' ' + hhmm(pt.t) + ' น.</b><span>ระดับ ' + pt.level.toFixed(3) + ' ม.รทก.</span><span>' + (dcm >= 0 ? '+' : '') + dcm.toFixed(1) + ' ซม. จากเริ่มต้น</span><span class="r" data-t="' + pt.t + '"></span>';
    tip.style.display = 'block'; tip.style.left = clamp(q[0] / W * 100, 14, 86) + '%'; tip.style.top = Math.max(2, q[1] - 74) / H * 100 + '%';
    if (svg._rain) { var rr = svg._rain[Math.round(pt.t / 3600000)]; tip.querySelector('.r').textContent = rr != null ? 'ฝน ' + rr.toFixed(1) + ' มม./ชม.' : ''; }
  });
  cap.addEventListener('mouseleave', function () { hv.style.display = 'none'; tip.style.display = 'none'; });
  if (peakLabel) { peakLabel.style.left = (pk[0] / W * 100).toFixed(2) + '%'; peakLabel.style.top = (Math.max(pk[1] - 12, 14) / H * 100).toFixed(2) + '%'; peakLabel.textContent = 'สูงสุด ' + peakTimeStr; }
  svg.classList.remove('uks-go'); void svg.getBoundingClientRect(); svg.classList.add('uks-go');
  // แท่งฝนรายชั่วโมงห้อยจากด้านบน (ข้อมูลจริง rainfall_hourly)
  mon().then(function (s) {
    if (my !== token || !s || !Array.isArray(s.rainfall_hourly)) return;
    var rows = s.rainfall_hourly.map(function (r) { return { t: new Date(r.t).getTime(), v: +r.rain_mm || 0 }; }).filter(function (r) { return r.t >= t0 - 1800000 && r.t <= t1 + 1800000; });
    svg._rain = {}; rows.forEach(function (r) { svg._rain[Math.round(r.t / 3600000)] = r.v; });
    var mx = Math.max.apply(null, rows.map(function (r) { return r.v; }).concat([4])), bw = Math.max(3, (W - 2 * padX) / Math.max(24, rows.length) * .6), rg2 = el('g', { class: 'uks-rain' }, svg);
    svg.insertBefore(rg2, area);
    rows.forEach(function (r, i) { if (r.v <= 0) return; var h = Math.max(2, r.v / mx * rainH), b = el('rect', { x: (X(r.t) - bw / 2).toFixed(1), y: 4, width: bw.toFixed(1), height: h.toFixed(1), rx: 2, style: 'animation-delay:' + (i * 25) + 'ms' }, rg2); var tt2 = el('title', {}, b); tt2.textContent = dmy(r.t) + ' ' + hhmm(r.t) + ' น. — ฝน ' + r.v.toFixed(1) + ' มม.'; });
    var rl = el('text', { x: padX, y: 12, class: 'uks-lbl b' }, svg); rl.textContent = rows.some(function (r) { return r.v > 0; }) ? 'ฝนรายชั่วโมง (สูงสุด ' + mx.toFixed(1) + ' มม.)' : 'ไม่มีฝนในช่วงนี้';
  });
};

/* ---------- 3) ตัวเลขนับขึ้นเมื่อค่าเปลี่ยน ---------- */
function tween(el0) {
  var tn = null; for (var n = el0.firstChild; n; n = n.nextSibling) if (n.nodeType === 3 && /\d/.test(n.nodeValue)) { tn = n; break; } if (!tn) return;
  var m = tn.nodeValue.match(/(-?[\d,]*\.?\d+)/); if (!m) return; var txt = m[1], to = parseFloat(txt.replace(/,/g, '')); if (!isFinite(to)) return;
  var dec = (txt.split('.')[1] || '').length, comma = txt.indexOf(',') >= 0, key = tn.nodeValue; if (el0._k === key || reduced()) return; el0._k = key;
  var pre = tn.nodeValue.slice(0, m.index), post = tn.nodeValue.slice(m.index + txt.length), t0 = performance.now();
  (function f(t) { var p = clamp((t - t0) / 1500, 0, 1), v = to * (1 - Math.pow(1 - p, 4)), s = v.toFixed(dec); if (comma) { var q = s.split('.'); q[0] = q[0].replace(/\B(?=(\d{3})+(?!\d))/g, ','); s = q.join('.'); } tn.nodeValue = pre + s + post; if (p < 1) requestAnimationFrame(f); else tn.nodeValue = key; })(t0);
}
function watch(id, sel) { var e = $(id); if (!e) return; var run = function () { (sel ? [].slice.call(e.querySelectorAll(sel)) : [e]).forEach(tween); }; new MutationObserver(run).observe(e, { childList: true }); run(); }
watch('kpiCurrentQin'); watch('pipEstimateValue'); watch('pipLiveGrid', '.pip-live-item .v');

/* ---------- 2) มินิกราฟในการ์ด KPI ---------- */
function cards() {
  var ch = window.Chart && Chart.getChart ? Chart.getChart($('inflowChart')) : null; if (!ch) return;
  var ds = ch.data.datasets[0], vals = ds.data || []; if (vals.length > 14) return; var ps = ds.pointStyle || [], sig = JSON.stringify(vals) + JSON.stringify(ps); if (cards.sig === sig) return; cards.sig = sig;
  var mx = Math.max.apply(null, vals.map(function (v) { return +v || 0; }).concat([1]));
  var k1 = $('kpiH1'), k3 = $('kpiLowConfCount'), k2 = $('kpiReservoir');
  var rm = function (id) { var o = $(id); if (o) o.remove(); };
  rm('ukMiniBars'); rm('ukMiniDots');
  if (k1) { var b = document.createElement('div'); b.id = 'ukMiniBars'; b.className = 'uk-mini';
    b.innerHTML = vals.map(function (v, i) { var low = ps[i] === 'rectRot'; return '<div class="mb' + (low ? ' low' : '') + (i === 0 ? ' h1' : '') + '" style="--h:' + Math.max(8, (+v || 0) / mx * 100).toFixed(0) + ';--k:' + i + '" title="ล่วงหน้า ' + (i + 1) + ' วัน: ' + Number(v).toLocaleString('th-TH', { maximumFractionDigits: 0 }) + ' ม³/วัน' + (low ? ' (ความเชื่อมั่นต่ำ)' : '') + '"><i></i><span>h' + (i + 1) + '</span></div>'; }).join('');
    k1.parentNode.insertBefore(b, $('kpiModelNse')); }
  if (k3) { var d = document.createElement('div'); d.id = 'ukMiniDots'; d.className = 'uk-dots';
    d.innerHTML = vals.map(function (v, i) { var low = ps[i] === 'rectRot'; return '<div class="dt' + (low ? ' low' : '') + '" style="--k:' + i + '" title="ล่วงหน้า ' + (i + 1) + ' วัน — ' + (low ? 'ความเชื่อมั่นต่ำ' : 'ปกติ') + '"><i></i><span>h' + (i + 1) + '</span></div>'; }).join('') + '<div class="lg"><b class="o"></b>ปกติ <b class="a"></b>ต่ำ</div>';
    k3.parentNode.insertBefore(d, k3.nextElementSibling); }
}
function capCard() {
  var k2 = $('kpiReservoir'); if (!k2) return;
  mon().then(function (s) {
    if (!s || s.capacity_pct == null) return; var p = +s.capacity_pct, w = Math.min(100, p), over = p > 100, c = $('ukCap'), key = p + '|' + s.distance_to_spillway_m;
    if (c && c._key === key) return;
    var html = '<div class="ch"><span>ความจุเก็บกักตอนนี้</span><b class="num">' + p.toFixed(1) + '%</b></div><div class="ct"><i style="--w:' + w + '"></i><u></u></div><div class="cn">' + (over ? 'สูงกว่าระดับสันสปิลเวย์ ' + (s.distance_to_spillway_m != null ? Math.abs(s.distance_to_spillway_m).toFixed(2) + ' ม.' : '') : 'ต่ำกว่าสันสปิลเวย์') + '</div>';
    if (!c) { c = document.createElement('div'); c.id = 'ukCap'; k2.parentNode.insertBefore(c, $('kpiDataSource')); }
    c._key = key; c.className = 'uk-cap' + (over ? ' over' : ''); c.innerHTML = html;
  });
}
setInterval(function () { cards(); capCard(); }, 1500); cards(); capCard();
})();
