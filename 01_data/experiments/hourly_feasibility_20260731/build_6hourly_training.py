# -*- coding: utf-8 -*-
"""
สร้างชุด training ราย 6 ชั่วโมง (4 จุด/วัน: 01:00, 07:00, 13:00, 19:00 -- ยึด 07:00 เป็นจุดยึดเดิม
ของระบบ) แทนรายวัน โดย reproduce สูตร water balance เดียวกับ reservoir_water_balance.py::
compute_daily_row() ทุกจุด แค่เปลี่ยนหน่วยเวลาจาก 24 ชม. เป็น 6 ชม.:

    Q_in_6h = ΔStorage_6h - R_runoff_6h + Release_6h + Spill_6h + Evap_6h + Infiltration_6h
    (floor ที่ 0 เหมือนเดิม)

ระดับน้ำใช้ MA 6 ชม. แบบ trailing (ไม่ look-ahead) ตามผลทดสอบ smoothing ก่อนหน้า (signal:noise
ดีที่สุดที่ MA 6h = 1.71) -- สปิลเวย์คำนวณจากระดับดิบ (ไม่ smooth) รายชั่วโมงจริงในหน้าต่าง 6 ชม.
(สูตร weir เป็น non-linear, ไม่ควร smooth ก่อนเข้าสูตร)

Release: refined ใช้ RELEASE_EVENTS (multi-event timeline จาก log การปล่อยน้ำจริง 9 เหตุการณ์ +
release_events.csv แปลง "จำนวนรอบที่เปิดวาล์ว" -> m3/day ด้วย flow_rate_spillway/inlet.csv --
ดู comment ที่ RELEASE_EVENTS ด้านล่าง) หาร 4 เป็น per-6h (ยังสมมติอัตราคงที่ตลอดช่วง event
เพราะไม่มีข้อมูลย่อยกว่านั้น)

Evap/Infiltration: ไม่มีข้อมูลย่อยรายชั่วโมงจริง -- ประมาณเป็นอัตรารายวัน/4 (สมมติฐานคงที่
ตลอดวัน -- ข้อจำกัดที่ต้องรู้ โดยเฉพาะ Evap ที่จริงมี diurnal cycle) -- ผู้ใช้ยืนยันแล้วว่าใช้วิธีนี้ได้

API_t: decay constant ปรับจาก RESERVOIR_API_K=0.95 (ต่อวัน) เป็น 0.95^(1/4)=0.9873 (ต่อ 6 ชม.)
เพื่อให้ decay ต่อวันเท่าเดิมถ้าคูณ 4 รอบ

ไม่แตะไฟล์ deploy ใดๆ ทำในโฟลเดอร์นี้ทั้งหมด
"""
import calendar
import csv
import os
from datetime import datetime, timedelta

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- ค่าคงที่ (คัดลอกจาก reservoir_water_balance.py ตรงตัว) ----------
SPILLWAY_LEVEL_ADJ_OFFSET_M = 0.155
SPILLWAY_CREST_LEVEL_MSL = 489.545
SPILLWAY_WEIR_COEFFICIENT_C = 1.82
SPILLWAY_WEIR_LENGTH_M = 30
MONTHLY_EVAP_CONST_MM = {
    1: 103.0692307692308, 2: 115.03999999999999, 3: 136.92461538461538,
    4: 152.96692307692308, 5: 146.68923076923076, 6: 140.09307692307695,
    7: 120.02538461538461, 8: 125.63923076923078, 9: 120.25076923076925,
    10: 112.23615384615384, 11: 101.06923076923077, 12: 99.02,
}
EVAP_PAN_COEFFICIENT = 0.7
INFILTRATION_RATE_MM_PER_DAY = 1.0
RESERVOIR_STORAGE_MAX_M3 = 1625463.7590197
API_K_DAILY = 0.95
API_K_6H = API_K_DAILY ** (1 / 4)  # 0.9873...

# ---------- Release rate: refined จาก 3 แหล่งข้อมูล (แทนสมมติฐาน "คงที่ 9446.4 ต่อเนื่องตั้งแต่
# 2026-06-26" เดิม ซึ่งใช้ได้แค่กับ event ล่าสุดเดียว) ----------
#
# 1. ตารางเก็บข้อมูลการจ่ายน้ำของอ่างเก็บน้ำแม่นาเรือ.xlsx -- log เหตุการณ์ปล่อยน้ำ 9 แถว (2025-06-26
#    ถึง 2026-04-18) แต่ละแถวมี "จำนวนรอบที่เปิดวาล์ว" (valve_turns) และ "ฝั่งท่อน้ำออก" แต่ไม่มีอัตรา
#    m3 ตรงๆ (คอลัมน์ "คิดเป็นปริมาณน้ำ" ว่างทุกแถว)
# 2. flow_rate_spillway.csv / flow_rate_inlet.csv -- ตาราง valve_turns -> avg_q_m3h แยกตามฝั่งท่อ
#    (มาจาก Spillway_Overflow_calculation.xlsx) -- นี่คือ conversion rule ที่ขาดไป
# 3. release_events.csv -- event ล่าสุดที่ยังไม่มีใน log ด้านบน (เริ่ม 2026-06-26)
#
# ยืนยันความถูกต้อง cross-check: ทุกแถวใน log มี valve_turns=6 เท่ากันหมด
#   - ฝั่งสปิลเวย์ valve_turns=6 -> avg_q_m3h=393.6 -> x24 = 9446.4 m3/day
#     ตรงกับ rate_m3_per_day=9446.4 ใน release_events.csv เป๊ะ (เป็น event ฝั่งสปิลเวย์เดียวกัน) --
#     ยืนยันว่ากติกาแปลง valve_turns -> m3/day คือ avg_q_m3h * 24 ถูกต้อง
#   - ฝั่งทางเข้าอ่าง valve_turns=6 -> avg_q_m3h=232.2 -> x24 = 5572.8 m3/day
RELEASE_RATE_SPILLWAY_6TURNS = 393.6 * 24  # = 9446.4 m3/day (ยืนยันตรงกับ release_events.csv)
RELEASE_RATE_INLET_6TURNS = 232.2 * 24  # = 5572.8 m3/day

# เหตุการณ์ปล่อยน้ำทั้งหมดที่ยืนยันได้ (start, end, rate_m3_per_day) -- รวมจาก log 9 แถว + release_events.csv
# หมายเหตุ: แถวที่ 1-2 และ 3-4 ในไฟล์ log เป็นคู่ (เปิดพร้อมกัน 2 ฝั่งท่อ ช่วงเวลาเดียวกัน) -- รวมอัตรา
# ทั้งสองฝั่งเข้าด้วยกันถ้า active ทับซ้อนกัน (ใช้ sum ของทุก event ที่ active ที่เวลานั้น)
#
# **ข้อยกเว้น/คุณภาพข้อมูล**: แถวที่ 7 ของ log (เริ่ม 27 มี.ค. 69 / ปิด 21 มี.ค. 69) วันที่ปิดมาก่อนวันที่
# เริ่ม (เป็นไปไม่ได้) -- ผู้ใช้ยืนยันแล้วว่าเป็นการกรอกข้อมูลผิดพลาดจริง -- **ตัดออกจาก timeline นี้**
# ยืนยันแล้ว (ไม่ใช้คำนวณ)
RELEASE_EVENTS = [
    # (start, end, rate_m3_per_day, source)
    (datetime(2025, 6, 26, 10, 0), datetime(2025, 10, 14, 13, 0), RELEASE_RATE_SPILLWAY_6TURNS, "log#1 สปิลเวย์"),
    (datetime(2025, 6, 26, 10, 0), datetime(2025, 10, 14, 13, 0), RELEASE_RATE_INLET_6TURNS, "log#2 ทางเข้าอ่าง"),
    (datetime(2025, 10, 18, 10, 0), datetime(2025, 11, 6, 10, 0), RELEASE_RATE_SPILLWAY_6TURNS, "log#3 สปิลเวย์"),
    (datetime(2025, 10, 18, 10, 0), datetime(2025, 11, 7, 10, 0), RELEASE_RATE_INLET_6TURNS, "log#4 ทางเข้าอ่าง"),
    (datetime(2026, 1, 6, 10, 0), datetime(2026, 1, 8, 10, 0), RELEASE_RATE_INLET_6TURNS, "log#5 ทางเข้าอ่าง"),
    (datetime(2026, 2, 2, 10, 0), datetime(2026, 2, 5, 10, 0), RELEASE_RATE_SPILLWAY_6TURNS, "log#6 สปิลเวย์"),
    # log#7 (27 มี.ค.69 - 21 มี.ค.69) ตัดออก -- วันที่ผิดปกติ (ปิดก่อนเริ่ม) ดู comment ด้านบน
    (datetime(2026, 3, 29, 10, 0), datetime(2026, 3, 30, 10, 0), RELEASE_RATE_INLET_6TURNS, "log#8 ทางเข้าอ่าง"),
    (datetime(2026, 4, 10, 10, 0), datetime(2026, 4, 18, 10, 0), RELEASE_RATE_SPILLWAY_6TURNS, "log#9 สปิลเวย์"),
    # release_events.csv -- event ล่าสุด ยังไม่มีใน log ด้านบน (log มีข้อมูลถึงแค่ 2026-04-18)
    # ผู้ใช้ยืนยันแล้ว: ตั้งแต่ 2026-06-26 เปิดฝั่งสปิลเวย์อย่างเดียว (ไม่ได้เปิดคู่ 2 ฝั่งแบบปีก่อน)
    # และยังเปิดอยู่จนถึงปัจจุบัน -- ใช้ rate เดียว ไม่ต้องเผื่อฝั่งทางเข้าอ่างเพิ่ม
    (datetime(2026, 6, 26, 10, 0), datetime(2026, 10, 14, 13, 0), RELEASE_RATE_SPILLWAY_6TURNS, "release_events.csv event#1 สปิลเวย์ (ยืนยันเปิดฝั่งเดียว ต่อเนื่องถึงปัจจุบัน)"),
]


def release_rate_m3_per_day(t):
    """ผลรวมอัตราปล่อยน้ำ (m3/day) ของทุก event ที่ active ที่เวลา t (รองรับเปิดพร้อมกันหลาย event/ฝั่งท่อ)"""
    return sum(rate for start, end, rate, _label in RELEASE_EVENTS if start <= t <= end)


def load_curve(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            rows.append([float(x) for x in row])
    rows.sort(key=lambda r: r[0])
    return rows


def xlookup_floor(level, table):
    """เหมือน _xlookup_floor เดิม -- หาแถวที่ level มากกว่าเท่ากับ ล่าสุด (floor match)"""
    best = table[0]
    for row in table:
        if row[0] <= level:
            best = row
        else:
            break
    return best


rating_curve = load_curve(os.path.join(HERE, "rating_curve_1cm.csv"))
area_terrain = load_curve(os.path.join(HERE, "area_terrain.csv"))


def storage_from_level(level):
    return xlookup_floor(level, rating_curve)[3]


def surface_area_from_level(level):
    return xlookup_floor(level, rating_curve)[2]


def terrain_area_from_level(level):
    return xlookup_floor(level, area_terrain)[2]


def spillway_overflow_m3(hourly_levels):
    total = 0.0
    for level in hourly_levels:
        adj = level - SPILLWAY_LEVEL_ADJ_OFFSET_M
        head = max(0.0, adj - SPILLWAY_CREST_LEVEL_MSL)
        q_m3_s = SPILLWAY_WEIR_COEFFICIENT_C * SPILLWAY_WEIR_LENGTH_M * (head ** 1.5)
        total += q_m3_s * 3600
    return total


# ---------- โหลดข้อมูลดิบ (level + rain) รวม 2 แหล่ง ----------
# ระดับน้ำที่เคยเห็นจริงตลอด session นี้ (ทั้งข้อมูล 1 ปีจาก Raw Data + wide_log) อยู่ในช่วง
# ~488.0-490.2 ม. เท่านั้น -- ตั้ง band กว้างกว่านั้นพอสมควรกันเผื่อระดับน้ำจริงต่ำ/สูงกว่าที่เคยเห็น
# แต่แคบพอจะจับ sensor glitch ที่ค้นพบระหว่างทดสอบ (2025-09-15 18:00 ถึง 2025-09-16 15:00: sensor
# ค้างที่ 487.216 นิ่งสนิท 22 ชม.ติด ทั้งที่ก่อนหน้า/หลังจากนั้นอยู่ที่ ~489.35-489.38 -- กระโดด 2.1+ ม.
# ในชั่วโมงเดียวซึ่งเป็นไปไม่ได้ทางกายภาพสำหรับอ่างขนาดนี้ ทำให้คำนวณ Q_in_6h ได้ 957,368 m3/6h ผิดปกติ
# มาก ก่อนแก้ไข) -- ค่านอกช่วงนี้ถือว่าเป็น sensor error ตัด (None) ไม่ใช้คำนวณ
# แก้ไข: ตรวจสอบ min/max ของข้อมูลถูกต้องทั้งปี (ไม่รวมช่วง glitch) แล้วพบว่าระดับน้ำจริงอยู่ในช่วง
# 488.13-490.17 ม. เท่านั้น (ทั้ง Raw Data ปี 2568-69 และ wide_log ก.ค. 2569) -- 485.0 กว้างเกินไป จับ
# glitch 487.216 ไม่ได้ (487.216 > 485.0) ปรับ band ให้แคบลงอิงจากข้อมูลจริง
PLAUSIBLE_LEVEL_MIN = 487.5
PLAUSIBLE_LEVEL_MAX = 491.0


def parse_raw_data_xlsx(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["20260202_RES002"]
    rows = list(ws.iter_rows(values_only=True))[1:]
    level, rain = {}, {}
    n_rejected = 0
    for r in rows:
        if not r[0]:
            continue
        t = datetime.strptime(str(r[0])[:19], "%Y-%m-%d %H:%M:%S")
        if r[7] == "water_level":
            v = float(r[2])
            if PLAUSIBLE_LEVEL_MIN <= v <= PLAUSIBLE_LEVEL_MAX:
                level[t] = v
            else:
                n_rejected += 1
        elif r[7] == "rainfall_1h":
            rain[t] = float(r[2]) if r[2] is not None else None
    if n_rejected:
        print(f"  parse_raw_data_xlsx: rejected {n_rejected} implausible water_level readings "
              f"(outside {PLAUSIBLE_LEVEL_MIN}-{PLAUSIBLE_LEVEL_MAX} m)")
    return level, rain


def parse_wide_log_csv(path):
    level, rain = {}, {}
    n_rejected = 0
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("measure_datetime"):
                continue
            t = datetime.strptime(row["measure_datetime"], "%Y-%m-%d %H:%M:%S")
            if row.get("RES002_water_level"):
                v = float(row["RES002_water_level"])
                if PLAUSIBLE_LEVEL_MIN <= v <= PLAUSIBLE_LEVEL_MAX:
                    level[t] = v
                else:
                    n_rejected += 1
            if row.get("RES002_rainfall_1h") not in (None, ""):
                rain[t] = float(row["RES002_rainfall_1h"])
    if n_rejected:
        print(f"  parse_wide_log_csv: rejected {n_rejected} implausible water_level readings")
    return level, rain


raw_level, raw_rain = parse_raw_data_xlsx(os.path.join(HERE, "Raw Data_RES002 station.xlsx"))
wide_level, wide_rain = parse_wide_log_csv(os.path.join(HERE, "wide_log_20260731.csv"))

level_pts = {**raw_level, **wide_level}
rain_pts = {**raw_rain, **wide_rain}
level_sorted = sorted(level_pts.items())
rain_sorted = sorted(rain_pts.items())
print(f"level points: {len(level_sorted)}, rain points: {len(rain_sorted)}")


def nearest_value(target_t, pts_sorted, tolerance_min=30):
    best, best_diff = None, None
    for t, v in pts_sorted:
        diff = abs((t - target_t).total_seconds())
        if diff > tolerance_min * 60:
            continue
        if best_diff is None or diff < best_diff:
            best, best_diff = v, diff
    return best


def build_hourly_grid(pts_sorted, start, end):
    grid = {}
    t = start
    while t <= end:
        grid[t] = nearest_value(t, pts_sorted)
        t += timedelta(hours=1)
    return grid


grid_start = min(level_sorted[0][0], rain_sorted[0][0]).replace(minute=0, second=0)
grid_end = max(level_sorted[-1][0], rain_sorted[-1][0]).replace(minute=0, second=0)
hourly_level = build_hourly_grid(level_sorted, grid_start, grid_end)
hourly_rain = build_hourly_grid(rain_sorted, grid_start, grid_end)


def ma6h_trailing(t):
    """ค่าเฉลี่ย 6 ชม.ล่าสุดจบที่ t (รวม t) แบบ trailing ไม่ look-ahead"""
    vals = [hourly_level.get(t - timedelta(hours=i)) for i in range(0, 6)]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def sum_rain_6h(t):
    vals = [hourly_rain.get(t - timedelta(hours=i)) for i in range(0, 6)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def raw_hourly_levels_6h(t):
    vals = [hourly_level.get(t - timedelta(hours=i)) for i in range(0, 6)]
    return [v for v in vals if v is not None]


def is_release_active(t):
    return release_rate_m3_per_day(t) > 0


# ---------- สร้าง 6h marks (01:00, 07:00, 13:00, 19:00 ของทุกวัน) ----------
MARK_HOURS = [1, 7, 13, 19]
marks = []
d = grid_start.date()
end_date = grid_end.date()
while d <= end_date:
    for h in MARK_HOURS:
        t = datetime(d.year, d.month, d.day, h)
        if grid_start <= t <= grid_end:
            marks.append(t)
    d += timedelta(days=1)
marks.sort()
print(f"6h marks in range: {len(marks)}")

rows = []
prev_storage = None
prev_api = None
for t in marks:
    smoothed_level = ma6h_trailing(t)
    rain_6h = sum_rain_6h(t)
    raw_levels = raw_hourly_levels_6h(t)

    if smoothed_level is None or rain_6h is None or len(raw_levels) < 4:
        # ข้อมูลไม่พอในหน้าต่างนี้ (ตกอยู่ในช่วง gap) -- ข้าม แต่ reset prev_storage/prev_api
        # เพื่อไม่ให้ DeltaS_t ข้าม gap ผิดๆ (เหมือน logic เดิมของระบบที่ raise error ถ้าไม่มีข้อมูล
        # วันก่อนหน้า แทนที่จะข้ามเงียบๆ)
        prev_storage = None
        prev_api = None
        continue

    storage = storage_from_level(smoothed_level)
    surface_area = surface_area_from_level(smoothed_level)
    terrain_area = terrain_area_from_level(smoothed_level)

    if prev_storage is None:
        # จุดแรกหลัง gap -- มี level แต่ยังคำนวณ DeltaS ไม่ได้ (ไม่รู้ storage ก่อนหน้า 6 ชม.)
        prev_storage = storage
        prev_api = rain_6h
        continue

    delta_s = storage - prev_storage
    r_runoff = surface_area * (rain_6h / 1000.0)
    days_in_month = calendar.monthrange(2000, t.month)[1]
    evap_6h = surface_area * ((MONTHLY_EVAP_CONST_MM[t.month] / days_in_month / 4) * EVAP_PAN_COEFFICIENT) / 1000.0
    infiltration_6h = terrain_area * ((INFILTRATION_RATE_MM_PER_DAY / 4) / 1000.0)
    release_6h = release_rate_m3_per_day(t) / 4
    spill_6h = spillway_overflow_m3(raw_levels)

    q_in_raw = delta_s - r_runoff + release_6h + spill_6h + evap_6h + infiltration_6h
    q_in_6h = max(0.0, q_in_raw)

    api_t = API_K_6H * prev_api + rain_6h

    rows.append({
        "Datetime": t.isoformat(),
        "Q_in_t (m3/6h)": round(q_in_6h, 4),
        "Water_Level_t (m)": round(smoothed_level, 4),
        "Storage_S_t (m3)": round(storage, 2),
        "DeltaS_t (m3/6h)": round(delta_s, 2),
        "%Full_t": round(storage / RESERVOIR_STORAGE_MAX_M3 * 100, 4),
        "Rain_obs_t (mm)": round(rain_6h, 3),
        "API_t (mm)": round(api_t, 4),
        "is_release_active": int(is_release_active(t)),
        "release_rate_daily (m3/day)": round(release_rate_m3_per_day(t), 1),
        "spill_m3": round(spill_6h, 2),
    })

    prev_storage = storage
    prev_api = api_t

print(f"\nRows built: {len(rows)} / {len(marks)} possible marks ({len(rows)/len(marks)*100:.1f}% coverage)")

out_path = os.path.join(HERE, "Training_6hourly_raw.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"Saved {out_path}")
