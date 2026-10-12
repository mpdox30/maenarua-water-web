"""
export_water_network.py — ส่งออกข้อมูล "ผังน้ำแบบอินเทอร์แอกทีฟ" จาก Supabase ของ community-dashboard มาเป็นไฟล์ JSON ของเว็บนี้
ได้: 03_website/assets/data/water_network.json  (nodes/edges ของผัง + แหล่งน้ำทั้ง 8 พร้อม %, หมู่/หมู่บ้าน, ประวัติรายวัน)
ใช้:   python export_water_network.py                       (อ่านคีย์จาก D:\\AI\\Community_dashboard\\maenaruea-dashboard\\.env)
       python export_water_network.py --env path\\to\\.env   (ระบุไฟล์ .env เอง)
ความปลอดภัย: ใช้เฉพาะ view สาธารณะแบบอ่านอย่างเดียว (anon key เดียวกับที่ฝังในเว็บ community-dashboard) · ไฟล์ผลลัพธ์ไม่มี URL/คีย์
รันซ้ำเมื่อ: แก้ผังน้ำ/เพิ่มแหล่งน้ำ หรืออยากอัปเดตค่า % ของแหล่งที่ไม่มีสถานีโทรมาตร (กรอกมือ)
หลังรัน: python deploy_to_production.py (ไม่จำเป็นถ้าไม่ได้แก้ kit) แล้ว git add 03_website && commit && push
"""
import os, sys, json, argparse, datetime as dt, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import preview_server as ps

ap = argparse.ArgumentParser(); ap.add_argument('--env', default=r'D:\AI\Community_dashboard\maenaruea-dashboard\.env'); a = ap.parse_args()
env = {}
for ln in open(a.env, encoding='utf-8'):
    ln = ln.strip()
    if ln and not ln.startswith('#') and '=' in ln:
        k, v = ln.split('=', 1); env[k.strip()] = v.strip().strip('"\'')
URL = env.get('VITE_SUPABASE_URL', '').rstrip('/'); KEY = env.get('VITE_SUPABASE_ANON_KEY', ''); SLUG = env.get('VITE_TAMBON_SLUG', 'mae-na-ruea')
if not URL or not KEY: sys.exit('ไม่พบ VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY ใน ' + a.env)

def get(view, **q):
    """อ่านทุกหน้า (PostgREST จำกัด 1000 แถว/ครั้ง)"""
    out, off = [], 0
    while True:
        qs = urllib.parse.urlencode({k: v for k, v in q.items()})
        req = urllib.request.Request('%s/rest/v1/%s?%s' % (URL, view, qs), headers={'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Range-Unit': 'items', 'Range': '%d-%d' % (off, off + 999)})
        with urllib.request.urlopen(req, timeout=60) as r: rows = json.loads(r.read().decode('utf-8'))
        out += rows
        if len(rows) < 1000: return out
        off += 1000

tb = get('v_tambons_public', select='*', slug='eq.' + SLUG)
if not tb: sys.exit('ไม่พบตำบล slug=' + SLUG)
tid = tb[0]['tambon_id']; print('ตำบล', tb[0].get('name_th') or SLUG)
nodes = get('nw_diagram_current_nodes', select='*', tambon_id='eq.%s' % tid)
edges = get('nw_diagram_current_edges', select='*', tambon_id='eq.%s' % tid)
srcs = get('v_water_sources_public', select='*', tambon_id='eq.%s' % tid, order='display_order.asc.nullsfirst')
risk = {r['source_id']: r for r in get('v_source_risk_forecast', select='*', tambon_id='eq.%s' % tid)}
ids = [s['source_id'] for s in srcs if s.get('source_role') == 'storage']
since = (dt.date.today() - dt.timedelta(days=120)).isoformat()
daily = get('v_water_level_daily_public', select='source_id,reading_date,level_pct', source_id='in.(%s)' % ','.join(ids), reading_date='gte.' + since, order='reading_date.asc') if ids else []
hist = {}
for r in daily:
    if r.get('level_pct') is not None: hist.setdefault(r['source_id'], []).append({'iso': r['reading_date'], 'pct': round(float(r['level_pct']), 1)})

def num(x, n=None):
    if x is None: return None
    x = float(x); return round(x, n) if n is not None else x
out_src = []
for s in srcs:
    rk = risk.get(s['source_id'], {}); cap = num(s.get('stored_capacity_m3')); pct = num(rk.get('current_pct'))
    out_src.append({'id': s['source_id'], 'ref': s.get('curve_node_key'), 'name': s.get('name_th'), 'nameEn': s.get('name_en'), 'role': s.get('source_role'), 'type': s.get('source_type'),
                    'moo': s.get('moo'), 'village': s.get('village_name_th'), 'isolated': bool(s.get('is_isolated')), 'maxM3': cap, 'pct': round(pct, 1) if pct is not None else None,
                    'm3': round(pct / 100 * cap) if pct is not None and cap else None, 'dW': num(rk.get('dw_value'), 2), 'currentDate': rk.get('current_date'),
                    'history': hist.get(s['source_id'], [])})
doc = {'generated_at': dt.datetime.now().isoformat(timespec='seconds'), 'tambon': tb[0].get('name_th') or SLUG, 'sources': out_src,
       'nodes': [{k: n.get(k) for k in ('node_key', 'label', 'node_type', 'rotation', 'dir', 'source_ref', 'status', 'pos_x', 'pos_y')} for n in nodes],
       'edges': [{k: e.get(k) for k in ('edge_key', 'source_node_key', 'target_node_key', 'label', 'edge_type', 'engine_straight', 'engine_bend', 'seg_dist', 'seg_weight')} for e in edges]}
dst = os.path.join(ps.SITE, 'assets', 'data', 'water_network.json')
with open(dst, 'w', encoding='utf-8', newline='\n') as f: json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
print('บันทึก', os.path.relpath(dst, ps.SITE), '| nodes', len(nodes), 'edges', len(edges), 'sources', len(out_src), '| ref ที่ผูกแล้ว', sum(1 for n in nodes if n.get('source_ref')))
