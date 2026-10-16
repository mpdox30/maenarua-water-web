/* flood-hero-kit.js — หน้า flood-forecast: ปรับส่วนบนสุด (แถบธงเตือน + หัวหน้า + KPI 4 ใบ) ให้สวยและอ่านง่ายขึ้น
   ไม่แก้หน้าเดิม: อ่านค่าที่หน้าเดิมเติมไว้ + ดึง flood_latest.json (cache เดียวกัน) มาวาดกราฟเล็ก
   ถอยกลับ: ลบ <script src="/__uikit/flood-hero-kit.js"> ออกจาก preview_server.py */
(function () {
  function thaiDT(s){if(!s)return s;var t=Date.parse(String(s).replace(' ','T')+(/[zZ]|[+-]\d\d:?\d\d$/.test(s)?'':'Z'));if(isNaN(t))return s;var i=new Date(t+7*36e5).toISOString();return i.slice(0,10)+' '+i.slice(11,16);} /* generated_at เป็น UTC -> แสดงเวลาไทย */
  var kpis = document.querySelectorAll('.kpi-grid .kpi');
  if (!kpis.length) return;
  var css = document.createElement('style');
  css.textContent = [
    /* หัวหน้า */
    '.page-hero{position:relative;overflow:hidden}',
    '.page-hero::before{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(60% 90% at 88% 0%,rgba(var(--t4-rgb),.2),transparent 62%),radial-gradient(40% 60% at 4% 100%,rgba(var(--a4-rgb),.1),transparent 70%)}',
    '.page-hero .wrap{position:relative;z-index:1}',
    '.fh-rip{position:absolute;right:max(24px,calc(50% - 600px));top:12px;width:260px;height:260px;pointer-events:none;z-index:0;opacity:.9}',
    '.fh-rip i{position:absolute;inset:0;border-radius:50%;border:1.5px solid rgba(var(--t5-rgb),.38);animation:fh-rip 5.4s cubic-bezier(.2,.6,.3,1) infinite}',
    '.fh-rip i:nth-child(2){animation-delay:1.8s}.fh-rip i:nth-child(3){animation-delay:3.6s}',
    '@keyframes fh-rip{0%{transform:scale(.12);opacity:.9}100%{transform:scale(1);opacity:0}}',
    '.page-hero h1{background:linear-gradient(95deg,var(--text-100) 35%,var(--teal-500,#2a9d8f) 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;font-size:34px;line-height:1.45;padding:.2em 0 .1em;margin:0 0 6px}',
    '.page-hero .wrap>.eyebrow{display:none}',
    '.fh-pill.fh-tag{background:linear-gradient(135deg,var(--teal-500),var(--teal-400));color:var(--accent-ink,#fff);border-color:transparent;font-weight:600;letter-spacing:.03em}',
    '.fh-meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}',
    '.fh-pill{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--text-300);padding:5px 12px;border-radius:999px;border:1px solid var(--border);background:rgba(255,255,255,.72);backdrop-filter:blur(6px)}',
    'html:not([data-uk-mode="light"]) .fh-pill,html:not([data-uk-mode="light"]) .fh-msgs .ch span{background:rgba(255,255,255,.07)}',
    '.fh-pill b{font-family:"Space Grotesk",sans-serif;color:var(--text-100);font-weight:600}',
    '.fh-pill i{width:7px;height:7px;border-radius:50%;background:var(--teal-500,#2a9d8f);box-shadow:0 0 0 0 rgba(var(--t5-rgb),.6);animation:fh-ping 2.2s infinite}',
    '@keyframes fh-ping{80%,100%{box-shadow:0 0 0 8px rgba(var(--t5-rgb),0)}}',
    /* แถบธง */
    '.flag-banner-inner{align-items:flex-start}',
    '.flag-badge{box-shadow:0 10px 24px -12px currentColor,0 0 0 4px rgba(var(--w-rgb),.35)}',
    '.fh-msgs{flex:1 1 360px;min-width:0;display:flex;flex-direction:column;gap:7px}',
    '.fh-msgs .hd{font-size:15px;font-weight:600;color:var(--text-100);line-height:1.45}',
    '.fh-msgs .ch{display:flex;flex-wrap:wrap;gap:6px}',
    '.fh-msgs .ch span{font-size:11.8px;line-height:1.4;padding:3px 11px;border-radius:999px;color:var(--text-300);background:rgba(255,255,255,.72);border:1px solid var(--border)}',
    '.fh-msgs .ch span.hot{color:var(--red-txt,#a3321f);border-color:rgba(224,82,82,.45);background:rgba(224,82,82,.1)}',
    '.fh-msgs .ch span.mid{color:var(--orange-txt,#8a5a12);border-color:rgba(224,169,79,.5);background:rgba(224,169,79,.12)}',
    /* KPI */
    '.kpi-grid .kpi{position:relative;overflow:hidden;padding:20px 22px 18px;transition:transform .35s var(--uk-ease,ease),box-shadow .35s}',
    '.kpi-grid .kpi::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:linear-gradient(90deg,rgb(var(--ac)),rgba(var(--ac),.25))}',
    '.kpi-grid .kpi::after{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(90% 70% at 100% 0%,rgba(var(--ac),.13),transparent 65%)}',
    '.kpi-grid .kpi>*{position:relative;z-index:1}',
    '.kpi-grid .kpi:hover{transform:translateY(-4px);box-shadow:0 22px 40px -26px rgba(var(--ac),.8)}',
    '.kpi .label{display:flex;align-items:center;gap:9px;font-weight:500}',
    '.fh-ic{flex:none;width:30px;height:30px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;color:rgb(var(--ac));background:rgba(var(--ac),.14)}',
    '.fh-ic svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}',
    '.kpi .value{font-size:32px}',
    '.kpi .sub.up,.kpi .sub.down{display:inline-flex;align-items:center;margin-top:8px;padding:2px 10px;border-radius:999px;font-size:11.5px;font-weight:600}',
    '.kpi .sub.up{color:var(--red-txt,#a3321f);background:rgba(224,82,82,.12)}.kpi .sub.down{color:var(--teal-500,#17776a);background:rgba(42,157,143,.14)}',
    '.fh-sp{margin-top:12px;width:100%;height:76px;display:block;overflow:visible}',
    '.fh-sp .ln{fill:none;stroke:rgb(var(--ac));stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:1;stroke-dashoffset:1;animation:fh-draw 1.6s .2s cubic-bezier(.16,1,.3,1) forwards}',
    '.fh-sp .fc{fill:none;stroke:rgb(var(--ac));stroke-width:2;stroke-dasharray:4 4;opacity:.85}',
    '.fh-sp .bd{fill:rgba(var(--ac),.16)}','.fh-sp .gp{stroke:rgb(var(--ac));stroke-width:1.8;stroke-dasharray:2 4;opacity:.6}',
    '.fh-sp .bk{stroke:#e05252;stroke-width:1;stroke-dasharray:3 3;opacity:.85}',
    '.fh-sp text{font:10px "IBM Plex Sans Thai",sans-serif;fill:var(--text-500)}',
    '@keyframes fh-draw{to{stroke-dashoffset:0}}',
    '.fh-sp-l{display:flex;justify-content:space-between;font-size:10.5px;color:var(--text-600);margin-top:2px}',
    '.kpi-banks .bank-row{flex-wrap:wrap;row-gap:3px}',
    '.fh-bb{flex:1 0 100%;height:4px;border-radius:4px;background:rgba(var(--bd-rgb),.25);overflow:hidden}',
    '.fh-bb i{display:block;height:100%;border-radius:4px;transform-origin:left;animation:fh-grow 1.1s .15s cubic-bezier(.16,1,.3,1) both}',
    '@keyframes fh-grow{from{transform:scaleX(0)}}',
    '.fh-bars{display:grid;gap:9px;margin-top:14px}',
    '.fh-br{display:grid;grid-template-columns:44px 1fr 38px;align-items:center;gap:8px;font-size:11.5px;color:var(--text-500)}',
    '.fh-br em{font-style:normal;font-family:"Space Grotesk",sans-serif;font-weight:600;color:var(--text-100);text-align:right}',
    '.fh-br .tr{height:8px;border-radius:8px;background:rgba(var(--bd-rgb),.25);overflow:hidden}',
    '.fh-br .tr i{display:block;height:100%;border-radius:8px;background:linear-gradient(90deg,rgba(var(--ac),.55),rgb(var(--ac)));animation:fh-grow 1.2s .2s cubic-bezier(.16,1,.3,1) both;transform-origin:left}',
    '.fh-cols{display:grid;grid-template-columns:repeat(7,1fr);gap:5px;align-items:end;height:64px;margin-top:14px}',
    '.fh-cols div{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;gap:4px;font-size:10px;color:var(--text-600)}',
    '.fh-cols i{display:block;width:100%;min-height:3px;border-radius:5px 5px 2px 2px;background:linear-gradient(180deg,rgb(var(--ac)),rgba(var(--ac),.4));transform-origin:bottom;animation:fh-up 1s .2s cubic-bezier(.16,1,.3,1) both}',
    '@keyframes fh-up{from{transform:scaleY(0)}}',
    'html.uk-reduce .fh-rip i,html.uk-reduce .fh-pill i,html.uk-reduce .fh-sp .ln{animation:none}html.uk-reduce .fh-sp .ln{stroke-dashoffset:0}',
    '@media(max-width:640px){.fh-rip{display:none}.page-hero h1{font-size:26px}}'
  ].join('');
  document.head.appendChild(css);

  var AC = ['42,157,143', '224,82,82', '58,134,200', '157,127,224'];
  var IC = [
    '<path d="M3 15c2.2-2.4 4.4-2.4 6.6 0s4.4 2.4 6.6 0 4.4-2.4 6.6 0"/><path d="M3 9.5c2.2-2.4 4.4-2.4 6.6 0s4.4 2.4 6.6 0 4.4-2.4 6.6 0"/><path d="M12 3v3"/>',
    '<path d="M4 20h16"/><path d="M6 20V9l6-5 6 5v11"/><path d="M9 14h6"/>',
    '<path d="M7 16.5A4.5 4.5 0 1 1 8 7.6 5.5 5.5 0 0 1 18.6 9 3.8 3.8 0 0 1 17.5 16.5"/><path d="M9 19l-1 2M13 19l-1 2M17 19l-1 2"/>',
    '<path d="M12 3s6 6.6 6 11a6 6 0 0 1-12 0c0-4.4 6-11 6-11z"/><path d="M9.5 15a2.6 2.6 0 0 0 2.5 2"/>'
  ];
  kpis.forEach(function (k, i) {
    k.style.setProperty('--ac', AC[i % 4]);
    var lb = k.querySelector('.label');
    if (lb && !lb.querySelector('.fh-ic')) { var s = document.createElement('span'); s.className = 'fh-ic'; s.innerHTML = '<svg viewBox="0 0 24 24">' + IC[i % 4] + '</svg>'; lb.insertBefore(s, lb.firstChild); }
  });

  /* ระลอกน้ำตกแต่งหัวหน้า */
  var hero = document.querySelector('.page-hero');
  if (hero) { var rp = document.createElement('div'); rp.className = 'fh-rip'; rp.innerHTML = '<i></i><i></i><i></i>'; hero.insertBefore(rp, hero.firstChild); }

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function num(t) { var m = String(t).match(/-?[\d,]*\.?\d+/); return m ? parseFloat(m[0].replace(/,/g, '')) : NaN; }

  function countUp(el) {
    var n = el.firstChild; if (!n || n.nodeType !== 3) return;
    var txt = n.nodeValue, v = num(txt); if (isNaN(v)) return;
    var dec = (txt.split('.')[1] || '').replace(/\D/g, '').length, t0 = performance.now(), D = 1100;
    setTimeout(function () { n.nodeValue = txt; }, D + 400); /* แท็บพื้นหลัง rAF ไม่ทำงาน → บังคับจบด้วยค่าจริง */
    (function f(t) {
      var p = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - p, 3);
      n.nodeValue = (v * e).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
      if (p < 1) requestAnimationFrame(f); else n.nodeValue = txt;
    })(t0);
  }

  function banner() {
    var msg = document.getElementById('flagMsg'); if (!msg || msg.dataset.fh) return;
    var parts = msg.textContent.split('|').map(function (x) { return x.trim(); }).filter(Boolean);
    if (!parts.length || /กำลังโหลด/.test(parts[0])) return;
    msg.dataset.fh = '1';
    var box = document.createElement('div'); box.className = 'fh-msgs';
    box.innerHTML = '<div class="hd">' + esc(parts[0]) + '</div>' + (parts.length > 1 ? '<div class="ch">' + parts.slice(1).map(function (p) {
      var c = /เหนือตลิ่ง|ล้น/.test(p) ? 'hot' : /แตะตลิ่ง|P90/.test(p) ? 'mid' : '';
      return '<span class="' + c + '">' + esc(p) + '</span>';
    }).join('') + '</div>' : '');
    msg.style.display = 'none'; msg.parentNode.insertBefore(box, msg.nextSibling);
  }

  function heroMeta(d) {
    var wrap = document.querySelector('.page-hero .wrap'), lead = wrap && wrap.querySelector('.lead'); if (!lead || wrap.querySelector('.fh-meta')) return;
    var m = document.createElement('div'); m.className = 'fh-meta';
    m.innerHTML = '<span class="fh-pill fh-tag">Flood Forecast · WMB Model</span><span class="fh-pill"><i></i>อัปเดต <b>' + esc(thaiDT(d.generated_at) + ' น.') + '</b></span><span class="fh-pill">วันฐานพยากรณ์ <b>' + esc(d.base_date) + '</b></span><span class="fh-pill">พยากรณ์ล่วงหน้า <b>7</b> วัน</span><span class="fh-pill">ตรวจพิสูจน์ด้วย <b>3</b> ชุดข้อมูลอิสระ</span>';
    lead.parentNode.insertBefore(m, lead.nextSibling);
  }

  function spark(d) {
    var card = kpis[0]; if (card.querySelector('.fh-sp')) return;
    var obs = (d.kwan_observed_30d || []).map(function (o) { return { t: Date.parse(o.date), y: o.level }; }),
      fc = (d.kwan_forecast || []).map(function (o) { return { t: Date.parse(o.date), y: o.level, lo: o.p10, hi: o.p90 }; });
    if (obs.length < 2 && fc.length < 2) return;
    var all = obs.concat(fc), t0 = Math.min.apply(0, all.map(function (p) { return p.t; })), t1 = Math.max.apply(0, all.map(function (p) { return p.t; }));
    var ys = obs.map(function (p) { return p.y; }).concat(fc.map(function (p) { return p.lo != null ? p.lo : p.y; }), fc.map(function (p) { return p.hi != null ? p.hi : p.y; }));
    var lo = Math.min.apply(0, ys), hi = Math.max.apply(0, ys), bank = d.banks && d.banks.Mae_Main1;
    if (bank != null && bank > lo - .5 && bank < hi + .5) { lo = Math.min(lo, bank); hi = Math.max(hi, bank); } else bank = null;
    var pad = (hi - lo) * .12 || .05; lo -= pad; hi += pad;
    var W = 260, H = 76, X = function (t) { return ((t - t0) / (t1 - t0 || 1)) * W; }, Y = function (v) { return H - ((v - lo) / (hi - lo)) * H; };
    function path(a) { return a.map(function (p, i) { return (i ? 'L' : 'M') + X(p.t).toFixed(1) + ' ' + Y(p.y).toFixed(1); }).join(''); }
    var bandPts = fc.filter(function (p) { return p.lo != null && p.hi != null; }), band = '';
    if (bandPts.length > 1) band = '<path class="bd" d="' + bandPts.map(function (p, i) { return (i ? 'L' : 'M') + X(p.t).toFixed(1) + ' ' + Y(p.hi).toFixed(1); }).join('') + bandPts.slice().reverse().map(function (p) { return 'L' + X(p.t).toFixed(1) + ' ' + Y(p.lo).toFixed(1); }).join('') + 'Z"/>';
    var join = obs.length && fc.length ? [obs[obs.length - 1]].concat(fc) : fc;
    var svg = '<svg class="fh-sp" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' + band +
      (bank != null ? '<line class="bk" x1="0" x2="' + W + '" y1="' + Y(bank).toFixed(1) + '" y2="' + Y(bank).toFixed(1) + '"/>' : '') +
      (obs.length > 1 ? '<path class="ln" pathLength="1" d="' + obs.map(function (p, i) { return (i && p.t - obs[i - 1].t > 1.5 * 864e5 ? 'M' : (i ? 'L' : 'M')) + X(p.t).toFixed(1) + ' ' + Y(p.y).toFixed(1); }).join('') + '"/>' + obs.map(function (p, i) { return i && p.t - obs[i - 1].t > 1.5 * 864e5 ? '<line class="gp" x1="' + X(obs[i - 1].t).toFixed(1) + '" y1="' + Y(obs[i - 1].y).toFixed(1) + '" x2="' + X(p.t).toFixed(1) + '" y2="' + Y(p.y).toFixed(1) + '"/>' : ''; }).join('') : '') +
      (join.length > 1 ? '<path class="fc" d="' + path(join) + '"/>' : '') +
      (obs.length ? '<circle cx="' + X(obs[obs.length - 1].t).toFixed(1) + '" cy="' + Y(obs[obs.length - 1].y).toFixed(1) + '" r="3.4" fill="rgb(var(--ac))" stroke="#fff" stroke-width="1.5"/>' : '') + '</svg>';
    var l = document.createElement('div'); l.innerHTML = svg + '<div class="fh-sp-l"><span>ย้อนหลัง 30 วัน</span><span>' + (bank != null ? '<span style="color:#d34a4a">┄ ตลิ่งห้วยแม่นาเรือ</span> · ' : '') + 'พยากรณ์ 7 วัน</span></div>';
    while (l.firstChild) card.appendChild(l.firstChild);
  }

  function banks() {
    var rows = document.querySelectorAll('#bankList .bank-row');
    [].forEach.call(rows, function (r) {
      if (r.querySelector('.fh-bb')) return;
      var bv = r.querySelector('.bval'); if (!bv) return;
      var v = num(bv.textContent.replace('+', '')), neg = /-/.test(bv.textContent) || v < 0;
      var g = Math.abs(v), pct = Math.max(6, Math.min(100, 100 - (Math.min(g, 2) / 2) * 94));
      /* แถบยาว = ใกล้/เกินตลิ่ง (เสี่ยงกว่า) */
      var b = document.createElement('span'); b.className = 'fh-bb'; b.innerHTML = '<i style="width:' + pct.toFixed(0) + '%;background:' + (neg ? '#e05252' : g < .6 ? '#e0a94f' : '#2a9d8f') + '"></i>';
      r.appendChild(b);
    });
  }

  function rain(d) {
    var card = kpis[2]; if (card.querySelector('.fh-bars') || !d.rain_7d) return;
    var mx = Math.max(100, d.rain_7d.mtn, d.rain_7d.low);
    var row = function (n, v) { return '<div class="fh-br"><span>' + n + '</span><div class="tr"><i style="width:' + Math.min(100, v / mx * 100).toFixed(0) + '%"></i></div><em>' + Math.round(v) + '</em></div>'; };
    var b = document.createElement('div'); b.className = 'fh-bars'; b.innerHTML = row('ภูเขา', d.rain_7d.mtn) + row('ที่ราบ', d.rain_7d.low);
    card.appendChild(b);
  }

  function overflow(d) {
    var card = kpis[3]; if (card.querySelector('.fh-cols')) return;
    var by = {}; (d.overflow_forecast || []).forEach(function (o) { by[o.date] = (by[o.date] || 0) + (o.mcm || 0); });
    var base = Date.parse(d.base_date || (d.kwan_forecast && d.kwan_forecast[0] && d.kwan_forecast[0].date)), days = [];
    var keys = (d.kwan_forecast || []).slice(0, 7).map(function (x) { return x.date; });
    if (!keys.length) keys = Object.keys(by).sort().slice(0, 7);
    keys.forEach(function (k) { days.push({ k: k, v: by[k] || 0 }); });
    if (!days.length) return;
    var mx = Math.max.apply(0, days.map(function (x) { return x.v; })) || 1;
    var c = document.createElement('div'); c.className = 'fh-cols';
    c.innerHTML = days.map(function (x) { var dd = new Date(x.k + 'T00:00:00'); return '<div title="' + esc(x.k) + ': ' + x.v.toFixed(4) + ' ล้าน ลบ.ม."><i style="height:' + (x.v ? Math.max(8, x.v / mx * 100) : 4).toFixed(0) + '%;opacity:' + (x.v ? 1 : .35) + '"></i><span>' + dd.getDate() + '</span></div>'; }).join('');
    card.appendChild(c);
  }

  function ready() { var e = document.getElementById('kpiKwan'); return e && /\d/.test(e.textContent); }
  var tries = 0, iv = setInterval(function () {
    if (!ready()) { if (++tries > 80) clearInterval(iv); return; }
    clearInterval(iv);
    banner(); banks();
    fetch('assets/data/flood_latest.json').then(function (r) { return r.json(); }).then(function (d) {
      try { heroMeta(d); spark(d); rain(d); overflow(d); } catch (e) { console.warn('flood-hero-kit', e); }
    }).catch(function () {});
    document.querySelectorAll('.kpi .value').forEach(countUp);
    new MutationObserver(function () { banks(); }).observe(document.getElementById('bankList'), { childList: true });
  }, 250);
})();
