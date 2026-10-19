"""standby_gate.py — ให้เครื่องสำรอง (เครื่อง 2) push เฉพาะตอนที่เครื่องหลักหยุด
ใช้โดย run_monitoring_data_builder.bat เมื่อมีไฟล์ standby.flag อยู่ข้างๆ (เฉพาะเครื่องสำรอง)

  python standby_gate.py [--max-age-min 45]
  exit 0 = monitoring.json บน origin/master เก่ากว่าเกณฑ์ (เครื่องหลักน่าจะหยุด) -> เครื่องนี้ควร push
  exit 1 = ยังสด (เครื่องหลัก/อื่นกำลัง push อยู่) หรือเช็คไม่ได้ -> เครื่องนี้ข้ามการ push รอบนี้

เหตุผล: สองเครื่อง push ไฟล์เดียวกันทุก 15 นาที = ชนกัน/merge commit รัวๆ (เคยเกิดตอน GitHub Actions รันคู่)
เครื่องสำรองยังรัน builder ตามปกติ แต่ push เฉพาะเมื่อเครื่องหลักไม่ push เกิน 45 นาที (พลาด ~3 รอบ)"""
import argparse, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]   # รากของ repo (pipeline -> scripts and code -> 01_data -> repo)

ap = argparse.ArgumentParser(); ap.add_argument('--max-age-min', type=float, default=45); a = ap.parse_args()
WATCH = '03_website/assets/data/monitoring.json'

def git(*args, timeout=90):
    return subprocess.run(['git', *args], capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))

try:
    f = git('fetch', 'origin', 'master')
    if f.returncode != 0:
        print('[standby_gate] fetch ไม่สำเร็จ ->', (f.stderr.strip().splitlines() or ['?'])[-1][:160], '-> ข้าม push'); sys.exit(1)
    r = git('log', '-1', '--format=%ct', 'origin/master', '--', WATCH)
    ts = int(r.stdout.strip() or 0)
except Exception as e:
    print('[standby_gate] เช็คไม่ได้:', e, '-> ข้าม push'); sys.exit(1)
if not ts:
    print('[standby_gate] ไม่พบประวัติ monitoring.json บน origin -> ให้ push'); sys.exit(0)
age = (time.time() - ts) / 60
print('[standby_gate] monitoring.json บน origin อายุ %.0f นาที (เกณฑ์ %.0f)' % (age, a.max_age_min))
sys.exit(0 if age > a.max_age_min else 1)
