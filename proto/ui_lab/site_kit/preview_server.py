"""
preview_server.py — พรีวิวเว็บ production (03_website) พร้อมชั้นธีม/ลูกเล่น โดย *ไม่แก้ไฟล์ production*
รัน:   python preview_server.py            (พอร์ต 8001)  แล้วเปิด http://localhost:8001/index.html
ทำงาน: ระหว่างส่ง .html จะ (1) แปลงสีเขียวน้ำทะเล/พื้นหลังที่ฮาร์ดโค้ดใน <style> และ style="" ให้เป็นตัวแปรธีม
       (2) แทรก theme-kit.css/js ท้ายหน้า   ไฟล์อื่น (json, รูป, js) ส่งตามเดิม
"""
import http.server, os, re, sys, socketserver
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, '..', '..', '..', '03_website'))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8001

def rgba(r, g, b): return re.compile(r'rgba\(\s*%d\s*,\s*%d\s*,\s*%d\s*,' % (r, g, b), re.I)
RULES = [
    (rgba(127, 224, 209), 'rgba(var(--t3-rgb),'), (rgba(69, 194, 173), 'rgba(var(--t4-rgb),'), (rgba(42, 157, 143), 'rgba(var(--t5-rgb),'),
    (rgba(224, 169, 79), 'rgba(var(--a4-rgb),'), (rgba(6, 22, 28), 'rgba(var(--bg950-rgb),'), (rgba(157, 201, 201), 'rgba(var(--bd-rgb),'), (rgba(255, 255, 255), 'rgba(var(--w-rgb),'), (rgba(8, 30, 38), 'rgba(var(--bg950-rgb),'),
]
HEX = {'#7fe0d1': 'var(--teal-300)', '#45c2ad': 'var(--teal-400)', '#2a9d8f': 'var(--teal-500)', '#e0a94f': 'var(--amber-400)', '#f0c47c': 'var(--amber-300)',
       '#06161c': 'var(--bg-950)', '#081e26': 'var(--bg-900)', '#0d2a34': 'var(--bg-800)', '#123643': 'var(--bg-700)', '#103743': 'var(--bg-glow-1)', '#0e2f2a': 'var(--bg-glow-2)',
       '#eef6f4': 'var(--text-100)', '#c4d6d3': 'var(--text-300)', '#8aa3a0': 'var(--text-500)', '#66807d': 'var(--text-600)', '#6fcf97': 'var(--ok-400)',
       '#f3a89f': 'var(--red-txt)', '#ff9f8a': 'var(--red-txt)', '#ff9d8e': 'var(--red-txt)', '#8fc4ff': 'var(--blue-txt)', '#e0a479': 'var(--orange-txt)', '#9d7fe0': 'var(--violet-txt)', '#0f2f38': 'var(--bg-800)'}
HEXRE = re.compile('|'.join(re.escape(k) for k in HEX), re.I)
def _conv(css):
    for rx, rep in RULES: css = rx.sub(rep, css)
    return HEXRE.sub(lambda m: HEX[m.group(0).lower()], css)

ROOTRE = re.compile(r'(:root\s*\{[^}]*\})', re.I)
def conv(css):
    # ห้ามแปลงภายใน :root {...} เพราะเป็นที่นิยามตัวแปรเอง (จะกลายเป็นอ้างอิงวนตัวเอง)
    return ''.join(p if i % 2 else _conv(p) for i, p in enumerate(ROOTRE.split(css)))

# รายการ kit ที่ฝังตามลำดับ (ลำดับสำคัญ) — เพิ่ม kit ใหม่ที่นี่ แล้วรัน deploy_to_production.py
KITS = ['theme-kit.js', 'page-kit.js', 'kwan-kit.js', 'hero-bg.js', 'inflow-kit.js', 'map-kit.js', 'flood-map-kit.js', 'flood-flow-kit.js', 'flood-3d-kit.js', 'flood-bathtub-kit.js', 'reliability-kit.js', 'flood-hero-kit.js', 'freshness-kit.js', 'ukm.js']

def ensure_kits(html, tag):
    """เติม <script> ของ kit ใหม่ที่ยังไม่มีในหน้า (หน้าที่ฝังไว้แล้ว) — แทรกก่อน ukm.js (ถ้ามี) ไม่งั้นก่อน </body>"""
    miss = [k for k in KITS if not re.search(r'uikit/' + re.escape(k) + r'[\"\'?]', html)]
    if not miss: return html
    add = ''.join(tag(k) for k in miss)
    m = re.search(r'<script src="[^"]*uikit/ukm\.js[^"]*"></script>', html)
    if m: return html[:m.start()] + add + html[m.start():]
    return html.replace('</body>', add + '</body>', 1) if '</body>' in html else html + add

def transform(html):
    if 'uikit/theme-kit.css' in html:   # หน้าที่ deploy_to_production.py ฝัง kit ไว้แล้ว → ชี้กลับมาใช้ kit ต้นทาง (แก้แล้วเห็นผลทันที) ไม่ฝังซ้ำ
        html = re.sub(r'(?:\.\./)*(?:assets/)uikit/([A-Za-z0-9_.\-]+?)(?:\?v=\d+)?(["\'])', r'/__uikit/\1\2', html)
        return ensure_kits(html, lambda k: '<script src="/__uikit/%s"></script>' % k)
    html = re.sub(r'(<style[^>]*>)(.*?)(</style>)', lambda m: m.group(1) + conv(m.group(2)) + m.group(3), html, flags=re.S | re.I)
    html = re.sub(r'style="([^"]*)"', lambda m: 'style="' + conv(m.group(1)) + '"', html)
    html = re.sub(r'(<script[^>]*src="assets/js/chart\.umd\.min\.js"[^>]*></script>)', r'\1<script src="/__uikit/chart-kit.js"></script>', html)
    inj = '<link rel="stylesheet" href="/__uikit/theme-kit.css">' + ''.join('<script src="/__uikit/%s"></script>' % k for k in KITS)
    return html.replace('</body>', inj + '</body>') if '</body>' in html else html + inj

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=SITE, **k)
    def log_message(self, *a): pass
    def _send(self, body, ctype):
        self.send_response(200); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        p = self.path.split('?')[0]
        if p.startswith('/__uikit/'):
            f = os.path.join(HERE, os.path.basename(p))
            if os.path.isfile(f): return self._send(open(f, 'rb').read(), 'text/css' if f.endswith('.css') else 'application/javascript')
            self.send_error(404); return
        if p == '/': p = '/index.html'
        f = os.path.join(SITE, p.lstrip('/').replace('/', os.sep))
        if p.endswith('.html') and os.path.isfile(f):
            return self._send(transform(open(f, encoding='utf-8').read()).encode('utf-8'), 'text/html; charset=utf-8')
        return super().do_GET()

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    print(f'พรีวิวธีม: http://localhost:{PORT}/index.html   (เสิร์ฟจาก {SITE})  กด Ctrl+C เพื่อหยุด')
    with socketserver.ThreadingTCPServer(('', PORT), H) as s: s.serve_forever()
