/* reliability-kit.js — หน้า flood-forecast: ปรับส่วน "ความน่าเชื่อถือและคุณภาพข้อมูล" ให้เป็นแดชบอร์ดย่อย
   - ตัด "คำเตือนคุณภาพข้อมูล" ออก (ซ่อนการ์ด + ไม่แสดง)
   - อ่านข้อความจาก #modelInfoList ที่หน้าเดิมเติม แล้วจัดใหม่: หัวโมเดล + ชิปองค์ประกอบ, วงแหวนค่า R²/r, แถบช่วงพยากรณ์, การ์ดสมมติฐาน
   - ถอยกลับ: ลบ <script src="/__uikit/reliability-kit.js"> ออกจาก preview_server.py */
(function () {
  var list = document.getElementById('modelInfoList');
  var grid = document.querySelector('.rel-grid');
  if (!list || !grid) return;

  var css = document.createElement('style');
  css.textContent = [
    '.rel-grid{display:none!important}',
    '.rk{display:grid;gap:18px}',
    '.rk-head{position:relative;overflow:hidden;border:1px solid var(--border);border-radius:18px;padding:22px 26px;background:linear-gradient(120deg,rgba(var(--t5-rgb),.16),rgba(var(--t5-rgb),.03) 60%),var(--surface)}',
    '.rk-head::after{content:"";position:absolute;right:-60px;top:-60px;width:220px;height:220px;border-radius:50%;background:radial-gradient(circle,rgba(var(--t4-rgb),.22),transparent 68%);pointer-events:none}',
    '.rk-eye{font:600 11px/1 "Space Grotesk",sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--teal-500,#2a9d8f);margin-bottom:10px;display:flex;align-items:center;gap:8px}',
    '.rk-eye i{width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 0 0 currentColor;animation:rk-ping 2.4s infinite}',
    '@keyframes rk-ping{0%{box-shadow:0 0 0 0 rgba(var(--t5-rgb),.55)}80%,100%{box-shadow:0 0 0 9px rgba(var(--t5-rgb),0)}}',
    '.rk-title{font:600 22px/1.3 "Noto Serif Thai","Space Grotesk",serif;color:var(--text-100);margin:0 0 4px}',
    '.rk-title small{font:500 13px "IBM Plex Sans Thai",sans-serif;color:var(--text-500);margin-left:8px}',
    '.rk-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;position:relative;z-index:1}',
    '.rk-chip{display:inline-flex;align-items:center;gap:7px;padding:6px 13px;border-radius:999px;font-size:12px;color:var(--text-300);background:rgba(var(--t5-rgb),.1);border:1px solid rgba(var(--t5-rgb),.28)}',
    '.rk-chip::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--teal-500,#2a9d8f)}',
    '.rk-chip b{color:var(--text-100);font-weight:600}',
    '.rk-gauges{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:18px}',
    '.rk-g{display:flex;align-items:center;gap:16px;border:1px solid var(--border);border-radius:16px;padding:18px 20px;background:var(--surface);transition:transform .35s var(--uk-ease,ease),box-shadow .35s}',
    '.rk-g:hover{transform:translateY(-3px);box-shadow:0 18px 38px -24px rgba(var(--t4-rgb),.6)}',
    '.rk-ring{flex:none;width:84px;height:84px;position:relative}',
    '.rk-ring svg{width:100%;height:100%;transform:rotate(-90deg)}',
    '.rk-ring circle{fill:none;stroke-width:8;stroke-linecap:round}',
    '.rk-ring .bg{stroke:rgba(var(--bd-rgb),.28)}',
    '.rk-ring .fg{stroke:var(--c);stroke-dasharray:var(--len);stroke-dashoffset:var(--len);transition:stroke-dashoffset 1.4s cubic-bezier(.16,1,.3,1)}',
    '.rk-g.in .rk-ring .fg{stroke-dashoffset:var(--off)}',
    '.rk-ring span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font:600 15px "Space Grotesk",sans-serif;color:var(--text-100)}',
    '.rk-gt{min-width:0}',
    '.rk-gt .n{font-size:14px;font-weight:600;color:var(--text-100);line-height:1.35}',
    '.rk-gt .s{font-size:11.5px;color:var(--text-500);margin-top:3px;line-height:1.45}',
    '.rk-gt .q{display:inline-block;margin-top:7px;font-size:10.5px;font-weight:600;padding:2px 9px;border-radius:999px;color:var(--c);border:1px solid var(--c);background:transparent}',
    '.rk-row{display:grid;grid-template-columns:1.3fr 1fr;gap:18px}',
    '@media(max-width:820px){.rk-row{grid-template-columns:1fr}.rk-head{padding:18px}.rk-title{font-size:19px}}',
    '.rk-card{border:1px solid var(--border);border-radius:16px;padding:20px 22px;background:var(--surface)}',
    '.rk-card h4{font:600 14px "Noto Serif Thai",serif;color:var(--text-100);margin:0 0 4px}',
    '.rk-card p{margin:0;font-size:12px;color:var(--text-500);line-height:1.55}',
    '.rk-days{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin:16px 0 8px}',
    '.rk-days i{height:34px;border-radius:9px;background:rgba(var(--bd-rgb),.2);display:flex;align-items:center;justify-content:center;font:600 11px "Space Grotesk",sans-serif;color:var(--text-600);font-style:normal;transition:transform .3s}',
    '.rk-days i.on{background:linear-gradient(180deg,rgba(var(--t4-rgb),.9),rgba(var(--t5-rgb),.9));color:#fff;box-shadow:0 8px 18px -10px rgba(var(--t5-rgb),.9)}',
    '.rk-days i.on:hover{transform:translateY(-2px)}',
    '.rk-days-l{display:flex;justify-content:space-between;font-size:10.5px;color:var(--text-600)}',
    '.rk-warn{border-color:rgba(var(--a4-rgb),.45);background:linear-gradient(135deg,rgba(var(--a4-rgb),.13),transparent 70%),var(--surface)}',
    '.rk-warn .big{font:600 30px/1 "Space Grotesk",sans-serif;color:var(--amber-400,#e0a94f);margin:8px 0 6px}',
    '.rk-warn .big small{font-size:14px;margin-left:4px;color:var(--text-500);font-weight:500}',
    '.rk-more{display:flex;flex-wrap:wrap;gap:8px}'
  ].join('');
  document.head.appendChild(css);

  var host = document.createElement('div'); host.className = 'rk';
  grid.parentNode.insertBefore(host, grid.nextSibling);

  var R = 34, LEN = 2 * Math.PI * R;
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function qual(v) { return v >= .85 ? ['ดีมาก', 'var(--teal-500,#2a9d8f)'] : v >= .7 ? ['ดี', 'var(--blue-txt,#3a86c8)'] : ['พอใช้', 'var(--amber-400,#e0a94f)']; }

  function render() {
    var items = [].slice.call(list.querySelectorAll('li')).map(function (l) { return l.textContent.trim(); }).filter(function (t) { return t && t !== 'กำลังโหลด…'; });
    if (!items.length) return;
    var head = '', gauges = [], hor = '', assume = '', extra = [];
    items.forEach(function (t, i) {
      var m = t.match(/(R²|R2|r|NSE|KGE)\s*=\s*([0-9.]+)/);   // mech_E: NSE/KGE (LOO-CV) แทน R² ของ candidate D
      var h = t.match(/(\d+)\s*[–-]\s*(\d+)\s*วัน/);
      if (m) {
        var v = parseFloat(m[2]), name = t.slice(0, m.index).replace(/^[^:]*:\s*/, '').replace(/\d+\s*จุด/, '').trim();
        var pts = (t.match(/\d+\s*จุด(?:\s+(?:calibrate|held-out|SAR))?/) || [])[0] || '';
        gauges.push({ v: v, name: name || 'ความแม่นยำ', metric: m[1] === 'R2' ? 'R²' : m[1], pts: pts });
      } else if (/ฝนล่วงหน้า/.test(t)) {
        var z = t.match(/=\s*([0-9.]+)\s*(มม\.?)/);
        var wn = /WeatherNext/.test(t);
        assume = '<div class="rk-card rk-warn"><h4>' + (wn ? 'ฝนล่วงหน้าที่ใช้ (7 วัน)' : 'สมมุติฐานฝนล่วงหน้า') + '</h4><div class="big">' + esc(z ? z[1] : '0') + '<small>' + esc(z ? z[2] : 'มม.') + '</small></div><p>' + (wn ? 'จากพยากรณ์ WeatherNext 3 (ค่าเฉลี่ยทั้งพื้นที่) — ค่าอาจคลาดเคลื่อน ช่วงพายุควรติดตามรายวัน' : 'ใช้เป็นค่าประมาณด้านต่ำ — ช่วงพายุควรติดตามรายวัน') + '</p></div>';
      } else if (h) {
        var a = +h[1], b = +h[2], d = '';
        for (var k = 1; k <= 7; k++) d += '<i class="' + (k >= a && k <= b ? 'on' : '') + '">' + k + '</i>';
        var det = (t.match(/\(([^)]*)\)/) || [])[1] || '';
        hor = '<div class="rk-card"><h4>พยากรณ์ระดับกว๊านพะเยา: แม่นช่วง ' + a + '–' + b + ' วัน</h4><div class="rk-days">' + d + '</div><div class="rk-days-l"><span>วันที่ 1</span><span>วันที่ 7</span></div><p style="margin-top:10px">' + esc(det) + ' · ช่วงที่ไฮไลต์คือวันที่ความแม่นยำสูงสุดจากการทดสอบย้อนหลัง</p></div>';
      } else if (i === 0 && !head) {
        var parts = t.split(/\s[—–-]\s/), ttl = parts[0], rest = parts.slice(1).join(' — ');
        var dt = ttl.match(/^(.*?)\s*\(([^)]*)\)\s*$/);
        head = '<div class="rk-head"><div class="rk-eye"><i></i>Model · ที่ใช้งานอยู่</div><h3 class="rk-title">' + esc(dt ? dt[1] : ttl) + (dt ? '<small>' + esc(dt[2]) + '</small>' : '') + '</h3><div class="rk-chips">' +
          rest.split(/\s\+\s/).filter(function (c) { return c && !/inflow\/release/.test(c); })   /* รายละเอียดเชิงเทคนิค -> ไปดูในเปเปอร์ (หน้า Research) */.map(function (c) { var kv = c.match(/^([\w฀-๿_ ./]+?)=\s*([0-9.]+)$/); return '<span class="rk-chip">' + (kv ? esc(kv[1]) + ' <b>' + esc(kv[2]) + '</b>' : esc(c)) + '</span>'; }).join('') + '</div></div>';
      } else extra.push(t);
    });
    var gh = gauges.length ? '<div class="rk-gauges">' + gauges.map(function (g) {
      var q = qual(g.v), off = LEN * (1 - Math.max(0, Math.min(1, g.v)));
      return '<div class="rk-g"><div class="rk-ring"><svg viewBox="0 0 84 84"><circle class="bg" cx="42" cy="42" r="' + R + '"/><circle class="fg" cx="42" cy="42" r="' + R + '" style="--len:' + LEN.toFixed(1) + ';--off:' + off.toFixed(1) + ';--c:' + q[1] + '"/></svg><span>' + g.v.toFixed(3) + '</span></div><div class="rk-gt"><div class="n">' + esc(g.name) + '</div><div class="s">' + esc(g.metric) + (g.pts ? ' · ' + esc(g.pts) : '') + '</div><span class="q" style="--c:' + q[1] + '">' + q[0] + '</span></div></div>';
    }).join('') + '</div>' : '';
    var rowH = (hor || assume) ? '<div class="rk-row">' + hor + assume + '</div>' : '';
    var ex = extra.length ? '<div class="rk-more">' + extra.map(function (e) { return '<span class="rk-chip">' + esc(e) + '</span>'; }).join('') + '</div>' : '';
    host.innerHTML = head + gh + rowH + ex;
    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }); }, { threshold: .3 }) : null;
    [].forEach.call(host.querySelectorAll('.rk-g'), function (g) { if (io) io.observe(g); else g.classList.add('in'); });
  }
  render();
  new MutationObserver(function () { render(); }).observe(list, { childList: true, subtree: true });
})();
