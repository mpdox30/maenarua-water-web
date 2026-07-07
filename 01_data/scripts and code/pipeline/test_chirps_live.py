"""
test_chirps_live.py
====================
สคริปต์ทดสอบแบบ manual (ไม่ใช่ส่วนหนึ่งของ pipeline) สำหรับรัน "1 ครั้ง" บนเครื่องที่ตั้งค่า
Earth Engine ไว้แล้ว (project='maenaruea-water-pipeline' ตามที่ยืนยันแล้วว่า
ee.Initialize(project='maenaruea-water-pipeline') + ee.String('test').getInfo() ใช้ได้จริง)

วิธีรัน (จากโฟลเดอร์ 01_data/scripts and code/pipeline/):
    ..\..\..\.venv\Scripts\python.exe test_chirps_live.py

หมายเหตุ: รันไฟล์นี้จากเครื่องของคุณเองเท่านั้น — รันจาก sandbox ของ Claude ไม่ได้ เพราะ sandbox
ไม่มี Earth Engine credentials ของคุณ และ endpoint ของ GEE (earthengine.googleapis.com,
oauth2.googleapis.com) ถูกบล็อกจาก network ของ sandbox ด้วย (ยืนยันแล้วด้วย curl คืนค่า HTTP:000)
"""
import json
import sys
from datetime import date, timedelta

import ee

import chirps_feature

GEE_PROJECT = chirps_feature.DEFAULT_GEE_PROJECT  # "maenaruea-water-pipeline"


def main() -> int:
    print(f"=== 1) ee.Initialize(project='{GEE_PROJECT}') ===")
    ee.Initialize(project=GEE_PROJECT)
    print("OK:", ee.String("earth engine ready").getInfo())

    print()
    print("=== 2) ทดสอบดึง CHIRPS-Prelim ดิบ (10 วันล่าสุด) ===")
    print(f"    collection_id = {chirps_feature.CHIRPS_PRELIM_COLLECTION_ID}")
    end_date = date.today() + timedelta(days=1)
    start_date = date.today() - timedelta(days=10)
    try:
        daily = chirps_feature._fetch_chirps_daily_from_gee(
            start_date=start_date,
            end_date=end_date,
            collection_id=chirps_feature.CHIRPS_PRELIM_COLLECTION_ID,
            gee_project=GEE_PROJECT,
        )
        print(f"    ดึงได้ {len(daily)} แถว (วัน) ตั้งแต่ {start_date} ถึง {end_date}")
        print(daily.to_string(index=False))
        if daily.empty:
            print(
                "    [WARNING] ดึงได้แต่ไม่มีข้อมูลเลย (0 แถว) — เป็นไปได้ว่า asset ID ของ "
                "CHIRPS-Prelim (community catalog) เปลี่ยนไปแล้ว หรือช่วงวันที่ยังไม่มีข้อมูล — "
                "ลองเช็ค https://gee-community-catalog.org/projects/chirps_prelim/ ว่า asset ID "
                f"'{chirps_feature.CHIRPS_PRELIM_COLLECTION_ID}' ยังถูกต้องอยู่ไหม"
            )
    except Exception as exc:
        print(f"    [FAILED] ดึง CHIRPS-Prelim ไม่สำเร็จ: {type(exc).__name__} - {exc}")
        print(
            "    ตรวจสอบว่า asset ID ยังใช้ได้อยู่หรือไม่ (community catalog อาจย้าย/เปลี่ยน id) "
            "ที่ https://gee-community-catalog.org/projects/chirps_prelim/"
        )
        return 1

    print()
    print("=== 3) ทดสอบ get_chirps_feature() แบบเต็ม (zone_A, ใช้ GEE จริง) ===")
    result = chirps_feature.get_chirps_feature(zone="zone_A")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print()
    print("=== 4) ทดสอบ get_chirps_feature() แบบเต็ม (zone_B, ใช้ GEE จริง) ===")
    result_b = chirps_feature.get_chirps_feature(zone="zone_B")
    print(json.dumps(result_b, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
