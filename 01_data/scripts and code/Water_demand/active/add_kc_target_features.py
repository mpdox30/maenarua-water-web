"""
add_kc_target_features.py
============================
2026-09-23 เพิ่ม -- ส่วนหนึ่งของข้อ 5 (ปรับปรุงโมเดล magnitude regressor)

พบจาก error breakdown (ดู /tmp/error_breakdown.py วันเดียวกัน) ว่า error ของโมเดล stage2
กระจุกตัวรุนแรงที่สุดที่สัปดาห์ demand พีค (Q4 ของ wet weeks) และ 10 อันดับ error แย่ที่สุด
ทั้งหมดตรงกับสัปดาห์ 27-31/2023 ของ zone_A -- ตรวจ kc_weekly_lookup_all_crops.csv แล้วพบว่า Kc
ของข้าว (พืชหลัก 1,510 ha ใน zone_A) กระโดดจาก 0.000 (offseason, week<=26) เป็น 1.208 (GS1,
week>=27) แบบ step function ทันที ไม่ค่อยๆ ไล่ขึ้น -- ทำให้ NIR_A_m3 = Kc * ET0 * area กระโดด
แบบไม่ต่อเนื่องตอนเข้าสู่ฤดูปลูก

**Kc lookup ขึ้นกับ "สัปดาห์ปฏิทิน" (week) ล้วนๆ ไม่ขึ้นกับปี -- แปลว่ารู้ Kc ของสัปดาห์เป้าหมาย
ล่วงหน้าแน่นอน 100% แม้จะทำนายล่วงหน้า 12 สัปดาห์ก็ตาม** (ต่างจาก ET0/ฝนที่ไม่รู้ล่วงหน้า) แต่เดิม
โมเดลไม่เคยได้รับ Kc ของสัปดาห์เป้าหมายเป็น feature เลย มีแค่ WoY_sin/WoY_cos (seasonality แบบ
smooth) ซึ่งไม่สามารถแทนค่า step function ได้ดี -- โมเดลต้องเดาเองจากข้อมูลแค่ 3 ปี train
(2020-2022) ว่าสัปดาห์ไหนกันแน่ที่ Kc เปลี่ยน

สคริปต์นี้: คำนวณ area-weighted Kc (ถ่วงน้ำหนักตามพื้นที่ปลูกต่อ crop, AREA_ZONE_A/B เดียวกับที่
ใช้คำนวณ NIR_A_m3/GIR_B_m3 เดิม -- ดู feature_schema.md หัวข้อ 2) ของ "สัปดาห์เป้าหมาย" (as_of
date + h สัปดาห์) สำหรับ h=1..12 แยกต่อ zone

**สำคัญ -- บันทึกเป็นไฟล์แยก `kc_target_features.csv` (key: zone, year, week) ไม่แก้
ml_features_phase4.csv ตรงๆ** เพราะ get_regressor_features()/get_feature_cols() ในสคริปต์เดิมทุกตัว
(build_conformal_intervals.py, build_cqr_intervals.py, build_mondrian_cqr_intervals.py) นิยาม
reg_feats = "ทุกคอลัมน์ใน ml_features_phase4.csv ที่ไม่อยู่ใน exclude set" -- ถ้าเพิ่มคอลัมน์
kc_target_h1..h12 เข้าไปตรงๆ ในไฟล์นั้น สคริปต์เดิมทั้ง 3 ตัวจะดึงคอลัมน์ทั้ง 12 (ของทุก horizon)
เข้าไปเป็น feature ของทุกโมเดลโดยอัตโนมัติแบบไม่ตั้งใจ (ทั้งที่แต่ละ horizon ควรใช้แค่
kc_target_h{h} ของตัวเอง) -- แยกไฟล์ไว้แล้ว merge เฉพาะคอลัมน์ที่ต้องการต่อ horizon ในสคริปต์
train ใหม่แทน (train_stage2_with_kc.py) ปลอดภัยกว่า ไม่กระทบของเดิมที่ commit ไปแล้ว
"""
from pathlib import Path

import numpy as np
import pandas as pd

ACTIVE_DIR = Path(__file__).resolve().parent
HORIZON = 12

# คัดลอกตรงจาก feature_schema.md หัวข้อ 2 (เดียวกับที่ใช้คำนวณ NIR_A_m3/GIR_B_m3 เดิมทุกประการ)
AREA_ZONE_A = {
    "rice": 1510.72 * 10000,
    "corn": 621.36 * 10000,
    "longan": 461.36 * 10000,
    "cassava": 0.16 * 10000,
    # 'etc' ไม่รวม -- ไม่มี Kc นิยาม (ดู feature_schema.md หัวข้อ 2)
}
AREA_ZONE_B = {
    "rice": 282.88 * 10000,
    "corn": 215.52 * 10000,
    "longan": 170.64 * 10000,
    "cassava": 0.32 * 10000,
}
ZONE_AREAS = {"zone_A": AREA_ZONE_A, "zone_B": AREA_ZONE_B}


def build_kc_weighted_lookup(kc_df: pd.DataFrame) -> dict:
    """คืน dict[(zone, week)] -> area-weighted Kc (เฉลี่ยถ่วงน้ำหนักพื้นที่ข้าม crop ทุกตัวใน zone)"""
    out = {}
    total_area = {zone: sum(areas.values()) for zone, areas in ZONE_AREAS.items()}
    for zone, areas in ZONE_AREAS.items():
        for week in range(1, 53):
            weighted_sum = 0.0
            for crop, area_m2 in areas.items():
                if area_m2 == 0:
                    continue
                row = kc_df[(kc_df["crop"] == crop) & (kc_df["week"] == week)]
                kc_val = float(row["Kc"].values[0]) if len(row) > 0 else 0.0
                weighted_sum += kc_val * area_m2
            out[(zone, week)] = weighted_sum / total_area[zone]
    return out


def target_week_for(date: pd.Timestamp, h: int) -> int:
    """สัปดาห์ปฏิทิน (ISO week, cap ที่ 52 -- ปีที่มี week 53 ให้ fallback ไปใช้ 52 เพราะ
    kc_weekly_lookup_all_crops.csv มีแค่ week 1-52) ของวันที่ h สัปดาห์ถัดจาก date"""
    target_date = date + pd.Timedelta(weeks=h)
    iso_week = int(target_date.isocalendar().week)
    return min(iso_week, 52)


def main():
    df = pd.read_csv(ACTIVE_DIR / "ml_features_phase4.csv", parse_dates=["date"])
    kc_df = pd.read_csv(ACTIVE_DIR / "kc_weekly_lookup_all_crops.csv")
    kc_lookup = build_kc_weighted_lookup(kc_df)

    out = df[["zone", "year", "week"]].copy()
    for h in range(1, HORIZON + 1):
        col = f"kc_target_h{h}"
        values = []
        for _, row in df.iterrows():
            wk = target_week_for(row["date"], h)
            values.append(kc_lookup[(row["zone"], wk)])
        out[col] = values
        print(f"kc_target_h{h}: min={min(values):.3f} max={max(values):.3f} "
              f"mean={np.mean(values):.3f}")

    out.to_csv(ACTIVE_DIR / "kc_target_features.csv", index=False)
    print("\nSaved kc_target_features.csv (ไฟล์แยก, key=zone/year/week -- ไม่แก้ ml_features_phase4.csv)")

    # แสดงตัวอย่างช่วงสัปดาห์ 24-31/2023 zone_A ว่า kc_target_h1 (พรุ่งนี้อีก 1 สัปดาห์) จับ step ได้ไหม
    merged = df.merge(out, on=["zone", "year", "week"])
    check = merged[(merged["zone"] == "zone_A") & (merged["year"] == 2023) &
                    (merged["week"] >= 20) & (merged["week"] <= 31)]
    print("\nตรวจสอบ zone_A 2023 week 20-31 (kc_target_h1 ควรกระโดดตรงสัปดาห์ 26->27):")
    print(check[["week", "kc_target_h1", "y_h1"]].to_string(index=False))


if __name__ == "__main__":
    main()
