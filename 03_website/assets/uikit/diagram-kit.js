/* diagram-kit.js — "ผังน้ำ" ตำบลแม่นาเรือ ต่อจากแผนที่ในหน้าแรก (index.html)
   พอร์ตจากโปรเจค community-dashboard (WaterNetworkPanel + WaterFlowDiagramCytoscape + SourceDetailCard + SourceCard)
   โหมดหลัก  : ผังอินเทอร์แอกทีฟ (Cytoscape) จากข้อมูล assets/data/water_network.json (python export_water_network.py สร้างให้)
               ปุ่มตัวอักษร ± · จัดกึ่งกลาง · เต็มจอ · จุดน้ำไหลบนคลองหลัก · กดโหนด → การ์ดรายละเอียด / แผงโทรมาตร / แผงฝาย-ปตร.
   โหมดสำรอง : ถ้ายังไม่มี water_network.json → ใช้ภาพผัง SVG (assets/img/water-network-diagram.svg) + กล่องสี % ทับตำแหน่ง
   ข้อมูลสด  : % ของอ่างที่มีสถานีโทรมาตรอ่านจาก monitoring.json (อัปเดตโดยบอต) · แหล่งอื่นใช้ค่า ณ วันที่ export
   ไลบรารี   : assets/vendor/cytoscape/cytoscape.min.js โหลดเมื่อเลื่อนถึงส่วนนี้เท่านั้น */
(function () {
  'use strict';
  var mapCard = document.querySelector('.map-card'); if (!mapCard || !document.getElementById('map')) return;
  var host = mapCard.closest('section'); if (!host) return;
  var EN = false; try { EN = (localStorage.getItem('uk_lang') || '') === 'en'; } catch (e) { }
  if (document.documentElement.lang === 'en') EN = true;
  function T(th, en) { return EN ? en : th; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var cs = document.currentScript, BASE = '';
  if (cs && cs.src) { var mm = cs.src.match(/^(.*\/)(?:assets\/uikit|__uikit)\//); if (mm) BASE = mm[1]; }
  if (!BASE) BASE = location.href.replace(/[^\/]*([?#].*)?$/, '');
  function J(p) { return fetch(BASE + 'assets/data/' + p, { cache: 'no-store' }).then(function (r) { if (!r.ok) throw 0; return r.json(); }).catch(function () { return null; }); }

  /* ---- ค่าคงที่เหมือนต้นฉบับ (status.js / theme.js) ---- */
  var C = { navy: '#0c4a6e', sky: '#0ea5e9', bg: '#f9f6ef', card: '#ffffff', border: '#eee3cc', text: '#0f172a', muted: '#64748b' };
  var SANS = "'Sarabun', 'Tahoma', sans-serif";
  var ST = {
    critical: { label: 'วิกฤต', en: 'Critical', bg: '#fef2f2', border: '#ef4444', text: '#b91c1c', badge: '#ef4444', dot: '🔴' },
    warning: { label: 'เฝ้าระวัง', en: 'Watch', bg: '#fff7ed', border: '#f97316', text: '#c2410c', badge: '#f97316', dot: '🟠' },
    medium: { label: 'ปานกลาง', en: 'Moderate', bg: '#fefce8', border: '#eab308', text: '#a16207', badge: '#eab308', dot: '🟡' },
    safe: { label: 'ปลอดภัย', en: 'Safe', bg: '#f0fdf4', border: '#22c55e', text: '#15803d', badge: '#22c55e', dot: '🟢' },
    unknown: { label: 'ไม่มีข้อมูล', en: 'No data', bg: '#f8fafc', border: '#cbd5e1', text: '#64748b', badge: '#94a3b8', dot: '⚪' }
  };
  function getStatus(p) { if (p == null) return 'unknown'; if (p < 20) return 'critical'; if (p < 40) return 'warning'; if (p < 60) return 'medium'; return 'safe'; }
  function sl(k) { return EN ? ST[k].en : ST[k].label; }
  function fmt(n) { return n == null || isNaN(n) ? '—' : Math.round(n).toLocaleString('th-TH'); }
  var MO = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'], MOE = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function fmtDate(iso) { var m = /(\d{4})-(\d\d)-(\d\d)/.exec(iso || ''); if (!m) return '—'; return EN ? +m[3] + ' ' + MOE[m[2] - 1] + ' ' + m[1] : +m[3] + ' ' + MO[m[2] - 1] + ' ' + (+m[1] + 543); }
  function fmtDT(iso) { return /T(\d\d:\d\d)/.test(iso || '') ? fmtDate(iso) + ' ' + /T(\d\d:\d\d)/.exec(iso)[1] + (EN ? '' : ' น.') : fmtDate(iso); }
  function trendInfo(dW) {
    if (dW == null) return { icon: '—', label: T('ไม่มีข้อมูล', 'No data'), color: '#94a3b8' };
    if (dW > 0.5) return { icon: '▲', label: '+' + dW.toFixed(1) + T('%/สัปดาห์', '%/week'), color: '#22c55e' };
    if (dW < -0.5) return { icon: '▼', label: dW.toFixed(1) + T('%/สัปดาห์', '%/week'), color: '#ef4444' };
    return { icon: '—', label: T('คงที่', 'Steady'), color: '#94a3b8' };
  }

  /* ---- โครงแหล่งน้ำ: โหมดสำรอง = 8 แหล่งตายตัว (พิกัดกล่อง = SVG_NODE_BOXES ของต้นฉบับ) · โหมดหลัก = จาก water_network.json ---- */
  var VB_W = 3178, VB_H = 2246;
  var NODES = [
    { id: 'MNR-01', th: 'อ่างเก็บน้ำแม่นาเรือ', en: 'Mae Na Rua Reservoir', x: 870, y: 201.9, w: 103, h: 108, shape: 'triangle' },
    { id: 'MNR-02', th: 'อ่างเก็บน้ำวิทยาลัยเกษตร', en: 'Phayao C.A.T. Reservoir', x: 1060, y: 362.9, w: 102, h: 108, shape: 'triangle' },
    { id: 'MNR-06', th: 'แก้มลิงโป่งหินน้อย', en: 'Pong Hin Noi retention pond', x: 1439, y: 474.9, w: 177, h: 110, shape: 'rect' },
    { id: 'MNR-03', th: 'อ่างเก็บน้ำห้วยถ้ำ', en: 'Huai Tham Reservoir', x: 883, y: 804.8, w: 102, h: 109, shape: 'triangle' },
    { id: 'MNR-07', th: 'แก้มลิงร่องซุ้ม', en: 'Rong Sum retention pond', x: 1399, y: 1260.7, w: 177, h: 109, shape: 'rect' },
    { id: 'MNR-04', th: 'อ่างเก็บน้ำห้วยโซ้', en: 'Huai So Reservoir', x: 887, y: 1439.6, w: 102, h: 108, shape: 'triangle' },
    { id: 'MNR-05', th: 'อ่างเก็บน้ำห้วยจำตุ้ม', en: 'Huai Cham Tum Reservoir', x: 836, y: 1952.5, w: 102, h: 109, shape: 'triangle' },
    { id: 'MNR-08', th: 'แก้มลิงห้วยน้ำขาว', en: 'Huai Nam Kao retention pond', x: 1179, y: 2084.5, w: 177, h: 110, shape: 'rect' }
  ];
  var FALLBACK_STATION = { 'MNR-01': 'RES002', 'MNR-02': 'RES004', 'MNR-03': 'RES005', 'MNR-04': 'RES006' };
  function nm(n) { return EN && n.en ? n.en : n.th; }
  var MODE = 'svg', NET = null, MON = null, S = {}, sel = null, mooF = 'all', cy = null, fitTarget = null;

  /* ---- สไตล์ ---- */
  var css = document.createElement('style');
  css.textContent = '#water-diagram .wd-panel{background:' + C.bg + ';border:1px solid ' + C.border + ';border-radius:20px;padding:16px;font-family:' + SANS + ';color:' + C.text + '}' +
    '#water-diagram .wd-frame{position:relative;border-radius:12px;overflow:hidden;border:1.5px solid ' + C.border + ';box-shadow:0 2px 12px rgba(0,0,0,.08);background:#fff;text-align:left}#water-diagram .wd-frame>svg{display:block;width:100%;height:auto}' +
    '#water-diagram .wd-frame:fullscreen{border-radius:0}' +
    '#water-diagram .wd-n{cursor:pointer}#water-diagram .wd-n:focus{outline:none}#water-diagram .wd-n:focus-visible .wd-s{stroke:#0c4a6e;stroke-width:6}' +
    '#water-diagram .wd-ov{position:absolute;background:rgba(255,255,255,.92);border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.15);font-size:11px;color:#0f172a;z-index:3}' +
    '#water-diagram .wd-tb{top:8px;left:70px;padding:4px 6px;display:flex;align-items:center;gap:4px;flex-wrap:wrap}#water-diagram .wd-north{top:8px;left:8px;padding:4px 10px 6px;display:flex;flex-direction:column;align-items:center;font-weight:700}' +
    '#water-diagram .wd-sq{width:20px;height:20px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;cursor:pointer;font-size:12px;line-height:1;padding:0;color:#0f172a}' +
    '#water-diagram .wd-bw{border:1px solid #cbd5e1;border-radius:4px;padding:2px 8px;background:#fff;cursor:pointer;font-size:11px;font-weight:600;color:' + C.navy + ';font-family:' + SANS + '}' +
    '#water-diagram .wd-sep{width:1px;height:16px;background:#e2e8f0;margin:0 2px}' +
    '#water-diagram .wd-leg,#water-diagram .wd-leg2{bottom:8px;padding:5px 10px;font-size:10px;display:flex;gap:10px;flex-wrap:wrap}#water-diagram .wd-leg{right:8px;justify-content:flex-end;max-width:220px}#water-diagram .wd-leg2{left:8px;padding:6px 10px;display:grid;grid-template-columns:auto auto;gap:3px 10px}' +
    '#water-diagram .wd-leg span,#water-diagram .wd-leg2 div{display:flex;align-items:center;gap:4px}#water-diagram .wd-leg i{width:14px;height:9px;border-radius:2px;flex-shrink:0;display:inline-block}' +
    '#water-diagram .wd-li{width:16px;display:flex;align-items:center;justify-content:center;flex-shrink:0}' +
    '#water-diagram .wd-pn{top:8px;right:8px;max-width:260px;padding:10px 14px 12px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.18);background:#fff;border:1.5px solid #cbd5e1}#water-diagram .wd-pn h5{margin:0;font-size:13px;color:' + C.navy + '}#water-diagram .wd-pn .x{border:none;background:none;cursor:pointer;font-size:14px;color:' + C.muted + ';line-height:1;padding:0;float:right}' +
    '#water-diagram .wd-pn small{display:block;font-size:10px;color:' + C.muted + '}#water-diagram .wd-pn .b{background:#f8fafc;border-radius:6px;padding:6px 8px}#water-diagram .wd-pn .g{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}' +
    '#water-diagram .wd-msg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.85);font-size:13px;color:' + C.muted + ';z-index:4}' +
    '#water-diagram .wd-leg{position:absolute}#water-diagram .wd-cap{padding:8px 2px;font-size:11px;color:' + C.muted + '}' +
    '#water-diagram .wd-det{margin:0 0 14px;background:' + C.card + ';border-radius:14px;overflow:hidden;box-shadow:0 2px 14px rgba(0,0,0,.12)}' +
    '#water-diagram .wd-ph{height:110px;background:#f1f5f9;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;color:#94a3b8;position:relative}#water-diagram .wd-ph b{font-size:24px;font-weight:400}#water-diagram .wd-ph span{font-size:11px}' +
    '#water-diagram .wd-x{position:absolute;top:8px;right:8px;width:26px;height:26px;border-radius:50%;border:none;background:rgba(15,23,42,.55);color:#fff;cursor:pointer;font-size:14px;line-height:1;padding:0}' +
    '#water-diagram .wd-bd{padding:14px 16px 16px}#water-diagram .wd-hd{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}' +
    '#water-diagram .wd-nm{font-weight:700;font-size:16px;color:' + C.text + '}#water-diagram .wd-sub{font-size:12px;color:' + C.muted + ';margin-top:2px}' +
    '#water-diagram .wd-bg{color:#fff;font-size:12px;font-weight:700;padding:3px 12px;border-radius:999px;white-space:nowrap}' +
    '#water-diagram .wd-g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}#water-diagram .wd-g2 div{background:#f8fafc;border-radius:8px;padding:8px 10px}#water-diagram .wd-g2 small{display:block;font-size:10px;color:' + C.muted + '}#water-diagram .wd-g2 b{font-size:15px;font-weight:700}' +
    '#water-diagram .wd-chl{font-size:11px;color:' + C.muted + ';margin:14px 0 4px}#water-diagram .wd-ch{position:relative}#water-diagram .wd-ch svg{display:block;width:100%;height:auto}' +
    '#water-diagram .wd-tip{position:absolute;pointer-events:none;background:#fff;border:1px solid #cbd5e1;border-radius:6px;padding:4px 8px;font-size:11px;box-shadow:0 2px 8px rgba(0,0,0,.12);white-space:nowrap;display:none;z-index:2}' +
    '#water-diagram .wd-flt{display:flex;gap:6px;margin:0 0 10px;flex-wrap:wrap;align-items:center;font-size:12px;color:' + C.muted + '}#water-diagram .wd-flt button{border-radius:999px;padding:3px 12px;font-size:12px;cursor:pointer;font-family:' + SANS + ';border:1.5px solid #cbd5e1;background:#fff;color:' + C.text + '}#water-diagram .wd-flt button.on{background:' + C.navy + ';color:#fff;border-color:' + C.navy + '}' +
    '#water-diagram .wd-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:8px}' +
    '#water-diagram .wd-sc{border-radius:12px;padding:12px 14px;cursor:pointer;font-family:' + SANS + ';text-align:left;width:100%}' +
    '#water-diagram .wd-sc .r1{display:flex;justify-content:space-between;align-items:flex-start;gap:6px}#water-diagram .wd-sc .t{font-weight:700;font-size:13px;color:' + C.text + '}#water-diagram .wd-sc .s{font-size:11px;color:' + C.muted + '}' +
    '#water-diagram .wd-sc .pb{color:#fff;font-size:11px;font-weight:700;padding:2px 10px;border-radius:999px;white-space:nowrap}#water-diagram .wd-sc .big{display:flex;align-items:baseline;gap:10px;margin-top:8px}#water-diagram .wd-sc .big b{font-size:26px;font-weight:800}#water-diagram .wd-sc .big span{font-size:12px;color:' + C.muted + '}' +
    '#water-diagram .wd-sc .bar{background:#e2e8f0;border-radius:999px;height:8px;overflow:hidden;margin-top:6px}#water-diagram .wd-sc .bar i{display:block;height:100%;border-radius:999px}#water-diagram .wd-sc .tr{margin-top:6px;font-size:12px;font-weight:700}';
  document.head.appendChild(css);

  var sec = document.createElement('section'); sec.className = 'section'; sec.id = 'water-diagram'; sec.style.display = 'none';
  sec.innerHTML = '<div class="wrap"><div class="section-head"><div><div class="eyebrow">' + T('ผังน้ำ', 'Water network') + '</div><h2>' + T('ผังน้ำตำบลแม่นาเรือ', 'Mae Na Rua water-flow diagram') + '</h2></div>' +
    '<p>' + T('ผังการไหลของน้ำระหว่างแหล่งเก็บกัก พร้อมปริมาณน้ำปัจจุบันเป็น % ของความจุ — กดที่โหนดเพื่อดูรายละเอียด', 'How water moves between storage sources, with current storage as % of capacity — click a node for details.') + '</p></div>' +
    '<div class="wd-panel"><div class="wd-frame" id="wd-frame"></div><div class="wd-cap">' + T('กล่องสี % ทับตำแหน่งแหล่งเก็บกักบนผังน้ำ — กดเพื่อดูรายละเอียด (ฝาย/เช็คดำไม่แสดง % เนื่องจากไม่มีการติดตาม)', 'Colored % boxes sit on each storage source — click for details (weirs/check dams have no % because they are not monitored).') + '</div>' +
    '<div id="wd-det"></div><div class="wd-flt" id="wd-flt"></div><div class="wd-grid" id="wd-grid"></div></div></div>';
  host.parentNode.insertBefore(sec, host.nextSibling);
  var frame = sec.querySelector('#wd-frame'), detEl = sec.querySelector('#wd-det'), grid = sec.querySelector('#wd-grid'), flt = sec.querySelector('#wd-flt');

  function legendHtml() { return '<div class="wd-ov wd-leg">' + ['critical', 'warning', 'medium', 'safe', 'unknown'].map(function (k) { return '<span><i style="background:' + ST[k].badge + '"></i><em style="font-style:normal;color:' + ST[k].text + '">' + ST[k].dot + ' ' + sl(k) + '</em></span>'; }).join('') + '</div>'; }

  /* ---- ข้อมูลต่อแหล่ง ---- */
  function station(code) { return MON && (MON.stations || []).filter(function (x) { return x.station_code === code; })[0]; }
  function stationByName(name) { var a = String(name || '').replace(/\s+/g, ''); return MON && (MON.stations || []).filter(function (x) { var b = String(x.name_th || '').replace(/\s+/g, ''); return a && (a === b || a.indexOf(b) >= 0 || b.indexOf(a) >= 0); })[0]; }
  function estimate(s, o) {   // ไม่มีประวัติ % รายวัน → ประมาณจากระดับน้ำ × พื้นที่ผิวอ่าง ÷ ความจุ
    var rv = (MON.reservoirs || []).filter(function (r) { return r.name_th === s.name_th; })[0], A = rv && /\(([\d.]+)\s*ตร\.กม\./.exec(rv.area_display || ''); A = A ? +A[1] * 1e6 : null;
    var H = s.history || []; if (!A || !o.maxM3 || H.length < 25 || o.pct == null) return;
    var kk = A / o.maxM3 * 100, last = H[H.length - 1], byDay = {}; H.forEach(function (h) { byDay[h.t.slice(0, 10)] = h; });
    o.hist = Object.keys(byDay).sort().map(function (d) { return { iso: d, pct: Math.max(0, Math.round((o.pct + (byDay[d].level - last.level) * kk) * 10) / 10) }; });
    if (o.dW == null) { var t0 = new Date(last.t).getTime() - 7 * 864e5, best = null; H.forEach(function (h) { var dt = Math.abs(new Date(h.t).getTime() - t0); if (!best || dt < best.dt) best = { dt: dt, h: h }; }); if (best && best.dt < 36e5 * 30) o.dW = Math.round((last.level - best.h.level) * kk * 100) / 100; }
  }
  function buildData() {
    NODES.forEach(function (n) {
      var o = { pct: null, m3: null, maxM3: n.maxM3 || null, dW: n.dW != null ? n.dW : null, hist: (n.history || []).slice(), t: n.currentDate || null, snap: !!n.snap, st: null };
      var s = MON && (n.stationCode ? station(n.stationCode) : (FALLBACK_STATION[n.id] ? station(FALLBACK_STATION[n.id]) : null)) || (MODE === 'cy' ? stationByName(n.th) : null);
      if (n.pct != null) o.pct = n.pct, o.m3 = n.m3;
      if (s) {   // สถานีโทรมาตร = ข้อมูลสดกว่า
        o.pct = s.capacity_pct != null ? Math.round(s.capacity_pct * 10) / 10 : o.pct; o.m3 = s.storage_m3; o.maxM3 = s.storage_max_m3 || o.maxM3; o.t = s.measure_datetime; o.snap = false; o.st = s;
        if (!o.hist.length || o.dW == null) estimate(s, o);
      }
      S[n.id] = o;
    });
  }

  /* ---- การ์ดรายละเอียด + การ์ดแหล่งน้ำ (SourceDetailCard / SourceCard) ---- */
  function chartSvg(h) {
    var W = 620, H = 170, l = 34, r = 10, t = 10, b = 22, mx = Math.max(100, Math.ceil(Math.max.apply(null, h.map(function (p) { return p.pct; })) / 10) * 10), n = h.length;
    function X(i) { return l + (W - l - r) * i / Math.max(1, n - 1); } function Y(v) { return H - b - (H - b - t) * v / mx; }
    var yt = []; for (var v = 0; v <= mx; v += mx > 100 ? 40 : 25) yt.push(v);
    var gr = yt.map(function (v) { return '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="#e2e8f0" stroke-dasharray="3 3"/><text x="' + (l - 4) + '" y="' + (Y(v) + 3.5) + '" font-size="10" text-anchor="end" fill="#64748b">' + v + '%</text>'; }).join('');
    var xt = [0, Math.round((n - 1) / 3), Math.round((n - 1) * 2 / 3), n - 1].filter(function (v, i, a) { return a.indexOf(v) === i; }).map(function (i) { return '<text x="' + X(i) + '" y="' + (H - 6) + '" font-size="9" text-anchor="middle" fill="#64748b">' + fmtDate(h[i].iso).replace(/ \d{4}$/, '') + '</text>'; }).join('');
    var line = h.map(function (p, i) { return (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p.pct).toFixed(1); }).join('');
    return '<svg viewBox="0 0 ' + W + ' ' + H + '">' + gr + '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(100) + '" y2="' + Y(100) + '" stroke="#22c55e" stroke-dasharray="4 4"/><text x="' + (W - r - 2) + '" y="' + (Y(100) + 11) + '" font-size="9" text-anchor="end" fill="#16a34a">' + T('เต็มความจุ', 'Full') + '</text>' +
      '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(20) + '" y2="' + Y(20) + '" stroke="#ef4444" stroke-dasharray="4 4"/><text x="' + (W - r - 2) + '" y="' + (Y(20) - 3) + '" font-size="9" text-anchor="end" fill="#b91c1c">' + sl('critical') + '</text>' + xt +
      '<path d="' + line + '" fill="none" stroke="' + C.navy + '" stroke-width="2" stroke-linejoin="round"/><circle class="wd-dot" r="4" fill="' + C.navy + '" stroke="#fff" stroke-width="1.5" cx="-9" cy="-9"/></svg>';
  }
  function place(n) { return n.moo != null ? T('หมู่ ', 'Moo ') + n.moo + (n.village ? ' (' + n.village + ')' : '') : (n.stationCode || FALLBACK_STATION[n.id] ? T('สถานีโทรมาตร ', 'Telemetry ') + (n.stationCode || FALLBACK_STATION[n.id]) : T('ไม่มีสถานีโทรมาตร', 'No telemetry station')); }
  function paintGrid() {
    var list = NODES.filter(function (n) { return mooF === 'all' || String(n.moo) === String(mooF); });
    grid.innerHTML = list.map(function (n) {
      var d = S[n.id] || {}, k = getStatus(d.pct), cfg = ST[k], tr = trendInfo(d.dW), on = sel === n.id;
      return '<button type="button" class="wd-sc" data-id="' + esc(n.id) + '" style="background:' + cfg.bg + ';border:1.5px solid ' + (on ? C.navy : cfg.border) + '"><div class="r1"><div><div class="t">' + esc(nm(n)) + '</div><div class="s">' + esc(place(n)) + (n.isolated ? ' · ☁ ' + T('รับน้ำจากฝนเท่านั้น', 'rain-fed only') : '') + '</div></div>' +
        '<span class="pb" style="background:' + cfg.badge + '">' + cfg.dot + ' ' + sl(k) + '</span></div><div class="big"><b style="color:' + cfg.text + '">' + (d.pct != null ? d.pct + '%' : '—') + '</b><span>' + (d.m3 != null ? fmt(d.m3) + ' / ' + fmt(d.maxM3) + T(' ลบ.ม.', ' m³') : T('ไม่มีข้อมูลระดับน้ำ', 'No level data')) + '</span></div>' +
        '<div class="bar"><i style="width:' + Math.min(100, d.pct || 0) + '%;background:' + cfg.badge + '"></i></div><div class="tr" style="color:' + tr.color + '">' + tr.icon + ' ' + tr.label + '</div></button>';
    }).join('');
    var moos = []; NODES.forEach(function (n) { if (n.moo != null && moos.indexOf(n.moo) < 0) moos.push(n.moo); }); moos.sort(function (a, b) { return a - b; });
    flt.innerHTML = moos.length ? '<span>' + T('กรองตามหมู่:', 'Filter by moo:') + '</span><button type="button" data-moo="all" class="' + (mooF === 'all' ? 'on' : '') + '">' + T('ทั้งหมด', 'All') + '</button>' + moos.map(function (m) { return '<button type="button" data-moo="' + m + '" class="' + (String(mooF) === String(m) ? 'on' : '') + '">' + T('หมู่ ', 'Moo ') + m + '</button>'; }).join('') : '';
  }
  function paintDet() {
    var n = NODES.filter(function (x) { return x.id === sel; })[0]; if (!n) { detEl.innerHTML = ''; return; }
    var d = S[n.id] || {}, k = getStatus(d.pct), cfg = ST[k], tr = trendInfo(d.dW), has = d.hist && d.hist.length > 1;
    detEl.innerHTML = '<div class="wd-det" style="border:1.5px solid ' + cfg.border + '"><div class="wd-ph"><b>📷</b><span>' + T('ยังไม่มีรูปภาพ', 'No photo yet') + '</span><button class="wd-x" type="button" data-close="1" title="' + T('ปิด', 'Close') + '">✕</button></div><div class="wd-bd">' +
      '<div class="wd-hd"><div><div class="wd-nm">' + esc(nm(n)) + '</div><div class="wd-sub">' + esc(place(n)) + (n.isolated ? ' · ☁ ' + T('รับน้ำจากฝนเท่านั้น', 'rain-fed only') : '') + (d.t ? ' · ' + (d.snap ? T('ข้อมูล ณ ', 'as of ') : T('วัดเมื่อ ', 'measured ')) + fmtDT(d.t) : '') + '</div></div>' +
      '<span class="wd-bg" style="background:' + cfg.badge + '">' + cfg.dot + ' ' + sl(k) + (d.pct != null ? ' · ' + d.pct + '%' : '') + '</span></div>' +
      '<div class="wd-g2"><div><small>' + T('ปริมาตรน้ำ', 'Water volume') + '</small><b style="color:' + C.navy + '">' + (d.m3 != null ? fmt(d.m3) + ' / ' + fmt(d.maxM3) + T(' ลบ.ม.', ' m³') : T('ไม่มีข้อมูล', 'No data')) + '</b></div><div><small>' + T('แนวโน้ม/สัปดาห์', 'Trend / week') + '</small><b style="color:' + tr.color + '">' + tr.icon + ' ' + tr.label + '</b></div></div>' +
      (has ? '<div class="wd-chl">📈 ' + T('ระดับน้ำย้อนหลัง (%)', 'Level history (%)') + '</div><div class="wd-ch">' + chartSvg(d.hist) + '<div class="wd-tip"></div></div>'
        : '<div style="margin-top:12px;font-size:11px;color:' + C.muted + ';text-align:center;padding:10px 0">' + T('ยังไม่มีข้อมูลย้อนหลังเพียงพอสำหรับกราฟ', 'Not enough history for a chart yet') + '</div>') + '</div></div>';
    var ch = detEl.querySelector('.wd-ch');
    if (ch) {
      var svg = ch.querySelector('svg'), tip = ch.querySelector('.wd-tip'), dot = svg.querySelector('.wd-dot'), h = d.hist, W = 620, l = 34, r = 10, mx = Math.max(100, Math.ceil(Math.max.apply(null, h.map(function (p) { return p.pct; })) / 10) * 10);
      ch.addEventListener('mousemove', function (e) { var b = svg.getBoundingClientRect(), x = (e.clientX - b.left) / b.width * W, i = Math.max(0, Math.min(h.length - 1, Math.round((x - l) / (W - l - r) * (h.length - 1))));
        dot.setAttribute('cx', l + (W - l - r) * i / Math.max(1, h.length - 1)); dot.setAttribute('cy', 170 - 22 - (170 - 22 - 10) * h[i].pct / mx);
        tip.style.display = 'block'; tip.innerHTML = fmtDate(h[i].iso) + ' · <b>' + h[i].pct + '%</b>'; tip.style.left = Math.min(b.width - 130, Math.max(0, e.clientX - b.left + 10)) + 'px'; tip.style.top = '6px'; });
      ch.addEventListener('mouseleave', function () { tip.style.display = 'none'; dot.setAttribute('cx', -9); });
    }
  }
  function pick(id) { sel = id; if (MODE === 'svg') paintSvg(); else cyHighlight(); paintGrid(); paintDet(); }
  sec.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('[data-close]')) { sel = null; if (MODE === 'svg') paintSvg(); else cyHighlight(); paintGrid(); paintDet(); return; }
    var m = e.target.closest && e.target.closest('[data-moo]'); if (m) { mooF = m.getAttribute('data-moo'); paintGrid(); return; }
    if (MODE === 'svg') { var t = e.target.closest && e.target.closest('[data-id]'); if (t) pick(t.getAttribute('data-id')); }
    else { var c = e.target.closest && e.target.closest('.wd-sc[data-id]'); if (c) pick(c.getAttribute('data-id')); }
  });
  sec.addEventListener('keydown', function (e) { if ((e.key === 'Enter' || e.key === ' ') && e.target.getAttribute && e.target.getAttribute('data-id') && e.target.tagName !== 'BUTTON') { e.preventDefault(); pick(e.target.getAttribute('data-id')); } });

  /* ================= โหมดสำรอง: ภาพ SVG + กล่องสี ================= */
  function tri(n, p) { p = p || 0; var x0 = n.x - p, y0 = n.y - p, w0 = n.w + 2 * p, h0 = n.h + 2 * p; return (x0 + w0 / 2) + ',' + y0 + ' ' + x0 + ',' + (y0 + h0) + ' ' + (x0 + w0) + ',' + (y0 + h0); }
  function paintSvg() {
    var g = frame.querySelector('#wd-g'); if (!g) return;
    g.innerHTML = NODES.map(function (n) {
      var d = S[n.id] || {}, cfg = ST[getStatus(d.pct)], on = sel === n.id, isTri = n.shape === 'triangle', fs = Math.min(n.w, n.h) * 0.32;
      var ty = isTri ? n.y + n.h * 2 / 3 + fs * 0.3 : n.y + n.h / 2 + fs * 0.35, sw = on ? 4 : 2.5, stroke = on ? '#0c4a6e' : cfg.badge, fill = on ? cfg.badge : cfg.bg;
      var halo = on ? (isTri ? '<polygon points="' + tri(n, 6) + '" fill="' + cfg.badge + '" opacity=".25"/>' : '<rect x="' + (n.x - 6) + '" y="' + (n.y - 6) + '" width="' + (n.w + 12) + '" height="' + (n.h + 12) + '" rx="6" fill="' + cfg.badge + '" opacity=".25"/>') : '';
      var shape = isTri ? '<polygon class="wd-s" points="' + tri(n) + '" fill="' + fill + '" opacity=".92" stroke="' + stroke + '" stroke-width="' + sw + '" stroke-linejoin="round"/>' : '<rect class="wd-s" x="' + n.x + '" y="' + n.y + '" width="' + n.w + '" height="' + n.h + '" rx="6" fill="' + fill + '" opacity=".92" stroke="' + stroke + '" stroke-width="' + sw + '"/>';
      return '<g class="wd-n" tabindex="0" role="button" data-id="' + n.id + '" aria-label="' + esc(nm(n)) + (d.pct != null ? ' ' + Math.round(d.pct) + '%' : '') + '">' + halo + shape +
        '<text x="' + (n.x + n.w / 2) + '" y="' + ty + '" text-anchor="middle" fill="' + (on ? '#fff' : cfg.text) + '" font-size="' + fs + '" font-weight="700" font-family="Sarabun,Tahoma,sans-serif">' + (d.pct != null ? Math.round(d.pct) + '%' : '—') + '</text></g>';
    }).join('');
  }
  function initSvgMode() {
    MODE = 'svg';
    frame.innerHTML = '<svg viewBox="0 0 ' + VB_W + ' ' + VB_H + '" role="img" aria-label="' + T('ผังน้ำตำบลแม่นาเรือ', 'Mae Na Rua water-flow diagram') + '"><image href="' + BASE + 'assets/img/water-network-diagram.svg" x="0" y="0" width="' + VB_W + '" height="' + VB_H + '"/><g id="wd-g"></g></svg>' + legendHtml();
    var probe = new Image(); probe.onload = function () { sec.style.display = ''; }; probe.src = BASE + 'assets/img/water-network-diagram.svg';
    buildData(); paintSvg(); paintGrid();
  }

  /* ================= โหมดหลัก: Cytoscape ================= */
  var cyBase = BASE + 'assets/vendor/cytoscape/cytoscape.min.js', flowDots = [], flowOn = true, flowCancel = false, fontSize = 12, userMoved = false;
  function loadCy(cb) {
    if (window.cytoscape) return cb(true);
    var s = document.createElement('script'); s.src = cyBase; s.onload = function () { cb(!!window.cytoscape); }; s.onerror = function () { cb(false); }; document.head.appendChild(s);
  }
  function cyStyle() {
    var F = SANS;
    return [
      { selector: 'node', style: { 'background-color': '#adb5bd', width: 8, height: 8, label: 'data(label)', 'font-family': F, 'font-size': '12px', 'text-valign': 'top', 'text-margin-y': -5, 'text-wrap': 'wrap', 'text-max-width': '150px', 'text-rotation': function (e) { return (e.data('rotation') || 0) + 'deg'; } } },
      { selector: 'node[type = "generic_node"]', style: { 'background-color': '#6c757d', width: 10, height: 10 } },
      { selector: 'node[type = "text_box"]', style: { shape: 'rectangle', 'background-opacity': 0, width: 1, height: 1, color: '#d9534f', 'font-size': '14px', 'font-weight': 'bold', 'text-valign': 'center', 'text-halign': 'center', 'text-outline-width': 2, 'text-outline-color': '#ffffff' } },
      { selector: 'edge', style: { width: 3, 'line-color': '#4da6ff', 'target-arrow-color': '#4da6ff', 'target-arrow-shape': 'triangle', 'curve-style': 'taxi', 'taxi-direction': 'downward', label: 'data(label)', 'font-size': '12px', 'text-rotation': '0deg', 'text-margin-y': -10, 'text-background-color': '#ffffff', 'text-background-opacity': 0.7, 'text-background-padding': '2px' } },
      { selector: 'edge[type = "main"]', style: { width: 6, 'line-color': '#0056b3', 'target-arrow-color': '#0056b3' } },
      { selector: 'edge[?engineStraight]', style: { 'curve-style': 'straight' } },
      { selector: 'edge[?engineBend]', style: { 'curve-style': 'segments', 'segment-distances': 'data(segDist)', 'segment-weights': 'data(segWeight)' } },
      { selector: 'node[type = "gate"]', style: { shape: 'diamond', 'background-color': 'black', width: 25, height: 25, 'text-margin-y': -15 } },
      { selector: 'node[type = "weir"]', style: { shape: 'rectangle', 'background-color': 'black', width: 35, height: 12, 'text-margin-y': -10 } },
      { selector: 'node[type = "weir"][dir = "v"]', style: { width: 12, height: 35, 'text-margin-y': -5, 'text-margin-x': 0, 'text-valign': 'top', 'text-halign': 'center' } },
      { selector: 'node[type = "reservoir"]', style: { shape: 'triangle', 'background-color': 'black', width: 30, height: 30, 'text-margin-y': -15 } },
      { selector: 'node[type = "gate_plan"]', style: { shape: 'diamond', 'background-color': 'white', 'border-width': 2, 'border-color': 'black', width: 25, height: 25, 'text-margin-y': -15 } },
      { selector: 'node[type = "weir_plan"]', style: { shape: 'rectangle', 'background-color': 'white', 'border-width': 2, 'border-color': 'black', width: 35, height: 12, 'text-margin-y': -10 } },
      { selector: 'node[type = "weir_plan"][dir = "v"]', style: { width: 12, height: 35, 'text-margin-y': -5, 'text-margin-x': 0, 'text-valign': 'top', 'text-halign': 'center' } },
      { selector: 'node[type = "telemetry"]', style: { shape: 'ellipse', 'background-color': 'white', 'border-width': 4, 'border-color': 'black', width: 20, height: 20 } },
      { selector: 'node[type = "pump"]', style: { shape: 'ellipse', 'background-color': 'white', 'border-width': 2, 'border-color': 'black', width: 25, height: 25, label: 'P', 'text-valign': 'center', 'text-halign': 'center', 'font-weight': 'bold', color: 'black', 'font-size': '14px' } },
      { selector: 'node[type = "waterbody"]', style: { shape: 'round-rectangle', 'background-color': '#99ccff', 'border-width': 1, 'border-color': '#0056b3', width: 70, height: 35, 'text-valign': 'center', 'text-margin-y': 0, color: '#003366', 'font-weight': 'bold' } },
      { selector: 'node[type = "waterbody"][dir = "v"]', style: { width: 35, height: 70 } },
      { selector: 'node[?hasStatus]', style: { 'background-color': 'data(statusColor)', 'border-color': 'data(statusColor)' } },
      { selector: 'node[status = "ชำรุด"]', style: { 'background-color': '#dc2626', 'border-color': '#7f1d1d', 'border-width': 2.5 } },
      { selector: '.flow-dot', style: { label: '', shape: 'ellipse', width: 6, height: 6, 'background-color': '#7dd3fc', 'background-opacity': 0.95, 'border-width': 1, 'border-color': '#0ea5e9', 'border-opacity': 0.6, events: 'no', 'z-compound-depth': 'top' } },
      { selector: '.selected-source', style: { 'border-width': 4, 'border-color': '#9333ea', 'border-opacity': 1 } }
    ];
  }
  function cyRefit() { if (!cy) return; cy.resize(); cy.fit(fitTarget || undefined, 40); }
  function cyHighlight() { if (!cy) return; cy.nodes().removeClass('selected-source'); var n = NODES.filter(function (x) { return x.id === sel; })[0]; if (n && n.ref) cy.nodes('[sourceRef = "' + n.ref + '"]').addClass('selected-source'); }
  function cyLabels() {
    if (!cy) return; var byRef = {}; NODES.forEach(function (n) { if (n.ref) byRef[n.ref] = n; });
    cy.nodes().forEach(function (node) {
      var ref = node.data('sourceRef'), n = ref && byRef[ref]; if (!n) return; var d = S[n.id] || {};
      if (node.data('origLabel') === undefined) node.data('origLabel', node.data('label') || ref);
      node.data({ hasStatus: true, statusColor: ST[getStatus(d.pct)].badge });
      node.data('label', node.data('origLabel') + (n.isolated ? ' ☁' : '') + '\n' + (d.pct != null ? Math.round(d.pct) + '%' : '—'));
    });
  }
  function startFlow() {
    flowCancel = true; flowDots.forEach(function (d) { if (!d.removed()) d.remove(); }); flowDots = []; if (!cy || !flowOn) return; flowCancel = false;
    var me = cy.edges('[type = "main"]'); if (!me.length) return;
    function loop(dot, edge, dur) {
      if (flowCancel || dot.removed() || edge.removed()) return; dot.position(edge.sourceEndpoint());
      dot.animate({ position: edge.midpoint() }, { duration: dur / 2, easing: 'linear', complete: function () { if (flowCancel || dot.removed() || edge.removed()) return; dot.animate({ position: edge.targetEndpoint() }, { duration: dur / 2, easing: 'linear', complete: function () { loop(dot, edge, dur); } }); } });
    }
    me.forEach(function (edge, i) { var s = edge.sourceEndpoint(), dot = cy.add({ group: 'nodes', classes: 'flow-dot', data: { id: 'flowdot-' + edge.id() }, position: { x: s.x, y: s.y }, selectable: false, grabbable: false }); flowDots.push(dot); setTimeout(function () { loop(dot, edge, 2200); }, i * 260); });
  }
  function panel(html) { var p = frame.querySelector('.wd-pn'); if (p) p.remove(); if (html) { var d = document.createElement('div'); d.className = 'wd-ov wd-pn'; d.innerHTML = html; frame.appendChild(d); var x = d.querySelector('.x'); if (x) x.onclick = function () { d.remove(); }; } }
  function structPanel(kind, label, type, status, code) {
    if (kind === 'infra') {
      var bad = status === 'ชำรุด', tn = { gate: T('ประตูระบายน้ำ (ปตร.)', 'Sluice gate'), weir: T('ฝาย', 'Weir'), pump: T('ระบบสูบน้ำ', 'Pump station') }[type] || type;
      panel('<button class="x">✕</button><h5>' + esc(label) + '</h5><small style="font-size:11px;margin-top:2px">' + tn + '</small><div style="display:inline-block;margin-top:6px;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:700;background:' + (bad ? '#fef2f2' : '#f0fdf4') + ';color:' + (bad ? '#dc2626' : '#15803d') + ';border:1px solid ' + (bad ? '#fecaca' : '#bbf7d0') + '">' + (bad ? '⚠️ ' + T('ชำรุด', 'Broken') : '✅ ' + T('ใช้งานได้', 'Working')) + '</div>'); return;
    }
    var s = station(code), H = s && s.history || [];
    if (!s) { panel('<button class="x">✕</button><h5>' + esc(label || T('สถานีโทรมาตร', 'Telemetry')) + '</h5><small>' + T('สถานีโทรมาตร', 'Telemetry station') + '</small><div style="font-size:11px;color:' + C.muted + ';margin-top:10px">⏳ ' + T('ยังไม่มีข้อมูลระดับน้ำจากสถานีนี้', 'No level data from this station yet') + '</div>'); return; }
    var prev = H.length >= 2 ? Math.round((s.water_level - H[H.length - 2].level) * 100) / 100 : null, dist = s.distance_to_spillway_m;
    panel('<button class="x">✕</button><h5>' + esc(s.station_code) + '</h5><small>' + T('สถานีโทรมาตร', 'Telemetry station') + '</small><small style="margin-top:8px">🕐 ' + T('ข้อมูลล่าสุด ', 'Latest ') + fmtDT(s.measure_datetime) + '</small>' +
      '<div style="display:flex;gap:8px;border-top:.5px solid #e2e8f0;margin-top:8px;padding-top:8px"><div style="flex:1"><small>' + T('ระดับน้ำปัจจุบัน', 'Current level') + '</small><div style="font-size:16px;font-weight:700;color:' + C.navy + '">' + (Math.round(s.water_level * 100) / 100) + ' <span style="font-size:10px;font-weight:400;color:' + C.muted + '">' + T('ม.รทก.', 'm MSL') + '</span></div></div>' +
      '<div style="flex:1"><small>' + T('เทียบรอบก่อนหน้า', 'vs previous reading') + '</small>' + (prev == null ? '<div style="font-size:12px;color:' + C.muted + ';margin-top:3px">' + T('ไม่มีข้อมูล', 'No data') + '</div>' : '<div style="font-size:16px;font-weight:700;color:#0ea5e9">' + (prev >= 0 ? '▲' : '▼') + ' ' + Math.abs(prev) + ' <span style="font-size:10px;font-weight:400;color:' + C.muted + '">' + T('ม.', 'm') + '</span></div>') + '</div></div>' +
      '<div class="g"><div class="b"><small>' + T('ระดับสปิลเวย์', 'Spillway level') + '</small><b style="font-size:13px;color:' + C.navy + '">' + s.spillway_msl + ' ' + T('ม.', 'm') + '</b></div><div class="b"><small>' + T('ระยะจากสปิลเวย์', 'vs spillway') + '</small><b style="font-size:13px;color:' + (dist > 0 ? '#dc2626' : C.navy) + '">' + (dist > 0 ? '+' : '') + Math.round(dist * 100) / 100 + ' ' + T('ม.', 'm') + '</b><small style="color:#94a3b8">' + (dist > 0 ? T('สูงกว่าสปิลเวย์', 'above spillway') : T('ต่ำกว่าสปิลเวย์', 'below spillway')) + '</small></div></div>' +
      '<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;padding:6px 8px;margin-top:6px"><small>' + T('ปริมาณน้ำปัจจุบัน', 'Current storage') + '</small><b style="font-size:14px;color:' + C.navy + '">' + fmt(s.storage_m3) + ' ' + T('ลบ.ม.', 'm³') + '</b></div>');
  }
  function initCyMode(net) {
    MODE = 'cy';
    var tb = '<div class="wd-ov wd-north"><div style="font-size:16px;line-height:1">↑</div><div>' + T('เหนือ', 'North') + '</div></div>' +
      '<div class="wd-ov wd-tb"><span style="color:' + C.muted + ';margin-right:2px">' + T('ตัวอักษร', 'Font') + '</span><button class="wd-sq" data-a="f-">−</button><span id="wd-fs" style="width:16px;text-align:center">12</span><button class="wd-sq" data-a="f+">+</button><div class="wd-sep"></div>' +
      '<button class="wd-bw" data-a="fit" title="' + T('จัดกึ่งกลางผังน้ำใหม่', 'Re-center') + '">⤢ ' + T('จัดกึ่งกลาง', 'Fit') + '</button><div class="wd-sep"></div><button class="wd-bw" data-a="fs" id="wd-fsb">⤢ ' + T('เต็มจอ', 'Fullscreen') + '</button><div class="wd-sep"></div>' +
      '<button class="wd-bw" data-a="flow" id="wd-flow" style="border-color:#0ea5e9;background:#e0f2fe">💧 ' + T('น้ำไหล: เปิด', 'Flow: on') + '</button></div>';
    var li = function (shape, label) { return '<div><span class="wd-li">' + shape + '</span><span style="color:#334155">' + label + '</span></div>'; };
    var leg2 = '<div class="wd-ov wd-leg2">' + li('<i style="width:16px;height:2px;background:#4da6ff;display:block"></i>', T('แม่น้ำ/คลอง', 'River/canal')) + li('<i style="width:10px;height:10px;background:#000;transform:rotate(45deg);display:block"></i>', T('ปตร.', 'Gate')) +
      li('<i style="width:12px;height:11px;background:#000;clip-path:polygon(50% 0,100% 100%,0 100%);display:block"></i>', T('อ่างเก็บน้ำ', 'Reservoir')) + li('<i style="width:14px;height:5px;background:#000;display:block"></i>', T('ฝาย', 'Weir')) +
      li('<i style="width:10px;height:10px;border-radius:50%;border:2.5px solid #000;background:#fff;display:block"></i>', T('โทรมาตร', 'Telemetry')) + li('<i style="width:10px;height:10px;border-radius:50%;border:1.5px solid #000;background:#fff;font-size:7px;font-weight:700;display:flex;align-items:center;justify-content:center;font-style:normal">P</i>', T('ระบบสูบน้ำ', 'Pump')) + li('<span style="font-size:12px">☁</span>', T('รับน้ำจากฝนเท่านั้น', 'Rain-fed only')) + '</div>';
    frame.style.height = '460px';
    frame.innerHTML = '<div id="wd-cyc" style="width:100%;height:100%"></div><div class="wd-msg" id="wd-msg">⏳ ' + T('กำลังโหลดผังน้ำ…', 'Loading diagram…') + '</div>' + tb + leg2 + legendHtml();
    sec.style.display = '';
    var started = false;
    function start() {
      if (started) return; started = true;
      loadCy(function (ok) {
        if (!ok) { initSvgMode(); return; }
        var els = net.nodes.map(function (r) { return { data: { id: r.node_key, label: r.label || '', type: r.node_type || undefined, rotation: r.rotation || 0, dir: r.dir || 'h', sourceRef: r.source_ref || '', status: r.status || null }, position: { x: r.pos_x, y: r.pos_y } }; })
          .concat((net.edges || []).map(function (r) { var d = { id: r.edge_key, source: r.source_node_key, target: r.target_node_key, label: r.label || '', type: r.edge_type || undefined }; if (r.engine_straight) d.engineStraight = true; if (r.engine_bend) { d.engineBend = true; d.segDist = r.seg_dist; d.segWeight = r.seg_weight; } return { data: d }; }));
        (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () { requestAnimationFrame(function () {
          var c = frame.querySelector('#wd-cyc'); if (!c) return;
          cy = window.cytoscape({ container: c, elements: els, layout: { name: 'preset' }, style: cyStyle(), userZoomingEnabled: true, userPanningEnabled: true, boxSelectionEnabled: false, autoungrabify: true });
          cy.on('tap', 'node', function (evt) {
            var t = evt.target, ref = t.data('sourceRef');
            if (ref) { var n = NODES.filter(function (x) { return x.ref === ref; })[0]; panel(''); if (n) pick(n.id); return; }
            var ty = t.data('type'), lab = t.data('origLabel') || t.data('label') || ty;
            if (ty === 'gate' || ty === 'weir' || ty === 'pump') structPanel('infra', lab, ty, t.data('status')); else if (ty === 'telemetry') structPanel('tele', lab, ty, null, lab);
          });
          cy.on('tap', function (e) { if (e.target === cy) panel(''); }); cy.on('pan zoom', function () { userMoved = true; });
          var comps = cy.elements().components(), main = cy.elements();
          if (comps.length > 1) { var big = comps.reduce(function (a, b) { return a.length >= b.length ? a : b; }); main = big.union(cy.elements().filter(function (e) { return e.isEdge() || e.data('sourceRef') || (e.data('label') && String(e.data('label')).trim()); })); }
          fitTarget = main; cyRefit(); setTimeout(function () { if (cy && !userMoved) cyRefit(); }, 200);
          var m = frame.querySelector('#wd-msg'); if (m) m.remove();
          cyLabels(); cyHighlight(); startFlow();
          if (window.ResizeObserver) new ResizeObserver(function () { if (cy && !userMoved) cyRefit(); }).observe(c);
        }); });
      });
    }
    if ('IntersectionObserver' in window) { var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { io.disconnect(); start(); } }, { rootMargin: '400px' }); io.observe(sec); } else start();
    frame.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('[data-a]'); if (!b || !cy) return; var a = b.getAttribute('data-a'), fsE = frame.querySelector('#wd-fs');
      if (a === 'f-' || a === 'f+') { fontSize = Math.max(6, Math.min(24, fontSize + (a === 'f+' ? 1 : -1))); fsE.textContent = fontSize; cy.style().selector('node').style({ 'font-size': fontSize + 'px' }).selector('edge').style({ 'font-size': Math.max(fontSize - 2, 8) + 'px' }).update(); }
      else if (a === 'fit') cyRefit();
      else if (a === 'fs') { if (document.fullscreenElement) document.exitFullscreen && document.exitFullscreen(); else frame.requestFullscreen && frame.requestFullscreen(); }
      else if (a === 'flow') { flowOn = !flowOn; b.textContent = '💧 ' + (flowOn ? T('น้ำไหล: เปิด', 'Flow: on') : T('น้ำไหล: ปิด', 'Flow: off')); b.style.borderColor = flowOn ? '#0ea5e9' : '#cbd5e1'; b.style.background = flowOn ? '#e0f2fe' : '#fff'; startFlow(); }
    });
    document.addEventListener('fullscreenchange', function () { var on = document.fullscreenElement === frame; frame.style.height = on ? '100vh' : '460px'; var b = frame.querySelector('#wd-fsb'); if (b) b.textContent = '⤢ ' + (on ? T('ออกเต็มจอ', 'Exit fullscreen') : T('เต็มจอ', 'Fullscreen')); requestAnimationFrame(cyRefit); });
    buildData(); paintGrid();
  }

  /* ---- เริ่มทำงาน ---- */
  Promise.all([J('monitoring.json'), J('water_network.json')]).then(function (r) {
    MON = r[0]; NET = r[1];
    if (NET && NET.nodes && NET.nodes.length && window.Promise) {
      var stor = (NET.sources || []).filter(function (s) { return s.role === 'storage'; });
      if (stor.length) {
        NODES = stor.map(function (s) { return { id: s.id, ref: s.ref, th: s.name, en: s.nameEn, moo: s.moo, village: s.village, isolated: s.isolated, maxM3: s.maxM3, pct: s.pct, m3: s.m3, dW: s.dW, history: s.history, currentDate: s.currentDate, snap: true }; });
        initCyMode(NET); return;
      }
    }
    initSvgMode();
  });
})();
