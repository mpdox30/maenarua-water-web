# retrain_refresh_20260918 — Findings

**Goal (user request, 2026-09-18):** rebuild the Reservoir Inflow training dataset with
all data through today, re-try the original 2-stage ("hurdle") architecture plus new
features, tune hyperparameters, and try to get H1-H3 to "high confidence" (currently
low_confidence at H1/H3, borderline at H2 per `latest.json`).

## 1. Dataset refresh (DONE — verified)

Rebuilt `Training_Values_Nofct_7day_Extended_lagfeat.csv`'s lineage using the EXACT
formulas from `data_pipeline.py::_ri_load_raw_monthly_data()`, applied across the full
raw monthly xlsx history instead of just the last row. Recompute verified byte-accurate
against the existing production CSV for the 391-row overlap (0 mismatches on Q_in_t or
%Full_t). Result:

- **446 rows** (up from 393), 2025-06-29 → 2026-09-17, 439 with all 7 targets present.
- **21 rows recovered purely by the 2026-09-17 gate raise (105%→120%)** — NOT just the
  Sept 2026 flood (11 rows, 2026-09-11..09-16 + the runup on 09-11): the old 105% gate
  had also been silently excluding flood-adjacent rows from **2025-07 (6 rows), 2025-08
  (4 rows), 2025-11 (3 rows), and 2026-05 (2 rows)** — i.e. every flood event in the
  dataset's history, not just the current one.
- Output: `Training_Values_Nofct_7day_Extended_lagfeat_v3_20260918.csv` (this folder).
  Audit columns `is_newly_appended_20260918_refresh` / `recovered_by_gate_raise_105_to_120`
  added; original manual-correction audit columns inherited for the overlap period.

## 2. Retrain: production recipe + 2-stage hurdle on refreshed data

Both retrained with the SAME walk-forward 5-fold TimeSeriesSplit CV methodology the team
has always used for architecture decisions (season-segmented 70/15/15 split, dry window
2026-02-03..2026-05-17). Internal CV-on-training-data numbers looked better than the old
393-row baseline at every horizon (e.g. H1 0.42→0.58). See `retrain_compare_results.csv`.

**This CV improvement did not survive the honest holdout test** (see §4) — a repeat of
the exact pattern this project has hit at least 3 times before (rain-forecast-continuous,
range_24h, log-transform: all looked good on CV, reversed on real holdout).

## 3. Hyperparameter tuning (Optuna) + new features + overfit audit

Per-horizon Optuna search (18 trials × 2 feature sets, inner 5-fold TimeSeriesSplit on
the pre-holdout "fit" block only — holdout never touched by the search):

- **Feature sets tried:** current 12 base features vs. an extended 22-feature set adding
  `Qin_lag3/4`, `Rain_roll10`, `%Full_t` lag1 + 3-day rate-of-change, `DeltaS` 3-day
  rolling mean, day-of-year sin/cos (seasonality), a binary `high_flow_regime` flag
  (`%Full_t > 100`), and a rain-acceleration term. None of these needed external data, so
  all were testable inside this sandbox (unlike the rain-forecast binary feature already
  in production for H3/H6/H7 — see §5, could not be extended here, no internet access).
- **Overfit red-flag audit** (the H5 bug pattern: `random_strength` far below neighbors +
  `tree_count` eating a large share of the iteration cap): re-ran for every horizon with
  a wider `random_strength` search floor (1.0–6.0). **Result: no horizon shows the H5
  pattern any more** — all tree_count/cap ratios ≤0.26, all random_strength ≥1.29. H6/H7
  (flagged as at-risk-but-never-audited in earlier session's history) are clean.
- **Inner-CV-on-fit-block results looked very strong**: H1=0.69, H2=0.59, H3=0.37,
  H4=0.18 (see `tuning_results_with_diagnostics.csv`).

## 4. Honest holdout validation — the decisive test

Same methodology the team has always used for real go/no-go decisions: fit strictly
before 2026-08-22 (65% of known-outcome `forecast_accuracy_log.csv` dates), evaluate on
the never-touched later 35% (2026-08-22→2026-09-16, 19-20 rows/horizon, includes the real
flood event).

| H | deployed (now) | refreshed-data retrain | Optuna-tuned + new feats | naive persistence |
|---|---|---|---|---|
| 1 | +0.563 | +0.571 | **+0.575** | +0.575 |
| 2 | **+0.285** | +0.265 | +0.275 | +0.279 |
| 3 | +0.015 | +0.023 | +0.009 | **+0.021** |
| 4 | **-0.137** | -0.139 | -0.145 | -0.141 |
| 5 | **-0.154** | -0.208 | -0.206 | -0.212 |
| 6 | **-0.311** | -0.334 | -0.347 | -0.348 |
| 7 | **-0.355** | -0.402 | -0.398 | **-0.409** |

**None of the three retrain attempts (more data / 2-stage / Optuna-tuned + new features)
beats naive "tomorrow = today" persistence by a meaningful margin at any horizon**, and
at H2-H7 the currently-deployed model is usually the best or tied-best of the four. The
large apparent gains from inner CV (§2, §3) evaporated on real out-of-sample data —
exactly the failure mode already documented 3 times in this project's history
(`inflow_rain_forecast_feature_20260907`, `inflow_h1h3_features_20260907`,
`inflow_logtransform_20260907`). This is now a 4th independent confirmation, across a
different intervention (dataset refresh + architecture + tuning combined) each time.

## 5. Not done / blocked

- Could not extend `01_data/experiments/inflow_rain_forecast_feature_20260907/rain_forecast_archive_raw.csv`
  (currently only covers through 2026-09-06) through today — this sandbox has no
  internet access to `historical-forecast-api.open-meteo.com` (confirmed: both this
  domain and the live `api.open-meteo.com` returned empty responses). The existing binary
  rain-forecast feature (H3/H6/H7 only) is already in the currently-deployed model; it
  was NOT included in the refreshed/tuned retrain candidates above for this reason, which
  slightly disadvantages them at H3/H6/H7 specifically. To close this gap: run
  `01_fetch_rain_forecast_archive.py` on a machine with internet (same as the original
  run) to extend the archive to today, then re-run this comparison with that feature
  included for all candidates on equal footing.

## 5b. Rain-forecast feature gap closed (2026-09-18, after user ran the archive extension)

User ran `02_extend_rain_forecast_archive.py` on their Windows machine, extending
`rain_forecast_archive_raw.csv` from 2026-09-06 through 2026-09-17 (+88 rows). Re-ran
H3/H6/H7 (the only horizons that use this feature in production) with the SAME
already-validated thresholds (H3=27.3mm, H6=3.1mm, H7=61.0mm) added on equal footing:

| H | deployed (now, has rain feat) | new tuned candidate (now also has rain feat) | persistence |
|---|---|---|---|
| 3 | +0.015 | +0.018 | +0.021 |
| 6 | -0.311 | -0.339 | -0.348 |
| 7 | -0.355 | -0.370 | -0.409 |

Closing the feature gap does not change the conclusion: all three (deployed / new
tuned candidate / naive persistence) remain within noise of each other at every one of
these horizons, and the new candidate still doesn't clearly beat either. See
`h367_with_rainfeat_comparison.csv`.

## 5c. Trying other ML algorithms (2026-09-18, user request)

Tuned (Optuna, same inner-CV-on-fit-block methodology) and holdout-evaluated LightGBM,
XGBoost, RandomForest, and Ridge (linear baseline) on the base 12-feature set, for all
7 horizons. LightGBM/XGBoost/Ridge reproduce the same pattern as CatBoost — roughly tied
with persistence, sometimes worse. **RandomForest is the one exception: it beats
persistence AND every other model at every single horizon** on the honest holdout
(H1 +0.650, H2 +0.474, H3 +0.315, H4 +0.187, H5 +0.026, H6 -0.108, H7 -0.135 — all
better than the corresponding persistence/deployed/CatBoost numbers in §4). See
`other_ml_comparison.csv`.

**Important caveat before treating this as a win**: RandomForest's *inner* CV (used for
tuning) was strongly *negative* at every horizon (e.g. H7 inner_cv=-25) — the opposite of
every other model, whose inner CV looked optimistic and then held up worse on holdout.
Row-by-row inspection of the H1 holdout explains why: the 20-row holdout window is
dominated by two extreme flood-surge days (2026-09-10/11, actual 233,501 / 429,690 m³/day
— roughly 10-20× every other value in the window), so NSE here is almost entirely decided
by how well each model handles those two days specifically. Persistence and the
regularized/early-stopped CatBoost both badly *undershoot* the sudden escalation
(persistence predicts 17,851 / 233,501 — i.e. yesterday's value — against actuals of
233,501 / 429,690). RandomForest's ensemble, trained on rain/API/ΔS features, reacts
faster to the escalating conditions (predicts 107,880 / 254,542) — still an undershoot,
but a meaningfully smaller one. That's a genuine, explainable mechanism (RF captures a
nonlinear "rain+ΔS rising fast → expect a jump" pattern that the more conservative,
heavily-regularized boosted models under-react to), not a bug or a leak — verified by
hand against the raw log rows. The tradeoff: RF is slightly *worse* than persistence
during long stable zero-flow stretches (small nonzero noise where persistence predicts
an exact 0).

**Read this cautiously, not as a settled win**: with only 19-20 holdout points and the
result driven by essentially 2-3 extreme days, this is thin evidence by the standard
this project has held itself to elsewhere (every one of the 4 prior "looked great, then
reversed" episodes had considerably more support than this). Recommended before any
deployment decision: run RandomForest in shadow (log its predictions alongside
production, don't serve them) through at least one more storm event, and re-check this
comparison once `forecast_accuracy_log.csv` has grown past today's 56 as_of-dates.

## 6. Conclusion

The ceiling this project's team identified in September 2026
(`inflow_logtransform_20260907`: "further technique/feature tweaks are hitting a
ceiling — more data is the only lever left") does **not** appear to have been resolved by
adding 2 more months of data (including a real flood event), retrying the original
2-stage architecture, adding 10 new candidate features, or careful Optuna tuning with an
explicit overfit audit. The most likely explanation: ~14 months of history is still only
~1.2 wet seasons — not enough to characterize year-to-year variability — and the
available point-source features (single rain gauge, single water-level sensor) may not
carry enough information about catchment-wide upstream conditions to beat next-day
persistence at H1-H3 for this reservoir. Recommended next real levers (none tried here):
upstream tributary telemetry, catchment-wide (not point) rainfall (radar/satellite),
soil moisture, or simply more calendar time. None of the current candidates are
recommended for deployment over the current production model.

**Update after trying other ML algorithms (§5c)**: RandomForest is a genuine partial
exception — it beats persistence and every other tried model at all 7 horizons on the
current 20-point holdout, via a real, explainable mechanism (reacts faster to
escalating rain/ΔS conditions than the heavily-regularized boosted models). Given how
thin the evidence is (dominated by 2 extreme days) and this project's history of
CV-looks-good-then-reverses, it is not recommended for immediate deployment, but it is
the single most promising lever found in this entire investigation and is worth
shadow-testing going forward.
