"""
vendor_cdn.py — ดาวน์โหลดไลบรารี/ฟอนต์ที่เว็บเรียกจาก CDN มาเก็บในเว็บเอง (03_website/assets/vendor/) แล้วแก้ลิงก์ในหน้า .html
ทำไม: เว็บไม่ล่มเมื่อ CDN (unpkg / jsdelivr / Google Fonts) ช้า/ล่ม/ถูกบล็อก และไม่ส่งข้อมูลผู้เข้าชมไปบุคคลที่สาม
ใช้:   python vendor_cdn.py            ดาวน์โหลด + แก้ลิงก์ (ต้องต่ออินเทอร์เน็ตบนเครื่องคุณ)
       python vendor_cdn.py --dry      แสดงว่าจะแก้อะไร ไม่ดาวน์โหลด/ไม่เขียนไฟล์
ปลอดภัย: สำรอง .html ที่จะแก้ไว้ proto/_deploy_backups/_backup_before_vendor_<วันที่>/ · รันซ้ำได้ · ดาวน์โหลดไม่ครบจะไม่แก้หน้าใดเลย
ถอยกลับ: คัดลอก .html จากโฟลเดอร์สำรองกลับมาทับ (ลบ assets/vendor ได้หรือจะทิ้งไว้ก็ได้)
หลังรัน: python site_smoke_test.py แล้ว git add 03_website && git commit && git push
"""
import os, re, sys, glob, shutil, time, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import preview_server as ps
SITE = ps.SITE; DRY = '--dry' in sys.argv
VEND = os.path.join(SITE, 'assets', 'vendor')
BK_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '_deploy_backups')   # proto/_deploy_backups (ไม่ถูก commit/เสิร์ฟ)
BK = os.path.join(BK_ROOT, '_backup_before_vendor_' + time.strftime('%Y%m%d'))
UA_MODERN = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

# (URL ในหน้า, ไฟล์ปลายทางใต้ assets/vendor)
LIBS = [
    ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'leaflet/leaflet.js'),
    ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', 'leaflet/leaflet.css'),
    ('https://unpkg.com/maplibre-gl@5.0.0/dist/maplibre-gl.js', 'maplibre/maplibre-gl.js'),
    ('https://unpkg.com/maplibre-gl@5.0.0/dist/maplibre-gl.css', 'maplibre/maplibre-gl.css'),
    ('https://unpkg.com/deck.gl@^9.0.0/dist.min.js', 'deckgl/dist.min.js'),
    ('https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js', 'hammerjs/hammer.min.js'),
    ('https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js', 'chartjs-plugin-zoom/chartjs-plugin-zoom.min.js'),
]
LEAFLET_IMAGES = ['layers.png', 'layers-2x.png', 'marker-icon.png', 'marker-icon-2x.png', 'marker-shadow.png']   # leaflet.css อ้างถึงด้วยพาธ images/
FONTS_URL = 'https://fonts.googleapis.com/css2?family=Noto+Serif+Thai:wght@500;600;700&family=IBM+Plex+Sans+Thai:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap'

def log(*a): print(('[dry] ' if DRY else '') + ' '.join(str(x) for x in a))
def get(url, ua=None):
    req = urllib.request.Request(url, headers={'User-Agent': ua or 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()
def put(rel, data):
    p = os.path.join(VEND, rel.replace('/', os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f: f.write(data)

pages = sorted(glob.glob(os.path.join(SITE, '*.html'))) + sorted(glob.glob(os.path.join(SITE, 'assets', 'embeds', '*.html')))
def prefix(path):
    rel = os.path.relpath(os.path.dirname(path), SITE)
    return 'assets/vendor/' if rel == '.' else '/'.join(['..'] * len(rel.split(os.sep))) + '/assets/vendor/'

# 1) ดาวน์โหลด (ถ้าพลาดข้อใด หยุดก่อนแก้หน้าใด ๆ)
fonts_css = None
if not DRY:
    try:
        for url, rel in LIBS:
            if os.path.exists(os.path.join(VEND, rel)) and os.path.getsize(os.path.join(VEND, rel)) > 1000: log('มีแล้ว', rel); continue
            d = get(url)
            if len(d) < 1000: raise RuntimeError('ไฟล์เล็กผิดปกติ: ' + url)
            put(rel, d); log('ดาวน์โหลด', rel, len(d) // 1024, 'KB')
        for im in LEAFLET_IMAGES:
            rel = 'leaflet/images/' + im
            if not os.path.exists(os.path.join(VEND, rel)): put(rel, get('https://unpkg.com/leaflet@1.9.4/dist/images/' + im)); log('ดาวน์โหลด', rel)
        css = get(FONTS_URL, UA_MODERN).decode('utf-8')
        def grab(m):
            u = m.group(1); name = re.sub(r'[^A-Za-z0-9_.\-]', '_', urllib.parse.urlparse(u).path.strip('/'))[-90:]
            rel = 'fonts/' + name
            if not os.path.exists(os.path.join(VEND, rel)): put(rel, get(u))
            return 'url(' + name + ')'
        fonts_css = re.sub(r'url\((https://fonts\.gstatic\.com/[^)]+)\)', grab, css)
        put('fonts/fonts.css', fonts_css.encode('utf-8')); log('ฟอนต์ → assets/vendor/fonts/fonts.css')
    except Exception as e:
        print('ดาวน์โหลดไม่สำเร็จ ไม่แก้หน้าใด ๆ:', e); sys.exit(1)

# 2) แก้ลิงก์ในหน้า
changed = 0
for p in pages:
    t = open(p, encoding='utf-8', newline='').read(); n = t; pre = prefix(p)
    for url, rel in LIBS: n = n.replace(url, pre + rel)
    n = n.replace(FONTS_URL, pre + 'fonts/fonts.css')
    n = re.sub(r'<link rel="preconnect" href="https://fonts\.(?:googleapis|gstatic)\.com"[^>]*>\s*', '', n)
    if n != t:
        rel = os.path.relpath(p, SITE); changed += 1; log('แก้', rel)
        if not DRY:
            dst = os.path.join(BK, rel)
            if not os.path.exists(dst): os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(p, dst)
            open(p, 'w', encoding='utf-8', newline='').write(n)
print('เสร็จ: แก้ %d หน้า' % changed + (' (dry-run)' if DRY else ' | สำรองที่ ' + os.path.relpath(BK, os.path.dirname(BK_ROOT))))
