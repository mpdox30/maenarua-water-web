"""
test_full_pipeline_live.py
===========================
สคริปต์ทดสอบแบบ manual (ไม่ใช่ส่วนหนึ่งของ pipeline เอง) สำหรับรัน run_pipeline() เต็มรูปแบบ 1 รอบ
บนเครื่อง Windows จริง เพื่อยืนยันว่า:

  1. Step 2/5 ใหม่ (_fetch_climate_features_step — MEI -> CHIRPS -> ERA5T) ทำงานร่วมกับ
     Step 1/5 (telemetry), Step 3/5 (SAR), Step 4/5 (model predict), Step 5/5 (save latest.json)
     เดิมได้โดยไม่ทำให้ pipeline พัง (ไม่ crash ทั้งโปรแกรม แม้บาง step ย่อยจะ fetch_error ก็ตาม)
  2. ml_features_live.csv มีแถวใหม่ถูก append เข้ามาจริง (2 แถวต่อรอบ: zone_A, zone_B)
  3. ค่า MEI/CHIRPS/ERA5T/AI_week ที่ได้ "ดูสมเหตุสมผล" ก่อนจะตัดสินใจเชื่อมเข้ากับ
     _wd_build_feature_vector() จริงในขั้นต่อไป (ยังไม่เชื่อมตอนนี้ตามที่ตกลงกันไว้)
  4. latest.json (Water Demand / Reservoir Inflow) ยังคงเขียนออกมาได้ตามปกติเหมือนก่อนมี Step 2/5

ข้อจำกัดที่ต้องรู้ก่อนรัน (ทำไมต้องรันบนเครื่องจริง ไม่ใช่ sandbox):
  - MEI: ต้องมีอินเทอร์เน็ตเข้าถึง NOAA PSL/NOAA CPC ได้
  - CHIRPS: ต้องเคยรัน ee.Authenticate() (Google Earth Engine, personal credential) บนเครื่องนี้
    มาก่อนแล้วอย่างน้อยหนึ่งครั้ง (ยังไม่ได้เปลี่ยนเป็น Service Account — ดู known_limitations ใน
    Water_demand/active/model_metadata.json) ถ้ายังไม่เคย auth จะเห็น fetch_error ของ CHIRPS
    ทั้งสอง zone แต่ pipeline จะไม่ crash (ตาม error-isolation design)
  - ERA5T: ต้องมี .cdsapirc ตั้งไว้แล้ว + conda env "era5-grib" (ArcGIS Pro) พร้อมใช้งานจริง
    (ยืนยันแล้วก่อนหน้านี้ว่าใช้งานได้ — ดู pipeline/ARCHITECTURE.md) และเนื่องจากเป็นโหมดรายสัปดาห์
    (--as-of-date) ครั้งแรกที่รันจริง มีความเป็นไปได้สูงที่ n_days_in_week จะน้อย/เป็น 0 โดยเฉพาะถ้า
    รันในช่วงต้นสัปดาห์ (ดูคำอธิบายใน docstring ของ era5t_worker.py::_run_weekly_mode()) — ไม่ใช่ bug

วิธีรัน (จากโฟลเดอร์ 01_data/scripts and code/pipeline/ ด้วย python ของ .venv หลักของโปรเจกต์
ไม่ใช่ python.exe ของ era5-grib — data_pipeline.py จะไปเรียก era5-grib เองผ่าน subprocess ตอน
ต้องการ ERA5T เท่านั้น):
    ..\\..\\..\\.venv\\Scripts\\python.exe test_full_pipeline_live.py
"""
import csv
import json
import sys
from pathlib import Path

import data_pipeline

SCRIPT_DIR = Path(__file__).resolve().parent


def _print_section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main() -> int:
    _print_section("1) รัน run_pipeline() เต็มรูปแบบ 1 รอบ")
    result = data_pipeline.run_pipeline()

    print(f"สถานะรวม: {result.status}")
    print("step_status:")
    # marker รู้จัก 3 สถานะแยกกัน (แก้ไข 2026-07-05): "partial" (เช่น climate_features ที่ได้ข้อมูล
    # บางส่วน/low_confidence แต่ไม่ crash) เป็นพฤติกรรมที่ถูกต้องและตั้งใจออกแบบไว้ — ไม่ควรโชว์เป็น
    # [FAIL] เหมือน step ที่พังจริง (exception) เพราะจะทำให้เข้าใจผิดว่าเป็นบั๊กตอนเปิด report ทีหลัง
    STATUS_MARKERS = {"ok": "OK     ", "partial": "PARTIAL", "failed": "FAIL   "}
    for step, status in result.step_status.items():
        marker = STATUS_MARKERS.get(status, "FAIL   ")  # ค่าอื่นที่ไม่รู้จัก (ไม่ควรเกิดขึ้น) ถือเป็น FAIL ไว้ก่อน กันเหนียว
        print(f"    [{marker}] {step} ({status})")

    if result.errors:
        print("\nรายละเอียด errors:")
        for err in result.errors:
            print(f"    - {err}")

    _print_section("2) ตรวจสอบว่า Step 2/5 (climate_features) รันแล้วไม่ทำให้ step อื่นพังไปด้วย")
    critical_steps = ["telemetry", "sar_classification", "prediction", "save_results"]
    other_steps_ok = all(result.step_status.get(s) == "ok" for s in critical_steps)
    print(f"telemetry/sar_classification/prediction/save_results ทั้งหมด = ok: "
          f"{'PASS' if other_steps_ok else 'FAIL (ดู step_status ด้านบนว่า step ไหนพัง)'}")

    climate_status = result.step_status.get("climate_features")
    print(f"climate_features step_status: {climate_status} "
          f"({'ไม่ crash ทั้งโปรแกรม แม้อาจมี fetch_error ย่อยบางจุด' if climate_status else 'ไม่พบ key นี้ใน step_status — ตรวจสอบว่า Step 2/5 ถูกเรียกจริงหรือไม่'})")

    _print_section("3) ตรวจสอบ latest.json ยังเขียนได้ตามปกติ (ไม่กระทบจาก Step 2/5 ใหม่)")
    if data_pipeline.OUTPUT_PATH.exists():
        with open(data_pipeline.OUTPUT_PATH, encoding="utf-8") as f:
            latest = json.load(f)
        print(f"latest.json run_timestamp: {latest.get('run_timestamp')}")
        print(f"latest.json status: {latest.get('status')}")
        print(f"forecasts.demand_zone_a present: {latest.get('forecasts', {}).get('demand_zone_a') is not None}")
        print(f"forecasts.demand_zone_b present: {latest.get('forecasts', {}).get('demand_zone_b') is not None}")
        print(f"forecasts.inflow.status: {latest.get('forecasts', {}).get('inflow', {}).get('status')}")
    else:
        print(f"[FAIL] ไม่พบ {data_pipeline.OUTPUT_PATH}")

    _print_section("4) ตรวจสอบ ml_features_live.csv มีแถวใหม่ถูก append เข้ามาจริง")
    csv_path = data_pipeline.ML_FEATURES_LIVE_CSV
    if not csv_path.exists():
        print(f"[FAIL] ไม่พบ {csv_path} — คาดว่า _append_ml_features_live() ควรสร้างไฟล์นี้ไว้แล้ว")
        return 1

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"จำนวนแถวทั้งหมดใน {csv_path.name}: {len(rows)}")
    last_two = rows[-2:] if len(rows) >= 2 else rows
    print(f"\n2 แถวล่าสุด (ควรเป็น zone_A/zone_B ของรอบนี้):")
    for row in last_two:
        print(f"\n  zone={row.get('zone')}  run_timestamp={row.get('run_timestamp')}")
        print(f"    MEI={row.get('MEI')}  MEI_lag4={row.get('MEI_lag4')}  MEI_lag8={row.get('MEI_lag8')}  "
              f"mei_reporting_lag_risk={row.get('mei_reporting_lag_risk')}  mei_fetch_error={row.get('mei_fetch_error')}")
        print(f"    P_mm_week={row.get('P_mm_week')}  SPI_4={row.get('SPI_4')}  drought_flag={row.get('drought_flag')}  "
              f"chirps_data_type={row.get('chirps_data_type')}  chirps_fetch_error={row.get('chirps_fetch_error')}")
        print(f"    ET0_mm_week={row.get('ET0_mm_week')}  era5t_n_days_in_week={row.get('era5t_n_days_in_week')}  "
              f"era5t_fetch_error={row.get('era5t_fetch_error')}")
        print(f"    AI_week={row.get('AI_week')}  AI_week_status={row.get('AI_week_status')}")

    _print_section("5) สรุปความสมเหตุสมผลเบื้องต้น (sanity check ก่อนตัดสินใจเชื่อมโมเดลจริง)")
    sanity_notes = []
    for row in last_two:
        zone = row.get("zone")
        mei_val = row.get("MEI")
        if mei_val not in (None, ""):
            try:
                mei_f = float(mei_val)
                if not (-3.0 <= mei_f <= 3.0):
                    sanity_notes.append(f"{zone}: MEI={mei_f} อยู่นอกช่วงปกติ (-3 ถึง 3) ตรวจสอบ parse ให้ดี")
            except ValueError:
                pass
        et0_val = row.get("ET0_mm_week")
        if et0_val not in (None, ""):
            try:
                et0_f = float(et0_val)
                if not (0 <= et0_f <= 80):  # weekly ET0 ที่พะเยาไม่ควรเกินราว 12 mm/day*7
                    sanity_notes.append(f"{zone}: ET0_mm_week={et0_f} ดูผิดปกติ (ควรอยู่ราว 0-80 mm/week)")
            except ValueError:
                pass

    if sanity_notes:
        print("พบจุดที่ควรตรวจสอบเพิ่มเติม:")
        for note in sanity_notes:
            print(f"    - {note}")
    else:
        print("ไม่พบค่าที่ดูผิดปกติชัดเจนจาก sanity check เบื้องต้นนี้ (ไม่ได้แปลว่าถูกต้อง 100% "
              "แค่ไม่ได้หลุดช่วงที่สมเหตุสมผลคร่าวๆ)")

    print()
    if other_steps_ok:
        print("=== สรุป: [PASS] Step ใหม่ (climate_features) ทำงานร่วมกับ pipeline เดิมได้โดยไม่ทำให้ step อื่นพัง ===")
        return 0
    else:
        print("=== สรุป: [FAIL] มี step อื่น (นอกเหนือจาก climate_features) พังไปด้วย — ต้องตรวจสอบด่วน ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
