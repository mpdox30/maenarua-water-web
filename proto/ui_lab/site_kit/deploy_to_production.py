"""
deploy_to_production.py — ปล่อยชั้นธีม/ลูกเล่น (site_kit) ขึ้นเว็บจริง 03_website
ใช้:   python deploy_to_production.py            ปล่อย/อัปเดตทั้งหมด (ปลอดภัย รันซ้ำได้)
       python deploy_to_production.py --dry      ดูว่าจะทำอะไร ไม่เขียนไฟล์
สิ่งที่ทำ
  1) สำรอง .html ต้นฉบับครั้งแรกไว้ที่ 03_website/_backup_before_uikit_<วันที่>/  (ไม่ทับถ้ามีแล้ว)
  2) คัดลอก kit (*.js, *.css, hero_contours.json) ไป 03_website/assets/uikit/
  3) หน้า .html ที่ยังไม่เคยฝัง: แปลงสี + แทรก <link>/<script> (พาธ assets/uikit/…?v=<เวลา>)
     หน้าที่ฝังแล้ว: แค่เปลี่ยน ?v= เพื่อให้เบราว์เซอร์โหลดไฟล์ kit ใหม่
ถอยกลับทั้งหมด: คัดลอกไฟล์จาก _backup_before_uikit_*/ กลับมาทับ แล้วลบ assets/uikit/
หลังรัน: git add 03_website && git commit && git push   (GitHub Pages จะอัปเดตเอง)
"""
import os, re, sys, shutil, time, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import preview_server as ps
SITE = ps.SITE
DRY = '--dry' in sys.argv
VER = time.strftime('%Y%m%d%H%M')
DEST = os.path.join(SITE, 'assets', 'uikit')
BK = os.path.join(SITE, '_backup_before_uikit_' + time.strftime('%Y%m%d'))
MARK = 'uikit/theme-kit.css'

def log(*a): print(('[dry] ' if DRY else '') + ' '.join(str(x) for x in a))

def pages():
    out = sorted(glob.glob(os.path.join(SITE, '*.html')))
    emb = os.path.join(SITE, 'assets', 'embeds')
    if os.path.isdir(emb): out += sorted(glob.glob(os.path.join(emb, '*.html')))
    return out

def prefix_for(path):  # พาธไป assets/uikit/ จากตำแหน่งไฟล์
    rel = os.path.relpath(os.path.dirname(path), SITE)
    return 'assets/uikit/' if rel == '.' else '/'.join(['..'] * len(rel.split(os.sep))) + '/assets/uikit/'

def read(p):
    with open(p, encoding='utf-8', newline='') as f: return f.read()
def write(p, s):
    with open(p, 'w', encoding='utf-8', newline='') as f: f.write(s)

# 1) สำรอง
existing_bk = glob.glob(os.path.join(SITE, '_backup_before_uikit_*'))
if existing_bk: BK = existing_bk[0]
for p in pages():
    t = read(p)
    if MARK in t: continue
    rel = os.path.relpath(p, SITE)
    dst = os.path.join(BK, rel)
    if not os.path.exists(dst):
        log('backup', rel)
        if not DRY: os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(p, dst)

# 2) คัดลอก kit
if not DRY: os.makedirs(DEST, exist_ok=True)
for f in sorted(os.listdir(HERE)):
    if not (f.endswith(('.js', '.css')) or f == 'hero_contours.json'): continue
    src = os.path.join(HERE, f)
    data = open(src, 'rb').read()
    log('kit', f)
    if not DRY: open(os.path.join(DEST, f), 'wb').write(data)

# 3) หน้า html
for p in pages():
    t = read(p); rel = os.path.relpath(p, SITE); pre = prefix_for(p)
    if MARK in t:
        n = ps.ensure_kits(t, lambda k: '<script src="%s%s"></script>' % (pre, k))   # kit ใหม่ที่เพิ่มภายหลัง
        n = re.sub(r'(uikit/[A-Za-z0-9_.\-]+?\.(?:js|css))(\?v=\d+)?(["\'])', lambda m: m.group(1) + '?v=' + VER + m.group(3), n)
        log('bump ', rel, '(+kit ใหม่)' if 'freshness-kit' not in t else '')
        if not DRY and n != t: write(p, n)
        continue
    n = ps.transform(t)
    n = n.replace('/__uikit/', pre)
    n = re.sub(r'(uikit/[A-Za-z0-9_.\-]+?\.(?:js|css))(["\'])', lambda m: m.group(1) + '?v=' + VER + m.group(2), n)
    log('inject', rel)
    if not DRY: write(p, n)
print('เสร็จ  เวอร์ชัน kit =', VER, '| สำรองที่', os.path.relpath(BK, SITE))
