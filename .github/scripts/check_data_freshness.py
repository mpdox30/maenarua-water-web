# -*- coding: utf-8 -*-
"""ตรวจความสดของไฟล์ข้อมูลที่เว็บใช้ (อ่านอย่างเดียว ไม่แก้/ไม่ push อะไร)
ใช้:  python .github/scripts/check_data_freshness.py [--json] [--site 03_website]
ผลลัพธ์: พิมพ์ตารางสถานะ; ถ้ามีไฟล์เก่าเกินเกณฑ์ → exit code 1 และเขียนรายงาน markdown ไว้ที่ $FRESH_REPORT (ถ้าตั้งค่า)
เวลาในไฟล์: flood_latest.generated_at / latest.run_timestamp = UTC ; monitoring.meta.updated / inflow_6h_display.computed_at = เวลาไทย (UTC+7)"""
import json, os, subprocess, sys
from datetime import datetime, timedelta, timezone
TH = timezone(timedelta(hours=7))
site = sys.argv[sys.argv.index('--site') + 1] if '--site' in sys.argv else '03_website'
D = os.path.join(site, 'assets', 'data')

def load(f):
    with open(os.path.join(D, f), encoding='utf-8') as fh: return json.load(fh)
def utc(s):
    s = str(s).replace('Z', '+00:00').replace(' ', 'T')
    t = datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
def th(s):
    t = datetime.fromisoformat(str(s).replace(' ', 'T'))
    return t if t.tzinfo else t.replace(tzinfo=TH)
def commit_time(path):
    try:
        r = subprocess.run(['git', 'log', '-1', '--format=%ct', '--', path], capture_output=True, text=True, timeout=60)
        return datetime.fromtimestamp(int(r.stdout.strip()), timezone.utc)
    except Exception: return None

# (ชื่อ, ฟังก์ชันอ่านเวลาล่าสุด, เกณฑ์เก่าสุดที่ยอมรับ ชม., คำอธิบายผลกระทบ)
CHECKS = [
    ('flood_latest.json', lambda: utc(load('flood_latest.json')['generated_at']), 36, 'พยากรณ์น้ำท่วม/กว๊าน (Colab รายวัน)'),
    ('latest.json', lambda: utc(load('latest.json')['run_timestamp']), 36, 'ผลหลักรายวัน/พยากรณ์ความต้องการน้ำ (Colab รายวัน)'),
    ('monitoring.json', lambda: th(load('monitoring.json')['meta']['updated']), 12, 'สถานการณ์น้ำสด (ทุก 15 นาที; เครื่อง Windows ปิดตอนกลางคืนได้)'),
    ('inflow_6h_display.json', lambda: th(load('inflow_6h_display.json')['computed_at']), 12, 'น้ำไหลลงอ่างราย 6 ชม. (ทุก 15 นาที)'),
    ('reservoir_inflow.json', lambda: commit_time(os.path.join(D, 'reservoir_inflow.json')), 60, 'ประวัติน้ำไหลลงอ่าง (อัปเดตเมื่อ Colab รายวันผ่าน)'),
]
now = datetime.now(timezone.utc)
rows, stale = [], []
for name, fn, limit, what in CHECKS:
    try:
        t = fn()
        age = (now - t).total_seconds() / 3600 if t else None
        ok = age is not None and age <= limit
        err = None if t else 'อ่านเวลาไม่ได้'
    except Exception as e:
        t, age, ok, err = None, None, False, f'อ่านไฟล์ไม่ได้: {e.__class__.__name__}'
    rows.append((name, t, age, limit, ok, err, what))
    if not ok: stale.append(rows[-1])

for name, t, age, limit, ok, err, what in rows:
    ts = t.astimezone(TH).strftime('%Y-%m-%d %H:%M') + ' (ไทย)' if t else '-'
    print(f"{'OK ' if ok else 'STALE'} {name:24s} {ts:24s} อายุ {('%.1f ชม.' % age) if age is not None else '-':>10s} / เกณฑ์ {limit} ชม.  {err or ''}")

rep = os.environ.get('FRESH_REPORT')
if rep:
    with open(rep, 'w', encoding='utf-8') as f:
        if stale:
            f.write('ตรวจพบข้อมูลบนเว็บไม่อัปเดตตามเกณฑ์ (ตรวจเมื่อ %s ไทย)\n\n| ไฟล์ | อัปเดตล่าสุด (ไทย) | อายุ | เกณฑ์ | ผลกระทบ |\n|---|---|---|---|---|\n' % now.astimezone(TH).strftime('%Y-%m-%d %H:%M'))
            for name, t, age, limit, ok, err, what in stale:
                f.write('| `%s` | %s | %s | %s ชม. | %s |\n' % (name, t.astimezone(TH).strftime('%Y-%m-%d %H:%M') if t else '-', ('%.1f ชม.' % age) if age is not None else (err or '-'), limit, what))
            f.write('\nแนวทางตรวจ: ดูแท็บ Actions ว่า deploy ผ่านไหม · Colab รายวันรันแล้วหรือยัง · งาน Windows (Task Scheduler) ทำงานอยู่ไหม\n')
sys.exit(1 if stale else 0)
