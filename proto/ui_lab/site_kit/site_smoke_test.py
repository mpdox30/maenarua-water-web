"""
site_smoke_test.py — ตรวจเว็บ 03_website หลัง deploy (ไม่ต้องใช้อินเทอร์เน็ต ไม่แก้ไฟล์)
ใช้:  python site_smoke_test.py
ตรวจ: 1) ทุกหน้า .html มี kit ครบ และ ?v= เท่ากันทั้งเว็บ
      2) ไฟล์ local ที่หน้าอ้างถึง (src/href) มีอยู่จริง
      3) ไฟล์ .json / .geojson ใน assets/data อ่านได้
      4) ข้อมูลสด: flood_latest.json / monitoring.json ไม่เก่าเกินเกณฑ์
ผลลัพธ์: พิมพ์ FAIL/WARN/OK  — exit code 1 ถ้ามี FAIL
"""
import os, re, sys, json, glob, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import preview_server as ps
SITE = ps.SITE
fails, warns = [], []
def fail(m): fails.append(m); print('FAIL', m)
def warn(m): warns.append(m); print('WARN', m)

pages = sorted(glob.glob(os.path.join(SITE, '*.html')))
if not pages: fail('ไม่พบหน้า .html ใน ' + SITE)
vers = set(); outside = {}
URLRE = re.compile(r'(?:src|href)\s*=\s*["\']([^"\'#?]+)(\?[^"\']*)?["\']', re.I)
for p in pages:
    rel = os.path.relpath(p, SITE); t = open(p, encoding='utf-8').read()
    if 'uikit/theme-kit.css' not in t: fail(rel + ': ยังไม่ฝัง kit'); continue
    for k in ps.KITS:
        if not re.search(r'uikit/' + re.escape(k) + r'[\"\'?]', t): fail('%s: ขาด %s' % (rel, k))
    vers |= set(re.findall(r'uikit/[A-Za-z0-9_.\-]+\?v=(\d+)', t))
    for m in URLRE.finditer(t):
        u = m.group(1)
        if re.match(r'^(https?:|//|mailto:|tel:|data:|javascript:)', u) or u.startswith('/__'): continue
        f = os.path.normpath(os.path.join(os.path.dirname(p), u))
        if not f.startswith(SITE): outside[rel] = outside.get(rel, 0) + 1; continue
        if not os.path.exists(f): fail('%s: ไม่พบไฟล์ %s' % (rel, u))
for r_, c_ in outside.items(): warn('%s: มี %d ลิงก์ชี้นอกโฟลเดอร์เว็บ (ไฟล์เอกสารวิจัย) — ไม่ตรวจ' % (r_, c_))
if len(vers) > 1: warn('?v= ไม่เท่ากันทั้งเว็บ: ' + ', '.join(sorted(vers)) + ' (รัน deploy_to_production.py ใหม่)')
kit_dir = os.path.join(SITE, 'assets', 'uikit')
for k in ps.KITS + ['theme-kit.css']:
    a, b = os.path.join(HERE, k), os.path.join(kit_dir, k)
    if not os.path.exists(b): fail('assets/uikit ขาด ' + k)
    elif open(a, 'rb').read() != open(b, 'rb').read(): warn(k + ': ต่างจากต้นทาง site_kit (ยังไม่ได้ deploy ล่าสุด)')

for f in glob.glob(os.path.join(SITE, 'assets', 'data', '*.json')) + glob.glob(os.path.join(SITE, 'assets', 'data', '*.geojson')):
    try: json.load(open(f, encoding='utf-8'))
    except Exception as e: fail('JSON อ่านไม่ได้ %s (%s)' % (os.path.basename(f), e))

def age_h(ts):
    return (dt.datetime.utcnow() - ts).total_seconds() / 3600
try:
    j = json.load(open(os.path.join(SITE, 'assets', 'data', 'flood_latest.json'), encoding='utf-8'))
    g = dt.datetime.fromisoformat(str(j['generated_at']).replace('Z', '').replace(' ', 'T')[:19])
    a = age_h(g); (fail if a > 54 else warn if a > 30 else print)(('พยากรณ์รายวันเก่า %.1f ชม.' % a) if a > 30 else 'OK  พยากรณ์รายวันอายุ %.1f ชม.' % a)
except Exception as e: fail('อ่าน flood_latest.json ไม่ได้: %s' % e)
try:
    j = json.load(open(os.path.join(SITE, 'assets', 'data', 'monitoring.json'), encoding='utf-8'))
    u = dt.datetime.fromisoformat(str(j['meta']['updated']).replace('Z', '').replace(' ', 'T')[:19]) - dt.timedelta(hours=7)   # เวลาไทย → UTC
    a = age_h(u); (fail if a > 12 else warn if a > 2 else print)(('ข้อมูลสถานีเก่า %.1f ชม.' % a) if a > 2 else 'OK  ข้อมูลสถานีอายุ %.1f ชม.' % a)
except Exception as e: fail('อ่าน monitoring.json ไม่ได้: %s' % e)

print('\nหน้าที่ตรวจ: %d | FAIL %d | WARN %d' % (len(pages), len(fails), len(warns)))
sys.exit(1 if fails else 0)
