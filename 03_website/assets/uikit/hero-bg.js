/* hero-bg.js — เลเยอร์พื้นหลังจางๆ ของ hero หน้าแรก (ตัวอย่างให้เลือก/ตัดทีละชั้น) — 6 ชั้น:
   1 ลำห้วย  2 เทือกเขา (เส้นชั้นความสูงจริงจาก LiDAR DTM)  3 ผืนนา  4 ฝนแสนห่า  5 เจดีย์พระธาตุภูขวาง+หลักศิลา  6 เรือ  */
(function () {
'use strict';
var hero = document.querySelector('.hero'); if (!hero || !hero.querySelector('.hero-art')) return;
var NS = 'http://www.w3.org/2000/svg';
var root = document.documentElement;
var reduced = function () { return root.classList.contains('uk-reduce') || matchMedia('(prefers-reduced-motion: reduce)').matches; };
function rng(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
var el = function (tag, attrs, parent) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
var div = function (cls, parent) { var d = document.createElement('div'); d.className = cls; if (parent) parent.appendChild(d); return d; };

var bg = div('hb'); bg.id = 'ukHeroBg'; hero.insertBefore(bg, hero.firstChild);
var names = { streams: 'ลำห้วย', topo: 'เทือกเขา', fields: 'ผืนนา', stupa: 'เจดีย์พระธาตุภูขวาง', boats: 'เรือ' };
var L = {}; Object.keys(names).forEach(function (k) { L[k] = div('hl hl-' + k, bg); });

/* ---------- 3 ผืนนา ---------- */
(function () {
  var r = rng(7), W = 1200, H = 300, cols = 26, rows = 6, cw = W / cols, rh = H / rows;
  var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' }, div('fz', L.fields));
  var pal = [[111, 186, 120], [214, 170, 80], [226, 140, 60], [150, 160, 70], [170, 120, 160], [232, 205, 100], [111, 186, 120], [150, 160, 70]];
  var V = []; for (var j = 0; j <= rows; j++) { V[j] = []; for (var i = 0; i <= cols; i++) V[j][i] = [i * cw + (i && i < cols ? (r() - .5) * cw * .7 : 0), j * rh + (j && j < rows ? (r() - .5) * rh * .7 : 0)]; }
  var pick = []; for (var a = 0; a < rows; a++) { pick[a] = []; for (var b = 0; b < cols; b++) { var p = r(); pick[a][b] = (b > 0 && p < .5) ? pick[a][b - 1] : (a > 0 && p < .75) ? pick[a - 1][b] : Math.floor(r() * pal.length); } }
  for (var y = 0; y < rows; y++) for (var x = 0; x < cols; x++) {
    var c = pal[pick[y][x]], q = [V[y][x], V[y][x + 1], V[y + 1][x + 1], V[y + 1][x]];
    var pg = el('polygon', { points: q.map(function (v) { return v[0].toFixed(0) + ',' + v[1].toFixed(0); }).join(' '), fill: 'rgba(' + c.join(',') + ',' + (.5 + r() * .35).toFixed(2) + ')', stroke: 'rgba(255,255,255,.55)', 'stroke-width': 1.2 }, svg);
    pg.style.animation = 'hb-grow ' + (5 + r() * 6).toFixed(1) + 's ease-in-out ' + (-r() * 8).toFixed(1) + 's infinite alternate';
    if (pick[y][x] === 3) for (var t = 0; t < 3; t++) el('circle', { cx: (q[0][0] + q[2][0]) / 2 + (t - 1) * 14, cy: (q[0][1] + q[2][1]) / 2 + (r() - .5) * 8, r: 5, fill: 'rgba(90,110,40,.55)' }, svg);
  }
})();

/* ---------- 5 เจดีย์พระธาตุภูขวาง + หลักศิลาจารึก (เส้นนามธรรม ไม่ใช่ตัวอักษรจริง) ---------- */
(function () {
  var svg = el('svg', { viewBox: '0 0 330 330', 'aria-hidden': 'true' }, div('st', L.stupa));
  var g = el('g', { fill: 'none', 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg), P = [];
  var add = function (tag, a) { var e = el(tag, a, g); e.setAttribute('class', 'ln'); P.push(e); return e; };
  [[18, 292, 164, 18], [32, 272, 136, 20], [46, 254, 108, 18], [60, 214, 80, 40], [68, 200, 64, 14], [76, 188, 48, 12]].forEach(function (b) { add('rect', { x: b[0], y: b[1], width: b[2], height: b[3], rx: 2 }); });
  [[46, 254], [154, 254], [32, 272], [168, 272]].forEach(function (c) { add('path', { d: 'M' + (c[0] - 5) + ' ' + c[1] + ' L' + c[0] + ' ' + (c[1] - 16) + ' L' + (c[0] + 5) + ' ' + c[1] }); });
  add('path', { d: 'M80 188 C72 150 82 118 100 102 C118 118 128 150 120 188 Z' });
  [[90, 20], [93, 14], [95, 10]].forEach(function (b, i) { add('rect', { x: b[0], y: 92 - i * 7, width: b[1], height: 6, rx: 2 }); });
  add('path', { d: 'M100 70 V26' });
  [[22, 66], [17, 58], [13, 50], [9, 43], [6, 37]].forEach(function (b) { add('path', { d: 'M' + (100 - b[0]) + ' ' + b[1] + ' H' + (100 + b[0]) }); });
  add('circle', { cx: 100, cy: 22, r: 4 });
  // หลักศิลา
  add('path', { d: 'M232 310 V200 Q232 178 258 178 Q284 178 284 200 V310 Z' });
  for (var k = 0; k < 9; k++) add('path', { d: 'M241 ' + (206 + k * 11) + ' H' + (275 - (k % 3) * 6) });
  P.forEach(function (e, i) { e.style.animationDelay = (i * 60) + 'ms'; });
})();

/* ---------- 6 เรือ ---------- */
(function () {
  var wave = div('wv', L.boats); var s = el('svg', { viewBox: '0 0 1200 60', preserveAspectRatio: 'none' }, wave);
  el('path', { d: 'M0 30 Q50 8 100 30 T200 30 T300 30 T400 30 T500 30 T600 30 T700 30 T800 30 T900 30 T1000 30 T1100 30 T1200 30', fill: 'none', 'stroke-width': 2 }, s);
  var boat = function (cls, scale) {
    var b = div('bt ' + cls, L.boats), sv = el('svg', { viewBox: '0 0 160 70', style: 'width:' + (160 * scale) + 'px' }, b);
    el('path', { d: 'M4 40 Q40 62 82 56 Q124 62 156 36 L146 44 Q84 54 14 46 Z', class: 'hull' }, sv);
    el('path', { d: 'M60 52 Q62 30 70 18', fill: 'none', 'stroke-width': 3, 'stroke-linecap': 'round', class: 'pole' }, sv);   // ไม้ถ่อ
    el('circle', { cx: 100, cy: 24, r: 6, class: 'pc' }, sv);                                                       // คนพาย
    el('path', { d: 'M100 30 Q92 42 90 52 M100 30 Q108 42 112 50 M96 36 L70 20', fill: 'none', 'stroke-width': 3, 'stroke-linecap': 'round', class: 'pl' }, sv);
    return b;
  };
  boat('b1', 1); boat('b2', .65);
})();

/* ---------- 1 ลำห้วย + 2 เทือกเขา (ข้อมูลจริง: LiDAR DTM / เส้นน้ำโครงการ) ---------- */
fetch(((document.currentScript && document.currentScript.src) || '/__uikit/x').replace(/[^\/]*(\?.*)?$/, '') + 'hero_contours.json').then(function (r) { return r.json(); }).then(function (D) {
  function geo(parent) { var g = div('geo', parent); g.style.aspectRatio = D.w + '/' + D.h; return el('svg', { viewBox: '0 0 ' + D.w + ' ' + D.h, 'aria-hidden': 'true' }, g); }
  var s2 = geo(L.topo), n = D.levels.length, lv = {}; D.levels.forEach(function (v, i) { lv[v] = i; });
  var cl = el('clipPath', { id: 'hbClip' }, el('defs', {}, s2)); el('path', { d: 'M' + D.outline.map(function (p) { return p.join(','); }).join('L') + 'Z' }, cl);
  var gg = el('g', { 'clip-path': 'url(#hbClip)' }, s2);
  D.lines.forEach(function (ln) {
    var i = lv[ln[0]], p = el('path', { d: 'M' + ln[1].map(function (q) { return q.join(','); }).join('L'), fill: 'none', pathLength: 1, class: 'ct' + (i % 4 === 0 ? ' mj' : '') }, gg);
    p.style.animationDelay = (i * 90) + 'ms';
  });
  el('path', { d: 'M' + D.outline.map(function (p) { return p.join(','); }).join('L') + 'Z', fill: 'none', class: 'ol' }, s2);
  var s1 = geo(L.streams);
  D.streams.forEach(function (st, i) { var d = 'M' + st.map(function (q) { return q.join(','); }).join('L'); el('path', { d: d, fill: 'none', class: 'sb' }, s1); el('path', { d: d, fill: 'none', class: 'sf', style: 'animation-delay:' + (-i * 0.7) + 's' }, s1); });
  (D.reservoirs || []).forEach(function (c, i) { var g = el('g', { transform: 'translate(' + c.join(' ') + ')' }, s1); el('circle', { r: 16, class: 'rr' }, g); el('circle', { r: 16, class: 'rr r2' }, g); el('circle', { r: 6, class: 'rd' }, g); });
}).catch(function () {});

bg.style.setProperty('--hb', 0.6); /* ความเข้มที่เลือกไว้ */
})();
