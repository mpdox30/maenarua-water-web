# -*- coding: utf-8 -*-
"""archive_live_outputs.py — เก็บสำเนา "ค่าพยากรณ์ที่ออกจริงรายวัน" ลง git ก่อนที่จะหาย/ถูกทับ

ทำไมต้องมี (2026-10-14): ข้อมูลโทรมาตรอยู่ใน Google Sheet + archive รายเดือน (ย้อนหลังได้เสมอ) แต่ "ค่าพยากรณ์ที่ออกจริง
ณ วันนั้น" กู้ย้อนหลังไม่ได้ (ข้อมูลฝนพยากรณ์/ผลโมเดลของวันนั้นเปลี่ยนไปแล้ว) และ Colab รันบนสำเนา repo ชั่วคราวที่หายตอนจบ
session — ผลของ WMB (09_live/output/forecast_*.csv) จึงหายถ้าวันนั้นรันแค่ Colab (เคยขาด 2026-09-09 และ 2026-10-10)

เก็บอะไร (ไปที่ <web>/01_data/archive_live/ — ไฟล์เล็ก ไม่ทับของเดิม ชื่อไฟล์อิงวันที่):
  latest/latest_YYYY-MM-DD.json.gz            ← 03_website/assets/data/latest.json (พยากรณ์ความต้องการน้ำ + น้ำไหลลงอ่าง h1-h7) วันตามเวลาไทยของ run_timestamp
  flood_latest/flood_latest_YYYY-MM-DD.json.gz ← flood_latest.json (พยากรณ์กว๊าน/น้ำล้น 7 วัน) วันตาม base_date
  wmb_forecast/forecast_YYYY-MM-DD.csv        ← <wmb>/09_live/output/forecast_*.csv (ผล WMB รายวัน)
  weathernext/forecast_YYYYMMDD_HHZ.csv       ← <wmb>/01_raw_data/rainfall/weathernext_archive/*.csv (พยากรณ์ฝนตามที่ออกจริง)

ใช้:
  python archive_live_outputs.py --web <root repo เว็บ> [--wmb <root repo WMB_Phayao>] [--dry-run] [--force]
  Colab: รันใน Cell 12 ก่อน git add (ดู DAILY_RUNBOOK.md) · Windows: รันมือครั้งเดียวเพื่อเก็บของเก่าที่ยังอยู่บนดิสก์
ปลอดภัยรันซ้ำ: ไม่ทับไฟล์ที่มีแล้ว (ยกเว้น --force) · ไม่มี wmb ก็ข้ามส่วน WMB/WeatherNext"""
import argparse, gzip, json, re, shutil, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TH = timezone(timedelta(hours=7))


def _gz_json(src: Path) -> bytes:
    raw = src.read_bytes()
    json.loads(raw.decode('utf-8'))      # ต้องเป็น JSON ที่อ่านได้จริง (กันบันทึกไฟล์เสีย)
    import io
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0, compresslevel=9) as g:
        g.write(raw)
    return buf.getvalue()


def archive(web, wmb=None, dry=False, force=False, log=print):
    web = Path(web); A = web / '01_data' / 'archive_live'; data = web / '03_website' / 'assets' / 'data'
    st = {'new': [], 'have': 0, 'skip': []}

    def put(dest: Path, writer):
        if dest.exists() and not force:
            st['have'] += 1; return
        if not dry:
            dest.parent.mkdir(parents=True, exist_ok=True); writer(dest)
        st['new'].append(str(dest.relative_to(A)))

    # 1) latest.json  (วันตามเวลาไทยของ run_timestamp)
    p = data / 'latest.json'
    try:
        j = json.loads(p.read_text(encoding='utf-8'))
        t = datetime.fromisoformat(str(j['run_timestamp']).replace('Z', '+00:00'))
        d = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(TH).date()
        put(A / 'latest' / f'latest_{d}.json.gz', lambda dst: dst.write_bytes(_gz_json(p)))
    except Exception as e:
        st['skip'].append(f'latest.json: {e.__class__.__name__}: {e}')
    # 2) flood_latest.json  (วันตาม base_date)
    p = data / 'flood_latest.json'
    try:
        j = json.loads(p.read_text(encoding='utf-8')); d = str(j['base_date'])[:10]
        datetime.strptime(d, '%Y-%m-%d')
        put(A / 'flood_latest' / f'flood_latest_{d}.json.gz', lambda dst: dst.write_bytes(_gz_json(p)))
    except Exception as e:
        st['skip'].append(f'flood_latest.json: {e.__class__.__name__}: {e}')
    # 3) WMB รายวัน + 4) WeatherNext
    if wmb:
        wmb = Path(wmb)
        for f in sorted((wmb / '09_live' / 'output').glob('forecast_*.csv')):
            if re.fullmatch(r'forecast_\d{4}-\d{2}-\d{2}\.csv', f.name):
                put(A / 'wmb_forecast' / f.name, lambda dst, f=f: shutil.copy2(f, dst))
        for f in sorted((wmb / '01_raw_data' / 'rainfall' / 'weathernext_archive').glob('forecast_*.csv')):
            put(A / 'weathernext' / f.name, lambda dst, f=f: shutil.copy2(f, dst))
    else:
        st['skip'].append('ไม่ได้ระบุ --wmb: ข้าม WMB/WeatherNext')
    log(f"archive_live: ไฟล์ใหม่ {len(st['new'])} · มีอยู่แล้ว {st['have']}" + (' (dry-run)' if dry else ''))
    for n in st['new'][:12]: log('  + ' + n)
    if len(st['new']) > 12: log(f"  ... อีก {len(st['new']) - 12} ไฟล์")
    for s in st['skip']: log('  ! ' + s)
    return st


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--web', required=True); ap.add_argument('--wmb'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    archive(a.web, a.wmb, a.dry_run, a.force)
