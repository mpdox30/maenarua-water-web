/* flood-map-kit.js — ปรับแผนที่จุดเสี่ยง (flood-forecast.html #riskMap) โดยไม่แก้ไฟล์หน้าเดิม
   1) จุดเสี่ยงเป็นป้าย "ชื่อ · ปริมาณน้ำล้น" + วงกระเพื่อมสำหรับระดับเตือนภัย/วิกฤต
   2) แถบเลือกวัน (รวม 7 วัน / วันที่ 1–7 / ▶) — สี-ขนาด-ตัวเลขของจุดเปลี่ยนตามวัน และ sync กับแถบเลื่อนชั้นความลึกน้ำท่วมเดิม
   3) ลำดับความเสี่ยง (คลิกแล้วบินไปจุดนั้น)
   4) popup: กราฟแท่งน้ำล้นคาดการณ์ 7 วัน + ระดับกว๊านเทียบตลิ่ง
   กลับแบบเดิม: ลบ <script src="/__uikit/flood-map-kit.js"> ออกจาก preview_server.py */
(function () {
'use strict';
if (!document.getElementById('riskMap') || typeof L === 'undefined') return;
var M = null;
L.Map.addInitHook(function () { if (this.getContainer && this.getContainer().id === 'riskMap') M = this; });

var HEX = { normal: '#2a9d8f', watch: '#e0a94f', warning: '#e0763f', critical: '#e05252' };
var TH = { normal: 'ปกติ', watch: 'เฝ้าระวัง', warning: 'เตือนภัย', critical: 'วิกฤต' };
var ORD = ['normal', 'watch', 'warning', 'critical'];
var HIDE = ['Mae_Branch1', 'So_HuaiCho', 'RongLaeng', 'ChamTum', 'HuayTham', 'RongPao'];
var BANKED = ['Mae_Main1', 'RongHai'];
var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
var tier = function (mx) { return mx > 0.2 ? 'critical' : mx > 0.05 ? 'warning' : mx > 0.001 ? 'watch' : 'normal'; };
var fmt = function (v) { return v >= 1 ? v.toFixed(2) : v >= 0.01 ? v.toFixed(3) : v > 0 ? v.toFixed(4) : '0'; };
var dshort = function (iso) { var d = new Date(iso + 'T00:00:00'); return isNaN(d) ? iso : d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short' }); };

var D = null, N = [], dates = [], day = 0 /* 0 = รวม 7 วัน */, mk = {}, grp = null, panel = null, timer = null;

function build() {
  dates = (D.kwan_forecast || []).map(function (f) { return f.date; });
  N = Object.keys(D.nodes).filter(function (k) { return HIDE.indexOf(k) < 0; }).map(function (k) {
    var p = D.nodes[k], rows = D.overflow_forecast.filter(function (r) { return r.node === k; }), by = {};
    rows.forEach(function (r) { by[r.date] = r.mcm; });
    var vals = dates.map(function (dt) { return by[dt] || 0; });
    return { k: k, name: p.name_th, lat: p.lat, lon: p.lon, vals: vals, total: vals.reduce(function (a, b) { return a + b; }, 0), bank: D.banks ? D.banks[k] : null };
  });
}
function levelOf(n, d) {
  if (d === 0) { try { if (typeof nodeFlagLevel === 'function') return nodeFlagLevel(D, n.k); } catch (e) {} return tier(Math.max.apply(null, n.vals.concat([0]))); }
  var lv = tier(n.vals[d - 1] || 0);
  if (BANKED.indexOf(n.k) >= 0 && n.bank != null && D.kwan_forecast[d - 1]) {
    var f = D.kwan_forecast[d - 1], k = f.level >= n.bank ? 'critical' : f.p90 >= n.bank ? 'warning' : null;
    if (k && ORD.indexOf(k) > ORD.indexOf(lv)) lv = k;
  }
  return lv;
}
var valOf = function (n, d) { return d === 0 ? n.total : (n.vals[d - 1] || 0); };

/* ---------- popup ---------- */
function popup(n) {
  var W = 250, H = 84, bw = W / (dates.length || 7), mx = Math.max.apply(null, n.vals.concat([0.05])), lv = levelOf(n, 0);
  var bars = n.vals.map(function (v, i) {
    var h = v > 0 ? Math.max(3, v / mx * 48) : 1.5, c = HEX[tier(v)];
    return '<rect x="' + (i * bw + 5) + '" y="' + (58 - h) + '" width="' + (bw - 10) + '" height="' + h + '" rx="3" fill="' + c + '" opacity="' + (i + 1 === day ? 1 : .8) + '"/>' +
      '<text x="' + (i * bw + bw / 2) + '" y="' + (52 - h) + '" text-anchor="middle" class="v">' + (v > 0 ? fmt(v) : '') + '</text>' +
      '<text x="' + (i * bw + bw / 2) + '" y="76" text-anchor="middle" class="t">' + dshort(dates[i]) + '</text>';
  }).join('');
  var kw = '';
  if (BANKED.indexOf(n.k) >= 0 && n.bank != null && D.kwan_now) {
    var diff = D.kwan_now.level - n.bank;
    kw = '<div class="ffp-kw ' + (diff >= 0 ? 'over' : 'ok') + '">ระดับกว๊านวันนี้ <b>' + D.kwan_now.level.toFixed(2) + '</b> ม. · ตลิ่ง ' + n.bank.toFixed(2) + ' ม. → ' + (diff >= 0 ? 'สูงกว่าตลิ่ง +' : 'ต่ำกว่าตลิ่ง ') + diff.toFixed(2) + ' ม.</div>';
  }
  return '<div class="ffp"><div class="ffp-h"><b>' + esc(n.name) + '</b><span style="background:' + HEX[lv] + '">' + TH[lv] + '</span></div>' +
    '<div class="ffp-s">น้ำล้นคาดการณ์รวม 7 วัน <b>' + (n.total > 0 ? fmt(n.total) : '0') + '</b> ล้าน ลบ.ม.</div>' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" class="ffp-ch">' + bars + '</svg>' + kw + '</div>';
}

/* ---------- ป้ายบนแผนที่ ---------- */
function pill(n) {
  var lv = levelOf(n, day), v = valOf(n, day), hot = lv === 'warning' || lv === 'critical';
  return '<div class="ffm ' + lv + (hot ? ' hot' : '') + '" style="--c:' + HEX[lv] + '">' + (hot ? '<s></s><s></s>' : '') + '<i class="dot"></i><span class="n">' + esc(n.name.replace(/\s*\(.*\)$/, '')) + '</span><b class="num">' + (v > 0 ? fmt(v) : '0') + '</b></div>';
}
function refresh() {
  N.forEach(function (n) { if (mk[n.k]) mk[n.k].setIcon(L.divIcon({ className: 'ffm-wrap', html: pill(n), iconSize: [0, 0] })); });
  if (!panel) return;
  var rows = N.slice().sort(function (a, b) { return valOf(b, day) - valOf(a, day) || ORD.indexOf(levelOf(b, day)) - ORD.indexOf(levelOf(a, day)); });
  var mx = Math.max.apply(null, rows.map(function (n) { return valOf(n, day); }).concat([0.001]));
  panel.querySelector('.ffl').innerHTML = rows.map(function (n, i) {
    var lv = levelOf(n, day), v = valOf(n, day);
    return '<button type="button" class="ffr" data-k="' + n.k + '" style="--c:' + HEX[lv] + '"><em>' + (i + 1) + '</em><span class="rn">' + esc(n.name.replace(/\s*\(.*\)$/, '')) + '<small>' + TH[lv] + '</small></span><span class="rb"><i style="width:' + Math.max(v > 0 ? 6 : 0, v / mx * 100).toFixed(0) + '%"></i></span><b class="num">' + (v > 0 ? fmt(v) : '0') + '</b></button>';
  }).join('');
  [].forEach.call(panel.querySelectorAll('.ffd button'), function (b) { b.classList.toggle('on', +b.dataset.d === day); });
  panel.querySelector('.ffu').textContent = day === 0 ? 'ล้าน ลบ.ม. รวม 7 วัน' : 'ล้าน ลบ.ม. ' + dshort(dates[day - 1]);
}
function setDay(n, fromSlider) {
  day = n; refresh();
  var r = document.getElementById('dayRange');
  if (!fromSlider && r && n > 0 && +r.value !== n) { r.value = n; r.dispatchEvent(new Event('input', { bubbles: true })); }
}
function stop() { if (timer) { clearInterval(timer); timer = null; var p = panel && panel.querySelector('.ffp-play'); if (p) p.textContent = '▶'; } }

function buildPanel() {
  var Ctl = L.Control.extend({
    options: { position: 'bottomleft' },
    onAdd: function () {
      var d = L.DomUtil.create('div', 'ffm-panel'); panel = d;
      d.innerHTML = '<button type="button" class="ph">⚠ ลำดับความเสี่ยง <i>▾</i></button><div class="pb"><div class="ffd"><button type="button" class="ffp-play" title="เล่น">▶</button><button type="button" data-d="0" class="on">รวม</button>' +
        dates.map(function (_, i) { return '<button type="button" data-d="' + (i + 1) + '">' + (i + 1) + '</button>'; }).join('') + '</div>' +
        '<div class="ffu"></div><div class="ffl"></div><div class="ffg"><span><i style="background:' + HEX.normal + '"></i>ปกติ</span><span><i style="background:' + HEX.watch + '"></i>เฝ้าระวัง</span><span><i style="background:' + HEX.warning + '"></i>เตือนภัย</span><span><i style="background:' + HEX.critical + '"></i>วิกฤต</span></div><div class="ffv"><select id="ffVil"><option value="">ย่านของฉัน: เลือกหมู่บ้าน…</option></select><div class="vi" id="ffVi"></div></div></div>';
      L.DomEvent.disableClickPropagation(d); L.DomEvent.disableScrollPropagation(d);
      d.querySelector('.ph').addEventListener('click', function () { d.classList.toggle('shut'); });
      d.querySelector('.ffd').addEventListener('click', function (e) {
        var b = e.target.closest('button'); if (!b) return;
        if (b.classList.contains('ffp-play')) {
          if (timer) { stop(); return; }
          b.textContent = '⏸'; setDay(day % dates.length + 1);
          timer = setInterval(function () { setDay(day % dates.length + 1); }, 1300); return;
        }
        stop(); setDay(+b.dataset.d);
      });
      d.querySelector('.ffl').addEventListener('click', function (e) {
        var b = e.target.closest('.ffr'); if (!b) return; var m = mk[b.dataset.k]; if (!m) return;
        M.flyTo(m.getLatLng(), Math.max(M.getZoom(), 14), { duration: .8 }); setTimeout(function () { m.openPopup(); }, 850);
      });
      return d;
    }
  });
  new Ctl().addTo(M);
  if (window.innerWidth <= 640 && panel) panel.classList.add('shut');   /* มือถือ: เริ่มแบบพับ */
}

/* ---------- ย่านของฉัน ---------- */
var VIL = [], vlayer = null;
function villages() {
  fetch('assets/data/villages.geojson.json').then(function (r) { return r.json(); }).then(function (g) {
    VIL = g.features.slice().sort(function (a, b) { return a.properties.Moo - b.properties.Moo; });
    var sel = panel.querySelector('#ffVil'); sel.insertAdjacentHTML('beforeend', VIL.map(function (f, i) { return '<option value="' + i + '">หมู่ ' + f.properties.Moo + ' ' + esc(f.properties.Name_TH) + '</option>'; }).join(''));
    sel.addEventListener('change', function () { pick(this.value); });
  }).catch(function () { var v = panel.querySelector('.ffv'); if (v) v.style.display = 'none'; });
}
function pick(i) {
  var vi = panel.querySelector('#ffVi'); if (vlayer) { M.removeLayer(vlayer); vlayer = null; } if (i === '') { vi.innerHTML = ''; return; }
  var f = VIL[+i]; vlayer = L.geoJSON(f, { style: { color: '#9d7fe0', weight: 3, fillColor: '#9d7fe0', fillOpacity: .18, dashArray: '6 4' }, interactive: false }).addTo(M);
  var b = vlayer.getBounds(), c = b.getCenter(); M.flyToBounds(b, { maxZoom: 15, duration: .9 });
  var near = N.map(function (n) { return { n: n, d: M.distance(c, L.latLng(n.lat, n.lon)) }; }).sort(function (a, b2) { return a.d - b2.d; })[0], lv = near ? levelOf(near.n, day) : 'normal';
  vi.innerHTML = '<b>หมู่ ' + f.properties.Moo + ' ' + esc(f.properties.Name_TH) + '</b>' + (near ? '<br>จุดเสี่ยงที่ใกล้ที่สุด: ' + esc(near.n.name.replace(/\s*\(.*\)$/, '')) + ' (' + (near.d / 1000).toFixed(1) + ' กม.) · <span style="color:' + HEX[lv] + '">' + TH[lv] + '</span>' : '') + '<br><button type="button" class="ffvb">น้ำฝนที่ตกในหมู่บ้านนี้ไหลไปไหน</button>';
  var bt = vi.querySelector('.ffvb'); if (bt) bt.onclick = function () { if (window.__ukFlow) window.__ukFlow.run2d(c.lat, c.lng); else this.textContent = 'ฟีเจอร์นี้ยังไม่พร้อม'; };
}
function start() {
  build();
  // ซ่อนจุดวงกลมเดิม (ยังอยู่ใต้ป้ายใหม่ ไม่ถูกลบ)
  var orig = null;
  M.eachLayer(function (l) { if (l instanceof L.LayerGroup && !(l instanceof L.FeatureGroup) && l.getLayers().length && l.getLayers().every(function (x) { return x instanceof L.CircleMarker; })) orig = l; });
  if (orig) orig.eachLayer(function (c) { c.setStyle({ opacity: 0, fillOpacity: 0 }); if (c.getElement) { var el = c.getElement(); if (el) el.style.pointerEvents = 'none'; } c.options.interactive = false; });
  grp = L.layerGroup();
  N.forEach(function (n) {
    var m = L.marker([n.lat, n.lon], { icon: L.divIcon({ className: 'ffm-wrap', html: pill(n), iconSize: [0, 0] }), zIndexOffset: 900, riseOnHover: true }).addTo(grp);
    m.bindPopup(function () { return popup(n); }, { minWidth: 260, maxWidth: 280, className: 'ukp-pop' }); mk[n.k] = m;
  });
  grp.addTo(M);
  if (orig) { orig.on('add', function () { if (!M.hasLayer(grp)) grp.addTo(M); }); orig.on('remove', function () { M.removeLayer(grp); }); }
  buildPanel(); refresh(); villages();
  // sync กับแถบเลื่อนวันเดิม (กดเล่น/เลื่อนเอง)
  var lab = document.getElementById('dayLabel'), rg = document.getElementById('dayRange');
  if (lab && rg) new MutationObserver(function () { var v = +rg.value; if (v >= 1 && v <= dates.length && v !== day && day !== 0) setDay(v, true); else if (v >= 1 && v !== day && day === 0 && document.getElementById('daySlider').classList.contains('show')) setDay(v, true); }).observe(lab, { childList: true, characterData: true, subtree: true });
  window.addEventListener('uk-theme', refresh);
}
var tries = 0, iv = setInterval(function () {
  tries++;
  if (M && D) { clearInterval(iv); try { start(); } catch (e) { console.warn('flood-map-kit', e); } }
  else if (tries > 80) clearInterval(iv);
}, 300);
fetch('assets/data/flood_latest.json').then(function (r) { return r.json(); }).then(function (j) { D = j; }).catch(function () {});
})();
