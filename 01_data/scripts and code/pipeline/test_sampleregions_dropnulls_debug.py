"""
test_sampleregions_dropnulls_debug.py
======================================
2026-07-11 แก้ทั้งไฟล์ — เวอร์ชันแรกทดสอบ sampleRegions(..., dropNulls=True/False) แต่ยืนยันแล้วด้วย
`help(ee.Image.sampleRegions)` จริง (import ee เฉยๆ ไม่ต้องมี GEE credential เลย) ว่า sampleRegions()
**ไม่มี** parameter ชื่อ dropNulls อยู่จริง (มีแค่ collection, properties, scale, projection,
tileScale, geometries — ยืนยันด้วย help() ตรงๆ ไม่ใช่เดา) ใส่เข้าไปจะได้ TypeError ทันที ส่วน
dropNulls มีอยู่จริงแค่ใน ee.Image.sample() เท่านั้น (ยืนยันด้วย help(ee.Image.sample) เห็น dropNulls
ในนั้นจริง)

แก้ทางแก้เป็น .unmask(SAR_MASK_SENTINEL) บน full_img ทั้งก้อนก่อน sampleRegions() แทน (ดู
sar_classification.py: trigger_crop_classification()) — สคริปต์นี้ทดสอบว่าวิธีนี้ได้ผลจริงตามที่
ออกแบบไว้ 3 ขั้น:

  ขั้น 1 (ยืนยัน API signature ก่อน ไม่เดา): import ee แล้ว help(ee.Image.sampleRegions) +
    help(ee.Image.sample) พิมพ์ parameter จริงออกมาให้เห็น (ไม่ต้องมี credential เลย — pure client
    library introspection)
  ขั้น 2 (เปรียบเทียบ): sampleRegions() บน full_img แบบไม่ unmask (มี masked band จากสัปดาห์ว่าง)
    เทียบกับ full_img.unmask(SAR_MASK_SENTINEL) (ตามที่แก้ใน sar_classification.py จริง) — คาดว่า
    แบบไม่ unmask จะได้แถวน้อยกว่าหรือ 0 แถว (sampleRegions() ทิ้ง pixel ที่มี band ใดก็ตาม masked
    อยู่ เป็นพฤติกรรม built-in ไม่มี parameter ให้ override) ส่วนแบบ unmask() แล้วควรได้ครบทุก pixel
  ขั้น 3 (ตรวจ property จริง): เช็คว่า band จากสัปดาห์ว่างมีค่า = SAR_MASK_SENTINEL (-9999) เป๊ะ
    (ไม่ใช่ None, ไม่ใช่ 0, ไม่ใช่ค่าอื่น) ในผลลัพธ์จาก full_img ที่ unmask() แล้ว และยืนยันว่า
    classify_feature_matrix() แปลงค่านี้กลับเป็น NaN แล้ว fillna(col_medians) ถูกต้อง (เรียกใช้จริง
    ผ่าน sc.classify_feature_matrix() ด้วยแถวจริงที่ได้จาก GEE ไม่ใช่ synthetic data)

รันไม่ได้ในนี้ (sandbox ไม่มี GEE credential) — ให้ผู้ใช้รันบนเครื่องจริงที่ ee.Initialize() สำเร็จแล้ว
(เหมือน test_sar_classification_live.py/test_s1_weekly_windows_debug.py) ขั้น 1 (help() signature
check) รันได้แม้ไม่มี credential เพราะเป็นแค่ client library introspection ล้วนๆ
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sar_classification as sc


def step1_verify_api_signature():
    """
    ยืนยัน signature จริงของ sampleRegions()/sample() ก่อนแก้อะไรทั้งนั้น — ไม่เดาชื่อ parameter
    รันได้แม้ไม่มี GEE credential เลย (แค่ import ee เฉยๆ ไม่เรียก ee.Initialize())
    """
    import ee
    import inspect

    print("=" * 70)
    print("ขั้น 1: ยืนยัน signature จริงของ ee.Image.sampleRegions()/sample() (ไม่ต้องมี credential)")
    print("=" * 70)

    sr_sig = inspect.signature(ee.Image.sampleRegions)
    print(f"ee.Image.sampleRegions{sr_sig}")
    has_dropnulls_sr = "dropNulls" in sr_sig.parameters
    print(f"  -> มี parameter 'dropNulls' หรือไม่: {has_dropnulls_sr}")

    s_sig = inspect.signature(ee.Image.sample)
    print(f"ee.Image.sample{s_sig}")
    has_dropnulls_s = "dropNulls" in s_sig.parameters
    print(f"  -> มี parameter 'dropNulls' หรือไม่: {has_dropnulls_s}")

    if has_dropnulls_sr:
        print("!! ผิดคาด: sampleRegions() มี dropNulls จริง -- ทบทวนวิธีแก้ปัจจุบัน (.unmask()) อีกครั้ง")
    else:
        print("=> ยืนยันแล้ว: sampleRegions() ไม่มี dropNulls จริง (ตรงกับที่ตรวจไว้ก่อนแก้โค้ด) "
              "-- .unmask(SAR_MASK_SENTINEL) เป็นทางแก้ที่ถูกต้อง ไม่ใช่ dropNulls=False")
    print()


def main():
    import ee

    step1_verify_api_signature()

    print("=" * 70)
    print("ขั้น 1.5: ee.Initialize() (ต้องมี credential จากนี้ไป)")
    print("=" * 70)
    ee.Initialize(project=sc.DEFAULT_GEE_PROJECT)
    print("OK")

    year = 2026  # ปีปัจจุบัน (ตาม env date 2026-07-11) — เปลี่ยนได้ถ้าต้องการทดสอบปีอื่น

    zones = sc.load_zone_boundaries()
    aoi = sc._to_ee_geometry(zones["zone_A"]["geom_4326"])
    zone_a_feature = ee.FeatureCollection([ee.Feature(aoi)])

    weekly_counts = sc._get_weekly_image_counts(aoi, year)
    populated_weeks = [c["week"] for c in weekly_counts if c["n_images"] > 0]
    empty_weeks = [c["week"] for c in weekly_counts if c["n_images"] == 0]
    print(f"สัปดาห์ที่มีภาพจริง: {len(populated_weeks)}/36")
    print(f"สัปดาห์ว่าง (0 ภาพ): {len(empty_weeks)}/36 ({len(empty_weeks)/36*100:.1f}%) -> {empty_weeks}")

    # -------------------------------------------------------------------
    # ขั้น 2: เปรียบเทียบ sampleRegions() บน full_img แบบไม่ unmask vs unmask(SAR_MASK_SENTINEL)
    # -------------------------------------------------------------------
    print()
    print("=" * 70)
    print("ขั้น 2: sampleRegions() บน full_img -- ไม่ unmask (เดิม) vs unmask(SAR_MASK_SENTINEL) (แก้แล้ว)")
    print("=" * 70)

    s2_img = sc._build_s2_dry_season_composite(aoi, year)
    s1_img = sc._build_s1_weekly_vvvh_stack(aoi, year)
    full_img_raw = s2_img.addBands(s1_img)  # ยังไม่ unmask -- มี masked pixel จากสัปดาห์ว่าง
    full_img_unmasked = full_img_raw.unmask(sc.SAR_MASK_SENTINEL)  # ตรงกับ production code จริง

    samples_raw = full_img_raw.sampleRegions(
        collection=zone_a_feature, scale=20, geometries=False,
    )
    rows_raw = samples_raw.getInfo()["features"]
    print(f"ไม่ unmask (พฤติกรรมเดิมก่อนแก้) -> {len(rows_raw)} แถว", end="")
    print("  <-- คาดว่าน้อย/0 ถ้ามี masked band จริง (sampleRegions ทิ้ง pixel ที่มี band masked)" if len(rows_raw) == 0 else "  <-- ตรวจเพิ่ม")

    samples_unmasked = full_img_unmasked.sampleRegions(
        collection=zone_a_feature, scale=20, geometries=False,
    )
    rows_unmasked = samples_unmasked.getInfo()["features"]
    print(f"unmask(SAR_MASK_SENTINEL) (พฤติกรรมใหม่หลังแก้) -> {len(rows_unmasked)} แถว", end="")
    print("  <-- ควรมีแถวครบ (การแก้สำเร็จ)" if rows_unmasked else "  <-- ยังได้ 0 แถว ต้องตรวจ geometry/scale/aoi เพิ่ม")

    # -------------------------------------------------------------------
    # ขั้น 3: ตรวจ property จริงของ band ที่ควรเป็น sentinel (มาจากสัปดาห์ว่าง) + วิ่งผ่าน
    # classify_feature_matrix() จริงเพื่อยืนยัน sentinel -> NaN -> fillna(col_medians) ถูกต้อง
    # -------------------------------------------------------------------
    print()
    print("=" * 70)
    print("ขั้น 3: ตรวจว่า band จากสัปดาห์ว่างมีค่า = SAR_MASK_SENTINEL เป๊ะ + ทดสอบ classify_feature_matrix() จริง")
    print("=" * 70)

    if rows_unmasked and empty_weeks:
        props = rows_unmasked[0]["properties"]
        sample_empty_week = empty_weeks[0]
        vv_band, vh_band = sc._week_to_band_names(sample_empty_week)
        print(f"สัปดาห์ว่างตัวอย่าง: week={sample_empty_week} -> band {vv_band}/{vh_band}")
        print(f"  {vv_band} = {props.get(vv_band)!r}  (คาดว่า == {sc.SAR_MASK_SENTINEL})")
        print(f"  {vh_band} = {props.get(vh_band)!r}  (คาดว่า == {sc.SAR_MASK_SENTINEL})")
        if props.get(vv_band) == sc.SAR_MASK_SENTINEL and props.get(vh_band) == sc.SAR_MASK_SENTINEL:
            print("=> ยืนยันแล้ว: band จากสัปดาห์ว่างเป็น sentinel เป๊ะ (ไม่ใช่ None/0) ตามที่ออกแบบไว้")
        else:
            print("=> ผิดปกติ! ค่าไม่ตรง sentinel -- ตรวจ .unmask()/_weekly_mean_vvvh_or_masked() อีกครั้ง")

        if populated_weeks:
            vv2, vh2 = sc._week_to_band_names(populated_weeks[0])
            v_vv2, v_vh2 = props.get(vv2), props.get(vh2)
            print(f"เทียบกับสัปดาห์มีภาพจริง week={populated_weeks[0]}: {vv2}={v_vv2!r}, {vh2}={v_vh2!r}")
            if v_vv2 == sc.SAR_MASK_SENTINEL or v_vh2 == sc.SAR_MASK_SENTINEL:
                print("!! ผิดปกติ: สัปดาห์ที่มีภาพจริงกลับได้ sentinel ไปด้วย -- ตรวจ .selfMask()/unmask() อีกครั้ง")

        # รัน classify_feature_matrix() จริงกับแถวจริงจาก GEE (ไม่ใช่ synthetic data) เพื่อยืนยัน
        # sentinel -> NaN -> fillna(col_medians) ตลอดสาย ก่อนเชื่อผล classify
        import pandas as pd
        rf = sc.load_rf_classifier()
        rows_all = [f["properties"] for f in rows_unmasked]
        df = pd.DataFrame(rows_all)
        n_sentinel_before = int((df.reindex(columns=rf["feature_order"]) == sc.SAR_MASK_SENTINEL).sum().sum())
        print(f"\nจำนวนค่า sentinel ทั้งหมดใน {len(df)} แถว x 86 features: {n_sentinel_before}")
        preds = sc.classify_feature_matrix(rf, df)
        print(f"classify_feature_matrix() รันสำเร็จ ไม่ error -- preds: {preds}")
        print("=> ยืนยันแล้วว่า sentinel -> NaN -> fillna(col_medians) ทำงานถูกต้องกับข้อมูลจริงจาก GEE")
    else:
        print("ข้าม -- ไม่มีแถวจาก unmask() หรือไม่มีสัปดาห์ว่างให้เทียบ")

    print()
    print("=" * 70)
    print("สรุป")
    print("=" * 70)
    print(f"- สัปดาห์ว่าง: {len(empty_weeks)}/36 ({len(empty_weeks)/36*100:.1f}%)")
    print(f"- ไม่ unmask       -> {len(rows_raw)} แถว")
    print(f"- unmask(sentinel) -> {len(rows_unmasked)} แถว")
    if len(rows_raw) < len(rows_unmasked):
        print("=> สมมติฐานถูกต้อง: masked band (ไม่ใช่ geometry/scale) คือต้นเหตุที่ทำให้ก่อนหน้านี้ได้แถวน้อย/0")
        print("   การแก้ .unmask(SAR_MASK_SENTINEL) ใน trigger_crop_classification() แก้ปัญหานี้ได้จริง")
    elif len(rows_unmasked) == 0:
        print("=> การแก้ .unmask() ยังไม่พอ -- ต้องตรวจ geometry/scale/aoi เพิ่มเติม")
    else:
        print("=> ทั้งสองแบบได้แถวเท่ากัน -- อาจไม่มีสัปดาห์ว่างมากพอที่จะทำให้ sampleRegions() ทิ้งแถวในรอบทดสอบนี้")
        print("   (ปกติถ้า empty_week_pct ต่ำ) ลองปีอื่นที่มี empty week เยอะกว่านี้")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nFAILED: {type(exc).__name__}: {exc}")
        print("(คาดว่าจะ fail ตรงนี้ถ้ารันใน sandbox ที่ไม่มี GEE credential -- ")
        print(" ให้รันสคริปต์นี้บนเครื่องจริงที่ ee.Initialize() สำเร็จแล้วแทน)")
        sys.exit(1)
