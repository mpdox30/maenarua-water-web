/* report-kit.js — ปุ่ม "📄 สรุป" ที่หัวเว็บ: สร้างรายงานสรุปจากข้อมูลสดตอนกด (ไม่ต้องมีเซิร์ฟเวอร์ ไม่ส่งข้อมูลออกนอกเครื่อง)
   - ฉบับประชาชน  : ภาพ PNG 1080 px (ส่ง LINE/โซเชียล) ภาษาง่าย ไม่ใช้คำที่ทำให้ตื่นตระหนก · ลำดับ: ① กว๊าน ② ลำน้ำ/หมู่บ้านที่ต้องจับตา ③ ฝน 7 วัน ④ น้ำในอ่าง
   - ฉบับเจ้าหน้าที่ : A4 สองหน้า พิมพ์/บันทึก PDF · ไฮไลต์ของแต่ละหน้าเว็บ (น้ำท่วม · น้ำไหลลงอ่าง · อ่างเก็บน้ำ · ความต้องการน้ำ · SAR · บัญชีน้ำ)
   ภาษา TH/EN ตาม uk_lang · เบอร์ติดต่อท้ายฉบับประชาชน: ตัวแปร CONTACT หรือ window.UK_REPORT_CONTACT */
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

  /* ---------- ระดับสถานการณ์ (ธง 4 ระดับเดียวกับหน้า flood-forecast) ---------- */
  var LV = ['normal', 'watch', 'warning', 'critical'];
  var HEX = { normal: '#2a9d8f', watch: '#e0a94f', warning: '#e0763f', critical: '#e05252' };            // เจ้าหน้าที่: ชื่อ/สีเดียวกับเว็บ
  var VHEX = { normal: '#35c2a8', watch: '#f0c24b', warning: '#f39a3d', critical: '#f27b4a' };              // ประชาชน: โทนอุ่น ไม่ใช้แดงเข้ม
  function lvName(l) { return { normal: T('ปกติ', 'Normal'), watch: T('เฝ้าระวัง', 'Watch'), warning: T('เตือนภัย', 'Warning'), critical: T('วิกฤต', 'Critical') }[l]; }
  function vName(l) { return { normal: T('ปกติ', 'Normal'), watch: T('เฝ้าระวัง', 'Watch'), warning: T('เฝ้าระวังใกล้ชิด', 'Stay alert'), critical: T('เตรียมความพร้อม', 'Be prepared') }[l]; }
  function vLevel(d) { return d >= .5 ? 'critical' : d >= .1 ? 'warning' : d >= .01 ? 'watch' : 'normal'; }   // เกณฑ์ความลึกน้ำท่วมอาคาร (เหมือนแผนที่ 3 มิติ)
  function fillWord(p) { return p >= 100 ? T('เต็มอ่าง', 'Full') : p >= 80 ? T('ค่อนข้างเต็ม', 'Nearly full') : p >= 50 ? T('ปานกลาง', 'Moderate') : p >= 25 ? T('ค่อนข้างน้อย', 'Low') : T('น้อย', 'Very low'); }
  function rainWord(mm) { return mm < 1 ? T('แทบไม่มีฝน', 'Almost none') : mm < 10 ? T('ฝนเล็กน้อย', 'Light') : mm < 35 ? T('ฝนปานกลาง', 'Moderate') : mm < 90 ? T('ฝนหนัก', 'Heavy') : T('ฝนหนักมาก', 'Very heavy'); }
  var MO = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'], MOE = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function pd(s) { var m = /(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d):(\d\d))?/.exec(String(s || '')); return m ? { y: +m[1], mo: +m[2], d: +m[3], h: m[4], mi: m[5] } : null; }
  function fDate(s, short) { var p = pd(s); if (!p) return '—'; return short ? (p.d + ' ' + (EN ? MOE : MO)[p.mo - 1]) : EN ? p.d + ' ' + MOE[p.mo - 1] + ' ' + p.y : p.d + ' ' + MO[p.mo - 1] + ' ' + (p.y + 543); }
  function fDT(s) { var p = pd(s); return p && p.h ? fDate(s) + ' ' + p.h + ':' + p.mi + (EN ? '' : ' น.') : fDate(s); }
  function f2(x, n) { return x == null || isNaN(x) ? '—' : Number(x).toFixed(n == null ? 2 : n); }
  function fN(x) { return x == null || isNaN(x) ? '—' : Math.round(x).toLocaleString('en-US'); }
  function dm(s) { return Math.abs(s).toFixed(2); }
  function tr_(s) { try { return EN && window.UKI18N ? window.UKI18N.tr(s) : s; } catch (e) { return s; } }   // ข้อความจากไฟล์ข้อมูล → อังกฤษด้วยพจนานุกรมของ i18n-kit

  /* ---------- โหลดข้อมูล + รวมเป็นโมเดลเดียว ---------- */
  function inRing(x, y, r) { var o = false; for (var i = 0, j = r.length - 1; i < r.length; j = i++) { if ((r[i][1] > y) !== (r[j][1] > y) && x < (r[j][0] - r[i][0]) * (y - r[i][1]) / (r[j][1] - r[i][1]) + r[i][0]) o = !o; } return o; }
  function inGeom(g, x, y) { var polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates; return polys.some(function (p) { return inRing(x, y, p[0]); }); }
  function ctr(c) { var r = c; while (typeof r[0][0] !== 'number') r = r[0]; var sx = 0, sy = 0; r.forEach(function (p) { sx += p[0]; sy += p[1]; }); return [sx / r.length, sy / r.length]; }
  function load() {
    return Promise.all([J('flood_latest.json'), J('monitoring.json'), J('villages.geojson.json'), J('buildings_flood_risk.geojson'), J('latest.json'), J('water_ledger.json')]).then(function (a) {
      var fl = a[0], mo = a[1], vg = a[2], bg = a[3], lt = a[4], wl = a[5];
      if (!fl) throw new Error('flood_latest');
      var m = { fl: fl, lt: lt, gen: fl.generated_at, level: fl.flags && fl.flags.overall || 'normal', kwan: fl.kwan_now.level, d3: fl.kwan_now.change_3d,
        bankMain: fl.banks.Mae_Main1, bankRH: fl.banks.RongHai, fc: fl.kwan_forecast || [], obs: fl.kwan_observed_30d || [], rain: fl.rain_7d || {}, res: [], vil: [], streams: [], ledger: [] };
      if (LV.indexOf(m.level) < 0) m.level = 'normal';
      m.res = ((mo && mo.stations) || []).map(function (s) { return { name: s.name_th, en: s.name_en, pct: s.capacity_pct, v: s.storage_m3 / 1e6, mx: s.storage_max_m3 / 1e6, lv: s.water_level, spill: s.distance_to_spillway_m, t: s.measure_datetime }; });
      var ag = {};      // ลำน้ำที่คาดว่าล้นตลิ่ง รวมรายลำน้ำ 7 วัน
      (fl.overflow_forecast || []).forEach(function (o) { if (!(o.mcm > 0)) return; var x = ag[o.node] || (ag[o.node] = { node: o.node, name: tr_(String(o.name_th || o.node).replace(/\s*\(.*\)\s*$/, '')), mcm: 0, days: [] }); x.mcm += o.mcm; x.days.push(o.date); });
      m.streams = Object.keys(ag).map(function (k) { return ag[k]; }).sort(function (p, q) { return q.mcm - p.mcm; });
      if (vg && bg) {
        var V = (vg.features || []).filter(function (f) { return f.geometry; }).map(function (f) { return { name: f.properties.Name_TH || ('หมู่ ' + f.properties.Moo), moo: f.properties.Moo, g: f.geometry, n: 0, w1: 0, w10: 0, mx: 0 }; });
        (bg.features || []).forEach(function (f) {
          var c = ctr(f.geometry.coordinates), ds = (f.properties || {}).depths || [], d = ds.length ? Math.max.apply(null, ds) : 0;
          for (var i = 0; i < V.length; i++) if (inGeom(V[i].g, c[0], c[1])) { var v = V[i]; v.n++; if (d > v.mx) v.mx = d; if (d >= .001) v.w1++; if (d >= .1) v.w10++; break; }
        });
        m.vil = V.map(function (v) { v.lv = vLevel(v.mx); return v; });
      }
      m.wet = m.vil.filter(function (v) { return v.lv !== 'normal'; }).sort(function (x, y) { return y.mx - x.mx; });
      m.ledger = wl && wl.rows ? wl.rows.slice(-30) : [];
      return m;
    });
  }
  function trend(m) {
    var L = m.fc.map(function (x) { return x.level; }); if (!L.length) return null;
    var hi = Math.max.apply(null, m.fc.map(function (x) { return x.p90 != null ? x.p90 : x.level; })), d = L[L.length - 1] - m.kwan;
    return { k: Math.abs(d) < .05 ? 0 : d > 0 ? 1 : -1, dir: Math.abs(d) < .05 ? T('ทรงตัว', 'steady') : d > 0 ? T('สูงขึ้น', 'rising') : T('ลดลง', 'falling'), min: Math.min.apply(null, L), max: Math.max.apply(null, L), p90: hi };
  }
  function overWord(mcm) { return mcm < .05 ? T('เล็กน้อย', 'slight') : mcm < .2 ? T('ปานกลาง', 'moderate') : T('มาก', 'large'); }
  function vAdvice(m) {
    var calm = !m.wet.length ? T(' ขณะนี้ยังไม่พบน้ำท่วมถึงบ้านเรือน', ' No water is projected to reach homes at the moment.') : '';
    return { normal: T('ระดับน้ำปกติ ยังไม่พบสัญญาณน้ำล้นตลิ่ง ติดตามข่าวสารตามปกติ', 'Water levels are normal and there is no sign of overbank flow. Keep following updates as usual.'),
      watch: T('ระดับน้ำเริ่มใกล้ตลิ่ง โปรดติดตามข่าวสารอย่างต่อเนื่อง', 'Water is getting close to the banks. Please keep following updates.') + calm,
      warning: T('คาดมีน้ำล้นตลิ่งบางจุด ผู้อยู่ใกล้ลำน้ำควรติดตามข่าวและเตรียมของใช้จำเป็น', 'Some overbank flow is expected. Those living near streams should follow updates and prepare essentials.') + calm,
      critical: T('ระดับน้ำสูงกว่าตลิ่งบางจุด โปรดติดตามประกาศของหน่วยงานในพื้นที่และเตรียมความพร้อม', 'Water is above the bank in places. Please follow local-authority announcements and stay prepared.') + calm }[m.level];
  }

  /* ---------- ฉบับประชาชน: PNG (ความสูงปรับตามเนื้อหา) ---------- */
  var FONT = '"IBM Plex Sans Thai","Noto Sans Thai","Leelawadee UI",Tahoma,sans-serif';
  var SEG = null; try { SEG = new Intl.Segmenter(EN ? 'en' : 'th', { granularity: 'word' }); } catch (e) { }
  function drawVillager(cv, m) {
    var t = document.createElement('canvas'), end = paint(t, m, 4200);
    paint(cv, m, Math.max(1920, Math.round(end + 190)));
  }
  function paint(cv, m, H) {
    var W = 1080, P = 44, IW = W - P * 2; cv.width = W; cv.height = H; var c = cv.getContext('2d');
    var col = VHEX[m.level], tr = trend(m);
    function F(sz, w) { return (w || 400) + ' ' + sz + 'px ' + FONT; }
    function rr(x, y, w, h, r, fill, stroke, lw) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); if (fill) { c.fillStyle = fill; c.fill(); } if (stroke) { c.strokeStyle = stroke; c.lineWidth = lw || 2; c.stroke(); } }
    function tx(s, x, y, sz, w, colr, al) { c.font = F(sz, w); c.fillStyle = colr || '#eef6f4'; c.textAlign = al || 'left'; c.textBaseline = 'alphabetic'; c.fillText(s, x, y); }
    function tw(s, sz, w) { c.font = F(sz, w); return c.measureText(s).width; }
    function wrap(s, x, y, mw, sz, w, colr, lh) {
      c.font = F(sz, w); var parts = SEG ? Array.from(SEG.segment(s)).map(function (p) { return p.segment; }) : s.split(''), ln = '', yy = y;
      parts.forEach(function (p) { var q = ln + p; if (c.measureText(q).width > mw && ln) { tx(ln.trim(), x, yy, sz, w, colr); yy += lh; ln = p.replace(/^\s+/, ''); } else ln = q; });
      if (ln.trim()) { tx(ln.trim(), x, yy, sz, w, colr); yy += lh; } return yy;
    }
    function circ(x, y, r, fill) { c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fillStyle = fill; c.fill(); }
    function drop(x, y, s, fill) { c.beginPath(); c.moveTo(x, y - s); c.bezierCurveTo(x + s * .15, y - s * .6, x + s * .8, y - s * .15, x + s * .8, y + s * .28); c.arc(x, y + s * .28, s * .8, 0, Math.PI, false); c.bezierCurveTo(x - s * .8, y - s * .15, x - s * .15, y - s * .6, x, y - s); c.fillStyle = fill; c.fill(); }
    function check(x, y, s, colr) { c.strokeStyle = colr; c.lineWidth = s * .28; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(x - s * .5, y); c.lineTo(x - s * .12, y + s * .4); c.lineTo(x + s * .55, y - s * .4); c.stroke(); c.lineCap = 'butt'; }
    function cloud(x, y, s, fill) { c.fillStyle = fill; c.beginPath(); c.arc(x - s * .45, y, s * .38, 0, 7); c.arc(x, y - s * .22, s * .5, 0, 7); c.arc(x + s * .5, y, s * .36, 0, 7); c.fill(); c.fillRect(x - s * .45, y, s * .95, s * .36); }
    function house(x, y, s, fill) { c.fillStyle = fill; c.beginPath(); c.moveTo(x - s, y); c.lineTo(x, y - s * .85); c.lineTo(x + s, y); c.lineTo(x + s * .72, y); c.lineTo(x + s * .72, y + s * .75); c.lineTo(x - s * .72, y + s * .75); c.lineTo(x - s * .72, y); c.closePath(); c.fill(); }
    function badge(n, x, y) { circ(x, y, 26, '#1b6f78'); tx(String(n), x, y + 10, 28, 700, '#fff', 'center'); }
    function card(y, h) { rr(P, y, IW, h, 34, 'rgba(255,255,255,.075)', 'rgba(143,230,214,.20)', 2); }
    function title(n, s, y) { badge(n, P + 46, y + 48); tx(s, P + 88, y + 59, 36, 700, '#fff'); }
    function chip(s, x, y, fill, tcol, sz, rgt) { var w = tw(s, sz || 24, 600) + 30; if (rgt) x -= w; rr(x, y - (sz || 24) - 8, w, (sz || 24) + 20, ((sz || 24) + 20) / 2, fill); tx(s, x + 15, y + 2, sz || 24, 600, tcol); return w; }
    // พื้นหลัง
    var g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#0f4a5a'); g.addColorStop(.35, '#0a2f3b'); g.addColorStop(1, '#06161c'); c.fillStyle = g; c.fillRect(0, 0, W, H);
    c.globalAlpha = .08; for (var k = 0; k < 4; k++) { c.beginPath(); for (var xx = 0; xx <= W; xx += 20) c.lineTo(xx, 150 + k * 26 + Math.sin(xx / 90 + k) * 12); c.lineTo(W, 0); c.lineTo(0, 0); c.closePath(); c.fillStyle = '#7fe0d1'; c.fill(); } c.globalAlpha = 1;
    // หัว
    circ(P + 38, 84, 38, 'rgba(127,224,209,.18)'); drop(P + 38, 86, 24, '#7fe0d1');
    tx(T('สรุปสถานการณ์น้ำ', 'Water Situation Summary'), P + 96, 84, 46, 700, '#fff');
    tx(T('ตำบลแม่นาเรือ จ.พะเยา · ข้อมูล ' + fDT(m.gen), 'Mae Na Rua, Phayao · data ' + fDT(m.gen)), P + 96, 126, 25, 400, '#a9d8d0');
    // แบนเนอร์สถานะ
    var by = 168; rr(P, by, IW, 128, 30, col + '2e', col, 3); circ(P + 64, by + 64, 38, col);
    if (m.level === 'normal') check(P + 64, by + 64, 38, '#06303a'); else { tx('i', P + 64, by + 82, 56, 700, '#06303a', 'center'); }
    tx(T('สถานะ', 'Status') + ' · ' + vName(m.level), P + 122, by + 48, 32, 700, col);
    wrap(vAdvice(m), P + 122, by + 86, IW - 150, 24, 400, '#eaf7f4', 31);
    var y = by + 128 + 28;

    // ① กว๊านพะเยา
    var h1 = 640; card(y, h1); title(1, T('ระดับน้ำกว๊านพะเยา · ปัจจุบันและแนวโน้ม', 'Kwan Phayao level · now & trend'), y);
    var gap = m.kwan - m.bankMain;
    tx(f2(m.kwan), P + 36, y + 190, 112, 700, '#fff'); tx(T('ม.รทก.', 'm MSL'), P + 36 + tw(f2(m.kwan), 112, 700) + 14, y + 190, 30, 500, '#a9d8d0');
    var tcol = tr ? (tr.k > 0 ? '#f0c24b' : tr.k < 0 ? '#7fe0d1' : '#9fd3ff') : '#9fd3ff';
    if (tr) { chip(T('แนวโน้ม 7 วัน: ', '7-day trend: ') + tr.dir, W - P - 30, y + 138, tcol + '33', tcol, 26, true); }
    chip((gap >= 0 ? T('สูงกว่า', 'Above') : T('ต่ำกว่า', 'Below')) + T('ตลิ่ง ', ' bank ') + dm(gap) + T(' ม.', ' m'), W - P - 30, y + 192, 'rgba(255,255,255,.12)', '#eaf7f4', 26, true);
    var cx0 = P + 100, cx1 = W - P - 34, cy0 = y + 240, cy1 = y + 508;
    var ob = m.obs.slice(-8), n = ob.length + m.fc.length, k0 = ob.length - 1;
    var vals = ob.map(function (p) { return p.level; }).concat(m.fc.map(function (p) { return p.p90 != null ? p.p90 : p.level; }), m.fc.map(function (p) { return p.p10 != null ? p.p10 : p.level; }), [m.bankMain]);
    var lo = Math.min.apply(null, vals) - .08, hi = Math.max.apply(null, vals) + .08;
    function X(i) { return cx0 + (cx1 - cx0) * i / Math.max(1, n - 1); } function Y(v) { return cy1 - (cy1 - cy0) * (v - lo) / (hi - lo); }
    rr(P + 18, cy0 - 22, IW - 36, cy1 - cy0 + 66, 22, 'rgba(0,0,0,.18)');
    c.strokeStyle = 'rgba(255,255,255,.08)'; c.lineWidth = 1.5; [0, .5, 1].forEach(function (q) { var yy = cy0 + (cy1 - cy0) * q; c.beginPath(); c.moveTo(cx0, yy); c.lineTo(cx1, yy); c.stroke(); });
    tx(f2(hi), cx0 - 12, cy0 + 8, 20, 400, '#8fb5b0', 'right'); tx(f2(lo), cx0 - 12, cy1 + 6, 20, 400, '#8fb5b0', 'right');
    if (m.bankMain >= lo && m.bankMain <= hi) { c.setLineDash([10, 8]); c.strokeStyle = '#ff9d7a'; c.lineWidth = 2.5; c.beginPath(); c.moveTo(cx0, Y(m.bankMain)); c.lineTo(cx1, Y(m.bankMain)); c.stroke(); c.setLineDash([]); tx(T('ตลิ่งห้วยแม่นาเรือ ', 'Mae Na Rua bank ') + f2(m.bankMain), cx1, Y(m.bankMain) - 10, 21, 500, '#ff9d7a', 'right'); }
    if (m.fc.length) {
      c.beginPath(); m.fc.forEach(function (p, i) { var q = Y(p.p90 != null ? p.p90 : p.level); i ? c.lineTo(X(k0 + 1 + i), q) : c.moveTo(X(k0 + 1 + i), q); });
      for (var i = m.fc.length - 1; i >= 0; i--) c.lineTo(X(k0 + 1 + i), Y(m.fc[i].p10 != null ? m.fc[i].p10 : m.fc[i].level)); c.closePath(); c.fillStyle = 'rgba(127,224,209,.22)'; c.fill();
    }
    c.lineWidth = 6; c.lineJoin = 'round'; c.strokeStyle = '#fff'; c.beginPath(); ob.forEach(function (p, i) { i ? c.lineTo(X(i), Y(p.level)) : c.moveTo(X(i), Y(p.level)); }); c.stroke();
    c.setLineDash([14, 10]); c.strokeStyle = '#7fe0d1'; c.beginPath(); c.moveTo(X(k0), Y(m.kwan)); m.fc.forEach(function (p, i) { c.lineTo(X(k0 + 1 + i), Y(p.level)); }); c.stroke(); c.setLineDash([]);
    circ(X(k0), Y(m.kwan), 13, 'rgba(255,255,255,.3)'); circ(X(k0), Y(m.kwan), 8, '#fff');
    tx(T('วันนี้', 'Today'), X(k0), cy1 + 40, 22, 700, '#fff', 'center');
    if (m.fc.length) { tx(T('พยากรณ์ 7 วัน', '7-day forecast') + ' – ' + fDate(m.fc[m.fc.length - 1].date, 1), cx1, cy1 + 40, 22, 400, '#7fe0d1', 'right'); }
    if (ob.length) tx(fDate(ob[0].date, 1), cx0, cy1 + 40, 22, 400, '#8fb5b0');
    if (tr) wrap(T('ช่วง 7 วันข้างหน้าคาดว่าอยู่ที่ ' + f2(tr.min) + '–' + f2(tr.max) + ' ม. (กรอบบนสุดที่เป็นไปได้ ' + f2(tr.p90) + ' ม.)', 'Next 7 days expected ' + f2(tr.min) + '–' + f2(tr.max) + ' m (upper bound ' + f2(tr.p90) + ' m).'), P + 36, cy1 + 92, IW - 72, 24, 400, '#cfe6e2', 33);
    y += h1 + 26;

    // ② ลำน้ำ/หมู่บ้านที่ต้องจับตา
    var rows = Math.min(3, m.streams.length), h2 = 96 + (rows ? rows * 96 : 96) + 130; card(y, h2); title(2, T('ลำน้ำและหมู่บ้านที่ต้องจับตา', 'Streams & villages to watch'), y);
    var yy = y + 92;
    if (!rows) { rr(P + 28, yy, IW - 56, 80, 22, 'rgba(53,194,168,.16)'); check(P + 72, yy + 40, 24, '#35c2a8'); tx(T('ไม่มีลำน้ำที่คาดว่าจะล้นตลิ่งใน 7 วันข้างหน้า', 'No stream is expected to overflow in the next 7 days'), P + 112, yy + 50, 27, 500, '#eaf7f4'); yy += 96; }
    else m.streams.slice(0, 3).forEach(function (s) {
      rr(P + 28, yy, IW - 56, 84, 22, 'rgba(255,255,255,.07)'); circ(P + 74, yy + 42, 28, VHEX.watch + '40'); drop(P + 74, yy + 44, 17, VHEX.watch);
      tx(s.name, P + 118, yy + 38, 29, 700, '#fff'); tx(T('คาดน้ำล้นตลิ่ง' + overWord(s.mcm) + ' · ' + fDate(s.days[0], 1) + '–' + fDate(s.days[s.days.length - 1], 1), 'Slight-to-' + overWord(s.mcm) + ' overbank flow · ' + fDate(s.days[0], 1) + '–' + fDate(s.days[s.days.length - 1], 1)), P + 118, yy + 70, 22, 400, '#a9d8d0');
      chip(fN(s.mcm * 1e6) + T(' ลบ.ม.', ' m³'), W - P - 50, yy + 52, VHEX.watch + '33', VHEX.watch, 24, true); yy += 96;
    });
    var hy = yy + 6; rr(P + 28, hy, IW - 56, 96, 22, m.wet.length ? 'rgba(243,154,61,.16)' : 'rgba(53,194,168,.16)');
    house(P + 76, hy + 40, 22, m.wet.length ? VHEX.warning : '#35c2a8');
    if (!m.wet.length) { wrap(T('ยังไม่พบหมู่บ้านที่น้ำท่วมถึงบ้านเรือนใน 7 วันข้างหน้า (จากแผนที่น้ำท่วม 3 มิติ)', 'No village is projected to get floodwater into homes in the next 7 days (3-D flood map)'), P + 122, hy + 40, IW - 170, 25, 500, '#eaf7f4', 33); }
    else { tx(T('หมู่บ้านที่น้ำอาจท่วมถึงอาคาร', 'Villages where water may reach buildings'), P + 122, hy + 36, 25, 700, '#fff'); var cx = P + 122; m.wet.slice(0, 3).forEach(function (v) { cx += chip(T('หมู่ ', 'Moo ') + v.moo + ' ' + v.name.replace(/^บ้าน/, ''), cx, hy + 76, VHEX[v.lv] + '40', '#fff', 22) + 10; }); }
    y += h2 + 26;

    // ③ ฝนสะสม 7 วัน
    var h3 = 322; card(y, h3); title(3, T('ฝนสะสม 7 วันที่ผ่านมา', 'Rain in the past 7 days'), y);
    [[T('บนภูเขา', 'Mountain'), m.rain.mtn, P + 28], [T('ที่ราบ', 'Lowland'), m.rain.low, P + 28 + (IW - 56) / 2 + 8]].forEach(function (r) {
      var v = r[1] || 0, bw = (IW - 56) / 2 - 8, bx = r[2], by2 = y + 92; rr(bx, by2, bw, 200, 26, 'rgba(255,255,255,.07)');
      cloud(bx + 56, by2 + 52, 34, '#9fd3ff'); for (var q = 0; q < 3; q++) { c.strokeStyle = '#6bb8ff'; c.lineWidth = 4; c.lineCap = 'round'; c.beginPath(); c.moveTo(bx + 34 + q * 22, by2 + 82); c.lineTo(bx + 28 + q * 22, by2 + 98); c.stroke(); } c.lineCap = 'butt';
      tx(r[0], bx + 118, by2 + 50, 27, 600, '#cfe6e2'); tx(f2(v, 0), bx + 30, by2 + 158, 70, 700, '#fff'); tx(T('มม.', 'mm'), bx + 30 + tw(f2(v, 0), 70, 700) + 10, by2 + 158, 26, 500, '#a9d8d0');
      chip(rainWord(v), bx + bw - 22, by2 + 148, 'rgba(107,184,255,.25)', '#bfe0ff', 22, true);
      rr(bx + 30, by2 + 176, bw - 60, 12, 6, 'rgba(255,255,255,.1)'); rr(bx + 30, by2 + 176, Math.max(12, (bw - 60) * Math.min(1, v / 100)), 12, 6, '#6bb8ff');
    });
    y += h3 + 26;

    // ④ ปริมาณน้ำในอ่าง
    var R = m.res.slice(0, 6), h4 = 92 + R.length * 108 + 14; card(y, h4); title(4, T('ปริมาณน้ำในอ่างเก็บน้ำ', 'Water stored in reservoirs'), y);
    R.forEach(function (r, i) {
      var ry = y + 90 + i * 108, p = r.pct == null ? 0 : r.pct, cc = p >= 80 ? '#35c2a8' : p >= 50 ? '#7fe0d1' : p >= 25 ? '#f0c24b' : '#f39a3d';
      rr(P + 28, ry, IW - 56, 96, 24, 'rgba(255,255,255,.06)');
      var cx = P + 28 + 56, cy = ry + 48; c.lineWidth = 11; c.strokeStyle = 'rgba(255,255,255,.12)'; c.beginPath(); c.arc(cx, cy, 33, 0, Math.PI * 2); c.stroke();
      c.strokeStyle = cc; c.lineCap = 'round'; c.beginPath(); c.arc(cx, cy, 33, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.min(.9995, p / 100)); c.stroke(); c.lineCap = 'butt';
      tx(f2(p, 0), cx, cy + 8, 22, 700, '#fff', 'center');
      tx(EN ? r.en : r.name, P + 28 + 122, ry + 42, 28, 700, '#fff'); tx(f2(r.v) + ' / ' + f2(r.mx) + T(' ล้าน ลบ.ม.', ' M m³'), P + 28 + 122, ry + 76, 22, 400, '#a9d8d0');
      chip(fillWord(p), W - P - 50, ry + 58, cc + '33', cc, 26, true);
    });
    y += h4 + 16;
    var endY = y;
    // ท้ายหน้า
    var fy = H - 150; c.fillStyle = 'rgba(255,255,255,.14)'; c.fillRect(P, fy - 24, IW, 2);
    var fe = wrap(T('เป็นข้อมูลพยากรณ์เพื่อประกอบการเฝ้าระวัง ไม่ใช่คำสั่งอพยพอย่างเป็นทางการ โปรดปฏิบัติตามประกาศของหน่วยงานในพื้นที่', 'Forecast information to support monitoring — not an official evacuation order. Please follow local-authority announcements.'), P, fy, IW, 22, 400, '#cfe6e2', 31);
    if (CONTACT) tx(CONTACT, P, fe + 2, 23, 600, '#fff');
    tx(SITE_URL.replace(/^https:\/\//, ''), W - P, H - 34, 22, 500, '#7fe0d1', 'right'); tx(T('ที่มา: สสน. · HII · แบบจำลอง WMB', 'Sources: HII/NHC · WMB model'), P, H - 34, 20, 400, '#7fa5a0');
    return endY;
  }

  /* ---------- ฉบับเจ้าหน้าที่: A4 สองหน้า ---------- */
  function svgKwan(m) {
    var ob = m.obs.slice(-30), fc = m.fc, n = ob.length + fc.length, W = 700, H = 210, l = 44, r = 10, t = 14, b = 26;
    var vals = ob.map(function (p) { return p.level; }).concat(fc.map(function (p) { return p.p90 != null ? p.p90 : p.level; }), fc.map(function (p) { return p.p10 != null ? p.p10 : p.level; }), [m.bankMain, m.bankRH]);
    var lo = Math.min.apply(null, vals) - .1, hi = Math.max.apply(null, vals) + .1;
    function X(i) { return l + (W - l - r) * i / Math.max(1, n - 1); } function Y(v) { return H - b - (H - b - t) * (v - lo) / (hi - lo); }
    function path(a, off) { return a.map(function (p, i) { return (i ? 'L' : 'M') + X(i + off).toFixed(1) + ' ' + Y(p.level).toFixed(1); }).join(''); }
    var band = fc.length ? 'M' + fc.map(function (p, i) { return X(ob.length + i).toFixed(1) + ' ' + Y(p.p90 != null ? p.p90 : p.level).toFixed(1); }).join('L') + 'L' + fc.slice().reverse().map(function (p, i) { return X(n - 1 - i).toFixed(1) + ' ' + Y(p.p10 != null ? p.p10 : p.level).toFixed(1); }).join('L') + 'Z' : '';
    var grid = [0, .25, .5, .75, 1].map(function (q) { var v = lo + (hi - lo) * q; return '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="#e3ecea"/><text x="' + (l - 5) + '" y="' + (Y(v) + 3) + '" font-size="9" text-anchor="end" fill="#6b7f7c">' + f2(v) + '</text>'; }).join('');
    var bl = [[m.bankMain, '#d6453d', T('ตลิ่งห้วยแม่นาเรือ', 'Mae Na Rua bank')], [m.bankRH, '#e07b1f', T('ตลิ่งห้วยร่องไฮ', 'Rong Hai bank')]].filter(function (x) { return x[0] >= lo && x[0] <= hi; }).map(function (x) { return '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(x[0]) + '" y2="' + Y(x[0]) + '" stroke="' + x[1] + '" stroke-dasharray="4 3" stroke-width="1.2"/><text x="' + (W - r - 2) + '" y="' + (Y(x[0]) - 3) + '" text-anchor="end" font-size="9" fill="' + x[1] + '">' + x[2] + ' ' + f2(x[0]) + '</text>'; }).join('');
    var lastObs = ob.length ? ob[ob.length - 1].level : m.kwan;
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" style="display:block"><rect width="' + W + '" height="' + H + '" rx="8" fill="#f7fbfa"/>' + grid + bl + '<path d="' + band + '" fill="#f1b24a" opacity=".28"/><path d="' + path(ob, 0) + '" fill="none" stroke="#1d6a87" stroke-width="2.2"/><path d="M' + X(ob.length - 1).toFixed(1) + ' ' + Y(lastObs).toFixed(1) + path(fc, ob.length).replace(/^M/, 'L') + '" fill="none" stroke="#d98a12" stroke-width="2" stroke-dasharray="5 3"/>' +
      '<line x1="' + X(ob.length - 1) + '" x2="' + X(ob.length - 1) + '" y1="' + t + '" y2="' + (H - b) + '" stroke="#456" stroke-dasharray="2 3"/><circle cx="' + X(ob.length - 1) + '" cy="' + Y(m.kwan) + '" r="4" fill="#1d6a87" stroke="#fff" stroke-width="1.5"/>' +
      '<text x="' + l + '" y="' + (H - 9) + '" font-size="9" fill="#6b7f7c">' + fDate(ob.length ? ob[0].date : '', 1) + '</text><text x="' + X(ob.length - 1) + '" y="' + (H - 9) + '" font-size="9" text-anchor="middle" fill="#1d6a87" font-weight="700">' + T('วันนี้', 'Today') + ' ' + f2(m.kwan) + '</text><text x="' + (W - r) + '" y="' + (H - 9) + '" font-size="9" text-anchor="end" fill="#6b7f7c">' + (fc.length ? fDate(fc[fc.length - 1].date, 1) : '') + '</text></svg>';
  }
  function svgInflow(hz) {
    var W = 330, H = 150, l = 34, r = 8, t = 18, b = 24, n = hz.length, mx = Math.max.apply(null, hz.map(function (h) { return h.p; })) * 1.12 || 1;
    function X(i) { return l + (W - l - r) * (i + .5) / n; } function Y(v) { return H - b - (H - b - t) * v / mx; }
    var line = hz.map(function (h, i) { return (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(h.p).toFixed(1); }).join('');
    var grid = [0, .5, 1].map(function (q) { var v = mx * q; return '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="#e3ecea"/><text x="' + (l - 4) + '" y="' + (Y(v) + 3) + '" font-size="8.5" text-anchor="end" fill="#6b7f7c">' + (v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v.toFixed(0)) + '</text>'; }).join('');
    var pts = hz.map(function (h, i) { var low = h.nse == null || h.nse < 0, c = low ? '#d98a12' : '#1d6a87'; return (low ? '<rect x="' + (X(i) - 4) + '" y="' + (Y(h.p) - 4) + '" width="8" height="8" transform="rotate(45 ' + X(i) + ' ' + Y(h.p) + ')" fill="' + c + '"/>' : '<circle cx="' + X(i) + '" cy="' + Y(h.p) + '" r="4" fill="' + c + '"/>') + '<text x="' + X(i) + '" y="' + (Y(h.p) - 8) + '" font-size="8.5" text-anchor="middle" fill="#123" font-weight="700">' + (h.p / 1000).toFixed(0) + 'k</text><text x="' + X(i) + '" y="' + (H - 9) + '" font-size="8.5" text-anchor="middle" fill="#6b7f7c">+' + (i + 1) + '</text>'; }).join('');
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" style="display:block"><rect width="' + W + '" height="' + H + '" rx="8" fill="#f7fbfa"/>' + grid + '<path d="' + line + '" fill="none" stroke="#d98a12" stroke-width="1.8" stroke-dasharray="5 3"/>' + pts + '</svg>';
  }
  function svgLedger(rows) {
    var v = rows.map(function (r) { return r.water_volume_m3; }).filter(function (x) { return x != null; }); if (v.length < 2) return '';
    var W = 330, H = 70, mn = Math.min.apply(null, v), mx = Math.max.apply(null, v) || 1, rg = (mx - mn) || 1;
    var d = v.map(function (x, i) { return (i ? 'L' : 'M') + (4 + (W - 8) * i / (v.length - 1)).toFixed(1) + ' ' + (H - 6 - (H - 14) * (x - mn) / rg).toFixed(1); }).join('');
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" style="display:block"><rect width="' + W + '" height="' + H + '" rx="8" fill="#f7fbfa"/><path d="' + d + 'L' + (W - 4) + ' ' + (H - 2) + 'L4 ' + (H - 2) + 'Z" fill="#1d6a87" opacity=".12"/><path d="' + d + '" fill="none" stroke="#1d6a87" stroke-width="1.8"/></svg>';
  }
  function officialHtml(m) {
    var fl = m.fl, lt = m.lt || {}, fc = lt.forecasts || {}, col = HEX[m.level], tr = trend(m), gap = m.kwan - m.bankMain;
    function sec(n, h, body, cls) { return '<section class="' + (cls || '') + '"><h2><i>' + n + '</i>' + esc(h) + '</h2>' + body + '</section>'; }
    function kpi(label, val, unit, sub, c) { return '<div class="kpi" style="border-top-color:' + (c || '#12846f') + '"><small>' + esc(label) + '</small><b>' + esc(val) + '<u>' + esc(unit || '') + '</u></b><span>' + esc(sub || '') + '</span></div>'; }
    function chip(s, c) { return '<em class="chip" style="background:' + c + '1f;color:' + c + ';border-color:' + c + '66">' + esc(s) + '</em>'; }
    var ovfTop = m.streams[0];
    var p1 = '<header><div><h1>' + T('รายงานสรุปสถานการณ์น้ำ', 'Water Situation Report') + '</h1><p>' + T('สำหรับเจ้าหน้าที่ · ตำบลแม่นาเรือ จ.พะเยา · ข้อมูล ณ ', 'For officials · Mae Na Rua, Phayao · data as of ') + esc(fDT(m.gen)) + '</p></div><div class="lv" style="background:' + col + '"><small>' + T('ธงเตือนรวม', 'Overall flag') + '</small>' + esc(lvName(m.level)) + '</div></header>';
    p1 += '<div class="kpis">' + kpi(T('ระดับกว๊านพะเยา', 'Kwan Phayao level'), f2(m.kwan), T(' ม.รทก.', ' m'), (gap >= 0 ? T('สูงกว่า', 'above') : T('ต่ำกว่า', 'below')) + T('ตลิ่งแม่นาเรือ ', ' bank ') + dm(gap) + T(' ม.', ' m') + ' · 3' + T(' วัน', ' d') + ' ' + (m.d3 >= 0 ? '+' : '') + f2(m.d3, 3), HEX[m.level]) +
      kpi(T('กรอบบน P90 สูงสุด 7 วัน', 'Max P90 in 7 days'), tr ? f2(tr.p90) : '—', T(' ม.', ' m'), T('แนวโน้มค่ากลาง: ', 'Median trend: ') + (tr ? tr.dir : '—'), '#e0a94f') +
      kpi(T('น้ำล้นตลิ่งรวม 7 วัน', 'Overbank volume, 7 d'), f2(fl.overflow_total_7d, 3), T(' ล้าน ลบ.ม.', ' M m³'), ovfTop ? ovfTop.name + ' ' + f2(ovfTop.mcm, 3) : T('ไม่มีลำน้ำล้น', 'No overflow'), '#e0763f') +
      kpi(T('ฝนสะสม 7 วันย้อนหลัง', 'Rain, past 7 days'), f2(m.rain.mtn, 0) + ' / ' + f2(m.rain.low, 0), ' mm', T('ภูเขา / ที่ราบ', 'mountain / lowland'), '#1d6a87') + '</div>';
    var msgs = String(fl.flags && fl.flags.message || '').split(' | ').filter(Boolean).slice(0, 4);
    var vtxt = m.wet.length ? T(m.wet.length + ' หมู่บ้านมีน้ำถึงอาคาร (ลึกสุด ' + (m.wet[0].mx * 100).toFixed(1) + ' ซม. ที่หมู่ ' + m.wet[0].moo + ')', m.wet.length + ' village(s) with water at buildings (max ' + (m.wet[0].mx * 100).toFixed(1) + ' cm, Moo ' + m.wet[0].moo + ')') : T('ไม่พบหมู่บ้านที่น้ำถึงอาคาร ใน 7 วัน (ลึกสุด < 1 มม.)', 'No village with water at buildings within 7 days (max < 1 mm)');
    p1 += sec(1, T('คาดการณ์น้ำท่วม · กว๊านพะเยา', 'Flood forecast · Kwan Phayao'), '<div class="two"><div>' + svgKwan(m) + '<p class="note">' + T('เส้นทึบ = สังเกตการณ์ 30 วัน · เส้นประ/แถบ = พยากรณ์ 7 วัน (P10–P90)', 'Solid = observed 30 d · dashed/band = 7-day forecast (P10–P90)') + '</p></div><div><h3>' + T('ข้อความเตือนจากแบบจำลอง', 'Model messages') + '</h3><ul class="msg">' + msgs.map(function (s) { return '<li>' + esc(tr_(s)) + '</li>'; }).join('') + '</ul><div class="pill">' + esc(vtxt) + '</div></div></div>');
    var inf = fc.inflow && fc.inflow.forecast, hz = [];
    if (inf && inf.horizons) hz = Object.keys(inf.horizons).map(function (k) { var x = inf.horizons[k], ns = x.walkforward_cv_nse && x.walkforward_cv_nse.mean; return { p: x.prediction_m3_per_day, nse: ns }; });
    if (hz.length) {
      var good = hz.filter(function (h) { return h.nse != null && h.nse >= 0; }).length;
      p1 += sec(2, T('น้ำไหลลงอ่างแม่นาเรือ ล่วงหน้า 7 วัน', 'Inflow to Mae Na Rua reservoir, 7 days'), '<div class="two"><div>' + svgInflow(hz) + '<p class="note">' + T('ม³/วัน · ● ความเชื่อมั่นปกติ · ◆ NSE ติดลบ (ความเชื่อมั่นต่ำ)', 'm³/day · ● normal · ◆ negative NSE (low confidence)') + '</p></div><div><div class="chips">' + hz.map(function (h, i) { var c = h.nse == null ? '#8aa3a0' : h.nse >= .5 ? '#2a9d8f' : h.nse >= 0 ? '#e0a94f' : '#d98a12'; return chip('+' + (i + 1) + ' ' + (h.nse == null ? '—' : h.nse >= .5 ? T('เชื่อถือได้', 'reliable') : h.nse >= 0 ? T('พอใช้', 'fair') : T('ยังไม่แม่น', 'weak')), c); }).join('') + '</div><p class="warn">' + (good ? T('ช่วงที่ผ่านเกณฑ์ ' + good + ' จาก 7 วัน — ', good + ' of 7 days pass — ') : T('ทุกช่วงยังไม่ดีกว่าค่าเฉลี่ย — ', 'No horizon beats the mean yet — ')) + T('ใช้ดูแนวโน้ม ไม่ใช้ตัวเลขจริง และเทียบกับระดับน้ำจริงในอ่างเสมอ', 'use for trend only; always compare with the measured reservoir level.') + '</p></div></div>');
    }
    // หน้า 2
    var rs = m.res.map(function (r) {
      var over = r.spill > 0, near = !over && r.spill > -.1, st = over ? [T('เหนือสันสปิลเวย์', 'Above spillway'), '#d6453d'] : near ? [T('ใกล้สัน', 'Near crest'), '#e0a94f'] : [T('ปกติ', 'Normal'), '#2a9d8f'];
      return '<tr><td><b>' + esc(EN ? r.en : r.name) + '</b></td><td>' + f2(r.lv, 3) + '</td><td>' + (over ? '+' : '') + f2(r.spill, 2) + '</td><td>' + f2(r.v) + ' / ' + f2(r.mx) + '</td><td><div class="bar"><i style="width:' + Math.min(100, r.pct) + '%;background:' + (r.pct >= 100 ? '#d6453d' : '#1d6a87') + '"></i></div><b>' + f2(r.pct, 1) + '%</b></td><td>' + chip(st[0], st[1]) + '</td></tr>';
    }).join('');
    var p2 = sec(3, T('สถานการณ์อ่างเก็บน้ำ', 'Reservoir status'), '<table><thead><tr><th>' + T('อ่างเก็บน้ำ', 'Reservoir') + '</th><th>' + T('ระดับน้ำ (ม.)', 'Level (m)') + '</th><th>' + T('จากสันสปิลเวย์ (ม.)', 'vs spillway (m)') + '</th><th>' + T('ปริมาณ/ความจุ (ล้าน ลบ.ม.)', 'Storage / cap. (M m³)') + '</th><th>' + T('% ความจุ', '% capacity') + '</th><th>' + T('สถานะ', 'Status') + '</th></tr></thead><tbody>' + rs + '</tbody></table>', 'brk');
    function zone(z, nm) {
      var f = fc['demand_zone_' + z]; if (!f || !f.horizons) return '';
      var H = Object.keys(f.horizons).map(function (k) { return f.horizons[k]; }), mx = Math.max.apply(null, H.map(function (h) { return h.final_m3 || 0; })) || 1, live = /live/i.test(f.data_source || '');
      return '<div class="zone"><div class="zh"><b>' + nm + '</b>' + chip(live ? 'Live' : 'Static snapshot', live ? '#2a9d8f' : '#e0a94f') + '</div><div class="zn">' + fN(H[0].final_m3) + '<u> ' + T('ลบ.ม./สัปดาห์ (h=1)', 'm³/week (h=1)') + '</u></div><small>P(' + T('มีความต้องการ', 'demand') + ') = ' + f2(H[0].probability_active * 100, 1) + '%</small><div class="mini">' + H.map(function (h, i) { return '<span title="h' + (i + 1) + '"><i style="height:' + Math.max(3, (h.final_m3 || 0) / mx * 100).toFixed(0) + '%"></i><em>' + (i + 1) + '</em></span>'; }).join('') + '</div></div>';
    }
    var zs = zone('a', 'Zone A · Rainfed') + zone('b', 'Zone B · ' + T('พื้นที่ใช้น้ำ', 'irrigated'));
    if (zs) p2 += sec(4, T('ความต้องการน้ำรายสัปดาห์ (7 สัปดาห์ข้างหน้า)', 'Weekly water demand (next 7 weeks)'), '<div class="two">' + zs + '</div>');
    var cc = lt.crop_classification, CC = { rice: ['#d9b44a', T('ข้าว', 'Rice')], corn: ['#e08e45', T('ข้าวโพด', 'Maize')], longan: ['#6aa84f', T('ลำไย', 'Longan')], cassava: ['#a67c52', T('มันสำปะหลัง', 'Cassava')], etc: ['#9aa7a6', T('อื่น ๆ', 'Other')] };
    if (cc && cc.zone_crop_area_ha) {
      var q = cc.sar_data_quality, dv = q && q.weeks_diverging_from_training && q.weeks_diverging_from_training.length;
      var bars = ['zone_A', 'zone_B'].map(function (z) { var o = cc.zone_crop_area_ha[z] || {}, tot = Object.keys(o).reduce(function (s, k) { return s + o[k]; }, 0) || 1; return '<div class="sb"><b>' + z.replace('zone_', 'Zone ') + '</b><div class="stack">' + Object.keys(CC).filter(function (k) { return o[k] > 0; }).map(function (k) { return '<i style="width:' + (o[k] / tot * 100).toFixed(1) + '%;background:' + CC[k][0] + '" title="' + CC[k][1] + '">' + (o[k] / tot > .1 ? Math.round(o[k] / tot * 100) + '%' : '') + '</i>'; }).join('') + '</div><small>' + fN(tot) + ' ha</small></div>'; }).join('');
      p2 += sec(5, T('พื้นที่เพาะปลูก (ภาพถ่ายดาวเทียม SAR)', 'Cropped area (SAR satellite)'), bars + '<div class="leg">' + Object.keys(CC).map(function (k) { return '<span><i style="background:' + CC[k][0] + '"></i>' + CC[k][1] + '</span>'; }).join('') + '</div>' + (dv ? '<p class="warn">' + T('คุณภาพภาพดาวเทียมรอบนี้ต่ำกว่าปกติ (' + q.weeks_diverging_from_training.length + ' สัปดาห์ผิดจากเกณฑ์ฝึกโมเดล) ใช้ดูภาพรวมเท่านั้น', 'Satellite data quality is lower this round (' + q.weeks_diverging_from_training.length + ' weeks diverge from training); overview only.') + '</p>' : ''));
    }
    var L = m.ledger, la = L.length ? L[L.length - 1] : null;
    if (la) p2 += sec(6, T('บัญชีน้ำอ่างเก็บน้ำแม่นาเรือ (30 วันล่าสุด)', 'Mae Na Rua reservoir water ledger (last 30 days)'), '<div class="two"><div class="lk"><div><small>' + T('วันที่', 'Date') + '</small><b>' + esc(fDate(la.date, 1)) + '</b></div><div><small>' + T('ปริมาณน้ำ', 'Volume') + '</small><b>' + fN(la.water_volume_m3) + ' m³</b></div><div><small>' + T('น้ำไหลเข้า', 'Inflow') + '</small><b>' + fN(la.inflow_m3) + '</b></div><div><small>' + T('ระบาย', 'Release') + '</small><b>' + fN(la.outlet_release_m3) + '</b></div><div><small>' + T('ล้นสปิลเวย์', 'Spill') + '</small><b>' + fN(la.spill_m3) + '</b></div><div><small>' + T('ฝน 24 ชม.', 'Rain 24 h') + '</small><b>' + f2(la.rain_24h_mm, 1) + ' mm</b></div></div><div>' + svgLedger(L) + '<p class="note">' + T('ปริมาณน้ำในอ่างรายวัน (ม³)', 'Daily storage (m³)') + '</p></div></div>');
    var cav = [];
    if (hz.length) cav.push(T('พยากรณ์น้ำไหลลงอ่างยังแม่นไม่ถึงเกณฑ์ในหลายช่วง (NSE ติดลบ) — ใช้เป็นแนวโน้ม', 'Inflow forecasts are still below the accuracy bar in most horizons (negative NSE) — trend only.'));
    cav.push(T('กว๊านพะเยา: พยากรณ์แม่นช่วง 3–5 วัน (ridge, backtest 18 เดือน) — กรอบ P10–P90 กว้างขึ้นตามวัน', 'Kwan Phayao: most accurate at 3–5 days (ridge, 18-month backtest); P10–P90 widens with lead time.'));
    cav.push(T('แผนที่น้ำท่วม: ตรวจสอบกับรอยน้ำ 32 จุด r=0.825; ความลึกในพื้นที่นอกขอบเขต LiDAR มีความไม่แน่นอนสูง', 'Flood map: checked against 32 flood marks (r = 0.825); depths outside the LiDAR footprint are less certain.'));
    p2 += sec(7, T('ข้อควรระวังในการใช้ข้อมูล', 'Caveats'), '<ul class="cv">' + cav.map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') + '</ul>');
    return '<div class="pg">' + p1 + '</div><div class="pg">' + p2 + '<footer>' + T('สร้างเมื่อ ', 'Generated ') + esc(new Date().toLocaleString(EN ? 'en-GB' : 'th-TH')) + ' · ' + esc(SITE_URL) + ' · ' + T('ข้อมูลพยากรณ์เพื่อประกอบการตัดสินใจ ไม่ใช่คำสั่งการอย่างเป็นทางการ', 'Forecast information for decision support; not an official order.') + '</footer></div>';
  }

  var PCSS = '#uk-rp{display:none}@media print{@page{size:A4;margin:9mm}body>*:not(#uk-rp){display:none!important}html,body{background:#fff!important}' +
    '#uk-rp{display:block!important;color:#17313a;background:#fff;font:10.5px/1.45 ' + FONT + ';-webkit-print-color-adjust:exact;print-color-adjust:exact}#uk-rp .pg{break-after:page}#uk-rp .pg:last-child{break-after:auto}' +
    '#uk-rp header{display:flex;justify-content:space-between;align-items:center;background:linear-gradient(120deg,#0d2a34,#12846f);color:#fff;border-radius:10px;padding:10px 14px;margin-bottom:8px}#uk-rp h1{font-size:19px;margin:0}#uk-rp header p{margin:2px 0 0;color:#cfeee8;font-size:10.5px}' +
    '#uk-rp .lv{font-weight:700;font-size:17px;padding:6px 18px;border-radius:999px;text-align:center;line-height:1.15}#uk-rp .lv small{display:block;font-size:8.5px;font-weight:500;opacity:.9}' +
    '#uk-rp .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:8px}#uk-rp .kpi{border:1px solid #d8e6e3;border-top:3px solid #12846f;border-radius:9px;padding:6px 9px;background:#fbfdfd}#uk-rp .kpi small{display:block;color:#5b7571;font-size:9px}#uk-rp .kpi b{display:block;font-size:19px;line-height:1.2;color:#0d2a34}#uk-rp .kpi b u{font-size:9.5px;font-weight:500;text-decoration:none;color:#5b7571}#uk-rp .kpi span{font-size:8.8px;color:#6b7f7c}' +
    '#uk-rp section{margin:0 0 9px;border:1px solid #d8e6e3;border-radius:10px;padding:8px 10px;break-inside:avoid;background:#fff}#uk-rp h2{font-size:12.5px;margin:0 0 6px;color:#0d2a34;display:flex;align-items:center;gap:7px}#uk-rp h2 i{font-style:normal;background:#12846f;color:#fff;width:18px;height:18px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:10.5px}#uk-rp h3{font-size:10.5px;margin:0 0 4px;color:#12846f}' +
    '#uk-rp .two{display:grid;grid-template-columns:1.25fr 1fr;gap:10px;align-items:start}#uk-rp .note{color:#6b7f7c;font-size:8.8px;margin:3px 0 0}#uk-rp .msg{margin:0 0 6px;padding-left:15px;font-size:9.6px;color:#2b4650}#uk-rp .msg li{margin-bottom:2px}#uk-rp .pill{background:#e8f6f2;border:1px solid #bfe3da;border-radius:8px;padding:5px 8px;font-size:10px;color:#0d4b43;font-weight:600}' +
    '#uk-rp .chip{font-style:normal;display:inline-block;border:1px solid;border-radius:999px;padding:1px 8px;font-size:9.2px;font-weight:600;margin:0 4px 4px 0}#uk-rp .chips{margin-bottom:4px}#uk-rp .warn{background:#fff6e5;border:1px solid #f3d99b;border-radius:8px;padding:5px 8px;font-size:9.6px;margin:4px 0 0;color:#6a4a07}' +
    '#uk-rp table{width:100%;border-collapse:collapse;font-size:10px}#uk-rp th{background:#eaf3f1;color:#35524d;text-align:left;font-size:9.2px;padding:4px 6px;border-bottom:1px solid #cfe0dc}#uk-rp td{padding:5px 6px;border-bottom:1px solid #e5eeec}#uk-rp .bar{display:inline-block;width:70px;height:7px;border-radius:4px;background:#e3ecea;vertical-align:middle;margin-right:6px;overflow:hidden}#uk-rp .bar i{display:block;height:100%}' +
    '#uk-rp .zone{border:1px solid #d8e6e3;border-radius:9px;padding:7px 10px;background:#fbfdfd}#uk-rp .zh{display:flex;justify-content:space-between;align-items:center}#uk-rp .zn{font-size:20px;font-weight:700;color:#0d2a34}#uk-rp .zn u{font-size:9.5px;font-weight:500;text-decoration:none;color:#5b7571}#uk-rp .mini{display:flex;gap:4px;align-items:flex-end;height:42px;margin-top:6px}#uk-rp .mini span{flex:1;height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center}#uk-rp .mini i{display:block;width:100%;background:#1d6a87;border-radius:3px 3px 0 0}#uk-rp .mini em{font-style:normal;font-size:8px;color:#6b7f7c}' +
    '#uk-rp .sb{display:grid;grid-template-columns:52px 1fr 60px;align-items:center;gap:8px;margin-bottom:5px}#uk-rp .stack{display:flex;height:17px;border-radius:5px;overflow:hidden}#uk-rp .stack i{display:flex;align-items:center;justify-content:center;color:#fff;font-size:8.5px;font-style:normal;font-weight:700}#uk-rp .leg{display:flex;gap:10px;font-size:9px;color:#35524d}#uk-rp .leg i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px}' +
    '#uk-rp .lk{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}#uk-rp .lk div{border:1px solid #e0ebe8;border-radius:7px;padding:4px 7px}#uk-rp .lk small{display:block;color:#6b7f7c;font-size:8.6px}#uk-rp .lk b{font-size:11.5px}#uk-rp .cv{margin:0;padding-left:16px;font-size:9.8px;color:#2b4650}#uk-rp .cv li{margin-bottom:3px}#uk-rp footer{margin-top:6px;color:#6b7f7c;font-size:8.6px;border-top:1px solid #d8e6e3;padding-top:4px}}' +
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
      '<button class="opt" data-k="o"><b>' + T('🗂 สำหรับเจ้าหน้าที่ — PDF (A4 สองหน้า)', '🗂 For officials — PDF (A4, 2 pages)') + '</b><span>' + T('ไฮไลต์จากทุกหน้าเว็บ: น้ำท่วม น้ำไหลลงอ่าง อ่างเก็บน้ำ ความต้องการน้ำ SAR บัญชีน้ำ (เลือก "บันทึกเป็น PDF" ในหน้าต่างพิมพ์)', 'Highlights from every page: flood, inflow, reservoirs, demand, SAR, ledger (choose "Save as PDF" in the print dialog)') + '</span></button>' +
      '<div class="row"><button class="btn g" data-k="x">' + T('ปิด', 'Close') + '</button></div>');
    md.addEventListener('click', function (e) { var k = e.target.closest && e.target.closest('[data-k]'); if (!k) return; k = k.getAttribute('data-k'); if (k === 'x') close(); else run(k); });
  }
  function fonts() { var f = function (w) { return document.fonts.load(w + ' 24px "IBM Plex Sans Thai"', 'ก้ำA1'); }; try { return Promise.all([f(400), f(500), f(600), f(700)]).then(function () { return document.fonts.ready; }).catch(function () { }); } catch (e) { return Promise.resolve(); } }
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
    var host = document.querySelector('header.site-header nav.main-nav') || document.querySelector('header.site-header'); if (!host) return; if (host.matches('nav.main-nav')) { var tl = host.querySelector('.uk-tools'); if (!tl) { tl = document.createElement('div'); tl.className = 'uk-tools'; host.appendChild(tl); } host = tl; }
    var b = document.createElement('button'); b.id = 'uk-report'; b.type = 'button'; b.textContent = T('📄 สรุป', '📄 Report'); b.title = T('สร้างรายงานสรุปสถานการณ์น้ำ (PNG/PDF)', 'Create a water situation summary (PNG/PDF)'); b.setAttribute('data-i18n', 'off');
    b.onclick = chooser; host.appendChild(b);
  }
  window.UKREPORT = { load: load, drawVillager: drawVillager, officialHtml: officialHtml, model: trend };
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
