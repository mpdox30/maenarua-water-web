/* map-kit.js — ปรับแผนที่ Leaflet (index.html / gis-map.html) โดยไม่แก้ไฟล์หน้าเดิม
   1) ป้ายสถานะอ่าง (ชื่อ · % ความจุ · ลูกศรแนวโน้ม) บนแผนที่ + สลับโหมดสี "ตามระดับน้ำ / ตามทิศทาง"
   2) รายการ "ขึ้นเร็วที่สุด / ลดเร็วที่สุด" (เปลี่ยนใน 6 ชม.) คลิกแล้วบินไปจุดนั้น
   3) popup อ่างแบบมีกราฟเล็ก (ระดับน้ำ 72 ชม. + ฝนรายชั่วโมง) แทนข้อความล้วน
   4) "ย่านของฉัน": เลือกหมู่บ้านแล้วซูม + บอกอ่างที่ใกล้ที่สุดและ % ความจุ */
(function () {
'use strict';
if (!document.getElementById('map')) return;
var root = document.documentElement;
var cssv = function (n) { return getComputedStyle(root).getPropertyValue(n).trim(); };
var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
var short = function (n) { return String(n || '').replace(/^อ่างเก็บน้ำ/, ''); };
var fmtT = function (iso) { var d = new Date(iso); return isNaN(d) ? '' : d.toLocaleString('th-TH', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Bangkok' }); };
var C = { up: [224, 118, 63], down: [42, 157, 143], flat: [111, 168, 196], over: [217, 96, 79], warn: [224, 169, 79], ok: [42, 157, 143], none: [138, 163, 160] };

var M = null, S = [], mode = 'level', markers = {}, polys = {}, polyOrig = {}, villages = [], tries = 0;
function getMap() { try { return Function('return typeof map!=="undefined"&&typeof L!=="undefined"?map:null')(); } catch (e) { return null; } }
function layersWith(fn) { var a = []; M.eachLayer(function (l) { if (fn(l)) a.push(l); }); return a; }

/* ---------- เตรียมข้อมูลสถานี ---------- */
function prep(st) {
  var now = new Date(st.measure_datetime).getTime(), h = (st.history || []).map(function (x) { return { t: new Date(x.t).getTime(), v: x.level }; }).filter(function (x) { return isFinite(x.t); });
  var target = now - 6 * 3600 * 1000, best = null; h.forEach(function (p) { if (!best || Math.abs(p.t - target) < Math.abs(best.t - target)) best = p; });
  var delta = best && Math.abs(best.t - target) < 90 * 60 * 1000 && st.water_level != null ? (st.water_level - best.v) * 100 : null;
  return { st: st, code: st.station_code, name: st.name_th, delta: delta, dir: delta == null ? 'none' : delta >= 1 ? 'up' : delta <= -1 ? 'down' : 'flat', hist: h.filter(function (p) { return p.t >= now - 72 * 3600 * 1000; }), now: now };
}
var arrow = function (d) { return d === 'up' ? '▲' : d === 'down' ? '▼' : d === 'flat' ? '●' : '–'; };
var colorOf = function (s) {
  if (mode === 'trend') return C[s.dir === 'up' ? 'up' : s.dir === 'down' ? 'down' : s.dir === 'flat' ? 'flat' : 'none'];
  var p = s.st.capacity_pct; return p == null ? C.none : p >= 100 ? C.over : p >= 90 ? C.warn : C.ok;
};
var dtxt = function (s) { return s.delta == null ? 'ไม่มีข้อมูล 6 ชม.' : (s.delta >= 0 ? '+' : '') + s.delta.toFixed(1) + ' ซม./6 ชม.'; };

/* ---------- popup ---------- */
function chart(s) {
  var W = 290, H = 120, pl = 6, pr = 6, rainH = 26, yT = 34, yB = 104, rain = (s.st.rainfall_hourly || []).filter(function (r) { var t = new Date(r.t).getTime(); return t >= s.now - 72 * 3600e3; });
  var h = s.hist; if (h.length < 2) return '<div class="ukp-nochart">ไม่มีประวัติระดับน้ำ</div>';
  var t0 = h[0].t, t1 = h[h.length - 1].t, lo = Math.min.apply(null, h.map(function (p) { return p.v; })), hi = Math.max.apply(null, h.map(function (p) { return p.v; })), rg = (hi - lo) || .01; lo -= rg * .1; hi += rg * .1; rg = hi - lo;
  var X = function (t) { return pl + (W - pl - pr) * (t - t0) / ((t1 - t0) || 1); }, Y = function (v) { return yB - (yB - yT) * (v - lo) / rg; };
  var pts = h.map(function (p) { return X(p.t).toFixed(1) + ',' + Y(p.v).toFixed(1); }), mx = Math.max.apply(null, rain.map(function (r) { return +r.rain_mm || 0; }).concat([4]));
  var bars = rain.map(function (r) { var v = +r.rain_mm || 0; if (v <= 0) return ''; var t = new Date(r.t).getTime(); return '<rect x="' + (X(t) - 1.4).toFixed(1) + '" y="2" width="2.8" height="' + Math.max(2, v / mx * rainH).toFixed(1) + '" rx="1" class="r"/>'; }).join('');
  var crest = s.st.spillway_msl, cl = crest != null && crest > lo && crest < hi ? '<line x1="' + pl + '" x2="' + (W - pr) + '" y1="' + Y(crest).toFixed(1) + '" y2="' + Y(crest).toFixed(1) + '" class="c"/><text x="' + (W - pr) + '" y="' + (Y(crest) - 3).toFixed(1) + '" text-anchor="end" class="t">สันสปิลเวย์ ' + crest + '</text>' : '';
  var lastY = Y(h[h.length - 1].v);
  return '<svg class="ukp-ch" viewBox="0 0 ' + W + ' ' + H + '"><defs><linearGradient id="ukpg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="s0"/><stop offset="1" class="s1"/></linearGradient></defs>' + bars + cl +
    '<polygon points="' + pts.join(' ') + ' ' + X(t1).toFixed(1) + ',' + yB + ' ' + X(t0).toFixed(1) + ',' + yB + '" fill="url(#ukpg)"/><polyline points="' + pts.join(' ') + '" class="l"/>' +
    '<circle cx="' + X(t1).toFixed(1) + '" cy="' + lastY.toFixed(1) + '" r="4" class="d"/><text x="' + pl + '" y="' + (H - 4) + '" class="t">ย้อนหลัง 72 ชม.</text><text x="' + (W - pr) + '" y="' + (H - 4) + '" text-anchor="end" class="t">ฟ้า = ฝนรายชั่วโมง</text></svg>';
}
function popupHtml(s) {
  var st = s.st, p = st.capacity_pct, c = colorOf({ st: st, dir: s.dir }), rc = 'rgb(' + (p == null ? C.none : p >= 100 ? C.over : p >= 90 ? C.warn : C.ok).join(',') + ')';
  var rain24 = (st.rainfall_hourly || []).filter(function (r) { return new Date(r.t).getTime() >= s.now - 24 * 3600e3; }).reduce(function (a, r) { return a + (+r.rain_mm || 0); }, 0);
  return '<div class="ukp"><div class="ukp-h"><b>' + esc(st.name_th) + '</b><span class="ukp-chip ' + s.dir + '">' + arrow(s.dir) + ' ' + esc(dtxt(s)) + '</span></div>' +
    '<div class="ukp-big" style="color:' + rc + '"><b>' + (p != null ? p.toFixed(1) : '—') + '</b><small>% ของความจุ</small></div>' +
    '<div class="ukp-row"><span>ระดับน้ำ <b>' + (st.water_level != null ? st.water_level.toFixed(2) : '—') + '</b> ม.รทก.</span><span>ฝน 24 ชม. <b>' + rain24.toFixed(1) + '</b> มม.</span></div>' + chart(s) +
    '<div class="ukp-n">ข้อมูล ณ ' + esc(fmtT(st.measure_datetime)) + ' น.</div></div>';
}

/* ---------- ป้ายบนแผนที่ + สีพื้นที่อ่าง ---------- */
function pillHtml(s) { var c = colorOf(s); return '<div class="ukm-pill" style="--c:' + c.join(',') + '"><span class="n">' + esc(short(s.name)) + '</span><b class="num">' + (s.st.capacity_pct != null ? s.st.capacity_pct.toFixed(1) + '%' : '—') + '</b><i>' + arrow(s.dir) + '</i></div>'; }
function refresh() {
  S.forEach(function (s) {
    var m = markers[s.code]; if (m) m.setIcon(L.divIcon({ className: 'ukm-pillwrap', html: pillHtml(s), iconSize: [0, 0] }));
    var pl = polys[s.code]; if (pl) { var c = colorOf(s); pl.setStyle({ color: 'rgb(' + c.join(',') + ')', fillColor: 'rgb(' + c.join(',') + ')', fillOpacity: .62 }); }
  });
  renderList();
}

/* ---------- แผงควบคุม ---------- */
var panel, listEl, sortDir = 'up';
function renderList() {
  if (!listEl) return;
  var rows = S.slice().sort(function (a, b) { var x = a.delta == null ? -1e9 * (sortDir === 'up' ? 1 : -1) : a.delta, y = b.delta == null ? -1e9 * (sortDir === 'up' ? 1 : -1) : b.delta; return sortDir === 'up' ? y - x : x - y; });
  listEl.innerHTML = rows.map(function (s, i) { var c = colorOf(s); return '<button type="button" class="ukm-row" data-c="' + s.code + '" style="--c:' + c.join(',') + '"><em>' + (i + 1) + '</em><span class="rn">' + esc(short(s.name)) + '</span><span class="rd ' + s.dir + '">' + arrow(s.dir) + ' ' + esc(dtxt(s)) + '</span><b class="num">' + (s.st.capacity_pct != null ? s.st.capacity_pct.toFixed(0) + '%' : '—') + '</b></button>'; }).join('');
}
function buildPanel() {
  var Ctl = L.Control.extend({
    options: { position: 'topleft' },
    onAdd: function () {
      var d = L.DomUtil.create('div', 'ukm-panel'); panel = d;
      d.innerHTML = '<button type="button" class="ph">◐ มุมมองแผนที่ <i>▾</i></button><div class="pb">' +
        '<div class="seg" id="ukmMode"><button type="button" data-m="level" class="on">ตามระดับน้ำ</button><button type="button" data-m="trend">ตามทิศทาง</button></div>' +
        '<div class="lg" id="ukmLg"></div>' +
        '<div class="sh"><span>เปลี่ยนใน 6 ชม.</span><span class="seg s2" id="ukmSort"><button type="button" data-d="up" class="on">ขึ้นเร็วสุด</button><button type="button" data-d="down">ลดเร็วสุด</button></span></div><div class="lst" id="ukmList"></div>' +
        '<div class="sh"><span>ย่านของฉัน</span></div><select id="ukmVil"><option value="">เลือกหมู่บ้าน…</option></select><div class="vi" id="ukmVi"></div></div>';
      L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
      d.querySelector('.ph').addEventListener('click', function () { d.classList.toggle('shut'); });
      d.querySelector('#ukmMode').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; mode = b.dataset.m; [].forEach.call(d.querySelectorAll('#ukmMode button'), function (x) { x.classList.toggle('on', x === b); }); legend(); refresh(); });
      d.querySelector('#ukmSort').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; sortDir = b.dataset.d; [].forEach.call(d.querySelectorAll('#ukmSort button'), function (x) { x.classList.toggle('on', x === b); }); renderList(); });
      d.querySelector('#ukmList').addEventListener('click', function (e) { var b = e.target.closest('.ukm-row'); if (!b) return; var m = markers[b.dataset.c]; if (m) { M.flyTo(m.getLatLng(), Math.max(M.getZoom(), 15), { duration: .9 }); setTimeout(function () { m.openPopup(); }, 950); } });
      d.querySelector('#ukmVil').addEventListener('change', function (e) { village(e.target.value); });
      return d;
    }
  });
  new Ctl().addTo(M); listEl = panel.querySelector('#ukmList'); legend();
}
function legend() {
  var el = panel && panel.querySelector('#ukmLg'); if (!el) return;
  var it = mode === 'level' ? [['≥100% (เกินสันสปิลเวย์)', C.over], ['90–100%', C.warn], ['<90%', C.ok]] : [['กำลังขึ้น (≥+1 ซม.)', C.up], ['ทรงตัว', C.flat], ['กำลังลด (≤−1 ซม.)', C.down]];
  el.innerHTML = it.map(function (x) { return '<span><i style="background:rgb(' + x[1].join(',') + ')"></i>' + x[0] + '</span>'; }).join('');
}

/* ---------- ย่านของฉัน ---------- */
function village(key) {
  var vi = panel.querySelector('#ukmVi'); villages.forEach(function (v) { v.layer.setStyle(v.base); });
  if (key === '') { vi.innerHTML = ''; return; }
  var v = villages[+key]; if (!v) return; var b = v.layer.getBounds(), ctr = b.getCenter();
  M.flyToBounds(b, { maxZoom: 15, duration: .9 }); v.layer.setStyle({ weight: 3, fillOpacity: .3, dashArray: null });
  var near = S.map(function (s) { var m = markers[s.code]; return m ? { s: s, d: M.distance(ctr, m.getLatLng()) } : null; }).filter(Boolean).sort(function (a, b2) { return a.d - b2.d; })[0];
  vi.innerHTML = near ? '<b>อ่างที่ใกล้ที่สุด:</b> ' + esc(short(near.s.name)) + ' <span>(' + (near.d / 1000).toFixed(1) + ' กม.)</span><br>ความจุ <b>' + (near.s.st.capacity_pct != null ? near.s.st.capacity_pct.toFixed(1) + '%' : '—') + '</b> · ' + arrow(near.s.dir) + ' ' + esc(dtxt(near.s)) : '';
}

/* ---------- เริ่มทำงาน ---------- */
function build(mon) {
  var sts = (mon.stations || []).map(prep); S = sts;
  var res = layersWith(function (l) { return l.feature && l.feature.properties && l.feature.properties.Name_T && l.getBounds; });
  S.forEach(function (s) {
    var pl = res.filter(function (l) { return l.feature.properties.Name_T === s.name; })[0]; if (!pl) return; polys[s.code] = pl;
    var m = L.marker(pl.getBounds().getCenter(), { icon: L.divIcon({ className: 'ukm-pillwrap', html: pillHtml(s), iconSize: [0, 0] }), zIndexOffset: 800, riseOnHover: true }).addTo(M);
    m.bindPopup(function () { return popupHtml(s); }, { minWidth: 300, maxWidth: 320, className: 'ukp-pop' }); markers[s.code] = m;
  });
  // เปลี่ยน popup ของพื้นที่อ่างเดิมเป็นแบบมีกราฟ
  M.on('popupopen', function (e) { var src = e.popup && e.popup._source, p = src && src.feature && src.feature.properties; if (!p || !p.Name_T) return; var s = S.filter(function (x) { return x.name === p.Name_T; })[0]; if (s) { e.popup.setContent(popupHtml(s)); e.popup.options.className = 'ukp-pop'; } });
  villages = layersWith(function (l) { return l.feature && l.feature.properties && l.feature.properties.Moo != null && l.getBounds; }).map(function (l) { return { layer: l, base: { weight: l.options.weight, fillOpacity: l.options.fillOpacity, dashArray: l.options.dashArray }, moo: +l.feature.properties.Moo, name: l.feature.properties.Name_TH }; }).sort(function (a, b) { return a.moo - b.moo; });
  buildPanel();
  panel.querySelector('#ukmVil').insertAdjacentHTML('beforeend', villages.map(function (v, i) { return '<option value="' + i + '">หมู่ ' + v.moo + ' ' + esc(v.name) + '</option>'; }).join(''));
  refresh();
  setInterval(function () { fetch('assets/data/monitoring.json', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (j) { var n = (j.stations || []).map(prep); n.forEach(function (x) { var o = S.filter(function (s) { return s.code === x.code; })[0]; if (o) { o.st = x.st; o.delta = x.delta; o.dir = x.dir; o.hist = x.hist; o.now = x.now; } }); refresh(); }).catch(function () {}); }, 5 * 60 * 1000);
}
var iv = setInterval(function () {
  M = M || getMap(); tries++;
  if (M && layersWith(function (l) { return l.feature; }).length >= 20) {
    clearInterval(iv);
    fetch('assets/data/monitoring.json').then(function (r) { return r.json(); }).then(build).catch(function () {});
  } else if (tries > 60) clearInterval(iv);
}, 400);
})();

/* เต็มจอ: ย้ายแผง "เปิด/ปิดชั้นข้อมูล" (.map-controls ที่อยู่นอก #map) เข้าไปในแผนที่ตอนเต็มจอ แล้วย้ายกลับตอนออก
   (checkbox ผูกด้วย id จึงยังทำงานเหมือนเดิม) — ถอยกลับ: ลบบล็อกนี้ */
(function () {
  var mc = document.querySelector('.map-controls'), mp = document.getElementById('map');
  if (!mc || !mp) return;
  var home = mc.parentNode, next = mc.nextSibling, open = true, btn;
  function stop(e) { e.stopPropagation(); }
  function enter() {
    mc.classList.add('mk-fs'); mp.appendChild(mc);
    if (!btn) { btn = document.createElement('button'); btn.type = 'button'; btn.className = 'mk-fs-h'; btn.onclick = function () { open = !open; sync(); }; }
    mc.insertBefore(btn, mc.firstChild); sync();
    ['mousedown', 'dblclick', 'wheel', 'touchstart', 'click'].forEach(function (ev) { mc.addEventListener(ev, stop); });
  }
  function sync() { mc.classList.toggle('mk-closed', !open); btn.textContent = '◧ ชั้นข้อมูล ' + (open ? '▾' : '▸'); }
  function leave() {
    mc.classList.remove('mk-fs', 'mk-closed'); if (btn && btn.parentNode === mc) mc.removeChild(btn);
    ['mousedown', 'dblclick', 'wheel', 'touchstart', 'click'].forEach(function (ev) { mc.removeEventListener(ev, stop); });
    home.insertBefore(mc, next && next.parentNode === home ? next : null);
  }
  function chg() {
    var fs = document.fullscreenElement || document.webkitFullscreenElement;
    if (fs === mp) enter(); else if (mc.classList.contains('mk-fs')) leave();
    setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 150);
  }
  ['fullscreenchange', 'webkitfullscreenchange'].forEach(function (e) { document.addEventListener(e, chg); });
})();

/* สวิตช์ซ่อน/แสดง "ป้ายสถานะอ่าง" และ "แผงมุมมองแผนที่" (ดูแผนที่โล่ง ๆ) — เพิ่มในแผงชั้นข้อมูลเดิม; ถอยกลับ: ลบบล็อกนี้ */
(function () {
  var mc = document.querySelector('.map-controls'), mp = document.getElementById('map');
  if (!mc || !mp) return;
  function add(id, cls, text, dot) {
    var l = document.createElement('label'); l.className = 'layer-toggle';
    l.innerHTML = '<input type="checkbox" id="' + id + '" checked><span class="legend-dot" style="' + dot + '"></span>' + text;
    mc.insertBefore(l, mc.firstChild);
    l.querySelector('input').addEventListener('change', function () { mp.classList.toggle(cls, !this.checked); });
  }
  add('toggle-ukm-panel', 'mk-nopanel', 'แผงมุมมอง/อันดับ', 'background:#2a9d8f');
  add('toggle-ukm-pill', 'mk-nopill', 'ป้ายสถานะอ่าง', 'background:#e0a94f');
})();
