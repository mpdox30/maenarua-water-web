"""
make_pwa_assets.py — สร้างไฟล์ PWA ให้เว็บ (ติดตั้งเป็นแอปบนมือถือ + เปิดซ้ำเร็วขึ้น) ลงใน 03_website/
สร้าง: manifest.webmanifest · sw.js · assets/img/icon-192.png · icon-512.png · icon-maskable-512.png · apple-touch-icon.png
ใช้:   python make_pwa_assets.py        (รันซ้ำได้ ทับไฟล์เดิม)   แล้ว python deploy_to_production.py (ฝัง pwa-kit.js)
หลักการ service worker:
  - หน้า .html          : เครือข่ายก่อน → ถ้าออฟไลน์ใช้สำเนาในเครื่อง
  - assets/vendor, uikit, fonts, img, js : เก็บไว้ใช้ซ้ำ (uikit มี ?v= เปลี่ยนทุกครั้งที่ deploy)
  - assets/data (JSON ข้อมูลสด) : ไม่เก็บ ไม่แตะ — ไม่มีทางได้ตัวเลขเก่าโดยไม่รู้ตัว
  - ลิงก์ข้ามโดเมน (แผนที่ฐาน, API) : ไม่แตะ
ถอยกลับ: ลบ pwa-kit.js ออกจาก KITS แล้ว deploy ใหม่ ผู้ใช้เดิมจะยังมี sw.js ค้าง → ให้คง sw.js ไว้ (มันแค่ unregister ตัวเองได้ด้วย ?off) หรือดู README
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import preview_server as ps
SITE = ps.SITE
IMG = os.path.join(SITE, 'assets', 'img'); os.makedirs(IMG, exist_ok=True)

def icon(size, maskable=False):
    from PIL import Image, ImageDraw
    S = size * 4; im = Image.new('RGB', (S, S), (6, 22, 28)); d = ImageDraw.Draw(im)
    # พื้นหลังไล่เฉด
    for y in range(S):
        t = y / S; d.line([(0, y), (S, y)], fill=(int(6 + 10 * t), int(22 + 30 * t), int(28 + 34 * t)))
    k = 0.62 if maskable else 0.80        # maskable ต้องมีขอบปลอดภัย ~10%
    cx, cy, R = S / 2, S * 0.62, S * 0.25 * k / 0.8
    import math
    L = R * 2.25; al = math.asin(R / L); tx, ty = R * math.cos(al), R * math.sin(al)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(69, 194, 173))
    d.polygon([(cx, cy - L), (cx - tx, cy - ty), (cx + tx, cy - ty)], fill=(69, 194, 173))
    d.chord([cx - R * 0.72, cy - R * 0.72, cx + R * 0.72, cy + R * 0.72], 100, 170, fill=(127, 224, 209))
    pts = [(cx - R * 0.62 + i * R * 1.24 / 40, cy + R * 0.28 + math.sin(i / 40 * 2 * math.pi * 1.5) * R * 0.09) for i in range(41)]
    d.line(pts, fill=(6, 22, 28), width=max(2, int(R * 0.10)), joint='curve')
    return im.resize((size, size), Image.LANCZOS)

for name, size, mk in [('icon-192.png', 192, False), ('icon-512.png', 512, False), ('icon-maskable-512.png', 512, True), ('apple-touch-icon.png', 180, False)]:
    icon(size, mk).save(os.path.join(IMG, name), optimize=True); print('สร้าง assets/img/' + name)

manifest = {
    'name': 'แม่นาเรือ · ระบบข้อมูลน้ำ', 'short_name': 'แม่นาเรือน้ำ',
    'description': 'พยากรณ์น้ำท่วม น้ำท่า ความต้องการน้ำ และเฝ้าระวังอ่างเก็บน้ำ ต.แม่นาเรือ จ.พะเยา',
    'lang': 'th', 'dir': 'ltr', 'start_url': './index.html', 'scope': './', 'id': './',
    'display': 'standalone', 'orientation': 'any', 'background_color': '#06161c', 'theme_color': '#081e26',
    'icons': [
        {'src': 'assets/img/icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
        {'src': 'assets/img/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
        {'src': 'assets/img/icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}],
    'shortcuts': [
        {'name': 'พยากรณ์น้ำท่วม', 'url': './flood-forecast.html'},
        {'name': 'พยากรณ์น้ำท่า', 'url': './inflow-forecast.html'},
        {'name': 'ตรวจวัดสถานี', 'url': './monitoring.html'}]}
with open(os.path.join(SITE, 'manifest.webmanifest'), 'w', encoding='utf-8', newline='\n') as f: json.dump(manifest, f, ensure_ascii=False, indent=2)
print('สร้าง manifest.webmanifest')

SW = r"""/* sw.js — service worker แม่นาเรือ (สร้างโดย make_pwa_assets.py) */
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
"""
with open(os.path.join(SITE, 'sw.js'), 'w', encoding='utf-8', newline='\n') as f: f.write(SW)
print('สร้าง sw.js')
