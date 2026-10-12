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
    '#water-diagram .wd-frame::after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:inherit;box-shadow:inset 0 0 64px rgba(12,74,110,.10);z-index:2}' +
    '#water-diagram .wd-frame{box-shadow:0 18px 38px -22px rgba(12,74,110,.5),0 2px 8px rgba(0,0,0,.06)}' +
    '#water-diagram .wd-bw.wd-on{border-color:#0ea5e9;background:#e0f2fe}#water-diagram .wd-brk{flex-basis:100%;height:0}#water-diagram .wd-tb{max-width:calc(100% - 340px)}' +
    '#water-diagram .wd-leg{right:8px}' +
    '#water-diagram .wd-scrub{left:50%;bottom:8px;transform:translateX(-50%);padding:5px 10px;display:flex;align-items:center;gap:8px;white-space:nowrap}#water-diagram .wd-scrub input{width:clamp(120px,22vw,260px);accent-color:#0ea5e9}' +
    '@media(max-width:760px){#water-diagram .wd-scrub{bottom:96px}#water-diagram .wd-tb{max-width:calc(100% - 80px)}}' +
    '#water-diagram .wd-frame:fullscreen{border-radius:0}#water-diagram .wd-frame:fullscreen .wd-ov{zoom:var(--wdz,1.6)}#water-diagram .wd-frame:fullscreen .wd-pn{max-height:calc((100vh - 24px) / var(--wdz,1.6))}' +
    '#water-diagram .wd-n{cursor:pointer}#water-diagram .wd-n:focus{outline:none}#water-diagram .wd-n:focus-visible .wd-s{stroke:#0c4a6e;stroke-width:6}' +
    '#water-diagram .wd-ov{position:absolute;background:rgba(255,255,255,.92);border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.15);font-size:11px;color:#0f172a;z-index:3}' +
    '#water-diagram .wd-tb{top:8px;left:70px;padding:4px 6px;display:flex;align-items:center;gap:4px;flex-wrap:wrap}#water-diagram .wd-north{top:8px;left:8px;padding:4px 10px 6px;display:flex;flex-direction:column;align-items:center;font-weight:700}' +
    '#water-diagram .wd-sq{width:20px;height:20px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;cursor:pointer;font-size:12px;line-height:1;padding:0;color:#0f172a}' +
    '#water-diagram .wd-bw{border:1px solid #cbd5e1;border-radius:4px;padding:2px 8px;background:#fff;cursor:pointer;font-size:11px;font-weight:600;color:' + C.navy + ';font-family:' + SANS + '}' +
    '#water-diagram .wd-sep{width:1px;height:16px;background:#e2e8f0;margin:0 2px}' +
    '#water-diagram .wd-leg,#water-diagram .wd-leg2{bottom:8px;padding:5px 10px;font-size:10px;display:flex;gap:10px;flex-wrap:wrap}#water-diagram .wd-leg{right:8px;justify-content:flex-end;max-width:220px}#water-diagram .wd-leg2{left:8px;padding:6px 10px;display:grid;grid-template-columns:auto auto;gap:3px 10px}' +
    '#water-diagram .wd-leg span,#water-diagram .wd-leg2 div{display:flex;align-items:center;gap:4px}#water-diagram .wd-leg i{width:14px;height:9px;border-radius:2px;flex-shrink:0;display:inline-block}' +
    '#water-diagram .wd-li{width:16px;display:flex;align-items:center;justify-content:center;flex-shrink:0}' +
    '#water-diagram .wd-pn{top:8px;right:8px;width:270px;max-width:calc(100% - 16px);max-height:calc(100% - 16px);overflow:auto;z-index:5;padding:10px 14px 12px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.18);background:#fff;border:1.5px solid #cbd5e1}#water-diagram .wd-pn h5{margin:0;font-size:13px;color:' + C.navy + '}#water-diagram .wd-pn .x{border:none;background:none;cursor:pointer;font-size:14px;color:' + C.muted + ';line-height:1;padding:0;float:right}' +
    '#water-diagram .wd-pn small{display:block;font-size:10px;color:' + C.muted + '}#water-diagram .wd-pn .b{background:#f8fafc;border-radius:6px;padding:6px 8px}#water-diagram .wd-pn .g{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}' +
    '#water-diagram .wd-msg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.85);font-size:13px;color:' + C.muted + ';z-index:4}' +
    '#water-diagram .wd-leg{position:absolute}#water-diagram .wd-br .wd-leg{position:static}#water-diagram .wd-cap{padding:8px 2px;font-size:11px;color:' + C.muted + '}' +
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
    '<div class="wd-panel"><div class="wd-frame" id="wd-frame"></div></div></div>';
  host.parentNode.insertBefore(sec, host.nextSibling);
  var frame = sec.querySelector('#wd-frame');

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
  function chartSvg(h, markIso) {
    var W = 620, H = 170, l = 34, r = 10, t = 10, b = 22, mx = Math.max(100, Math.ceil(Math.max.apply(null, h.map(function (p) { return p.pct; })) / 10) * 10), n = h.length;
    function X(i) { return l + (W - l - r) * i / Math.max(1, n - 1); } function Y(v) { return H - b - (H - b - t) * v / mx; }
    var yt = []; for (var v = 0; v <= mx; v += mx > 100 ? 40 : 25) yt.push(v);
    var gr = yt.map(function (v) { return '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="#e2e8f0" stroke-dasharray="3 3"/><text x="' + (l - 4) + '" y="' + (Y(v) + 3.5) + '" font-size="10" text-anchor="end" fill="#64748b">' + v + '%</text>'; }).join('');
    var xt = [0, Math.round((n - 1) / 3), Math.round((n - 1) * 2 / 3), n - 1].filter(function (v, i, a) { return a.indexOf(v) === i; }).map(function (i) { return '<text x="' + X(i) + '" y="' + (H - 6) + '" font-size="9" text-anchor="middle" fill="#64748b">' + fmtDate(h[i].iso).replace(/ \d{4}$/, '') + '</text>'; }).join('');
    var line = h.map(function (p, i) { return (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p.pct).toFixed(1); }).join('');
    return '<svg viewBox="0 0 ' + W + ' ' + H + '">' + gr + '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(100) + '" y2="' + Y(100) + '" stroke="#22c55e" stroke-dasharray="4 4"/><text x="' + (W - r - 2) + '" y="' + (Y(100) + 11) + '" font-size="9" text-anchor="end" fill="#16a34a">' + T('เต็มความจุ', 'Full') + '</text>' +
      '<line x1="' + l + '" x2="' + (W - r) + '" y1="' + Y(20) + '" y2="' + Y(20) + '" stroke="#ef4444" stroke-dasharray="4 4"/><text x="' + (W - r - 2) + '" y="' + (Y(20) - 3) + '" font-size="9" text-anchor="end" fill="#b91c1c">' + sl('critical') + '</text>' + xt +
      (function () { if (!markIso) return ''; var ix = -1; for (var q = 0; q < n; q++) if (h[q].iso <= markIso) ix = q; return ix < 0 ? '' : '<line x1="' + X(ix) + '" x2="' + X(ix) + '" y1="' + t + '" y2="' + (H - b) + '" stroke="#c2410c" stroke-dasharray="3 3"/><circle cx="' + X(ix) + '" cy="' + Y(h[ix].pct) + '" r="4" fill="#c2410c" stroke="#fff" stroke-width="1.5"/>'; })() + '<path d="' + line + '" fill="none" stroke="' + C.navy + '" stroke-width="2" stroke-linejoin="round"/><circle class="wd-dot" r="4" fill="' + C.navy + '" stroke="#fff" stroke-width="1.5" cx="-9" cy="-9"/></svg>';
  }
  function place(n) { return n.moo != null ? T('หมู่ ', 'Moo ') + n.moo + (n.village ? ' (' + n.village + ')' : '') : (((S[n.id] || {}).st || {}).station_code || n.stationCode || FALLBACK_STATION[n.id] ? T('สถานีโทรมาตร ', 'Telemetry ') + (((S[n.id] || {}).st || {}).station_code || n.stationCode || FALLBACK_STATION[n.id]) : T('ไม่มีสถานีโทรมาตร', 'No telemetry station')); }
  function paintDet() {   // กล่องข้อมูลอ่าง (มุมขวาบนของผัง) สไตล์เดียวกับกล่องโทรมาตร
    var n = NODES.filter(function (x) { return x.id === sel; })[0]; if (!n) { panel(''); return; }
    var d = S[n.id] || {}, v = MODE === 'cy' ? view(n) : { pct: d.pct, m3: d.m3, live: true }, k = getStatus(v.pct), cfg = ST[k], tr = v.live ? trendInfo(d.dW) : { icon: '📅', label: T('ย้อนหลัง', 'History'), color: '#c2410c' }, has = d.hist && d.hist.length > 1;
    panel('<button class="x" type="button">✕</button><h5>' + esc(nm(n)) + '</h5><small>' + esc(place(n)) + (n.isolated ? ' · ☁ ' + T('รับน้ำจากฝนเท่านั้น', 'rain-fed only') : '') + '</small>' +
      '<small style="margin-top:6px">🕐 ' + (!v.live ? T('ดูย้อนหลัง ', 'Viewing ') + fmtDate(scrubIso) : d.t ? (d.snap ? T('ข้อมูล ณ ', 'As of ') : T('ข้อมูลล่าสุด ', 'Latest ')) + fmtDT(d.t) : T('ไม่มีข้อมูล', 'No data')) + '</small>' +
      '<div style="margin-top:8px"><span class="wd-bg" style="background:' + cfg.badge + '">' + cfg.dot + ' ' + sl(k) + (v.pct != null ? ' · ' + v.pct + '%' : '') + '</span></div>' +
      '<div class="g"><div class="b"><small>' + T('ปริมาตรน้ำ', 'Water volume') + '</small><b style="font-size:13px;color:' + C.navy + '">' + (v.m3 != null ? fmt(v.m3) + ' / ' + fmt(d.maxM3) : T('ไม่มีข้อมูล', 'No data')) + '</b><small>' + T('ลบ.ม.', 'm³') + '</small></div>' +
      '<div class="b"><small>' + T('แนวโน้ม/สัปดาห์', 'Trend / week') + '</small><b style="font-size:13px;color:' + tr.color + '">' + tr.icon + ' ' + tr.label + '</b></div></div>' +
      (has ? '<small style="margin-top:8px">📈 ' + T('ระดับน้ำย้อนหลัง (%)', 'Level history (%)') + '</small><div class="wd-ch">' + chartSvg(d.hist, v.live ? null : scrubIso) + '<div class="wd-tip"></div></div>'
        : '<div style="margin-top:8px;font-size:11px;color:' + C.muted + '">' + T('ยังไม่มีข้อมูลย้อนหลังเพียงพอสำหรับกราฟ', 'Not enough history for a chart yet') + '</div>'));
    var pn = frame.querySelector('.wd-pn'), x = pn && pn.querySelector('.x'); if (x) x.onclick = clearSel;
    var ch = pn && pn.querySelector('.wd-ch');
    if (ch) {
      var svg = ch.querySelector('svg'), tip = ch.querySelector('.wd-tip'), dot = svg.querySelector('.wd-dot'), h = d.hist, W = 620, l = 34, r = 10, mx = Math.max(100, Math.ceil(Math.max.apply(null, h.map(function (p) { return p.pct; })) / 10) * 10);
      ch.addEventListener('mousemove', function (e) { var b = svg.getBoundingClientRect(), x = (e.clientX - b.left) / b.width * W, i = Math.max(0, Math.min(h.length - 1, Math.round((x - l) / (W - l - r) * (h.length - 1))));
        dot.setAttribute('cx', l + (W - l - r) * i / Math.max(1, h.length - 1)); dot.setAttribute('cy', 170 - 22 - (170 - 22 - 10) * h[i].pct / mx);
        tip.style.display = 'block'; tip.innerHTML = fmtDate(h[i].iso) + ' · <b>' + h[i].pct + '%</b>'; var z = document.fullscreenElement === frame ? (parseFloat(frame.style.getPropertyValue('--wdz')) || 1) : 1; tip.style.left = Math.min(b.width / z - 110, Math.max(0, (e.clientX - b.left) / z + 8)) + 'px'; tip.style.top = '0px'; });
      ch.addEventListener('mouseleave', function () { tip.style.display = 'none'; dot.setAttribute('cx', -9); });
    }
  }
  function pick(id) { sel = id; if (MODE === 'svg') paintSvg(); else cyHighlight(); paintDet(); }
  sec.addEventListener('click', function (e) {
    if (MODE === 'svg') { var t = e.target.closest && e.target.closest('[data-id]'); if (t) pick(t.getAttribute('data-id')); }
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
    buildData(); paintSvg();
  }

  /* ================= โหมดหลัก: Cytoscape ================= */
  var FH = Math.round(Math.min(720, Math.max(520, window.innerHeight * 0.78))) + 'px', cyBase = BASE + 'assets/vendor/cytoscape/cytoscape.min.js', flowOn = true, fontSize = 12, userMoved = false, lineScale = 2,
    baseZoom = 1, scrubIso = null, dates = [], playT = null, inView = true, flowEdges = null, flowOff = 0, flowSpeed = 40, lastT = 0, pulseNodes = null,
    REDUCED = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  function applyLines() {
    if (!cy) return; var k = lineScale;
    cy.style().selector('edge').style({ width: 3 * k, 'arrow-scale': Math.max(0.8, k * 0.8) }).selector('edge[type = "main"]').style({ width: 6 * k, 'underlay-padding': 2.4 * k }).selector('edge.flowline').style({ width: 2.2 * k }).update();
  }
  function loadCy(cb) {
    if (window.cytoscape) return cb(true);
    var s = document.createElement('script'); s.src = cyBase; s.onload = function () { cb(!!window.cytoscape); }; s.onerror = function () { cb(false); }; document.head.appendChild(s);
  }
  function cyStyle() {
    var F = SANS;
    return [
      { selector: 'node', style: { 'background-color': '#adb5bd', width: 8, height: 8, label: 'data(label)', 'font-family': F, 'font-size': '12px', 'text-valign': 'top', 'text-margin-y': -5, 'text-wrap': 'wrap', 'text-max-width': '150px', 'text-rotation': function (e) { return (e.data('rotation') || 0) + 'deg'; },
        'text-background-color': '#ffffff', 'text-background-opacity': 0.78, 'text-background-padding': '2px', 'text-background-shape': 'roundrectangle', 'underlay-opacity': 0, 'underlay-shape': 'ellipse' } },
      { selector: 'node[type = "generic_node"]', style: { 'background-color': '#6c757d', width: 10, height: 10 } },
      { selector: 'node[type = "text_box"]', style: { shape: 'rectangle', 'background-opacity': 0, width: 1, height: 1, color: '#d9534f', 'font-size': '14px', 'font-weight': 'bold', 'text-valign': 'center', 'text-halign': 'center', 'text-outline-width': 2, 'text-outline-color': '#ffffff', 'text-background-opacity': 0 } },
      { selector: 'edge', style: { width: 3, 'line-color': '#58a8f5', 'target-arrow-color': '#58a8f5', 'target-arrow-shape': 'triangle', 'curve-style': 'taxi', 'taxi-direction': 'downward', label: 'data(label)', 'font-size': '12px', 'text-rotation': '0deg', 'text-margin-y': -10,
        'text-background-color': '#ffffff', 'text-background-opacity': 0.8, 'text-background-padding': '2px', 'text-background-shape': 'roundrectangle', 'min-zoomed-font-size': 7 } },
      { selector: 'edge[type = "main"]', style: { width: 6, 'line-color': '#1565c0', 'target-arrow-color': '#0b4a99', 'underlay-color': '#0a3a78', 'underlay-opacity': 0.5, 'underlay-padding': 4 } },
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
      { selector: 'node[type = "kwan_band"]', style: { shape: 'round-rectangle', width: 'data(w)', height: 'data(h)', 'background-color': '#bfe0ff', 'background-opacity': 0.7, 'border-width': 2, 'border-style': 'dashed', 'border-color': '#0b4a99', 'border-opacity': 0.8,
        label: 'data(label)', color: '#0a3a78', 'font-size': '30px', 'font-weight': 'bold', 'text-valign': 'center', 'text-halign': 'center', 'text-margin-y': 0, 'text-rotation': '-90deg', 'text-wrap': 'wrap', 'text-max-width': '600px', 'text-background-opacity': 0, events: 'no' } },
      { selector: 'node.halo-critical', style: { 'underlay-color': '#ef4444', 'underlay-opacity': 0.28, 'underlay-padding': 11 } },
      { selector: 'node.halo-warning', style: { 'underlay-color': '#f97316', 'underlay-opacity': 0.26, 'underlay-padding': 11 } },
      { selector: 'node.halo-full', style: { 'underlay-color': '#22c55e', 'underlay-opacity': 0.28, 'underlay-padding': 9 } },
      { selector: 'edge.flowline', style: { width: 5, 'line-color': '#e3f4ff', 'line-style': 'dashed', 'line-dash-pattern': [9, 15], 'line-cap': 'round', 'target-arrow-shape': 'none', label: '', events: 'no', opacity: 0.95, 'underlay-opacity': 0, 'z-index': 20 } },
      { selector: '.selected-source', style: { 'border-width': 4, 'border-color': '#9333ea', 'border-opacity': 1 } },
      { selector: '.flowoff', style: { display: 'none' } }
    ];
  }
  function cyRefit() { if (!cy) return; cy.resize(); cy.fit(fitTarget || undefined, 40); baseZoom = cy.zoom(); }
  function cyHighlight() { if (!cy) return; cy.nodes().removeClass('selected-source'); var n = NODES.filter(function (x) { return x.id === sel; })[0]; if (n && n.ref) cy.nodes('[sourceRef = "' + n.ref + '"]').addClass('selected-source'); }
  function srcNode(n) { return cy && n && n.ref ? cy.nodes().filter(function (e) { return e.data('sourceRef') === n.ref; }) : null; }
  function clearSel() { sel = null; if (MODE === 'svg') paintSvg(); else { cyHighlight(); } panel(''); }
  function view(n) {   // ค่าที่แสดง ณ วันที่เลื่อนดู (null = ปัจจุบัน)
    var d = S[n.id] || {}; if (!scrubIso) return { pct: d.pct, m3: d.m3, live: true };
    var h = d.hist || [], p = null; for (var i = 0; i < h.length; i++) { if (h[i].iso <= scrubIso) p = h[i].pct; else break; }
    return { pct: p, m3: p != null && d.maxM3 ? Math.round(p / 100 * d.maxM3) : null, live: false };
  }
  function cyLabels() {
    if (!cy) return; var byRef = {}; NODES.forEach(function (n) { if (n.ref) byRef[n.ref] = n; });
    cy.nodes().forEach(function (node) {
      var ref = node.data('sourceRef'), n = ref && byRef[ref]; if (!n) return; var v = view(n), k = getStatus(v.pct);
      if (node.data('origLabel') === undefined) node.data('origLabel', node.data('label') || ref);
      node.data({ hasStatus: true, statusColor: ST[k].badge });
      node.data('label', node.data('origLabel') + (n.isolated ? ' ☁' : '') + '\n' + (v.pct != null ? Math.round(v.pct) + '%' : '—'));
      node.removeClass('halo-critical halo-warning halo-full'); node.removeStyle('underlay-opacity underlay-padding');
      if (k === 'critical') node.addClass('halo-critical'); else if (k === 'warning') node.addClass('halo-warning'); if (v.pct != null && v.pct >= 95) node.addClass('halo-full');
    });
    pulseNodes = REDUCED ? null : cy.nodes('.halo-full');
  }
  function buildFlowLines() {   // ข้อ 5: เส้นประสว่างวิ่งบนคลองหลัก
    cy.edges('.flowline').remove(); var arr = [];
    cy.edges('[type = "main"]').forEach(function (e) { var d = e.data(), nd = { id: 'fl-' + d.id, source: d.source, target: d.target, label: '', type: 'flow' }; ['engineStraight', 'engineBend', 'segDist', 'segWeight'].forEach(function (k) { if (d[k] !== undefined) nd[k] = d[k]; }); arr.push({ group: 'edges', data: nd, classes: 'flowline' + (flowOn ? '' : ' flowoff') }); });
    flowEdges = arr.length ? cy.add(arr) : null;
    var ps = NODES.map(function (n) { return view(n).pct; }).filter(function (x) { return x != null; }), avg = ps.length ? ps.reduce(function (a, b) { return a + b; }, 0) / ps.length : 60;
    flowSpeed = 26 + 54 * Math.min(1.2, Math.max(0.2, avg / 100));   // น้ำในอ่างเฉลี่ยมาก → เส้นประไหลเร็วขึ้น (เชิงภาพ ไม่ใช่อัตราการไหลจริง)
  }
  function tick(ts) {
    requestAnimationFrame(tick); if (!cy || !inView || document.hidden || REDUCED || ts - lastT < 40) return; var dt = Math.min(0.1, (ts - lastT) / 1000); lastT = ts;
    if (flowOn && flowEdges && flowEdges.length) { flowOff -= flowSpeed * dt; flowEdges.style('line-dash-offset', flowOff); }
    if (pulseNodes && pulseNodes.length) { var ph = (ts % 2200) / 2200; pulseNodes.style({ 'underlay-opacity': 0.36 * (1 - ph), 'underlay-padding': 7 + 12 * ph }); }
  }
  /* ---- ข้อ 8: แถบเวลา ---- */
  function buildDates() { var m = {}; NODES.forEach(function (n) { ((S[n.id] || {}).hist || []).forEach(function (h) { m[h.iso] = 1; }); }); dates = Object.keys(m).sort().slice(-120); }
  function scrubLabel() {
    var el = frame.querySelector('#wd-sd'), lv = frame.querySelector('[data-a="live"]'); if (el) { el.textContent = scrubIso ? '📅 ' + fmtDate(scrubIso) : T('ปัจจุบัน', 'Now'); el.style.color = scrubIso ? '#c2410c' : C.navy; } if (lv) lv.style.display = scrubIso ? '' : 'none';
  }
  function setScrub(i) {
    var last = dates.length - 1; i = Math.max(0, Math.min(last, i)); scrubIso = i >= last ? null : dates[i]; var rg = frame.querySelector('#wd-rg'); if (rg) rg.value = i; scrubLabel(); cyLabels(); if (sel) paintDet();
  }
  function stopPlay() { if (playT) { clearInterval(playT); playT = null; } var b = frame.querySelector('[data-a="play"]'); if (b) b.textContent = '▶'; }
  function togglePlay() {
    if (playT) { stopPlay(); return; } var last = dates.length - 1, i = scrubIso ? dates.indexOf(scrubIso) : last; if (i >= last - 1) i = Math.max(0, last - 30); setScrub(i);
    var b = frame.querySelector('[data-a="play"]'); if (b) b.textContent = '⏸';
    playT = setInterval(function () { var cur = scrubIso ? dates.indexOf(scrubIso) : last; if (cur >= last) { stopPlay(); return; } setScrub(cur + 1); if (cur + 1 >= last) stopPlay(); }, 330);
  }
  function contourBg() {   // ข้อ 4: ลายเส้นชั้นความสูงจาง ๆ (ไม่มีไฟล์ภาพ สร้างจากโค้ด)
    var Wt = 900, Ht = 560, p = [], i, x;
    for (i = 0; i < 11; i++) { var y0 = 20 + i * 52, a = 12 + (i % 4) * 7, m1 = 1 + (i % 2), m2 = 2 + (i % 3), ph = i * 0.9, d = ''; for (x = 0; x <= Wt; x += 15) { var y = y0 + a * Math.sin(2 * Math.PI * (x / Wt) * m1 + ph) + a * 0.45 * Math.sin(2 * Math.PI * (x / Wt) * m2 + ph * 1.7); d += (x ? 'L' : 'M') + x + ' ' + y.toFixed(1); } p.push('<path d="' + d + '"/>'); }
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + Wt + '" height="' + Ht + '" viewBox="0 0 ' + Wt + ' ' + Ht + '"><g fill="none" stroke="#93bfe6" stroke-opacity=".13" stroke-width="1" stroke-linejoin="round">' + p.join('') + '</g></svg>';
    return 'url("data:image/svg+xml,' + encodeURIComponent(svg) + '"), radial-gradient(900px 500px at 15% 0%, #ffffff 0%, rgba(255,255,255,0) 70%), linear-gradient(160deg, #f4faff 0%, #e6f1fa 55%, #f1f6ec 100%)';
  }
  function panel(html) { var p = frame.querySelector('.wd-pn'); if (p) p.remove(); if (html) { var d = document.createElement('div'); d.className = 'wd-ov wd-pn'; d.innerHTML = html; frame.appendChild(d); var x = d.querySelector('.x'); if (x) x.onclick = function () { if (MODE === 'cy') clearSel(); else d.remove(); }; } }
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
      '<span style="color:' + C.muted + ';margin-right:2px">' + T('เส้น', 'Lines') + '</span><button class="wd-sq" data-a="l-">−</button><span id="wd-ls" style="min-width:26px;text-align:center">' + lineScale.toFixed(1) + '×</span><button class="wd-sq" data-a="l+">+</button><div class="wd-sep"></div>' +
      '<button class="wd-bw" data-a="fit" title="' + T('จัดกึ่งกลางผังน้ำใหม่', 'Re-center') + '">⤢ ' + T('จัดกึ่งกลาง', 'Fit') + '</button><div class="wd-sep"></div><button class="wd-bw" data-a="fs" id="wd-fsb">⤢ ' + T('เต็มจอ', 'Fullscreen') + '</button><div class="wd-sep"></div>' +
      '<button class="wd-bw wd-on" data-a="flow" id="wd-flow">💧 ' + T('น้ำไหล: เปิด', 'Flow: on') + '</button></div>';
    var li = function (shape, label) { return '<div><span class="wd-li">' + shape + '</span><span style="color:#334155">' + label + '</span></div>'; };
    var leg2 = '<div class="wd-ov wd-leg2">' + li('<i style="width:16px;height:2px;background:#4da6ff;display:block"></i>', T('แม่น้ำ/คลอง', 'River/canal')) + li('<i style="width:10px;height:10px;background:#000;transform:rotate(45deg);display:block"></i>', T('ปตร.', 'Gate')) +
      li('<i style="width:12px;height:11px;background:#000;clip-path:polygon(50% 0,100% 100%,0 100%);display:block"></i>', T('อ่างเก็บน้ำ', 'Reservoir')) + li('<i style="width:14px;height:5px;background:#000;display:block"></i>', T('ฝาย', 'Weir')) +
      li('<i style="width:10px;height:10px;border-radius:50%;border:2.5px solid #000;background:#fff;display:block"></i>', T('โทรมาตร', 'Telemetry')) + li('<i style="width:10px;height:10px;border-radius:50%;border:1.5px solid #000;background:#fff;font-size:7px;font-weight:700;display:flex;align-items:center;justify-content:center;font-style:normal">P</i>', T('ระบบสูบน้ำ', 'Pump')) + li('<span style="font-size:12px">☁</span>', T('รับน้ำจากฝนเท่านั้น', 'Rain-fed only')) + li('<i style="width:14px;height:9px;background:#bfe0ff;border:1.5px dashed #0b4a99;border-radius:2px;display:block"></i>', T('กว๊านพะเยา', 'Kwan Phayao')) + '</div>';
    frame.style.height = FH; frame.style.background = contourBg(); frame.style.backgroundSize = '900px 560px, auto, auto';
    frame.innerHTML = '<div id="wd-cyc" style="width:100%;height:100%"></div><div class="wd-msg" id="wd-msg">⏳ ' + T('กำลังโหลดผังน้ำ…', 'Loading diagram…') + '</div>' + tb + leg2 + legendHtml();
    sec.style.display = '';
    var started = false;
    function start() {
      if (started) return; started = true;
      loadCy(function (ok) {
        if (!ok) { initSvgMode(); return; }
        var els = net.nodes.map(function (r) { return { data: { id: r.node_key, label: r.label || '', type: r.node_type || undefined, rotation: r.rotation || 0, dir: r.dir || 'h', sourceRef: r.source_ref || '', status: r.status || null }, position: { x: r.pos_x, y: r.pos_y } }; })
          .concat((net.edges || []).map(function (r) { var d = { id: r.edge_key, source: r.source_node_key, target: r.target_node_key, label: r.label || '', type: r.edge_type || undefined }; if (r.engine_straight) d.engineStraight = true; if (r.engine_bend) { d.engineBend = true; d.segDist = r.seg_dist; d.segWeight = r.seg_weight; } return { data: d }; }));
        (function () {   // แถบ "กว๊านพะเยา" ปลายทางของน้ำทุกสาย — วางถัดจากขอบขวาสุดของผัง (ใช้สไตล์แหล่งน้ำมาตรฐาน)
          var xs = net.nodes.map(function (r) { return r.pos_x; }), ys = net.nodes.map(function (r) { return r.pos_y; }); if (!xs.length) return;
          var x1 = Math.max.apply(null, xs), y1 = Math.min.apply(null, ys), y2 = Math.max.apply(null, ys), w = Math.max(90, (x1 - Math.min.apply(null, xs)) * 0.06), h = y2 - y1 + 80;
          els.unshift({ data: { id: '__kwan', label: T('กว๊านพะเยา\n(ปลายทางของน้ำทุกสาย)', 'Kwan Phayao\n(final destination of all streams)'), type: 'kwan_band', w: w, h: h, rotation: 0 }, position: { x: x1 + 40 + w / 2, y: (y1 + y2) / 2 }, selectable: false, grabbable: false });
        })();
        (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () { requestAnimationFrame(function () {
          var c = frame.querySelector('#wd-cyc'); if (!c) return;
          cy = window.cytoscape({ container: c, elements: els, layout: { name: 'preset' }, style: cyStyle(), userZoomingEnabled: true, userPanningEnabled: true, boxSelectionEnabled: false, autoungrabify: true });
          cy.on('tap', 'node', function (evt) {
            var t = evt.target, ref = t.data('sourceRef');
            if (ref) { var n = NODES.filter(function (x) { return x.ref === ref; })[0]; panel(''); if (n) pick(n.id); return; }
            var ty = t.data('type'), lab = t.data('origLabel') || t.data('label') || ty;
            sel = null; cyHighlight();
            if (ty === 'gate' || ty === 'weir' || ty === 'pump') structPanel('infra', lab, ty, t.data('status')); else if (ty === 'telemetry') structPanel('tele', lab, ty, null, lab);
          });
          cy.on('tap', function (e) { if (e.target === cy) clearSel(); });
          cy.on('pan zoom', function () { userMoved = true; });
          cy.on('viewport', function () { var p = cy.pan(); frame.style.backgroundPosition = (p.x * 0.2).toFixed(0) + 'px ' + (p.y * 0.2).toFixed(0) + 'px, 0 0, 0 0'; });
          var comps = cy.elements().components(), main = cy.elements();
          if (comps.length > 1) { var big = comps.reduce(function (a, b) { return a.length >= b.length ? a : b; }); main = big.union(cy.elements().filter(function (e) { return e.isEdge() || e.data('sourceRef') || (e.data('label') && String(e.data('label')).trim()); })); }
          fitTarget = main; cyRefit(); setTimeout(function () { if (cy && !userMoved) cyRefit(); }, 200);
          var m = frame.querySelector('#wd-msg'); if (m) m.remove();
          buildFlowLines(); applyLines(); cyLabels(); cyHighlight(); requestAnimationFrame(tick);
          if (window.ResizeObserver) new ResizeObserver(function () { if (cy && !userMoved) cyRefit(); }).observe(c);
          if ('IntersectionObserver' in window) new IntersectionObserver(function (es) { inView = es.some(function (e) { return e.isIntersecting; }); }, { threshold: 0.05 }).observe(frame);
        }); });
      });
    }
    if ('IntersectionObserver' in window) { var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { io.disconnect(); start(); } }, { rootMargin: '400px' }); io.observe(sec); } else start();
    function setOn(b, on) { b.classList.toggle('wd-on', !!on); }
    frame.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('[data-a]'); if (!b || !cy) return; var a = b.getAttribute('data-a'), fsE = frame.querySelector('#wd-fs');
      if (a === 'f-' || a === 'f+') { fontSize = Math.max(6, Math.min(24, fontSize + (a === 'f+' ? 1 : -1))); fsE.textContent = fontSize; cy.style().selector('node').style({ 'font-size': fontSize + 'px' }).selector('node[type = "kwan_band"]').style({ 'font-size': Math.round(fontSize * 2.4) + 'px' }).selector('edge').style({ 'font-size': Math.max(fontSize - 2, 8) + 'px' }).update(); }
      else if (a === 'l-' || a === 'l+') { lineScale = Math.max(0.6, Math.min(5, Math.round((lineScale + (a === 'l+' ? 0.5 : -0.5)) * 10) / 10)); frame.querySelector('#wd-ls').textContent = lineScale.toFixed(1) + '×'; applyLines(); }
      else if (a === 'fit') { userMoved = false; cyRefit(); }
      else if (a === 'fs') { if (document.fullscreenElement) document.exitFullscreen && document.exitFullscreen(); else frame.requestFullscreen && frame.requestFullscreen(); }
      else if (a === 'flow') { flowOn = !flowOn; b.textContent = '💧 ' + (flowOn ? T('น้ำไหล: เปิด', 'Flow: on') : T('น้ำไหล: ปิด', 'Flow: off')); setOn(b, flowOn); if (flowEdges) { flowEdges.toggleClass('flowoff', !flowOn); } }
      else if (a === 'play') togglePlay();
      else if (a === 'live') { stopPlay(); setScrub(dates.length - 1); }
    });
    frame.addEventListener('input', function (e) { if (e.target && e.target.id === 'wd-rg') { stopPlay(); setScrub(+e.target.value); } });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && cy && sel) clearSel(); });
    document.addEventListener('fullscreenchange', function () { var on = document.fullscreenElement === frame; frame.style.setProperty('--wdz', String(Math.round(Math.max(1.4, Math.min(2.4, window.innerWidth / 1000)) * 10) / 10)); frame.style.height = on ? '100vh' : FH; var b = frame.querySelector('#wd-fsb'); if (b) b.textContent = '⤢ ' + (on ? T('ออกเต็มจอ', 'Exit fullscreen') : T('เต็มจอ', 'Fullscreen')); requestAnimationFrame(cyRefit); });
    buildData(); buildDates();
    if (dates.length > 1) {   // แถบเวลา: ต้องมีประวัติรายวันอย่างน้อย 2 วัน
      frame.insertAdjacentHTML('beforeend', '<div class="wd-ov wd-scrub"><button class="wd-sq" data-a="play" title="' + T('เล่นย้อนหลัง', 'Play history') + '">▶</button><input id="wd-rg" type="range" min="0" max="' + (dates.length - 1) + '" value="' + (dates.length - 1) + '" step="1" aria-label="' + T('เลื่อนดูย้อนหลัง', 'Scrub history') + '"><span id="wd-sd" style="min-width:92px;font-weight:700;color:' + C.navy + '"></span><button class="wd-bw" data-a="live" style="display:none">' + T('กลับปัจจุบัน', 'Back to now') + '</button></div>');
      scrubLabel();
    }
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
