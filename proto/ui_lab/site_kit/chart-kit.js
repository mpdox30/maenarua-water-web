/* chart-kit.js — ปลั๊กอิน Chart.js แบบ drop-in: ธีมสีตามชุดสี, เส้นวาดเข้า, + เอฟเฟกต์เฉพาะกราฟ (ไม่แก้โค้ดหน้าเดิม) */
(function () {
'use strict';
if (!window.Chart || !Chart.register) return;
var clamp = function (v, a, b) { return Math.min(b, Math.max(a, v)); };
var root = document.documentElement;
var cv = function (n) { return getComputedStyle(root).getPropertyValue(n).trim(); };
var triple = function (n, d) { var s = cv(n); if (!s) return d; var p = s.split(',').map(Number); return p.length === 3 && p.every(isFinite) ? p : d; };
function parse(c) {
  if (typeof c !== 'string') return null; c = c.trim();
  var m = c.match(/^#([0-9a-f]{6})$/i);
  if (m) return { rgb: [0, 2, 4].map(function (i) { return parseInt(m[1].substr(i, 2), 16); }), a: null };
  m = c.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/i);
  return m ? { rgb: [+m[1], +m[2], +m[3]], a: m[4] == null ? null : +m[4] } : null;
}
function hexRgb(h) { return parse(h) ? parse(h).rgb : null; }
var TABLE = [
  [[69, 194, 173], function () { return triple('--t4-rgb', [69, 194, 173]); }],
  [[127, 224, 209], function () { return triple('--t3-rgb', [127, 224, 209]); }],
  [[42, 157, 143], function () { return triple('--t5-rgb', [42, 157, 143]); }],
  [[224, 169, 79], function () { return triple('--a4-rgb', [224, 169, 79]); }],
  [[240, 196, 124], function () { return triple('--a3-rgb', [240, 196, 124]); }],
  [[157, 201, 201], function () { return triple('--bd-rgb', [157, 201, 201]); }],
  [[6, 22, 28], function () { return triple('--bg950-rgb', [6, 22, 28]); }],
  [[138, 163, 160], function () { return hexRgb(cv('--text-500')) || [138, 163, 160]; }],
  [[196, 214, 211], function () { return hexRgb(cv('--text-300')) || [196, 214, 211]; }],
  [[238, 246, 244], function () { return hexRgb(cv('--text-100')) || [238, 246, 244]; }]
];
var CACHE = {};
window.addEventListener('uk-theme', function () { CACHE = {}; });
function mapColor(c) {
  var p = parse(c); if (!p) return c;
  for (var i = 0; i < TABLE.length; i++) {
    var t = TABLE[i][0]; if (p.rgb[0] === t[0] && p.rgb[1] === t[1] && p.rgb[2] === t[2]) {
      var n = CACHE[i] || (CACHE[i] = TABLE[i][1]()); return p.a == null ? 'rgb(' + n.join(',') + ')' : 'rgba(' + n.join(',') + ',' + p.a + ')';
    }
  }
  return c;
}
(function () { // แปลงสีที่ฮาร์ดโค้ดใน canvas (เช่น ป้ายค่าบนแท่ง) ให้ตามธีม
  var cp = CanvasRenderingContext2D.prototype;
  ['fillStyle', 'strokeStyle'].forEach(function (k) {
    var d = Object.getOwnPropertyDescriptor(cp, k); if (!d || !d.set) return;
    Object.defineProperty(cp, k, { get: d.get, configurable: true, set: function (v) { d.set.call(this, typeof v === 'string' ? mapColor(v) : v); } });
  });
})();
var ORIG = new WeakMap();
function remap(obj, props) {
  if (!obj || typeof obj !== 'object') return;
  var o = ORIG.get(obj); if (!o) { o = {}; ORIG.set(obj, o); }
  props.forEach(function (k) {
    var v = obj[k]; if (v == null) return;
    if (!(k in o)) { if (typeof v === 'string' || Array.isArray(v)) o[k] = v; else return; }
    else if (typeof v === 'string' && v !== o[k] && !o['_m_' + k]) { /* ค่าถูกเปลี่ยนโดยหน้าเว็บ */ o[k] = v; }
    var src = o[k]; obj[k] = Array.isArray(src) ? src.map(mapColor) : mapColor(src); o['_m_' + k] = obj[k];
  });
}
var DS_PROPS = ['borderColor', 'backgroundColor', 'pointBackgroundColor', 'pointBorderColor', 'hoverBackgroundColor', 'hoverBorderColor'];
function theme(chart) {
  var cfg = chart.config; if (!cfg || !cfg.data) return;
  (cfg.data.datasets || []).forEach(function (d) { remap(d, DS_PROPS); });
  var op = cfg.options || {};
  Object.keys(op.scales || {}).forEach(function (k) {
    var s = op.scales[k]; if (!s) return;
    remap(s.ticks, ['color']); remap(s.grid, ['color']); remap(s.border, ['color']); remap(s.title, ['color']);
  });
  if (op.plugins && op.plugins.legend) remap(op.plugins.legend.labels, ['color']);
}
var reduced = function () { return root.classList.contains('uk-reduce') || matchMedia('(prefers-reduced-motion: reduce)').matches; };
var ease = function (p) { return 1 - Math.pow(1 - p, 3); };
var backOut = function (p) { var c = 1.70158; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); };
var fmtK = function (v) { var a = Math.abs(v); return a >= 1e6 ? (v / 1e6).toFixed(2) + 'M' : a >= 1e3 ? (v / 1e3).toFixed(1) + 'k' : String(Math.round(v * 10) / 10); };

function startLoop(chart, st) {
  if (st.loop) return; st.loop = true;
  (function f() {
    if (!chart.canvas || !chart.canvas.isConnected) { st.loop = false; return; }
    if (st.vis && !document.hidden) { try { chart.draw(); } catch (e) {} }
    requestAnimationFrame(f);
  })();
}
function startReveal(chart, st) {
  if (st.started) return; st.started = true; var t0 = performance.now(), D = 2000;
  (function f(t) {
    if (!chart.canvas) return; var p = clamp((t - t0) / D, 0, 1); st.t = ease(p); if (!st.loop) { try { chart.draw(); } catch (e) {} }
    if (p < 1) requestAnimationFrame(f); else st.t = 1;
  })(t0);
}
function drop(ctx, x, y, s, A, bg) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  ctx.beginPath(); ctx.moveTo(0, -30); ctx.bezierCurveTo(10, -15, 15, -8, 15, 0); ctx.arc(0, 0, 15, 0, Math.PI, false); ctx.bezierCurveTo(-15, -8, -10, -15, 0, -30); ctx.closePath();
  ctx.fillStyle = 'rgb(' + A.join(',') + ')'; ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = bg; ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.beginPath(); ctx.ellipse(-5, -9, 3, 6, 0, 0, 7); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(-5, -1, 2.3, 0, 7); ctx.arc(5, -1, 2.3, 0, 7); ctx.fill();
  ctx.fillStyle = '#0b1c27'; ctx.beginPath(); ctx.arc(-4.6, -1, .9, 0, 7); ctx.arc(5.4, -1, .9, 0, 7); ctx.fill();
  ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.6; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(-4, 5); ctx.quadraticCurveTo(0, 9, 4, 5); ctx.stroke();
  ctx.restore();
}

var FONT = '"IBM Plex Sans Thai","Sarabun",sans-serif';
var MAE = null, MAE_REQ = false; // MAE ต่อ horizon (ลบ.ม./วัน) จากบันทึกย้อนหลัง ใช้วาดแถบ "ช่วงคลาดเคลื่อนปกติ"
function loadMae(chart) {
  if (MAE || MAE_REQ) { return; } MAE_REQ = true;
  fetch('assets/data/forecast_accuracy_log.csv', { cache: 'no-store' }).then(function (r) { return r.ok ? r.text() : ''; }).then(function (t) {
    var L = t.trim().split('\n'); if (L.length < 2) return; var H = L[0].split(','), ih = H.indexOf('horizon'), ie = H.indexOf('abs_error_m3'), s = {}, n = {};
    L.slice(1).forEach(function (l) { var c = l.split(','), e = parseFloat(c[ie]); if (!isFinite(e)) return; var h = +c[ih]; s[h] = (s[h] || 0) + Math.abs(e); n[h] = (n[h] || 0) + 1; });
    MAE = {}; Object.keys(s).forEach(function (h) { if (n[h] >= 3) MAE[h] = s[h] / n[h]; });
    try { chart.update('none'); } catch (e) {}
  }).catch(function () {});
}
var ERRC = function (pct) { return pct == null ? [138, 163, 160] : pct < 25 ? [42, 157, 127] : pct < 60 ? [224, 169, 79] : [217, 96, 79]; };
var plugin = {
  id: 'ukfx',
  afterInit: function (chart) {
    var st = chart._uk = { t: 1, started: true, vis: true };
    var op = chart.config.options || {};
    if (op.plugins && op.plugins.ukfx === false) return;
    var isLine = chart.config.type === 'line';
    if (isLine && !reduced()) {
      st.t = 0; st.started = false;
      if ('IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (es) { es.forEach(function (e) { st.vis = e.isIntersecting; if (e.isIntersecting) startReveal(chart, st); }); }, { threshold: .2 });
        io.observe(chart.canvas); st.io = io;
      } else { st.t = 1; st.started = true; }
    }
    var id = chart.canvas.id;
    if (id === 'inflowChart') loadMae(chart);
    if ((id === 'demandChart' || id === 'cmpCanvas' || id === 'rainfallChart' || id === 'inflowChart' || id === 'accChart') && !reduced()) {
      if ('IntersectionObserver' in window && !st.io) { var io2 = new IntersectionObserver(function (es) { es.forEach(function (e) { st.vis = e.isIntersecting; }); }, { threshold: .1 }); io2.observe(chart.canvas); st.io = io2; st.vis = false; }
      startLoop(chart, st);
    }
  },
  beforeUpdate: function (chart) {
    theme(chart);
    var id = chart.canvas && chart.canvas.id, cfg = chart.config, ds = cfg.data.datasets || [];
    var A = triple('--t4-rgb', [69, 194, 173]), B = triple('--a4-rgb', [224, 169, 79]);
    if (id === 'demandChart' && ds.length >= 2) {
      // เอฟเฟกต์แบบ river-profile: เส้นเพดาน (magnitude) ทึบ + เส้นค่าจริง (final) จุดไข่ปลา + แรเงาส่วนต่าง
      var f = ds[0], m = ds[1];
      // final = เส้นทึบ (ค่าจริง) · magnitude = เส้นจุดไข่ปลา (เพดานก่อนคูณความน่าจะเป็น) · แรเงาส่วนต่างระหว่างสองเส้น
      f.borderColor = 'rgb(' + A.join(',') + ')'; f.backgroundColor = 'rgba(' + A.join(',') + ',.2)'; f.borderWidth = 3.5; f.borderDash = []; f.borderCapStyle = 'round';
      f.pointRadius = 0; f.pointHoverRadius = 0; f.tension = .38; f.fill = '+1';
      m.borderColor = 'rgb(' + B.join(',') + ')'; m.backgroundColor = 'rgb(' + B.join(',') + ')'; m.borderWidth = 3.5; m.borderDash = [1, 9]; m.borderCapStyle = 'round'; m.pointRadius = 0; m.pointHoverRadius = 4; m.tension = .38; m.fill = false;
      if (cfg.options) { cfg.options.animation = false; cfg.options.layout = cfg.options.layout || {}; cfg.options.layout.padding = { top: 26, right: 12 }; }
    }
    if (id === 'rainfallChart' && cfg.type === 'bar' && ds[0]) {
      var d0 = ds[0], vv = (d0.data || []).map(function (v) { return +v || 0; }), mxv = Math.max.apply(null, vv.concat([1e-9]));
      d0.borderRadius = 7; d0.borderSkipped = false; d0.borderWidth = 0; d0.maxBarThickness = 44; d0.hoverBackgroundColor = 'rgb(' + B.join(',') + ')';
      d0.backgroundColor = function (c) {
        var ch = c.chart, a = ch.chartArea, v = +c.raw || 0, base = v >= mxv * .7 ? [217, 96, 79] : v >= mxv * .35 ? A : [Math.round(A[0] * .55 + 255 * .45), Math.round(A[1] * .55 + 255 * .45), Math.round(A[2] * .55 + 255 * .45)];
        if (!a) return 'rgb(' + base.join(',') + ')';
        var g = ch.ctx.createLinearGradient(0, a.bottom, 0, a.top); g.addColorStop(0, 'rgba(' + base.join(',') + ',.3)'); g.addColorStop(1, 'rgba(' + base.join(',') + ',.95)'); return g;
      };
      if (cfg.options) { cfg.options.animation = { duration: 900, easing: 'easeOutCubic', delay: function (c) { return c.type === 'data' && c.mode === 'default' ? c.dataIndex * 14 : 0; } }; cfg.options.layout = cfg.options.layout || {}; cfg.options.layout.padding = { top: 58 }; }
    }
    if (id === 'cmpCanvas' && cfg.type === 'bar') {
      cfg.options.layout = cfg.options.layout || {}; cfg.options.layout.padding = { top: 84 };
    }
    if (id === 'accChart' && cfg.type === 'line' && ds.length >= 2) {
      var P = ds[0], Ac = ds[1];
      P.borderWidth = 3; P.borderCapStyle = 'round'; P.tension = .32; P.pointRadius = 0; P.pointHoverRadius = 5; P.fill = 'origin';
      P.backgroundColor = function (c) {
        var ch = c.chart, a = ch.chartArea; if (!a) return 'rgba(' + A.join(',') + ',.12)';
        var g = ch.ctx.createLinearGradient(0, a.top, 0, a.bottom); g.addColorStop(0, 'rgba(' + A.join(',') + ',.34)'); g.addColorStop(1, 'rgba(' + A.join(',') + ',0)'); return g;
      };
      Ac.pointRadius = 5.5; Ac.pointHoverRadius = 8; Ac.pointBorderWidth = 2.5; Ac.pointBorderColor = cv('--bg-800') || '#fff';
      if (cfg.options) { cfg.options.animation = false; cfg.options.layout = cfg.options.layout || {}; cfg.options.layout.padding = { top: 30, right: 10 }; }
    }
    if (id === 'inflowChart' && cfg.type === 'line' && ds[0]) {
      var Q = ds[0];
      Q.borderWidth = 3.5; Q.borderCapStyle = 'round'; Q.tension = .35; Q.fill = 'origin'; Q.pointHoverRadius = 9; Q.pointBorderWidth = 2.5;
      Q.backgroundColor = function (c) {
        var ch = c.chart, a = ch.chartArea; if (!a) return 'rgba(' + A.join(',') + ',.12)';
        var g = ch.ctx.createLinearGradient(0, a.top, 0, a.bottom); g.addColorStop(0, 'rgba(' + A.join(',') + ',.30)'); g.addColorStop(1, 'rgba(' + A.join(',') + ',0)'); return g;
      };
      if (cfg.options) {
        cfg.options.animation = false; cfg.options.layout = cfg.options.layout || {}; cfg.options.layout.padding = { top: 70, right: 16, left: 6 };
        var yy = cfg.options.scales && cfg.options.scales.y;
        if (yy && MAE) { var hi = -Infinity, lo = Infinity; (Q.data || []).forEach(function (v, i) { var m = MAE[i + 1] || 0; if (v == null) return; hi = Math.max(hi, v + m); lo = Math.min(lo, v - m); }); if (isFinite(hi)) { yy.suggestedMax = hi * 1.04; yy.suggestedMin = Math.max(0, lo); } }
      }
    }
  },
  beforeDatasetsDraw: function (chart) {
    var st = chart._uk; if (!st) return;
    var a = chart.chartArea, c = chart.ctx, id = chart.canvas.id;
    if (st.t < 1) { c.save(); c.beginPath(); c.rect(a.left - 12, a.top - 40, (a.right - a.left + 24) * st.t, a.bottom - a.top + 80); c.clip(); st.clipped = true; }
    var A = triple('--t4-rgb', [69, 194, 173]);
    if (id === 'accChart' && chart.data.datasets.length >= 2) { // เส้นเชื่อมพยากรณ์ ↔ ค่าจริง สีตามขนาดความคลาดเคลื่อน
      var d0 = chart.data.datasets[0].data, d1 = chart.data.datasets[1].data, m0 = chart.getDatasetMeta(0).data, m1 = chart.getDatasetMeta(1).data;
      c.save(); c.lineWidth = 3.5; c.lineCap = 'round';
      for (var i = 0; i < d1.length; i++) {
        if (d1[i] == null || d0[i] == null || !m0[i] || !m1[i]) continue;
        var pct = d1[i] ? Math.abs(d0[i] - d1[i]) / Math.abs(d1[i]) * 100 : null, col = ERRC(pct);
        c.strokeStyle = 'rgba(' + col.join(',') + ',.75)'; c.beginPath(); c.moveTo(m0[i].x, m0[i].y); c.lineTo(m1[i].x, m1[i].y); c.stroke();
      }
      c.restore();
    }
    if (id === 'inflowChart' && MAE && chart.data.datasets[0]) { // แถบช่วงคลาดเคลื่อนปกติ ± MAE ของแต่ละ horizon
      var q = chart.data.datasets[0].data, y = chart.scales.y, mq = chart.getDatasetMeta(0).data, up = [], lw = [];
      q.forEach(function (v, i) { var m = MAE[i + 1]; if (v == null || m == null || !mq[i]) return; up.push([mq[i].x, y.getPixelForValue(v + m)]); lw.push([mq[i].x, y.getPixelForValue(Math.max(y.min, v - m))]); });
      if (up.length > 1) {
        c.save(); c.beginPath(); c.rect(a.left, a.top, a.right - a.left, a.bottom - a.top); c.clip();
        c.beginPath(); up.forEach(function (p, i) { i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1]); }); for (var k = lw.length - 1; k >= 0; k--) c.lineTo(lw[k][0], lw[k][1]); c.closePath();
        var g = c.createLinearGradient(0, a.top, 0, a.bottom); g.addColorStop(0, 'rgba(' + A.join(',') + ',.20)'); g.addColorStop(1, 'rgba(' + A.join(',') + ',.07)'); c.fillStyle = g; c.fill();
        c.setLineDash([5, 5]); c.lineWidth = 1.4; c.strokeStyle = 'rgba(' + A.join(',') + ',.55)';
        [up, lw].forEach(function (L) { c.beginPath(); L.forEach(function (p, i) { i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1]); }); c.stroke(); });
        c.restore();
      }
    }
  },
  afterDatasetsDraw: function (chart) {
    var st = chart._uk, c = chart.ctx; if (!st) return;
    if (st.clipped) { c.restore(); st.clipped = false; }
    var id = chart.canvas.id, a = chart.chartArea, A = triple('--t4-rgb', [69, 194, 173]), B = triple('--a4-rgb', [224, 169, 79]);
    var bg = cv('--bg-800') || '#0d2a34', txt = cv('--text-100') || '#eef6f4', now = performance.now();
    if (id === 'demandChart' && chart.data.datasets.length >= 2) {
      var m0 = chart.getDatasetMeta(0).data, m1 = chart.getDatasetMeta(1).data, vals = chart.data.datasets[0].data, n = m0.length, peak = 0;
      vals.forEach(function (v, i) { if (v > vals[peak]) peak = i; });
      c.save(); c.textAlign = 'center'; c.font = '600 12px ' + FONT;
      for (var i = 0; i < n; i++) {
        if (vals[i] == null || !m0[i]) continue;
        var th = (m0[i].x - a.left) / Math.max(1, a.right - a.left), p = clamp((st.t - th) * 9 + 1, 0, 1); if (st.t >= 1) p = 1; if (p <= 0) continue;
        var yTop = Math.min(m0[i].y, m1[i] ? m1[i].y : m0[i].y);
        if (i === peak) { var ph = (now % 1900) / 1900; c.strokeStyle = 'rgba(' + A.join(',') + ',' + (1 - ph) * .8 + ')'; c.lineWidth = 2; c.beginPath(); c.arc(m0[i].x, m0[i].y, 7 + ph * 16, 0, 7); c.stroke(); }
        c.fillStyle = 'rgb(' + A.join(',') + ')'; c.strokeStyle = bg; c.lineWidth = 3; c.beginPath(); c.arc(m0[i].x, m0[i].y, 6.5 * backOut(p), 0, 7); c.fill(); c.stroke();
        c.globalAlpha = p; c.fillStyle = txt; c.fillText(fmtK(vals[i]), m0[i].x, Math.max(a.top + 4, yTop - 13)); c.globalAlpha = 1;
      }
      c.restore();
    }
    if (id === 'rainfallChart' && chart.config.type === 'bar' && chart.data.datasets[0]) {
      var rv = chart.data.datasets[0].data.map(function (v) { return +v || 0; }), rm = chart.getDatasetMeta(0).data, rmx = Math.max.apply(null, rv.concat([0])), pk = rv.indexOf(rmx);
      c.save(); c.textAlign = 'center'; c.font = '700 11.5px ' + FONT;
      rv.forEach(function (v, i) { if (!rm[i] || v < rmx * .45 || i === pk) return; c.fillStyle = cv('--text-300') || '#555'; c.fillText(v >= 10 ? v.toFixed(0) : v.toFixed(1), rm[i].x, rm[i].y - 7); });
      if (rmx > 0 && rm[pk]) {
        var hop = reduced() ? 0 : Math.abs(Math.sin(now / 550)) * 4, px = rm[pk].x, py = rm[pk].y;
        c.fillStyle = cv('--text-100') || '#111'; c.font = '700 13px ' + FONT; c.fillText(rmx.toFixed(1) + ' มม.', px, py - 46 - hop * 0);
        drop(c, px, py - 12 - hop, .8, A, bg);
      }
      c.restore();
    }
    if (id === 'accChart' && chart.data.datasets.length >= 2) {
      var ad = chart.data.datasets[1].data, am = chart.getDatasetMeta(1).data, li = -1; ad.forEach(function (v, i) { if (v != null) li = i; });
      c.save(); c.font = '600 11px ' + FONT; c.textAlign = 'right'; c.textBaseline = 'middle';
      var lx = a.right; [['< 25%', [42, 157, 127]], ['25–60%', [224, 169, 79]], ['≥ 60%', [217, 96, 79]]].reverse().forEach(function (it) {
        var w = c.measureText(it[0]).width; c.fillStyle = cv('--text-500') || '#777'; c.fillText(it[0], lx, a.top - 14); lx -= w + 6; c.fillStyle = 'rgb(' + it[1].join(',') + ')'; c.fillRect(lx - 14, a.top - 17, 14, 6); lx -= 24;
      });
      c.fillStyle = cv('--text-500') || '#777'; c.fillText('เส้นเชื่อม = % คลาดเคลื่อน', lx, a.top - 14);
      if (li >= 0 && am[li] && !reduced()) { var ph = (now % 1800) / 1800; c.strokeStyle = 'rgba(' + B.join(',') + ',' + (1 - ph) * .85 + ')'; c.lineWidth = 2.2; c.beginPath(); c.arc(am[li].x, am[li].y, 7 + ph * 16, 0, 7); c.stroke(); }
      c.restore();
    }
    if (id === 'inflowChart' && chart.data.datasets[0]) {
      var qd = chart.data.datasets[0], qv = qd.data, qm = chart.getDatasetMeta(0).data, qpk = 0, ps = qd.pointStyle;
      qv.forEach(function (v, i) { if (v != null && v > qv[qpk]) qpk = i; });
      c.save(); c.textAlign = 'center';
      // เส้น "วันนี้" ที่ขอบซ้าย แบ่งอดีต | อนาคต
      c.setLineDash([3, 5]); c.lineWidth = 1.4; c.strokeStyle = 'rgba(' + B.join(',') + ',.8)'; c.beginPath(); c.moveTo(a.left + 1, a.top - 6); c.lineTo(a.left + 1, a.bottom); c.stroke(); c.setLineDash([]);
      c.textAlign = 'left'; c.font = '700 11px ' + FONT; c.fillStyle = 'rgb(' + B.join(',') + ')'; c.fillText('● วันนี้', a.left + 7, a.top - 12);
      if (MAE) { c.textAlign = 'right'; c.font = '600 11px ' + FONT; c.fillStyle = cv('--text-500') || '#777'; c.fillText('แถบประ = ช่วงคลาดเคลื่อนเฉลี่ยย้อนหลัง (±MAE)', a.right, a.top - 12); }
      c.textAlign = 'center'; c.font = '700 12px ' + FONT;
      for (var j = 0; j < qv.length; j++) {
        if (qv[j] == null || !qm[j]) continue;
        var th2 = (qm[j].x - a.left) / Math.max(1, a.right - a.left), p2 = clamp((st.t - th2) * 9 + 1, 0, 1); if (st.t >= 1) p2 = 1; if (p2 <= 0) continue;
        var low = ps && ps[j] === 'rectRot';
        if (low && !reduced()) { var ph2 = ((now + j * 260) % 2000) / 2000; c.strokeStyle = 'rgba(' + B.join(',') + ',' + (1 - ph2) * .8 + ')'; c.lineWidth = 2; c.beginPath(); c.arc(qm[j].x, qm[j].y, 8 + ph2 * 14, 0, 7); c.stroke(); }
        c.globalAlpha = p2; c.fillStyle = cv('--text-100') || '#111'; c.fillText(fmtK(qv[j]), qm[j].x, qm[j].y - (j === qpk ? 38 : 14)); c.globalAlpha = 1;
      }
      if (qm[qpk] && !reduced() && st.t >= 1) { var hp = Math.abs(Math.sin(now / 550)) * 4; drop(c, qm[qpk].x, qm[qpk].y - 16 - hp, .72, A, bg); }
      c.restore();
    }
    if (id === 'cmpCanvas' && chart.config.type === 'bar') {
      var ds = chart.data.datasets[0], meta = chart.getDatasetMeta(0).data, prev = null, lastIdx = -1;
      ds.data.forEach(function (v, i) { if (v != null) lastIdx = i; });
      var dec = function (d) { var x = Math.abs(d); return x >= 1e6 ? (x / 1e6).toFixed(2) + 'M' : x >= 1e3 ? (x / 1e3).toFixed(1) + 'k' : x >= 10 ? x.toFixed(1) : x.toFixed(2); };
      c.save(); c.textAlign = 'center'; c.font = '700 12px ' + FONT;
      ds.data.forEach(function (v, i) {
        if (v == null || !meta[i]) return; var x = meta[i].x, y = meta[i].y, lift = i === lastIdx ? 36 : 0;
        if (prev != null) {
          var d = v - prev, flat = Math.abs(d) < Math.max(1e-9, Math.abs(prev) * .003), col = flat ? '--flat' : d > 0 ? '--up' : '--down';
          c.fillStyle = flat ? 'rgb(111,168,196)' : d > 0 ? 'rgb(217,96,79)' : 'rgb(42,157,127)';
          c.fillText(flat ? '● เท่าเดิม' : (d > 0 ? '▲ +' : '▼ −') + dec(d), x, y - 24 - lift);
        }
        prev = v;
        if (i === lastIdx) { var hop = reduced() ? 0 : Math.abs(Math.sin(now / 550)) * 4; drop(c, x, y - 24 - hop, .85, A, bg); }
      });
      c.restore();
    }
  }
};
Chart.register(plugin);
window.addEventListener('uk-theme', function () { (Chart.instances ? Object.values(Chart.instances) : []).forEach(function (ch) { try { ch.update('none'); } catch (e) {} }); });
})();
