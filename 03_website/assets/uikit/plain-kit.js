/* plain-kit.js — แปลง "หมายเหตุโมเดล" เป็นภาษาคน (TH/EN ตาม localStorage uk_lang)
   - inflow-forecast.html : การ์ดสรุปความน่าเชื่อถือรายวัน (+1…+7) + ย้ายกล่องเทคนิคเข้า <details>
   - water-demand.html    : การ์ด "ตัวเลขนี้มาจากไหน" (Live / Static / ผสม) + ย้ายหมายเหตุเทคนิคเข้า <details>
   - gis-map.html, index.html : ประโยคอธิบายคุณภาพข้อมูล SAR + ซ่อนรายละเอียดเทคนิคใน <details>
   ไม่แก้ข้อมูล ไม่แก้สคริปต์เดิมของหน้า — อ่านจาก DOM ที่หน้าเรนเดอร์แล้วเท่านั้น */
(function () {
  'use strict';
  var EN = false;
  try { EN = (localStorage.getItem('uk_lang') || '') === 'en'; } catch (e) { }
  if (document.documentElement.lang === 'en') EN = true;
  function T(th, en) { return EN ? en : th; }
  function $(id) { return document.getElementById(id); }
  function el(tag, cls, html) { var n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; }
  function once(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms || 60); }; }

  var css = '.pk-card{margin:0 0 16px;padding:16px 18px;border-radius:14px;border:1px solid rgba(var(--bd-rgb,157,201,201),.22);background:rgba(var(--w-rgb,255,255,255),.035);border-left:3px solid var(--teal-400,#45c2ad)}' +
    '.pk-card.warn{border-left-color:var(--amber-400,#e0a94f)}.pk-card.bad{border-left-color:var(--red-txt,#f3a89f)}' +
    '.pk-card h4{margin:0 0 6px;font-size:15px;color:var(--text-100,#eef6f4)}' +
    '.pk-lead{margin:0 0 10px;font-size:14px;line-height:1.65;color:var(--text-300,#c4d6d3)}' +
    '.pk-chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 12px}' +
    '.pk-chip{display:flex;flex-direction:column;align-items:center;min-width:74px;padding:8px 10px;border-radius:12px;border:1px solid rgba(var(--bd-rgb,157,201,201),.25);font-size:12px;line-height:1.35;text-align:center;color:var(--text-300,#c4d6d3)}' +
    '.pk-chip b{font-size:13px;color:var(--text-100,#eef6f4)}.pk-chip i{font-style:normal;font-size:11px;opacity:.85}' +
    '.pk-chip.g{border-color:rgba(111,207,151,.55);background:rgba(111,207,151,.10)}.pk-chip.f{border-color:rgba(224,169,79,.55);background:rgba(224,169,79,.10)}.pk-chip.p{border-color:rgba(243,168,159,.55);background:rgba(243,168,159,.09)}' +
    '.pk-list{margin:0;padding-left:20px;font-size:13.5px;line-height:1.7;color:var(--text-300,#c4d6d3)}' +
    '.pk-key{margin:10px 0 0;font-size:12px;color:var(--text-500,#8aa3a0)}' +
    '.pk-det{margin:0 0 16px;border-radius:12px;border:1px dashed rgba(var(--bd-rgb,157,201,201),.28);padding:2px 14px}' +
    '.pk-det>summary{cursor:pointer;padding:10px 0;font-size:13px;color:var(--text-500,#8aa3a0);list-style:none}' +
    '.pk-det>summary::-webkit-details-marker{display:none}.pk-det>summary:before{content:"▸ ";color:var(--teal-300,#7fe0d1)}.pk-det[open]>summary:before{content:"▾ "}' +
    '.pk-det .disclaimer-box{margin:0 0 12px}';
  var st = el('style'); st.textContent = css; document.head.appendChild(st);

  function wrapDetails(nodes, label, before) {
    nodes = nodes.filter(Boolean);
    if (!nodes.length || nodes[0].closest('details.pk-det')) return null;
    var d = el('details', 'pk-det'), s = el('summary', '', label);
    d.appendChild(s); (before || nodes[0]).parentNode.insertBefore(d, before || nodes[0]);
    nodes.forEach(function (n) { d.appendChild(n); });
    return d;
  }
  function num(s) { var m = String(s || '').replace(/,/g, '').match(/-?\d+(?:\.\d+)?/); return m ? parseFloat(m[0]) : null; }

  /* ---------- 1) inflow-forecast : สรุปความน่าเชื่อถือรายวัน ---------- */
  function inflow() {
    var tb = $('horizonTableBody'); if (!tb) return;
    function build() {
      var rows = [].slice.call(tb.querySelectorAll('tr')).filter(function (r) { return r.cells && r.cells.length >= 5; });
      var card = $('pk-inflow'), anchor = tb.closest('.table-card');
      if (!rows.length) { if (card) card.style.display = 'none'; return; }
      var H = rows.map(function (r, i) {
        var nse = num(r.cells[3].textContent.split('(')[0]);
        return { d: i + 1, p: num(r.cells[1].textContent), nse: nse, low: !!r.querySelector('.badge-low') };
      });
      var good = H.filter(function (h) { return h.nse != null && h.nse >= 0.5; }),
        fair = H.filter(function (h) { return h.nse != null && h.nse >= 0 && h.nse < 0.5; }),
        poor = H.filter(function (h) { return h.nse == null || h.nse < 0; });
      var cls = poor.length === H.length ? 'bad' : (poor.length ? 'warn' : '');
      var lead;
      if (poor.length === H.length) lead = T('ตอนนี้ตัวเลขพยากรณ์น้ำไหลเข้าอ่างทุกวันที่ล่วงหน้า (1–' + H.length + ' วัน) ยังแม่นไม่ถึงระดับ "ดีกว่าเดาด้วยค่าเฉลี่ย" — ใช้ดูทิศทางขึ้น/ลงเท่านั้น ไม่ควรเอาตัวเลขไปคำนวณต่อโดยตรง',
        'Inflow forecasts for all ' + H.length + ' days ahead are not yet better than simply guessing the average — use them to see the direction (up/down) only, not as exact volumes.');
      else if (!poor.length) lead = T('พยากรณ์น้ำไหลเข้าอ่างทุกวันล่วงหน้าผ่านเกณฑ์ขั้นต่ำ (แม่นกว่าการเดาด้วยค่าเฉลี่ย) ใช้ประกอบการตัดสินใจได้ แต่ยังควรเทียบกับระดับน้ำจริง',
        'Inflow forecasts for every day ahead beat the average-guess baseline. Usable as supporting evidence, but still compare with the measured reservoir level.');
      else lead = T('บางวันพยากรณ์ได้พอใช้ (' + fair.concat(good).map(function (h) { return '+' + h.d; }).join(', ') + ' วัน) แต่วัน ' + poor.map(function (h) { return '+' + h.d; }).join(', ') + ' ยังไม่แม่น ควรดูเป็นแนวโน้มเท่านั้น',
        'Some days are usable (+' + fair.concat(good).map(function (h) { return h.d; }).join(', +') + ' d) but +' + poor.map(function (h) { return h.d; }).join(', +') + ' d are still unreliable — treat them as trend only.');
      var chips = H.map(function (h) {
        var c = h.nse == null ? 'p' : h.nse >= 0.5 ? 'g' : h.nse >= 0 ? 'f' : 'p';
        var w = h.nse == null ? T('ไม่มีข้อมูล', 'n/a') : h.nse >= 0.5 ? T('เชื่อถือได้', 'reliable') : h.nse >= 0 ? T('พอใช้', 'fair') : T('ยังไม่แม่น', 'weak');
        return '<div class="pk-chip ' + c + '"><b>+' + h.d + T(' วัน', ' d') + '</b><i>' + w + '</i></div>';
      }).join('');
      var tr = '';
      if (H[0].p && H[H.length - 1].p != null) {
        var ch = (H[H.length - 1].p - H[0].p) / H[0].p * 100;
        tr = Math.abs(ch) < 10 ? T('ปริมาณน้ำเข้าอ่างคาดว่าใกล้เคียงเดิมตลอด ' + H.length + ' วัน', 'Inflow is expected to stay about the same over ' + H.length + ' days')
          : T('แนวโน้ม ' + H.length + ' วัน: น้ำเข้าอ่าง' + (ch < 0 ? 'ลดลง' : 'เพิ่มขึ้น') + ' ประมาณ ' + Math.abs(ch).toFixed(0) + '% เทียบกับวันแรก',
            H.length + '-day trend: inflow ' + (ch < 0 ? 'falls' : 'rises') + ' about ' + Math.abs(ch).toFixed(0) + '% vs. day 1');
      }
      var html = '<h4>' + T('สรุปแบบเข้าใจง่าย', 'Plain-language summary') + '</h4><p class="pk-lead">' + lead + '</p>' +
        '<div class="pk-chips">' + chips + '</div>' +
        '<ul class="pk-list">' + (tr ? '<li>' + tr + '</li>' : '') +
        '<li>' + T('ตัดสินใจเรื่องการระบายน้ำ ให้ดูระดับน้ำจริงในอ่างและพยากรณ์ฝนล่าสุดควบคู่เสมอ', 'For release decisions, always check the measured reservoir level and the latest rain forecast alongside this.') + '</li>' +
        '<li>' + T('ความแม่นจะดีขึ้นเมื่อระบบสะสมผลเทียบจริงได้นานขึ้น (ตอนนี้บันทึกย้อนหลังยังสั้น)', 'Accuracy should improve as the system accumulates more forecast-vs-actual history (the log is still short).') + '</li></ul>' +
        '<p class="pk-key">' + T('NSE: 1 = แม่นสมบูรณ์ · 0 = เท่ากับเดาด้วยค่าเฉลี่ย · ติดลบ = แย่กว่าเดาด้วยค่าเฉลี่ย', 'NSE: 1 = perfect · 0 = same as guessing the average · negative = worse than guessing the average') + '</p>';
      if (!card) { card = el('div', 'pk-card'); card.id = 'pk-inflow'; anchor.parentNode.insertBefore(card, anchor); }
      card.className = 'pk-card ' + cls; card.style.display = ''; card.innerHTML = html;
    }
    var run = once(build, 80);
    new MutationObserver(run).observe(tb, { childList: true, subtree: true, characterData: true });
    build();
    var ti = $('thresholdInstabilityBox'), lim = $('limitationsList') && $('limitationsList').closest('.disclaimer-box');
    if (lim) wrapDetails([ti, lim], T('รายละเอียดทางเทคนิคของโมเดล (สำหรับนักวิเคราะห์) — ข้อจำกัด ความเบี่ยงเบนจากสูตรต้นฉบับ ความแกว่งของ NSE', 'Technical model details (for analysts) — limitations, deviations from the original formula, NSE instability'), ti || lim);
  }

  /* ---------- 2) water-demand : แหล่งข้อมูลของตัวเลข ---------- */
  function demand() {
    var sd = $('snapshotDisclaimer'), dv = $('dataSourceValue'); if (!sd || !dv) return;
    var box = sd.closest('.disclaimer-box'); if (!box) return;
    function build() {
      var v = (dv.textContent || '').trim(); if (!v || /โหลด|loading/i.test(v)) return;
      var live = /^Live/i.test(v) && v.indexOf('/') < 0, stat = /Static/i.test(v) && v.indexOf('/') < 0;
      var cls = live ? '' : 'warn', h, p;
      if (live) { h = T('ตัวเลขนี้คำนวณจากข้อมูลจริงล่าสุด', 'These figures use the latest real data'); p = T('ใช้ข้อมูลภูมิอากาศและพื้นที่เพาะปลูกจากดาวเทียมของสัปดาห์นี้ ทั้ง 2 โซน — เชื่อถือเป็นแนวทางวางแผนน้ำรายสัปดาห์ได้', 'Built from this week\'s climate data and satellite-mapped crop area for both zones — fine to use as a weekly planning guide.'); }
      else if (stat) { h = T('ตัวเลขนี้ยังเป็นค่าตัวอย่างคงที่ (ไม่ใช่ข้อมูลสดสัปดาห์นี้)', 'These figures are a fixed snapshot (not this week\'s live data)'); p = T('ระบบกำลังสะสมข้อมูลจริงเบื้องหลัง เมื่อครบ 12 สัปดาห์ต่อเนื่องจะสลับมาใช้ข้อมูลสดเองอัตโนมัติ ระหว่างนี้ใช้ดูภาพรวมเท่านั้น', 'The system is collecting real data in the background and will switch to live data automatically after 12 consecutive weeks. For now, use it as an overview only.'); }
      else { h = T('ตัวเลขผสม: โซนหนึ่งเป็นข้อมูลสด อีกโซนยังเป็นค่าตัวอย่าง', 'Mixed: one zone uses live data, the other a fixed snapshot'); p = T('ดูป้ายแหล่งข้อมูลของแต่ละโซนด้านบน โซนที่ยังเป็นค่าตัวอย่างให้ใช้ดูภาพรวมเท่านั้น', 'Check each zone\'s source label above; use the snapshot zone as an overview only.'); }
      var c = $('pk-demand');
      if (!c) { c = el('div', 'pk-card'); c.id = 'pk-demand'; box.parentNode.insertBefore(c, box); wrapDetails([box], T('รายละเอียดแหล่งข้อมูล (เทคนิค)', 'Data-source details (technical)'), c.nextSibling); }
      c.className = 'pk-card ' + cls; c.innerHTML = '<h4>' + h + '</h4><p class="pk-lead" style="margin:0">' + p + '</p>';
    }
    var run = once(build, 80);
    new MutationObserver(run).observe(dv, { childList: true, subtree: true, characterData: true });
    build();
  }

  /* ---------- 3) SAR quality (gis-map + index) ---------- */
  function sar() {
    var box = $('sarQualityBox'); if (!box) return;
    var note = $('sarQualityNote'), list = $('sarQualityWeeksList');
    function build() {
      if (box.style.display === 'none') return;
      var li = list && list.querySelector('li'), n = li ? num(li.textContent) : null;
      var p = $('pk-sar');
      if (!p) {
        p = el('p', 'pk-lead'); p.id = 'pk-sar';
        var h = box.querySelector('h4'); box.insertBefore(p, h ? h.nextSibling : box.firstChild);
        wrapDetails([note, list], T('ดูรายละเอียดทางเทคนิค', 'Technical details'), note);
      }
      p.textContent = n != null
        ? T('ภาพดาวเทียมรอบนี้มี ' + n + ' สัปดาห์ที่ข้อมูลหายไปมากกว่าที่โมเดลเคยเจอตอนเรียนรู้ จึงอาจจำแนกชนิดพืชคลาดเคลื่อน — ตัวเลขพื้นที่ปลูกด้านบนใช้ดูภาพรวมเท่านั้น',
          'This round of satellite imagery has ' + n + ' week(s) with more missing data than the model saw in training, so crop classes may be off — treat the crop-area figures above as a rough overview.')
        : T('คุณภาพภาพดาวเทียมรอบนี้ต่ำกว่าปกติ ตัวเลขพื้นที่ปลูกใช้ดูภาพรวมเท่านั้น', 'Satellite data quality is lower than usual this round; treat crop-area figures as a rough overview.');
    }
    var run = once(build, 80), mo = new MutationObserver(run);
    mo.observe(box, { attributes: true, attributeFilter: ['style'] });
    if (list) mo.observe(list, { childList: true });
    build();
  }

  function init() { try { inflow(); } catch (e) { } try { demand(); } catch (e) { } try { sar(); } catch (e) { } }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
