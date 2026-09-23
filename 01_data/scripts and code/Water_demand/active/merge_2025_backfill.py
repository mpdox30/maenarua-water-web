"""
merge_2025_backfill.py
=======================
รวมข้อมูลปี 2025 ที่ backfill เสร็จแล้ว (ml_features_live.csv) เข้ากับ
ml_features_phase4.csv (2020-2024) แบบต่อเนื่อง (continuous time series)
แล้ว recompute lag/rolling/y_h1..h12 ใหม่ทั้งหมดข้ามรอยต่อปี 2024->2025

Protocol การคำนวณ lag/rolling/target อ้างอิงจาก build_feature_matrix()
ใน archive/combined_final_pipeline.py (ต้นทางของ ml_features_phase4.csv เดิม)
ทุกประการ:
  LAG_WINDOWS (target)   = [1,2,3,4,8,12]
  ROLL_WINDOWS (target)  = [4,8]  (roll_mean/std ใช้ shift(1) ก่อน แล้วค่อย rolling)
  ET0_mm_week lag        = [1,2,4]
  P_mm_week lag          = [1,2,4]
  VPD_kPa lag            = [1,2]
  MEI lag                = [4,8]
  y_h{h} = target_col.shift(-h)  สำหรับ h=1..12

season_enc: ยืนยันจากข้อมูลจริงแล้วว่าเป็น deterministic function ของ "week"
เพียงอย่างเดียว (ค่าเดียวกันทุกปี 2020-2024 ในแต่ละสัปดาห์) จึงสร้าง lookup
table week->season_enc จาก phase4 เดิมแล้ว apply กับสัปดาห์ปี 2025 ได้ตรงๆ

หมายเหตุสำคัญ: สคริปต์นี้ "recompute ใหม่ทั้งหมด" ไม่ใช่แค่ append -- เพราะ
lag/rolling ของแถวท้ายปี 2024 (เช่น week 45-52) เดิมมี NaN บางส่วนเพราะไม่มี
future data ให้ shift(-h) ได้ (ไม่มีปี 2025 ตอนนั้น) -- พอมีปี 2025 ต่อแล้ว
ค่า y_h1..h12 ของสัปดาห์ปลายปี 2024 เหล่านั้นควรมีค่าจริงแล้ว (ไม่ใช่ NaN อีกต่อไป)
"""
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ACTIVE_DIR = Path(__file__).resolve().parent  # จะ override ด้านล่างให้ชี้ไป active/ จริง
HORIZON = 12
LAG_WINDOWS = [1, 2, 3, 4, 8, 12]
ROLL_WINDOWS = [4, 8]

ZONE_CONFIG = {
    "zone_A": "NIR_A_m3",
    "zone_B": "GIR_B_m3",
}

BASE_COLS_TEMPLATE = [
    "year", "week", "month", "date",
    "ET0_mm_week", "T_mean", "RH_pct", "VPD_kPa", "u2_ms", "Rn_MJ",
    "P_mm_week", "P_eff_mm",
    "SPI_4", "drought_flag", "AI_week",
    "MEI", "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
    "season_enc",
]


def add_lag_features(df, col, lags):
    for lag in lags:
        df[f"{col}_lag{lag}"] = df[col].shift(lag)
    return df


def add_rolling_features(df, col, windows):
    for w in windows:
        df[f"{col}_roll{w}_mean"] = df[col].shift(1).rolling(w).mean()
        df[f"{col}_roll{w}_std"] = df[col].shift(1).rolling(w).std()
    return df


def main(active_dir: Path, pipeline_dir: Path):
    phase4_path = active_dir / "ml_features_phase4.csv"
    live_path = pipeline_dir / "ml_features_live.csv"

    # ── backup ต้นฉบับก่อนเขียนทับ ──────────────────────────────────────────
    backup_path = active_dir / "ml_features_phase4_backup_before_2025_merge.csv"
    shutil.copy2(phase4_path, backup_path)
    print(f"[backup] สำรอง phase4 เดิมไว้ที่: {backup_path.name}")

    phase4 = pd.read_csv(phase4_path)
    live = pd.read_csv(live_path)
    live25 = live[live["year"] == 2025].copy()

    if live25.empty:
        raise SystemExit("ไม่พบข้อมูลปี 2025 ใน ml_features_live.csv -- หยุดทำงาน")

    # ── week -> season_enc lookup (deterministic ต่อสัปดาห์ ยืนยันจากข้อมูลจริงแล้ว) ──
    week_season = (
        phase4[["week", "season_enc"]]
        .dropna()
        .drop_duplicates(subset=["week"])
        .set_index("week")["season_enc"]
        .to_dict()
    )
    missing_weeks = sorted(set(live25["week"].unique()) - set(week_season.keys()))
    if missing_weeks:
        raise SystemExit(f"ไม่มี season_enc lookup สำหรับสัปดาห์: {missing_weeks}")

    all_frames = []
    diagnostics = []

    for zone, target_col in ZONE_CONFIG.items():
        # ── 1) raw base ของปี 2020-2024 จาก phase4 (ตัด lag/roll/y_h ออก) ──────
        z_old = phase4[phase4["zone"] == zone].copy()
        base_cols_old = BASE_COLS_TEMPLATE + [target_col]
        z_old_base = z_old[base_cols_old].copy()
        z_old_base["zone"] = zone
        z_old_base["target_col"] = target_col

        # ── 2) raw base ของปี 2025 จาก ml_features_live.csv ─────────────────
        z_new = live25[live25["zone"] == zone].copy().sort_values("week")
        z_new["date"] = pd.to_datetime(
            z_new["year"].astype(int).astype(str) + "-W" +
            z_new["week"].astype(int).astype(str).str.zfill(2) + "-1",
            format="%G-W%V-%u",
        )
        z_new["month"] = z_new["date"].dt.month
        z_new["date"] = z_new["date"].dt.strftime("%Y-%m-%d")
        z_new["WoY_sin"] = np.sin(2 * np.pi * z_new["week"] / 52)
        z_new["WoY_cos"] = np.cos(2 * np.pi * z_new["week"] / 52)
        z_new["MoY_sin"] = np.sin(2 * np.pi * z_new["month"] / 12)
        z_new["MoY_cos"] = np.cos(2 * np.pi * z_new["month"] / 12)
        z_new["season_enc"] = z_new["week"].map(week_season)
        z_new["zone"] = zone
        z_new["target_col"] = target_col
        z_new_base = z_new[base_cols_old + ["zone", "target_col"]].copy()

        # ── 3) รวมต่อเนื่อง + เรียงตาม year,week ─────────────────────────────
        z = pd.concat([z_old_base, z_new_base], ignore_index=True)
        z = z.sort_values(["year", "week"]).reset_index(drop=True)

        n_dup = z.duplicated(subset=["year", "week"]).sum()
        if n_dup:
            raise SystemExit(f"{zone}: พบแถวซ้ำ (year,week) {n_dup} แถวหลังรวม -- หยุดทำงาน")

        # ── 4) recompute lag + rolling บน target (ข้าม 2024->2025 ต่อเนื่อง) ──
        z = add_lag_features(z, target_col, LAG_WINDOWS)
        z = add_rolling_features(z, target_col, ROLL_WINDOWS)
        z = add_lag_features(z, "ET0_mm_week", [1, 2, 4])
        z = add_lag_features(z, "P_mm_week", [1, 2, 4])
        z = add_lag_features(z, "VPD_kPa", [1, 2])
        z = add_lag_features(z, "MEI", [4, 8])

        # ── 5) recompute y_h1..h12 ──────────────────────────────────────────
        for h in range(1, HORIZON + 1):
            z[f"y_h{h}"] = z[target_col].shift(-h)

        all_frames.append(z)

        # diagnostics: กี่แถวของปลายปี 2024 ที่ y_h เดิมเป็น NaN แล้วตอนนี้มีค่าแล้ว
        old_tail_2024 = z_old[(z_old["year"] == 2024) & (z_old["week"] >= 41)]
        n_old_nan_yh1 = old_tail_2024["y_h1"].isna().sum() if "y_h1" in old_tail_2024 else None
        diagnostics.append((zone, len(z_old_base), len(z_new_base), len(z), n_old_nan_yh1))

    merged = pd.concat(all_frames, ignore_index=True)
    merged = merged.sort_values(["year", "week", "zone"]).reset_index(drop=True)

    horizon_cols = [f"y_h{h}" for h in range(1, HORIZON + 1)]
    before_drop = len(merged)
    merged = merged.dropna(subset=horizon_cols, how="all").reset_index(drop=True)
    dropped = before_drop - len(merged)

    # ── จัดคอลัมน์ให้ตรงลำดับเดิมของ phase4 เป๊ะ (รวม column ใหม่ถ้ามี = ไม่ควรมี) ──
    missing_cols = set(phase4.columns) - set(merged.columns)
    extra_cols = set(merged.columns) - set(phase4.columns)
    if missing_cols:
        raise SystemExit(f"คอลัมน์หายไปจาก schema เดิม: {missing_cols}")
    if extra_cols:
        raise SystemExit(f"มีคอลัมน์เกินจาก schema เดิม: {extra_cols}")
    merged = merged[phase4.columns.tolist()]

    merged.to_csv(phase4_path, index=False)

    print(f"\n{'='*70}")
    print("สรุปการ merge")
    print(f"{'='*70}")
    print(f"phase4 เดิม: {len(phase4)} แถว  ->  phase4 ใหม่ (2020-2025): {len(merged)} แถว")
    print(f"ตัดแถวที่ y_h1..h12 เป็น NaN ทั้งหมด (ไม่มี future ให้ shift): {dropped} แถว")
    for zone, n_old, n_new25, n_total, n_old_nan in diagnostics:
        print(f"  {zone}: 2020-2024={n_old} แถว, 2025={n_new25} แถว, รวม (ก่อนตัด NaN)={n_total} แถว, "
              f"เดิม y_h1 เป็น NaN ที่ week>=41/2024={n_old_nan}")

    print(f"\nปีที่มีในไฟล์ใหม่: {sorted(merged['year'].unique())}")
    for zone in ZONE_CONFIG:
        zsub = merged[merged["zone"] == zone]
        print(f"  {zone}: {len(zsub)} แถว, สัปดาห์ปี 2025 ที่มี: "
              f"{sorted(zsub[zsub['year']==2025]['week'].unique())}")

    # ── ตรวจ sanity: week 45-48/2024 ตอนนี้ y_h1..h4 ไม่ควรเป็น NaN แล้ว ──────
    check = merged[(merged["zone"] == "zone_A") & (merged["year"] == 2024) & (merged["week"] == 48)]
    if not check.empty:
        row = check.iloc[0]
        print(f"\n[sanity check] zone_A week48/2024 y_h1={row['y_h1']} y_h4={row['y_h4']} "
              f"(ควรมีค่าแล้ว ไม่ใช่ NaN เพราะตอนนี้มีข้อมูลปี 2025 ต่อให้ shift ได้)")

    print(f"\nเขียนทับ: {phase4_path}")
    print(f"สำรองไว้ที่ (ถ้าต้องย้อนกลับ): {backup_path}")


if __name__ == "__main__":
    ACTIVE = Path(r"D:\maenaruea-water-web\01_data\scripts and code\Water_demand\active")
    PIPELINE = Path(r"D:\maenaruea-water-web\01_data\scripts and code\pipeline")
    main(ACTIVE, PIPELINE)
