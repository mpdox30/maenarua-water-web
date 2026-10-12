/* table-kit.js — ตารางที่สวยขึ้น + ลูกเล่น (ไม่แก้ข้อมูล/โครงเดิมของหน้า ทำงานซ้อนทับเมื่อหน้าเรนเดอร์แถวเสร็จ)
   1) water-demand: ตารางค่าพยากรณ์รายสัปดาห์ — เลขสัปดาห์เป็นป้ายกลม, Prob. เป็นแถบสีตามระดับ, Magnitude/ค่าสุดท้ายเป็นแถบเทียบสัดส่วน,
      ป้าย "สูงสุด" ที่สัปดาห์พีก, แถวสรุปรวม, คลิกหัวคอลัมน์เพื่อเรียงลำดับ (คลิกซ้ำ = สลับน้อย↔มาก, คลิกครั้งที่ 3 = กลับลำดับเดิม)
   2) gis-map: ตารางพื้นที่พืช Zone A/B — ไอคอนพืช, แถบสัดส่วนของแต่ละพืช, % ของโซน, แถบองค์ประกอบรวม, แถวรวมทั้งโซน
   แถบวิ่งขึ้นเมื่อเลื่อนมาถึง · ปิดเอฟเฟกต์เมื่อเปิด "ลดการเคลื่อนไหว"
   กลับแบบเดิม: ลบ <script …/table-kit.js> ออกจากหน้า (หรือจาก KITS ใน preview_server.py) */
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var num = function (t) { var v = parseFloat(String(t).replace(/,/g, '').replace(/[^0-9.\-]/g, '')); return isNaN(v) ? null : v; };
  var fmt = function (v) { return Math.round(v).toLocaleString('en-US'); };

  var css = document.createElement('style');
  css.textContent = [
    '.tk-bar{height:6px;border-radius:99px;background:rgba(var(--t5-rgb),.12);overflow:hidden;margin-top:6px}',
    '.tk-bar i{display:block;height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,var(--c1,var(--teal-500)),var(--c2,var(--teal-300)));transition:width 1s cubic-bezier(.2,.8,.2,1)}',
    '.tk-in .tk-bar i{width:var(--w)}',
    'html.uk-reduce .tk-bar i{transition:none}',
    /* ตารางสัปดาห์ */
    'table.tk-wk-t th[data-tk]{cursor:pointer;user-select:none;white-space:nowrap}table.tk-wk-t th[data-tk]:hover{color:var(--text-100)}',
    'table.tk-wk-t th[data-tk]::after{content:"↕";margin-left:6px;opacity:.35;font-size:11px}table.tk-wk-t th[data-tk="asc"]::after{content:"↑";opacity:1;color:var(--teal-400)}table.tk-wk-t th[data-tk="desc"]::after{content:"↓";opacity:1;color:var(--teal-400)}',
    'table.tk-wk-t tbody td{vertical-align:middle}',
    '.tk-w{display:inline-flex;align-items:center;gap:10px}',
    '.tk-w b{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:50%;font:600 12.5px "Space Grotesk",sans-serif;color:var(--accent-ink,#fff);background:linear-gradient(135deg,var(--teal-500),var(--teal-400));box-shadow:0 2px 8px rgba(var(--t5-rgb),.25)}',
    '.tk-v{min-width:120px}.tk-v span{display:flex;justify-content:space-between;gap:10px;font-variant-numeric:tabular-nums}',
    '.tk-v em{font-style:normal;font-size:11px;color:var(--text-500)}',
    '.tk-lo{--c1:#7aa7c9;--c2:#a9c8e0}.tk-mid{--c1:var(--teal-500);--c2:var(--teal-300)}.tk-hi{--c1:#d9962f;--c2:#f0c47c}',
    '.tk-fin{--c1:var(--teal-500);--c2:var(--teal-300)}',
    '.tk-peak{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:99px;font-size:10.5px;font-weight:700;color:#7a4b00;background:linear-gradient(135deg,#f6d27a,#e8a93c);vertical-align:1px}',
    '.tk-zero{opacity:.55}',
    'table.tk-wk-t tbody tr.tk-pk{background:linear-gradient(90deg,rgba(var(--a4-rgb),.12),transparent 70%)}',
    'table.tk-wk-t tbody tr.tk-tot td{font-weight:700;color:var(--text-100);background:rgba(var(--t5-rgb),.07);border-top:2px solid var(--border-strong,var(--border))}',
    'table.tk-wk-t tbody tr.tk-tot td.hl{color:var(--teal-400)}',
    'table.tk-wk-t tbody tr.tk-row{opacity:0;transform:translateY(8px);transition:opacity .5s,transform .5s;transition-delay:calc(var(--i,0)*45ms)}',
    'table.tk-wk-t.tk-in tbody tr.tk-row{opacity:1;transform:none}',
    'html.uk-reduce table.tk-wk-t tbody tr.tk-row{opacity:1;transform:none;transition:none}',
    /* ตารางพืช */
    '.tk-ci{display:inline-grid;place-items:center;width:30px;height:30px;margin-right:10px;border-radius:9px;font-size:16px;background:color-mix(in srgb,var(--c) 18%,transparent);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--c) 40%,transparent);vertical-align:middle}',
    '.tk-sv{display:flex;justify-content:space-between;align-items:baseline;gap:12px}.tk-sv em{font-style:normal;font-size:11.5px;font-weight:700;color:var(--c)}',
    'table.tk-crop td.hl{min-width:230px}table.tk-crop .tk-bar i{--c1:var(--c);--c2:color-mix(in srgb,var(--c) 55%,#fff)}',
    'tr.tk-stk td{padding-top:14px;padding-bottom:10px}.tk-stack{display:flex;height:12px;border-radius:99px;overflow:hidden;gap:2px;background:rgba(var(--t5-rgb),.1)}',
    '.tk-stack i{display:block;height:100%;width:0;background:var(--c);transition:width 1.1s cubic-bezier(.2,.8,.2,1)}.tk-in .tk-stack i{width:var(--w)}',
    'html.uk-reduce .tk-stack i{transition:none}',
    'tr.tk-ctot td{font-weight:700;color:var(--text-100);background:rgba(var(--t5-rgb),.07);border-top:2px solid var(--border-strong,var(--border))}',
    '@media(max-width:640px){.tk-v{min-width:90px}table.tk-crop td.hl{min-width:0}}'
  ].join('');
  document.head.appendChild(css);

  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('tk-in'); io.unobserve(e.target); } }); }, { threshold: .15 }) : null;
  function reveal(tbl) { if (!io) { tbl.classList.add('tk-in'); return; } if (!tbl.classList.contains('tk-in')) io.observe(tbl); }

  /* ---------- ตารางพยากรณ์รายสัปดาห์ ---------- */
  function weekly(tb) {
    var tbl = tb.closest('table'), rows = [].slice.call(tb.rows).filter(function (r) { return r.cells.length === 4 && !r.classList.contains('tk-tot'); });
    if (!rows.length || rows.every(function (r) { return r.classList.contains('tk-row'); })) return;
    tbl.classList.add('tk-wk-t');
    var d = rows.map(function (r, i) { return { r: r, i: i, w: r.cells[0].textContent.trim(), p: num(r.cells[1].textContent), m: num(r.cells[2].textContent), f: num(r.cells[3].textContent), pt: r.cells[1].textContent.trim(), mt: r.cells[2].textContent.trim(), ft: r.cells[3].textContent.trim() }; });
    var mxM = Math.max.apply(null, d.map(function (x) { return x.m || 0; })) || 1, mxF = Math.max.apply(null, d.map(function (x) { return x.f || 0; })) || 1;
    var pk = d.reduce(function (a, b) { return (b.f || 0) > (a.f || 0) ? b : a; }), sum = 0;
    d.forEach(function (x) {
      var n = (x.w.match(/\d+/) || [x.i + 1])[0], lv = x.p == null ? 'tk-lo' : x.p >= 80 ? 'tk-hi' : x.p >= 50 ? 'tk-mid' : 'tk-lo';
      sum += x.f || 0;
      x.r.classList.add('tk-row'); x.r.style.setProperty('--i', x.i); x.r.dataset.tkI = x.i; x.r.dataset.tkW = n; x.r.dataset.tkP = x.p == null ? -1 : x.p; x.r.dataset.tkM = x.m == null ? -1 : x.m; x.r.dataset.tkF = x.f == null ? -1 : x.f;
      x.r.cells[0].innerHTML = '<span class="tk-w"><b>' + esc(n) + '</b><span>' + esc(x.w) + '</span></span>';
      x.r.cells[1].innerHTML = '<div class="tk-v"><span>' + esc(x.pt) + '</span><div class="tk-bar ' + lv + '"><i style="--w:' + Math.max(0, Math.min(100, x.p || 0)) + '%"></i></div></div>';
      x.r.cells[2].innerHTML = '<div class="tk-v"><span>' + esc(x.mt) + '</span><div class="tk-bar tk-mid"><i style="--w:' + ((x.m || 0) / mxM * 100).toFixed(1) + '%"></i></div></div>';
      x.r.cells[3].innerHTML = '<div class="tk-v"><span><b>' + esc(x.ft) + '</b>' + (x === pk && (x.f || 0) > 0 ? '<span class="tk-peak">สูงสุด</span>' : '') + '</span><div class="tk-bar tk-fin"><i style="--w:' + ((x.f || 0) / mxF * 100).toFixed(1) + '%"></i></div></div>';
      x.r.classList.toggle('tk-pk', x === pk && (x.f || 0) > 0); x.r.classList.toggle('tk-zero', !(x.f > 0));
    });
    var tot = document.createElement('tr'); tot.className = 'tk-tot';
    tot.innerHTML = '<td>รวม</td><td></td><td></td><td class="hl">' + fmt(sum) + '</td>'; tb.appendChild(tot);
    var ths = [].slice.call(tbl.querySelectorAll('thead th'));
    ths.forEach(function (th, ci) {
      if (th.dataset.tkBound) return; th.dataset.tkBound = 1; th.setAttribute('data-tk', ''); th.title = 'เรียงลำดับ';
      th.addEventListener('click', function () {
        var cur = th.getAttribute('data-tk'), nx = cur === 'desc' ? 'asc' : cur === 'asc' ? '' : 'desc'; ths.forEach(function (o) { o.setAttribute('data-tk', ''); }); th.setAttribute('data-tk', nx);
        var key = ['tkW', 'tkP', 'tkM', 'tkF'][ci], rs = [].slice.call(tb.querySelectorAll('tr.tk-row')), t = tb.querySelector('tr.tk-tot');
        rs.sort(function (a, b) { return nx === '' ? a.dataset.tkI - b.dataset.tkI : (nx === 'asc' ? 1 : -1) * (a.dataset[key] - b.dataset[key]); });
        busy = true; rs.forEach(function (r) { tb.insertBefore(r, t); }); busy = false;
      });
    });
    reveal(tbl);
  }

  /* ---------- ตารางพื้นที่พืช (SAR) ---------- */
  var CROP = [[/ข้าวโพด|maize|corn/i, '🌽', '#e0a94f'], [/ข้าว|rice/i, '🌾', '#6fb36a'], [/มันสำปะหลัง|cassava/i, '🍠', '#c08a5b'], [/ลำไย|longan/i, '🌳', '#d9822b'], [/อื่น|other/i, '🌴', '#8e86c9']];
  function crop(tb) {
    var tbl = tb.closest('table'), rows = [].slice.call(tb.rows).filter(function (r) { return r.cells.length === 2 && !r.classList.contains('tk-stk') && !r.classList.contains('tk-ctot'); });
    if (!rows.length || rows.every(function (r) { return r.dataset.tkC; })) return;
    tbl.classList.add('tk-crop');
    var d = rows.map(function (r) { var nm = r.cells[0].textContent.trim(), tx = r.cells[1].textContent.trim(), c = CROP.filter(function (k) { return k[0].test(nm); })[0] || [0, '🌱', '#7aa7c9']; return { r: r, nm: nm, tx: tx, ha: num(tx) || 0, ic: c[1], col: c[2] }; });
    var tot = d.reduce(function (a, x) { return a + x.ha; }, 0) || 1;
    d.forEach(function (x) {
      var p = x.ha / tot * 100; x.r.dataset.tkC = 1; x.r.style.setProperty('--c', x.col);
      x.r.cells[0].innerHTML = '<span class="tk-ci" style="--c:' + x.col + '">' + x.ic + '</span>' + esc(x.nm);
      x.r.cells[1].innerHTML = '<div class="tk-sv"><span>' + esc(x.tx) + '</span><em>' + p.toFixed(1) + '%</em></div><div class="tk-bar"><i style="--w:' + p.toFixed(1) + '%"></i></div>';
    });
    var st = document.createElement('tr'); st.className = 'tk-stk';
    st.innerHTML = '<td colspan="2"><div class="tk-stack">' + d.map(function (x) { return '<i title="' + esc(x.nm) + ' ' + (x.ha / tot * 100).toFixed(1) + '%" style="--c:' + x.col + ';--w:' + (x.ha / tot * 100).toFixed(2) + '%"></i>'; }).join('') + '</div></td>';
    tb.insertBefore(st, tb.firstChild);
    var tr = document.createElement('tr'); tr.className = 'tk-ctot';
    tr.innerHTML = '<td>รวม</td><td><div class="tk-sv"><span>' + tot.toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 }) + ' ha (' + (tot * 6.25).toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 }) + ' ไร่)</span><em style="color:var(--text-100)">100%</em></div></td>';
    tb.appendChild(tr); reveal(tbl);
  }

  var busy = false, targets = [['performanceTableBody', weekly], ['sarZoneATableBody', crop], ['sarZoneBTableBody', crop]];
  targets.forEach(function (t) {
    var tb = document.getElementById(t[0]); if (!tb) return;
    var run = function () { if (busy) return; busy = true; try { t[1](tb); } catch (e) { console.warn('table-kit', e); } busy = false; };
    new MutationObserver(function () { if (!busy) run(); }).observe(tb, { childList: true });
    run();
  });
})();
