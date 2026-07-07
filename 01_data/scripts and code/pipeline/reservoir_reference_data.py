"""
reservoir_reference_data.py
=============================
Reference data lookups + water-balance term functions สำหรับอ่างเก็บน้ำแม่นาเรือ

ที่มาไฟล์อ้างอิง: 01_data/Reservoirs/reference/ (ผู้ใช้วางไว้ 5 ก.ค. 2569 — ดู README.md
ในโฟลเดอร์นั้นสำหรับที่มาแบบเต็มของแต่ละไฟล์)
  - rating_curve_1cm.csv    : Area(m2)/Volume(m3) ต่อระดับน้ำ (771 แถว, step 1 cm, 482.80-490.50 m)
                              มาจาก sheet "Rating Curve 1 CM" ของ 2026_May_MNR.xlsx —
                              เป็นตารางเดียวที่ใช้อ้างอิง Area/Volume ทั้งหมด (ตาราง "Rating Curve"
                              เก่า และ "Area_Terrain" ถูกตัดออก ไม่ใช้อีกต่อไป)
  - flow_rate_spillway.csv  : Q(m3/h) ต่อจำนวนรอบวาล์ว ฝั่งท่อน้ำออกสปิลเวย์ (ค่าเฉลี่ย 3 รอบทดลอง)
  - flow_rate_inlet.csv     : เหมือนกันแต่ฝั่งท่อทางเข้าอ่าง
  - monthly_evap_norm.json  : ค่าระเหยเฉลี่ยรายเดือน (mm/เดือน) แบบ climatological คงที่ 12 ค่า
  - weir_constants.json     : ค่าคงที่ทางกายภาพของสปิลเวย์ (C, L, spillway_level_msl)

สูตร Inflow เต็ม (ยืนยันกับผู้ใช้ 5 ก.ค. 2569 — ดู README.md ข้างต้นประกอบ):

    Inflow(day) = ΔS − R + O + Spill + E + Infiltration

    ΔS            = Volume(level_today) − Volume(level_yesterday)      [rating_curve_1cm.csv]
    R             = Area(level_today) × Rain_mm / 1000                 [rating_curve_1cm.csv]
    E             = Area(level_today) × (EvapNorm[เดือน]/days_in_month × 0.7) / 1000
    Infiltration  = Area(level_today) × 0.001
    Spill         = sum ของ weir formula 24 ค่า/ชม. ใน 1 วัน                [weir_constants.json]
    O             = overlap เวลาที่ event ปล่อยน้ำ × flow rate ต่อ ชม.      [flow_rate_*.csv]

สอง "การตั้งใจไม่ replicate ของเดิม" ที่ยืนยัน/พบระหว่าง implement โมดูลนี้ (5 ก.ค. 2569) —
**อัปเดต 2026-07-05 (รอบ 2)**: หลังตรวจสอบไฟล์ดิบทั้ง 13 ไฟล์ (2025_June ถึง 2026_June) พบว่า
ทั้ง 2 bug นี้ **ไม่ได้เกิดสม่ำเสมอทุกเดือน** อย่างที่เข้าใจตอนแรกจากการดูแค่ 2026_May_MNR.xlsx
ไฟล์เดียว — รายละเอียดจริงตามนี้ (ดูรายงานเต็มในบทสนทนา วันที่ 2026-07-05):

  1. Infiltration — สูตร `D6 = IF(K6-H6+E6+F6+I6[+J6] < 0, 0, K6-H6+E6+F6+I6[+J6])` **มี +J6
     (รวม Infiltration) จริงตั้งแต่ 2025_July ถึง 2026_January (7 เดือน)** แล้ว "หายไป" อีกครั้ง
     ตั้งแต่ **2026_February ถึง 2026_June (5 เดือนล่าสุด ณ ตอนตรวจสอบ)** — 2026_May ที่ตรวจตอนแรก
     บังเอิญอยู่ในช่วงที่ bug กลับมา จึงดูเหมือนเป็น bug ถาวรทั้งที่จริงเป็นการ regression เฉพาะ
     5 เดือนหลังสุด (2025_June เดือนแรกสุดก็ไม่มี column J เลย เพราะเป็นช่วงก่อนเริ่มเก็บข้อมูลเป็น
     ระบบ — มีข้อมูลแค่ 4 วันสุดท้ายของเดือน) ผู้ใช้ยืนยันแล้วว่าการไม่รวม Infiltration เป็น bug
     ต้องแก้ ให้ compute_daily_inflow() ของโมดูลนี้รวม Infiltration เข้าไปในสูตรเสมอไม่ว่ากรณีใด

  2. Evaporation — วันที่ (days_in_month) ที่ใช้หารใน formula ก็ hardcode เป็นค่าคงที่ต่อไฟล์
     เหมือนกัน **แต่ไม่ได้ผิดทุกเดือน**: ตรวจสอบ cell formula I6 ของทั้ง 13 ไฟล์แล้วพบว่าเดือนที่
     หารด้วยเลขวันที่ "ผิด" (ไม่ตรงกับจำนวนวันจริงของเดือนนั้น) มีแค่ **กุมภาพันธ์ 2569 (หาร 30
     ทั้งที่กุมภาพันธ์ 2569 มี 28 วัน — ปีนี้ไม่ใช่ปีอธิกสุรทิน), มีนาคม 2569 (หาร 30 ทั้งที่มี 31 วัน),
     และพฤษภาคม 2569 (หาร 30 ทั้งที่มี 31 วัน)** — เดือนอื่นๆ ทั้งหมด (ก.ค.-ธ.ค. 2568, ม.ค./เม.ย./
     มิ.ย. 2569) หารด้วยจำนวนวันที่ถูกต้องอยู่แล้ว ส่วนค่า norm เองก็ถูกปัดเศษ 2 ตำแหน่งเสมอทุกเดือน
     (เช่น 146.69 แทน 146.68923076923076) ซึ่งเป็นความคลาดเคลื่อนเล็กน้อยที่มีผลทุกเดือนเท่าๆ กัน
     (ไม่ใช่ปัญหาใหญ่) compute_evap_term() ด้านล่าง implement ด้วยสูตรที่ถูกต้องเสมอ (รับ
     month/days_in_month จริงเป็น parameter, ใช้ค่า norm แบบเต็มความละเอียดจาก monthly_evap_norm.json
     ไม่ปัดเศษ) — ยืนยันกับผู้ใช้แล้ว (2026-07-05) ว่าให้ใช้สูตรที่ถูกต้องนี้ในโค้ดใหม่เสมอ

  **ผลกระทบต่อข้อมูล training จริง (Training_Values_Nofct_7day_Final.csv, ตรวจสอบ 2026-07-05):**
  ยืนยันแล้วว่า Q_in_t ของ training มาจากคอลัมน์ Inflow (M3) ของไฟล์ดิบตรงๆ (314/359 แถวตรงกันเป๊ะ
  แถวที่เหลือเป็นความคลาดเคลื่อนเล็กน้อยไม่เกี่ยวกับ 2 bug นี้) เท่ากับว่า training set มีทั้งช่วงที่
  ใช้สูตรถูก (2025-06-27 ถึง 2026-01-31, ~7 เดือน) และช่วงที่ใช้สูตรที่ยังไม่รวม Infiltration
  (2026-02-01 ถึง 2026-06-20 ซึ่งเป็นท้ายสุดของ training set พอดี) ปนกันอยู่ — ขนาดผลกระทบเฉลี่ย
  ทั้ง training set ~121 m3/day (~0.1% ของ Q_in_t เฉลี่ย ~121,668 m3/day) เทียบกับ Hurdle_RMSE ของ
  โมเดล deploy จริง (CatBoost, 19,306-52,436 m3/day ต่อ horizon) แล้วเล็กน้อยมาก (~0.2-2% ของ RMSE)
  แต่มีผลข้างเคียงที่สำคัญกว่านั้น: ใน 46 วันที่ training set บันทึกเป็น "Inflow=0" (ถูก clip)
  45 วัน (เกือบทั้งหมด, ทุกวันอยู่ในช่วง ก.พ.-พ.ค. 2569 ที่ Infiltration หายไปจากสูตรพอดี) จะกลาย
  เป็นค่าบวกเล็กน้อย (~260-360 m3/day) แทนถ้าใช้สูตรที่แก้ไขแล้ว — เท่ากับว่าคลาส "zero-inflow" ที่
  stage1 classifier ถูกออกแบบมาเพื่อจับ อาจแทบไม่เหลือเลยถ้า retrain ด้วยข้อมูลที่แก้บั๊กแล้ว
  นี่เป็นผลกระทบเชิงโครงสร้างต่อ label ไม่ใช่แค่ noise ต่อเนื่อง — ควรพิจารณาแยกจากตัวเลข RMSE
  ข้างต้น ถ้าจะตัดสินใจ retrain ในอนาคต (ยังไม่ได้ตัดสินใจ/ดำเนินการใดๆ ณ ตอนนี้)

TODO (KNOWN_DEVIATION — ยืนยันกับผู้ใช้ 2026-07-05, ยังไม่ได้ทำ): เมื่อเชื่อมโมดูลนี้เข้า pipeline
จริง (wire compute_daily_inflow()/RatingCurve ฯลฯ เข้า _ri_build_feature_vector()/
_ri_run_prediction() ใน data_pipeline.py) **ต้อง copy ข้อความ known_limitation ด้านล่างนี้ไปเพิ่มใน
`01_data/scripts and code/Reservoir_inflow/active/model_metadata.json` ("known_limitations" array)
ด้วยเสมอ** — ไม่ใช่ optional เพราะเป็นข้อมูลที่กระทบการตีความผลทำนายของโมเดลที่ deploy อยู่จริง
ร่างข้อความสำหรับ model_metadata.json (สรุป 4 ประเด็นตามที่ผู้ใช้ยืนยัน):

    "Training data (Training_Values_Nofct_7day_Final.csv) มี Infiltration ขาดหายเป็นช่วงๆ ไม่ใช่
    ตลอดทั้งชุด — ขาดเฉพาะช่วง ก.พ.-พ.ค. 2569 (5 เดือนล่าสุดของ training set ณ ตอนตรวจสอบ)
    ส่วน มิ.ย.-ธ.ค. 2568 และ ม.ค. 2569 มี Infiltration รวมอยู่แล้วถูกต้อง และ evaporation
    หารด้วยจำนวนวันผิด (hardcode 30 แทนจำนวนวันจริงของเดือน) เฉพาะ ก.พ./มี.ค./พ.ค. 2569 เท่านั้น
    เดือนอื่นถูกต้องอยู่แล้ว (ดู reservoir_reference_data.py docstring สำหรับรายละเอียดต่อเดือนเต็ม)
    ผลกระทบเชิงตัวเลขต่อ Q_in_t เล็กน้อย: mean(|diff|) ~121 m3/day (~0.1% ของ Q_in_t เฉลี่ย
    ~121,668 m3/day) เทียบกับ Hurdle_RMSE ของโมเดล deploy จริงต่อ horizon (19,306-52,436 m3/day)
    คิดเป็นเพียง ~0.2-3% ของ RMSE โมเดลเอง — ไม่มีนัยสำคัญในแง่ความแม่นยำเชิงตัวเลข (regression)
    แต่กระทบ label ของ stage1 hurdle classifier ชัดเจนกว่า: ใน 46 วันที่ training set บันทึกเป็น
    'Inflow=0' (ถูก clip โดยสูตรเดิม) มี 45 วัน (เกือบทั้งหมด ทุกวันอยู่ในช่วง ก.พ.-พ.ค. 2569 ที่
    Infiltration ขาดหายพอดี) ที่ควรจะเป็นค่าบวกเล็กน้อย (~260-360 m3/day) ถ้าใช้สูตรที่แก้ไขแล้ว —
    เท่ากับว่าคลาส 'zero-inflow' ที่ stage1 ถูกออกแบบมาจับ อาจแทบไม่เหลือเลยถ้า retrain ด้วยข้อมูล
    ที่แก้บั๊กแล้ว เป็นผลกระทบเชิงโครงสร้างต่อ label ไม่ใช่แค่ noise ต่อเนื่อง ยังไม่ได้ retrain
    โมเดลที่ deploy อยู่ด้วยข้อมูลที่แก้ไขแล้ว ณ วันที่บันทึกนี้ (2026-07-05) — เป็นการตัดสินใจที่
    รอไว้ก่อน (ต้องชั่งน้ำหนักผลกระทบต่อ label กับความคุ้มค่าของการ retrain) การใช้สูตรที่แก้ไขแล้ว
    ใน pipeline สด (compute_daily_inflow() ของ reservoir_reference_data.py) ยังคงเดินหน้าต่อได้ตาม
    แผนเดิม แยกจากประเด็นการ retrain นี้โดยสิ้นเชิง — โมเดลที่ deploy อยู่ตอนนี้ train ด้วยข้อมูลเดิม
    (สูตรเก่าปนสูตรถูกตามเดือน) ไม่ใช่สูตรที่แก้ไขแล้ว การรันสด (prediction) กับ feature ที่คำนวณด้วย
    สูตรใหม่จึงมี train/serve skew เล็กน้อยจากประเด็นนี้ด้วย (แยกอีกเรื่องจากผลกระทบต่อ label ข้างต้น)"

decided_by: ผู้ใช้ยืนยันกับ Claude ในบทสนทนา 2026-07-05 (ตรวจสอบเต็มด้วยการอ่าน cell formula จริง
ของไฟล์ดิบทั้ง 13 ไฟล์ 2025_June-2026_June + merge กับ Training_Values_Nofct_7day_Final.csv)

Rating Curve lookup ต้อง replicate พฤติกรรม Excel `XLOOKUP(lookup_value, lookup_array,
return_array, , -1)` เป๊ะ — match_mode=-1 คือ "exact match หรือค่าที่เล็กกว่าถัดไป" (STEP LOOKUP /
floor) **ไม่ใช่ linear interpolation** ยืนยันด้วยข้อมูลจริง 2 แถวใน 2026_May_MNR.xlsx:
water_level=489.643 (date=20) และ water_level=489.644 (date=22) ต่าง floor ลงที่ 489.64 เหมือนกัน
เลยได้ Volume เท่ากันเป๊ะ (1655645.1614623) ทั้งที่ water_level ต่างกัน — ถ้า implement ผิดเป็น
interpolation ค่าทั้งสองแถวนี้จะต่างกัน (ดู test_reservoir_reference_data.py)
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date as date_cls, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional, Sequence, Union

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DIR = PROJECT_ROOT / "01_data" / "Reservoirs" / "reference"

RATING_CURVE_CSV = REFERENCE_DIR / "rating_curve_1cm.csv"
FLOW_RATE_SPILLWAY_CSV = REFERENCE_DIR / "flow_rate_spillway.csv"
FLOW_RATE_INLET_CSV = REFERENCE_DIR / "flow_rate_inlet.csv"
MONTHLY_EVAP_NORM_JSON = REFERENCE_DIR / "monthly_evap_norm.json"
WEIR_CONSTANTS_JSON = REFERENCE_DIR / "weir_constants.json"

# ---------------------------------------------------------------------------
# Constants ที่ไม่ได้อยู่ในไฟล์อ้างอิง (มาจากสูตรที่ยืนยันกับผู้ใช้ 5 ก.ค. 2569 ตรงๆ)
# ---------------------------------------------------------------------------
PAN_COEFFICIENT = 0.7                  # ค่าคงที่แปลง pan evaporation -> reservoir evaporation
INFILTRATION_RATE_M_PER_DAY = 0.001    # Infiltration = Area(m2) * ค่านี้

MONTH_NUM_TO_ABBR = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
}
MONTH_NAME_TO_ABBR = {
    "January": "JAN", "February": "FEB", "March": "MAR", "April": "APR",
    "May": "MAY", "June": "JUN", "July": "JUL", "August": "AUG",
    "September": "SEP", "October": "OCT", "November": "NOV", "December": "DEC",
}


# ===========================================================================
# ส่วนที่ 1: Reference data lookups
# ===========================================================================


@dataclass(frozen=True)
class RatingCurveRow:
    msl_height_m: float
    z_factor: float
    area_m2: float
    volume_m3: float


class RatingCurve:
    """
    Lookup table Area(m2)/Volume(m3) ต่อระดับน้ำ (rating_curve_1cm.csv)

    ต้อง replicate พฤติกรรม Excel `XLOOKUP(lookup_value, lookup_array, return_array, , -1)` เป๊ะ:
    match_mode = -1 = "exact match หรือค่าที่เล็กกว่าถัดไป (next smaller item)" — เป็น STEP LOOKUP
    (floor ไปที่ขั้นบันไดที่ใกล้ที่สุดจากด้านล่าง) **ไม่ใช่ linear interpolation**

    ตัวอย่างจริง (2026_May_MNR.xlsx): water_level=489.643 -> floor ไปที่ msl_height_m=489.64
    (ไม่ interpolate ระหว่าง 489.64-489.65) -> Volume=1655645.1614623
    """

    def __init__(self, rows: Sequence[RatingCurveRow]):
        # เรียงจากมากไปน้อย (ตรงกับลำดับในไฟล์ต้นฉบับ) ให้ step-lookup (floor) ทำงานถูกต้อง
        self._rows: list[RatingCurveRow] = sorted(rows, key=lambda r: r.msl_height_m, reverse=True)
        if not self._rows:
            raise ValueError("RatingCurve: rows ว่างเปล่า — โหลดไฟล์ rating_curve_1cm.csv ไม่สำเร็จ?")
        self._min_level = self._rows[-1].msl_height_m
        self._max_level = self._rows[0].msl_height_m

    @classmethod
    def from_csv(cls, path: Path = RATING_CURVE_CSV) -> "RatingCurve":
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(
                    RatingCurveRow(
                        msl_height_m=float(r["msl_height_m"]),
                        z_factor=float(r["z_factor"]),
                        area_m2=float(r["area_m2"]),
                        volume_m3=float(r["volume_m3"]),
                    )
                )
        return cls(rows)

    def lookup(self, water_level: float) -> RatingCurveRow:
        """
        Step lookup แบบ XLOOKUP(match_mode=-1): คืนแถวที่ msl_height_m <= water_level ที่ "ใกล้
        water_level ที่สุด" (exact match ถ้ามีพอดี ไม่งั้นเอาค่าที่เล็กกว่าถัดไป)

        ถ้า water_level ต่ำกว่าค่าต่ำสุดในตาราง -> ValueError (เทียบเท่า Excel #N/A เพราะไม่มี
        "ค่าที่เล็กกว่าถัดไป" ให้ fallback จริงๆ)
        ถ้า water_level สูงกว่าหรือเท่ากับค่าสูงสุดในตาราง -> คืนแถวบนสุด (กัน crash เฉยๆ
        ในทางปฏิบัติ water_level ของอ่างจริงไม่เกิน spillway crest ~489.5-490.5m อยู่แล้ว)
        """
        if water_level < self._min_level:
            raise ValueError(
                f"RatingCurve.lookup: water_level={water_level} ต่ำกว่าค่าต่ำสุดในตาราง "
                f"({self._min_level}) — เทียบเท่า Excel XLOOKUP(match_mode=-1) คืนค่า #N/A"
            )
        if water_level >= self._max_level:
            return self._rows[0]
        for row in self._rows:
            if row.msl_height_m <= water_level:
                return row
        raise ValueError(f"RatingCurve.lookup: หา water_level={water_level} ไม่พบ (ไม่ควรเกิดขึ้น)")

    def area_m2(self, water_level: float) -> float:
        return self.lookup(water_level).area_m2

    def volume_m3(self, water_level: float) -> float:
        return self.lookup(water_level).volume_m3


@dataclass(frozen=True)
class FlowRateRow:
    valve_turns: int
    avg_v_ms: float
    avg_q_m3h: float
    avg_q_m3min: float


class FlowRateTable:
    """
    Lookup ตาราง flow rate ต่อฝั่งท่อ (สปิลเวย์ / ทางเข้าอ่าง) จากจำนวนรอบวาล์ว (valve_turns)
    Exact match เท่านั้น (valve_turns เป็นจำนวนเต็ม ไม่มีค่ากลาง ไม่ต้อง step lookup/interpolation)
    """

    def __init__(self, rows: Sequence[FlowRateRow], name: str = ""):
        self._by_turns: dict[int, FlowRateRow] = {r.valve_turns: r for r in rows}
        self.name = name

    @classmethod
    def from_csv(cls, path: Path, name: str = "") -> "FlowRateTable":
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(
                    FlowRateRow(
                        valve_turns=int(float(r["valve_turns"])),
                        avg_v_ms=float(r["avg_v_ms"]),
                        avg_q_m3h=float(r["avg_q_m3h"]),
                        avg_q_m3min=float(r["avg_q_m3min"]),
                    )
                )
        return cls(rows, name=name or path.stem)

    def q_m3_per_hour(self, valve_turns: int) -> float:
        row = self._by_turns.get(int(valve_turns))
        if row is None:
            raise ValueError(
                f"FlowRateTable[{self.name}]: ไม่มีข้อมูล valve_turns={valve_turns} ในตาราง "
                f"(ค่าที่มี: {sorted(self._by_turns)})"
            )
        return row.avg_q_m3h


def load_monthly_evap_norm(path: Path = MONTHLY_EVAP_NORM_JSON) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_evap_norm_mm(month: Union[int, str], evap_norm: Optional[dict] = None) -> float:
    """
    คืนค่าระเหยเฉลี่ยรายเดือน (mm/เดือน) รับ month เป็น int (1-12), ชื่อเดือนเต็มภาษาอังกฤษ
    ("May"), หรือตัวย่อ 3 ตัวอักษร ("MAY") ก็ได้ (case-insensitive สำหรับตัวย่อ)
    """
    if evap_norm is None:
        evap_norm = get_default_evap_norm()
    if isinstance(month, int):
        key = MONTH_NUM_TO_ABBR.get(month)
        if key is None:
            raise ValueError(f"get_evap_norm_mm: เดือนต้องอยู่ระหว่าง 1-12 (ได้รับ {month})")
    elif month in MONTH_NAME_TO_ABBR:
        key = MONTH_NAME_TO_ABBR[month]
    else:
        key = str(month).upper()
    if key not in evap_norm:
        raise ValueError(f"get_evap_norm_mm: ไม่รู้จักเดือน {month!r} (key ที่แปลงแล้ว: {key!r})")
    return evap_norm[key]


@dataclass(frozen=True)
class WeirConstants:
    """
    ค่าคงที่ทางกายภาพของสปิลเวย์ (weir_constants.json)
    Q(m3/s) = C * L * H^1.5 ,  H = max(0, water_level - spillway_level_msl)
    Volume(m3/h) = Q(m3/s) * 3600

    หมายเหตุ: ใช้ water_level ดิบจากโทรมาตรตรงๆ **ไม่ใช่** water_level(ADJ) (=water_level-0.155)
    ที่เคยเห็นใน Spillway_Overflow_calculation.xlsx — ผู้ใช้ยืนยันแล้วว่า ADJ ไม่ได้ใช้แล้ว
    (5 ก.ค. 2569 — ดู README.md ของ 01_data/Reservoirs/reference/)
    """

    spillway_level_msl: float
    weir_coefficient_C: float
    weir_length_L: float

    @classmethod
    def from_json(cls, path: Path = WEIR_CONSTANTS_JSON) -> "WeirConstants":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return cls(
            spillway_level_msl=float(d["spillway_level_msl"]),
            weir_coefficient_C=float(d["weir_coefficient_C"]),
            weir_length_L=float(d["weir_length_L"]),
        )

    def head_m(self, water_level: float) -> float:
        return max(0.0, water_level - self.spillway_level_msl)

    def flow_rate_m3_per_s(self, water_level: float) -> float:
        h = self.head_m(water_level)
        if h <= 0.0:
            return 0.0
        return self.weir_coefficient_C * self.weir_length_L * (h ** 1.5)

    def flow_volume_m3_per_hour(self, water_level: float) -> float:
        return self.flow_rate_m3_per_s(water_level) * 3600.0


# ---------------------------------------------------------------------------
# Default (lazy-loaded) singletons — โหลดจากไฟล์ครั้งเดียวต่อ process แล้ว cache ไว้
# ทุก compute_* function ด้านล่างรับ instance เหล่านี้เป็น optional parameter เสมอ
# (ไม่ผูกกับ default) เพื่อให้ unit test inject ค่าจำลองแทนได้ตรงตามข้อกำหนด
# ---------------------------------------------------------------------------
_default_rating_curve: Optional[RatingCurve] = None
_default_evap_norm: Optional[dict] = None
_default_weir_constants: Optional[WeirConstants] = None
_default_flow_rate_spillway: Optional[FlowRateTable] = None
_default_flow_rate_inlet: Optional[FlowRateTable] = None


def get_default_rating_curve() -> RatingCurve:
    global _default_rating_curve
    if _default_rating_curve is None:
        _default_rating_curve = RatingCurve.from_csv()
    return _default_rating_curve


def get_default_evap_norm() -> dict:
    global _default_evap_norm
    if _default_evap_norm is None:
        _default_evap_norm = load_monthly_evap_norm()
    return _default_evap_norm


def get_default_weir_constants() -> WeirConstants:
    global _default_weir_constants
    if _default_weir_constants is None:
        _default_weir_constants = WeirConstants.from_json()
    return _default_weir_constants


def get_default_flow_rate_spillway() -> FlowRateTable:
    global _default_flow_rate_spillway
    if _default_flow_rate_spillway is None:
        _default_flow_rate_spillway = FlowRateTable.from_csv(FLOW_RATE_SPILLWAY_CSV, name="spillway")
    return _default_flow_rate_spillway


def get_default_flow_rate_inlet() -> FlowRateTable:
    global _default_flow_rate_inlet
    if _default_flow_rate_inlet is None:
        _default_flow_rate_inlet = FlowRateTable.from_csv(FLOW_RATE_INLET_CSV, name="inlet")
    return _default_flow_rate_inlet


# ===========================================================================
# ส่วนที่ 2: Water-balance term functions
# ===========================================================================
# แต่ละฟังก์ชันรับ water_level/rainfall/ฯลฯ เป็น parameter ตรงๆ ไม่ผูกกับแหล่งข้อมูล (Excel/CSV/
# API ใดๆ) เพื่อให้ unit-testable อิสระ — ชั้นที่อ่านไฟล์จริง (เช่น _ri_load_raw_monthly_data() ใน
# data_pipeline.py) มีหน้าที่แปลงข้อมูลดิบให้อยู่ในรูป parameter เหล่านี้ก่อนเรียกใช้


def compute_delta_storage(
    level_today: float,
    level_yesterday: float,
    rating_curve: Optional[RatingCurve] = None,
) -> float:
    """ΔS = Volume(level_today) − Volume(level_yesterday)"""
    rc = rating_curve or get_default_rating_curve()
    return rc.volume_m3(level_today) - rc.volume_m3(level_yesterday)


def compute_rain_term(
    level: float,
    rain_mm: float,
    rating_curve: Optional[RatingCurve] = None,
) -> float:
    """R = Area(level) × Rain_mm / 1000"""
    rc = rating_curve or get_default_rating_curve()
    return rc.area_m2(level) * rain_mm / 1000.0


def compute_evap_term(
    level: float,
    month: Union[int, str],
    days_in_month: int,
    rating_curve: Optional[RatingCurve] = None,
    evap_norm: Optional[dict] = None,
    pan_coefficient: float = PAN_COEFFICIENT,
) -> float:
    """
    E = Area(level) × (MonthlyEvapNorm[เดือน]/days_in_month × pan_coefficient) / 1000

    หมายเหตุ: ใช้ days_in_month ของเดือนนั้นจริง (28-31) ไม่ hardcode เป็น 30 เหมือนที่พบใน
    cell formula จริงของ 2026_May_MNR.xlsx (ดู docstring หัวไฟล์ ข้อค้นพบข้อ 2 — ยังไม่ได้ยืนยัน
    กับผู้ใช้ว่าเป็น bug ที่ต้องแก้เหมือน Infiltration หรือไม่ ควรตรวจสอบเพิ่มเติม)
    """
    if days_in_month <= 0:
        raise ValueError(f"compute_evap_term: days_in_month ต้องมากกว่า 0 (ได้รับ {days_in_month})")
    rc = rating_curve or get_default_rating_curve()
    norm_mm = get_evap_norm_mm(month, evap_norm)
    return rc.area_m2(level) * ((norm_mm / days_in_month) * pan_coefficient) / 1000.0


def compute_infiltration_term(
    level: float,
    rating_curve: Optional[RatingCurve] = None,
    rate_m_per_day: float = INFILTRATION_RATE_M_PER_DAY,
) -> float:
    """
    Infiltration = Area(level) × 0.001

    หมายเหตุ: สูตร Inflow จริงในไฟล์ Excel ต้นฉบับไม่ได้รวม term นี้เข้าไปเลย (bug ที่ผู้ใช้ยืนยัน
    แล้วว่าต้องแก้ — ดู docstring หัวไฟล์ ข้อค้นพบข้อ 1) compute_daily_inflow() ด้านล่างรวม term
    นี้เข้าไปในผลรวมเสมอ
    """
    rc = rating_curve or get_default_rating_curve()
    return rc.area_m2(level) * rate_m_per_day


def compute_spillway_daily(
    hourly_levels: Sequence[float],
    weir: Optional[WeirConstants] = None,
) -> float:
    """
    Spill(day) = sum ของ weir formula (Volume m3/h) คำนวณจาก water_level รายชั่วโมง 24 ค่าใน 1 วัน

    ต้องได้รับ hourly_levels ยาวเป๊ะ 24 ค่า (1 ค่า/ชั่วโมง เรียงตามเวลาในวันนั้น) — ถ้าข้อมูล
    โทรมาตรราย ชม. ขาดหายบางชั่วโมงจริง เป็นหน้าที่ของชั้นเรียกใช้ (data ingestion) ที่ต้อง
    ตัดสินใจว่าจะเติมค่า/ข้ามวันนั้นอย่างไรก่อนเรียกฟังก์ชันนี้ ไม่ใช่หน้าที่ของฟังก์ชันนี้
    """
    if len(hourly_levels) != 24:
        raise ValueError(
            f"compute_spillway_daily: ต้องการ water_level ราย ชม. 24 ค่าเป๊ะ (ได้รับ {len(hourly_levels)})"
        )
    w = weir or get_default_weir_constants()
    return sum(w.flow_volume_m3_per_hour(lvl) for lvl in hourly_levels)


def compute_outlet_release(
    date: Any,
    events: Sequence[dict],
    flow_rate_spillway: Optional[FlowRateTable] = None,
    flow_rate_inlet: Optional[FlowRateTable] = None,
) -> float:
    """
    O(day) = sum ของ (จำนวนชั่วโมงที่ event overlap กับวันที่ `date` จริง) × flow_rate(ฝั่ง, valve_turns)

    รับ `events` เป็น list ของ dict ที่ **normalize แล้ว** แต่ละอันมี key:
      - start (datetime.datetime): เวลาที่เริ่มเปิดวาล์ว
      - end   (datetime.datetime): เวลาที่ปิดวาล์ว
      - valve_turns (int): จำนวนรอบที่เปิดวาล์ว
      - pipe_side (str): "spillway" หรือ "inlet"

    ตั้งใจไม่รับ event log รูปแบบดิบตรงจากไฟล์ Excel ("ตารางปล่อยน้ำ" ใช้วันที่ พ.ศ. เป็นข้อความ
    เช่น "26 มิ.ย 68" แยกคอลัมน์ชั่วโมงเริ่ม/ปิดเป็นตัวเลขเดี่ยว) — การ parse/normalize รูปแบบไฟล์
    ต้นฉบับเป็นความรับผิดชอบของชั้นอ่านข้อมูลดิบ (เช่นใน data_pipeline.py) แยกต่างหาก เพื่อให้
    ฟังก์ชันนี้ทดสอบง่ายและไม่ผูกกับรูปแบบไฟล์ที่อาจเปลี่ยนได้
    """
    fr_spillway = flow_rate_spillway or get_default_flow_rate_spillway()
    fr_inlet = flow_rate_inlet or get_default_flow_rate_inlet()

    day_start = datetime.combine(date, time.min)
    day_end = day_start + timedelta(days=1)

    total_m3 = 0.0
    for ev in events:
        overlap_start = max(ev["start"], day_start)
        overlap_end = min(ev["end"], day_end)
        overlap_hours = (overlap_end - overlap_start).total_seconds() / 3600.0
        if overlap_hours <= 0:
            continue
        side = ev["pipe_side"]
        if side == "spillway":
            q_m3h = fr_spillway.q_m3_per_hour(ev["valve_turns"])
        elif side == "inlet":
            q_m3h = fr_inlet.q_m3_per_hour(ev["valve_turns"])
        else:
            raise ValueError(f"compute_outlet_release: pipe_side ไม่รู้จัก: {side!r} (ต้องเป็น 'spillway'/'inlet')")
        total_m3 += q_m3h * overlap_hours
    return total_m3


def compute_daily_inflow(
    level_today: float,
    level_yesterday: float,
    rain_mm: float,
    month: Union[int, str],
    days_in_month: int,
    hourly_levels: Sequence[float],
    date: Any,
    events: Sequence[dict],
    *,
    rating_curve: Optional[RatingCurve] = None,
    evap_norm: Optional[dict] = None,
    weir: Optional[WeirConstants] = None,
    flow_rate_spillway: Optional[FlowRateTable] = None,
    flow_rate_inlet: Optional[FlowRateTable] = None,
    clip_negative_to_zero: bool = True,
) -> dict:
    """
    รวมทุก term ตามสูตร Inflow(day) = ΔS − R + O + Spill + E + Infiltration
    (ยืนยันกับผู้ใช้ 5 ก.ค. 2569 — รวม Infiltration เข้าไปเสมอ ต่างจากสูตรเดิมใน Excel ที่ไม่ได้
    รวม ซึ่งเป็น bug ที่ยืนยันแล้วว่าต้องแก้ ดู docstring หัวไฟล์)

    คืนค่าเป็น dict มี inflow_m3 (ผลรวมสุดท้าย, clip ที่ 0 ถ้า clip_negative_to_zero=True ตาม
    พฤติกรรมเดิมของสูตร Excel: `IF(...<0, 0, ...)`) พร้อม breakdown ของแต่ละ term แยกไว้ debug
    """
    delta_storage = compute_delta_storage(level_today, level_yesterday, rating_curve)
    rain_term = compute_rain_term(level_today, rain_mm, rating_curve)
    evap_term = compute_evap_term(level_today, month, days_in_month, rating_curve, evap_norm)
    infiltration_term = compute_infiltration_term(level_today, rating_curve)
    spill_term = compute_spillway_daily(hourly_levels, weir)
    outlet_term = compute_outlet_release(date, events, flow_rate_spillway, flow_rate_inlet)

    raw_inflow = delta_storage - rain_term + outlet_term + spill_term + evap_term + infiltration_term
    inflow_m3 = max(0.0, raw_inflow) if clip_negative_to_zero else raw_inflow

    return {
        "inflow_m3": inflow_m3,
        "raw_inflow_before_clip_m3": raw_inflow,
        "delta_storage_m3": delta_storage,
        "rain_term_m3": rain_term,
        "evap_term_m3": evap_term,
        "infiltration_term_m3": infiltration_term,
        "spill_term_m3": spill_term,
        "outlet_term_m3": outlet_term,
    }
