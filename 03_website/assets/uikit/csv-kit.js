/* csv-kit.js — ปุ่ม "ดาวน์โหลด CSV" ใต้ตารางข้อมูลหลัก (.table-card table)
   อ่านจากตารางที่แสดงอยู่ (ค่าที่เห็นบนจอ) · UTF-8 มี BOM เปิดใน Excel ได้ภาษาไทย · ไม่ส่งข้อมูลออกนอกเครื่อง
   ภาษา: ตาม localStorage uk_lang (th/en) */
(function () {
  'use strict';
  var EN = false;
  try { EN = (localStorage.getItem('uk_lang') || '') === 'en'; } catch (e) { }
  if (document.documentElement.lang === 'en') EN = true;
  function T(th, en) { return EN ? en : th; }

  var NAMES = { performanceTableBody: 'water-demand-forecast', horizonTableBody: 'inflow-forecast-7day', reservoirTableBody: 'reservoirs',
    cadenceTableBody: 'data-update-cadence', ledgerTableBody: 'water-ledger-monthly', sarZoneATableBody: 'sar-crop-zoneA', sarZoneBTableBody: 'sar-crop-zoneB' };

  var css = document.createElement('style');
  css.textContent = '.csv-bar{display:flex;justify-content:flex-end;margin:8px 2px 0}' +
    '.csv-btn{font:inherit;font-size:12.5px;line-height:1;cursor:pointer;padding:7px 12px;border-radius:999px;border:1px solid rgba(var(--bd-rgb,157,201,201),.35);background:rgba(var(--w-rgb,255,255,255),.04);color:var(--text-300,#c4d6d3);transition:background .15s,border-color .15s}' +
    '.csv-btn:hover{background:rgba(var(--t4-rgb,69,194,173),.16);border-color:var(--teal-400,#45c2ad);color:var(--text-100,#eef6f4)}' +
    '.csv-btn:focus-visible{outline:2px solid var(--teal-300,#7fe0d1);outline-offset:2px}.csv-btn[disabled]{opacity:.5;cursor:default}' +
    '@media print{.csv-bar{display:none!important}}';
  document.head.appendChild(css);

  function clean(td) {
    var c = td.cloneNode(true);
    [].forEach.call(c.querySelectorAll('.tk-bar,.tk-ci,.tk-peak,.tk-stack,script,style'), function (n) { n.remove(); });
    var sv = c.querySelector('.tk-sv > span'); if (sv) return sv.textContent.replace(/\s+/g, ' ').trim();
    var tv = c.querySelector('.tk-v > span'); if (tv) return tv.textContent.replace(/\s+/g, ' ').trim();
    return c.textContent.replace(/\s+/g, ' ').trim();
  }
  function q(v) { v = String(v); return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function toCsv(tbl) {
    var out = [], head = tbl.tHead && tbl.tHead.rows[tbl.tHead.rows.length - 1];
    if (head) out.push([].map.call(head.cells, clean));
    var n = 0;
    [].forEach.call(tbl.tBodies, function (tb) {
      [].forEach.call(tb.rows, function (r) {
        if (r.classList.contains('tk-stk')) return;
        if ([].some.call(r.cells, function (c) { return c.colSpan > 1 && r.cells.length === 1; })) return;   // แถว "กำลังโหลด/ไม่มีข้อมูล"
        out.push([].map.call(r.cells, clean)); n++;
      });
    });
    return n ? '﻿' + out.map(function (r) { return r.map(q).join(','); }).join('\r\n') + '\r\n' : '';
  }
  function fname(tbl) {
    var tb = tbl.tBodies[0], id = tb && tb.id, base = (id && NAMES[id]) || id || 'table';
    var page = (location.pathname.split('/').pop() || 'index').replace(/\.html?$/i, '') || 'index';
    var d = new Date(), p = function (x) { return String(x).padStart(2, '0'); };
    return 'maenarua-' + (NAMES[id] ? '' : page + '-') + base + '-' + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '.csv';
  }
  function dl(tbl, btn) {
    var csv = toCsv(tbl), label = btn.textContent;
    if (!csv) { btn.textContent = T('ยังไม่มีข้อมูลในตาราง', 'No data in table yet'); setTimeout(function () { btn.textContent = label; }, 1800); return; }
    var url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })), a = document.createElement('a');
    a.href = url; a.download = fname(tbl); document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  }
  function init() {
    [].forEach.call(document.querySelectorAll('.table-card'), function (card) {
      var tbl = card.querySelector('table'); if (!tbl || card.nextElementSibling && card.nextElementSibling.classList.contains('csv-bar')) return;
      var bar = document.createElement('div'), b = document.createElement('button');
      bar.className = 'csv-bar'; b.type = 'button'; b.className = 'csv-btn';
      b.textContent = T('⬇ ดาวน์โหลด CSV', '⬇ Download CSV'); b.title = T('ดาวน์โหลดตารางนี้เป็นไฟล์ CSV (เปิดใน Excel ได้)', 'Download this table as CSV (opens in Excel)');
      b.addEventListener('click', function () { dl(tbl, b); });
      bar.appendChild(b); card.parentNode.insertBefore(bar, card.nextSibling);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
