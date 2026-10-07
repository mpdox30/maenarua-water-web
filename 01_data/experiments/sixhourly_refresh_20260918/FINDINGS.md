# sixhourly_refresh_20260918 — Findings

**Goal (user request, 2026-09-18):** rebuild a 6-hourly training dataset from ALL raw
sub-daily sources available today (a prior 2026-07-31 study, `hourly_feasibility_20260731/`,
found 6-hourly was the noise floor but lost to daily at every horizon), then retrain
every model family tried so far, fully tuned, and compare all results.

## 1. Extended dataset

Stitched 3 raw sources not all available/used in the prior study:
- `Raw Data_RES002 station.xlsx` (hourly, 2025-06-26 → 2026-06-27)
- `WMB_Phayao/01_raw_data/Reservoirs/RES002 July.csv` (10-min, fills 2026-06-27→07-06)
- `WMB_Phayao/09_live/data/api_snapshots.csv` (the live `gdrive_log` telemetry store,
  10-min nominal, 2026-07-10 → today, actively growing)

Reused the exact water-balance formula from `build_6hourly_training.py` (MA-6h trailing
smoothed level, non-linear spillway weir formula on raw hourly levels, same
RELEASE_EVENTS timeline, same evap/infiltration ÷4 approximation, same sensor-glitch
plausibility band 487.5–491.0 m). Result: **1,772 six-hourly rows, 98.7% coverage of
possible marks**, 2025-06-27 → 2026-09-18 (vs. 1,537 rows through 2026-07-31 previously)
— now includes the full September flood event (peak %Full_t = 111.1% at 6h resolution,
vs. 108.1% at daily resolution — finer sampling caught a higher true instantaneous peak).
After adding lag/rolling features + 12 targets (6h→72h ahead): **1,730 usable rows**.
Files: `Training_6hourly_raw_extended_20260918.csv`, `Training_6hourly_full_extended_20260918.csv`.

## 2. Training + tuning methodology

No live forecast log exists at 6-hourly resolution (it was never deployed), so — unlike
the daily investigation — there is no external "honest holdout" to check against. Used
the strictest self-contained substitute: tuned every model (Optuna, inner 5-fold
TimeSeriesSplit CV) on the first 85% chronologically (1,460 rows, through 2026-07-13),
then evaluated ONCE on the last 15% (258 rows, 2026-07-13 → 2026-09-15) — a block that
happens to include the full flood event, never touched during tuning.

Models tried, all newly tuned on this dataset: **CatBoost direct delta-regression,
CatBoost 2-stage hurdle (classifier gate + regressor, first time with lag/rolling
features), LightGBM, XGBoost, RandomForest, Ridge** — the same 6 families tried on the
daily dataset earlier today.

## 3. Results — every model beats 6-hourly persistence at every horizon except Ridge

| H | lead | persistence | CatBoost_direct | CatBoost_hurdle | LightGBM | XGBoost | RandomForest | Ridge |
|---|---|---|---|---|---|---|---|---|
| 1 | 6h | 0.644 | 0.686 | **0.724** | 0.701 | 0.698 | 0.619 | 0.697 |
| 2 | 12h | 0.528 | 0.571 | **0.647** | 0.584 | 0.570 | 0.552 | 0.507 |
| 3 | 18h | 0.511 | 0.534 | 0.561 | **0.579** | 0.578 | 0.527 | 0.349 |
| 4 | 24h | 0.560 | 0.563 | 0.585 | 0.597 | **0.621** | 0.568 | 0.350 |
| 5 | 30h | 0.394 | 0.435 | 0.447 | 0.445 | **0.469** | 0.400 | 0.198 |
| 6 | 36h | 0.231 | 0.309 | **0.382** | 0.364 | 0.319 | 0.270 | 0.110 |
| 7 | 42h | 0.170 | 0.268 | 0.324 | 0.292 | **0.328** | 0.255 | 0.032 |
| 8 | 48h | 0.153 | 0.256 | 0.286 | 0.324 | **0.357** | 0.292 | 0.022 |
| 9 | 54h | -0.015 | 0.101 | 0.160 | 0.139 | **0.246** | 0.170 | -0.073 |
| 10 | 60h | -0.164 | 0.042 | 0.072 | 0.096 | **0.119** | 0.078 | -0.079 |
| 11 | 66h | -0.217 | -0.001 | 0.071 | 0.068 | **0.078** | -0.007 | -0.083 |
| 12 | 72h | -0.171 | 0.070 | 0.080 | **0.156** | 0.140 | 0.074 | -0.020 |

XGBoost is the most consistent top performer (best or near-best at H4-H11); CatBoost
hurdle wins the shortest horizons (H1/H2/H6). Full CSV: `sixhourly_master_comparison.csv`.

## 4. Comparison against the daily production model at matched real lead times

This is the headline result the user cares about — same calendar lead time, daily vs.
6-hourly (using each side's honest/held-out evaluation from today's investigations):

| Lead time | Daily model (deployed, real live-log holdout) | Best 6-hourly model (self-holdout) |
|---|---|---|
| 24h | 0.563 | **0.621 (XGBoost)** |
| 48h | 0.285 | **0.357 (XGBoost)** |
| 72h | 0.015 | **0.156 (LightGBM)** |

**At matched lead times, the best-tuned 6-hourly models now beat the daily production
model** — the opposite conclusion from the 2026-07-31 study. Plus 6-hourly offers 9
additional forecast checkpoints (6h, 12h, 18h, 30h, 36h, 42h, 54h, 60h, 66h) the daily
model cannot produce at all, several of which (6h-36h) are the strongest NSE values seen
anywhere in this entire day's investigation (up to 0.72).

## 5. Why this reverses the July conclusion, and important caveats

Likely reasons the conclusion flipped: (a) 1,730 vs 1,537 usable rows, including a full
real flood event the July dataset never saw at all; (b) proper per-model Optuna tuning
across 6 families this time vs. a single CatBoost configuration in July; (c) the 2-stage
hurdle and boosted-tree models specifically seem to benefit from the added flood-event
contrast (echoes the RandomForest finding in the daily investigation: models that can
react to rapid escalation do better when the evaluation window includes one).

**Caveats before trusting this over the daily model:**
- This is a **self-contained chronological holdout**, not a real deployed/live-logged
  prediction stream like the daily model's `forecast_accuracy_log.csv`. It's legitimate
  (never touched by tuning) but weaker evidence than genuinely blind real-time logging.
- The 6-hourly Q_in values are **derived** via the water-balance formula with several
  approximations that compound at finer resolution (evap/infiltration split ÷4 assuming
  a constant rate through the day; a manually-reconstructed multi-event release timeline)
  — these are NOT the audited official ledger numbers the daily model trains on directly.
- Both the 6-hourly holdout and the daily model's real holdout window overlap the same
  September flood event, so neither comparison is fully independent of "did this
  particular event help."
- This project has reversed CV-looked-good findings 5 times already today across both
  investigations. A result this uniformly positive (5 of 6 model families beating
  persistence at literally every horizon) is unusual enough to warrant real-world
  shadow-testing before trusting it as strongly as the table above suggests.

## 6. Recommendation

Most promising outcome of the entire day's work. Before considering deployment: (1) get
a second, cleaner holdout by waiting for the 6-hourly dataset to accumulate real new
data past today and re-checking, since the current holdout's flood event is also visible
during tuning-block feature history (lag features from the tail of the fit block do see
early flood onset); (2) if this holds up, XGBoost (mid-long horizons) + CatBoost hurdle
(short horizons) is the combination to pursue; (3) building a live 6-hourly deployment
would require wiring `api_snapshots.csv`/gdrive_log into the daily pipeline as a new,
faster-cadence data source — a real engineering task not yet scoped.

## 7. Shadow-test deployment + a real data bug found and fixed (2026-09-18, later same day)

User chose to shadow-test for 1 month before any real deployment decision. Built:
`shadow_predict.py` (self-contained — downloads the `raw_log` gdrive sheet directly by
its file_id over HTTPS, no dependency on `api_snapshots.csv`, Google Drive Desktop,
Colab, or `daily_update.py`; backfills every unlogged 6h mark since the last run so PC-off
gaps self-heal), `train_final_shadow_models.py` (freezes one model per horizon per
§3's best-family table, trained once on all data through deployment, not retrained per
run), `score_shadow.py` (reconciles logged predictions against reality once available),
and `run_shadow_predict.bat` + Task Scheduler instructions (4x/day, 30 min after each
6h mark). `DEPLOY_START_MARK = 2026-09-18 07:00` — the shadow log only ever contains
marks at/after this point, specifically to avoid ever scoring the models against rows
they were trained on (an early test run that backfilled the *entire* history had to be
discarded for exactly this reason).

**While validating the shadow-test ground truth against the official daily ledger
(`2026_September_MNR.xlsx`), found and fixed a real bug**, not a resolution artifact:

- `RELEASE_EVENTS`'s current-year entry was a guess (copied last year's 26 Jun–14 Oct
  pattern) and was flagged as such in the code from the start. The user supplied the
  authoritative release log
  (`ตารางเก็บข้อมูลการจ่ายน้ำของอ่างเก็บน้ำ.xlsx`): the real 2026 event is **29 Jun – 4 Aug
  2026**, closing over 2 months earlier than assumed. From 2026-08-04 through deployment,
  the old formula silently added a phantom ~9,446 m³/day of "release" into every day's
  Q_in — including the entire September flood window used for both training and the
  original §3–4 comparison. Two more real events the old list never had at all (21–27 Mar,
  15–18 Jun 2026) were also added. Fixed in both `build_6hourly_extended.py` and
  `shadow_predict.py`.
- Separately (see reconciliation below): a **day-labeling bug in the validation script
  itself** (not the training data) made the original per-day comparison against the
  official ledger look far worse than reality — the official ledger's "day N" row is the
  24h window *ending* at 07:00 on day N, not *starting* there. Once corrected, the 6-hourly
  water-balance recompute tracks the official ledger to within **0.6–5% on every flood day
  (10–17 Sep)**, not the 13–86% originally reported. This was purely a bug in how this
  investigation checked its own work — it does not touch the training data or models.

**Rebuilt the dataset and retrained everything (release-event fix only; the day-labeling
fix needed no data change) — the core conclusion is essentially unchanged:**

| H | lead | persistence | CatBoost_direct | CatBoost_hurdle | LightGBM | XGBoost | RandomForest | Ridge |
|---|---|---|---|---|---|---|---|---|
| 1 | 6h | 0.650 | 0.687 | **0.745** | 0.709 | 0.707 | 0.632 | 0.702 |
| 2 | 12h | 0.538 | 0.570 | **0.643** | 0.595 | 0.579 | 0.560 | 0.512 |
| 3 | 18h | 0.512 | 0.542 | 0.581 | 0.571 | **0.580** | 0.527 | 0.353 |
| 4 | 24h | 0.551 | 0.554 | 0.575 | 0.586 | **0.613** | 0.560 | 0.355 |
| 5 | 30h | 0.390 | 0.430 | 0.449 | 0.433 | **0.466** | 0.400 | 0.203 |
| 6 | 36h | 0.229 | 0.295 | **0.368** | 0.372 | 0.320 | 0.282 | 0.117 |
| 7 | 42h | 0.160 | 0.226 | 0.284 | 0.294 | **0.333** | 0.257 | 0.041 |
| 8 | 48h | 0.130 | 0.135 | 0.296 | 0.302 | **0.341** | 0.277 | 0.033 |
| 9 | 54h | -0.034 | 0.128 | 0.148 | 0.143 | **0.238** | 0.158 | -0.062 |
| 10 | 60h | -0.179 | 0.035 | 0.057 | 0.086 | **0.110** | 0.071 | -0.066 |
| 11 | 66h | -0.238 | 0.015 | 0.028 | 0.051 | **0.066** | -0.021 | -0.069 |
| 12 | 72h | -0.202 | -0.034 | 0.061 | 0.137 | 0.119 | 0.054 | -0.006 |

Matched-lead-time vs. daily production is unchanged in conclusion: 24h XGBoost 0.613 vs
daily 0.563; 48h XGBoost 0.341 vs daily 0.285; 72h LightGBM 0.137 vs daily 0.015 — 6-hourly
still wins at all three. Full CSV: `sixhourly_master_comparison.csv` (pre-fix version kept
at `sixhourly_master_comparison_ORIGINAL_pre_release_fix.csv` for the audit trail; same
for `shadow_models_ORIGINAL_pre_release_fix/` and
`Training_6hourly_full_extended_20260918_ORIGINAL_pre_release_fix.csv`). The 12 frozen
`shadow_models/` were retrained on the corrected data before the shadow-test's first real
log entry was written, so the shadow test never ran on the buggy models at all.

**~~Still-open puzzle~~ RESOLVED (2026-09-25, during the NSE-improvement follow-up below):**
a handful of near-zero/dry days (1, 2, 4, 6 Sep) had shown large *relative* errors against
the official ledger (e.g. day 6: 405 m³ official vs. ~23,000 recomputed). Traced directly
from `RES002_New/RES002.csv` hourly telemetry: **it was a day-window boundary mismatch in
whoever built that original ad-hoc comparison (script not saved, see below), not a rain-
source or R-term data quality issue** — the same *class* of bug as the day-labeling bug
found and fixed in §7 below, just never applied to this separate, earlier comparison.
Concretely for day 6: the official ledger's "day 6" row uses the correct
07:00-anchored window (07:00 Sep 5 → 07:00 Sep 6) — real hourly level over that exact
window is flat (488.239 → 488.234 m, Δstorage ≈ 0), so the official ledger's near-zero
Inflow (405 m³) for day 6 was **correct all along**. The big rain event people were seeing
started right at ~08:00-10:00 Sep 6 (level spikes to 488.64 m by 10:00) and is entirely
captured — correctly, with no anomaly — in the official ledger's **day 7** row (ΔS
+60,204 m³, Inflow 61,302 m³). Recomputing day 6 with a naive **midnight-anchored
calendar-day window** instead (00:00→24:00 Sep 6, i.e. the boundary mistake) pulls that
same rain event's storage rise into "day 6" instead: Δstorage ≈ +54,457 m³, implied
inflow ≈ +55,548 m³ — same order of magnitude and direction as the ~23,000 m³ figure
originally reported (exact value differs since Evap/Infiltration/rain weren't
recalculated for the shifted window in this quick check), confirming the mechanism.
Days 1/2/4 show small level *declines* in the correct 07:00-anchored window (-0.05 to
-0.09 m) — consistent with the official ledger's near-zero Inflow being right for those
too; their large *relative* error is just the usual artifact of dividing by a
near-zero denominator, not a separate issue. **No fix needed in the current pipeline** —
`build_6hourly_extended.py`/`shadow_predict.py` already use the correct 07:00-anchored
`MARK_HOURS` convention throughout; this was only ever a bug in one earlier, unsaved,
one-off validation script. Confirms (again) this project's recurring lesson: check
day/window boundary conventions before trusting any official-vs-recompute delta, however
large it looks in percentage terms.

## 6. 2026-09-25 — spillway formula corrected (constant-Cd → critical-flow+friction), shadow-test replaced

Separate investigation (`WMB_Phayao/Spillway_check/`) found the spillway weir formula used
everywhere in this project (`Q = C·L·H^1.5`, `C=1.82` constant) implies `Cd ≈ 1.07` at this
site's very-low `H/b` regime (H/b = 0.02–0.04, well outside the standard broad-crested-weir
valid range of 0.08–0.33) — physically impossible for a real crest with friction (`Cd` must
be `< 1`). No verified `Cd(H/b)` empirical curve exists in the literature for `H/b` this
low from a single clean source, so per user decision (2026-09-25) replaced it with a
critical-flow + Manning-friction model (long-throated-flume method, USBR/Bos) instead of an
empirical fit: solves critical depth at the downstream end of the crest, walks the energy
equation upstream with Manning friction loss (`n=0.017` central estimate, crest length
`b=10.0 m` from independent satellite-imagery + RTK-survey cross-checks). Full derivation
and code: `Spillway_check/03_experiment/weir_friction_model.py`. Result: **~26–28% lower
total Spill** on independent hourly telemetry cross-validated two ways (original + a second
independent `RES002_New` source), and **~17.6% lower total 6-hourly Q_in dataset-wide**
(222/1,772 marks changed, concentrated on spill days).

Backtested old-vs-corrected labels on both the daily production model (full notebook
retrain, all 3 families + Optuna) and this 6-hourly model (same honest holdout as section 3
above): corrected labels improved Hurdle_NSE at 4/7 daily horizons (especially H5–H7,
long-lead) and improved "skill over persistence" at **all 12** 6-hourly horizons (raw NSE
looks lower across the board post-correction, but that's because correcting spill-day
peaks shrinks the target's own variance — persistence's NSE drops by nearly the same
amount, so the model's actual edge over naive persistence grew everywhere, most at H9–H12).

User instruction: replace this shadow-test with the corrected version (not just re-run it
alongside). Found and fixed a second-order issue during this: `shadow_predict.py` computes
`Q_in_t` **live** from raw hourly levels every 6h run (not from the training CSV) using its
own embedded copy of the spillway formula — swapping only the frozen models would have left
a train/inference skew (models trained on corrected labels fed features from the old
formula), the same class of bug as the RELEASE_EVENTS issue in section 4. Fixed by
replacing the embedded formula in `shadow_predict.py` with a precomputed
`(head → q_per_m)` lookup table (`spillway_friction_curve_n017.csv`, interpolated with
`numpy.interp` — no new runtime dependency for the unattended Task Scheduler job) built
from the same `weir_friction_model.py`. Also patched `build_6hourly_extended.py` (the
from-scratch training-set builder) the same way, so any future re-extension of the dataset
stays consistent. `BEST_FAMILY` per horizon was recomputed from a fresh honest-holdout
comparison on the corrected data (restricted to the 3 families `train_final_shadow_models.py`
supports: CatBoost_hurdle/LightGBM/XGBoost) — H4, H5 moved XGBoost→LightGBM; H7 moved
CatBoost_hurdle→XGBoost; H10, H11 moved XGBoost→CatBoost_hurdle; H12 moved LightGBM→XGBoost.
New frozen models trained the same way as section 4 (Optuna N_TRIALS=12, inner 5-fold
TimeSeriesSplit CV, full-data final fit) — see
`Spillway_check/06_ri_6h_experiment/train_final_shadow_models_CORRECTED.py`.

**Everything from before this fix is preserved, not deleted**, suffixed
`_PRE_SPILLWAY_FIX_20260925`: `shadow_models_PRE_SPILLWAY_FIX_20260925/`,
`shadow_predict_PRE_SPILLWAY_FIX_20260925.py`,
`build_6hourly_extended_PRE_SPILLWAY_FIX_20260925.py`,
`Training_6hourly_full_extended_20260918_PRE_SPILLWAY_FIX_20260925.csv`,
`shadow_predictions_log_PRE_SPILLWAY_FIX_20260925.csv`,
`shadow_scoring_report_PRE_SPILLWAY_FIX_20260925.csv`. The live prediction log/scoring
report were reset to empty (not merged) so the corrected models' real-world track record
isn't mixed with the old models' — `shadow_predict.py`'s existing backfill logic will
retroactively re-log every 6h mark from `DEPLOY_START_MARK` (2026-09-18 07:00, unchanged —
still outside every horizon's corrected training window) forward on its next scheduled run,
so the full shadow-test window gets rebuilt cleanly under the corrected methodology with no
gap. Does not touch the live daily production pipeline.

**Backfill note (same day):** the user noticed the live `wide_log` Google Sheet tab was
visibly missing 2026-09-14→09-20 (likely `archive_telemetry_monthly.gs` pruning old rows out
of the live tab) and asked to patch around it for the re-baseline run. Investigation found
this wasn't actually a problem: `shadow_gdrive_raw_store.csv` (the script's own local
accumulating cache, separate from the live Sheet, built up from each 6-hourly run's download
since 2026-09-18) already had that period fully cached from before the Sheet was pruned —
confirmed gap-free (max gap 30 min) for all of 2026-09-13→09-25. Ran the new `shadow_predict.py`
directly (sandbox has no outbound internet, so the live download failed and it fell back to
the local cache exactly as designed — no crash, no data loss) and it backfilled all 29 marks
from `DEPLOY_START_MARK` through 2026-09-25 07:00 with no gap, using the corrected models. Ran
`score_shadow.py` immediately after: **the corrected models already beat persistence on both
NSE and MAE at every single horizon (H1–H12)** on this first real-world scoring pass (270
scored pairs) — a clear improvement over the pre-fix shadow-test's real-world numbers, which
were deeply negative NSE at most horizons (see section 5). Still very early (n=17–28 per
horizon, longer horizons barely past their first few scored pairs) — not a final verdict, but
a good sign. `shadow_gdrive_raw_store.csv` was left untouched (the script only rewrites it on
a successful download, never on fallback), so the next real Task Scheduler run on the user's
PC (with real internet) will pick up fresh telemetry normally.

## 7. 2026-09-30 — status check, 12 days into the corrected shadow-test

Windows Task Scheduler has been running `shadow_predict.py` on schedule since the 2026-09-25
swap — `shadow_gdrive_raw_store.csv` and `shadow_predictions_log.csv` both show live updates
through 2026-09-30 08:55, no gaps, 49 issued-at marks logged (2026-09-18 07:00 →
2026-09-30 07:00 — the pre-swap marks were re-logged cleanly under the corrected models per
the backfill note above). Family assignment in the log matches the deployed `BEST_FAMILY` dict
exactly at every horizon (H1/H2/H6/H10/H11 → CatBoost_hurdle, H3/H4/H5 → LightGBM, H7/H8/H9/H12
→ XGBoost) — no drift.

Re-ran `score_shadow.py` fresh (510 scored pairs now vs. 270 on 09-25, 78 still pending at the
long horizons):

```
 H  lead_hours  n  model_nse  persistence_nse  model_mae  persistence_mae
 1           6 48      0.775            0.693     9587.7          12306.3
 2          12 47      0.479            0.348    14260.5          20187.5
 3          18 46      0.381            0.184    19376.1          25248.9
 4          24 45      0.221           -0.001    23782.7          29822.1
 5          30 44      0.067           -0.185    26979.0          34182.6
 6          36 43     -0.179           -0.319    29449.7          37671.4
 7          42 42     -0.142           -0.394    35153.1          39650.6
 8          48 41     -0.146           -0.371    36596.4          40671.1
 9          54 40     -0.187           -0.448    37848.5          43333.7
10          60 39     -0.357           -0.760    35850.0          46293.8
11          66 38     -0.498           -0.952    38743.5          47346.2
12          72 37     -0.308           -1.563    30919.7          44267.0
```

Holding up well after 5 extra days of real data: model still beats persistence on both NSE and
MAE at **every single horizon H1–H12**, and H1's NSE improved further (0.654→0.775 vs. the
09-25 first-pass numbers). H1–H5 have genuinely positive absolute NSE (real predictive skill,
not just "less bad than persistence"); H6–H12 are still negative in absolute terms (as expected
for a small, young dataset at long lead times — consistent with the walk-forward CV findings in
section 6.x that flagged these horizons as unstable) but consistently less negative than
persistence, so the shadow-test's core claim (correcting the spillway formula improves the
model) continues to hold up under real, out-of-sample data. No action needed — keep letting it
accumulate; H9–H12 need more weeks before their NSE estimates are trustworthy at all (n=37–40
scored pairs only).


## 2026-10-06 — เพิ่มตัวกรอง spike ระดับน้ำ (`spike_filter.py`) ใน `shadow_predict.py`

- เปิดเป็นค่า default, ปิดได้ด้วย env `SHADOW_DESPIKE=0` (สำเนาก่อนแก้: `shadow_predict_PRE_DESPIKE_20261006.py`)
- กรองเฉพาะกริดชั่วโมงในหน่วยความจำ ไม่แก้ข้อมูลดิบ/store และไม่แตะ frozen models
- ตรวจกับประวัติทั้งหมด (1,841 แถว 6 ชม.): พบ 22 เหตุการณ์ ทั้งหมดอยู่ใน 10 ส.ค.–6 ก.ย. 2569, ครอบคลุม 18/18 หน้าต่างที่ติด flag, ไม่แตะพายุ 5 ต.ค. เลย (ระดับ > สันฝาย + มีฝน), แถวที่ Q_in เปลี่ยน 31 แถว, ยอด Q_in รวมลด 3.3%
- ขั้น HOLD (ค้างค่าเดิม <= 6 ชม. ให้ jump >= 0.25 ม./ชม. ที่ไม่มีฝน): replay ทีละชั่วโมงบนประวัติ trigger 6 ครั้ง ทั้งหมดเป็น spike จริงที่ยืนยันย้อนหลัง ไม่มี false hold
- ข้อจำกัด: frozen models ถูกเทรนด้วยข้อมูลที่ยังมี spike (ถึง 18 ก.ย.) -- ควรสร้าง training set ใหม่ด้วยกริดที่กรองแล้วก่อน retrain; ตัวกรองไม่จับ bump ที่ไม่ย้อนกลับภายใน 8 ชม. หรือที่เกิดตอนระดับเหนือสันฝาย
