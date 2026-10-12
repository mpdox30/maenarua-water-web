/* flood-bathtub-kit.js — "ระดับกว๊านพะเยา → น้ำเข้าถึงที่ไหน" บนแผนที่จุดเสี่ยง (2D #riskMap และ 3D #riskMap3D)
   แบบจำลองอย่างง่าย (bathtub): น้ำจากกว๊านแผ่เข้าพื้นที่ที่ต่ำกว่าระดับน้ำและ "เชื่อมต่อถึงกัน" จาก DEM LiDAR (ผ่าน window.__ukFlow.grid())
   เลือกระดับ: ล่าสุด / พยากรณ์ 7 วัน + สมมติระดับเพิ่ม 0–150 ซม. → พื้นที่ (ตร.กม.) และหมู่บ้านที่โดนมากสุด
   ไม่ใช่ผลแบบจำลองไฮดรอลิก (ไม่รวมคันกั้น/ท่อลอด/ฝนท้องที่) ใช้ประกอบการสื่อสารเท่านั้น
   กลับแบบเดิม: ลบ <script src="/__uikit/flood-bathtub-kit.js"> ออกจาก preview_server.py (ต้องโหลดหลัง flood-flow-kit.js) */
(function () {
'use strict';
var has2d = !!document.getElementById('riskMap'), host3 = document.getElementById('riskMap3D');
if (!has2d) return;
var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
var dshort = function (iso) { var d = new Date(iso + 'T00:00:00'); return isNaN(d) ? iso : d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short' }); };

var M = null, M3 = null, D = null, G = null, VIL = [], src = 'now', add = 0, level = 0, on2 = false, on3 = false, ov = null, url = '', corners = null, timer = null, boxes = [], last = null;
L.Map.addInitHook(function () { if (this.getContainer && this.getContainer().id === 'riskMap') M = this; });

function lvlBase() { if (!D) return 0; if (src === 'now') return D.kwan_now ? D.kwan_now.level : 0; var f = D.kwan_forecast[+src - 1]; return f ? f.level : 0; }

/* ---------- พิกัด ---------- */
function toLL(x, y) { var n = Math.PI - 2 * Math.PI * y / G.world; return [180 / Math.PI * Math.atan(.5 * (Math.exp(n) - Math.exp(-n))), x / G.world * 360 - 180]; }
function toPx(lat, lon) { var s = Math.sin(lat * Math.PI / 180); return [(lon + 180) / 360 * G.world, (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * G.world]; }

/* ---------- เตรียมกริด + หมู่บ้าน ---------- */
function prep() {
  if (G) return Promise.resolve();
  return window.__ukFlow.grid().then(function (g) {
    G = g; var tl = toLL(g.ox * g.pool, g.oy * g.pool), br = toLL((g.ox + g.w) * g.pool, (g.oy + g.h) * g.pool);
    corners = [[tl[1], tl[0]], [br[1], tl[0]], [br[1], br[0]], [tl[1], br[0]]];
    var mpp = 156543.03392 * Math.cos(19.12 * Math.PI / 180) / (g.world / 256) * g.pool; G.cellKm2 = mpp * mpp / 1e6;
    return fetch('assets/data/villages.geojson.json').then(function (r) { return r.json(); }).then(function (v) {
      v.features.forEach(function (f) {
        var polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates, rings = polys.map(function (p) { return p[0].map(function (c) { return toPx(c[1], c[0]); }); }), cells = [], b = [1e12, 1e12, -1, -1];
        rings.forEach(function (r) { r.forEach(function (q) { b = [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[0]), Math.max(b[3], q[1])]; }); });
        var x0 = Math.max(0, Math.floor(b[0] / g.pool) - g.ox), x1 = Math.min(g.w - 1, Math.ceil(b[2] / g.pool) - g.ox), y0 = Math.max(0, Math.floor(b[1] / g.pool) - g.oy), y1 = Math.min(g.h - 1, Math.ceil(b[3] / g.pool) - g.oy);
        for (var y = y0; y <= y1; y++) for (var x = x0; x <= x1; x++) { var wx = (x + g.ox + .5) * g.pool, wy = (y + g.oy + .5) * g.pool, ins = false; for (var k = 0; k < rings.length && !ins; k++) { var r2 = rings[k]; for (var a = 0, c = r2.length - 1; a < r2.length; c = a++) if ((r2[a][1] > wy) !== (r2[c][1] > wy) && wx < (r2[c][0] - r2[a][0]) * (wy - r2[a][1]) / (r2[c][1] - r2[a][1]) + r2[a][0]) ins = !ins; } if (ins) cells.push(y * g.w + x); }
        var ctr = toLL((b[0] + b[2]) / 2, (b[1] + b[3]) / 2); VIL.push({ moo: f.properties.Moo, name: f.properties.Name_TH, cells: Int32Array.from(cells), lat: ctr[0], lon: ctr[1] });
      });
    }).catch(function () {});
  });
}

/* ---------- bathtub ---------- */
function baseLevel() { return D && D.kwan_now ? D.kwan_now.level : 0; }
var OUT0 = null;
function flood(L0) {
  var w = G.w, h = G.h, N = w * h, o = G.orig, out = new Uint8Array(N), q = new Int32Array(N), hd = 0, tl = 0;
  for (var i = 0; i < N; i++) if (G.seed[i] === 1) { out[i] = 2; q[tl++] = i; }
  while (hd < tl) {
    var c = q[hd++], x = c % w, y = (c / w) | 0, j;
    if (x > 0) { j = c - 1; if (!out[j] && o[j] <= L0) { out[j] = 1; q[tl++] = j; } }
    if (x < w - 1) { j = c + 1; if (!out[j] && o[j] <= L0) { out[j] = 1; q[tl++] = j; } }
    if (y > 0) { j = c - w; if (!out[j] && o[j] <= L0) { out[j] = 1; q[tl++] = j; } }
    if (y < h - 1) { j = c + w; if (!out[j] && o[j] <= L0) { out[j] = 1; q[tl++] = j; } }
  }
  return out;
}
/* ส่วนที่น้ำ "เข้าไปเพิ่ม" = พื้นที่ที่สูงกว่าระดับล่าสุด (B) แต่ไม่เกินระดับที่เลือก (L0) และต่อเนื่องจากผืนน้ำกว๊านเดิม
   (ไม่นับแอ่งต่ำที่อยู่ต่ำกว่า B แต่ไม่เชื่อมกับกว๊าน เช่น ร่องน้ำท้ายน้ำ เพราะน้ำจะไหลลงไปไม่ใช่ท่วมขังเท่าระดับกว๊าน) */
function compute(L0) {
  var w = G.w, h = G.h, o = G.orig, N = o.length, B = baseLevel(); if (!OUT0) OUT0 = flood(B);
  var out = new Uint8Array(N), q = new Int32Array(N), hd = 0, tl = 0, cnt0 = 0, ext = 0, mx = 0;
  for (var i = 0; i < N; i++) if (OUT0[i]) { out[i] = OUT0[i]; q[tl++] = i; if (OUT0[i] === 1) cnt0++; }
  if (L0 > B) while (hd < tl) {
    var c = q[hd++], x = c % w, y = (c / w) | 0, j;
    if (x > 0) { j = c - 1; if (!out[j] && o[j] > B && o[j] <= L0) { out[j] = 3; q[tl++] = j; } }
    if (x < w - 1) { j = c + 1; if (!out[j] && o[j] > B && o[j] <= L0) { out[j] = 3; q[tl++] = j; } }
    if (y > 0) { j = c - w; if (!out[j] && o[j] > B && o[j] <= L0) { out[j] = 3; q[tl++] = j; } }
    if (y < h - 1) { j = c + w; if (!out[j] && o[j] > B && o[j] <= L0) { out[j] = 3; q[tl++] = j; } }
  }
  for (var k = 0; k < N; k++) if (out[k] === 3) { ext++; var d = L0 - o[k]; if (d > mx) mx = d; }
  var vs = VIL.map(function (v) { var n = 0; for (var m = 0; m < v.cells.length; m++) if (out[v.cells[m]] === 3) n++; return { v: v, pct: v.cells.length ? n / v.cells.length * 100 : 0, km2: n * G.cellKm2 }; }).filter(function (r) { return r.km2 > 0.0005; }).sort(function (a, b) { return b.pct - a.pct; });
  return { out: out, km2: cnt0 * G.cellKm2, extKm2: ext * G.cellKm2, maxd: mx, vs: vs, base: B };
}
var cv = document.createElement('canvas');
function render(r, L0) {
  cv.width = G.w; cv.height = G.h; var cx = cv.getContext('2d'), im = cx.createImageData(G.w, G.h), d = im.data, o = G.orig, out = r.out, B = r.base;
  for (var i = 0, n = out.length; i < n; i++) if (out[i] === 1 || out[i] === 3) {
    var p = i * 4;
    if (out[i] === 1) { d[p] = 110; d[p + 1] = 190; d[p + 2] = 235; d[p + 3] = 70; }                       // ผืนน้ำกว๊านที่ระดับล่าสุด (พื้นฐาน)
    else { var dep = Math.min(1, (L0 - o[i]) / 1.5); d[p] = 255; d[p + 1] = 190 - dep * 120; d[p + 2] = 60 - dep * 20; d[p + 3] = 170 + dep * 70; }   // น้ำที่เข้าไปเพิ่ม
  }
  cx.putImageData(im, 0, 0); return cv.toDataURL('image/png');
}

/* ---------- ปรับใช้กับแผนที่ ---------- */
function calc() { level = lvlBase() + add / 100; var r = compute(level); url = render(r, level); last = r; boxes.forEach(function (b) { fill(b, r); }); }
function apply() {
  if (!G) return;
  setTimeout(function () {
    try { calc(); if (ov) ov.setUrl(url); if (M3 && on3) put3d(); } catch (e) { console.warn('bathtub', e); }
  }, 30);
}
function fill(b, r) {
  var df = level - r.base;
  b.querySelector('.st').innerHTML = 'ระดับที่ใช้ <b>' + level.toFixed(2) + '</b> ม.รทก. (' + (df >= 0 ? '+' : '') + df.toFixed(2) + ' จากระดับล่าสุด ' + r.base.toFixed(2) + ')<br>ผืนน้ำกว๊านรวม ~' + r.km2.toFixed(1) + ' ตร.กม. · ' + (r.extKm2 > 0.0005 ? 'น้ำเข้าไปเพิ่ม <b>' + r.extKm2.toFixed(2) + '</b> ตร.กม. (ลึกสุด ~' + r.maxd.toFixed(1) + ' ม.)' : '<b>ไม่มีพื้นที่เพิ่มจากระดับล่าสุด</b>');
  b.querySelector('.vl').innerHTML = r.vs.length ? '<span>หมู่บ้านที่น้ำเข้าไปเพิ่มมากสุด (% ของพื้นที่หมู่บ้าน)</span>' + r.vs.slice(0, 5).map(function (x) { return '<button type="button" data-i="' + VIL.indexOf(x.v) + '"><em>หมู่ ' + x.v.moo + ' ' + esc(x.v.name) + '</em><b>' + x.pct.toFixed(0) + '%</b></button>'; }).join('') : '<span>ไม่มีหมู่บ้านที่น้ำเข้าไปเพิ่มที่ระดับนี้</span>';
}
function buildBox(kind) {
  var b = document.createElement('div'); b.className = 'fbt-box ' + kind;
  var opts = '<option value="now">ระดับล่าสุด' + (D.kwan_now ? ' (' + D.kwan_now.level.toFixed(2) + ' ม.)' : '') + '</option>' + D.kwan_forecast.map(function (f, i) { return '<option value="' + (i + 1) + '">พยากรณ์ วันที่ ' + (i + 1) + ' · ' + dshort(f.date) + ' (' + f.level.toFixed(2) + ')</option>'; }).join('');
  b.innerHTML = '<button type="button" class="x" title="ปิด">×</button><div class="t">ระดับกว๊านพะเยา → น้ำเข้าถึงที่ไหน</div><select class="src">' + opts + '</select>' +
    '<label>สมมติให้กว๊านสูงขึ้นอีก <b class="av">0</b> ซม.<input type="range" class="add" min="0" max="150" step="10" value="0"></label><div class="st">กำลังเตรียมข้อมูลภูมิประเทศ… (ครั้งแรก ~5–10 วินาที)</div><div class="vl"></div>' +
    '<div class="n"><i style="background:rgb(110,190,235)"></i>ผืนน้ำกว๊านที่ระดับล่าสุด <i style="background:#ffb23c"></i>น้ำที่เข้าไปเพิ่ม<br>แบบจำลองอย่างง่าย (bathtub): น้ำจากกว๊านแผ่เข้าพื้นที่ที่ต่ำกว่าระดับน้ำและเชื่อมต่อถึงกัน จาก DEM LiDAR ~18 ม./เซลล์ ไม่รวมคันกั้น/ท่อลอด/ฝนท้องที่ — ไม่ใช่ผลแบบจำลองไฮดรอลิก ใช้ประกอบเท่านั้น</div>';
  ['mousedown', 'dblclick', 'wheel', 'touchstart', 'click'].forEach(function (ev) { b.addEventListener(ev, function (e) { e.stopPropagation(); }); });
  b.querySelector('.src').onchange = function () { src = this.value; sync(); apply(); };
  b.querySelector('.add').oninput = function () { add = +this.value; sync(); clearTimeout(timer); timer = setTimeout(apply, 160); };
  b.querySelector('.vl').onclick = function (e) { var t = e.target.closest('button'); if (!t) return; var v = VIL[+t.dataset.i]; if (!v) return; if (kind === 'd2' && M) M.flyTo([v.lat, v.lon], 14, { duration: .9 }); else if (M3) M3.flyTo({ center: [v.lon, v.lat], zoom: 14.6, pitch: 60, duration: 1500 }); };
  b.querySelector('.x').onclick = function () { (kind === 'd2' ? set2d : set3d)(false); };
  boxes.push(b); return b;
}
function sync() { boxes.forEach(function (b) { b.querySelector('.src').value = src; b.querySelector('.add').value = add; b.querySelector('.av').textContent = add; }); }

function ensure(then) {
  if (!window.__ukFlow || !window.__ukFlow.grid) { boxes.forEach(function (b) { b.querySelector('.st').textContent = 'ตัวคำนวณภูมิประเทศยังไม่พร้อม'; }); return; }
  prep().then(function () { calc(); then(); }).catch(function (e) { console.warn('bathtub prep', e); boxes.forEach(function (b) { b.querySelector('.st').textContent = 'เตรียมข้อมูลภูมิประเทศไม่สำเร็จ'; }); });
}
var box2, box3, btn2, btn3;
function set2d(on) {
  on2 = on; btn2.classList.toggle('on', on); box2.classList.toggle('show', on);
  if (on) ensure(function () { if (!ov) ov = L.imageOverlay(url || 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==', [[corners[2][1], corners[0][0]], [corners[0][1], corners[1][0]]], { opacity: .85, interactive: false }); ov.addTo(M); if (url) ov.setUrl(url); });
  else if (ov) M.removeLayer(ov);
}
/* รีเฟรชภาพใน 3D โดยสร้าง source/layer ใหม่ (ไม่ใช้ updateImage) */
var btLayer = null;
function put3d() {
  var T = window.__ukImgTiles; if (!T || !T.ready()) return;
  var before = M3.getLayer('reservoirs-fill') ? 'reservoirs-fill' : undefined, old = btLayer;
  btLayer = T.add(M3, 'bt', url, { w: corners[0][0], n: corners[0][1], e: corners[2][0], s: corners[2][1] }, .85, before);
  if (old) setTimeout(function () { T.remove(M3, old); }, 600);
}
function set3d(on) {
  on3 = on; btn3.classList.toggle('on', on); box3.classList.toggle('show', on);
  if (on) ensure(function () { put3d(); });
  else if (M3 && btLayer && window.__ukImgTiles) { window.__ukImgTiles.remove(M3, btLayer); btLayer = null; }
}

function start2d() {
  box2 = buildBox('d2'); M.getContainer().appendChild(box2);
  var Ctl = L.Control.extend({ options: { position: 'bottomright' }, onAdd: function () { var d = L.DomUtil.create('div', 'fbt-bar'); d.innerHTML = '<button type="button">ระดับกว๊านท่วมถึงไหน</button>'; L.DomEvent.disableClickPropagation(d); btn2 = d.querySelector('button'); btn2.onclick = function () { set2d(!on2); }; return d; } });
  new Ctl().addTo(M);
}
function start3d() {
  box3 = buildBox('d3'); host3.appendChild(box3);
  btn3 = document.createElement('button'); btn3.type = 'button'; btn3.className = 'fbt-btn3'; btn3.textContent = 'ระดับกว๊านท่วมถึงไหน'; host3.appendChild(btn3);
  ['mousedown', 'dblclick', 'wheel', 'touchstart'].forEach(function (ev) { btn3.addEventListener(ev, function (e) { e.stopPropagation(); }); });
  btn3.onclick = function () { set3d(!on3); };
}

window.__ukBath = { get villages() { return VIL; }, get last() { return last; } };
fetch('assets/data/flood_latest.json').then(function (r) { return r.json(); }).then(function (j) { D = j; }).catch(function () {});
var t2 = 0, i2 = setInterval(function () { t2++; if (M && D) { clearInterval(i2); try { start2d(); } catch (e) { console.warn('bathtub 2d', e); } } else if (t2 > 80) clearInterval(i2); }, 300);
var i3 = setInterval(function () {
  if (!host3 || !D || !window.__wmbMap3d || typeof maplibregl === 'undefined') return;
  clearInterval(i3); M3 = window.__wmbMap3d; var go = function () { try { start3d(); } catch (e) { console.warn('bathtub 3d', e); } };
  if (M3.isStyleLoaded && M3.isStyleLoaded()) go(); else M3.once('load', go);
}, 700);
})();
