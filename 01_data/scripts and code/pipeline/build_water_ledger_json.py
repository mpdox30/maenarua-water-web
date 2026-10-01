# -*- coding: utf-8 -*-
"""
สร้าง assets/data/water_ledger.json จากไฟล์บัญชีน้ำรายเดือน (01_data/Reservoirs/inflow/<year>/<year>_<Month>_MNR.xlsx,
ชีต "บัญชีน้ำ") สำหรับหน้า water-balance.html (ตารางบัญชีน้ำรายวัน พร้อมตัวกรองเลือกเดือน)

โครงสร้างชีตคงที่ทุกไฟล์ (เช็คแล้วทั้ง 2025 July-December และ 2026 January-October):
  แถว 5 = หัวตาราง, แถว 6 เป็นต้นไป = ข้อมูลรายวัน (คอลัมน์ A = วันที่ 1-31)
  A=Date(day) B=Water Level(MSL) C=Water Volume(M3) D=Inflow(M3) E=O(discharge outlet,M3)
  F=Spill(M3) G=R(cumulative rainfall 24h, mm) H=Runoff from rainfall(M3) I=Evaporation(M3)
  J=Infiltration(M3) K=DeltaS(M3)

ปี/เดือนเอาจาก "ชื่อไฟล์" ตรงๆ (ไม่ใช้ label เดือน/ปีในแถว 3 ของชีต เพราะเจอไฟล์ที่ label ไม่ตรงกับชื่อไฟล์จริง
เช่น 2026_September_MNR.xlsx แต่แถว 3 เขียนว่า "เดือน สิงหาคม" -- เป็น label เก่าที่ไม่ได้อัปเดตตอน copy
template ไม่ใช่ความผิดพลาดของข้อมูลตัวเลข)

ข้ามแถวที่ยังไม่มีข้อมูลจริง (Water Level เป็น None -- วันที่ยังไม่ถึง/pipeline ยังไม่เขียน)

2026-10-01 สร้างครั้งแรก -- รันแบบ manual เท่านั้น (python build_water_ledger_json.py) ไม่ได้ผูกกับ
data_pipeline.py อัตโนมัติทุก ~15 นาทีเหมือนไฟล์ latest.json อื่นๆ -- ต้องรันซ้ำเองหลังกรอกบัญชีน้ำเดือนใหม่
เพิ่ม ถ้าจะทำให้อัตโนมัติ แนะนำเรียกจากท้าย reservoir_daily_orchestration.py หลังเขียนบัญชีน้ำประจำวันเสร็จ

2026-10-01 แก้ -- เปลี่ยนแหล่งข้อมูลจากไฟล์ทางการ production (01_data/Reservoirs/inflow/) มาเป็นไฟล์
"ฉบับสูตรสปิลเวย์แก้ไข" ที่ D:\WMB_Phayao\01_raw_data\Reservoirs\บัญชีน้ำ\ แทน (เขียนโดย
D:\WMB_Phayao\01_raw_data\Reservoirs\บัญชีน้ำ\recompute_corrected_ledger.py -- ดู docstring ของไฟล์นั้น
สำหรับรายละเอียดสูตร/การ sanity-check เต็มๆ) ตามที่ผู้ใช้ขอ -- สูตรนี้ใช้เฉพาะหน้า water-balance.html
เท่านั้น ไม่กระทบไฟล์ทางการ/โมเดล ML/ส่วนอื่นใดใน production เลย คอลัมน์โครงสร้างเหมือนไฟล์ทางการทุกจุด
บวกคอลัมน์ L (หมายเหตุ) บอกว่าวันนั้นคำนวณด้วยสูตรใหม่จริง หรือ fallback ใช้ค่าเดิม (เช่น telemetry
รายชั่วโมงยังไม่ครบ) -- เก็บ note นี้ไว้ใน JSON ด้วยให้หน้าเว็บแสดงความโปร่งใส
"""
import json
from pathlib import Path
import openpyxl

# 2026-10-01 แก้ -- hardcode absolute path ข้าม drive (D:\WMB_Phayao คนละ drive กับ repo นี้
# D:\maenaruea-water-web ใช้ path สัมพัทธ์ข้าม drive ไม่ได้)
ROOT = Path(__file__).resolve().parents[3]
INFLOW_DIR = Path(r"D:\WMB_Phayao\01_raw_data\Reservoirs\บัญชีน้ำ")
OUT_PATH = ROOT / "03_website" / "assets" / "data" / "water_ledger.json"

THAI_MONTH = {
    "January": "มกราคม", "February": "กุมภาพันธ์", "March": "มีนาคม", "April": "เมษายน",
    "May": "พฤษภาคม", "June": "มิถุนายน", "July": "กรกฎาคม", "August": "สิงหาคม",
    "September": "กันยายน", "October": "ตุลาคม", "November": "พฤศจิกายน", "December": "ธันวาคม",
}
MONTH_NUM = {name: i + 1 for i, name in enumerate(THAI_MONTH.keys())}

COLS = ["day", "water_level_m", "water_volume_m3", "inflow_m3", "outlet_release_m3",
        "spill_m3", "rain_24h_mm", "runoff_m3", "evap_m3", "infiltration_m3", "delta_s_m3", "note"]


def extract_month_file(path: Path):
    stem = path.stem  # e.g. "2026_September_MNR"
    parts = stem.split("_")
    year = int(parts[0])
    month_name_en = parts[1]
    month_num = MONTH_NUM.get(month_name_en)
    if month_num is None:
        print(f"  skip (unrecognized month in filename): {path.name}")
        return []

    wb = openpyxl.load_workbook(path, data_only=True)
    if "บัญชีน้ำ" not in wb.sheetnames:
        print(f"  skip (no บัญชีน้ำ sheet): {path.name}")
        return []
    ws = wb["บัญชีน้ำ"]

    rows = []
    for r in range(6, 38):
        vals = [ws.cell(row=r, column=c).value for c in range(1, 13)]
        day = vals[0]
        if day is None or not isinstance(day, (int, float)):
            continue
        water_level = vals[1]
        if water_level is None:
            continue  # วันที่ยังไม่มีข้อมูลจริง (ยังไม่ถึง/pipeline ยังไม่เขียน) -- ใช้ Water Level
            # เป็นตัวเช็คหลัก เจอบางแถว (2025-06) ที่ DeltaS=0 ค้างจาก template แต่ค่าอื่นว่างหมด
        row = dict(zip(COLS, vals))
        row["year"] = year
        row["month"] = month_num
        row["date"] = f"{year:04d}-{month_num:02d}-{int(day):02d}"
        rows.append(row)
    return rows


def main():
    all_rows = []
    # 2026-10-01 แก้ -- ไฟล์ฉบับแก้ไขอยู่แบบ flat ใต้โฟลเดอร์เดียว (ไม่มี subfolder ปีเหมือนไฟล์ทางการ
    # production เดิมที่เป็น inflow/<year>/<year>_<Month>_MNR.xlsx)
    files = sorted(INFLOW_DIR.glob("*_MNR.xlsx"))
    for f in files:
        rows = extract_month_file(f)
        # 2026-10-01 แก้ -- f.relative_to(ROOT) พังตั้งแต่ INFLOW_DIR ย้ายไปอยู่คนละ drive (D:\WMB_Phayao)
        # กับ ROOT (D:\maenaruea-water-web) ใช้ f.name เฉยๆ พอสำหรับ log
        print(f"{f.name}: {len(rows)} day-rows")
        all_rows.extend(rows)

    all_rows.sort(key=lambda r: r["date"])

    months_present = sorted({f"{r['year']:04d}-{r['month']:02d}" for r in all_rows})

    payload = {
        "generated_at": None,
        "unit_note": "Water Level = MSL (m); Volume/Inflow/O/Spill/Runoff/Evap/Infiltration/DeltaS = m3 (ยกเว้น rain_24h_mm = mm)",
        "source_note": (
            "ดึงจาก D:\\WMB_Phayao\\01_raw_data\\Reservoirs\\บัญชีน้ำ\\<year>_<Month>_MNR.xlsx "
            "('ฉบับสูตรสปิลเวย์แก้ไข' -- เขียนโดย recompute_corrected_ledger.py, ไม่ใช่ไฟล์ทางการ "
            "production) ด้วย build_water_ledger_json.py"
        ),
        "formula_note": (
            "Spill คำนวณด้วย critical-flow + Manning friction model (n=0.017) แทนสูตร Q=1.82*L*H^1.5 "
            "เดิม -- ใช้เฉพาะหน้า water-balance.html เท่านั้น ไม่กระทบไฟล์ทางการ/โมเดล ML ใน production "
            "ดูคอลัมน์ note ต่อแถวว่าวันนั้นคำนวณด้วยสูตรใหม่จริง หรือ fallback ใช้ค่าเดิม"
        ),
        "months_available": months_present,
        "rows": all_rows,
    }

    from datetime import datetime, timezone
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    print(f"\nSaved {len(all_rows)} rows across {len(months_present)} months -> {OUT_PATH}")


if __name__ == "__main__":
    main()
