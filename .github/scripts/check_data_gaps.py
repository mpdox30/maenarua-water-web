# -*- coding: utf-8 -*-
"""check_data_gaps.py — ตรวจ "ช่องว่าง" ในข้อมูลที่ต้องสะสมต่อเนื่อง (อ่านอย่างเดียว ไม่แก้ไฟล์)
ต่างจาก check_data_freshness.py (ดูว่าไฟล์เว็บสดไหม): ตัวนี้ดูว่า "มีวันไหนขาดหายไปแล้วกู้ไม่ได้/ต้องเติม" หรือไม่

ตรวจ 2 อย่าง
  1) archive_live (ค่าพยากรณ์ที่ออกจริงรายวัน — สร้างโดย colab_migration/archive_live_outputs.py): วันที่ขาดระหว่างไฟล์แรก→วันนี้ (เวลาไทย)
     วันที่รู้และยอมรับแล้วให้ใส่ใน 01_data/archive_live/KNOWN_GAPS.txt (บรรทัดละ YYYY-MM-DD, # = คอมเมนต์)
  2) โทรมาตร Google Sheet (wide_log) ย้อนหลัง N วัน: ช่องว่างระหว่างแถวที่ยาวกว่าเกณฑ์ (ปกติ poll ทุก 10 นาที)
     ระบุแหล่งด้วย --sheet-csv <URL หรือไฟล์> | env RESERVOIR_TELEMETRY_SHEET_CSV_URL | ค่า default ใน pipeline/reservoir_telemetry_from_sheet.py
     (ถ้าอ่านไม่ได้ จะแจ้ง "ข้าม" ไม่ถือว่าผิด)
ใช้:  python .github/scripts/check_data_gaps.py [--web .] [--days 14] [--gap-min 30] [--sheet-csv URL|ไฟล์.csv]
exit code: 0 = ไม่พบช่องว่างใหม่ · 1 = พบช่องว่าง (Colab ใช้พิมพ์เตือนท้ายรอบ ไม่ควรให้งานล้ม)"""
import argparse, csv, io, os, re, sys, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TH = timezone(timedelta(hours=7))
ap = argparse.ArgumentParser(); ap.add_argument('--web', default='.'); ap.add_argument('--days', type=int, default=14)
ap.add_argument('--gap-min', type=int, default=30); ap.add_argument('--sheet-csv'); a = ap.parse_args()
web = Path(a.web); A = web / '01_data' / 'archive_live'; today = datetime.now(TH).date(); problems = []


def dates_in(folder: Path, rx: str):
    out = set()
    for f in folder.glob('*') if folder.exists() else []:
        m = re.search(rx, f.name)
        if m:
            try: out.add(date.fromisoformat(m.group(1)))
            except ValueError: pass
    return out


known = set()
kg = A / 'KNOWN_GAPS.txt'
if kg.exists():
    for ln in kg.read_text(encoding='utf-8').splitlines():
        ln = ln.split('#')[0].strip()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', ln): known.add(date.fromisoformat(ln))

print('== 1) archive_live (ค่าพยากรณ์ที่ออกจริงรายวัน) ==')
for name, sub, rx in [('พยากรณ์ WMB/กว๊าน', 'wmb_forecast', r'(\d{4}-\d{2}-\d{2})\.csv$'),
                      ('latest.json', 'latest', r'(\d{4}-\d{2}-\d{2})\.json\.gz$'),
                      ('flood_latest.json', 'flood_latest', r'(\d{4}-\d{2}-\d{2})\.json\.gz$')]:
    ds = dates_in(A / sub, rx)
    if not ds:
        print(f'  - {name}: ยังไม่มีไฟล์ใน archive_live/{sub} (ยังไม่เคยรัน archive_live_outputs.py?)'); continue
    d0 = min(ds); miss = [d0 + timedelta(i) for i in range((today - d0).days + 1) if (d0 + timedelta(i)) not in ds]
    new = [d for d in miss if d not in known and d != today]
    tdy = today in miss
    print(f'  {"!!" if new else "OK"} {name}: {len(ds)} วัน ({d0} → {max(ds)}) ขาด {len([d for d in miss if d != today])} วัน'
          + (f' (ยอมรับแล้ว {len([d for d in miss if d in known])})' if known & set(miss) else '') + ('  · วันนี้ยังไม่มี' if tdy else ''))
    if new:
        problems.append(f'{name}: ขาด {", ".join(str(d) for d in new[:10])}' + (' ...' if len(new) > 10 else ''))
        print('     ขาดวันที่: ' + ', '.join(str(d) for d in new[:15]) + (' ...' if len(new) > 15 else ''))
wn = sorted((A / 'weathernext').glob('forecast_*.csv')) if (A / 'weathernext').exists() else []
print(f'  - พยากรณ์ฝน WeatherNext: {len(wn)} ไฟล์' + (f' (ล่าสุด {wn[-1].name})' if wn else ' (ไม่มี — Colab อาจไม่ได้ดึง WeatherNext; ไม่นับเป็นช่องว่าง)'))

print('== 2) โทรมาตร Google Sheet ==')
src = a.sheet_csv or os.environ.get('RESERVOIR_TELEMETRY_SHEET_CSV_URL')
if not src:
    try:
        sys.path.insert(0, str(web / '01_data' / 'scripts and code' / 'pipeline'))
        import reservoir_telemetry_from_sheet as rts; src = rts.DEFAULT_SHEET_CSV_URL
    except Exception: src = None
text = None
if src:
    try:
        if re.match(r'https?://', src):
            with urllib.request.urlopen(src, timeout=60) as r: text = r.read().decode('utf-8-sig')
        else: text = Path(src).read_text(encoding='utf-8-sig')
    except Exception as e:
        print(f'  - ข้าม: อ่านชีตไม่ได้ ({e.__class__.__name__})')
else:
    print('  - ข้าม: ไม่ระบุแหล่งชีต (--sheet-csv หรือ RESERVOIR_TELEMETRY_SHEET_CSV_URL)')
if text:
    rx = re.compile(r'^(\d+)-(\d+)-(\d+)\s+(\d+):(\d+)')
    ts = []
    for r in csv.DictReader(io.StringIO(text)):
        m = rx.match((r.get('measure_datetime') or '').strip())
        if m: ts.append(datetime(*map(int, m.groups()), tzinfo=TH))
    if not ts: print('  - ข้าม: ไม่พบคอลัมน์ measure_datetime ในชีตที่อ่านมา (ผิดแท็บ/ว่าง?)')
    else:
        ts = sorted(set(ts)); end = datetime.now(TH); beg = end - timedelta(days=a.days); win = [t for t in ts if t >= beg]
        gaps = [(x, y) for x, y in zip(win, win[1:]) if (y - x) > timedelta(minutes=a.gap_min)]
        tail = end - ts[-1]
        print(f'  แถวล่าสุด {ts[-1]:%Y-%m-%d %H:%M} (อายุ {tail.total_seconds() / 3600:.1f} ชม.) · ช่วงที่ตรวจ {a.days} วัน {len(win)} แถว · ช่องว่าง >{a.gap_min} นาที: {len(gaps)}')
        if tail > timedelta(hours=2): problems.append(f'โทรมาตร: แถวล่าสุดเก่า {tail.total_seconds() / 3600:.1f} ชม. (Apps Script หยุด?)')
        for x, y in sorted(gaps, key=lambda g: g[1] - g[0], reverse=True)[:8]:
            print(f'    !! {x:%m-%d %H:%M} → {y:%m-%d %H:%M} ({(y - x).total_seconds() / 3600:.1f} ชม.)')
        if gaps: problems.append(f'โทรมาตร: ช่องว่าง {len(gaps)} จุด (ยาวสุด {max((y - x).total_seconds() for x, y in gaps) / 3600:.1f} ชม.)')

print('\nสรุป: ' + ('พบช่องว่าง → ' + ' | '.join(problems) if problems else 'ไม่พบช่องว่างใหม่'))
sys.exit(1 if problems else 0)
