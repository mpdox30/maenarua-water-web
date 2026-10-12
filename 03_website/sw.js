/* sw.js — service worker แม่นาเรือ (สร้างโดย make_pwa_assets.py) */
const VER = 'mnr-v1', STATIC = VER + '-static', PAGES = VER + '-pages';
self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (!k.startsWith(VER + '-')) await caches.delete(k);
  await self.clients.claim();
})()));
const isStatic = p => /\/assets\/(vendor|uikit|fonts|img|js)\//.test(p);
self.addEventListener('fetch', e => {
  const r = e.request; if (r.method !== 'GET') return;
  const u = new URL(r.url); if (u.origin !== location.origin) return;      // ข้ามโดเมน: ไม่แตะ
  if (/\/assets\/data\//.test(u.pathname)) return;                          // ข้อมูลสด: ไม่แตะ ไม่เก็บ
  if (r.mode === 'navigate' || /\.html?$/.test(u.pathname)) {               // หน้าเว็บ: เครือข่ายก่อน
    e.respondWith((async () => {
      try { const res = await fetch(r); if (res.ok) { const c = await caches.open(PAGES); c.put(r, res.clone()); } return res; }
      catch (err) { return (await caches.match(r, { ignoreSearch: true })) || (await caches.match('index.html')) || Response.error(); }
    })()); return;
  }
  if (isStatic(u.pathname)) {                                               // ไลบรารี/ธีม/รูป: ใช้ของในเครื่องก่อน
    e.respondWith((async () => {
      const hit = await caches.match(r); if (hit) return hit;
      const res = await fetch(r); if (res.ok) { const c = await caches.open(STATIC); c.put(r, res.clone()); } return res;
    })());
  }
});
