"""
test_reservoir_reference_data.py
===================================
Unit test สำหรับ reservoir_reference_data.py — ไม่ต้องพึ่ง network/GEE/CDS ใดๆ อ่านแค่ไฟล์
อ้างอิงใน 01_data/Reservoirs/reference/ และ 01_data/Reservoirs/inflow/2026/2026_May_MNR.xlsx
(ใช้ pandas/openpyxl อ่านค่าจริงมาเทียบเฉพาะตอนสร้างไฟล์นี้ — ค่าที่เทียบใน assert ด้านล่างเป็น
ค่าคงที่ที่คัดลอกมาจากผลตรวจสอบไฟล์จริงแล้ว ไม่ได้อ่านไฟล์ .xlsx ระหว่างรัน test)

โครงสร้าง:
  Section 1  RatingCurve            — step lookup (XLOOKUP match_mode=-1) ไม่ใช่ interpolation
  Section 2  FlowRateTable          — spillway/inlet lookup ตรงจำนวนรอบวาล์ว
  Section 3  MonthlyEvapNorm        — get_evap_norm_mm รับ int/full name/abbr
  Section 4  WeirConstants          — head_m/flow_rate/flow_volume + H clipping ที่ 0
  Section 5  compute_delta_storage  — เทียบค่าจริง 2026_May_MNR.xlsx (date 1->2)
  Section 6  compute_rain_term      — เทียบค่าจริง 2026_May_MNR.xlsx (date 20)
  Section 7  compute_evap_term      — พิสูจน์ความแตกต่างที่ตั้งใจจากสูตร Excel เดิม (hardcode 146.69/30)
  Section 8  compute_infiltration_term — พิสูจน์ความแตกต่างที่ตั้งใจ (ใช้ rating_curve ไม่ใช่ Area_Terrain)
  Section 9  compute_spillway_daily — synthetic 24-hour weir sum + H-clipping
  Section 10 compute_outlet_release — event log จริง (แปลง พ.ศ.->ค.ศ. แล้ว) overlap หลายกรณี
  Section 11 compute_daily_inflow   — integration test: replica สูตร Excel เดิม (bit-exact) vs
             สูตรที่แก้ไขแล้ว (ต่างกันเฉพาะจาก 2 จุดที่ตั้งใจแก้ ไม่มีจุดอื่นคลาดเคลื่อน)
"""
import sys
from datetime import date, datetime

sys.path.insert(0, r"D:\maenaruea-water-web\01_data\scripts and code\pipeline")
import reservoir_reference_data as rrd

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


rc = rrd.get_default_rating_curve()
fr_spillway = rrd.get_default_flow_rate_spillway()
fr_inlet = rrd.get_default_flow_rate_inlet()
evap_norm = rrd.get_default_evap_norm()
weir = rrd.get_default_weir_constants()

print("=== Section 1: RatingCurve step lookup (XLOOKUP match_mode=-1) ===")
row_643 = rc.lookup(489.643)
row_644 = rc.lookup(489.644)
check("489.643 -> floor msl=489.64 (ไม่ใช่ 489.65)", row_643.msl_height_m == 489.64)
check("489.644 -> floor msl=489.64 เหมือนกัน (พิสูจน์ step lookup ไม่ใช่ interpolation)",
      row_644.msl_height_m == 489.64)
check("489.643 กับ 489.644 ได้ Volume เท่ากันเป๊ะ (1655645.1614623) — ตรงกับ 2026_May_MNR.xlsx "
      "date=20 และ date=22", row_643.volume_m3 == row_644.volume_m3 == 1655645.1614623)
check("Area ที่ msl=489.64 == 302992.5428894 (ตรงกับไฟล์จริง)", row_643.area_m2 == 302992.5428894)
row_exact = rc.lookup(489.65)
check("exact match 489.65 คืนแถวตัวเอง (ไม่ floor ผิดไปแถวถัดไป)", row_exact.msl_height_m == 489.65)
try:
    rc.lookup(480.0)
    check("water_level ต่ำกว่าตารางต้อง raise ValueError", False)
except ValueError:
    check("water_level ต่ำกว่าตารางต้อง raise ValueError", True)
check("water_level เกิน max คืนแถวบนสุด (490.5) ไม่ crash", rc.lookup(500.0).msl_height_m == 490.5)

print("\n=== Section 2: FlowRateTable (exact match ตามจำนวนรอบวาล์ว) ===")
check("spillway valve_turns=6 -> avg_q_m3h ~ 393.6 (ตรงไฟล์จริง)",
      close(fr_spillway.q_m3_per_hour(6), 393.59999999999997))
check("inlet valve_turns=2 -> avg_q_m3h = 13.8 (ตรงไฟล์จริง)",
      close(fr_inlet.q_m3_per_hour(2), 13.8))
check("spillway valve_turns=1 -> 0 (ยังไม่เปิดวาล์วพอให้มีการไหล)",
      fr_spillway.q_m3_per_hour(1) == 0.0)
try:
    fr_spillway.q_m3_per_hour(999)
    check("valve_turns ที่ไม่มีในตารางต้อง raise ValueError", False)
except ValueError:
    check("valve_turns ที่ไม่มีในตารางต้อง raise ValueError", True)

print("\n=== Section 3: MonthlyEvapNorm ===")
check("get_evap_norm_mm(5) == MAY == 146.68923076923076", rrd.get_evap_norm_mm(5) == 146.68923076923076)
check("get_evap_norm_mm('May') == เดียวกับข้างบน", rrd.get_evap_norm_mm("May") == rrd.get_evap_norm_mm(5))
check("get_evap_norm_mm('MAY') (ตัวย่อ) == เดียวกัน", rrd.get_evap_norm_mm("MAY") == rrd.get_evap_norm_mm(5))
check("มีครบ 12 เดือนใน evap_norm dict", len(evap_norm) == 12)

print("\n=== Section 4: WeirConstants ===")
check("spillway_level_msl == 489.545", weir.spillway_level_msl == 489.545)
check("weir_coefficient_C == 1.82 และ weir_length_L == 30", weir.weir_coefficient_C == 1.82 and weir.weir_length_L == 30)
check("water_level ต่ำกว่า spillway crest -> head_m = 0 (ไม่ติดลบ)", weir.head_m(489.0) == 0.0)
check("water_level ต่ำกว่า spillway crest -> flow_rate = 0", weir.flow_rate_m3_per_s(489.0) == 0.0)
h01_q = weir.flow_rate_m3_per_s(489.545 + 0.1)
check("H=0.1 -> Q(m3/s) = C*L*H^1.5 = 1.7266036024519353", close(h01_q, 1.7266036024519353))
check("Volume(m3/h) = Q * 3600 = 6215.772968826967", close(weir.flow_volume_m3_per_hour(489.545 + 0.1), 6215.772968826967))

print("\n=== Section 5: compute_delta_storage (เทียบค่าจริง May date 1->2) ===")
delta_s = rrd.compute_delta_storage(488.814, 488.801)
check("ΔS(488.814, 488.801) == 2901.8524869999383 (ตรงกับ K7 ในไฟล์จริง)", close(delta_s, 2901.8524869999383))

print("\n=== Section 6: compute_rain_term (เทียบค่าจริง May date 20) ===")
r_term = rrd.compute_rain_term(489.643, 4.2)
check("R(489.643, rain=4.2mm) == 1272.56868013548 (ตรงกับ H24 ในไฟล์จริง เป๊ะ)", close(r_term, 1272.56868013548))

print("\n=== Section 7: compute_evap_term (ตั้งใจต่างจาก Excel เดิม — ดูเหตุผลใน docstring) ===")
e_term_correct = rrd.compute_evap_term(489.643, "May", 31)
check("E(489.643, May, days=31 จริง) == 1003.6135526348861 (สูตรที่แก้ไขแล้ว ใช้ days_in_month จริง)",
      close(e_term_correct, 1003.6135526348861))
# พิสูจน์ว่าความต่างมาจาก 2 จุดเจตนา (146.69 ปัดเศษ vs 146.68923... ค่าจริง, และ 30 vs 31 วัน) ไม่ใช่ bug อื่น
e_term_excel_replica = rrd.compute_evap_term(489.643, "May", 30, evap_norm={"MAY": 146.69})
check("ถ้า inject evap_norm=146.69 และ days_in_month=30 (จำลอง bug เดิมของ Excel) จะได้ 1037.0727760504085 "
      "ตรงกับคอลัมน์ Evaporation จริงในไฟล์เป๊ะ — ยืนยันว่า formula ถูกต้อง ต่างกันแค่ input ที่ตั้งใจแก้",
      close(e_term_excel_replica, 1037.0727760504085))

print("\n=== Section 8: compute_infiltration_term (ตั้งใจต่างจาก Excel เดิม — ใช้ rating_curve ไม่ใช่ Area_Terrain) ===")
infil_term = rrd.compute_infiltration_term(489.643)
check("Infiltration(489.643) == Area(rating_curve, floor 489.64)*0.001 == 302.9925428894",
      close(infil_term, 302.9925428894))
check("ค่านี้ไม่เท่ากับคอลัมน์ Infiltration จริงในไฟล์ (307.23725027043) เพราะไฟล์เดิมใช้ Area_Terrain "
      "(ตารางที่ถูกตัดออกแล้วตาม README) — ต่างกันเพราะ Area ต่างตาราง ไม่ใช่ formula ผิด",
      not close(infil_term, 307.23725027043, tol=1e-4))

print("\n=== Section 9: compute_spillway_daily (synthetic 24-hour) ===")
levels_no_spill = [489.0] * 24
check("24 ชม. อยู่ต่ำกว่า spillway crest ตลอด -> spill รวมทั้งวัน = 0",
      rrd.compute_spillway_daily(levels_no_spill) == 0.0)
levels_uniform_01 = [489.545 + 0.1] * 24
expected_uniform = 24 * 6215.772968826967
check("24 ชม. คงที่ที่ H=0.1 ตลอด -> รวม = 24 * Volume/hr ที่ H=0.1", close(rrd.compute_spillway_daily(levels_uniform_01), expected_uniform))
try:
    rrd.compute_spillway_daily([489.6] * 23)
    check("hourly_levels ต้องมี 24 ค่าเป๊ะ ไม่งั้น raise ValueError", False)
except ValueError:
    check("hourly_levels ต้องมี 24 ค่าเป๊ะ ไม่งั้น raise ValueError", True)

print("\n=== Section 10: compute_outlet_release (event log จริงจาก 2026_May_MNR.xlsx แปลง พ.ศ.->ค.ศ.) ===")
# แถวที่ 1 ของ sheet "ตารางปล่อยน้ำ": เปิดวาล์ว 6 รอบ ฝั่งสปิลเวย์ 26 มิ.ย. 2568(BE)=2025-06-26 10:00
# ถึง 14 ต.ค. 2568(BE)=2025-10-14 13:00 (แปลงเป็น ค.ศ. แล้วตรงตัว)
real_event = {
    "start": datetime(2025, 6, 26, 10, 0),
    "end": datetime(2025, 10, 14, 13, 0),
    "valve_turns": 6,
    "pipe_side": "spillway",
}
q_6_spillway = fr_spillway.q_m3_per_hour(6)
o_full_day = rrd.compute_outlet_release(date(2025, 7, 1), [real_event])
check("วันที่อยู่ในช่วง event เต็มวัน (2025-07-01) -> overlap 24 ชม. เต็ม",
      close(o_full_day, 24 * q_6_spillway))
o_start_day = rrd.compute_outlet_release(date(2025, 6, 26), [real_event])
check("วันแรกของ event (เริ่ม 10:00) -> overlap แค่ 14 ชม. (10:00-24:00)",
      close(o_start_day, 14 * q_6_spillway))
o_end_day = rrd.compute_outlet_release(date(2025, 10, 14), [real_event])
check("วันสุดท้ายของ event (ปิด 13:00) -> overlap แค่ 13 ชม. (00:00-13:00)",
      close(o_end_day, 13 * q_6_spillway))
o_no_overlap = rrd.compute_outlet_release(date(2025, 1, 1), [real_event])
check("วันที่ไม่ overlap กับ event ไหนเลย -> 0", o_no_overlap == 0.0)
o_empty = rrd.compute_outlet_release(date(2025, 7, 1), [])
check("ไม่มี event เลย -> 0", o_empty == 0.0)

print("\n=== Section 11: compute_daily_inflow (integration, เทียบ replica Excel เดิม vs สูตรที่แก้ไขแล้ว) ===")
# May date=2: level_yesterday(date1)=488.801, level_today(date2)=488.814, rain=0, ไม่มี spill/outlet วันนี้
level_today, level_yesterday, rain_mm = 488.814, 488.801, 0.0
no_spill_hours = [480.0] * 24  # ต่ำกว่า spillway crest ตลอด -> spill=0 ตรงกับ F7=0 ในไฟล์จริง

result_corrected = rrd.compute_daily_inflow(
    level_today, level_yesterday, rain_mm, "May", 31, no_spill_hours, date(2026, 5, 2), [],
)
check("compute_daily_inflow (สูตรที่แก้ไขแล้ว) ให้ raw_inflow == 4153.387973260127",
      close(result_corrected["raw_inflow_before_clip_m3"], 4153.387973260127))

# Replica สูตร Excel เดิม (ไม่รวม Infiltration, evap hardcode 146.69/30) เพื่อพิสูจน์ว่าต่างกันเฉพาะ
# 2 จุดที่ตั้งใจแก้ ไม่มีจุดอื่นคลาดเคลื่อน — คำนวณ raw_inflow ตรงๆ ไม่ผ่าน compute_infiltration_term
delta_s_2 = rrd.compute_delta_storage(level_today, level_yesterday)
r_2 = rrd.compute_rain_term(level_today, rain_mm)
e_2_excel_buggy = rrd.compute_evap_term(level_today, "May", 30, evap_norm={"MAY": 146.69})
spill_2 = rrd.compute_spillway_daily(no_spill_hours)
outlet_2 = rrd.compute_outlet_release(date(2026, 5, 2), [])
excel_replica_inflow = delta_s_2 - r_2 + outlet_2 + spill_2 + e_2_excel_buggy  # ไม่บวก Infiltration
check("replica สูตร Excel เดิม (ΔS-R+O+Spill+E, ไม่มี Infiltration, evap hardcode) == 3895.21489783474 "
      "(ตรงกับ Inflow (M3) จริงในไฟล์ 2026_May_MNR.xlsx date=2 เป๊ะ)",
      close(excel_replica_inflow, 3895.21489783474))

diff = result_corrected["raw_inflow_before_clip_m3"] - excel_replica_inflow
expected_diff = result_corrected["infiltration_term_m3"] + (e_2_excel_buggy - result_corrected["evap_term_m3"]) * -1
# diff ต้อง = infiltration_term (ที่เพิ่มเข้ามาใหม่) + (evap_corrected - evap_excel_buggy)
expected_diff2 = result_corrected["infiltration_term_m3"] + (result_corrected["evap_term_m3"] - e_2_excel_buggy)
check("ผลต่างระหว่างสูตรที่แก้ไขแล้วกับ replica Excel เดิม อธิบายได้ครบ 100% ด้วย 2 จุดที่ตั้งใจแก้เท่านั้น "
      "(Infiltration ที่เพิ่มเข้ามา + evap ที่เปลี่ยนวิธีคำนวณ) ไม่มีความคลาดเคลื่อนจากจุดอื่น",
      close(diff, expected_diff2, tol=1e-9))
check("inflow_m3 (หลัง clip) เท่ากับ raw_inflow เพราะเป็นบวกอยู่แล้ว ไม่ต้อง clip",
      result_corrected["inflow_m3"] == result_corrected["raw_inflow_before_clip_m3"])
neg_result = rrd.compute_daily_inflow(488.0, 489.0, 0.0, "May", 31, no_spill_hours, date(2026, 5, 2), [])
check("ถ้า raw_inflow ติดลบ (เช่น level ลดฮวบ) -> inflow_m3 ถูก clip เป็น 0 ตาม IF(...<0,0,...) ของ Excel เดิม",
      neg_result["inflow_m3"] == 0.0 and neg_result["raw_inflow_before_clip_m3"] < 0.0)

print()
n_pass = sum(1 for _, ok in checks if ok)
print(f"สรุป: {n_pass}/{len(checks)} PASS")
sys.exit(0 if n_pass == len(checks) else 1)
