/* report-kit.js — ปุ่ม "สรุป" ที่หัวเว็บ: สร้างรายงานสรุปจากข้อมูลสดตอนกด (ไม่ต้องมีเซิร์ฟเวอร์ ไม่ส่งข้อมูลออกนอกเครื่อง)
   - ฉบับประชาชน : ภาพ PNG 1080×1920 (ส่ง LINE/โซเชียล) สถานะ 4 ระดับตามเกณฑ์เดียวกับหน้า flood-forecast
   - ฉบับเจ้าหน้าที่ : A4 พิมพ์/บันทึกเป็น PDF (ตัวเลขครบ + ความน่าเชื่อถือ + ข้อจำกัด)
   ภาษา TH/EN ตาม uk_lang · ตั้งเบอร์ติดต่อท้ายฉบับประชาชนที่ CONTACT ด้านล่าง หรือ window.UK_REPORT_CONTACT */
(function () {
  'use strict';
  var CONTACT = window.UK_REPORT_CONTACT || '';          // เช่น 'เทศบาลตำบลแม่นาเรือ โทร 0-5444-xxxx'
  var SITE_URL = 'https://mpdox30.github.io/maenarua-water-web/';
  var EN = false; try { EN = (localStorage.getItem('uk_lang') || '') === 'en'; } catch (e) { }
  if (document.documentElement.lang === 'en') EN = true;
  function T(th, en) { return EN ? en : th; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var cs = document.currentScript, BASE = '';
  if (cs && cs.src) { var mm = cs.src.match(/^(.*\/)(?:assets\/uikit|__uikit)\//); if (mm) BASE = mm[1]; }
  if (!BASE) BASE = location.href.replace(/[^\/]*([?#].*)?$/, '');
  function J(p) { return fetch(BASE + 'assets/data/' + p, { cache: 'no-store' }).then(function (r) { if (!r.ok) throw 0; return r.json(); }).catch(function () { return null; }); }

  /* ---------- เกณฑ์/ข้อความ (เหมือนหน้า flood-forecast: ปกติ / เฝ้าระวัง / เตือนภัย / วิกฤต) ---------- */
  var LV = ['normal', 'watch', 'warning', 'critical'];
  var HEX = { normal: '#2a9d8f', watch: '#e0a94f', warning: '#e0763f', critical: '#e05252' };
  function lvName(l) { return { normal: T('ปกติ', 'Normal'), watch: T('เฝ้าระวัง', 'Watch'), warning: T('เตือนภัย', 'Warning'), critical: T('วิกฤต', 'Critical') }[l]; }
  function lvAdvice(l) {
    return { normal: T('ยังไม่พบสัญญาณน้ำล้นตลิ่งใน 7 วันข้างหน้า ติดตามข่าวสารตามปกติ', 'No sign of overbank flow in the next 7 days. Keep following updates as usual.'),
      watch: T('ระดับน้ำใกล้ตลิ่งหรือคาดมีน้ำล้นเล็กน้อย ติดตามข่าวสารอย่างต่อเนื่อง', 'Water is near the bank or slight overflow is expected. Keep following updates closely.'),
      warning: T('คาดมีน้ำล้นตลิ่ง ผู้อยู่พื้นที่ลุ่มต่ำควรเตรียมของใช้จำเป็นและยกของขึ้นที่สูง', 'Overbank flow is expected. Residents of low-lying areas should prepare essentials and raise belongings.'),
      critical: T('ระดับน้ำสูงเกินตลิ่งหรือคาดว่าล้นมาก โปรดติดตามประกาศของหน่วยงานในพื้นที่อย่างใกล้ชิดและเตรียมพร้อม', 'Water is above the bank or heavy overflow is expected. Follow local-authority announcements closely and stay prepared.') }[l];
  }
  function vLevel(d) { return d >= .5 ? 'critical' : d >= .1 ? 'warning' : d >= .01 ? 'watch' : 'normal'; }   // เกณฑ์เดียวกับแผนที่ 3 มิติ
  function fillWord(p) { return p >= 100 ? T('เต็มอ่าง', 'Full') : p >= 80 ? T('ค่อนข้างเต็ม', 'Nearly full') : p >= 50 ? T('ปานกลาง', 'Moderate') : p >= 25 ? T('ค่อนข้างน้อย', 'Low') : T('น้อย', 'Very low'); }
  function rainWord(mm) { return mm < 1 ? T('แทบไม่มีฝน', 'Almost none') : mm < 10 ? T('ฝนเล็กน้อย', 'Light') : mm < 35 ? T('ฝนปานกลาง', 'Moderate') : mm < 90 ? T('ฝนหนัก', 'Heavy') : T('ฝนหนักมาก', 'Very heavy'); }
  var MO = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'], MOE = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function pd(s) { var m = /(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d):(\d\d))?/.exec(String(s || '')); return m ? { y: +m[1], mo: +m[2], d: +m[3], h: m[4], mi: m[5] } : null; }
  function fDate(s, short) { var p = pd(s); if (!p) return '—'; return short ? (p.d + ' ' + (EN ? MOE : MO)[p.mo - 1]) : EN ? p.d + ' ' + MOE[p.mo - 1] + ' ' + p.y : p.d + ' ' + MO[p.mo - 1] + ' ' + (p.y + 543); }
  function fDT(s) { var p = pd(s); return p && p.h ? fDate(s) + ' ' + p.h + ':' + p.mi + (EN ? '' : ' น.') : fDate(s); }
  function f2(x, n) { return x == null || isNaN(x) ? '—' : Number(x).toFixed(n == null ? 2 : n); }

  /* ---------- โหลดข้อมูล + รวมเป็นโมเดลเดียว ---------- */
  function inRing(x, y, r) { var o = false; for (var i = 0, j = r.length - 1; i < r.length; j = i++) { if ((r[i][1] > y) !== (r[j][1] > y) && x < (r[j][0] - r[i][0]) * (y - r[i][1]) / (r[j][1] - r[i][1]) + r[i][0]) o = !o; } return o; }
  function inGeom(g, x, y) { var polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates; return polys.some(function (p) { return inRing(x, y, p[0]); }); }
  function ctr(c) { var r = c; while (typeof r[0][0] !== 'number') r = r[0]; var sx = 0, sy = 0; r.forEach(function (p) { sx += p[0]; sy += p[1]; }); return [sx / r.length, sy / r.length]; }
  function load() {
    return Promise.all([J('flood_latest.json'), J('monitoring.json'), J('villages.geojson.json'), J('buildings_flood_risk.geojson'), J('latest.json'), J('water_demand.json')]).then(function (a) {
      var fl = a[0], mo = a[1], vg = a[2], bg = a[3], lt = a[4], wd = a[5];
      if (!fl) throw new Error('flood_latest');
      var m = { fl: fl, lt: lt, wd: wd, gen: fl.generated_at, level: fl.flags && fl.flags.overall || 'normal', kwan: fl.kwan_now.level,
        bankMain: fl.banks.Mae_Main1, bankRH: fl.banks.RongHai, fc: fl.kwan_forecast || [], obs: fl.kwan_observed_30d || [], rain: fl.rain_7d || {}, res: [], vil: [], mon: mo };
      if (LV.indexOf(m.level) < 0) m.level = 'normal';
      m.res = ((mo && mo.stations) || []).map(function (s) { return { name: s.name_th, en: s.name_en, pct: s.capacity_pct, v: s.storage_m3 / 1e6, mx: s.storage_max_m3 / 1e6, lv: s.water_level, spill: s.distance_to_spillway_m, t: s.measure_datetime }; });
      if (vg && bg) {
        var V = (vg.features || []).filter(function (f) { return f.geometry; }).map(function (f) { return { name: f.properties.Name_TH || ('หมู่ ' + f.properties.Moo), moo: f.properties.Moo, g: f.geometry, n: 0, w1: 0, w10: 0, mx: 0 }; });
        (bg.features || []).forEach(function (f) {
          var c = ctr(f.geometry.coordinates), ds = (f.properties || {}).depths || [], d = ds.length ? Math.max.apply(null, ds) : 0;
          for (var i = 0; i < V.length; i++) if (inGeom(V[i].g, c[0], c[1])) { var v = V[i]; v.n++; if (d > v.mx) v.mx = d; if (d >= .001) v.w1++; if (d >= .1) v.w10++; break; }
        });
        m.vil = V.map(function (v) { v.lv = vLevel(v.mx); return v; });
      }
      return m;
    });
  }
  function trend(m) {
    var L = m.fc.map(function (x) { return x.level; }); if (!L.length) return null;
    var hi = Math.max.apply(null, m.fc.map(function (x) { return x.p90 != null ? x.p90 : x.level; })), d = L[L.length - 1] - m.kwan;
    return { dir: Math.abs(d) < .05 ? T('ทรงตัว', 'steady') : d > 0 ? T('สูงขึ้น', 'rising') : T('ลดลง', 'falling'), min: Math.min.apply(null, L), max: Math.max.apply(null, L), p90: hi };
  }
  function dm(s) { return Math.abs(s).toFixed(2); }
  function kwanSentence(m) {
    var g = m.kwan - m.bankMain;
    return T('ระดับกว๊านพะเยาวันนี้ ' + f2(m.kwan) + ' ม.รทก. ' + (g >= 0 ? 'สูงกว่า' : 'ต่ำกว่า') + 'ตลิ่งห้วยแม่นาเรือ (' + f2(m.bankMain) + ') อยู่ ' + dm(g) + ' ม.',
      'Kwan Phayao today: ' + f2(m.kwan) + ' m MSL — ' + dm(g) + ' m ' + (g >= 0 ? 'above' : 'below') + ' the Mae Na Rua stream bank (' + f2(m.bankMain) + ').');
  }
  function villageSentence(m) {
    if (!m.vil.length) return '';
    var w = m.vil.filter(function (v) { return v.lv !== 'normal'; });
    if (!w.length) { var mx = Math.max.apply(null, m.vil.map(function (v) { return v.mx; })); return T('ยังไม่พบหมู่บ้านที่น้ำท่วมถึงอาคารใน 7 วันข้างหน้า' + (mx >= .001 ? ' (น้ำตื้นสุดราว ' + (mx * 1000).toFixed(0) + ' มม.)' : ''), 'No village is projected to get water into buildings in the next 7 days' + (mx >= .001 ? ' (max ≈ ' + (mx * 1000).toFixed(0) + ' mm)' : '') + '.'); }
    return T(w.length + ' หมู่บ้านมีน้ำท่วมถึงอาคารใน 7 วันข้างหน้า', w.length + ' village(s) projected to have water reach buildings within 7 days');
  }

  /* ---------- ฉบับประชาชน: PNG 1080×1920 ---------- */
  var FONT = '"IBM Plex Sans Thai","Noto Sans Thai","Leelawadee UI",Tahoma,sans-serif';
  var SEG = null; try { SEG = new Intl.Segmenter(EN ? 'en' : 'th', { granularity: 'word' }); } catch (e) { }
  function drawVillager(cv, m) {
    var t = document.createElement('canvas'), end = paint(t, m, 3400);
    paint(cv, m, Math.max(1920, Math.round(end + 200)));
  }
  function paint(cv, m, H) {
    var W = 1080; cv.width = W; cv.height = H; var c = cv.getContext('2d');
    function F(sz, w) { return (w || 400) + ' ' + sz + 'px ' + FONT; }
    function rr(x, y, w, h, r, fill, stroke) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); if (fill) { c.fillStyle = fill; c.fill(); } if (stroke) { c.strokeStyle = stroke; c.lineWidth = 2; c.stroke(); } }
    function tx(s, x, y, sz, w, col, al) { c.font = F(sz, w); c.fillStyle = col || '#eef6f4'; c.textAlign = al || 'left'; c.textBaseline = 'alphabetic'; c.fillText(s, x, y); }
    function wrap(s, x, y, mw, sz, w, col, lh) {
      c.font = F(sz, w); var parts = SEG ? Array.from(SEG.segment(s)).map(function (p) { return p.segment; }) : s.split(''), ln = '', yy = y;
      parts.forEach(function (p) { var t = ln + p; if (c.measureText(t).width > mw && ln) { tx(ln.trim(), x, yy, sz, w, col); yy += lh; ln = p.replace(/^\s+/, ''); } else ln = t; });
      if (ln.trim()) { tx(ln.trim(), x, yy, sz, w, col); yy += lh; } return yy;
    }
    var col = HEX[m.level], tr = trend(m), P = 56, IW = W - P * 2;
    var g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#0d2a34'); g.addColorStop(1, '#06161c'); c.fillStyle = g; c.fillRect(0, 0, W, H);
    // หัว
    tx(T('แม่นาเรือ · สรุปสถานการณ์น้ำ', 'Mae Na Rua · Water Situation'), P, 92, 44, 700, '#7fe0d1');
    tx(T('ข้อมูลล่าสุด ', 'Data as of ') + fDT(m.gen), P, 138, 28, 400, '#8aa3a0');
    // สถานะ
    rr(P, 176, IW, 316, 36, col + '26', col); rr(P, 176, 18, 316, 9, col);
    c.beginPath(); c.arc(P + 130, 334, 70, 0, Math.PI * 2); c.fillStyle = col; c.fill();
    c.strokeStyle = '#06161c'; c.lineWidth = 14; c.lineCap = 'round'; c.beginPath();
    if (m.level === 'normal') { c.moveTo(P + 100, 335); c.lineTo(P + 122, 359); c.lineTo(P + 162, 309); } else { c.moveTo(P + 130, 295); c.lineTo(P + 130, 341); c.moveTo(P + 130, 365); c.lineTo(P + 130, 366); }
    c.stroke(); c.lineCap = 'butt';
    tx(T('ระดับ', 'Level'), P + 250, 262, 32, 500, '#c4d6d3'); tx(lvName(m.level), P + 250, 356, 92, 700, col);
    var y = wrap(lvAdvice(m.level), P + 250, 402, IW - 270, 26, 400, '#eef6f4', 35);
    // กว๊าน
    y = 552; tx(T('ระดับน้ำกว๊านพะเยา', 'Kwan Phayao water level'), P, y, 38, 700);
    y = wrap(kwanSentence(m), P, y + 50, IW, 30, 400, '#c4d6d3', 42);
    var cx0 = P + 90, cx1 = W - P - 10, cy0 = y + 14, cy1 = cy0 + 270;
    rr(P, cy0 - 14, IW, 270 + 62, 28, 'rgba(255,255,255,.04)');
    var ob = m.obs.slice(-8), pts = ob.concat(m.fc), n = pts.length, vals = pts.map(function (p) { return p.level; }).concat(m.fc.map(function (p) { return p.p90 || p.level; }), m.fc.map(function (p) { return p.p10 || p.level; }), [m.bankMain]);
    var lo = Math.min.apply(null, vals) - .08, hi = Math.max.apply(null, vals) + .08; if (m.bankRH > lo - .3 && m.bankRH < hi + .3) { lo = Math.min(lo, m.bankRH - .05); hi = Math.max(hi, m.bankRH + .05); }
    function X(i) { return cx0 + (cx1 - cx0) * i / Math.max(1, n - 1); } function Y(v) { return cy1 - (cy1 - cy0 - 20) * (v - lo) / (hi - lo); }
    [[m.bankMain, '#e05252', T('ตลิ่งห้วยแม่นาเรือ', 'Mae Na Rua bank')], [m.bankRH, '#e0763f', T('ตลิ่งห้วยร่องไฮ', 'Rong Hai bank')]].forEach(function (b) {
      if (b[0] < lo || b[0] > hi) return; c.setLineDash([10, 8]); c.strokeStyle = b[1]; c.lineWidth = 2.5; c.beginPath(); c.moveTo(cx0, Y(b[0])); c.lineTo(cx1, Y(b[0])); c.stroke(); c.setLineDash([]);
      tx(b[2] + ' ' + f2(b[0]), cx1, Y(b[0]) - 8, 22, 500, b[1], 'right');
    });
    var k0 = ob.length - 1;      // แถบ P10–P90
    if (m.fc.length) {
      c.beginPath(); m.fc.forEach(function (p, i) { var xx = X(k0 + 1 + i); i ? c.lineTo(xx, Y(p.p90 != null ? p.p90 : p.level)) : c.moveTo(xx, Y(p.p90 != null ? p.p90 : p.level)); });
      for (var i = m.fc.length - 1; i >= 0; i--) c.lineTo(X(k0 + 1 + i), Y(m.fc[i].p10 != null ? m.fc[i].p10 : m.fc[i].level)); c.closePath(); c.fillStyle = 'rgba(69,194,173,.22)'; c.fill();
    }
    c.lineWidth = 5; c.lineJoin = 'round'; c.strokeStyle = '#eef6f4'; c.beginPath(); ob.forEach(function (p, i) { i ? c.lineTo(X(i), Y(p.level)) : c.moveTo(X(i), Y(p.level)); }); c.stroke();
    c.setLineDash([12, 9]); c.strokeStyle = '#45c2ad'; c.beginPath(); c.moveTo(X(k0), Y(ob[k0] ? ob[k0].level : m.kwan)); m.fc.forEach(function (p, i) { c.lineTo(X(k0 + 1 + i), Y(p.level)); }); c.stroke(); c.setLineDash([]);
    c.beginPath(); c.arc(X(k0), Y(m.kwan), 10, 0, 7); c.fillStyle = '#eef6f4'; c.fill();
    tx(T('วันนี้', 'Today'), X(k0), cy1 + 34, 22, 600, '#eef6f4', 'center');
    if (m.fc.length) { tx(fDate(m.fc[m.fc.length - 1].date, 1), X(n - 1) + 4, cy1 + 34, 22, 400, '#8aa3a0', 'right'); tx(T('พยากรณ์ 7 วัน', '7-day forecast'), (X(k0) + X(n - 1)) / 2 - 10, cy1 + 34, 22, 400, '#45c2ad', 'center'); }
    tx(f2(hi - .08), cx0 - 10, Y(hi - .08) + 8, 20, 400, '#8aa3a0', 'right'); tx(f2(lo + .08), cx0 - 10, Y(lo + .08) + 8, 20, 400, '#8aa3a0', 'right');
    y = cy1 + 64;
    if (tr) y = wrap(T('7 วันข้างหน้าคาดว่าระดับ' + tr.dir + ' (ช่วง ' + f2(tr.min) + '–' + f2(tr.max) + ' ม. กรอบสูงสุด ' + f2(tr.p90) + ' ม.)', 'Next 7 days: level ' + tr.dir + ' (' + f2(tr.min) + '–' + f2(tr.max) + ' m; upper bound ' + f2(tr.p90) + ' m).'), P, y + 22, IW, 28, 400, '#c4d6d3', 40);
    // หมู่บ้านที่ต้องจับตา
    y += 22; tx(T('หมู่บ้านที่ต้องจับตา', 'Villages to watch'), P, y, 38, 700); y += 18;
    var watch = m.vil.filter(function (v) { return v.lv !== 'normal'; }).sort(function (a, b) { return b.mx - a.mx; }).slice(0, 3);
    if (!watch.length) { y = wrap(villageSentence(m) || T('ไม่มีข้อมูลหมู่บ้าน', 'No village data'), P, y + 40, IW, 30, 400, '#c4d6d3', 42); }
    else watch.forEach(function (v) {
      y += 14; rr(P, y, IW, 76, 20, HEX[v.lv] + '26', HEX[v.lv]); tx(T('หมู่ ', 'Moo ') + v.moo + ' ' + v.name, P + 26, y + 50, 30, 600); tx(lvName(v.lv) + ' · ' + (v.mx >= .1 ? v.mx.toFixed(2) + ' ม.' : (v.mx * 100).toFixed(1) + ' ซม.'), W - P - 26, y + 50, 28, 600, HEX[v.lv], 'right'); y += 76;
    });
    // ฝน
    y += 52; tx(T('ฝนสะสม 7 วันที่ผ่านมา', 'Rain in the past 7 days'), P, y, 38, 700); y += 26;
    [[T('ภูเขา', 'Mountain'), m.rain.mtn], [T('ที่ราบ', 'Lowland'), m.rain.low]].forEach(function (r) {
      var v = r[1] || 0; y += 52; tx(r[0], P, y, 28, 500, '#c4d6d3'); rr(P + 150, y - 26, 560, 26, 13, 'rgba(255,255,255,.08)'); rr(P + 150, y - 26, Math.max(10, 560 * Math.min(1, v / 100)), 26, 13, '#8fc4ff');
      tx(f2(v, 0) + T(' มม.', ' mm'), P + 730, y - 2, 28, 700, '#eef6f4'); tx(rainWord(v), W - P, y - 2, 24, 400, '#8aa3a0', 'right');
    });
    // อ่างเก็บน้ำ
    y += 70; tx(T('ปริมาณน้ำในอ่างเก็บน้ำแต่ละแห่ง', 'Water stored in each reservoir'), P, y, 38, 700); y += 8;
    m.res.slice(0, 6).forEach(function (r) {
      y += 74; var p = r.pct == null ? 0 : r.pct, cc = p >= 80 ? '#45c2ad' : p >= 50 ? '#7fe0d1' : p >= 25 ? '#e0a94f' : '#e0763f';
      tx(EN ? r.en : r.name.replace(/^อ่างเก็บน้ำ/, T('อ่าง', '') ), P, y - 18, 27, 500, '#eef6f4');
      rr(P, y - 4, 620, 24, 12, 'rgba(255,255,255,.08)'); rr(P, y - 4, Math.max(12, 620 * Math.min(1, p / 100)), 24, 12, cc);
      tx(f2(p, 0) + '%  ' + fillWord(p), P + 640, y + 16, 26, 700, cc);
      tx(f2(r.v) + ' / ' + f2(r.mx) + T(' ล้าน ลบ.ม.', ' M m³'), W - P, y - 18, 24, 400, '#8aa3a0', 'right');
    });
    var endY = y + 24;
    // ท้ายหน้า
    var fy = H - 150; c.fillStyle = 'rgba(255,255,255,.12)'; c.fillRect(P, fy - 26, IW, 2);
    var yy = wrap(T('เป็นข้อมูลพยากรณ์เพื่อประกอบการเฝ้าระวัง ไม่ใช่คำสั่งอพยพอย่างเป็นทางการ โปรดปฏิบัติตามประกาศของหน่วยงานในพื้นที่', 'Forecast information to support monitoring — not an official evacuation order. Please follow local-authority announcements.'), P, fy, IW, 22, 400, '#c4d6d3', 31);
    if (CONTACT) tx(CONTACT, P, yy + 2, 23, 600, '#eef6f4');
    tx(SITE_URL.replace(/^https:\/\//, ''), W - P, H - 36, 22, 500, '#7fe0d1', 'right');
    tx(T('ที่มา: สสน. · HII · แบบจำลอง WMB', 'Sources: HII/NHC · WMB model'), P, H - 36, 20, 400, '#66807d');
    return endY;
  }

  /* ---------- ฉบับเจ้าหน้าที่: A4 พิมพ์/PDF ---------- */
  function svgKwan(m) {
    var ob = m.obs.slice(-30), fc = m.fc, n = ob.length + fc.length, W = 720, H = 200, l = 44, r = 10, t = 12, b = 26;
    var vals = ob.map(function (p) { return p.level; }).concat(fc.map(function (p) { return p.p90 || p.level; }), fc.map(function (p) { return p.p10 || p.level; }), [m.bankMain]);
    var lo = Math.min.apply(null, vals) - .1, hi = Math.max.apply(null, vals) + .1;
    function X(i) { return l + (W - l - r) * i / Math.max(1, n - 1); } function Y(v) { return H - b - (H - b - t) * (v - lo) / (hi - lo); }
    function path(a, off) { return a.map(function (p, i) { return (i ? 'L' : 'M') + X(i + off).toFixed(1) + ' ' + Y(p.level).toFixed(1); }).join(''); }
    var band = fc.length ? 'M' + fc.map(function (p, i) { return X(ob.length + i).toFixed(1) + ' ' + Y(p.p90 != null ? p.p90 : p.level).toFixed(1); }).join('L') + 'L' + fc.slice().reverse().map(function (p, i) { return X(n - 1 - i).toFixed(1) + ' ' + Y(p.p10 != null ? p.p10 : p.level).toFixed(1); }).join('L') + 'Z' : '';
    var bl = [[m.bankMain, '#c0392b', 'Mae Na Rua'], [m.bankRH, '#d35400', 'Rong Hai']].filter(function (x) { return x[0] >= lo && x[0] <= hi; }).map(function (x) { return '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(x[0]) + '" y2="' + Y(x[0]) + '" stroke="' + x[1] + '" stroke-dasharray="5 4"/><text x="' + (W - r) + '" y="' + (Y(x[0]) - 3) + '" text-anchor="end" font-size="9" fill="' + x[1] + '">' + x[2] + ' ' + f2(x[0]) + '</text>'; }).join('');
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" style="display:block"><rect width="' + W + '" height="' + H + '" fill="#f6f9f9"/>' + bl + '<path d="' + band + '" fill="#45c2ad" opacity=".25"/><path d="' + path(ob, 0) + '" fill="none" stroke="#123643" stroke-width="1.8"/><path d="M' + X(ob.length - 1).toFixed(1) + ' ' + Y(ob.length ? ob[ob.length - 1].level : m.kwan).toFixed(1) + path(fc, ob.length).replace(/^M/, 'L') + '" fill="none" stroke="#12846f" stroke-width="1.8" stroke-dasharray="5 3"/>' +
      '<text x="' + (l - 4) + '" y="' + (Y(hi - .1) + 3) + '" font-size="9" text-anchor="end" fill="#555">' + f2(hi - .1) + '</text><text x="' + (l - 4) + '" y="' + (Y(lo + .1) + 3) + '" font-size="9" text-anchor="end" fill="#555">' + f2(lo + .1) + '</text>' +
      '<text x="' + l + '" y="' + (H - 8) + '" font-size="9" fill="#555">' + fDate(ob.length ? ob[0].date : '', 1) + '</text><text x="' + X(ob.length - 1) + '" y="' + (H - 8) + '" font-size="9" text-anchor="middle" fill="#123643" font-weight="700">' + T('วันนี้', 'Today') + '</text><text x="' + (W - r) + '" y="' + (H - 8) + '" font-size="9" text-anchor="end" fill="#555">' + (fc.length ? fDate(fc[fc.length - 1].date, 1) : '') + '</text></svg>';
  }
  function officialHtml(m) {
    var fl = m.fl, col = HEX[m.level], inf = m.lt && m.lt.forecasts && m.lt.forecasts.inflow && m.lt.forecasts.inflow.forecast, tr = trend(m);
    function tbl(head, rows) { return '<table><thead><tr>' + head.map(function (h) { return '<th>' + esc(h) + '</th>'; }).join('') + '</tr></thead><tbody>' + rows.map(function (r) { return '<tr>' + r.map(function (c) { return '<td>' + c + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table>'; }
    function sec(h, body) { return '<section><h2>' + esc(h) + '</h2>' + body + '</section>'; }
    var h = '<header><div><h1>' + T('รายงานสรุปสถานการณ์น้ำ — สำหรับเจ้าหน้าที่', 'Water Situation Report — for officials') + '</h1><p>' + T('ตำบลแม่นาเรือ จ.พะเยา · ข้อมูล ณ ', 'Mae Na Rua, Phayao · data as of ') + esc(fDT(m.gen)) + '</p></div><div class="lv" style="background:' + col + '">' + esc(lvName(m.level)) + '</div></header>';
    h += '<p class="lead">' + esc(kwanSentence(m)) + ' ' + esc(villageSentence(m)) + '</p>';
    if (fl.flags && fl.flags.message) h += '<ul class="msg">' + String(fl.flags.message).split(' | ').map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') + '</ul>';
    var fr = m.fc.map(function (p) { return [esc(fDate(p.date, 1)), f2(p.level), f2(p.p10), f2(p.p90), (p.p90 >= m.bankMain ? '<b style="color:#c0392b">' : '') + f2(p.p90 - m.bankMain) + (p.p90 >= m.bankMain ? '</b>' : '')]; });
    h += sec(T('1. กว๊านพะเยา', '1. Kwan Phayao'), svgKwan(m) + '<p class="note">' + T('เส้นทึบ = สังเกตการณ์ 30 วัน · เส้นประ/แถบ = พยากรณ์ 7 วัน (P10–P90) · เส้นแดง = ตลิ่ง', 'Solid = observed 30 d · dashed/band = 7-day forecast (P10–P90) · red = bank') + '</p>' +
      tbl([T('วันที่', 'Date'), T('ระดับ (ม.รทก.)', 'Level (m)'), 'P10', 'P90', T('P90 − ตลิ่งแม่นาเรือ (ม.)', 'P90 − bank (m)')], fr) +
      '<p class="note">' + T('น้ำล้นรวม 7 วัน ', '7-day overflow total ') + f2(fl.overflow_total_7d, 3) + T(' ล้าน ลบ.ม. · ฝนสะสม 7 วันย้อนหลัง ภูเขา ', ' M m³ · past-7-day rain: mountain ') + f2(m.rain.mtn, 0) + T(' / ที่ราบ ', ' / lowland ') + f2(m.rain.low, 0) + ' mm' + (tr ? ' · ' + T('แนวโน้ม', 'trend') + ' ' + tr.dir : '') + '</p>');
    if (inf && inf.horizons) {
      var hz = Object.keys(inf.horizons).map(function (k, i) { var x = inf.horizons[k], ns = x.walkforward_cv_nse && x.walkforward_cv_nse.mean; return ['+' + (i + 1), Math.round(x.prediction_m3_per_day).toLocaleString('en-US'), esc(x.model_name || '—'), f2(ns, 3), ns == null ? '—' : ns >= .5 ? T('เชื่อถือได้', 'reliable') : ns >= 0 ? T('พอใช้', 'fair') : '<b style="color:#c0392b">' + T('ยังไม่แม่น', 'weak') + '</b>']; });
      h += sec(T('2. น้ำไหลเข้าอ่างแม่นาเรือ 7 วัน', '2. Inflow to the reservoir, 7 days'), tbl([T('ล่วงหน้า (วัน)', 'Lead (d)'), T('พยากรณ์ (ลบ.ม./วัน)', 'Forecast (m³/d)'), T('โมเดล', 'Model'), 'NSE (walk-forward)', T('ความน่าเชื่อถือ', 'Reliability')], hz) + '<p class="note">' + T('NSE: 1 = สมบูรณ์ · 0 = เท่าค่าเฉลี่ย · ติดลบ = แย่กว่าค่าเฉลี่ย', 'NSE: 1 = perfect · 0 = same as mean · negative = worse than mean') + '</p>');
    }
    h += sec(T('3. อ่างเก็บน้ำ', '3. Reservoirs'), tbl([T('อ่าง', 'Reservoir'), T('ระดับน้ำ (ม.)', 'Level (m)'), T('ห่างสันฝาย (ม.)', 'Below spillway (m)'), T('ปริมาณ (ล้าน ลบ.ม.)', 'Storage (M m³)'), T('% ความจุ', '% capacity'), T('สถานะ', 'Status'), T('เวลาวัด', 'Measured')],
      m.res.map(function (r) { return [esc(EN ? r.en : r.name), f2(r.lv, 3), f2(r.spill, 2), f2(r.v) + ' / ' + f2(r.mx), f2(r.pct, 1), esc(fillWord(r.pct)), esc(fDT(r.t))]; })));
    if (m.vil.length) {
      var vs = m.vil.slice().sort(function (a, b) { return b.mx - a.mx; });
      h += sec(T('4. ความเสี่ยงน้ำท่วมรายหมู่บ้าน (7 วัน)', '4. Flood exposure by village (7 days)'), tbl([T('หมู่', 'Moo'), T('หมู่บ้าน', 'Village'), T('อาคาร', 'Buildings'), T('มีน้ำ ≥1 มม.', 'Wet ≥1 mm'), T('≥10 ซม.', '≥10 cm'), T('ความลึกสูงสุด', 'Max depth'), T('ระดับ', 'Level')],
        vs.map(function (v) { return [v.moo, esc(v.name), v.n, v.w1, v.w10, v.mx >= .1 ? v.mx.toFixed(2) + ' m' : (v.mx * 1000).toFixed(1) + ' mm', '<b style="color:' + HEX[v.lv] + '">' + esc(lvName(v.lv)) + '</b>']; })) + '<p class="note">' + T('เกณฑ์: ≥1 ซม. เฝ้าระวัง · ≥10 ซม. เตือนภัย · ≥50 ซม. วิกฤต (แผนที่ 3 มิติ)', 'Thresholds: ≥1 cm watch · ≥10 cm warning · ≥50 cm critical (3-D map)') + '</p>');
    }
    var wd = m.wd && m.wd.kpi;
    if (wd) h += sec(T('5. ความต้องการน้ำรายสัปดาห์', '5. Weekly water demand'), '<p>' + T('Zone A: MAE h1 ', 'Zone A: MAE h1 ') + Math.round(wd.zoneA_mae_h1).toLocaleString('en-US') + ' m³ · ' + esc(wd.zoneA_note || '') + '<br>Zone B: MAE h1 ' + Math.round(wd.zoneB_mae_h1).toLocaleString('en-US') + ' m³ · ' + esc(wd.zoneB_note || '') + '</p><p class="note">' + T('ผลนี้เป็นชุดทดสอบปี 2024 (โหมดตรวจสอบ) ดูป้าย Live/Static ที่หน้า water-demand', 'These are 2024 test-set results (validation mode); see the Live/Static badge on the water-demand page.') + '</p>');
    h += sec(T('6. ความน่าเชื่อถือและข้อจำกัด', '6. Reliability & limitations'), '<p>' + esc(fl.model_info || '') + '</p>' + (inf && inf.known_limitations ? '<ul>' + inf.known_limitations.map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') + '</ul>' : '') + (fl.warnings && fl.warnings.length ? '<p class="note">' + T('คำเตือนจากไปป์ไลน์ ' + fl.warnings.length + ' รายการ (ดูไฟล์ flood_latest.json)', fl.warnings.length + ' pipeline warning(s) — see flood_latest.json') + '</p>' : ''));
    h += '<footer>' + T('สร้างเมื่อ ', 'Generated ') + esc(new Date().toLocaleString(EN ? 'en-GB' : 'th-TH')) + ' · ' + esc(SITE_URL) + ' · ' + T('ข้อมูลพยากรณ์เพื่อประกอบการตัดสินใจ ไม่ใช่คำสั่งการอย่างเป็นทางการ', 'Forecast information for decision support; not an official order.') + '</footer>';
    return h;
  }
  var PCSS = '#uk-rp{display:none}@media print{@page{size:A4;margin:11mm}body>*:not(#uk-rp){display:none!important}html,body{background:#fff!important}#uk-rp{display:block!important;color:#111;background:#fff;font:11px/1.45 ' + FONT + '}' +
    '#uk-rp header{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #123643;padding-bottom:6px;margin-bottom:6px}#uk-rp h1{font-size:18px;margin:0;color:#123643}#uk-rp header p{margin:2px 0 0;color:#555}' +
    '#uk-rp .lv{color:#fff;font-weight:700;font-size:16px;padding:6px 16px;border-radius:999px;-webkit-print-color-adjust:exact;print-color-adjust:exact}#uk-rp .lead{font-size:12.5px;margin:6px 0}#uk-rp .msg{margin:4px 0 6px;padding-left:16px;color:#333;font-size:10.5px}' +
    '#uk-rp section{margin:9px 0;break-inside:avoid}#uk-rp h2{font-size:13px;margin:0 0 4px;color:#12846f;border-bottom:1px solid #cfe3de}#uk-rp table{width:100%;border-collapse:collapse;font-size:10px}#uk-rp th,#uk-rp td{border:1px solid #d5dedc;padding:2px 5px;text-align:left}' +
    '#uk-rp th{background:#eaf3f1;-webkit-print-color-adjust:exact;print-color-adjust:exact}#uk-rp .note{color:#555;font-size:9.5px;margin:3px 0}#uk-rp ul{margin:3px 0;padding-left:16px}#uk-rp footer{margin-top:8px;border-top:1px solid #ccc;padding-top:4px;color:#666;font-size:9px}}' +
    '#uk-rmodal{position:fixed;inset:0;z-index:99999;background:rgba(3,12,16,.78);display:flex;align-items:center;justify-content:center;padding:16px;font-family:' + FONT + '}' +
    '#uk-rmodal .bx{background:#0d2a34;color:#eef6f4;border:1px solid rgba(127,224,209,.3);border-radius:18px;max-width:560px;width:100%;max-height:92vh;overflow:auto;padding:20px}' +
    '#uk-rmodal h3{margin:0 0 4px;font-size:18px}#uk-rmodal p{margin:0 0 14px;font-size:13px;color:#a9c1be}#uk-rmodal .opt{display:block;width:100%;text-align:left;font:inherit;color:inherit;cursor:pointer;margin:0 0 10px;padding:14px 16px;border-radius:14px;border:1px solid rgba(127,224,209,.35);background:rgba(255,255,255,.04)}' +
    '#uk-rmodal .opt:hover{background:rgba(69,194,173,.16)}#uk-rmodal .opt b{display:block;font-size:15px}#uk-rmodal .opt span{font-size:12.5px;color:#a9c1be}#uk-rmodal .row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}' +
    '#uk-rmodal .btn{font:inherit;cursor:pointer;padding:9px 16px;border-radius:999px;border:1px solid rgba(127,224,209,.5);background:rgba(69,194,173,.22);color:#eef6f4}#uk-rmodal .btn.g{background:transparent}#uk-rmodal img{width:100%;border-radius:12px;display:block}' +
    '#uk-report{all:unset;box-sizing:border-box;cursor:pointer;margin-left:8px;padding:4px 10px;border-radius:999px;border:1px solid var(--border-strong,rgba(127,127,127,.4));font-size:12px;font-weight:600;color:var(--text-300,#888)}#uk-report:hover{color:var(--teal-300,#7fe0d1);border-color:var(--teal-400,#45c2ad)}';
  var st = document.createElement('style'); st.textContent = PCSS; document.head.appendChild(st);

  /* ---------- UI ---------- */
  var modal = null;
  function close() { if (modal) { modal.remove(); modal = null; } }
  function open(html) { close(); modal = document.createElement('div'); modal.id = 'uk-rmodal'; modal.setAttribute('data-i18n', 'off'); modal.innerHTML = '<div class="bx" role="dialog" aria-modal="true">' + html + '</div>'; modal.addEventListener('click', function (e) { if (e.target === modal) close(); }); document.body.appendChild(modal); return modal; }
  function chooser() {
    var md = open('<h3>' + T('สร้างรายงานสรุป', 'Create summary report') + '</h3><p>' + T('สร้างจากข้อมูลล่าสุดบนเว็บ ณ ตอนนี้', 'Built from the latest data on this site, right now') + '</p>' +
      '<button class="opt" data-k="v"><b>' + T('📱 สำหรับประชาชน — ภาพ PNG', '📱 For residents — PNG image') + '</b><span>' + T('อ่านง่ายบนมือถือ ส่งต่อทาง LINE ได้ ไม่มีศัพท์เทคนิค', 'Easy to read on a phone, shareable via chat, no jargon') + '</span></button>' +
      '<button class="opt" data-k="o"><b>' + T('🗂 สำหรับเจ้าหน้าที่ — PDF (A4)', '🗂 For officials — PDF (A4)') + '</b><span>' + T('ตัวเลขครบ พยากรณ์รายวัน อ่าง หมู่บ้าน ความน่าเชื่อถือ (เลือก "บันทึกเป็น PDF" ในหน้าต่างพิมพ์)', 'Full numbers, daily forecast, reservoirs, villages, reliability (choose "Save as PDF" in the print dialog)') + '</span></button>' +
      '<div class="row"><button class="btn g" data-k="x">' + T('ปิด', 'Close') + '</button></div>');
    md.addEventListener('click', function (e) { var k = e.target.closest && e.target.closest('[data-k]'); if (!k) return; k = k.getAttribute('data-k'); if (k === 'x') close(); else run(k); });
  }
  function fonts() { try { return Promise.all([document.fonts.load('400 24px "IBM Plex Sans Thai"', 'ก้ำA1'), document.fonts.load('500 24px "IBM Plex Sans Thai"', 'ก้ำA1'), document.fonts.load('600 24px "IBM Plex Sans Thai"', 'ก้ำA1'), document.fonts.load('700 24px "IBM Plex Sans Thai"', 'ก้ำA1')]).then(function () { return document.fonts.ready; }).catch(function () { }); } catch (e) { return Promise.resolve(); } }
  function run(kind) {
    open('<h3>' + T('กำลังสร้างรายงาน…', 'Building report…') + '</h3>');
    Promise.all([load(), fonts()]).then(function (r) {
      var m = r[0];
      if (kind === 'o') {
        close(); var old = document.getElementById('uk-rp'); if (old) old.remove();
        var d = document.createElement('div'); d.id = 'uk-rp'; d.setAttribute('data-i18n', 'off'); d.innerHTML = officialHtml(m); document.body.appendChild(d);
        var t0 = document.title; document.title = 'maenarua-water-report-' + (m.gen || '').slice(0, 10);
        var done = function () { document.title = t0; d.remove(); window.removeEventListener('afterprint', done); };
        window.addEventListener('afterprint', done); setTimeout(function () { window.print(); }, 150);
        return;
      }
      var cv = document.createElement('canvas'); drawVillager(cv, m);
      var url = cv.toDataURL('image/png'), name = 'maenarua-water-' + (m.gen || '').slice(0, 10) + '.png';
      var md = open('<h3>' + T('ภาพสรุปพร้อมแล้ว', 'Summary image ready') + '</h3><img alt="" src="' + url + '"><div class="row"><button class="btn" data-k="dl">' + T('⬇ บันทึกภาพ', '⬇ Save image') + '</button>' +
        (navigator.share && navigator.canShare ? '<button class="btn" data-k="sh">' + T('📤 แชร์', '📤 Share') + '</button>' : '') + '<button class="btn g" data-k="x">' + T('ปิด', 'Close') + '</button></div>');
      md.addEventListener('click', function (e) {
        var k = e.target.closest && e.target.closest('[data-k]'); if (!k) return; k = k.getAttribute('data-k');
        if (k === 'x') close();
        else if (k === 'dl') { var a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); }
        else if (k === 'sh') cv.toBlob(function (b) { var f = new File([b], name, { type: 'image/png' }); if (navigator.canShare({ files: [f] })) navigator.share({ files: [f], title: T('สรุปสถานการณ์น้ำ แม่นาเรือ', 'Mae Na Rua water summary') }).catch(function () { }); });
      });
    }).catch(function () { open('<h3>' + T('สร้างรายงานไม่สำเร็จ', 'Could not build the report') + '</h3><p>' + T('โหลดข้อมูลไม่ได้ ลองใหม่อีกครั้ง', 'Data could not be loaded. Please try again.') + '</p><div class="row"><button class="btn g" data-k="x">' + T('ปิด', 'Close') + '</button></div>').addEventListener('click', function (e) { if (e.target.getAttribute && e.target.getAttribute('data-k') === 'x') close(); }); });
  }
  function mount() {
    if (document.getElementById('uk-report')) return;
    var host = document.querySelector('header.site-header nav.main-nav') || document.querySelector('header.site-header'); if (!host) return;
    var b = document.createElement('button'); b.id = 'uk-report'; b.type = 'button'; b.textContent = T('📄 สรุป', '📄 Report'); b.title = T('สร้างรายงานสรุปสถานการณ์น้ำ (PNG/PDF)', 'Create a water situation summary (PNG/PDF)'); b.setAttribute('data-i18n', 'off');
    b.onclick = chooser; host.appendChild(b);
  }
  window.UKREPORT = { load: load, drawVillager: drawVillager, officialHtml: officialHtml, model: trend };
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
