"""
test_s1_weekly_windows_debug.py
=================================
สคริปต์ทดสอบแบบ manual (ไม่ใช่ส่วนหนึ่งของ pipeline เอง) — ทดสอบ filterDate() ช่วงแคบจริงๆ ที่
_build_s1_weekly_vvvh_stack() ใช้ (sar_classification.py) ไม่ใช่ช่วง 30 วันที่
test_s1_collection_debug.py ทดสอบไปก่อนหน้า

ข้อเท็จจริงที่ยืนยันแล้วจากการอ่านโค้ดจริง (sar_classification.py บรรทัด 284-302 — ไม่ใช่การเดา):
  1. s1 (ImageCollection) filter ระดับบนสุดใช้ .filterDate(f"{year}-01-01", f"{year}-12-31") คือ
     "ทั้งปี" ไม่ใช่ 30 วัน และไม่ได้ผูกกับ latest_s1_image_date=2026-07-05 จาก check_new_sar_image()
     เลย (ตัวเลข 30 วันที่ test_s1_collection_debug.py ใช้ทดสอบไปคือช่วงที่ check_new_sar_image()
     ใช้เช็คว่า "มีภาพใหม่ไหม" เท่านั้น เป็นคนละฟังก์ชัน คนละ filterDate กับตัวนี้)
  2. ข้างในลูป for w in range(36): มีการเรียก s1.filterDate(start, end) ซ้ำอีกชั้น โดย
     start = ee.Date(f"{year}-01-01").advance(w*7, "day"), end = start.advance(7, "day")
     คือหน้าต่าง 7 วัน คงที่ 36 ช่วง นับจากวันที่ 1 ม.ค. ของปีนั้น (ปฏิทิน ไม่ใช่ rolling window
     รอบวันที่ล่าสุด) — นี่คือ "ช่วงแคบ" ตัวจริงที่ต้องทดสอบ
  3. reducer ที่ใช้คือ .mean() เท่านั้น (ไม่มี .median()/.mosaic() ในฟังก์ชันนี้เลย — .median() ใช้ใน
     _build_s2_dry_season_composite() ซึ่งเป็นคนละฟังก์ชัน)
  4. .select("VV")/.select("VH") ถูกเรียกทันทีหลัง .mean() ของแต่ละสัปดาห์ (บรรทัด 301-302) — นี่คือ
     จุดเสี่ยงตัวจริง: ถ้าสัปดาห์ไหนมี 0 ภาพหลัง filter ก่อน .mean() ผลลัพธ์คือ Image ที่มี 0 band
     แล้ว .select("VV") จะ error "Image.select: Pattern 'VV' did not match any bands." ทันทีที่ถูก
     evaluate (ตอน .getInfo()/sampleRegions().getInfo() ที่ปลายทาง ไม่ใช่ตอนสร้าง object) — เป็นคนละ
     สาเหตุกับ orbit mismatch (ถ้า orbit ผิดทั้งปี collection ทั้งปีจะว่างตั้งแต่ต้น แต่ถ้า orbit ถูก
     บางสัปดาห์แต่บางสัปดาห์ไม่มีภาพเข้ามาเลยเพราะ revisit cycle ของ S1 (~6-12 วัน) ไม่ตรงกับ
     ขอบเขตสัปดาห์ปฏิทินพอดี ก็จะพังแบบสัปดาห์ต่อสัปดาห์แทน)

สคริปต์นี้:
  1. จำลอง filter chain เดิม (IW + DESCENDING + VV + VH) เหมือน _build_s1_weekly_vvvh_stack() เป๊ะ
  2. ใช้ filterDate() ของแต่ละสัปดาห์ทั้ง 36 สัปดาห์ (ไม่ใช่ 30 วันเดียว) นับภาพที่เหลือต่อสัปดาห์
  3. รายงานว่าสัปดาห์ไหนมี 0 ภาพ (ตัวการที่ทำให้ .select('VV') พังปลายทาง)
  4. ทดสอบจริง (ปลอดภัย ไม่ raise) ว่า .mean().select('VV') พังตามที่คาดไว้ไหมสำหรับสัปดาห์ที่ 0 ภาพ
     เทียบกับสัปดาห์ที่มีภาพ (ควรผ่านได้ปกติ)

ยังไม่แก้ sar_classification.py ตามที่ตกลงไว้ — รอผลจากเครื่องจริงก่อน

วิธีรัน (จากโฟลเดอร์ 01_data/scripts and code/pipeline/):
    ..\\..\\..\\.venv\\Scripts\\python.exe test_s1_weekly_windows_debug.py [year]

ถ้าไม่ระบุ year จะใช้ปีปัจจุบัน (datetime.now().year)

หมายเหตุ: รันไฟล์นี้จากเครื่องของคุณเองเท่านั้น — รันจาก sandbox ของ Claude ไม่ได้ (ไม่มี Earth
Engine credentials เหมือนสคริปต์ทดสอบตัวอื่นในโฟลเดอร์นี้)

สคริปต์นี้ห้าม raise exception ออกไปเด็ดขาด — ทุก step ห่อด้วย try/except แล้ว print รายละเอียด
error เต็มก่อนไปต่อแบบ graceful
"""
import sys
import traceback
from datetime import datetime

import sar_classification as sc

N_DRY_WEEKS = sc.N_DRY_WEEKS   # 16
N_WET_WEEKS = sc.N_WET_WEEKS   # 20
N_TOTAL_WEEKS = N_DRY_WEEKS + N_WET_WEEKS  # 36 — ตรงกับ range(36) ใน _build_s1_weekly_vvvh_stack()


def _print_section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def _apply_same_filter_chain(coll):
    """filter chain เดียวกับที่ _build_s1_weekly_vvvh_stack() ใช้เป๊ะ (IW+DESCENDING+VV+VH)"""
    import ee

    return (
        coll
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
    )


def main() -> int:
    import ee

    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().year
    print(f"ปีที่ทดสอบ: {year}")
    print(
        f"ยืนยันจากโค้ดจริง (sar_classification.py): filterDate ระดับบนสุด = "
        f"{year}-01-01 ถึง {year}-12-31 (ทั้งปี ไม่ใช่ 30 วัน) แล้วค่อยหั่นเป็น {N_TOTAL_WEEKS} "
        f"หน้าต่างสัปดาห์ละ 7 วัน นับจาก 1 ม.ค. (ปฏิทิน ไม่ใช่ rolling รอบ latest_s1_image_date)"
    )

    # -------------------------------------------------------------------
    # ขั้น 0: ee.Initialize() + โหลด AOI เดียวกับที่ _build_s1_weekly_vvvh_stack() ใช้ (zone_A)
    # -------------------------------------------------------------------
    _print_section("0) ee.Initialize() + โหลด AOI (zone_A)")
    try:
        ee.Initialize(project=sc.DEFAULT_GEE_PROJECT)
        print(f"OK: ee.Initialize(project='{sc.DEFAULT_GEE_PROJECT}') สำเร็จ")
    except Exception as exc:
        print(f"[FAILED] ee.Initialize(): {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 1

    try:
        zones = sc.load_zone_boundaries()
        aoi = sc._to_ee_geometry(zones["zone_A"]["geom_4326"])
        print("OK: โหลด zone_A boundary + แปลงเป็น ee.Geometry สำเร็จ")
    except Exception as exc:
        print(f"[FAILED] โหลด/แปลง AOI: {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 1

    # -------------------------------------------------------------------
    # ขั้น 1: สร้าง s1 ทั้งปีเหมือนโค้ดจริง (บรรทัด 284-292) แล้วนับภาพทั้งปีไว้เทียบ
    # -------------------------------------------------------------------
    _print_section("1) s1 ทั้งปี (filter IW+DESCENDING+VV+VH + filterDate ทั้งปี) — เหมือนบรรทัด 284-292 เป๊ะ")
    try:
        s1_year = _apply_same_filter_chain(
            ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(aoi)
        ).filterDate(f"{year}-01-01", f"{year}-12-31").select(["VV", "VH"])
        n_year = s1_year.size().getInfo()
        print(f"จำนวนภาพทั้งปีหลัง filter (IW+DESCENDING+VV+VH) = {n_year}")
    except Exception as exc:
        print(f"[FAILED] {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 1

    if n_year == 0:
        print(
            "\n[สรุป] ทั้งปีมี 0 ภาพหลัง filter แล้ว — ปัญหาอยู่ที่ orbit/instrumentMode filter "
            "ไม่ตรงกับข้อมูลทั้งปี (ดู test_s1_collection_debug.py) ไม่ต้องดูรายสัปดาห์ต่อ เพราะทุก "
            "สัปดาห์จะว่างหมดแน่นอน — ต้องแก้ filter ก่อน"
        )
        return 1

    # -------------------------------------------------------------------
    # ขั้น 2: นับภาพทีละสัปดาห์ (36 หน้าต่าง 7 วัน) เหมือนบรรทัด 297-300 เป๊ะ
    # -------------------------------------------------------------------
    _print_section(f"2) นับภาพทีละสัปดาห์ ({N_TOTAL_WEEKS} หน้าต่าง 7 วัน นับจาก {year}-01-01) — ช่วงแคบจริงที่โค้ดใช้")
    weekly_counts = []
    for w in range(N_TOTAL_WEEKS):
        try:
            start = ee.Date(f"{year}-01-01").advance(w * 7, "day")
            end = start.advance(7, "day")
            week_coll = s1_year.filterDate(start, end)
            n_week = week_coll.size().getInfo()
            start_str = start.format("YYYY-MM-dd").getInfo()
            end_str = end.format("YYYY-MM-dd").getInfo()
            weekly_counts.append((w, start_str, end_str, n_week))
            flag = "" if n_week > 0 else "  <-- 0 ภาพ! .mean().select('VV') จะพังตรงนี้"
            print(f"  week {w:>2} [{start_str} .. {end_str}) : {n_week} ภาพ{flag}")
        except Exception as exc:
            print(f"  week {w:>2}: [FAILED] {type(exc).__name__}: {exc}")
            weekly_counts.append((w, None, None, None))

    n_empty_weeks = sum(1 for w in weekly_counts if w[3] == 0)
    n_ok_weeks = sum(1 for w in weekly_counts if w[3] and w[3] > 0)
    print(f"\nสรุป: {n_ok_weeks}/{N_TOTAL_WEEKS} สัปดาห์มีภาพอย่างน้อย 1 ภาพ, "
          f"{n_empty_weeks}/{N_TOTAL_WEEKS} สัปดาห์มี 0 ภาพ")

    # -------------------------------------------------------------------
    # ขั้น 3: ทดสอบจริงว่า .mean().select('VV') พังตามที่คาดไหม — เทียบสัปดาห์ที่มีภาพ vs ว่าง
    # -------------------------------------------------------------------
    _print_section("3) ทดสอบ .mean().select('VV') จริง — เทียบสัปดาห์ที่มีภาพ vs สัปดาห์ที่ 0 ภาพ")

    sample_ok_week = next((w for w in weekly_counts if w[3] and w[3] > 0), None)
    sample_empty_week = next((w for w in weekly_counts if w[3] == 0), None)

    def _test_week_mean_select(w_idx: int, label: str):
        try:
            start = ee.Date(f"{year}-01-01").advance(w_idx * 7, "day")
            end = start.advance(7, "day")
            img = s1_year.filterDate(start, end).mean()
            vv = img.select("VV")
            band_names = img.bandNames().getInfo()  # trigger evaluation จริง (lazy -> eager ตรงนี้)
            print(f"  {label} (week {w_idx}): [OK] .mean().bandNames() = {band_names}, .select('VV') ไม่พัง")
        except Exception as exc:
            print(f"  {label} (week {w_idx}): [FAILED ตามคาด] {type(exc).__name__}: {exc}")

    if sample_ok_week is not None:
        _test_week_mean_select(sample_ok_week[0], "สัปดาห์ที่มีภาพ")
    else:
        print("  ไม่มีสัปดาห์ไหนมีภาพเลยทั้งปี — ข้ามการทดสอบเทียบ (ทุกสัปดาห์จะพังเหมือนกันหมด)")

    if sample_empty_week is not None:
        _test_week_mean_select(sample_empty_week[0], "สัปดาห์ที่ 0 ภาพ")
    else:
        print("  ไม่มีสัปดาห์ไหน 0 ภาพเลย — ทุกสัปดาห์ควรผ่านหมด (ไม่มีปัญหาจุดนี้)")

    # -------------------------------------------------------------------
    # สรุปรวม
    # -------------------------------------------------------------------
    _print_section("สรุปรวม")
    print(f"ภาพทั้งปีหลัง filter                : {n_year}")
    print(f"สัปดาห์ที่มีภาพ (จาก {N_TOTAL_WEEKS})        : {n_ok_weeks}")
    print(f"สัปดาห์ที่ 0 ภาพ (จาก {N_TOTAL_WEEKS})       : {n_empty_weeks}")
    if n_empty_weeks > 0:
        print(
            "\n[สรุปสาเหตุที่เป็นไปได้] มีอย่างน้อย 1 สัปดาห์ที่ 0 ภาพ แม้ทั้งปีจะมีภาพรวม "
            f"{n_year} ภาพก็ตาม — แปลว่าไม่ใช่ปัญหา orbit/instrumentMode ผิดทั้งหมด แต่เป็นเพราะ "
            "รอบ revisit ของ Sentinel-1 (DESCENDING เท่านั้น ทำให้รอบถี่ลดลงเหลือ ~12 วัน) ไม่ตรงกับ "
            "ขอบเขตสัปดาห์ปฏิทิน 7 วันคงที่พอดีทุกสัปดาห์ — สัปดาห์ที่ไม่มีภาพผ่านจะทำให้ "
            ".mean().select('VV') พังตรงนั้น ต้องแก้ในเทิร์นถัดไป เช่น ขยายหน้าต่างต่อสัปดาห์ให้กว้างขึ้น "
            "(เช่น +-3 วัน) หรือ fallback ไปใช้ภาพล่าสุดก่อนหน้าถ้าสัปดาห์นั้นว่าง"
        )
    else:
        print("\nทุกสัปดาห์มีภาพครบ — filter/ช่วงเวลาปัจจุบันไม่มีปัญหาจุดนี้")

    return 1 if n_empty_weeks > 0 else 0


if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = main()
    except Exception as exc:  # กันสุดท้ายจริงๆ
        print("\n" + "=" * 78)
        print("[UNEXPECTED] เกิด exception หลุดออกมาถึงระดับบนสุดของสคริปต์ (ไม่ควรเกิดขึ้น)")
        print("=" * 78)
        print(f"{type(exc).__name__}: {exc}")
        print("--- traceback เต็ม ---")
        print(traceback.format_exc())
        exit_code = 1
    sys.exit(exit_code)
