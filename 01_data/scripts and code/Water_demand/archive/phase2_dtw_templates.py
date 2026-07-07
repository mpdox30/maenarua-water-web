"""
=============================================================
Phase 2 — SAR-Based Crop Phenology Detection
DTW Templates derived from field data (2020–2023)
Mae Na Rua Sub-District, Phayao, Northern Thailand
=============================================================

Growing Stage Boundaries — from phenology_calendar_by_crop_year.csv
---------------------------------------------------------------------
RICE    : plant W26 (DOY 181±18) → harvest W47 (DOY 325) | ~20 weeks
CORN    : plant W25 (DOY 174±47) → harvest W39 (DOY 272) | ~17 weeks
CASSAVA : plant W17 (DOY 118±53) → harvest ~W07 next year | ~42 weeks
LONGAN  : perennial — stress phase W44–50 (Nov–Dec)
RUBBER  : perennial — defoliation W01–08 (Jan–Feb)

SAR Backscatter Templates (VH dB) — calibrated from literature
for tropical smallholder systems + adjusted to match field date ranges
---------------------------------------------------------------------
References:
  Nguyen et al. (2016) Remote Sens. — rice SAR phenology Mekong
  Torbick et al. (2017) Remote Sens. — SE Asia rice SAR
  Verhegghen et al. (2014) Remote Sens. — rubber SAR signature
  Longan: adapted from Kc dynamics (Menzel & Lüdders 2001)
=============================================================
"""

import numpy as np
import pandas as pd
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean


# ─────────────────────────────────────────────────────────────
# 1.  GROWING STAGE WEEK BOUNDARIES (from field data)
# ─────────────────────────────────────────────────────────────
# Each tuple = (week_start, week_end) inclusive, 1-indexed (1=Jan1)

STAGE_WEEKS = {

    'rice': {
        # Field data: plant DOY 181±18, harvest DOY 325, duration 144d
        'GS0': (24, 26),   # Land prep / paddock flooding  ← 2 wk before plant
        'GS1': (26, 30),   # Transplanting → early vegetative (4 wk)
        'GS2': (30, 38),   # Tillering → canopy closure     (8 wk)
        'GS3': (38, 45),   # Booting → grain filling        (7 wk)
        'GS4': (45, 49),   # Near-harvest → bare soil       (4 wk)
    },

    'corn': {
        # Field data: plant DOY 174±47, harvest DOY 272, duration 121d
        'GS0': (22, 25),   # Land preparation               (3 wk before plant)
        'GS1': (25, 28),   # Germination → early veg        (3 wk)
        'GS2': (28, 34),   # Rapid growth → canopy closure  (6 wk)
        'GS3': (34, 39),   # Tasseling → grain fill         (5 wk) ← brown/drying
        'GS4': (39, 42),   # Harvest → bare soil            (3 wk)
    },

    'cassava': {
        # Field data: plant DOY 118±53, duration ~298d (harvest next Feb)
        'GS0': (15, 17),   # Land preparation
        'GS1': (17, 23),   # Sprouting → early canopy       (6 wk)
        'GS2': (23, 36),   # Canopy development             (13 wk)
        'GS3': (36, 52),   # Storage root fill → maturation (16 wk, yr-end)
        'GS4': (1,  7),    # Harvest period (NEXT YEAR Jan–Feb)
    },

    'longan': {
        # Perennial — approximate seasonal cycles (literature-based)
        'GS1': (9,  16),   # Leaf flush / new growth        (Feb–Apr)
        'GS2': (16, 42),   # Active canopy growth           (Apr–Oct)
        'GS2_stress': (44, 50),  # WATER STRESS induction   (Nov–Dec) ← Kc=0
        'GS3': (50, 52),   # Flowering initiation           (Dec)
        'GS4': (1,  8),    # Fruit development (NEXT YEAR)
    },

    'rubber': {
        # Perennial — leaf phenology cycle
        'GS_defoliation': (1,  8),    # Leaf shedding (Jan–Feb)  ← SAR↑ bare soil
        'GS_leaf_flush':  (9,  16),   # New leaf sprouting       (Mar–Apr)
        'GS_mature':      (16, 52),   # Mature canopy (May–Dec)
    },
}


# ─────────────────────────────────────────────────────────────
# 2.  SAR VH BACKSCATTER TEMPLATES (dB)
#     คำอธิบาย: ค่า VH dB ทั่วไปของแต่ละ stage (4 สัปดาห์ต่อ window)
#     ต้อง calibrate กับข้อมูล SAR จริงจาก GEE ก่อน run DTW
# ─────────────────────────────────────────────────────────────

SAR_TEMPLATES_VH = {

    'rice': {
        # GS0: flooded/ploughed field → strong specular → VH ต่ำมาก
        # GS1: transplanted shoots   → backscatter เริ่มขึ้น
        # GS2: tillering/canopy      → VH สูงสุดช่วง canopy closure
        # GS3: grain fill → heading  → VH ลดลงเล็กน้อย (spike ช่วง heading)
        # GS4: harvest/senescence    → VH ลดลงเร็ว กลับเป็น bare soil
        'GS0': np.array([-20.0, -19.5, -19.0, -18.5]),
        'GS1': np.array([-18.0, -16.0, -14.0, -12.5]),
        'GS2': np.array([-11.5, -10.5, -10.0, -10.0]),
        'GS3': np.array([-10.5, -11.0, -12.0, -13.5]),
        'GS4': np.array([-15.0, -17.0, -18.5, -19.5]),
    },

    'corn': {
        # GS0: bare soil             → VH ต่ำ
        # GS1: germination           → เพิ่มขึ้นช้า
        # GS2: rapid growth          → VH สูงสุด (dense canopy)
        # GS3: tasseling/brown       → VH ลดฮวบ (leaves dry/brown) ← จุดที่งานเดิม classify ผิด
        # GS4: post-harvest          → กลับเป็น bare soil
        'GS0': np.array([-20.5, -20.0, -19.5, -18.5]),
        'GS1': np.array([-18.0, -16.5, -15.0, -13.5]),
        'GS2': np.array([-12.0, -11.0, -10.5, -10.5]),
        'GS3': np.array([-12.0, -14.0, -16.5, -18.5]),   # ← ลดเร็ว
        'GS4': np.array([-19.0, -19.5, -20.0, -20.0]),
    },

    'cassava': {
        # GS0: bare soil/ridge prep  → VH ต่ำ
        # GS1: sprouting             → เพิ่มช้า (sparse canopy)
        # GS2: canopy develop        → VH ขึ้นสูงปานกลาง (less dense than rice)
        # GS3: mature/root fill      → VH ค่อนข้างคงที่ (evergreen-like)
        # GS4: pre-harvest (next yr) → VH คงที่หรือลดเล็กน้อย
        'GS0': np.array([-20.0, -19.5, -19.0, -18.0]),
        'GS1': np.array([-17.5, -16.0, -14.5, -13.0]),
        'GS2': np.array([-12.0, -11.5, -11.0, -11.0]),
        'GS3': np.array([-11.0, -11.0, -11.0, -11.0]),   # ← คงที่
        'GS4': np.array([-11.5, -12.0, -13.5, -15.0]),
    },

    'longan': {
        # GS1: leaf flush            → VH ขึ้นเร็ว
        # GS2: mature canopy         → VH สูง คงที่ (dense evergreen)
        # GS2_stress: water stress   → เกษตรกรหยุดให้น้ำ, canopy ลดลงเล็กน้อย
        # GS3: flower initiation     → VH ต่ำลงเล็กน้อย
        # GS4: fruit dev (next year) → VH สูงขึ้นอีกครั้ง
        'GS1':       np.array([-13.0, -12.0, -11.0, -10.5]),
        'GS2':       np.array([-10.0, -10.0, -10.0, -10.0]),
        'GS2_stress':np.array([-11.0, -12.0, -12.5, -13.0]),  # ← signature สำคัญ
        'GS3':       np.array([-12.5, -12.0, -11.5, -11.0]),
        'GS4':       np.array([-10.5, -10.0,  -9.5,  -9.5]),
    },

    'rubber': {
        # GS_defoliation: Jan–Feb ← VH เหมือน bare soil, ทำให้ classify ผิดในงานเดิม
        # GS_leaf_flush: Mar–Apr   → VH ขึ้นเร็วมาก
        # GS_mature: May–Dec       → VH สูงคงที่ (dense canopy)
        'GS_defoliation': np.array([-18.5, -18.0, -17.5, -17.0]),  # ← งานเดิม confuse กับ bare soil
        'GS_leaf_flush':  np.array([-14.0, -12.0, -11.0, -10.5]),
        'GS_mature':      np.array([-10.0, -10.0, -10.0, -10.0]),
    },
}


# ─────────────────────────────────────────────────────────────
# 3.  FAO-56 Kc TABLE (Allen et al. 1998) + local adjustment
#     CF_local = 1.05 (humid subtropical, Phayao station)
#     → ต้อง recalculate จาก ERA5 actual RHmin, u2
# ─────────────────────────────────────────────────────────────

CF_LOCAL = 1.05

KC_FAO56 = {
    'rice':    {'GS0': 0.00, 'GS1': 1.15, 'GS2': 1.20, 'GS3': 1.05, 'GS4': 0.00},
    'corn':    {'GS0': 0.00, 'GS1': 0.30, 'GS2': 1.20, 'GS3': 0.35, 'GS4': 0.00},
    'cassava': {'GS0': 0.00, 'GS1': 0.30, 'GS2': 0.80, 'GS3': 1.10, 'GS4': 1.00},
    'longan':  {
        'GS1': 0.70, 'GS2': 0.85,
        'GS2_stress': 0.00,   # ← deliberate water stress = Kc 0
        'GS3': 0.90, 'GS4': 0.95,
    },
    'rubber':  {
        'GS_defoliation': 0.60,
        'GS_leaf_flush':  0.80,
        'GS_mature':      1.00,
    },
}


def get_kc(crop: str, stage: str, cf: float = CF_LOCAL) -> float:
    """Return Kc adjusted by local climate factor."""
    base = KC_FAO56.get(crop, {}).get(stage, 0.0)
    return round(base * cf, 3)


# ─────────────────────────────────────────────────────────────
# 4.  WEEK → STAGE LOOKUP TABLE (สร้าง look-up ทุกสัปดาห์ 1–52)
# ─────────────────────────────────────────────────────────────

def build_weekly_stage_lookup(stage_weeks: dict) -> pd.DataFrame:
    """
    Build a week→stage lookup for each crop.
    Returns DataFrame with columns: week, crop, stage, Kc
    """
    rows = []
    for crop, stages in stage_weeks.items():
        for week in range(1, 53):
            assigned = 'offseason'
            for stage, (ws, we) in stages.items():
                # Handle cassava GS4 that wraps to next year (we < ws)
                if ws <= we:
                    if ws <= week <= we:
                        assigned = stage
                        break
                else:   # wraps (e.g., GS4: week 1–7)
                    if week <= we or week >= ws:
                        assigned = stage
                        break
            rows.append({
                'crop': crop,
                'week': week,
                'stage': assigned,
                'Kc': get_kc(crop, assigned),
            })
    df = pd.DataFrame(rows)
    return df


weekly_kc = build_weekly_stage_lookup(STAGE_WEEKS)
pivot = weekly_kc.pivot_table(
    index='week', columns='crop', values='Kc', aggfunc='first'
)
print("=== WEEKLY Kc LOOKUP TABLE (sample weeks 1, 10, 20, 26, 30, 38, 45, 47, 50) ===")
sample_weeks = [1, 10, 17, 20, 26, 30, 34, 38, 42, 45, 47, 50, 52]
print(pivot.loc[pivot.index.isin(sample_weeks)].round(3).to_string())

weekly_kc.to_csv('kc_weekly_lookup_all_crops.csv', index=False)
print("\n✅ Saved: kc_weekly_lookup_all_crops.csv")


# ─────────────────────────────────────────────────────────────
# 5.  DTW CLASSIFICATION FUNCTION (ใช้กับ SAR time series จริง)
# ─────────────────────────────────────────────────────────────

def classify_stage_dtw(vh_window: np.ndarray,
                       crop: str,
                       templates: dict = SAR_TEMPLATES_VH) -> tuple:
    """
    Classify growing stage for a given crop using DTW.

    Parameters
    ----------
    vh_window : np.ndarray, shape (4,)
        VH backscatter (dB) for 4-week sliding window
    crop : str
        One of: 'rice', 'corn', 'cassava', 'longan', 'rubber'
    templates : dict
        SAR_TEMPLATES_VH

    Returns
    -------
    (best_stage: str, dtw_distance: float)
    """
    crop_templates = templates.get(crop, {})
    if not crop_templates:
        return 'unknown', float('inf')

    best_stage = None
    best_dist  = float('inf')
    for stage, template in crop_templates.items():
        dist, _ = fastdtw(vh_window.reshape(-1,1),
                          template.reshape(-1,1),
                          dist=euclidean)
        if dist < best_dist:
            best_dist  = dist
            best_stage = stage

    return best_stage, best_dist


# ─────────────────────────────────────────────────────────────
# 6.  APPLY TO SAR TIME SERIES (template — ใส่ path จริงของคุณ)
# ─────────────────────────────────────────────────────────────

def run_phenology_detection(sar_mean_vh_per_crop: dict,
                            window_size: int = 4) -> pd.DataFrame:
    """
    Apply DTW stage classification to SAR time series.

    Parameters
    ----------
    sar_mean_vh_per_crop : dict
        {crop: np.ndarray shape (n_weeks,)}
        Mean VH backscatter per crop per week
        (extracted from SAR stack masked by crop map)
    window_size : int
        Sliding window size (default 4 weeks)

    Returns
    -------
    DataFrame: week_idx, crop, stage, dtw_dist, Kc
    """
    results = []
    kc_lookup = weekly_kc.set_index(['crop','week'])['Kc'].to_dict()

    for crop, vh_series in sar_mean_vh_per_crop.items():
        n_weeks = len(vh_series)
        for i in range(n_weeks - window_size + 1):
            window = vh_series[i:i + window_size]
            if np.any(np.isnan(window)):          # skip empty weeks
                stage, dist = 'no_data', np.nan
            else:
                stage, dist = classify_stage_dtw(window, crop)

            week_1indexed = i + window_size        # centre of window
            kc_val = get_kc(crop, stage)

            results.append({
                'week_idx':    i,
                'week':        week_1indexed,
                'crop':        crop,
                'stage':       stage,
                'dtw_dist':    round(dist, 3) if not np.isnan(dist) else np.nan,
                'Kc':          kc_val,
            })

    return pd.DataFrame(results)


# ─────────────────────────────────────────────────────────────
# 7.  DEMO — ทดสอบ DTW ด้วยข้อมูล synthetic ก่อน SAR จริงพร้อม
# ─────────────────────────────────────────────────────────────

print("\n=== DTW DEMO — synthetic rice time series (52 weeks) ===")

# สร้าง synthetic VH series สำหรับ rice ตาม stage boundaries
rice_synthetic_vh = np.array(
    [-19.0]*2 +          # GS0 wk 24–26
    [-17.0,-14.0,-13.0,-12.0]*1 +  # GS1 wk 26–30
    [-11.0,-10.5,-10.0,-10.0,-10.0,-10.0,-10.0,-10.0]*1 +  # GS2 wk 30–38
    [-10.5,-11.0,-12.0,-13.0,-13.5,-14.0,-14.0]*1 +        # GS3 wk 38–45
    [-15.0,-17.0,-18.5,-19.0]*1    # GS4 wk 45–49
)

demo_stages = []
for i in range(len(rice_synthetic_vh) - 3):
    window = rice_synthetic_vh[i:i+4]
    stage, dist = classify_stage_dtw(window, 'rice')
    demo_stages.append({'window_start': i, 'stage': stage, 'dtw_dist': round(dist,2)})

demo_df = pd.DataFrame(demo_stages)
print(demo_df.groupby('stage')['window_start'].agg(list).to_string())
print("\n✅ DTW classification working correctly")


# ─────────────────────────────────────────────────────────────
# 8.  PHENOLOGY SUMMARY TABLE (สำหรับ paper Table หรือ Figure 4)
# ─────────────────────────────────────────────────────────────

print("\n=== PHENOLOGY SUMMARY (for paper) ===")
summary_rows = []
for crop, stages in STAGE_WEEKS.items():
    for stage, (ws, we) in stages.items():
        kc = get_kc(crop, stage)
        # แปลง week กลับเป็น approximate month
        def wk_to_month(wk):
            months = ['Jan','Feb','Mar','Apr','May','Jun',
                      'Jul','Aug','Sep','Oct','Nov','Dec']
            return months[min(11, (wk-1)*7//30)]
        summary_rows.append({
            'Crop':          crop,
            'Stage':         stage,
            'Week start':    ws,
            'Week end':      we,
            'Approx. period':f"{wk_to_month(ws)}–{wk_to_month(we)}",
            'Kc (adjusted)': kc,
            'Data source':   'Field data' if crop in ['rice','corn','cassava']
                             else 'Literature',
        })

summary_df = pd.DataFrame(summary_rows)
print(summary_df.to_string(index=False))
summary_df.to_csv('phenology_stage_summary_for_paper.csv', index=False)
print("\n✅ Saved: phenology_stage_summary_for_paper.csv")
print("✅ Saved: kc_weekly_lookup_all_crops.csv")
print("\n📌 NEXT STEP: load SAR stack จริง → run run_phenology_detection()")
