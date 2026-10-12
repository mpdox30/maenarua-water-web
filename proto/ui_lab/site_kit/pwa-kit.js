/* pwa-kit.js — ติดตั้งเป็นแอป (manifest) + service worker เก็บไลบรารี/ธีมไว้ใช้ซ้ำ (ข้อมูลสดไม่ถูกเก็บ)
   ปิดเมื่อพรีวิวบน localhost · เติม ?nosw=1 ท้าย URL เพื่อถอน service worker ในเครื่องนั้น */
(function () {
  'use strict';
  var h = location.hostname;
  if (/^(localhost|127\.|\[::1\])/.test(h) || location.protocol === 'file:') return;
  var cs = document.currentScript, base = '';
  if (cs && cs.src) { var m = cs.src.match(/^(.*\/)assets\/uikit\//); if (m) base = m[1]; }
  if (!base) base = location.href.replace(/[^\/]*([?#].*)?$/, '');
  function add(tag, attrs) { var n = document.createElement(tag); for (var k in attrs) n.setAttribute(k, attrs[k]); document.head.appendChild(n); }
  if (!document.querySelector('link[rel="manifest"]')) add('link', { rel: 'manifest', href: base + 'manifest.webmanifest' });
  if (!document.querySelector('meta[name="theme-color"]')) add('meta', { name: 'theme-color', content: '#081e26' });
  if (!document.querySelector('link[rel="apple-touch-icon"]')) add('link', { rel: 'apple-touch-icon', href: base + 'assets/img/apple-touch-icon.png' });
  if (!('serviceWorker' in navigator)) return;
  if (/[?&]nosw=1/.test(location.search)) {
    navigator.serviceWorker.getRegistrations().then(function (rs) { rs.forEach(function (r) { r.unregister(); }); });
    if (window.caches) caches.keys().then(function (ks) { ks.forEach(function (k) { if (k.indexOf('mnr-') === 0) caches.delete(k); }); });
    return;
  }
  window.addEventListener('load', function () {
    navigator.serviceWorker.register(base + 'sw.js', { scope: base }).catch(function () { });
  });
})();
