# -*- coding: utf-8 -*-
"""
รวม intraday_range_full_history.csv (max/min/range รายวัน, ครอบคลุม 386/393 วัน) เข้ากับ
Training_Values_with_release_flag.csv (393 แถว, มี is_release_active/release_rate_m3day อยู่แล้ว)
ด้วย join บนคอลัมน์ Date -- วันที่ไม่มีข้อมูล intraday (ช่องว่าง 2026-06-28..2026-07-09) จะเป็น NaN
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

train = pd.read_csv(os.path.join(HERE, "Training_Values_with_release_flag.csv"))
rng = pd.read_csv(os.path.join(HERE, "intraday_range_full_history.csv"))

merged = train.merge(
    rng[["Date", "max_level_24h", "range_24h"]], on="Date", how="left"
)

n_missing = merged["range_24h"].isna().sum()
print(f"Rows: {len(merged)}, missing range_24h: {n_missing} ({n_missing/len(merged)*100:.1f}%)")
print(merged.loc[merged["range_24h"].isna(), "Date"].tolist())

out_path = os.path.join(HERE, "Training_Values_full_features.csv")
merged.to_csv(out_path, index=False)
print(f"Saved {out_path}")
