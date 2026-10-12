/* flood-3d-kit.js — เพิ่มบนแผนที่ 3 มิติ (flood-forecast #riskMap3D) ตามไอเดียจาก POPNIX Flood 3D
   1) หลอดแก้วระดับน้ำ 3 มิติ (ป้ายตั้งบนภูมิประเทศ): ก้นหลอด = ปกติ, เส้นแดง = ตลิ่ง, น้ำทะลุหลอด = ล้นตลิ่ง + วงน้ำกระเพื่อมที่ฐาน
   2) แถบเวลา ย้อนหลัง 7 วัน → วันนี้ → พยากรณ์ 7 วัน (เล่นได้) — วันพยากรณ์ sync กับแถบเลื่อนวันเดิม (อาคารเปลี่ยนตาม)
   3) "พาชมจุดวิกฤต" บินกล้องไปทีละจุดเรียงตามความเสี่ยง + "บินไปตำแหน่งของฉัน"
   กลับแบบเดิม: ลบ <script src="/__uikit/flood-3d-kit.js"> ออกจาก preview_server.py */
(function () {
'use strict';
var host = document.getElementById('riskMap3D'); if (!host) return;
var ORD = ['normal', 'watch', 'warning', 'critical'];
var HEX = { normal: '#2a9d8f', watch: '#e0a94f', warning: '#e0763f', critical: '#e05252' };
var TH = { normal: 'ปกติ', watch: 'เฝ้าระวัง', warning: 'เตือนภัย', critical: 'วิกฤต' };
var SHOW = ['Mae_Main1', 'Mae_Main2', 'RongHai', 'CAT_KU3'], BANKED = ['Mae_Main1', 'RongHai'];
var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
var tierMcm = function (v) { return v > 0.2 ? 'critical' : v > 0.05 ? 'warning' : v > 0.001 ? 'watch' : 'normal'; };
var dshort = function (iso) { var d = new Date(iso + 'T00:00:00'); return isNaN(d) ? iso : d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short' }); };
var addDays = function (iso, n) { var d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };

var D = null, M = null, N = [], tubes = {}, t = 0, timer = null, tourTimer = null, panel, bar, info, todayIso = '', onDepth = null;

function build() {
  var fc = D.kwan_forecast || [], ob = D.kwan_observed_30d || [];
  todayIso = fc.length ? addDays(fc[0].date, -1) : '';
  N = SHOW.filter(function (k) { return D.nodes[k]; }).map(function (k) {
    var p = D.nodes[k], by = {}; D.overflow_forecast.filter(function (r) { return r.node === k; }).forEach(function (r) { by[r.date] = r.mcm; });
    return { k: k, name: p.name_th.replace(/\s*\(.*\)$/, ''), lat: p.lat, lon: p.lon, by: by, bank: D.banks ? D.banks[k] : null, banked: BANKED.indexOf(k) >= 0 && D.banks && D.banks[k] != null };
  });
}
/* สถานะของแต่ละหลอด ณ ขั้นเวลา t (-7..+7) */
function state(n, t) {
  var fc = D.kwan_forecast || [], ob = D.kwan_observed_30d || [], lv = null, tier = 'normal', tx = '', nodata = false, fill = .2;
  if (n.banked) {
    if (t > 0 && fc[t - 1]) { lv = fc[t - 1].level; var p90 = fc[t - 1].p90; tier = lv >= n.bank ? 'critical' : p90 >= n.bank ? 'warning' : tierMcm(n.by[fc[t - 1].date] || 0); }
    else if (t === 0 && D.kwan_now) { lv = D.kwan_now.level; try { tier = typeof nodeFlagLevel === 'function' ? nodeFlagLevel(D, n.k) : (lv >= n.bank ? 'critical' : 'normal'); } catch (e) { tier = lv >= n.bank ? 'critical' : 'normal'; } }
    else { var o = ob[ob.length - 1 + t]; if (!o) nodata = true; else { lv = o.level; tier = lv >= n.bank ? 'critical' : lv >= n.bank - .3 ? 'warning' : lv >= n.bank - .6 ? 'watch' : 'normal'; } }
    if (lv != null) { fill = Math.max(.04, Math.min(1, (lv - (n.bank - .6)) / (.6 + .3))); tx = lv.toFixed(2) + ' ม. · ตลิ่ง ' + n.bank.toFixed(2); }
  } else {
    if (t > 0 && fc[t - 1]) { var v = n.by[fc[t - 1].date] || 0; tier = tierMcm(v); tx = v > 0 ? 'น้ำล้น ' + (v >= .01 ? v.toFixed(3) : v.toFixed(4)) + ' ล้าน ลบ.ม.' : 'ไม่มีน้ำล้นคาดการณ์'; }
    else if (t === 0) { try { tier = typeof nodeFlagLevel === 'function' ? nodeFlagLevel(D, n.k) : 'normal'; } catch (e) {} tx = 'สรุป 7 วัน: ' + TH[tier]; }
    else nodata = true;
    fill = { normal: .18, watch: .42, warning: .62, critical: .8 }[tier];
  }
  if (nodata) { tier = 'normal'; tx = 'ไม่มีข้อมูลย้อนหลัง'; fill = .06; }
  return { tier: tier, tx: tx, fill: fill, nodata: nodata, over: !nodata && (tier === 'critical' || (n.banked && lv != null && lv >= n.bank)) };
}
/* โหมดสนุก: ของลอยน้ำบอกระดับเตือน (ลายเส้นออกแบบเอง) เฝ้าระวัง=เป็ดยาง เตือนภัย=เจ็ตสกี วิกฤต=เรือดำน้ำ */
var TOY = {
  watch: '<svg viewBox="0 0 40 30"><ellipse cx="18" cy="21" rx="13" ry="7" fill="#ffd23f"/><circle cx="28" cy="11" r="7" fill="#ffd23f"/><path d="M34 11l6 2-6 2z" fill="#ff8c1a"/><circle cx="29.5" cy="9.5" r="1.4" fill="#222"/><path d="M8 20c4 4 12 4 16-1" fill="none" stroke="#e8a900" stroke-width="1.5"/></svg>',
  warning: '<svg viewBox="0 0 40 30"><path d="M2 21c4 5 26 5 33-3l-6-4H12z" fill="#e0763f"/><path d="M12 14l5-6h6l2 6z" fill="#f7f7f7"/><path d="M24 8l4-3" stroke="#555" stroke-width="2" stroke-linecap="round"/><circle cx="18" cy="6" r="3" fill="#ffcf9f"/><path d="M0 26c6 2 10-1 14 1" fill="none" stroke="#fff" stroke-width="1.6" opacity=".8"/></svg>',
  critical: '<svg viewBox="0 0 40 30"><rect x="14" y="3" width="8" height="8" rx="2" fill="#6b7f8c"/><path d="M18 3v-2h5" stroke="#6b7f8c" stroke-width="2" fill="none"/><ellipse cx="19" cy="19" rx="17" ry="8" fill="#e05252"/><circle cx="11" cy="19" r="2.2" fill="#cfe9f5"/><circle cx="19" cy="19" r="2.2" fill="#cfe9f5"/><circle cx="27" cy="19" r="2.2" fill="#cfe9f5"/><path d="M36 15l4-3v14l-4-3z" fill="#b53a3a"/></svg>'
};
var BANKLINE = .67; // ตำแหน่งตลิ่งบนหลอด (สัดส่วนความสูง)
function makeTube(n) {
  var el = document.createElement('div'); el.className = 'f3-tube';
  el.innerHTML = '<div class="lb"><b>' + esc(n.name) + '</b><span class="tx"></span></div><div class="gl"><i class="wt"></i><s class="bk"></s><em class="sp"></em><span class="toy"></span></div><div class="bs"><u></u><u></u></div>';
  el.querySelector('.bk').style.bottom = (BANKLINE * 100) + '%';
  el.addEventListener('click', function (e) { e.stopPropagation(); focus(n, false); });
  var mk = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([n.lon, n.lat]).addTo(M);
  tubes[n.k] = { el: el, mk: mk };
}
function render() {
  N.forEach(function (n) {
    var s = state(n, t), el = tubes[n.k].el, f = s.nodata ? .06 : s.fill;
    el.style.setProperty('--c', HEX[s.tier]); el.classList.toggle('nodata', s.nodata); el.classList.toggle('over', s.over); el.classList.toggle('hot', !s.nodata && (s.tier === 'warning' || s.tier === 'critical'));
    el.querySelector('.wt').style.height = (f * 100) + '%'; var ty = el.querySelector('.toy'); ty.style.setProperty('--f', f); if (ty.dataset.k !== (s.nodata ? 'normal' : s.tier)) { ty.dataset.k = s.nodata ? 'normal' : s.tier; ty.innerHTML = TOY[ty.dataset.k] || ''; } el.querySelector('.tx').textContent = TH[s.tier] + (s.tx ? ' · ' + s.tx : '');
  });
  var ob = D.kwan_observed_30d || [], lab = t === 0 ? 'ล่าสุด' + (todayIso ? ' ' + dshort(todayIso) : '') : t < 0 ? 'ย้อนหลัง ' + (-t) + ' วัน' + (ob[ob.length - 1 + t] ? ' (' + dshort(ob[ob.length - 1 + t].date) + ')' : '') : 'พยากรณ์ +' + t + ' วัน' + (D.kwan_forecast[t - 1] ? ' (' + dshort(D.kwan_forecast[t - 1].date) + ')' : '');
  bar.querySelector('.lab').textContent = lab; bar.querySelector('input').value = t;
}
function setT(v, fromPage) {
  t = Math.max(-7, Math.min(7, v)); render();
  var r = document.getElementById('dayRange');
  if (!fromPage && r && t >= 1 && +r.value !== t) { r.value = t; r.dispatchEvent(new Event('input', { bubbles: true })); }
}
function stop() { if (timer) { clearInterval(timer); timer = null; bar.querySelector('.pl').textContent = '▶'; } }

/* ---------- พาชมจุดวิกฤต ---------- */
function ranked() { return N.slice().sort(function (a, b) { var sa = state(a, t), sb = state(b, t); return ORD.indexOf(sb.tier) - ORD.indexOf(sa.tier) || sb.fill - sa.fill; }); }
/* flyTo จัดกล้องตามระดับ 0 ม. แต่ภูมิประเทศสูง ~390 ม. ทำให้จุดที่เล็งไปโผล่สูงลอยพ้นจอ →
   หลังบินถึง วัดตำแหน่งหลอดจริงบนจอแล้วเลื่อนแผนที่ให้หลอดอยู่ในกรอบที่มองเห็นทั้งป้ายและหลอด */
var focusTok = 0;
function settle(n, i, tok) {
  setTimeout(function () {
    if (tok !== focusTok || !tubes[n.k]) return;
    var r = tubes[n.k].el.getBoundingClientRect(), h = host.getBoundingClientRect(), px = r.left + r.width / 2, py = r.bottom, tx = h.left + (230 + h.width) / 2, ty = h.top + h.height * .66, dx = px - tx, dy = py - ty;
    if (Math.abs(dx) < 30 && Math.abs(dy) < 30) return;
    M.panBy([dx, dy], { duration: 800, essential: true });
    if (i < 2) M.once('moveend', function () { if (tok === focusTok) settle(n, i + 1, tok); });
  }, 450);
}
function focus(n, tour, i, total) {
  var s = state(n, t), brg = -12 + (tour ? (i || 0) * 38 : 0);
  var tok = ++focusTok;
  M.flyTo({ center: [n.lon, n.lat], zoom: 15.4, pitch: 62, bearing: brg, duration: tour ? 2600 : 1600, essential: true });
  M.once('moveend', function () { if (tok === focusTok) settle(n, 0, tok); });
  info.innerHTML = (tour ? '<small>จุดที่ ' + (i + 1) + '/' + total + '</small>' : '') + '<b style="color:' + HEX[s.tier] + '">' + esc(n.name) + '</b><br>' + TH[s.tier] + (s.tx ? ' · ' + esc(s.tx) : '');
  info.classList.add('show');
}
function stopTour() { if (tourTimer) { clearTimeout(tourTimer); tourTimer = null; } panel.querySelector('.tour').textContent = '▶ พาชมจุดวิกฤต'; panel.querySelector('.tour').classList.remove('on'); }
function tour() {
  var b = panel.querySelector('.tour'); if (tourTimer) { stopTour(); return; }
  b.textContent = '■ หยุดทัวร์'; b.classList.add('on'); var list = ranked(), i = 0;
  (function next() { if (i >= list.length) { stopTour(); M.flyTo({ center: [99.87, 19.115], zoom: 13.2, pitch: 60, bearing: -12, duration: 2400 }); info.classList.remove('show'); return; } focus(list[i], true, i, list.length); i++; tourTimer = setTimeout(next, 5200); })();
}


/* ---------- ภาพ → ไทล์ราสเตอร์ (protocol "ukimg") ----------
   image source ของ MapLibre ไม่ถูก "ทาบ" บนภูมิประเทศ 3 มิติเสมอไป (ทดสอบแล้วชั้น P95/ยากิในบริเวณกว๊านไม่ขึ้น) แต่ raster tiles ทาบได้ปกติ
   จึงตัดภาพ PNG เป็นไทล์ XYZ ในเบราว์เซอร์ตามที่ขอ แล้วใช้เป็น raster source */
var IMG = {}, protoOn = false, imgSeq = 0;
function mY(lat) { return Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)); }
function ensureProto() {
  if (protoOn) return; protoOn = true;
  maplibregl.addProtocol('ukimg', function (params) {
    var m = /ukimg:\/\/([^/]+)\/(\d+)\/(\d+)\/(\d+)/.exec(params.url), rec = m && IMG[m[1]];
    if (!rec) return Promise.reject(new Error('ukimg: unknown'));
    var z = +m[2], x = +m[3], y = +m[4], n = Math.pow(2, z), b = rec.b;
    return rec.bmp.then(function (bmp) {
      var cv = typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(256, 256) : Object.assign(document.createElement('canvas'), { width: 256, height: 256 }), cx = cv.getContext('2d');
      var lon0 = x / n * 360 - 180, lon1 = (x + 1) / n * 360 - 180, u0 = (lon0 - b.w) / (b.e - b.w), u1 = (lon1 - b.w) / (b.e - b.w);
      var YN = .5 - mY(b.n) / (2 * Math.PI), YS = .5 - mY(b.s) / (2 * Math.PI), v0 = (y / n - YN) / (YS - YN), v1 = ((y + 1) / n - YN) / (YS - YN);
      if (u1 > 0 && u0 < 1 && v1 > 0 && v0 < 1) { cx.imageSmoothingEnabled = true; cx.drawImage(bmp, u0 * bmp.width, v0 * bmp.height, (u1 - u0) * bmp.width, (v1 - v0) * bmp.height, 0, 0, 256, 256); }
      return (cv.convertToBlob ? cv.convertToBlob({ type: 'image/png' }) : new Promise(function (r) { cv.toBlob(r, 'image/png'); })).then(function (bl) { return bl.arrayBuffer(); }).then(function (ab) { return { data: ab }; });
    });
  });
}
/* เพิ่มภาพเป็นชั้น raster ทาบภูมิประเทศ: คืน id ชั้น (ลบด้วย removeImg) */
function addImg(map, key, url, b, opacity, before) {
  ensureProto(); var id = key + '-' + (++imgSeq);
  IMG[id] = { b: b, bmp: fetch(url).then(function (r) { return r.blob(); }).then(function (bl) { return createImageBitmap(bl); }) };
  map.addSource('uki-' + id, { type: 'raster', tiles: ['ukimg://' + id + '/{z}/{x}/{y}'], tileSize: 256, minzoom: 8, maxzoom: 18, bounds: [b.w, b.s, b.e, b.n] });
  map.addLayer({ id: 'uki-' + id, type: 'raster', source: 'uki-' + id, layout: { visibility: 'visible' }, paint: { 'raster-opacity': opacity, 'raster-fade-duration': 0 } }, before);
  return 'uki-' + id;
}
function removeImg(map, lid) { if (!lid) return; if (map.getLayer(lid)) map.removeLayer(lid); if (map.getSource(lid)) map.removeSource(lid); delete IMG[lid.slice(4)]; }
window.__ukImgTiles = { add: addImg, remove: removeImg, ready: function () { return typeof maplibregl !== 'undefined' && !!maplibregl.addProtocol; } };

/* ---------- ชั้นความลึกน้ำท่วม (ยากิ 2567 / P95 / พยากรณ์รายวัน) ซ้อนบนภูมิประเทศ 3 มิติ ---------- */
var dReadyUnused = 0, DB = { s: 19.01883856557195, w: 99.75718730414324, n: 19.158288896246347, e: 99.92468585009338 }, dOn = true, dReady = false, vmaxF = 0.02, dayMax = {};
var DCOORD = [[DB.w, DB.n], [DB.e, DB.n], [DB.e, DB.s], [DB.w, DB.s]];
function dSrc() { var b = document.querySelector('#map3dSourceToggle button.active'); return b ? b.dataset.source : 'forecast'; }
function dDay() { var r = document.getElementById('dayRange'); return parseInt(r && r.value, 10) || 1; }
function dInfo() {
  var k = dSrc(), day = dDay();
  if (k === 'p95') return { id: 'p95', url: 'assets/data/flood_risk_p95.png', label: 'ความเสี่ยงเชิงสถิติ (P95)', vmax: 4, op: .85 };
  if (k === 'yagi2024') return { id: 'yagi', url: 'assets/data/flood_depth_yagi2024.png', label: 'ความลึกน้ำท่วมจริง — พายุยากิ 2567', vmax: 4, op: .85 };
  var mx = dayMax[day], note = '';
  if (typeof mx === 'number') note = 'ความลึกสูงสุดวันนี้ ≈ ' + (mx >= 0.01 ? (mx * 100).toFixed(1) + ' ซม.' : (mx * 1000).toFixed(1) + ' มม.') + (mx < 0.05 ? ' — ตื้นมาก ยังไม่ถึงระดับน้ำท่วมที่เป็นอันตราย (สีที่เห็นคือจุดลุ่มที่มีน้ำขังตื้น ๆ)' : '');
  return { id: 'd' + day, url: 'assets/data/flood_depth_forecast_d' + day + '.png', label: 'พยากรณ์ 7 วัน — วันที่ ' + day + (typeof mx === 'number' && mx < 0.05 ? ' (สเกลขยายให้เห็นความต่าง)' : ''), vmax: vmaxF, op: .55, note: note };
}
var fmtD = function (v) { return v >= 1 ? v.toFixed(1) : v >= 0.01 ? v.toFixed(3) : v.toFixed(4); };
/* หนึ่ง source/layer ต่อภาพ (สร้างตอนใช้ครั้งแรก) แล้วสลับ visibility — ไม่ใช้ updateImage เพราะบางเวอร์ชันไม่รีเฟรชภาพ */
var dLayers = {}, DBB = { w: DB.w, s: DB.s, e: DB.e, n: DB.n };
function depthUpdate() {
  if (!M) return; var d = dInfo(), before = M.getLayer('reservoirs-fill') ? 'reservoirs-fill' : undefined;
  if (!dLayers[d.id]) dLayers[d.id] = addImg(M, 'depth', d.url, DBB, d.op, before);
  Object.keys(dLayers).forEach(function (k) { M.setLayoutProperty(dLayers[k], 'visibility', dOn && k === d.id ? 'visible' : 'none'); });
  var dl = panel.querySelector('.f3-dl'); dl.style.display = dOn ? 'block' : 'none';
  var q = dl.querySelector('.dq'); if (!q) { q = document.createElement('div'); q.className = 'dq'; dl.appendChild(q); } q.textContent = d.note || ''; q.style.display = d.note ? 'block' : 'none';
  dl.querySelector('.dn').textContent = d.label; dl.querySelector('.dm').textContent = fmtD(d.vmax / 2); dl.querySelector('.dx').textContent = fmtD(d.vmax) + ' ม.+';
  if (onDepth) onDepth();
}
function depthInit() {
  fetch('assets/data/flood_depth_forecast_series_meta.json').then(function (r) { return r.json(); }).then(function (j) { if (typeof j.vmax_m === 'number') vmaxF = j.vmax_m; (j.days || []).forEach(function (x) { dayMax[x.day] = x.max_depth_m; }); depthUpdate(); }).catch(function () {});
  depthUpdate();
  var tg = document.getElementById('map3dSourceToggle'); if (tg) tg.addEventListener('click', function () { setTimeout(depthUpdate, 0); });
  var rg = document.getElementById('dayRange'); if (rg) rg.addEventListener('input', function () { if (dSrc() === 'forecast') depthUpdate(); });
  var lab = document.getElementById('dayLabel'); if (lab) new MutationObserver(function () { if (dSrc() === 'forecast') depthUpdate(); }).observe(lab, { childList: true, characterData: true, subtree: true });
  panel.querySelector('.dp').onclick = function () { dOn = !dOn; this.classList.toggle('on', dOn); this.textContent = 'ชั้นความลึกน้ำท่วม: ' + (dOn ? 'เปิด' : 'ปิด'); depthUpdate(); };
}

/* ---------- จุดอ่างเก็บน้ำ (% ความจุ) ---------- */
function reservoirs() {
  Promise.all([fetch('assets/data/monitoring.json').then(function (r) { return r.json(); }), fetch('assets/data/wmb_reservoirs7.geojson.json').then(function (r) { return r.json(); })]).then(function (a) {
    var st = a[0].stations || [];
    a[1].features.forEach(function (f) {
      var s0 = st.filter(function (x) { return x.name_th === f.properties.Name_T; })[0]; if (!s0 || s0.capacity_pct == null) return;
      var ring = f.geometry.coordinates[0], xs = ring.map(function (c) { return c[0]; }), ys = ring.map(function (c) { return c[1]; }), lo = (Math.min.apply(null, xs) + Math.max.apply(null, xs)) / 2, la = (Math.min.apply(null, ys) + Math.max.apply(null, ys)) / 2;
      var p = s0.capacity_pct, c = p >= 100 ? '#e05252' : p >= 90 ? '#e0a94f' : '#2a9d8f', el = document.createElement('div'); el.className = 'f3-res'; el.style.setProperty('--c', c);
      el.innerHTML = '<b>' + p.toFixed(0) + '%</b><span>' + esc(s0.name_th.replace(/^อ่างเก็บน้ำ/, '')) + '</span>';
      el.onclick = function (e) { e.stopPropagation(); var d = s0.distance_to_spillway_m; info.innerHTML = '<b style="color:' + c + '">' + esc(s0.name_th) + '</b><br>ความจุ ' + p.toFixed(1) + '% · ระดับ ' + s0.water_level.toFixed(2) + ' ม.' + (d != null ? '<br>' + (d >= 0 ? 'สูงกว่า' : 'ต่ำกว่า') + 'สันสปิลเวย์ ' + Math.abs(d).toFixed(2) + ' ม.' : ''); info.classList.add('show'); M.flyTo({ center: [lo, la], zoom: Math.max(M.getZoom(), 14.8), pitch: 60, duration: 1600 }); };
      new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([lo, la]).addTo(M);
    });
  }).catch(function () {});
}

/* ---------- น้ำฝนไหลไปไหน (ใช้ตัวคำนวณจาก flood-flow-kit.js) ---------- */
var flow3 = false, fAnim = 0, fMk = [], fReady = false;
function flowLayers() {
  if (fReady) return; fReady = true;
  M.addSource('f3-flow', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } } });
  M.addLayer({ id: 'f3-flow-under', type: 'line', source: 'f3-flow', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#ffffff', 'line-width': 9, 'line-opacity': .6 } });
  M.addLayer({ id: 'f3-flow-line', type: 'line', source: 'f3-flow', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#1d9bf0', 'line-width': 5 } });
}
function flowClear() { cancelAnimationFrame(fAnim); fMk.forEach(function (m) { m.remove(); }); fMk = []; if (fReady) M.getSource('f3-flow').setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [] } }); }
function flowOn(on) {
  flow3 = on; panel.querySelector('.fl').classList.toggle('on', on); M.getCanvas().style.cursor = on ? 'crosshair' : '';
  if (on) { info.innerHTML = 'คลิกบนแผนที่ตรงจุดที่ต้องการ เพื่อปล่อยหยดน้ำฝน'; info.classList.add('show'); if (window.__ukFlow) window.__ukFlow.ready(); } else { flowClear(); info.classList.remove('show'); }
}
function flowClick(e) {
  if (!flow3) return; if (!window.__ukFlow) { info.textContent = 'ตัวคำนวณทางไหลของน้ำยังไม่พร้อม'; return; }
  flowClear(); flowLayers(); info.innerHTML = 'กำลังไล่ตามทางลาด… (ครั้งแรกอาจใช้ ~5–10 วินาที)'; info.classList.add('show');
  window.__ukFlow.trace(e.lngLat.lat, e.lngLat.lng).then(function (r) {
    if (r.err) { info.textContent = r.err; return; }
    var ll = r.ll.map(function (p) { return [p[1], p[0]]; }), seg = [0];
    for (var i = 1; i < ll.length; i++) seg[i] = seg[i - 1] + Math.hypot(ll[i][0] - ll[i - 1][0], ll[i][1] - ll[i - 1][1]);
    var total = seg[seg.length - 1] || 1, dur = Math.min(6000, 2200 + r.len / 4), t0 = null, reduced = matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.classList.contains('uk-reduce');
    var dEl = document.createElement('div'); dEl.className = 'fft-drop'; var dm = new maplibregl.Marker({ element: dEl, anchor: 'bottom' }).setLngLat(ll[0]).addTo(M); fMk.push(dm);
    var b = new maplibregl.LngLatBounds(ll[0], ll[0]); ll.forEach(function (q) { b.extend(q); });
    M.fitBounds(b, { padding: { top: 90, bottom: 130, left: 240, right: 60 }, maxZoom: 15.4, pitch: 62, duration: 1800 });
    info.innerHTML = window.__ukFlow.html(r).replace('class="t"', 'class="t" style="font-weight:700"') + '<div class="f3-fa"><button type="button" class="fx">ล้างเส้นทาง</button></div>';
    info.querySelector('.fx').onclick = function () { flowClear(); info.classList.remove('show'); };
    function frame(ts) {
      if (!flow3) return; if (t0 == null) t0 = ts; var f = reduced ? 1 : Math.min(1, (ts - t0) / dur), d = f * f * (3 - 2 * f) * total, j = 1; while (j < seg.length - 1 && seg[j] < d) j++;
      var a = ll[j - 1], c = ll[j], u = Math.min(1, (d - seg[j - 1]) / ((seg[j] - seg[j - 1]) || 1)), cur = [a[0] + (c[0] - a[0]) * u, a[1] + (c[1] - a[1]) * u], part = ll.slice(0, j); part.push(cur);
      M.getSource('f3-flow').setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: part } }); dm.setLngLat(cur);
      if (f < 1) fAnim = requestAnimationFrame(frame); else { dm.remove(); var en = document.createElement('div'); en.className = 'fft-en'; en.style.setProperty('--c', { kwan: '#1d9bf0', res: '#2a9d8f', pit: '#e0a94f' }[r.end.t] || '#8aa3a0'); en.innerHTML = '<s></s>'; fMk.push(new maplibregl.Marker({ element: en }).setLngLat(ll[ll.length - 1]).addTo(M)); }
    }
    setTimeout(function () { fAnim = requestAnimationFrame(frame); }, 700);
  }).catch(function (er) { console.warn('flow3d', er); info.textContent = 'คำนวณเส้นทางไม่สำเร็จ'; });
}

function start() {
  build();
  N.forEach(makeTube);
  panel = document.createElement('div'); panel.className = 'f3-panel';
  panel.innerHTML = '<button type="button" class="f3-pt">☰ เมนูแผนที่</button><button type="button" class="tour">▶ พาชมจุดวิกฤต</button><button type="button" class="dp on">ชั้นความลึกน้ำท่วม: เปิด</button><div class="f3-dl"><div class="dn"></div><div class="db"></div><div class="ds"><span>0</span><span class="dm"></span><span class="dx"></span></div></div><button type="button" class="fl">น้ำฝนไหลไปไหน (คลิกแผนที่)</button><button type="button" class="fun">โหมดสนุก: ปิด</button><select class="f3-vs" aria-label="เลือกหมู่บ้าน"><option value="">บินไปหมู่บ้าน…</option></select><div class="f3-ab"><button type="button" class="sh">🔗 คัดลอกลิงก์มุมมอง</button><button type="button" class="sv">📷 บันทึกภาพ</button><button type="button" class="pr">🖨 พิมพ์หน้านี้</button></div><div class="f3-info"></div><div class="f3-key"><i></i>หลอดแก้ว = ระดับน้ำเทียบตลิ่ง · เส้นแดง = ตลิ่ง · น้ำทะลุหลอด = ล้นตลิ่ง · วงกลม = อ่างเก็บน้ำ (% ความจุ)</div>';
  info = panel.querySelector('.f3-info');
  bar = document.createElement('div'); bar.className = 'f3-time';
  bar.innerHTML = '<button type="button" class="pl">▶</button><div class="sl"><input type="range" min="-7" max="7" step="1" value="0"><div class="tk"><span>ย้อนหลัง 7 วัน</span><span>ล่าสุด</span><span>พยากรณ์ 7 วัน</span></div></div><span class="lab"></span>';
  host.appendChild(panel); host.appendChild(bar);
  /* โหมดเต็มจอ (Fullscreen API; ถ้าเบราว์เซอร์ไม่รองรับ เช่น iOS ใช้เต็มหน้าต่างแทน) */
  var fs = document.createElement('button'); fs.type = 'button'; fs.className = 'f3-fs'; fs.title = 'เต็มจอ'; fs.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>เต็มจอ'; host.appendChild(fs);
  var isFs = function () { return document.fullscreenElement === host || host.classList.contains('f3-pfs'); };
  var after = function () { fs.classList.toggle('on', isFs()); fs.lastChild.textContent = isFs() ? 'ออกจากเต็มจอ' : 'เต็มจอ'; setTimeout(function () { try { M.resize(); } catch (e) {} }, 120); };
  fs.onclick = function () {
    if (isFs()) { if (document.fullscreenElement) document.exitFullscreen(); host.classList.remove('f3-pfs'); after(); return; }
    if (host.requestFullscreen) host.requestFullscreen().then(after).catch(function () { host.classList.add('f3-pfs'); after(); }); else { host.classList.add('f3-pfs'); after(); }
  };
  document.addEventListener('fullscreenchange', after);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && host.classList.contains('f3-pfs')) { host.classList.remove('f3-pfs'); after(); } });
  ['mousedown', 'dblclick', 'wheel', 'touchstart'].forEach(function (ev) { fs.addEventListener(ev, function (x) { x.stopPropagation(); }); });
  [panel, bar].forEach(function (e) { ['mousedown', 'dblclick', 'wheel', 'touchstart'].forEach(function (ev) { e.addEventListener(ev, function (x) { x.stopPropagation(); }); }); });
  panel.querySelector('.f3-pt').onclick = function () { panel.classList.toggle('open'); this.textContent = panel.classList.contains('open') ? '✕ ปิดเมนู' : '☰ เมนูแผนที่'; };
  panel.querySelector('.tour').onclick = function () { stop(); tour(); };
  panel.querySelector('.fl').onclick = function () { stopTour(); flowOn(!flow3); };
  panel.querySelector('.fun').onclick = function () { var on = !host.classList.contains('f3-fun'); host.classList.toggle('f3-fun', on); this.classList.toggle('on', on); this.textContent = 'โหมดสนุก: ' + (on ? 'เปิด' : 'ปิด'); };
  /* ฝังความสูงพื้นดินให้อาคาร "ทีละหลัง" (หน้าเดิมทำแบบครบทุกหลังพร้อมกัน → ถ้าไทล์ DEM ยังโหลดไม่ครบ อาคารจมใต้ภูมิประเทศ มองไม่เห็น โดยเฉพาะตอนเต็มจอ/มุมกล้องต่างกัน) */
  /* แก้ถาวร: วาดอาคารด้วย fill-extrusion ของ MapLibre เอง (ตามภูมิประเทศอัตโนมัติ ไม่ต้องฝัง z) แล้วซ่อนชั้น deck.gl
     — ค่าความสูง/สีดึงจาก accessor ของชั้น deck เดิม จึงตรงกับหน้าเดิมเสมอ; tooltip ทำเองด้วย mousemove */
  var bldOv = null, bldData = null, bldRaw = null, bldTip = null;
  function strip2(c) { return typeof c[0] === 'number' ? [c[0], c[1]] : c.map(strip2); }
  function bldSync(L) {
    if (!L || !L.props || !L.props.data || !L.props.data.length) return;
    var D = L.props.data;
    if (D !== bldData) { bldData = D; bldRaw = D.map(function (f) { return { type: 'Feature', properties: f.properties, geometry: { type: f.geometry.type, coordinates: strip2(f.geometry.coordinates) } }; }); }
    var feats = bldRaw.map(function (f, i) {
      var src = D[i], c = L.props.getFillColor(src), h = L.props.getElevation(src);
      return { type: 'Feature', properties: { h: h, col: 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + ((c[3] == null ? 255 : c[3]) / 255).toFixed(2) + ')', i: i }, geometry: f.geometry };
    });
    var fc = { type: 'FeatureCollection', features: feats };
    if (M.getSource('f3-bld')) M.getSource('f3-bld').setData(fc);
    else {
      M.addSource('f3-bld', { type: 'geojson', data: fc });
      M.addLayer({ id: 'f3-bld', type: 'fill-extrusion', source: 'f3-bld', paint: { 'fill-extrusion-height': ['get', 'h'], 'fill-extrusion-base': 0, 'fill-extrusion-color': ['get', 'col'], 'fill-extrusion-opacity': .95 } });
    }
  }
  function bldDepth(p) {
    var k = 0, tg = document.getElementById('map3dSourceToggle'); if (tg) { var b = tg.querySelectorAll('button'); for (var i = 0; i < b.length; i++) if (b[i].classList.contains('active')) k = i; }
    var r = document.getElementById('dayRange'), d = r ? parseInt(r.value, 10) || 1 : 1;
    return k === 1 ? (p.depth_p95 || 0) : k === 2 ? (p.depth_yagi2024 || 0) : ((p.depths || [])[d - 1] || 0);
  }
  function bldInit() {
    if (bldOv) return;
    var ov = (M._controls || []).filter(function (c) { return c && c._deck; })[0]; if (!ov) return;
    var L = ov._deck.props.layers && ov._deck.props.layers[0]; if (!L || !L.props.getElevation) return;
    bldOv = ov;
    var orig = ov.setProps.bind(ov);
    ov.setProps = function (p) {
      if (p && p.layers && p.layers[0] && p.layers[0].id === 'flood-buildings') { try { bldSync(p.layers[0]); } catch (e) { console.error('f3 bldSync', e); } p =Object.assign({}, p, { layers: [] }); }
      return orig(p);
    };
    try { bldSync(L); } catch (e) { console.error('f3 bldSync0', e); }
    orig({ layers: [] });
    bldTip = document.createElement('div'); bldTip.style.cssText = 'position:absolute;z-index:6;pointer-events:none;display:none;background:#081e26;color:#eef6f4;font-size:12px;border-radius:6px;padding:6px 10px;max-width:240px'; host.appendChild(bldTip);
    M.on('mousemove', function (e) {
      var fs = M.getLayer('f3-bld') ? M.queryRenderedFeatures(e.point, { layers: ['f3-bld'] }) : [];
      if (!fs.length) { bldTip.style.display = 'none'; M.getCanvas().style.cursor = ''; return; }
      var p = fs[0].properties, pr = typeof p.depth_p95 !== 'undefined' ? p : (bldRaw && bldRaw[p.i] ? bldRaw[p.i].properties : {});
      var d = bldDepth(pr), nm = pr.name_th || 'อาคาร';
      bldTip.innerHTML = '<b>' + nm + '</b><br>' + (d > 0 ? 'ความลึกน้ำท่วม: ' + (d >= .1 ? d.toFixed(2) + ' ม.' : (d * 100).toFixed(2) + ' ซม.') : 'ไม่คาดว่าจะได้รับผลกระทบ');
      bldTip.style.left = (e.point.x + 14) + 'px'; bldTip.style.top = (e.point.y + 14) + 'px'; bldTip.style.display = 'block';
    });
  }
  M.on('idle', bldInit);
  M.on('click', flowClick); reservoirs(); depthInit();

  /* ---------- D2: เลือกหมู่บ้าน → บินไป + สรุปอาคารที่ได้รับผลกระทบ ---------- */
  var VIL = [], vSel = null, vOf = null;
  function bbox(c, b) { if (typeof c[0] === 'number') { b[0] = Math.min(b[0], c[0]); b[1] = Math.min(b[1], c[1]); b[2] = Math.max(b[2], c[0]); b[3] = Math.max(b[3], c[1]); } else c.forEach(function (x) { bbox(x, b); }); return b; }
  function inRing(x, y, r) { var o = false; for (var i = 0, j = r.length - 1; i < r.length; j = i++) { if ((r[i][1] > y) !== (r[j][1] > y) && x < (r[j][0] - r[i][0]) * (y - r[i][1]) / (r[j][1] - r[i][1]) + r[i][0]) o = !o; } return o; }
  function inVil(v, x, y) { var g = v.g; if (x < v.b[0] || x > v.b[2] || y < v.b[1] || y > v.b[3]) return false; var polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates; return polys.some(function (p) { return inRing(x, y, p[0]); }); }
  function ctr(c) { var r = c; while (typeof r[0][0] !== 'number') r = r[0]; var sx = 0, sy = 0; r.forEach(function (p) { sx += p[0]; sy += p[1]; }); return [sx / r.length, sy / r.length]; }
  function vilIndex() { /* อาคารแต่ละหลังอยู่หมู่บ้านไหน (คำนวณครั้งเดียว) */
    if (vOf || !bldRaw) return; vOf = bldRaw.map(function (f) { var c = ctr(f.geometry.coordinates), k = -1; for (var i = 0; i < VIL.length; i++) if (inVil(VIL[i], c[0], c[1])) { k = i; break; } return k; });
  }
  function vilStats() {
    var i = vSel; if (i == null || i < 0) return; var v = VIL[i]; vilIndex();
    if (!vOf) { info.innerHTML = '<b>' + esc(v.name) + '</b> (หมู่ ' + v.moo + ')<br>กำลังโหลดข้อมูลอาคาร…'; info.classList.add('show'); setTimeout(vilStats, 1500); return; }
    var n = 0, w1 = 0, w10 = 0, mx = 0;
    bldRaw.forEach(function (f, j) { if (vOf[j] !== i) return; n++; var d = bldDepth(f.properties || {}); if (d > mx) mx = d; if (d >= .001) w1++; if (d >= .1) w10++; });
    var dl = mx >= .1 ? mx.toFixed(2) + ' ม.' : mx >= .01 ? (mx * 100).toFixed(1) + ' ซม.' : (mx * 1000).toFixed(1) + ' มม.';
    var lv = mx >= .5 ? 'critical' : mx >= .1 ? 'warning' : mx >= .01 ? 'watch' : 'normal';
    info.innerHTML = '<b style="color:' + HEX[lv] + '">' + esc(v.name) + '</b> (หมู่ ' + v.moo + ')<br>อาคารในแผนที่ ' + n + ' หลัง · มีน้ำ ≥ 1 มม. ' + w1 + ' หลัง · ≥ 10 ซม. ' + w10 + ' หลัง<br>ลึกสุด ' + dl + (n ? '' : ' <small>(ไม่พบอาคารในข้อมูล)</small>');
    info.classList.add('show');
  }
  fetch('assets/data/villages.geojson.json').then(function (r) { return r.json(); }).then(function (j) {
    VIL = (j.features || []).filter(function (f) { return f.geometry; }).map(function (f) { var b = bbox(f.geometry.coordinates, [1e9, 1e9, -1e9, -1e9]); return { name: f.properties.Name_TH || ('หมู่ ' + f.properties.Moo), moo: f.properties.Moo, g: f.geometry, b: b, c: [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] }; }).sort(function (a, b) { return a.moo - b.moo; });
    var s = panel.querySelector('.f3-vs'); VIL.forEach(function (v, i) { var o = document.createElement('option'); o.value = i; o.textContent = 'หมู่ ' + v.moo + ' ' + v.name.replace(/^บ้าน/, ''); s.appendChild(o); });
    if (pendV != null) goVil(pendV);
  }).catch(function () {});
  var pendV = null;
  function goVil(i) { if (!VIL.length) { pendV = i; return; } vSel = i; var v = VIL[i]; stopTour(); M.flyTo({ center: v.c, zoom: 15.6, pitch: 60, bearing: -12, duration: 1800, essential: true }); vilStats(); panel.querySelector('.f3-vs').value = i; }
  panel.querySelector('.f3-vs').onchange = function () { if (this.value === '') { vSel = null; info.classList.remove('show'); return; } goVil(+this.value); };
  onDepth = function () { if (vSel != null) vilStats(); };

  /* ---------- D1: ลิงก์แชร์มุมมอง (#v3=lat,lng,zoom,pitch,bearing,แหล่ง,วัน) ---------- */
  var SRC = ['forecast', 'p95', 'yagi2024'];
  function shareUrl() {
    var c = M.getCenter(), a = [c.lat.toFixed(5), c.lng.toFixed(5), M.getZoom().toFixed(2), M.getPitch().toFixed(0), M.getBearing().toFixed(0), Math.max(0, SRC.indexOf(dSrc())), dDay()];
    return location.href.split('#')[0] + '#v3=' + a.join(',');
  }
  panel.querySelector('.sh').onclick = function () {
    var b = this, u = shareUrl(), ok = function () { b.textContent = '✓ คัดลอกแล้ว'; setTimeout(function () { b.textContent = '🔗 คัดลอกลิงก์มุมมอง'; }, 1800); };
    try { history.replaceState(null, '', u); } catch (e) {}
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(u).then(ok, function () { prompt('คัดลอกลิงก์นี้', u); });
    else { prompt('คัดลอกลิงก์นี้', u); }
  };
  function applyHash() {
    var m = /v3=(-?[\d.]+),(-?[\d.]+),([\d.]+),(-?[\d.]+),(-?[\d.]+)(?:,(\d),(\d))?/.exec(location.hash); if (!m) return;
    var s = +m[6] || 0, dy = +m[7] || 0, bt = document.querySelectorAll('#map3dSourceToggle button');
    if (bt[s] && !bt[s].classList.contains('active')) bt[s].click();
    var r = document.getElementById('dayRange'); if (s === 0 && dy >= 1 && dy <= 7 && r) { r.value = dy; r.dispatchEvent(new Event('input', { bubbles: true })); t = dy; render(); }
    M.jumpTo({ center: [+m[2], +m[1]], zoom: +m[3], pitch: +m[4], bearing: +m[5] });
    try { host.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) {}
  }
  applyHash();

  /* ---------- D4: บันทึกภาพแผนที่ 3 มิติเป็น PNG (ประกอบแผนที่ + ป้ายหัวเรื่อง) ---------- */
  panel.querySelector('.pr').onclick = function () { window.print(); };
  panel.querySelector('.sv').onclick = function () {
    var b = this; b.textContent = 'กำลังสร้างภาพ…';
    M.once('render', function () {
      try {
        var c = M.getCanvas(), w = c.width, h = c.height, pad = Math.round(h * .07), o = document.createElement('canvas'); o.width = w; o.height = h + pad;
        var x = o.getContext('2d'), s = Math.max(1, w / 900);
        x.fillStyle = '#081e26'; x.fillRect(0, 0, w, h + pad); x.drawImage(c, 0, 0);
        x.fillStyle = '#eef6f4'; x.font = '600 ' + Math.round(13 * s) + 'px sans-serif'; x.textBaseline = 'middle';
        x.fillText('แม่นาเรือ — แผนที่น้ำท่วม 3 มิติ · ' + (bar.querySelector('.lab').textContent || '') + ' · ' + panel.querySelector('.f3-dl .dn').textContent, 12 * s, h + pad / 2);
        o.toBlob(function (bl) { var a = document.createElement('a'); a.href = URL.createObjectURL(bl); a.download = 'maenarua-flood-3d-' + new Date().toISOString().slice(0, 10) + '.png'; document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000); b.textContent = '📷 บันทึกภาพ'; }, 'image/png');
      } catch (e) { console.warn('f3 save', e); b.textContent = '📷 บันทึกภาพ (ไม่สำเร็จ)'; }
    });
    M.triggerRepaint();
  };
  bar.querySelector('input').oninput = function () { stop(); setT(+this.value); };
  bar.querySelector('.pl').onclick = function () {
    if (timer) { stop(); return; } this.textContent = '⏸'; if (t >= 7) setT(-7); else setT(t + 1);
    timer = setInterval(function () { if (t >= 7) { stop(); return; } setT(t + 1); }, 1000);
  };
  var lab = document.getElementById('dayLabel'), rg = document.getElementById('dayRange');
  if (lab && rg) new MutationObserver(function () { var v = +rg.value; if (v >= 1 && v <= 7 && t >= 1 && v !== t) { t = v; render(); } }).observe(lab, { childList: true, characterData: true, subtree: true });
  render();
}

/* ลิงก์แชร์ #v3=… → เปิดโหมด 3 มิติให้อัตโนมัติ (kit จะย้ายกล้องเองเมื่อแผนที่พร้อม) */
if (/v3=/.test(location.hash)) { var ob3 = document.getElementById('view3dBtn'); if (ob3) setTimeout(function () { if (!M) ob3.click(); }, 800); }
fetch('assets/data/flood_latest.json').then(function (r) { return r.json(); }).then(function (j) { D = j; }).catch(function () {});
var iv = setInterval(function () {
  if (!D || !window.__wmbMap3d || typeof maplibregl === 'undefined') return;
  clearInterval(iv); M = window.__wmbMap3d;
  var go = function () { try { start(); } catch (e) { console.warn('flood-3d-kit', e); } };
  if (M.loaded && M.isStyleLoaded && M.isStyleLoaded()) go(); else M.once('load', go);
}, 600);
})();
