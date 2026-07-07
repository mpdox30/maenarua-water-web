"""
test_mei_live.py
====================
สคริปต์ทดสอบแบบ manual (ไม่ใช่ส่วนหนึ่งของ pipeline) สำหรับดึงข้อมูล MEI จริงจาก NOAA PSL
1 ครั้ง — ยังไม่เคยรันทดสอบแบบนี้มาก่อนเลย (การทดสอบก่อนหน้าทั้งหมดของ mei_feature.py เป็นแบบ
fixture/synthetic offline เท่านั้น เพราะ sandbox ของ Claude ยิง network ไปหา psl.noaa.gov ไม่ได้
— ยืนยันแล้วด้วยทั้ง curl และ web fetch คืนค่า HTTP:000/binary data)

วิธีรัน (จากโฟลเดอร์ 01_data/scripts and code/pipeline/):
    ..\..\..\.venv\Scripts\python.exe test_mei_live.py
"""
import json
import sys
from datetime import date

import requests

import mei_feature


def main() -> int:
    print(f"=== 1) ทดสอบดึงไฟล์ดิบจาก {mei_feature.MEI_DATA_URL} ตรงๆ ===")
    resp = requests.get(mei_feature.MEI_DATA_URL, timeout=mei_feature.MEI_REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    print(f"    HTTP {resp.status_code}, ขนาด {len(resp.text)} ตัวอักษร")
    lines = resp.text.strip().split("\n")
    print(f"    บรรทัดแรก (header ปีเริ่ม-จบ): {lines[0]!r}")
    print(f"    5 บรรทัดสุดท้าย (ควรมีปีล่าสุด + ข้อความ metadata ท้ายไฟล์):")
    for line in lines[-5:]:
        print(f"      {line}")

    print()
    print("=== 2) ทดสอบ get_mei_feature() แบบเต็ม (ใช้ requests.get จริง, as_of=วันนี้) ===")
    today = date.today()
    result = mei_feature.get_mei_feature(as_of_date=today)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print()
    print("=== 3) สรุปความล่าช้าของข้อมูล ===")
    if result["fetch_error"]:
        print(f"    [FAILED] ดึงข้อมูลไม่สำเร็จ: {result['fetch_error']}")
        return 1

    latest = result["latest_available_period"]
    print(f"    วันนี้ (as_of):        {result['as_of_date']}")
    print(f"    ข้อมูลจริงล่าสุดที่มี:  {latest['year']}-{latest['month']:02d}")
    print(f"    อายุข้อมูล:            {result['data_age_days']} วัน")
    print(f"    เกณฑ์ stale:           > {result['stale_threshold_days']} วัน")
    print(f"    is_stale:              {result['is_stale']}")
    print(f"    stale_fallback_used:   {result['stale_fallback_used']} (ค่า MEI ของสัปดาห์นี้ต้องพึ่ง forward-fill หรือไม่)")
    print(f"    MEI={result['mei_current']}, MEI_lag4={result['mei_lag4']}, MEI_lag8={result['mei_lag8']}")

    if result["is_stale"]:
        print()
        print(
            f"    => ยืนยัน: ข้อมูล MEI ล่าสุดที่ NOAA ปล่อยจริงล่าช้ากว่าที่หน้าเว็บประกาศไว้เอง "
            f"('by the 10th of each month') อยู่ {result['data_age_days']} วัน (~{result['data_age_days']/30:.1f} เดือน)"
        )
    else:
        print()
        print("    => ข้อมูลยังไม่เก่าเกินเกณฑ์ที่ตั้งไว้ (60 วัน) รอบนี้ปกติดี")

    print()
    print("=== 4) mei_reporting_lag_risk + cross-check กับ ONI (Nino 3.4) จาก NOAA CPC ===")
    print(f"    mei_reporting_lag_risk: {result['mei_reporting_lag_risk']}")
    if result["mei_reporting_lag_risk"]:
        print(f"    หมายเหตุ: {result['mei_reporting_lag_risk_note']}")
    if result["nino34_oni_fetch_error"]:
        print(f"    [WARN] ดึง ONI cross-check ไม่สำเร็จ: {result['nino34_oni_fetch_error']} (ไม่กระทบ MEI feature หลัก)")
    else:
        oni = result["nino34_oni_latest"]
        print(
            f"    ONI ล่าสุดจาก NOAA CPC: {oni['season']} {oni['year']} = {oni['anom']} "
            f"(เทียบกับ MEI={result['mei_current']})"
        )
    print(f"    ตรวจสอบเพิ่มเติมด้วยตาเองได้ที่: {result['enso_advisory_url']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
