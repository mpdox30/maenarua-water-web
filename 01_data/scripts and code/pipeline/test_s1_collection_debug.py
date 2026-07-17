"""
test_s1_collection_debug.py
=============================
สคริปต์ทดสอบแบบ manual (ไม่ใช่ส่วนหนึ่งของ pipeline เอง) สำหรับ debug ทีละชั้นว่า
COPERNICUS/S1_GRD มีภาพจริงอะไรบ้างสำหรับ AOI/ช่วงเวลาที่ trigger_crop_classification() ใช้
ก่อนจะเชื่อ/แก้ filter ที่ hardcode ไว้ใน _build_s1_weekly_vvvh_stack() (instrumentMode='IW',
orbitProperties_pass='DESCENDING', ต้องมีทั้ง VV+VH)

ทำไมต้องเช็คก่อนแก้: gee_step1_2_sentinel1_sar_weekly.js ที่ sar_classification.py port มา มี
คอมเมนต์หัวไฟล์ยอมรับเองว่า DESCENDING-orbit filter เป็นจุดที่ผู้เขียนสคริปต์เดิม "ADDED" เอง ไม่ใช่
ยืนยันจาก source ต้นฉบับ 100% (ดู docstring หัวไฟล์ sar_classification.py) — ถ้าพื้นที่ AOI จริงมีแต่
ภาพ ASCENDING (หรือ instrumentMode ไม่ใช่ 'IW') filter ปัจจุบันจะกรองออกจนเหลือ 0 ภาพ ทำให้
ee.ImageCollection ว่างเปล่า .mean() ของ collection ว่างจะได้ image ที่ทุก pixel เป็น masked/no-data
ซึ่ง sampleRegions() จะไม่ error แต่ได้แถวว่างหรือค่า NaN ทั้งหมด (ผลลัพธ์ผิดแบบเงียบๆ ไม่ crash) —
ต้อง debug ทีละชั้นแบบนี้ก่อนไว้ใจตัวเลขที่ trigger_crop_classification() คืนมา

ตามที่ตกลงกันไว้: สคริปต์นี้ทำหน้าที่ diagnostic เท่านั้น ไม่แก้ sar_classification.py ให้ — ถ้าเจอ
filter ไม่ตรงกับข้อมูลจริง จะ print คำแนะนำว่าควรแก้อย่างไร แต่รอผลจริงจากเครื่องที่มี credential ก่อน
ค่อยไปแก้โค้ดจริงในเทิร์นถัดไป

วิธีรัน (จากโฟลเดอร์ 01_data/scripts and code/pipeline/):
    ..\\..\\..\\.venv\\Scripts\\python.exe test_s1_collection_debug.py [year]

ถ้าไม่ระบุ year จะใช้ปีปัจจุบัน (datetime.now().year) — ถ้าต้องการเช็คปีอื่น (เช่นปีที่มี crop area
ปี 2020 ไว้เทียบ) ให้ระบุปีเป็น argument เช่น: test_s1_collection_debug.py 2024

หมายเหตุ: รันไฟล์นี้จากเครื่องของคุณเองเท่านั้น — รันจาก sandbox ของ Claude ไม่ได้ เพราะ sandbox
ไม่มี Earth Engine credentials ของคุณ (เหมือนข้อจำกัดเดียวกับ test_sar_classification_live.py)

สคริปต์นี้ห้าม raise exception ออกไปเด็ดขาด — ทุก step ห่อด้วย try/except ของตัวเอง ถ้า error จะ
print รายละเอียด error เต็ม (รวม traceback) แล้วไปต่อ step ถัดไปแบบ graceful เท่าที่ทำได้
"""
import sys
import traceback
from datetime import datetime

import sar_classification as sc


def _print_section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main() -> int:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().year
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    print(f"ปีที่ทดสอบ: {year}  (ช่วงวันที่ {start} ถึง {end} — ตรงกับที่ "
          f"_build_s1_weekly_vvvh_stack()/trigger_crop_classification() ใช้จริงเมื่อ sar_trigger['year']={year})")

    # -------------------------------------------------------------------
    # ขั้น 0: ee.Initialize() + โหลด AOI เดียวกับที่ trigger_crop_classification() ใช้ (zone_A geom_4326)
    # -------------------------------------------------------------------
    _print_section("0) ee.Initialize() + โหลด AOI (zone_A, ผ่าน sc.load_zone_boundaries()/sc._to_ee_geometry() จริง)")
    try:
        import ee

        ee.Initialize(project=sc.DEFAULT_GEE_PROJECT)
        print(f"OK: ee.Initialize(project='{sc.DEFAULT_GEE_PROJECT}') สำเร็จ")
    except Exception as exc:
        print(f"[FAILED] ee.Initialize(): {type(exc).__name__}: {exc}")
        print("--- traceback เต็ม ---")
        print(traceback.format_exc())
        print(
            "\n[หมายเหตุ] ee.Initialize() ล้มเหลว — ขั้นถัดไปทั้งหมดต้องพึ่ง ee ที่ initialize แล้ว "
            "จะหยุดสคริปต์ตรงนี้ (ไม่มีอะไรให้ debug ต่อได้ถ้ายังต่อ GEE ไม่ได้เลย)"
        )
        return 1

    try:
        zones = sc.load_zone_boundaries()
        aoi = sc._to_ee_geometry(zones["zone_A"]["geom_4326"])
        print("OK: โหลด zone_A boundary + แปลงเป็น ee.Geometry สำเร็จ (ใช้ฟังก์ชันจริงจาก sar_classification.py)")
    except Exception as exc:
        print(f"[FAILED] โหลด/แปลง AOI: {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 1

    # -------------------------------------------------------------------
    # ขั้น 1: query แบบไม่ filter orbit/instrumentMode เลย — filterBounds + filterDate เท่านั้น
    # -------------------------------------------------------------------
    _print_section("1) ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(aoi).filterDate(...) — ไม่ filter orbit/mode เลย")
    try:
        raw_coll = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(aoi)
            .filterDate(start, end)
        )
        n_total = raw_coll.size().getInfo()
        print(f"จำนวนภาพทั้งหมดในแคตตาล็อกสำหรับ AOI/ช่วงเวลานี้ (ไม่ filter orbit/mode) = {n_total}")
    except Exception as exc:
        print(f"[FAILED] query ไม่สำเร็จ: {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 1

    if n_total == 0:
        print(
            "\n[สรุป] ไม่มีภาพ S1_GRD เลยสำหรับ AOI/ปีนี้ในแคตตาล็อก — ปัญหาไม่ได้อยู่ที่ filter "
            "orbit/instrumentMode แต่อยู่ที่ AOI หรือปีที่เลือกไม่มีภาพครอบคลุมเลย (ลองรันใหม่ด้วยปีอื่น "
            "เช่น test_s1_collection_debug.py 2023 หรือตรวจสอบว่า AOI (zone_A boundary) พิกัดถูกต้อง)"
        )
        return 1

    # -------------------------------------------------------------------
    # ขั้น 2: ค่า orbitProperties_pass ที่มีจริง (distinct)
    # -------------------------------------------------------------------
    _print_section("2) ค่า orbitProperties_pass ที่มีจริงในแคตตาล็อก (distinct)")
    orbit_values = None
    try:
        orbit_values = raw_coll.aggregate_array("orbitProperties_pass").distinct().getInfo()
        print(f"orbitProperties_pass ที่พบจริง: {orbit_values}")
    except Exception as exc:
        print(f"[FAILED] อ่าน orbitProperties_pass ไม่สำเร็จ: {type(exc).__name__}: {exc}")
        print(traceback.format_exc())

    # -------------------------------------------------------------------
    # ขั้น 3: ค่า instrumentMode ที่มีจริง (distinct)
    # -------------------------------------------------------------------
    _print_section("3) ค่า instrumentMode ที่มีจริงในแคตตาล็อก (distinct)")
    mode_values = None
    try:
        mode_values = raw_coll.aggregate_array("instrumentMode").distinct().getInfo()
        print(f"instrumentMode ที่พบจริง: {mode_values}")
    except Exception as exc:
        print(f"[FAILED] อ่าน instrumentMode ไม่สำเร็จ: {type(exc).__name__}: {exc}")
        print(traceback.format_exc())

    # -------------------------------------------------------------------
    # ขั้น 4: รายชื่อ band ของภาพแรกที่เจอ (+ property อื่นที่เป็นประโยชน์ประกอบการ debug)
    # -------------------------------------------------------------------
    _print_section("4) รายชื่อ band ของภาพแรกที่เจอในคอลเลกชัน (.bandNames().getInfo())")
    band_names = None
    try:
        first_img = raw_coll.first()
        band_names = first_img.bandNames().getInfo()
        print(f"bandNames() ของภาพแรก: {band_names}")

        print("\nproperty อื่นของภาพแรก (ไว้เทียบ/อ้างอิงเพิ่ม):")
        for prop in (
            "orbitProperties_pass", "instrumentMode",
            "transmitterReceiverPolarisation", "system:time_start",
        ):
            try:
                val = first_img.get(prop).getInfo()
                print(f"    {prop:<32} = {val}")
            except Exception:
                print(f"    {prop:<32} = (ไม่มี property นี้ หรืออ่านไม่ได้)")
    except Exception as exc:
        print(f"[FAILED] อ่าน band names ไม่สำเร็จ: {type(exc).__name__}: {exc}")
        print(traceback.format_exc())

    # -------------------------------------------------------------------
    # ขั้น 5: เทียบกับ filter ปัจจุบันใน _build_s1_weekly_vvvh_stack() (sar_classification.py)
    # -------------------------------------------------------------------
    _print_section("5) เทียบกับ filter ปัจจุบันใน sar_classification._build_s1_weekly_vvvh_stack()")
    print("filter ที่ hardcode ไว้ในโค้ดตอนนี้ (sar_classification.py):")
    print("    .filter(ee.Filter.eq('instrumentMode', 'IW'))")
    print("    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))")
    print("    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))")
    print("    .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))")

    mismatches = []
    if mode_values is not None and "IW" not in mode_values:
        mismatches.append(
            f"instrumentMode: โค้ด filter ต้องการ 'IW' แต่ข้อมูลจริงมีแค่ {mode_values} "
            f"(ไม่มี 'IW' เลย) — ต้องแก้เป็นค่าที่พบจริง"
        )
    if orbit_values is not None and "DESCENDING" not in orbit_values:
        mismatches.append(
            f"orbitProperties_pass: โค้ด filter ต้องการ 'DESCENDING' แต่ข้อมูลจริงมีแค่ {orbit_values} "
            f"(ไม่มี 'DESCENDING' เลย) — ต้องแก้เป็นค่าที่พบจริง หรือเอา filter นี้ออกถ้าไม่จำเป็นต้องล็อก orbit"
        )
    if band_names is not None:
        missing_bands = [b for b in ("VV", "VH") if b not in band_names]
        if missing_bands:
            mismatches.append(
                f"band names: โค้ดคาดว่าต้องมี ['VV', 'VH'] แต่ภาพจริงไม่มี band {missing_bands} "
                f"(bandNames จริง = {band_names})"
            )

    print()
    if mismatches:
        print("[พบจุดไม่ตรงกัน] filter ปัจจุบันน่าจะกรองข้อมูลออกจนหมด/ผิดพลาด:")
        for m in mismatches:
            print(f"    - {m}")
        print(
            "\n[ยังไม่แก้ sar_classification.py ตามที่ตกลงไว้] รอผล diagnostic นี้จากเครื่องจริงก่อน "
            "ค่อยไปแก้ filter ในเทิร์นถัดไปให้ตรงกับค่าที่พบจริงข้างต้น"
        )
    else:
        print(
            "[ตรงกัน] filter ปัจจุบัน (IW + DESCENDING + ต้องมี VV/VH) สอดคล้องกับข้อมูลจริงที่พบทั้งหมด "
            "— ไม่จำเป็นต้องแก้ sar_classification.py"
        )

    # -------------------------------------------------------------------
    # ขั้นเสริม 6: จำลอง filter ปัจจุบันแบบเป๊ะๆ แล้วนับว่าเหลือกี่ภาพจริง (ยืนยันผลกระทบเป็นตัวเลข)
    # -------------------------------------------------------------------
    _print_section("6) (เสริม) จำลอง filter ปัจจุบันแบบเป๊ะๆ แล้วนับภาพที่เหลือ เทียบกับก่อน filter")
    try:
        filtered = (
            raw_coll
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        )
        n_filtered = filtered.size().getInfo()
        print(f"ก่อน filter: {n_total} ภาพ   หลัง filter ปัจจุบันทั้งหมด: {n_filtered} ภาพ")
        if n_filtered == 0 and n_total > 0:
            print(
                "[ยืนยันปัญหา] filter ปัจจุบันกรองภาพออกจนเหลือ 0 ภาพ ทั้งที่มีภาพอยู่จริง "
                f"{n_total} ภาพก่อน filter — ตรงกับสมมติฐานที่สงสัย ต้องแก้ filter แน่นอน"
            )
        elif n_filtered < n_total:
            pct = n_filtered / n_total * 100
            print(f"filter ปัจจุบันเหลือภาพ {pct:.1f}% ของทั้งหมด (ไม่ใช่ 0 แต่ก็กรองออกไปพอสมควร)")
    except Exception as exc:
        print(f"[FAILED] ทดสอบจำลอง filter ไม่สำเร็จ: {type(exc).__name__}: {exc}")
        print(traceback.format_exc())

    # -------------------------------------------------------------------
    # สรุปรวม
    # -------------------------------------------------------------------
    _print_section("สรุปรวม")
    print(f"ภาพทั้งหมดก่อน filter (AOI+date เท่านั้น) : {n_total}")
    print(f"orbitProperties_pass ที่พบจริง            : {orbit_values}")
    print(f"instrumentMode ที่พบจริง                  : {mode_values}")
    print(f"band names ของภาพแรก                      : {band_names}")
    print(f"filter ปัจจุบันตรงกับข้อมูลจริงไหม           : {'ไม่ตรง — ต้องแก้' if mismatches else 'ตรงกัน'}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = main()
    except Exception as exc:  # กันสุดท้ายจริงๆ — ไม่ควรถึงจุดนี้เลยถ้าทุก step ห่อ try/except ไว้ครบ
        print("\n" + "=" * 78)
        print("[UNEXPECTED] เกิด exception หลุดออกมาถึงระดับบนสุดของสคริปต์ (ไม่ควรเกิดขึ้น)")
        print("=" * 78)
        print(f"{type(exc).__name__}: {exc}")
        print("--- traceback เต็ม ---")
        print(traceback.format_exc())
        exit_code = 1
    sys.exit(exit_code)
