/* kwan-kit.js — แทนที่ drawChart() ของ flood-forecast.html (กราฟระดับกว๊านพะเยา) ด้วยเวอร์ชันมีเอฟเฟกต์ — ไม่แก้ไฟล์หน้าเดิม */
(function () {
'use strict';
var cv0 = document.getElementById('kwanChart'); if (!cv0) return;
var root = document.documentElement, FONT = '"IBM Plex Sans Thai","Sarabun",sans-serif', NUM = '"Space Grotesk","IBM Plex Sans Thai",sans-serif';
var cssv = function (n) { return getComputedStyle(root).getPropertyValue(n).trim(); };
var rgb = function (n, d) { var p = cssv(n).split(',').map(Number); return p.length === 3 && p.every(isFinite) ? p : d; };
var clamp = function (v, a, b) { return Math.min(b, Math.max(a, v)); };
var ease = function (p) { return 1 - Math.pow(1 - p, 3); };
var reduced = function () { return root.classList.contains('uk-reduce') || matchMedia('(prefers-reduced-motion: reduce)').matches; };
var TH = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
var thd = function (s) { var p = String(s).split('-'); return +p[2] + ' ' + TH[+p[1] - 1]; };
var rgba = function (c, a) { return 'rgba(' + c.join(',') + ',' + a + ')'; };

var S = { d: null, t: 1, hover: -1, raf: 0, t0: 0, geo: null };

function drop(c, x, y, s, A, bg) {
  c.save(); c.translate(x, y); c.scale(s, s);
  c.beginPath(); c.moveTo(0, -30); c.bezierCurveTo(10, -15, 15, -8, 15, 0); c.arc(0, 0, 15, 0, Math.PI, false); c.bezierCurveTo(-15, -8, -10, -15, 0, -30); c.closePath();
  c.fillStyle = rgba(A, 1); c.fill(); c.lineWidth = 2.5; c.strokeStyle = bg; c.stroke();
  c.fillStyle = 'rgba(255,255,255,.55)'; c.beginPath(); c.ellipse(-5, -9, 3, 6, 0, 0, 7); c.fill();
  c.fillStyle = '#fff'; c.beginPath(); c.arc(-5, -1, 2.3, 0, 7); c.arc(5, -1, 2.3, 0, 7); c.fill();
  c.fillStyle = '#0b1c27'; c.beginPath(); c.arc(-4.6, -1, .9, 0, 7); c.arc(5.4, -1, .9, 0, 7); c.fill();
  c.strokeStyle = '#fff'; c.lineWidth = 1.6; c.lineCap = 'round'; c.beginPath(); c.moveTo(-4, 5); c.quadraticCurveTo(0, 9, 4, 5); c.stroke();
  c.restore();
}

function frame() {
  var d = S.d, cv = document.getElementById('kwanChart'); if (!d || !cv) return;
  var dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = 380; if (!W) return;
  if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  cv.style.height = H + 'px';
  var c = cv.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
  var A = rgb('--t4-rgb', [69, 194, 173]), A5 = rgb('--t5-rgb', [42, 157, 143]), B = rgb('--a4-rgb', [224, 169, 79]), BG = cssv('--bg-800') || '#fff';
  var T5 = cssv('--text-500') || '#777', T3 = cssv('--text-300') || '#444', T1 = cssv('--text-100') || '#111';
  var RED = [224, 82, 82], ORG = [224, 118, 63];
  var obs = d.kwan_observed_30d, fc = d.kwan_forecast, bM = d.banks.Mae_Main1, bR = d.banks.RongHai;
  var n = obs.length + fc.length, no = obs.length;
  var ys = obs.map(function (o) { return o.level; }).concat(fc.map(function (f) { return f.level; }), fc.map(function (f) { return f.p10; }), fc.map(function (f) { return f.p90; }), [bM, bR]);
  var ymin = Math.min.apply(null, ys) - 0.15, ymax = Math.max.apply(null, ys) + 0.15;
  var padL = 58, padR = 74, padT = 62, padB = 36, xw = (W - padL - padR) / (n - 1);
  var X = function (i) { return padL + i * xw; }, Y = function (v) { return padT + (ymax - v) / (ymax - ymin) * (H - padT - padB); };
  var t = S.t, tObs = ease(clamp(t / .62, 0, 1)), tFan = ease(clamp((t - .55) / .45, 0, 1)), now = performance.now();
  var xNow = X(no - 1), yNow = Y(obs[no - 1].level), top = padT, bot = H - padB;
  S.geo = { X: X, Y: Y, padL: padL, padR: padR, W: W, H: H, n: n, no: no, padT: padT, padB: padB };

  // โซนเหนือตลิ่ง (พื้นหลังโทนเตือน)
  c.save(); c.beginPath(); c.rect(padL, top, W - padL - padR, bot - top); c.clip();
  var yM = Y(bM), yR = Y(bR);
  c.fillStyle = rgba(RED, .07); c.fillRect(padL, top, W - padL - padR, Math.max(0, yM - top));
  c.fillStyle = rgba(ORG, .08); c.fillRect(padL, Math.max(top, yM), W - padL - padR, Math.max(0, yR - yM));
  c.restore();
  // กริด + ป้ายแกน Y
  var step = (ymax - ymin) > 1.6 ? 0.5 : 0.25; c.font = '11px ' + NUM; c.textAlign = 'right';
  for (var v = Math.ceil(ymin / step) * step; v <= ymax; v += step) {
    c.strokeStyle = rgba(rgb('--bd-rgb', [157, 201, 201]), .22); c.lineWidth = 1; c.beginPath(); c.moveTo(padL, Y(v)); c.lineTo(W - padR, Y(v)); c.stroke();
    c.fillStyle = T5; c.fillText(v.toFixed(2), padL - 8, Y(v) + 3.5);
  }
  // เส้นตลิ่ง + ป้ายชื่อ
  [[bM, RED, 'ตลิ่งแม่นาเรือ'], [bR, ORG, 'ตลิ่งร่องไฮ']].forEach(function (b) {
    c.save(); c.strokeStyle = rgba(b[1], .9); c.setLineDash([2, 4]); c.lineWidth = 1.6; c.beginPath(); c.moveTo(padL, Y(b[0])); c.lineTo(W - padR, Y(b[0])); c.stroke(); c.restore();
    c.font = '600 10.5px ' + FONT; c.textAlign = 'left'; c.fillStyle = rgba(b[1], 1); c.fillText(b[2], W - padR + 6, Y(b[0]) - 3); c.fillText(b[0].toFixed(2), W - padR + 6, Y(b[0]) + 9);
  });
  // ส่วนสังเกตการณ์: พื้นที่ใต้เส้น + เส้น (เปิดทีละน้อยจากซ้ายไปขวา)
  c.save(); c.beginPath(); c.rect(padL - 4, 0, (xNow - padL + 8) * tObs, H); c.clip();
  var g = c.createLinearGradient(0, top, 0, bot); g.addColorStop(0, rgba(A, .32)); g.addColorStop(1, rgba(A, 0));
  c.beginPath(); obs.forEach(function (o, i) { i ? c.lineTo(X(i), Y(o.level)) : c.moveTo(X(i), Y(o.level)); }); c.lineTo(xNow, bot); c.lineTo(X(0), bot); c.closePath(); c.fillStyle = g; c.fill();
  c.strokeStyle = rgba(A5, 1); c.lineWidth = 3; c.lineJoin = 'round'; c.lineCap = 'round';
  /* ช่วงที่ข้อมูลวัดขาด (>1 วัน) วาดเป็นเส้นประจาง = ค่าประมาณ (interpolation) ไม่ใช่ค่าวัดจริง */
  var gapDays = function (i) { return (Date.parse(obs[i].date) - Date.parse(obs[i - 1].date)) / 864e5; }, gaps = [];
  c.beginPath(); obs.forEach(function (o, i) { if (i && gapDays(i) > 1.5) { gaps.push(i); c.moveTo(X(i), Y(o.level)); } else i ? c.lineTo(X(i), Y(o.level)) : c.moveTo(X(i), Y(o.level)); }); c.stroke();
  if (gaps.length) {
    c.save(); c.setLineDash([3, 6]); c.lineWidth = 2.2; c.strokeStyle = rgba(A5, .55);
    gaps.forEach(function (i) { c.beginPath(); c.moveTo(X(i - 1), Y(obs[i - 1].level)); c.lineTo(X(i), Y(obs[i].level)); c.stroke(); });
    c.setLineDash([]); c.font = '500 10.5px ' + FONT; c.textAlign = 'center'; c.fillStyle = rgba(rgb('--bd-rgb', [120, 150, 150]), .95);
    gaps.forEach(function (i) { c.fillText('ข้อมูลขาด ' + Math.round(gapDays(i) - 1) + ' วัน (ประมาณ)', (X(i - 1) + X(i)) / 2, Math.min(bot - 6, Y(Math.min(obs[i - 1].level, obs[i].level)) + 20)); });
    c.restore();
  }
  c.restore();
  // แถบ P10–P90 กางพัดจากจุด "วันนี้"
  if (tFan > 0) {
    c.save(); c.beginPath(); c.rect(xNow, 0, (W - padR - xNow + 6) * tFan, H); c.clip();
    c.beginPath(); c.moveTo(xNow, yNow); fc.forEach(function (f, i) { c.lineTo(X(no + i), Y(f.p90)); });
    for (var i = fc.length - 1; i >= 0; i--) c.lineTo(X(no + i), Y(fc[i].p10)); c.closePath();
    var g2 = c.createLinearGradient(xNow, 0, W - padR, 0); g2.addColorStop(0, rgba(B, .08)); g2.addColorStop(1, rgba(B, .32)); c.fillStyle = g2; c.fill();
    c.strokeStyle = rgba(B, .55); c.lineWidth = 1.2; c.setLineDash([4, 4]);
    [function (f) { return f.p90; }, function (f) { return f.p10; }].forEach(function (fn) { c.beginPath(); c.moveTo(xNow, yNow); fc.forEach(function (f, i) { c.lineTo(X(no + i), Y(fn(f))); }); c.stroke(); });
    c.setLineDash([]);
    // เส้นพยากรณ์ค่ากลาง
    c.strokeStyle = rgba(B, 1); c.lineWidth = 3; c.setLineDash([7, 6]); c.beginPath(); c.moveTo(xNow, yNow); fc.forEach(function (f, i) { c.lineTo(X(no + i), Y(f.level)); }); c.stroke(); c.setLineDash([]);
    fc.forEach(function (f, i) { c.fillStyle = rgba(B, 1); c.strokeStyle = BG; c.lineWidth = 2; c.beginPath(); c.arc(X(no + i), Y(f.level), 4.5, 0, 7); c.fill(); c.stroke(); });
    c.restore();
  }
  // เส้นแบ่ง "วันนี้"
  c.save(); c.strokeStyle = rgba(rgb('--bd-rgb', [157, 201, 201]), .8); c.setLineDash([3, 4]); c.beginPath(); c.moveTo(xNow, top - 14); c.lineTo(xNow, bot); c.stroke(); c.restore();
  c.font = '700 11px ' + FONT; c.textAlign = 'left'; c.fillStyle = rgba(B, 1); c.fillText('● วันนี้', xNow + 6, top - 18);
  c.fillStyle = T5; c.font = '600 10.5px ' + FONT; c.textAlign = 'right'; c.fillText('พยากรณ์ 7 วัน ▸', W - padR, top - 18);
  // สะพานระยะห่างจากตลิ่ง (วันนี้ + วันสุดท้ายของพยากรณ์)
  var bracket = function (x, lvl, bank, col, side) {
    var y1 = Y(lvl), y2 = Y(bank), up = lvl >= bank, g = lvl - bank; if (Math.abs(y1 - y2) < 6) return;
    c.save(); c.strokeStyle = rgba(col, .95); c.fillStyle = rgba(col, 1); c.lineWidth = 1.8;
    var bx = x + side * 14; c.beginPath(); c.moveTo(bx, y1); c.lineTo(bx, y2); c.moveTo(bx - 4, y1); c.lineTo(bx + 4, y1); c.moveTo(bx - 4, y2); c.lineTo(bx + 4, y2); c.stroke();
    var tx = (up ? 'สูงกว่าตลิ่ง +' : 'ต่ำกว่าตลิ่ง −') + Math.abs(g).toFixed(2) + ' ม.'; c.font = '700 11.5px ' + FONT; c.textAlign = side < 0 ? 'right' : 'left';
    var w = c.measureText(tx).width + 14, lx = side < 0 ? bx - 6 - w : bx + 6, ly = (y1 + y2) / 2;
    c.fillStyle = BG; c.strokeStyle = rgba(col, .6); c.lineWidth = 1; c.beginPath(); c.roundRect ? c.roundRect(lx, ly - 11, w, 22, 11) : c.rect(lx, ly - 11, w, 22); c.fill(); c.stroke();
    c.fillStyle = rgba(col, 1); c.textAlign = 'left'; c.fillText(tx, lx + 7, ly + 4.2); c.restore();
  };
  if (tObs >= 1) bracket(xNow, obs[no - 1].level, bM, RED, -1);
  // วงกระเพื่อม + น้องหยด + ป้ายค่าล่าสุด
  var hop = reduced() ? 0 : Math.abs(Math.sin(now / 550)) * 4;
  if (tObs >= 1) {
    if (!reduced()) { var ph = (now % 1900) / 1900; c.strokeStyle = rgba(A5, (1 - ph) * .8); c.lineWidth = 2; c.beginPath(); c.arc(xNow, yNow, 7 + ph * 16, 0, 7); c.stroke(); }
    c.fillStyle = rgba(A5, 1); c.strokeStyle = BG; c.lineWidth = 3; c.beginPath(); c.arc(xNow, yNow, 6.5, 0, 7); c.fill(); c.stroke();
    drop(c, xNow, yNow - 22 - hop, .7, A, BG);
    c.font = '700 12.5px ' + NUM; c.textAlign = 'center'; c.fillStyle = T1; c.fillText(obs[no - 1].level.toFixed(2), xNow - 36, yNow - 13);
  }
  if (tFan >= 1) {
    var lf = fc[fc.length - 1], xe = X(n - 1);
    c.font = '700 12px ' + NUM; c.textAlign = 'left'; c.fillStyle = T1; c.fillText(lf.level.toFixed(2), xe + 8, Y(lf.level) + 4);
    c.font = '600 10.5px ' + FONT; c.fillStyle = T5; c.fillText('P90 ' + lf.p90.toFixed(2), xe + 8, Y(lf.p90) + 4); c.fillText('P10 ' + lf.p10.toFixed(2), xe + 8, Y(lf.p10) + 4);
  }
  // ป้ายแกน X: เลือกวาดจากขวาไปซ้าย ไม่ให้ทับกัน
  c.font = '11px ' + NUM; c.textAlign = 'center'; var edge = W - 1;
  for (var k = n - 1; k >= 0; k--) {
    var isF = k >= no; if (!(isF || k % 6 === 0)) continue; var lab = thd((isF ? fc[k - no] : obs[k]).date), w2 = c.measureText(lab).width, x = X(k);
    if (x + w2 / 2 > edge - 6 && k !== n - 1) continue; if (x + w2 / 2 > edge + 40) continue;
    c.fillStyle = isF ? T3 : T5; c.fillText(lab, x, H - 12); edge = x - w2 / 2;
  }
  // เส้นตามเมาส์ + ป้ายค่า
  var hi = S.hover;
  if (hi >= 0 && hi < n && t >= 1) {
    var isFc = hi >= no, p = isFc ? fc[hi - no] : obs[hi], hx = X(hi), hy = Y(p.level);
    c.save(); c.strokeStyle = rgba(rgb('--bd-rgb', [157, 201, 201]), .9); c.lineWidth = 1; c.beginPath(); c.moveTo(hx, top); c.lineTo(hx, bot); c.stroke();
    c.fillStyle = rgba(isFc ? B : A5, 1); c.strokeStyle = BG; c.lineWidth = 2.5; c.beginPath(); c.arc(hx, hy, 6, 0, 7); c.fill(); c.stroke();
    var L = [thd(p.date) + (isFc ? ' (พยากรณ์)' : ''), 'ระดับ ' + p.level.toFixed(2) + ' ม.รทก.'];
    if (isFc) L.push('P10–P90: ' + p.p10.toFixed(2) + ' – ' + p.p90.toFixed(2));
    var gM = p.level - bM; L.push((gM >= 0 ? 'สูงกว่า' : 'ต่ำกว่า') + 'ตลิ่งแม่นาเรือ ' + Math.abs(gM).toFixed(2) + ' ม.');
    var gRh = p.level - bR; L.push((gRh >= 0 ? 'สูงกว่า' : 'ต่ำกว่า') + 'ตลิ่งร่องไฮ ' + Math.abs(gRh).toFixed(2) + ' ม.');
    c.font = '600 12px ' + FONT; var bw = Math.max.apply(null, L.map(function (s) { return c.measureText(s).width; })) + 22, bh = L.length * 18 + 14;
    var bx2 = hx + 14 + bw > W - 4 ? hx - 14 - bw : hx + 14, by2 = clamp(hy - bh / 2, 4, H - bh - 4);
    c.shadowColor = 'rgba(0,0,0,.25)'; c.shadowBlur = 14; c.fillStyle = BG; c.strokeStyle = rgba(rgb('--bd-rgb', [157, 201, 201]), .8); c.beginPath(); c.roundRect ? c.roundRect(bx2, by2, bw, bh, 10) : c.rect(bx2, by2, bw, bh); c.fill(); c.shadowBlur = 0; c.stroke();
    c.textAlign = 'left'; L.forEach(function (s, j) { c.fillStyle = j === 0 ? T1 : T3; c.font = (j === 0 ? '700 ' : '500 ') + '12px ' + FONT; c.fillText(s, bx2 + 11, by2 + 19 + j * 18); });
    c.restore();
  }
}

function loop() {
  S.raf = 0; var el = performance.now() - S.t0; S.t = reduced() ? 1 : clamp(el / 2600, 0, 1);
  var cv = document.getElementById('kwanChart'); if (!cv || !cv.isConnected) return;
  var vis = S.vis !== false && !document.hidden; if (vis) frame();
  S.raf = requestAnimationFrame(loop);
}
function start(d) {
  S.d = d; S.t = reduced() ? 1 : 0; S.t0 = performance.now();
  var cv = document.getElementById('kwanChart');
  if (!S.bound) {
    S.bound = true;
    cv.addEventListener('mousemove', function (e) { var g = S.geo; if (!g) return; var r = cv.getBoundingClientRect(), x = e.clientX - r.left, i = Math.round((x - g.padL) / ((g.W - g.padL - g.padR) / (g.n - 1))); S.hover = i >= 0 && i < g.n ? i : -1; });
    cv.addEventListener('mouseleave', function () { S.hover = -1; });
    if ('IntersectionObserver' in window) new IntersectionObserver(function (es) { es.forEach(function (e) { var was = S.vis; S.vis = e.isIntersecting; if (e.isIntersecting && !was && !S.played) { S.played = 1; S.t0 = performance.now(); } }); }, { threshold: .25 }).observe(cv);
    window.addEventListener('uk-theme', function () { frame(); });
  }
  if (!S.raf) S.raf = requestAnimationFrame(loop);
}
window.drawChart = function (d) { start(d); };

/* ---------- heatmap น้ำล้นตลิ่ง รายลำน้ำ × รายวัน (แทนที่ drawHeat) ---------- */
var origHeat = window.drawHeat;
var TIER = function (v) { return v > 0.2 ? { n: 'วิกฤต', c: [224, 82, 82] } : v > 0.05 ? { n: 'เตือน', c: [224, 118, 63] } : v > 0.001 ? { n: 'เฝ้าระวัง', c: [224, 169, 79] } : null; };
window.drawHeat = function (d) {
  var box = document.getElementById('heatContainer'); if (!box) return;
  if (!d.overflow_forecast || !d.overflow_forecast.length) { if (origHeat) origHeat(d); return; }
  var days = d.kwan_forecast.map(function (f) { return f.date; }), nodes = {}, order = [], all = [];
  d.overflow_forecast.forEach(function (r) { if (!nodes[r.node]) { nodes[r.node] = { name: r.name_th, vals: {} }; order.push(r.node); } nodes[r.node].vals[r.date] = r.mcm; all.push({ node: r.node, name: r.name_th, date: r.date, v: r.mcm }); });
  var peak = all.reduce(function (a, b) { return b.v > a.v ? b : a; }), total = all.reduce(function (s, r) { return s + r.v; }, 0), pt = TIER(peak.v);
  var fmt = function (v) { return v < 0.01 ? v.toFixed(3) : v.toFixed(2); }, m3 = function (v) { return Math.round(v * 1e6).toLocaleString('th-TH'); };
  var rows = order.map(function (k) { var vs = days.map(function (dd) { return nodes[k].vals[dd]; }), sum = vs.reduce(function (s, v) { return s + (v || 0); }, 0), mx = Math.max.apply(null, vs.map(function (v) { return v || 0; })); return { k: k, name: nodes[k].name, vs: vs, sum: sum, mx: mx }; }).sort(function (a, b) { return b.sum - a.sum; });
  var h = '<div class="uk-heat"><div class="hh">' +
    '<div class="hs"><span>น้ำล้นรวมทุกลำน้ำ 7 วัน</span><b class="num">' + fmt(total) + '<small> ล้าน ลบ.ม.</small></b><em>≈ ' + m3(total) + ' ลบ.ม.</em></div>' +
    '<div class="hs"><span>วัน/ลำน้ำที่ล้นสูงสุด</span><b class="num">' + fmt(peak.v) + '<small> ล้าน ลบ.ม./วัน</small></b><em>' + peak.name + ' · ' + thd(peak.date) + (pt ? ' · ระดับ' + pt.n : '') + '</em></div>' +
    '<div class="hl"><span class="lg"><i style="--c:224,169,79"></i>เฝ้าระวัง &gt;0.001</span><span class="lg"><i style="--c:224,118,63"></i>เตือน &gt;0.05</span><span class="lg"><i style="--c:224,82,82"></i>วิกฤต &gt;0.2</span><span class="lg dim">ล้านลบ.ม./วัน · ความสูงของน้ำในช่อง = ปริมาณ</span></div></div>' +
    '<div class="hg" style="--n:' + days.length + '"><div class="hr head"><span></span>' + days.map(function (dd) { return '<span>' + thd(dd) + '</span>'; }).join('') + '<span>รวม 7 วัน</span></div>';
  rows.forEach(function (r, ri) {
    h += '<div class="hr"><span class="rn">' + r.name + '</span>';
    r.vs.forEach(function (v, ci) {
      if (v === undefined) { h += '<span class="hc none"><b>·</b></span>'; return; }
      var t = TIER(v), c = t ? t.c : [138, 163, 160], lvl = Math.min(1, Math.sqrt(v / 0.2)), isPk = r.k === peak.node && days[ci] === peak.date;
      h += '<span class="hc' + (isPk ? ' pk' : '') + '" style="--c:' + c.join(',') + ';--l:' + (Math.max(.1, lvl) * 100).toFixed(0) + ';--d:' + ((ri + ci) * 60) + 'ms" title="' + r.name + ' · ' + thd(days[ci]) + ' — ' + fmt(v) + ' ล้าน ลบ.ม. (' + m3(v) + ' ลบ.ม.)' + (t ? ' · ระดับ' + t.n : '') + '"><i></i><b>' + fmt(v) + '</b></span>';
    });
    var tr = TIER(r.mx);
    h += '<span class="rs"><b class="num">' + fmt(r.sum) + '</b><small>ล้าน ลบ.ม.</small><span class="bar"><u style="--w:' + (r.sum / (rows[0].sum || 1) * 100).toFixed(0) + ';--c:' + (tr ? tr.c : [138, 163, 160]).join(',') + '"></u></span></span></div>';
  });
  h += '</div></div>'; box.innerHTML = h;
};
})();
