/* flood-flow-kit.js — เพิ่มบนแผนที่จุดเสี่ยง (flood-forecast #riskMap)
   1) เรดาร์ฝน (RainViewer ย้อนหลัง 2 ชม. ทุก 10 นาที) พร้อมแถบเวลา/เล่น
   2) "น้ำฝนไหลไปไหน": คลิกแผนที่ → ไล่ตามทางลาดชันสุดบน DEM LiDAR (terrain-RGB z13 เฉลี่ย 2×2 = ~18 ม./เซลล์ + Priority-Flood + เจาะแนวลำน้ำ)
      ผ่านลำน้ำ/อ่างที่พบ จนถึงอ่างเก็บน้ำ / กว๊านพะเยา / ที่ลุ่มปิด
   กลับแบบเดิม: ลบ <script src="/__uikit/flood-flow-kit.js"> ออกจาก preview_server.py */
(function () {
'use strict';
if (!document.getElementById('riskMap') || typeof L === 'undefined') return;
var M = null;
L.Map.addInitHook(function () { if (this.getContainer && this.getContainer().id === 'riskMap') M = this; });

var Z = 13, TS = 512, POOL = 2, WORLD = Math.pow(2, Z) * TS, WATER = 385.05, TX0 = 6364, TX1 = 6371, TY0 = 3649, TY1 = 3656;
var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
var NAMES = { 'MaenaruaMain1': 'ห้วยแม่นาเรือ', 'MaenaruaMain2': 'ห้วยจุ๋มปี๋', 'Mae_Branch1': 'เส้นแยก 1', 'KU_main3': 'ห้วยแม่ใส', 'HuaiTham4': 'ห้วยถ้ำ', 'HuaiCho_Main': 'ห้วยโซ้', 'JamTom': 'ห้วยจำตุ้ม', 'So_Branch2': 'ห้วยโซ้ (แยก 2)', 'RongLaeng': 'ห้วยร่องแล้ง', 'RongHai': 'ห้วยร่องไฮ', 'RongPao': 'ห้วยร่องเปา', 'MaeSai_loop3': 'ห้วยแม่ใส', 'BanTun_nat': 'ห้วยตุ่น', 'ChamTum_up1': 'ห้วยจำตุ้ม' };
function thName(n) { if (/^[\d_.]+$/.test(n)) return ''; if (n.indexOf('เส้นน้ำเพิ่มเติม') === 0) return 'ลำน้ำสาขา'; var k = Object.keys(NAMES).filter(function (x) { return n.indexOf(x) >= 0; })[0]; return k ? NAMES[k] : n.replace(/^[\d_.]+/, '') || n; }

/* ---------- พิกัด ↔ พิกเซลโลก (z13 × 512) ---------- */
function toPx(lat, lon) { var s = Math.sin(lat * Math.PI / 180); return [(lon + 180) / 360 * WORLD, (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * WORLD]; }
function toLL(x, y) { var n = Math.PI - 2 * Math.PI * y / WORLD; return [180 / Math.PI * Math.atan(.5 * (Math.exp(n) - Math.exp(-n))), x / WORLD * 360 - 180]; }
var mpp = function (lat) { return 156543.03392 * Math.cos(lat * Math.PI / 180) / (WORLD / 256); };

/* ---------- Priority-Flood (Barnes 2014): ทุกเซลล์ได้ทิศไหลลงปลายทางเสมอ แม้เป็นแอ่ง/ที่ราบ ---------- */
function flowDirs(dem, w, h, seed) {
  var DX = [1, -1, 0, 0, 1, 1, -1, -1], DY = [0, 0, 1, -1, 1, -1, 1, -1], N = w * h, dir = new Int32Array(N).fill(-2), hk = new Float32Array(N), hv = new Int32Array(N), hn = 0, E = 1e-4;
  function push(k, v) { var i = hn++; while (i > 0) { var p = (i - 1) >> 1; if (hk[p] <= k) break; hk[i] = hk[p]; hv[i] = hv[p]; i = p; } hk[i] = k; hv[i] = v; }
  function pop() { var v0 = hv[0], k = hk[--hn], v = hv[hn], i = 0; for (;;) { var c = 2 * i + 1; if (c >= hn) break; if (c + 1 < hn && hk[c + 1] < hk[c]) c++; if (hk[c] >= k) break; hk[i] = hk[c]; hv[i] = hv[c]; i = c; } if (hn) { hk[i] = k; hv[i] = v; } return v0; }
  for (var i = 0; i < N; i++) { var x = i % w, y = (i / w) | 0; if (dem[i] !== dem[i]) { dir[i] = -3; continue; } var edge = seed[i] || x === 0 || y === 0 || x === w - 1 || y === h - 1; if (!edge) { for (var d = 0; d < 8 && !edge; d++) { var nx = x + DX[d], ny = y + DY[d], j = ny * w + nx; if (dem[j] !== dem[j]) edge = true; } } if (edge) { dir[i] = -1; push(dem[i], i); } }
  while (hn) { var c = pop(), cx = c % w, cy = (c / w) | 0, ch = dem[c]; for (var d2 = 0; d2 < 8; d2++) { var xx = cx + DX[d2], yy = cy + DY[d2]; if (xx < 0 || yy < 0 || xx >= w || yy >= h) continue; var j2 = yy * w + xx; if (dir[j2] !== -2) continue; dir[j2] = c; if (dem[j2] <= ch) dem[j2] = ch + E; push(dem[j2], j2); } }
  return dir;
}

/* ---------- เตรียมกริด ---------- */
var GW = 0, GH = 0, OX = 0, OY = 0, ORIG = null, DIR = null, SEEDKIND = null, RES = [], SEG = {}, PREP = null;
function decodeTile(tx, ty) {
  return new Promise(function (res) {
    var im = new Image(); im.onload = function () {
      try { var cv = document.createElement('canvas'); cv.width = cv.height = TS; var cx = cv.getContext('2d', { willReadFrequently: true }); cx.drawImage(im, 0, 0, TS, TS); var d = cx.getImageData(0, 0, TS, TS).data, h = new Float32Array(TS * TS); for (var i = 0, j = 0; j < h.length; i += 4, j++) h[j] = -10000 + (d[i] * 65536 + d[i + 1] * 256 + d[i + 2]) * .1; res(h); } catch (e) { res(null); }
    };
    im.onerror = function () { res(null); }; im.src = 'assets/data/terrain/' + Z + '/' + tx + '/' + ty + '.png';
  });
}
function inRes(x, y) {
  for (var i = 0; i < RES.length; i++) { var r = RES[i]; if (x < r.b[0] || x > r.b[2] || y < r.b[1] || y > r.b[3]) continue; var inside = false, g = r.ring; for (var a = 0, b = g.length - 1; a < g.length; b = a++) if ((g[a][1] > y) !== (g[b][1] > y) && x < (g[b][0] - g[a][0]) * (y - g[a][1]) / (g[b][1] - g[a][1]) + g[a][0]) inside = !inside; if (inside) return r.name; }
  return null;
}
function nearCanal(x, y, R) {
  var best = null, bd = R * R, c0 = Math.floor(x / 64), r0 = Math.floor(y / 64);
  for (var i = -1; i <= 1; i++) for (var j = -1; j <= 1; j++) { var l = SEG[(c0 + i) + ',' + (r0 + j)]; if (!l) continue; l.forEach(function (s) { var dx = s.b[0] - s.a[0], dy = s.b[1] - s.a[1], t = Math.max(0, Math.min(1, ((x - s.a[0]) * dx + (y - s.a[1]) * dy) / (dx * dx + dy * dy || 1))), px = s.a[0] + t * dx - x, py = s.a[1] + t * dy - y, d = px * px + py * py; if (d < bd) { bd = d; best = s.n; } }); }
  return best;
}
function prepare(onProg) {
  if (PREP) return PREP;
  return PREP = Promise.all([fetch('assets/data/wmb_reservoirs7.geojson.json').then(function (r) { return r.json(); }), fetch('assets/data/wmb_canals.geojson.json').then(function (r) { return r.json(); })]).then(function (g) {
    g[0].features.forEach(function (f) { var ring = f.geometry.coordinates[0].map(function (c) { return toPx(c[1], c[0]); }), b = [1e12, 1e12, -1, -1]; ring.forEach(function (p) { b = [Math.min(b[0], p[0]), Math.min(b[1], p[1]), Math.max(b[2], p[0]), Math.max(b[3], p[1])]; }); RES.push({ name: f.properties.Name_T, ring: ring, b: b }); });
    var lines = [];
    g[1].features.forEach(function (f) { var nm = thName(f.properties.name) || '', pts = f.geometry.coordinates.map(function (c) { return toPx(c[1], c[0]); }); lines.push(pts); for (var i = 0; i < pts.length - 1; i++) { var s = { n: nm, a: pts[i], b: pts[i + 1] }, x0 = Math.floor(Math.min(s.a[0], s.b[0]) / 64), x1 = Math.floor(Math.max(s.a[0], s.b[0]) / 64), y0 = Math.floor(Math.min(s.a[1], s.b[1]) / 64), y1 = Math.floor(Math.max(s.a[1], s.b[1]) / 64); for (var x = x0; x <= x1; x++) for (var y = y0; y <= y1; y++) (SEG[x + ',' + y] = SEG[x + ',' + y] || []).push(s); } });
    var jobs = [], tw = TX1 - TX0 + 1, th = TY1 - TY0 + 1; for (var ty = TY0; ty <= TY1; ty++) for (var tx = TX0; tx <= TX1; tx++) jobs.push(decodeTile(tx, ty));
    return Promise.all(jobs).then(function (T) {
      GW = tw * TS / POOL; GH = th * TS / POOL; OX = TX0 * TS / POOL; OY = TY0 * TS / POOL; var dem = new Float32Array(GW * GH).fill(NaN), seed = new Uint8Array(GW * GH);
      T.forEach(function (t, n) { if (!t) return; var tx = n % tw, ty = (n / tw) | 0; for (var cy = 0; cy < TS / POOL; cy++) for (var cx = 0; cx < TS / POOL; cx++) { var sum = 0, wc = 0, c = 0; for (var a = 0; a < POOL; a++) for (var b = 0; b < POOL; b++) { var v = t[(cy * POOL + a) * TS + cx * POOL + b]; if (v > 1) { sum += v; c++; if (v <= WATER) wc++; } } var gi = (ty * TS / POOL + cy) * GW + tx * TS / POOL + cx; if (c) { dem[gi] = sum / c; if (wc * 2 >= c) { seed[gi] = 1; } } } });
      ORIG = Float32Array.from(dem); SEEDKIND = seed;
      // อ่างเก็บน้ำ = ปลายทาง (seed 2)
      RES.forEach(function (r) { var x0 = Math.max(0, Math.floor(r.b[0] / POOL) - OX), x1 = Math.min(GW - 1, Math.ceil(r.b[2] / POOL) - OX), y0 = Math.max(0, Math.floor(r.b[1] / POOL) - OY), y1 = Math.min(GH - 1, Math.ceil(r.b[3] / POOL) - OY); for (var y = y0; y <= y1; y++) for (var x = x0; x <= x1; x++) if (inRes((x + OX + .5) * POOL, (y + OY + .5) * POOL)) seed[y * GW + x] = 2; });
      // เจาะ (burn) แนวลำน้ำลง 3 ม. ให้น้ำไหลตามลำน้ำ/ข้ามถนนที่ DEM มองไม่เห็นท่อลอด
      lines.forEach(function (pts) { for (var i = 0; i < pts.length - 1; i++) { var a = pts[i], b = pts[i + 1], n = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / (POOL * .5)) || 1; for (var k = 0; k <= n; k++) { var x = Math.floor((a[0] + (b[0] - a[0]) * k / n) / POOL) - OX, y = Math.floor((a[1] + (b[1] - a[1]) * k / n) / POOL) - OY; if (x < 0 || y < 0 || x >= GW || y >= GH) continue; var gi = y * GW + x; if (dem[gi] === dem[gi] && !seed[gi]) dem[gi] -= 3; } } });
      return runFlow(dem, seed);
    });
  }).then(function (d) { DIR = d; return true; });
}
function runFlow(dem, seed) {
  var src = flowDirs.toString();
  if (typeof Worker !== 'undefined' && typeof Blob !== 'undefined' && typeof URL !== 'undefined' && URL.createObjectURL) {
    try {
      var blob = new Blob([src + ';onmessage=function(e){var d=e.data;var r=flowDirs(d.dem,d.w,d.h,d.seed);postMessage(r,[r.buffer])};'], { type: 'text/javascript' }), wk = new Worker(URL.createObjectURL(blob));
      return new Promise(function (res, rej) { wk.onmessage = function (e) { res(e.data); wk.terminate(); }; wk.onerror = function () { wk.terminate(); try { res(flowDirs(dem, GW, GH, seed)); } catch (e) { rej(e); } }; wk.postMessage({ dem: dem, w: GW, h: GH, seed: seed }, [dem.buffer.slice ? dem.buffer : dem.buffer]); });
    } catch (e) { /* ใช้ main thread */ }
  }
  return Promise.resolve(flowDirs(dem, GW, GH, seed));
}

function traceFrom(lat, lon) {
  var p = toPx(lat, lon), cx = Math.floor(p[0] / POOL) - OX, cy = Math.floor(p[1] / POOL) - OY;
  if (cx < 0 || cy < 0 || cx >= GW || cy >= GH || ORIG[cy * GW + cx] !== ORIG[cy * GW + cx]) return { err: 'จุดนี้อยู่นอกขอบเขตข้อมูลภูมิประเทศ (DEM)' };
  var i = cy * GW + cx, pts = [], canals = [], steps = 0, h0 = ORIG[i];
  while (steps++ < 6000) {
    var x = i % GW, y = (i / GW) | 0, wx = (x + OX + .5) * POOL, wy = (y + OY + .5) * POOL; pts.push([wx, wy, ORIG[i]]);
    var cn = nearCanal(wx, wy, 1.2 * POOL); if (cn && canals.indexOf(cn) < 0) canals.push(cn);
    var d = DIR[i]; if (d < 0) break; i = d;
  }
  var last = pts[pts.length - 1], li = ((Math.floor(last[1] / POOL) - OY) * GW) + Math.floor(last[0] / POOL) - OX, end;
  if (SEEDKIND[li] === 2) end = { t: 'res', th: inRes(last[0], last[1]) || 'อ่างเก็บน้ำ' };
  else if (SEEDKIND[li] === 1) end = { t: 'kwan', th: 'กว๊านพะเยา / ผืนน้ำขนาดใหญ่' };
  else if (DIR[li] === -1) end = { t: 'edge', th: 'ออกนอกขอบเขตข้อมูลภูมิประเทศ (ไหลต่อออกนอกพื้นที่)' };
  else end = { t: 'far', th: 'ยังไม่ถึงปลายทางในระยะที่คำนวณ' };
  var m = mpp(toLL(pts[0][0], pts[0][1])[0]), len = 0; for (var k = 1; k < pts.length; k++) len += Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]) * m;
  return { pts: pts, len: len, h0: h0, h1: last[2], canals: canals, end: end };
}
async function trace(lat, lon) { await prepare(); return traceFrom(lat, lon); }
/* API ให้ kit อื่น (3D / ย่านของฉัน) ใช้ร่วมกัน */
window.__ukFlow = {
  trace: function (lat, lon) { return trace(lat, lon).then(function (r) { if (!r.err) r.ll = smooth(r.pts); return r; }); },
  ready: function () { return prepare(); },
  grid: function () { return prepare().then(function () { return { orig: ORIG, seed: SEEDKIND, w: GW, h: GH, ox: OX, oy: OY, pool: POOL, world: WORLD }; }); },
  html: function (r) { return cardBody(r); },
  run2d: function (lat, lng) { if (!M || !card) return; if (!flowOn) setFlow(true); onClick({ latlng: { lat: lat, lng: lng } }); }
};

/* ---------- วาด/เคลื่อนไหว ---------- */
var traces = [], flowOn = false, card = null, bar, radar = null;
function smooth(pts) {
  var s = pts.filter(function (_, i) { return i % 3 === 0 || i === pts.length - 1; }), o = s.map(function (p, i) { var a = s[Math.max(0, i - 1)], b = s[Math.min(s.length - 1, i + 1)]; return i === 0 || i === s.length - 1 ? p : [(a[0] + p[0] * 2 + b[0]) / 4, (a[1] + p[1] * 2 + b[1]) / 4]; });
  return o.map(function (p) { return toLL(p[0], p[1]); });
}
var dropIcon = L.divIcon({ className: 'fft-wrap', html: '<div class="fft-drop"></div>', iconSize: [0, 0] });
function draw(r) {
  var ll = smooth(r.pts), grp = L.layerGroup().addTo(M), under = L.polyline([], { color: '#fff', weight: 7, opacity: .55, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(grp), line = L.polyline([], { color: '#1d9bf0', weight: 4, opacity: .95, lineCap: 'round', lineJoin: 'round', className: 'fft-line', interactive: false }).addTo(grp), drop = L.marker(ll[0], { icon: dropIcon, interactive: false, zIndexOffset: 1500 }).addTo(grp);
  traces.push(grp);
  var seg = [0]; for (var i = 1; i < ll.length; i++) seg[i] = seg[i - 1] + Math.hypot(ll[i][0] - ll[i - 1][0], ll[i][1] - ll[i - 1][1]);
  var total = seg[seg.length - 1] || 1, dur = Math.min(5200, 1800 + r.len / 4), t0 = null, reduced = matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.classList.contains('uk-reduce');
  function frame(ts) {
    if (!M.hasLayer(grp)) return; if (t0 == null) t0 = ts; var f = reduced ? 1 : Math.min(1, (ts - t0) / dur), e = f * f * (3 - 2 * f), d = e * total, j = 1; while (j < seg.length - 1 && seg[j] < d) j++;
    var part = ll.slice(0, j); var a = ll[j - 1], b = ll[j], u = (d - seg[j - 1]) / ((seg[j] - seg[j - 1]) || 1), cur = [a[0] + (b[0] - a[0]) * Math.min(1, u), a[1] + (b[1] - a[1]) * Math.min(1, u)]; part.push(cur);
    under.setLatLngs(part); line.setLatLngs(part); drop.setLatLng(cur);
    if (f < 1) requestAnimationFrame(frame); else finish();
  }
  function finish() {
    grp.removeLayer(drop);
    L.marker(ll[0], { icon: L.divIcon({ className: 'fft-wrap', html: '<div class="fft-st"></div>', iconSize: [0, 0] }), interactive: false }).addTo(grp);
    var endc = { kwan: '#1d9bf0', res: '#2a9d8f', pit: '#e0a94f', edge: '#8aa3a0', far: '#8aa3a0' }[r.end.t];
    L.marker(ll[ll.length - 1], { icon: L.divIcon({ className: 'fft-wrap', html: '<div class="fft-en" style="--c:' + endc + '"><s></s></div>', iconSize: [0, 0] }), interactive: false }).addTo(grp);
    L.polyline(ll, { color: '#fff', weight: 2, opacity: .9, dashArray: '1 12', lineCap: 'round', className: 'fft-flow', interactive: false }).addTo(grp);
  }
  requestAnimationFrame(frame);
  showCard(r);
}
function cardBody(r) {
  var drop = r.h0 - r.h1, route = r.canals.length ? r.canals.map(esc).join(' → ') + ' → ' : '';
  return '<div class="t">หยดน้ำฝนจุดนี้ไหลไปไหน</div>' +
    '<div class="r"><span>เริ่มที่ความสูง</span><b>' + r.h0.toFixed(1) + ' ม.รทก.</b></div>' +
    '<div class="r"><span>เส้นทาง</span><b>' + route + esc(r.end.th) + '</b></div>' +
    '<div class="r"><span>ระยะทาง · ลดระดับ</span><b>' + (r.len / 1000).toFixed(2) + ' กม. · ' + (drop > 0 ? drop.toFixed(1) : '0') + ' ม.</b></div>' +
    '<div class="n">ประมาณจาก DEM LiDAR (เฉลี่ย ~18 ม./เซลล์) ไหลตามทางลาดชันสุด และให้ไหลตามแนวลำน้ำของโครงการ — ไม่รวมคันนา/ท่อลอด/ประตูน้ำจริง</div>';
}
var lastLL = null;
function showCard(r) {
  card.innerHTML = '<button type="button" class="x" title="ปิด">×</button>' + cardBody(r) + '<div class="a"><button type="button" class="lnk">คัดลอกลิงก์จุดนี้</button><button type="button" class="clr">ล้างเส้นทาง</button></div>';
  card.classList.add('show');
  card.querySelector('.x').onclick = function () { card.classList.remove('show'); };
  card.querySelector('.clr').onclick = clearAll;
  card.querySelector('.lnk').onclick = function () {
    var b = this, u = location.href.split('#')[0] + '#flow=' + lastLL[0].toFixed(5) + ',' + lastLL[1].toFixed(5);
    var ok = function () { b.textContent = 'คัดลอกแล้ว ✓'; setTimeout(function () { b.textContent = 'คัดลอกลิงก์จุดนี้'; }, 1800); };
    try { navigator.clipboard.writeText(u).then(ok, function () { prompt('คัดลอกลิงก์นี้', u); }); } catch (e) { prompt('คัดลอกลิงก์นี้', u); }
  };
}
function clearAll() { traces.forEach(function (g) { M.removeLayer(g); }); traces = []; card.classList.remove('show'); }

function onClick(e) {
  if (!flowOn) return; M.closePopup();
  var ll = e.latlng; lastLL = [ll.lat, ll.lng]; card.innerHTML = '<div class="t">กำลังไล่ตามทางลาด…</div>'; card.classList.add('show');
  clearAll(); card.innerHTML = '<div class="t">กำลังไล่ตามทางลาด…</div>'; card.classList.add('show');
  trace(ll.lat, ll.lng).then(function (r) { if (r.err) { card.innerHTML = '<button type="button" class="x">×</button><div class="t">' + esc(r.err) + '</div>'; card.querySelector('.x').onclick = function () { card.classList.remove('show'); }; return; } draw(r); }).catch(function (er) { console.warn('flow', er); card.classList.remove('show'); });
}
function setFlow(on) {
  flowOn = on; M.getContainer().classList.toggle('fft-aim', on); bar.querySelector('[data-b=flow]').classList.toggle('on', on);
  document.getElementById('fftHint').classList.toggle('show', on && !traces.length);
  if (!on) { clearAll(); } else {
    hintOnce();
    if (!PREP) { card.innerHTML = '<div class="t">กำลังเตรียมข้อมูลภูมิประเทศและทิศทางไหลของน้ำ… (ครั้งแรก ~5–10 วินาที)</div>'; card.classList.add('show'); }
    prepare().then(function () { if (!traces.length) card.classList.remove('show'); }).catch(function (e) { console.warn('flow prepare', e); card.innerHTML = '<button type="button" class="x">×</button><div class="t">เตรียมข้อมูลภูมิประเทศไม่สำเร็จ</div>'; card.querySelector('.x').onclick = function () { card.classList.remove('show'); }; });
  }
}
function hintOnce() { var h = document.getElementById('fftHint'); h.classList.add('show'); setTimeout(function () { h.classList.remove('show'); }, 5000); }

/* ---------- เรดาร์ฝน ---------- */
function radarInit() {
  return fetch('https://api.rainviewer.com/public/weather-maps.json').then(function (r) { return r.json(); }).then(function (j) {
    var fr = (j.radar && j.radar.past) || []; if (!fr.length) throw 0;
    var layers = fr.map(function (f) { return L.tileLayer(j.host + f.path + '/512/{z}/{x}/{y}/2/1_1.png', { tileSize: 512, zoomOffset: -1, maxNativeZoom: 8, maxZoom: 18, opacity: 0, attribution: 'Radar © RainViewer', className: 'ffr-tile' }); });
    return { fr: fr, layers: layers, i: fr.length - 1, timer: null };
  });
}
function radarShow(i) {
  radar.layers.forEach(function (l, k) { l.setOpacity(k === i ? .72 : 0); }); radar.i = i;
  var t = new Date(radar.fr[i].time * 1000), el = document.getElementById('fftRt'); el.textContent = t.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Bangkok' }) + ' น.' + (i === radar.fr.length - 1 ? ' (ล่าสุด)' : '');
  document.getElementById('fftRs').value = i;
}
function radarPlay(on) {
  var b = document.getElementById('fftRp'); if (radar.timer) { clearInterval(radar.timer); radar.timer = null; } b.textContent = on ? '⏸' : '▶';
  if (on) radar.timer = setInterval(function () { radarShow((radar.i + 1) % radar.fr.length); }, 650);
}
function setRadar(on) {
  var btn = bar.querySelector('[data-b=radar]'), box = document.getElementById('fftRadar');
  if (on) {
    btn.classList.add('on'); box.classList.add('show', 'load');
    (radar ? Promise.resolve(radar) : radarInit().then(function (r) { radar = r; var s = document.getElementById('fftRs'); s.max = r.fr.length - 1; return r; })).then(function (r) {
      box.classList.remove('load'); r.layers.forEach(function (l) { l.addTo(M); }); radarShow(r.i); radarPlay(true);
    }).catch(function () { box.classList.remove('load'); document.getElementById('fftRt').textContent = 'โหลดเรดาร์ไม่ได้ (ต้องต่ออินเทอร์เน็ต)'; });
  } else {
    btn.classList.remove('on'); box.classList.remove('show'); if (radar) { radarPlay(false); radar.layers.forEach(function (l) { M.removeLayer(l); }); }
  }
}

function start() {
  var Ctl = L.Control.extend({ options: { position: 'bottomright' }, onAdd: function () {
    var d = L.DomUtil.create('div', 'fft-bar'); bar = d;
    d.innerHTML = '<button type="button" data-b="radar"><svg viewBox="0 0 24 24"><path d="M7 18a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 17 9a3.5 3.5 0 0 1 .5 6.96M8 21l1-3M12 21l1-3M16 21l1-3"/></svg>เรดาร์ฝน</button><button type="button" data-b="flow"><svg viewBox="0 0 24 24"><path d="M12 3c3 4.2 5 7 5 10a5 5 0 0 1-10 0c0-3 2-5.8 5-10z"/></svg>น้ำฝนไหลไปไหน</button>';
    L.DomEvent.disableClickPropagation(d);
    d.querySelector('[data-b=radar]').onclick = function () { setRadar(!this.classList.contains('on')); };
    d.querySelector('[data-b=flow]').onclick = function () { setFlow(!flowOn); };
    return d; } });
  new Ctl().addTo(M);
  var c = M.getContainer(); c.style.position = c.style.position || 'relative';
  var wrap = document.createElement('div'); wrap.innerHTML =
    '<div class="fft-card" id="fftCard"></div><div class="fft-hint" id="fftHint">คลิกบนแผนที่ตรงจุดที่ต้องการ เพื่อปล่อยหยดน้ำฝนแล้วดูว่าไหลไปไหน</div>' +
    '<div class="fft-radar" id="fftRadar"><button type="button" id="fftRp">⏸</button><input type="range" id="fftRs" min="0" max="11" value="11"><span id="fftRt">กำลังโหลด…</span><i class="lg"></i><small>เบา → หนัก · RainViewer ย้อนหลัง 2 ชม. ความละเอียดต่ำ</small></div>';
  while (wrap.firstChild) c.appendChild(wrap.firstChild);
  card = document.getElementById('fftCard');
  ['fftCard', 'fftRadar'].forEach(function (id) { var e = document.getElementById(id); L.DomEvent.disableClickPropagation(e); L.DomEvent.disableScrollPropagation(e); });
  document.getElementById('fftRp').onclick = function () { radarPlay(!radar.timer); };
  document.getElementById('fftRs').oninput = function () { radarPlay(false); radarShow(+this.value); };
  M.on('click', onClick);
  var hm = /flow=(-?[\d.]+),(-?[\d.]+)/.exec(location.hash);
  if (hm) setTimeout(function () { try { c.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) {} M.setView([+hm[1], +hm[2]], 14); window.__ukFlow.run2d(+hm[1], +hm[2]); }, 1200);
}
var tries = 0, iv = setInterval(function () { tries++; if (M) { clearInterval(iv); try { start(); } catch (e) { console.warn('flood-flow-kit', e); } } else if (tries > 80) clearInterval(iv); }, 300);
})();
