/* freshness-kit.js — แถบสถานะ "ข้อมูลล่าสุดเมื่อ…" ใต้หัวเว็บทุกหน้า
   อ่าน assets/data/monitoring.json (meta.updated = เวลาไทย) และ flood_latest.json (generated_at = UTC)
   สีเขียว = สดตามปกติ · เหลือง = ช้ากว่าปกติ · แดง = เก่ามาก (ควรตรวจระบบ) — ไม่มีข้อมูลก็ซ่อนแถบ
   ถอยกลับ: ลบ <script src="…/freshness-kit.js"> ออกจากหน้า (หรือจาก KITS ใน preview_server.py) */
(function () {
  if (window.top !== window) return;                 // ไม่แสดงใน iframe/embed
  var head = document.querySelector('header.site-header'); if (!head) return;
  var css = document.createElement('style');
  css.textContent = [
    '.fk-bar{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 18px;padding:5px 16px;font-size:11.5px;color:var(--text-500);border-bottom:1px solid var(--border);background:rgba(var(--t5-rgb),.05)}',
    '.fk-bar span{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}',
    '.fk-bar i{width:7px;height:7px;border-radius:50%;background:var(--c,#999);box-shadow:0 0 0 0 var(--c,#999)}',
    '.fk-bar .ok i{--c:#2fa36b;animation:fk-ping 2.4s infinite}.fk-bar .warn i{--c:#e0a94f}.fk-bar .bad i{--c:#e05252}',
    '.fk-bar b{color:var(--text-300);font-weight:600}',
    '.fk-bar .bad b{color:var(--red-txt,#b3362a)}.fk-bar .warn b{color:var(--orange-txt,#b25a1e)}',
    '@keyframes fk-ping{80%,100%{box-shadow:0 0 0 7px transparent}}',
    'html.uk-reduce .fk-bar .ok i{animation:none}',
    '@media(max-width:640px){.fk-bar{font-size:10.5px;gap:3px 12px;padding:4px 10px}}'
  ].join('');
  document.head.appendChild(css);
  var bar = document.createElement('div'); bar.className = 'fk-bar'; bar.hidden = true;
  head.parentNode.insertBefore(bar, head.nextSibling);

  var T = { live: null, daily: null };
  function rel(ms) {
    var m = Math.max(0, Math.round(ms / 60000));
    if (m < 2) return 'เมื่อสักครู่';
    if (m < 60) return m + ' นาทีที่แล้ว';
    var h = Math.round(m / 60); if (h < 36) return h + ' ชม.ที่แล้ว';
    return Math.round(h / 24) + ' วันที่แล้ว';
  }
  function hhmm(d) { return d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Bangkok' }); }
  function dmy(d) { return d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short', timeZone: 'Asia/Bangkok' }); }
  function cls(ageH, okH, warnH) { return ageH <= okH ? 'ok' : ageH <= warnH ? 'warn' : 'bad'; }
  function draw() {
    var now = Date.now(), out = [];
    if (T.live) { var a = (now - T.live) / 36e5, d = new Date(T.live); out.push('<span class="' + cls(a, 2, 12) + '" title="เวลาที่ระบบอัปเดตข้อมูลสถานีล่าสุด"><i></i>สถานการณ์น้ำสด <b>' + hhmm(d) + ' น.</b> (' + rel(now - T.live) + ')</span>'); }
    if (T.daily) { var a2 = (now - T.daily) / 36e5, d2 = new Date(T.daily); out.push('<span class="' + cls(a2, 30, 54) + '" title="เวลาที่รันพยากรณ์ 7 วันล่าสุด"><i></i>พยากรณ์รายวัน <b>' + dmy(d2) + ' ' + hhmm(d2) + ' น.</b> (' + rel(now - T.daily) + ')</span>'); }
    bar.hidden = !out.length; bar.innerHTML = out.join('');
  }
  function load() {
    fetch('assets/data/monitoring.json', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (j) {
      var u = j && j.meta && j.meta.updated; if (u) { var t = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(u) ? u : u + '+07:00'); if (!isNaN(t)) T.live = t; } draw();
    }).catch(function () {});
    fetch('assets/data/flood_latest.json', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (j) {
      var g = j && j.generated_at; if (g) { var t = Date.parse(String(g).replace(' ', 'T') + (/[zZ]|[+-]\d\d:?\d\d$/.test(g) ? '' : 'Z')); if (!isNaN(t)) T.daily = t; } draw();
    }).catch(function () {});
  }
  load(); setInterval(draw, 60000); setInterval(load, 5 * 60000);
})();
