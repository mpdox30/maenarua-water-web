"""
reservoir_water_balance.py

คำนวณ "บัญชีน้ำ" รายวันของอ่างเก็บน้ำแม่นาเรือ จากสูตรที่สกัดตรงตัวจากไฟล์ต้นฉบับ
<year>_<month>_MNR.xlsx (ชีต "บัญชีน้ำ", "Rating Curve 1 CM", "Area_Terrain",
"น้ำล้นสปิลเวย์") — ทำให้สามารถคำนวณ Inflow (Q_in_t) เองได้จากแค่ 4 อินพุตดิบ แทนที่จะ
ต้องรอให้มีคนกรอกไฟล์ xlsx รายเดือนด้วยมือ:

    1. ระดับน้ำ (MSL, m)          -- จาก API สถานีโทรมาตร (ยืนยันว่ามีอยู่แล้ว 2026-07-14)
    2. ปริมาณฝนสะสม 24 ชม. (mm)  -- จาก API สถานีโทรมาตร (ยืนยันว่ามีอยู่แล้ว 2026-07-14)
    3. ปริมาณน้ำที่ปล่อยออก O (m3/day) -- ต้องมาจาก Google Form บันทึกการปล่อยน้ำ
       (ดู RESERVOIR_AUTOMATION_DESIGN.md > ส่วน Google Form) เพราะเป็นการตัดสินใจของ
       เจ้าหน้าที่ ไม่มีทางวัดจากเซนเซอร์ได้
    4. ปริมาณน้ำล้นสปิลเวย์ Spill (m3/day) -- คำนวณได้จากระดับน้ำล้วนๆ ผ่าน
       compute_spillway_overflow_m3() ถ้ามีข้อมูลระดับน้ำแบบรายชั่วโมง (จากสถานีโทรมาตร)
       ถ้ามีแค่ระดับน้ำ 1 ค่า/วัน (07:00 น.) จะประมาณแบบระดับคงที่ตลอดวันแทน (ดู docstring
       ของฟังก์ชัน)

สอบทานแล้ว (2026-07-14): re-implementation นี้ให้ผลตรงกับค่า Inflow ที่คำนวณจริงในไฟล์
2026_July_MNR.xlsx (ที่ผู้ใช้อัปโหลด) แบบ bit-exact ทั้ง 14 วัน (1-14 กรกฎาคม 2569)
รวมถึงกรณีขอบ (edge case) ที่ระดับน้ำไม่ตรง grid 0.01 พอดี (เช่น 489.586, 489.547, 489.165)
ซึ่งพิสูจน์ได้ว่า XLOOKUP ในไฟล์ต้นฉบับใช้ match_mode=-1 (exact match หรือค่าที่เล็กกว่าถัดไป
"floor" ไม่ใช่ round-to-nearest) — เป็นรายละเอียดสำคัญที่ต้อง reproduce ให้ตรง มิฉะนั้นค่า
Storage ที่ได้จะคลาดเคลื่อนหลักพันลูกบาศก์เมตรต่อวัน

อัปเดต 2026-07-14: ได้ค่าคงที่ evaporation ครบ 12 เดือนแล้ว (จาก Evap_Monthly.xlsx ที่ผู้ใช้
เพิ่มให้) และได้สเปค API สถานีโทรมาตรจริงแล้ว (ดู reservoir_telemetry_client.py) —
เหลือเฉพาะ Google Form + orchestration script ที่ยังไม่ได้สร้าง

ยังไม่ได้ทำ (ต้องรอข้อมูล/การตัดสินใจเพิ่มจากผู้ใช้ — ดู RESERVOIR_AUTOMATION_DESIGN.md):
  - โครงสร้าง Google Form + กติกาแปลง "จำนวนรอบที่เปิดวาล์ว" เป็น O (m3/day)
  - Orchestration/polling script ที่เรียก API จริงเป็นระยะ (API ให้แค่ค่าล่าสุด ไม่มี query
    ช่วงเวลาย้อนหลัง — ต้อง poll เองแล้วสะสม log เพื่อรวมฝนรายชั่วโมงเป็น 24 ชม. และเก็บระดับ
    น้ำรายชั่วโมงไว้คำนวณ spillway) + ผูกเข้ากับ _ri_load_raw_monthly_data() ใน data_pipeline.py
    (ตอนนี้โมดูลนี้เป็น standalone ยังไม่ได้ wire เข้า pipeline หลัก)
"""

from __future__ import annotations

import bisect
import csv
from pathlib import Path
from typing import Optional

REFERENCE_DIR = Path(__file__).resolve().parent.parent.parent / "Reservoirs" / "reference"
RATING_CURVE_CSV = REFERENCE_DIR / "rating_curve_1cm.csv"
AREA_TERRAIN_CSV = REFERENCE_DIR / "area_terrain.csv"
FLOW_RATE_INLET_CSV = REFERENCE_DIR / "flow_rate_inlet.csv"
FLOW_RATE_SPILLWAY_CSV = REFERENCE_DIR / "flow_rate_spillway.csv"

# ปรับตาม "ตารางปล่อยน้ำ" ของแม่นาเรือ — พารามิเตอร์ weir formula จากชีต "น้ำล้นสปิลเวย์"
SPILLWAY_LEVEL_ADJ_OFFSET_M = 0.155   # water_level (ADJ) = water_level - 0.155
SPILLWAY_CREST_LEVEL_MSL = 489.545    # Spillway_level
SPILLWAY_WEIR_COEFFICIENT_C = 1.82
SPILLWAY_WEIR_LENGTH_M = 30           # ความยาวสัน spillway (L) — จากสูตร Q(m3/s) = C * L * H^1.5

# ค่าคงที่ระเหย (evap) รายเดือน mm ต่อเดือน — Average_2012_2024 ของสถานี 310201 (พะเยา)
# จากไฟล์ 01_data/Reservoirs/inflow/Evap_Monthly.xlsx (ผู้ใช้เพิ่มให้ 2026-07-14)
# ตรวจสอบแล้ว: ค่าเดือนกรกฎาคม (120.0254) ตรงกับค่าที่ใช้จริงในสูตร cell I6 ของ
# 2026_July_MNR.xlsx (120.03 — ปัดทศนิยม 2 ตำแหน่ง) คลาดเคลื่อน <0.005mm ไม่กระทบผลลัพธ์
# (ยืนยัน bit-exact ต่อใน reservoir_water_balance_test.py)
MONTHLY_EVAP_CONST_MM = {
    1: 103.0692307692308,   # JAN
    2: 115.03999999999999,  # FEB
    3: 136.92461538461538,  # MAR
    4: 152.96692307692308,  # APR
    5: 146.68923076923076,  # MAY
    6: 140.09307692307695,  # JUN
    7: 120.02538461538461,  # JUL
    8: 125.63923076923078,  # AUG
    9: 120.25076923076925,  # SEP
    10: 112.23615384615384, # OCT
    11: 101.06923076923077, # NOV
    12: 99.02,               # DEC
}
EVAP_PAN_COEFFICIENT = 0.7
INFILTRATION_RATE_MM_PER_DAY = 1.0  # จาก header เดิม "Infiltration (1mm/day)"


def _load_curve(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            rows.append([float(x) for x in row])
    rows.sort(key=lambda r: r[0])
    return rows


_rating_curve_cache: Optional[list[list[float]]] = None
_area_terrain_cache: Optional[list[list[float]]] = None


def _rating_curve() -> list[list[float]]:
    global _rating_curve_cache
    if _rating_curve_cache is None:
        _rating_curve_cache = _load_curve(RATING_CURVE_CSV)
    return _rating_curve_cache


def _area_terrain() -> list[list[float]]:
    global _area_terrain_cache
    if _area_terrain_cache is None:
        _area_terrain_cache = _load_curve(AREA_TERRAIN_CSV)
    return _area_terrain_cache


_flow_rate_inlet_cache: Optional[dict[int, float]] = None
_flow_rate_spillway_cache: Optional[dict[int, float]] = None


def _load_flow_rate_table(path: Path) -> dict[int, float]:
    """
    โหลดตาราง "จำนวนรอบวาล์ว -> อัตราการไหล" (valve_turns, avg_v_ms, avg_q_m3h, avg_q_m3min)
    คืนค่า dict {valve_turns(int): avg_q_m3h(float)} — เก็บเฉพาะคอลัมน์ avg_q_m3h เพราะเป็นหน่วยที่
    ใช้แปลงเป็น m3/day ตรงๆ (× จำนวนชั่วโมงที่เปิด)
    """
    table: dict[int, float] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            table[int(float(row["valve_turns"]))] = float(row["avg_q_m3h"])
    return table


def _flow_rate_inlet() -> dict[int, float]:
    global _flow_rate_inlet_cache
    if _flow_rate_inlet_cache is None:
        _flow_rate_inlet_cache = _load_flow_rate_table(FLOW_RATE_INLET_CSV)
    return _flow_rate_inlet_cache


def _flow_rate_spillway() -> dict[int, float]:
    global _flow_rate_spillway_cache
    if _flow_rate_spillway_cache is None:
        _flow_rate_spillway_cache = _load_flow_rate_table(FLOW_RATE_SPILLWAY_CSV)
    return _flow_rate_spillway_cache


def valve_turns_to_flow_m3_per_day(
    valve_turns: int, outlet: str = "inlet", open_hours: float = 24.0,
) -> float:
    """
    แปลง "จำนวนรอบที่เปิดวาล์ว" เป็นปริมาณน้ำที่ปล่อยออก O (m3/day) — ใช้ตาราง
    flow_rate_inlet.csv/flow_rate_spillway.csv (01_data/Reservoirs/reference/) ที่มาจากการวัดจริง
    3 รอบต่อค่า valve_turns (ดู README.md ในโฟลเดอร์เดียวกัน) — เพิ่ม 2026-07-18 เพื่อรองรับ
    Google Form บันทึกการปล่อยน้ำในอนาคต (ตอนนี้ยังไม่มี Form จริง ฟังก์ชันนี้พร้อมใช้งานรอไว้)

    outlet: "inlet" (ท่อฝั่งทางเข้าอ่าง) หรือ "spillway" (ท่อฝั่ง spillway) — ต้องเลือกให้ตรงกับ
    ท่อที่เปิดจริง เพราะอัตราการไหลต่อรอบวาล์วไม่เท่ากัน (ดูตัวอย่าง: รอบ 6 inlet ให้ 232.2 m3/h
    แต่ spillway ให้ 393.6 m3/h)
    open_hours: จำนวนชั่วโมงที่เปิดวาล์วจริงในวันนั้น (default 24 = เปิดทั้งวันเต็ม)

    lookup แบบ exact match ตาม valve_turns เท่านั้น (ไม่มีทศนิยม ตามที่ README.md ระบุ — วัดจริงมา
    เป็นจำนวนเต็มรอบ ไม่ได้ interpolate ระหว่างรอบ)

    raises KeyError ถ้า valve_turns ไม่มีในตาราง (ต้องเป็นค่าที่วัดจริงไว้เท่านั้น ไม่ประมาณเอง)
    """
    if outlet == "inlet":
        table = _flow_rate_inlet()
    elif outlet == "spillway":
        table = _flow_rate_spillway()
    else:
        raise ValueError(f"outlet ต้องเป็น 'inlet' หรือ 'spillway' เท่านั้น ได้รับ: {outlet!r}")

    if valve_turns not in table:
        raise KeyError(
            f"ไม่มีข้อมูลวัดจริงสำหรับ valve_turns={valve_turns} ในตาราง flow_rate_{outlet}.csv "
            f"(ค่าที่มี: {sorted(table.keys())}) -- ไม่ประมาณค่าเอง ต้องใช้ค่าที่วัดจริงไว้เท่านั้น"
        )
    avg_q_m3h = table[valve_turns]
    return avg_q_m3h * open_hours


def _xlookup_floor(level: float, table: list[list[float]]) -> list[float]:
    """
    จำลอง Excel XLOOKUP(level, keys, values, , -1) ของไฟล์ต้นฉบับ — match_mode=-1
    หมายถึง "exact match หรือถ้าไม่เจอให้เอาค่าที่เล็กกว่าถัดไป (floor)" ไม่ใช่ round-to-nearest
    (ยืนยันจากการสอบทาน bit-exact กับไฟล์จริง 2026-07-14 — ระดับน้ำที่ไม่ตรง grid 0.01 พอดี
    เช่น 489.586 ต้องแมพกับแถว 489.58 ไม่ใช่ 489.59)
    """
    keys = [r[0] for r in table]
    idx = bisect.bisect_right(keys, level + 1e-9) - 1
    idx = max(0, min(idx, len(table) - 1))
    return table[idx]


def compute_spillway_overflow_m3(hourly_levels_msl: list[float]) -> float:
    """
    คำนวณปริมาณน้ำล้นสปิลเวย์รายวัน (m3) จากระดับน้ำรายชั่วโมง (24 ค่า) — สูตร weir
    ที่สกัดจากชีต "น้ำล้นสปิลเวย์" ของไฟล์ต้นฉบับ:

        water_level_adj = water_level - 0.155
        H = max(0, water_level_adj - 489.545)
        Q (m3/s) = 1.82 * 30 * H^1.5
        Q (m3/h) = Q(m3/s) * 3600

    daily spill (m3) = sum(Q(m3/h) สำหรับ 24 ชั่วโมง)

    ถ้ามีระดับน้ำแค่ 1 ค่า/วัน (เช่น อ่านจาก telemetry แค่ตอน 07:00 น. เหมือนชีต "บัญชีน้ำ"
    หลัก) ให้เรียกฟังก์ชันนี้ด้วย list ที่มีค่าเดียวซ้ำ 24 ครั้ง (ประมาณว่าระดับคงที่ตลอดวัน —
    เป็นการประมาณคร่าวๆ อาจคลาดเคลื่อนถ้าระดับน้ำเปลี่ยนเร็วในวันที่มีน้ำล้นจริง ควรใช้ระดับ
    รายชั่วโมงจริงถ้า API โทรมาตรมีให้)
    """
    total_m3 = 0.0
    for level in hourly_levels_msl:
        adj = level - SPILLWAY_LEVEL_ADJ_OFFSET_M
        head = max(0.0, adj - SPILLWAY_CREST_LEVEL_MSL)
        q_m3_s = SPILLWAY_WEIR_COEFFICIENT_C * SPILLWAY_WEIR_LENGTH_M * (head ** 1.5)
        q_m3_h = q_m3_s * 3600
        total_m3 += q_m3_h
    return total_m3


def compute_daily_row(
    level_msl: float,
    rain_mm: float,
    release_o_m3: float,
    spill_m3: float,
    prev_storage_m3: float,
    month: int,
) -> dict:
    """
    คำนวณค่าเทียบเท่าแถวเดียวของชีต "บัญชีน้ำ" จาก 4 อินพุตดิบ + storage ของเมื่อวาน

    คืนค่า dict ที่มี key ตรงกับคอลัมน์ feature ที่ _ri_load_raw_monthly_data() ใน
    data_pipeline.py ต้องการ (Q_in_t, Water_Level_t, Storage_S_t, DeltaS_t, %Full_t,
    Rain_obs_t) ยกเว้น API_t (ต้อง track แยกข้ามวันเหมือนใน _ri_load_raw_monthly_data)

    raises KeyError ถ้าไม่มีค่าคงที่ evap ของเดือนนั้นใน MONTHLY_EVAP_CONST_MM
    """
    if month not in MONTHLY_EVAP_CONST_MM:
        raise KeyError(
            f"ไม่มีค่าคงที่ evaporation ของเดือน {month} ใน MONTHLY_EVAP_CONST_MM "
            "— ต้องขอค่านี้จากผู้ใช้ก่อน (ดู TODO ด้านบนของไฟล์นี้)"
        )
    evap_const_mm = MONTHLY_EVAP_CONST_MM[month]

    # จำนวนวันในเดือน (ใช้ calendar เพื่อความถูกต้อง ไม่ hardcode 31 แบบไฟล์เก่าที่เคยมีบั๊ก
    # evap_days_in_month_bug ที่แก้ไปแล้วในไฟล์ raw ต้นทาง — ดู latest.json >
    # known_deviations_from_original_template)
    import calendar

    # หมายเหตุ: ต้องรู้ปีด้วยเพื่อความแม่นยำ (ปีอธิกสุรทิน) — ฟังก์ชันนี้รับแค่ month เพื่อความง่าย
    # ผู้เรียกที่ต้องการความแม่นยำ 100% ควรส่ง days_in_month มาแทน หรือขยาย signature ภายหลัง
    days_in_month = calendar.monthrange(2000, month)[1]  # ปีอธิกสุรทินไม่กระทบเดือนอื่นนอกจาก ก.พ.

    rc_row = _xlookup_floor(level_msl, _rating_curve())
    surface_area_m2 = rc_row[2]
    storage_m3 = rc_row[3]

    at_row = _xlookup_floor(level_msl, _area_terrain())
    terrain_area_m2 = at_row[2]

    r_runoff_m3 = surface_area_m2 * (rain_mm / 1000.0)
    evap_m3 = surface_area_m2 * ((evap_const_mm / days_in_month) * EVAP_PAN_COEFFICIENT) / 1000.0
    infiltration_m3 = terrain_area_m2 * (INFILTRATION_RATE_MM_PER_DAY / 1000.0)
    delta_s_m3 = storage_m3 - prev_storage_m3

    inflow_raw = delta_s_m3 - r_runoff_m3 + release_o_m3 + spill_m3 + evap_m3 + infiltration_m3
    inflow_m3 = max(0.0, inflow_raw)

    return {
        "Q_in_t": inflow_m3,
        "Water_Level_t": level_msl,
        "Storage_S_t": storage_m3,
        "DeltaS_t": delta_s_m3,
        "Rain_obs_t": rain_mm,
        "surface_area_m2": surface_area_m2,
        "terrain_area_m2": terrain_area_m2,
        "R_runoff_m3": r_runoff_m3,
        "Evap_m3": evap_m3,
        "Infiltration_m3": infiltration_m3,
        "release_O_m3": release_o_m3,
        "spill_m3": spill_m3,
    }
