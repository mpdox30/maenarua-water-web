"""
test_sar_classification_live.py
=================================
สคริปต์ทดสอบแบบ manual (ไม่ใช่ส่วนหนึ่งของ pipeline เอง) สำหรับรัน SAR crop classification
(sar_classification.py) กับ Google Earth Engine จริง 1 รอบ บนเครื่อง Windows ที่ตั้งค่า Earth
Engine ไว้แล้ว (project='maenaruea-water-pipeline' — ดู DEFAULT_GEE_PROJECT ใน sar_classification.py)

2026-07-11 อัปเดต docstring นี้ให้ตรงกับสถาปัตยกรรมใหม่ (export+local-classify) — ตัว logic ของ
สคริปต์ทดสอบเองไม่ต้องแก้ เพราะยังเรียก check_new_sar_image()/trigger_crop_classification() แบบ
เดิมทุกอย่าง แค่ผลลัพธ์ข้างในตอนนี้มาจาก flow ใหม่ (ดูหัวข้อ "ทดสอบทีละขั้น" ด้านล่าง)

ทดสอบทีละขั้น (ไม่ mock):
  1. ee.Initialize(project=...) สำเร็จไหม
  2. sc.check_new_sar_image() — เจอภาพ Sentinel-1 ใหม่ในช่วง 30 วันล่าสุดไหม (AOI = zone A boundary)
  3. sc.trigger_crop_classification() — สถาปัตยกรรมใหม่ (2026-07-11): สร้าง S2 dry-season
     composite + S1 weekly VV/VH stack -> unmask(SAR_MASK_SENTINEL) -> clip ตาม zone A/B ->
     ee.Image.getDownloadURL() ดาวน์โหลด GeoTIFF เต็ม zone (ไม่ใช่ sampleRegions() แบบ synchronous
     เดิมที่ชน GEE 5,000-element limit) -> classify ทุก pixel local ด้วย rasterio+numpy+RF v3b
     (เหมือน Retrain3.ipynb cell 16 เป๊ะ) — ขั้นตอนนี้ใช้เวลานาน (นาทีถึงหลายนาทีต่อ zone เพราะต้อง
     ดาวน์โหลด GeoTIFF จริง) ไม่ใช่วินาทีเหมือนตอนยังใช้ sampleRegions()
  4. สรุปพื้นที่รวมต่อ class (rice/corn/cassava/longan/etc) เป็นทั้งไร่และเฮกตาร์ แยก zone A/zone B
  5. เทียบกับพื้นที่ hardcode ปี 2020 (area_2020_ha ใน sar_classification.trigger_crop_classification —
     มาจาก feature_schema.md หัวข้อ 2 / AREA_ZONE_A, AREA_ZONE_B) พร้อม % ต่าง
  6. raster_meta ต่อ zone — pixel_area_ha (ควรได้ 0.04 ha ที่ scale=20m, คือ 20x20m/10000),
     n_pixels_valid (พิกเซลในโซนจริงที่ถูกนับพื้นที่), n_pixels_outside_zone (พิกเซลนอกขอบเขต zone
     จริงที่ถูกตัดออกจาก .clip() — ควร > 0 เสมอเพราะ bounding box การ export ใหญ่กว่า polygon จริง),
     และ path ของไฟล์ crop_map_v3b_<zone>_<year>.tif ที่เขียนไว้เป็น audit trail

หมายเหตุสำคัญที่ต้องรู้ก่อนอ่านผลลัพธ์ (คัดลอกมาจาก docstring ของ sar_classification.py):
  - min_days_between_runs ของ check_new_sar_image() ถูก override เป็น 0 และใช้ marker file แยก
    ต่างหาก (.sar_last_classified_test) ในสคริปต์นี้ เพื่อไม่ให้ gate 30 วันของรอบ production
    บล็อกการทดสอบ และไม่ไปแตะ marker file จริงที่ pipeline ใช้งาน
  - trigger_crop_classification() ใช้ ee.Image.getDownloadURL() (ไม่ใช่ ee.batch.Export.image.toDrive()
    + Task.status() polling) เพราะโปรเจกต์นี้ไม่มี Drive/GCS download infrastructure (OAuth,
    google-cloud-storage, pydrive ฯลฯ) อยู่เลย — getDownloadURL() ใช้ session credential เดิม
    (personal ee.Authenticate()) ได้ตรงๆ ไม่ต้องตั้งค่าเพิ่ม ถ้าไฟล์ใหญ่เกิน ~32MB จะ fallback
    เป็นแบ่ง tile 2x2 (แล้ว mosaic กลับด้วย rasterio.merge) อัตโนมัติ (ดู _download_ee_image_geotiff())
  - n_pixels_outside_zone ควรมีค่า > 0 เสมอ (เพราะ export เป็น bounding box สี่เหลี่ยม ไม่ใช่ทรง
    polygon จริงของ zone) — ถ้าเป็น 0 ทั้งหมด อาจแปลว่า .clip() ไม่ทำงานตามคาด ควรตรวจสอบเพิ่ม
  - ทั้ง gee_step1_1_sentinel2_dryseason.js / gee_step1_2_sentinel1_sar_weekly.js ที่ port มาเป็น
    "reconstructed" จากเอกสาร ไม่ใช่สคริปต์ต้นฉบับยืนยัน 100% — ดู docstring หัวไฟล์ sar_classification.py

วิธีรัน (จากโฟลเดอร์ 01_data/scripts and code/pipeline/):
    ..\\..\\..\\.venv\\Scripts\\python.exe test_sar_classification_live.py

หมายเหตุ: รันไฟล์นี้จากเครื่องของคุณเองเท่านั้น — รันจาก sandbox ของ Claude ไม่ได้ เพราะ sandbox
ไม่มี Earth Engine credentials ของคุณ และ endpoint ของ GEE ถูกบล็อกจาก network ของ sandbox ด้วย
(ยืนยันแล้วก่อนหน้านี้กับ chirps_feature.py / mei_feature.py ด้วย curl คืนค่า HTTP:000) นอกจากนี้
ขั้นตอน 3 (export+download+classify) ใช้เวลานาน (นาทีถึงหลายนาทีต่อ zone) และดาวน์โหลด GeoTIFF
จริงหลายสิบ MB ต่อ zone — ควรรันตอนอินเทอร์เน็ตเสถียร ไม่ใช่ wifi สาธารณะที่ตัดง่าย

สคริปต์นี้ห้าม raise exception ออกไปเด็ดขาด — ทุก step ห่อด้วย try/except ของตัวเอง ถ้า error จะ
print รายละเอียด error เต็ม (รวม traceback) แล้วไปต่อ step ถัดไปแบบ graceful (ไม่ crash ทั้งสคริปต์)
"""
import logging
import sys
import traceback
from pathlib import Path

import sar_classification as sc

# 2026-07-14 เพิ่ม — แก้บั๊กที่ยืนยันแล้วจากการตรวจสอบจริง (grep ทั้ง repo): สคริปต์นี้**ไม่เคยเรียก
# logging.basicConfig() เลยตั้งแต่สร้างไฟล์มา** ทำให้ logger.info()/logger.debug() ทุกจุดใน
# sar_classification.py (มีเยอะมาก -- band name matching diagnostic, outside_zone_mask, NaN row
# count, live bandNames() confirmation ฯลฯ) **ไม่เคยแสดงในผลทดสอบทุกรอบที่ผ่านมาเลย** (Python's
# logging module: ถ้าไม่มี handler ถูกตั้งค่าไว้เลยในทั้ง hierarchy จะใช้ "handler of last resort"
# ซึ่งแสดงแค่ระดับ WARNING ขึ้นไปเท่านั้น -- นี่คือเหตุผลที่ logger.warning()/logger.error() บางจุด
# เคยโผล่ในผลทดสอบ (เช่น "getDownloadURL() single-shot ล้มเหลว...") แต่ logger.info() ไม่เคยโผล่เลย)
# เพิ่ม basicConfig(level=INFO) ตรงนี้เพื่อให้ diagnostic logging ทั้งหมดที่มีอยู่แล้วในโค้ด (และที่จะ
# เพิ่มในอนาคต) แสดงผลจริงในคอนโซลของสคริปต์ทดสอบนี้ ไม่ใช่ถูกกลืนหายไปเงียบๆ อีกต่อไป
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

SCRIPT_DIR = Path(__file__).resolve().parent
GEE_PROJECT = sc.DEFAULT_GEE_PROJECT  # "maenaruea-water-pipeline"

# marker แยกต่างหากสำหรับการทดสอบเท่านั้น — ไม่แตะ SAR_LAST_CLASSIFIED_MARKER ตัวจริงที่
# data_pipeline.py ใช้งานใน production
TEST_MARKER_PATH = sc.GIS_DIR / ".sar_last_classified_test"

HA_TO_RAI = 6.25  # 1 ไร่ = 1600 m^2 = 0.16 ha  ->  1 ha = 6.25 ไร่

CROP_ORDER = ["rice", "corn", "cassava", "longan", "etc"]


def _print_section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def _print_full_error(exc: Exception) -> None:
    print(f"[FAILED] {type(exc).__name__}: {exc}")
    print("--- traceback เต็ม ---")
    print(traceback.format_exc())
    print("--- จบ traceback ---")


def _fmt_area(ha: float) -> str:
    return f"{ha:8.2f} ha  ({ha * HA_TO_RAI:9.2f} ไร่)"


def main() -> int:
    overall_ok = True

    # -------------------------------------------------------------------
    # ขั้นที่ 1: ee.Initialize()
    # -------------------------------------------------------------------
    _print_section(f"1) ee.Initialize(project='{GEE_PROJECT}') ผ่าน gee_auth.init_ee()")
    ee_ready = False
    try:
        import ee
        import gee_auth

        auth_mode = gee_auth.init_ee(GEE_PROJECT)
        print(f"auth_mode = {auth_mode}", "(Service Account -- พร้อมสำหรับ scheduled task)"
              if auth_mode == "service_account"
              else "(personal credential -- ยังไม่พร้อมสำหรับ scheduled task ระยะยาว ดู gee_auth.py)")
        print("OK:", ee.String("earth engine ready").getInfo())
        ee_ready = True
    except Exception as exc:
        _print_full_error(exc)
        print(
            "\n[หมายเหตุ] ee.Initialize() ล้มเหลว — ขั้นถัดไป (check_new_sar_image / "
            "trigger_crop_classification) จะยังถูกเรียกจริงตามที่ร้องขอ (ไม่ mock) แต่คาดว่าจะ "
            "ล้มเหลวด้วยเหตุผลเดียวกันนี้ (sar_classification.py มี try/except คลุมไว้แล้ว จึงไม่ raise "
            "แต่จะคืนค่า None / status='failed' แทน)"
        )
        overall_ok = False

    # -------------------------------------------------------------------
    # ขั้นที่ 2: check_new_sar_image() — เจอภาพ SAR ใหม่ไหม
    # -------------------------------------------------------------------
    _print_section("2) sc.check_new_sar_image() — เช็คภาพ Sentinel-1 ใหม่ (30 วันล่าสุด, AOI=zone A)")
    trigger = None
    try:
        trigger = sc.check_new_sar_image(
            gee_project=GEE_PROJECT,
            marker_path=TEST_MARKER_PATH,
            min_days_between_runs=0,  # bypass gate การรอรอบ production เพื่อทดสอบตอนนี้เลย
        )
        if trigger is None:
            print(
                "ผลลัพธ์: None — ไม่พบภาพ SAR ใหม่ในช่วง 30 วันที่ผ่านมา หรือ ee.Initialize()/ดึงข้อมูล "
                "จาก GEE ล้มเหลว (ดู log warning ด้านบน/ใน console ถ้ามี logging handler ตั้งไว้)"
            )
            overall_ok = False
        else:
            print("ผลลัพธ์: พบภาพ SAR ใหม่ — เข้าเงื่อนไขควรรัน crop classification")
            print(f"    as_of_date          = {trigger.get('as_of_date')}")
            print(f"    year                = {trigger.get('year')}")
            print(f"    latest_s1_image_date = {trigger.get('latest_s1_image_date')}")
    except Exception as exc:
        _print_full_error(exc)
        print(
            "[หมายเหตุ] เกิด exception ที่ไม่คาดคิดหลุดออกมาจาก check_new_sar_image() เอง (ผิดปกติ — "
            "ฟังก์ชันนี้ควรดัก exception ไว้ข้างในแล้วคืน None แทน) — จะข้ามไปทดสอบ "
            "trigger_crop_classification() แบบ synthetic ไม่ได้ เพราะไม่มี year ให้ใช้"
        )
        overall_ok = False

    # -------------------------------------------------------------------
    # ขั้นที่ 3: trigger_crop_classification() — classify ได้ crop map ไหม
    # -------------------------------------------------------------------
    _print_section("3) sc.trigger_crop_classification() — รัน RF v3b classify จริง")
    result = None
    if trigger is None:
        print(
            "ข้าม step นี้: ไม่มี trigger dict จาก step 2 (ไม่พบภาพ SAR ใหม่ หรือ GEE ใช้งานไม่ได้) — "
            "ถ้าต้องการทดสอบ trigger_crop_classification() แยกโดยไม่ผ่าน check_new_sar_image() ให้แก้ "
            "สคริปต์นี้ใส่ trigger = {'year': <ปีที่ต้องการ>, 'as_of_date': ..., "
            "'latest_s1_image_date': ...} เอง"
        )
    else:
        try:
            # 2026-07-12 แก้: เดิมไม่ส่ง marker_path เข้ามา ทำให้ trigger_crop_classification()
            # เขียนทับ SAR_LAST_CLASSIFIED_MARKER ตัวจริงโดยไม่ตั้งใจ (production marker ที่
            # check_new_sar_image() ใช้ gate 30 วัน) ส่งผลให้ step 7 (ทดสอบ sar_background_job.py)
            # เห็นว่า "เพิ่งรันไปเมื่อกี้นี้เอง" แล้วข้ามตัวเองไปทันที ทั้งที่ step นี้ (step 3) แค่
            # ทดสอบ classify แยกต่างหาก ไม่ควรไปยุ่งกับ marker ที่ใช้ gate จริงเลย -- ใช้
            # TEST_MARKER_PATH เดียวกับ step 2 แทน ให้ step 7 (ที่เรียก sar_background_job.py ผ่าน
            # marker ตัวจริง) ยังทดสอบ check_new_sar_image()'s gate ได้ตามที่ตั้งใจจริงๆ
            result = sc.trigger_crop_classification(trigger, marker_path=TEST_MARKER_PATH)
            print(f"status = {result.get('status')}")

            # 2026-07-14 เพิ่ม — print explicit ผล live bandNames() check (ไม่พึ่ง logging เลย เพื่อ
            # ให้เห็นหลักฐานแน่นอนว่า positional matching (FULL_IMG_BAND_ORDER) ปลอดภัยจริงสำหรับรอบนี้
            # ไม่ใช่แค่ "ไม่มี error โผล่มา" -- ดู comment เต็มที่ trigger_crop_classification() ใน
            # sar_classification.py และที่ logging.basicConfig() ด้านบนไฟล์นี้สำหรับเหตุผลที่ต้องเพิ่ม
            # การ print แบบ explicit นี้แยกจาก log
            band_check = result.get("band_order_check")
            if band_check is None:
                print(
                    "[band_order_check] ไม่มีข้อมูล -- แปลว่าโค้ดยังไม่ถึงจุดเช็ค bandNames() เลย "
                    "(ee.Initialize()/load_rf_classifier()/load_zone_boundaries() ล้มเหลวก่อนถึงจุดนั้น "
                    "ดู errors ด้านล่าง)"
                )
            elif band_check["verified"]:
                print(
                    f"[band_order_check] PASS -- full_img.bandNames().getInfo() ตรงกับ "
                    f"FULL_IMG_BAND_ORDER เป๊ะทั้ง {band_check['actual_band_count']} band "
                    f"(positional matching ใน _classify_raster_local() ปลอดภัยสำหรับรอบนี้)"
                )
            else:
                print(
                    f"[band_order_check] FAIL -- ลำดับ band จริง ({band_check['actual_band_count']} "
                    f"band, 5 ตัวแรก={band_check['actual_first5']}) ไม่ตรงกับที่คาดไว้ "
                    f"({band_check['expected_band_count']} band, 5 ตัวแรก="
                    f"{band_check['expected_first5']}) -- ควรเห็น exception raise ออกมาแล้วด้านล่าง"
                )

            if result.get("errors"):
                print("errors:")
                for err in result["errors"]:
                    print(f"    - {err}")
            if result.get("status") == "failed":
                overall_ok = False
        except Exception as exc:
            _print_full_error(exc)
            print(
                "[หมายเหตุ] เกิด exception ที่ไม่คาดคิดหลุดออกมาจาก trigger_crop_classification() เอง "
                "(ผิดปกติ — ฟังก์ชันนี้ควรดัก exception ไว้ข้างในแล้วคืน dict status='failed' แทน)"
            )
            overall_ok = False

    # -------------------------------------------------------------------
    # ขั้นที่ 3.5 (เพิ่ม 2026-07-10): sar_data_quality — สัดส่วนสัปดาห์ว่าง (0 ภาพ) เทียบ training
    #   baseline ก่อนเชื่อผล classify (ตามที่ตกลงไว้ว่าต้องรายงานให้เห็นชัดเจน ไม่ใช่แค่ไม่ error)
    # -------------------------------------------------------------------
    _print_section("3.5) sar_data_quality — สัดส่วนสัปดาห์ว่างเทียบ training baseline (ก่อนเชื่อผล classify)")
    sar_quality = (result or {}).get("sar_data_quality")
    if not sar_quality:
        print("ไม่มีข้อมูล sar_data_quality ให้แสดง (step 3 ไม่สำเร็จ หรือถูกข้าม)")
    elif "error" in sar_quality:
        print(f"[คำนวณ sar_data_quality ไม่สำเร็จ] {sar_quality['error']}")
    else:
        print(f"สัปดาห์ทั้งหมด           : {sar_quality['n_total_weeks']}")
        print(f"สัปดาห์ว่าง (0 ภาพ)      : {sar_quality['n_empty_weeks']} "
              f"({sar_quality['empty_week_pct']}%)")
        print(f"Training baseline        : {sar_quality['training_baseline_null_band_pct']}% "
              f"ของ SAR band ว่างทั้งคอลัมน์ตั้งแต่ train แล้ว (ยืนยันจาก col_medians_v3b_final.json)")
        print(f"สัปดาห์ว่างที่ตรงกับ training gap (ความเสี่ยงต่ำ)   : "
              f"{len(sar_quality['weeks_matching_training_gap'])} สัปดาห์ "
              f"{sar_quality['weeks_matching_training_gap']}")
        print(f"สัปดาห์ว่างที่ diverge จาก training (ควรระวัง)      : "
              f"{len(sar_quality['weeks_diverging_from_training'])} สัปดาห์ "
              f"{sar_quality['weeks_diverging_from_training']}")
        print(f"\n{sar_quality['risk_note']}")
        if sar_quality["weeks_diverging_from_training"]:
            overall_ok = False

    # -------------------------------------------------------------------
    # ขั้นที่ 4: สรุปพื้นที่ต่อ class เป็นไร่/เฮกตาร์ แยก zone A / zone B
    # -------------------------------------------------------------------
    _print_section("4) พื้นที่ที่ classify ได้ต่อ crop class (ไร่ / เฮกตาร์) แยก zone")
    zone_crop_area_ha = (result or {}).get("zone_crop_area_ha") or {}
    if not zone_crop_area_ha:
        print("ไม่มีข้อมูล zone_crop_area_ha ให้แสดง (step 3 ไม่สำเร็จ หรือถูกข้าม)")
    else:
        for zone_label in ("zone_A", "zone_B"):
            crop_area_ha = zone_crop_area_ha.get(zone_label)
            print(f"\n--- {zone_label} ---")
            if not crop_area_ha:
                print("    (ไม่มีข้อมูล)")
                continue
            all_crops = CROP_ORDER + [c for c in crop_area_ha if c not in CROP_ORDER]
            total_ha = sum(crop_area_ha.values())
            for crop in all_crops:
                if crop not in crop_area_ha:
                    continue
                print(f"    {crop:<8} : {_fmt_area(crop_area_ha[crop])}")
            print(f"    {'รวม':<8} : {_fmt_area(total_ha)}")

    # -------------------------------------------------------------------
    # ขั้นที่ 5: ตารางเทียบพื้นที่ classify ได้ vs พื้นที่ hardcode ปี 2020
    # -------------------------------------------------------------------
    _print_section("5) ตารางเทียบ: พื้นที่ classify ได้ vs พื้นที่ hardcode ปี 2020 (% ต่าง)")
    comparison = (result or {}).get("comparison_vs_2020_hardcoded") or {}
    if not comparison:
        print("ไม่มีข้อมูล comparison_vs_2020_hardcoded ให้แสดง (step 3 ไม่สำเร็จ หรือถูกข้าม)")
    else:
        header = (
            f"{'zone':<8} {'crop':<8} {'2020 (ha / ไร่)':<24} "
            f"{'classify ใหม่ (ha / ไร่)':<26} {'% ต่าง':>10}"
        )
        print(header)
        print("-" * len(header))
        for zone_label in ("zone_A", "zone_B"):
            zone_comparison = comparison.get(zone_label, {})
            for crop in CROP_ORDER:
                row = zone_comparison.get(crop)
                if row is None:
                    continue
                area_2020 = row.get("area_2020_ha") or 0.0
                area_new = row.get("area_new_ha") or 0.0
                delta_pct = row.get("delta_pct")
                col_2020 = f"{area_2020:7.2f} / {area_2020 * HA_TO_RAI:8.2f}"
                col_new = f"{area_new:7.2f} / {area_new * HA_TO_RAI:8.2f}"
                col_delta = f"{delta_pct:+.1f}%" if delta_pct is not None else "n/a"
                print(f"{zone_label:<8} {crop:<8} {col_2020:<24} {col_new:<26} {col_delta:>10}")

    # -------------------------------------------------------------------
    # ขั้นที่ 6 (เพิ่ม 2026-07-11): raster_meta — ตรวจสอบผล export+download+classify ต่อ zone
    #   (pixel_area_ha ควรตรงกับ scale=20m, n_pixels_outside_zone ควร > 0 เสมอเพราะ bounding box
    #   ใหญ่กว่า polygon จริงของ zone, classified_tif_path ควรมีไฟล์จริงอยู่บนดิสก์)
    # -------------------------------------------------------------------
    _print_section("6) raster_meta — ตรวจสอบผล export+download+classify ต่อ zone (สถาปัตยกรรมใหม่)")
    raster_meta = (result or {}).get("raster_meta") or {}
    if not raster_meta:
        print("ไม่มีข้อมูล raster_meta ให้แสดง (step 3 ไม่สำเร็จ หรือถูกข้าม)")
    else:
        for zone_label in ("zone_A", "zone_B"):
            meta = raster_meta.get(zone_label)
            print(f"\n--- {zone_label} ---")
            if not meta:
                print("    (ไม่มีข้อมูล — zone นี้ export/classify ล้มเหลว ดู errors ด้านบน)")
                continue
            tif_path = Path(meta.get("classified_tif_path", ""))
            tif_exists = tif_path.exists()
            tif_size_mb = (tif_path.stat().st_size / (1024 * 1024)) if tif_exists else None
            expected_pixel_area_ha = (20 * 20) / 10000  # scale=20m -> 0.04 ha/pixel
            pixel_area_ok = abs((meta.get("pixel_area_ha") or 0.0) - expected_pixel_area_ha) < 1e-6
            print(f"    pixel_area_ha         : {meta.get('pixel_area_ha')} "
                  f"({'ตรงกับ scale=20m ที่คาดไว้ (0.04 ha)' if pixel_area_ok else 'ผิดปกติ — คาดว่าควรเป็น 0.04 ha ที่ scale=20m ตรวจสอบ transform ของ GeoTIFF'})")
            print(f"    n_pixels_valid        : {meta.get('n_pixels_valid')} (พิกเซลในโซนจริงที่นับพื้นที่)")
            print(f"    n_pixels_outside_zone : {meta.get('n_pixels_outside_zone')} "
                  f"({'ปกติ (bounding box ใหญ่กว่า polygon จริง)' if (meta.get('n_pixels_outside_zone') or 0) > 0 else 'ผิดปกติ — คาดว่าควร > 0 เสมอ อาจแปลว่า .clip() ไม่ทำงานตามคาด'})")
            print(f"    classified_tif_path   : {tif_path}")
            print(f"    ไฟล์มีอยู่จริงบนดิสก์  : {'PASS' if tif_exists else 'FAIL — ไม่พบไฟล์'}"
                  + (f" ({tif_size_mb:.2f} MB)" if tif_size_mb is not None else ""))
            if not tif_exists or not pixel_area_ok or (meta.get("n_pixels_outside_zone") or 0) == 0:
                overall_ok = False

    # -------------------------------------------------------------------
    # ขั้นที่ 7 (เพิ่ม 2026-07-11): sar_background_job.py wiring — เขียน/อ่าน sar_result_latest.json
    #   ได้จริงไหม (แยกจาก sc.trigger_crop_classification() ตรงๆ ที่ทดสอบใน step 3 — นี่ทดสอบ
    #   "ชั้นห่อ" background job ที่ data_pipeline.py หลักจะมาอ่านผลผ่าน get_sar_crop_classification())
    #   หมายเหตุ: เรียก sbj.run_sar_background_job() ตรงๆ จะไปแตะ SAR_LAST_CLASSIFIED_MARKER ตัวจริง
    #   (ไม่ใช่ TEST_MARKER_PATH ที่ step 2 ใช้) — เขียนผลลง sar_result_latest.json ตัวจริงด้วย
    #   (production file) จึงข้าม step นี้ถ้า step 3 ไม่ได้รันจริงสำเร็จ กัน sar_result_latest.json
    #   ถูกเขียนทับด้วยผลที่ไม่สมบูรณ์ระหว่างทดสอบ
    # -------------------------------------------------------------------
    _print_section("7) sar_background_job.py — เขียน/อ่าน sar_result_latest.json ผ่าน background job wrapper")
    if result is None or result.get("status") not in ("ok", "partial"):
        print(
            "ข้าม step นี้: step 3 (trigger_crop_classification) ไม่สำเร็จ (status="
            f"{result.get('status') if result else None}) — จะไม่เรียก sbj.run_sar_background_job() "
            "ตรงๆ เพราะจะไปเขียนทับ sar_result_latest.json ตัวจริงด้วยผลที่ไม่สมบูรณ์ "
            "(หมายเหตุ: การจะทดสอบ step นี้ให้ครบ ต้องรอ step 3 ผ่านก่อน)"
        )
    else:
        try:
            import sar_background_job as sbj

            print(f"sar_background_job.SAR_LATEST_RESULT_PATH = {sbj.SAR_LATEST_RESULT_PATH}")
            read_before = sbj.read_latest_sar_result()
            print(
                f"read_latest_sar_result() ก่อนรัน job: "
                f"{'พบผลลัพธ์เดิม (age_days=' + str(read_before.get('age_days')) + ')' if read_before else 'ยังไม่มีผลลัพธ์เลย (ครั้งแรก)'}"
            )

            print("\nกำลังรัน sbj.run_sar_background_job() (จะ re-run trigger_crop_classification() "
                  "อีกรอบเต็มๆ เพราะเป็นฟังก์ชันคนละตัวกับ step 3 — ใช้เวลานานอีกรอบ)...")
            outcome = sbj.run_sar_background_job(gee_project=GEE_PROJECT)
            print(f"outcome.ran    = {outcome.get('ran')}")
            print(f"outcome.reason = {outcome.get('reason')}")

            read_after = sbj.read_latest_sar_result()
            if read_after is None:
                print("[FAIL] read_latest_sar_result() คืน None หลังรัน job สำเร็จ — ไม่ควรเกิดขึ้น")
                overall_ok = False
            else:
                print(
                    f"read_latest_sar_result() หลังรัน job: age_days={read_after.get('age_days')}, "
                    f"is_stale={read_after.get('is_stale')}, status={read_after.get('status')}, "
                    f"zones={list((read_after.get('zone_crop_area_ha') or {}).keys())}"
                )
                if read_after.get("is_stale"):
                    print(
                        "[FAIL] is_stale=True ทันทีหลังรันเสร็จ — ไม่ควรเกิดขึ้น (generated_at เพิ่งเขียน "
                        "ไม่กี่วินาทีก่อนหน้านี้เอง) ตรวจสอบ parse ของ generated_at ใน read_latest_sar_result()"
                    )
                    overall_ok = False
                else:
                    print("[PASS] เขียน+อ่าน sar_result_latest.json ผ่าน background job wrapper สำเร็จ")
        except Exception as exc:
            _print_full_error(exc)
            print(
                "[หมายเหตุ] เกิด exception ที่ไม่คาดคิดหลุดออกมาจาก sar_background_job.py เอง (ผิดปกติ — "
                "ทั้ง run_sar_background_job()/read_latest_sar_result() ควรดัก exception ไว้ข้างในแล้ว "
                "คืนค่า dict/None แทน)"
            )
            overall_ok = False

    # -------------------------------------------------------------------
    # สรุปรวม
    # -------------------------------------------------------------------
    _print_section("สรุปรวม")
    print(f"ee.Initialize สำเร็จ         : {'PASS' if ee_ready else 'FAIL'}")
    print(f"พบภาพ SAR ใหม่ (มี trigger)   : {'PASS' if trigger is not None else 'FAIL/ไม่พบ'}")
    print(
        f"classify สำเร็จ (status)      : "
        f"{result.get('status') if result else 'ไม่ได้รัน (ข้าม step 3)'}"
    )
    if sar_quality and "error" not in sar_quality:
        print(
            f"sar_data_quality             : {sar_quality['n_empty_weeks']}/{sar_quality['n_total_weeks']} "
            f"สัปดาห์ว่าง ({sar_quality['empty_week_pct']}%), diverge จาก training "
            f"{len(sar_quality['weeks_diverging_from_training'])} สัปดาห์ "
            f"({'ควรตรวจสอบเพิ่มก่อนเชื่อผล classify' if sar_quality['weeks_diverging_from_training'] else 'ความเสี่ยงต่ำ'})"
        )
    print(
        "\n[หมายเหตุ] สคริปต์นี้ไม่ raise exception ออกไปไม่ว่ากรณีใด — ทุก error ถูกดักและ print "
        "รายละเอียดเต็มไว้ด้านบนแล้ว ผลลัพธ์ FAIL ในสรุปนี้แปลว่า 'ทดสอบแล้วไม่ผ่าน' ไม่ใช่ 'สคริปต์พัง'"
    )
    return 0 if overall_ok else 1


if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = main()
    except Exception as exc:  # กันสุดท้ายจริงๆ — ไม่ควรถึงจุดนี้เลยถ้าทุก step ห่อ try/except ไว้ครบ
        print("\n" + "=" * 78)
        print("[UNEXPECTED] เกิด exception หลุดออกมาถึงระดับบนสุดของสคริปต์ (ไม่ควรเกิดขึ้น)")
        print("=" * 78)
        _print_full_error(exc)
        exit_code = 1
    sys.exit(exit_code)
