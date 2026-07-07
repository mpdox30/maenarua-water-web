"""
=============================================================================
 Manuscript-Final Figures & Tables Generator (single split, single model)
=============================================================================
Unlike manuscript_figures.py (which compares chronological vs. stratified
side by side for internal decision-making), this script produces the FINAL,
committed figure/table set for the manuscript itself -- one split, one
headline model, no side-by-side justification needed in the text.

Default: STRATIFIED split, CatBoost as the headline model (see
SPLIT_DIR / HEADLINE_MODEL below to change either).

Reads from a single results folder (default: outputs_stratified/) produced
by inflow_forecasting_MULTIMODEL_stratified_split.ipynb, and writes:

  Tables:
    table1_headline_performance.csv   - CatBoost test performance, all metrics, all horizons
    table2_model_comparison.csv       - all 3 models side by side (for a supplementary table,
                                         or to justify why CatBoost was chosen as headline)
    table3_q1_benchmarking.csv         - Naive baseline + all 3 models, long format
                                         (the "Naive + SOTA" table Q1 reviewers expect --
                                         see Q1_Manuscript_Guide_Hydrology.md Part 6.5)
    table4_cv_stability.csv           - walk-forward CV mean+-std, headline model only

  Figures:
    fig1_performance_by_horizon.png   - Test NSE + KGE by horizon (2-panel), headline model
    fig2_error_metrics_by_horizon.png - Test RMSE + MAE by horizon (2-panel), headline model
    fig3_q1_benchmarking_comparison.png - Naive baseline + CatBoost/XGBoost/LightGBM, NSE
                                         and RMSE side by side (the Q1 "Naive + SOTA"
                                         benchmarking figure)
    fig4_skill_vs_baseline.png        - RMSE/MAE improvement (%) over persistence, headline model
    fig5_cv_stability.png             - walk-forward CV stability, headline model, mean +/- std
    fig6_shap_feature_importance.png  - top SHAP features, headline model, horizontal bar per horizon
    fig7_hurdle_comparison.png        - single-stage vs hurdle NSE, headline model (optional,
                                         only if you decide to report the hurdle model)

Run this script from the directory that CONTAINS your results folder
(e.g. outputs_stratified/), or edit SPLIT_DIR below.

Usage:
    python manuscript_figures_final.py

Requires: pandas, numpy, matplotlib
=============================================================================
"""
import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# =============================================================================
# Configuration -- edit these for your setup
# =============================================================================
SPLIT_DIR = r"D:\University of Phayao\เอกสารการเรียน\Paper 3\ML\CB\Retrain\outputs_stratified"   # folder containing the notebook's CSV outputs
HEADLINE_MODEL = "CatBoost"        # which model to feature as the main result
INCLUDE_HURDLE = True              # set False to skip the hurdle figure entirely
                                    # if you decide not to report it in the manuscript
OUTDIR = r"D:\University of Phayao\เอกสารการเรียน\Paper 3\ML\CB\Retrain\manuscript_figures_final"
os.makedirs(OUTDIR, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update({
    "figure.dpi": 150, "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.labelsize": 11, "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 9,
})
HEADLINE_COLOR = "#4C72B0"
MODEL_ORDER = ["CatBoost", "XGBoost", "LightGBM"]
MODEL_COLORS = {"CatBoost": "#4C72B0", "XGBoost": "#DD8452", "LightGBM": "#55A868"}


def load_csv(folder, name):
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        print(f"  [WARN] Missing file, skipping what depends on it: {path}")
        return None
    return pd.read_csv(path)


print("=" * 78)
print(f" Loading results from: {SPLIT_DIR}/  (headline model: {HEADLINE_MODEL})")
print("=" * 78)

perf = load_csv(SPLIT_DIR, "all_models_test_performance.csv")
cv = load_csv(SPLIT_DIR, "cv_stability_diagnostic.csv")
shap_df = load_csv(SPLIT_DIR, "shap_importance_all_models.csv")
hurdle = load_csv(SPLIT_DIR, "hurdle_test_performance_all_models.csv") if INCLUDE_HURDLE else None

HAS_MAE = perf is not None and "Test_MAE" in perf.columns
if perf is not None and not HAS_MAE:
    print("  [NOTE] Test_MAE column not found -- re-run the notebook with the MAE fix")
    print("         for complete error-metric reporting (Q1 guidance requires both")
    print("         error metrics [RMSE, MAE] and skill metrics [NSE, KGE]).")

# =============================================================================
# TABLE 1 -- Headline model, all metrics, all horizons (the main manuscript table)
# =============================================================================
print("\n" + "=" * 78)
print(f" Table 1 -- {HEADLINE_MODEL} test performance (headline result)")
print("=" * 78)

if perf is not None:
    cols = ["H"]
    if HAS_MAE:
        cols += ["Baseline_MAE", "Test_MAE", "MAE_improve_%"]
    cols += ["Baseline_RMSE", "Test_RMSE", "RMSE_improve_%", "Baseline_NSE", "Test_NSE", "Test_KGE"]

    table1 = perf[perf.Model == HEADLINE_MODEL][cols].round(3).reset_index(drop=True)
    table1_path = os.path.join(OUTDIR, "table1_headline_performance.csv")
    table1.to_csv(table1_path, index=False)
    print(table1.to_string(index=False))
    print(f"\nSaved: {table1_path}")
else:
    print("  [SKIP] all_models_test_performance.csv not found.")

# =============================================================================
# TABLE 2 -- All 3 models side by side (supplementary / model-selection justification)
# =============================================================================
print("\n" + "=" * 78)
print(" Table 2 -- All models compared (for supplementary material / model-choice justification)")
print("=" * 78)

if perf is not None:
    metric_cols = ["Test_NSE", "Test_KGE", "Test_RMSE"] + (["Test_MAE"] if HAS_MAE else [])
    table2 = perf.pivot_table(index="H", columns="Model", values=metric_cols)
    table2_path = os.path.join(OUTDIR, "table2_model_comparison.csv")
    table2.to_csv(table2_path)
    print(table2.round(3).to_string())
    print(f"\nSaved: {table2_path}")
else:
    print("  [SKIP] all_models_test_performance.csv not found.")

# =============================================================================
# TABLE 4 -- CV stability, headline model only
# =============================================================================
print("\n" + "=" * 78)
print(f" Table 4 -- Walk-forward CV stability, {HEADLINE_MODEL} (train-block-only)")
print("=" * 78)

if cv is not None:
    cv_head = cv[cv.Model == HEADLINE_MODEL]
    table4 = cv_head.groupby("H")["Model_NSE"].agg(["mean", "std"]).reset_index()
    table4 = table4.rename(columns={"mean": "CV_NSE_mean", "std": "CV_NSE_std"})
    table4_path = os.path.join(OUTDIR, "table4_cv_stability.csv")
    table4.to_csv(table4_path, index=False)
    print(table4.round(3).to_string(index=False))
    print(f"\nSaved: {table4_path}")
else:
    print("  [SKIP] cv_stability_diagnostic.csv not found.")

# =============================================================================
# FIGURE 1 -- Test NSE + KGE by horizon (2-panel), headline model
# =============================================================================
if perf is not None:
    sub = perf[perf.Model == HEADLINE_MODEL].sort_values("H")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    axes[0].plot(sub["H"], sub["Test_NSE"], marker="o", color=HEADLINE_COLOR, linewidth=2)
    axes[0].axhline(0, color="gray", linestyle="--", linewidth=1)
    axes[0].set_xlabel("Forecast horizon (days)")
    axes[0].set_ylabel("Test NSE")
    axes[0].set_title("Nash-Sutcliffe Efficiency")
    axes[0].set_xticks(range(1, 8))

    axes[1].plot(sub["H"], sub["Test_KGE"], marker="s", color=HEADLINE_COLOR, linewidth=2)
    axes[1].axhline(0, color="gray", linestyle="--", linewidth=1)
    axes[1].set_xlabel("Forecast horizon (days)")
    axes[1].set_ylabel("Test KGE")
    axes[1].set_title("Kling-Gupta Efficiency")
    axes[1].set_xticks(range(1, 8))

    plt.suptitle(f"{HEADLINE_MODEL} forecast skill by horizon", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "fig1_performance_by_horizon.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("\nSaved: fig1_performance_by_horizon.png")

# =============================================================================
# FIGURE 2 -- Test RMSE + MAE by horizon (2-panel), headline model, with baseline overlay
# =============================================================================
if perf is not None:
    sub = perf[perf.Model == HEADLINE_MODEL].sort_values("H")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    axes[0].plot(sub["H"], sub["Baseline_RMSE"], marker="o", color="gray", linewidth=1.5,
                 linestyle="--", label="Persistence baseline")
    axes[0].plot(sub["H"], sub["Test_RMSE"], marker="o", color=HEADLINE_COLOR, linewidth=2,
                 label=HEADLINE_MODEL)
    axes[0].set_xlabel("Forecast horizon (days)")
    axes[0].set_ylabel("RMSE (m\u00b3/day)")
    axes[0].set_title("Root Mean Squared Error")
    axes[0].set_xticks(range(1, 8))
    axes[0].legend(frameon=True)

    if HAS_MAE:
        axes[1].plot(sub["H"], sub["Baseline_MAE"], marker="s", color="gray", linewidth=1.5,
                     linestyle="--", label="Persistence baseline")
        axes[1].plot(sub["H"], sub["Test_MAE"], marker="s", color=HEADLINE_COLOR, linewidth=2,
                     label=HEADLINE_MODEL)
        axes[1].set_xlabel("Forecast horizon (days)")
        axes[1].set_ylabel("MAE (m\u00b3/day)")
        axes[1].set_title("Mean Absolute Error")
        axes[1].set_xticks(range(1, 8))
        axes[1].legend(frameon=True)
    else:
        axes[1].axis("off")
        axes[1].text(0.5, 0.5, "MAE not available\n(re-run notebook with MAE fix)",
                     ha="center", va="center", fontsize=10, color="gray")

    plt.suptitle(f"{HEADLINE_MODEL} error metrics vs. persistence baseline", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "fig2_error_metrics_by_horizon.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: fig2_error_metrics_by_horizon.png")

# =============================================================================
# TABLE 3 -- Q1 benchmarking table: Naive baseline + all 3 models (NSE, RMSE,
# and MAE where available), in the "Naive + SOTA" format the Q1 guide
# requires (Q1_Manuscript_Guide_Hydrology.md, Part 6.5 / Part 2 benchmarking
# row / common rejection reason #2: "Inadequate benchmarking").
# =============================================================================
print("\n" + "=" * 78)
print(" Table 3 -- Q1 benchmarking table: Naive persistence + CatBoost/XGBoost/LightGBM")
print("=" * 78)

if perf is not None:
    bench_rows = []
    base_once = perf[perf.Model == MODEL_ORDER[0]][["H", "Baseline_NSE", "Baseline_RMSE"]].copy()
    base_once = base_once.rename(columns={"Baseline_NSE": "NSE", "Baseline_RMSE": "RMSE"})
    base_once["Model"] = "Persistence (naive baseline)"
    if HAS_MAE:
        base_mae_once = perf[perf.Model == MODEL_ORDER[0]][["H", "Baseline_MAE"]].rename(columns={"Baseline_MAE": "MAE"})
        base_once = base_once.merge(base_mae_once, on="H")
    bench_rows.append(base_once)

    for model in MODEL_ORDER:
        sub = perf[perf.Model == model][["H", "Test_NSE", "Test_RMSE"] + (["Test_MAE"] if HAS_MAE else [])].copy()
        sub = sub.rename(columns={"Test_NSE": "NSE", "Test_RMSE": "RMSE", "Test_MAE": "MAE"})
        sub["Model"] = model
        bench_rows.append(sub)

    table3 = pd.concat(bench_rows, ignore_index=True)
    col_order = ["Model", "H", "NSE", "RMSE"] + (["MAE"] if HAS_MAE else [])
    table3 = table3[col_order].sort_values(["H", "Model"]).reset_index(drop=True)
    table3_path = os.path.join(OUTDIR, "table3_q1_benchmarking.csv")
    table3.round(3).to_csv(table3_path, index=False)
    print(table3.round(3).to_string(index=False))
    print(f"\nSaved: {table3_path}")
else:
    print("  [SKIP] all_models_test_performance.csv not found.")

# =============================================================================
# FIGURE 3 -- Q1 benchmarking figure: Naive baseline + 3 models, NSE and RMSE
# side by side. This is the figure that directly answers the Q1 "Naive +
# SOTA" benchmarking requirement -- XGBoost/LightGBM serve as the SOTA
# tree-based comparators alongside the headline model, all shown against
# the same naive persistence baseline.
# =============================================================================
if perf is not None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    base_nse = perf[perf.Model == MODEL_ORDER[0]].sort_values("H")
    axes[0].plot(base_nse["H"], base_nse["Baseline_NSE"], marker="D", color="black",
                 linewidth=1.8, linestyle=":", label="Persistence (naive baseline)")
    for model in MODEL_ORDER:
        sub = perf[perf.Model == model].sort_values("H")
        marker = "o" if model == HEADLINE_MODEL else ("s" if model == MODEL_ORDER[1] else "^")
        lw = 2.5 if model == HEADLINE_MODEL else 1.8
        axes[0].plot(sub["H"], sub["Test_NSE"], marker=marker, color=MODEL_COLORS[model],
                     linewidth=lw, label=model)
    axes[0].axhline(0, color="gray", linestyle="--", linewidth=1)
    axes[0].set_xlabel("Forecast horizon (days)")
    axes[0].set_ylabel("Test NSE")
    axes[0].set_title("Skill (NSE): higher is better")
    axes[0].set_xticks(range(1, 8))
    axes[0].legend(frameon=True, fontsize=8.5)

    base_rmse = perf[perf.Model == MODEL_ORDER[0]].sort_values("H")
    axes[1].plot(base_rmse["H"], base_rmse["Baseline_RMSE"], marker="D", color="black",
                 linewidth=1.8, linestyle=":", label="Persistence (naive baseline)")
    for model in MODEL_ORDER:
        sub = perf[perf.Model == model].sort_values("H")
        marker = "o" if model == HEADLINE_MODEL else ("s" if model == MODEL_ORDER[1] else "^")
        lw = 2.5 if model == HEADLINE_MODEL else 1.8
        axes[1].plot(sub["H"], sub["Test_RMSE"], marker=marker, color=MODEL_COLORS[model],
                     linewidth=lw, label=model)
    axes[1].set_xlabel("Forecast horizon (days)")
    axes[1].set_ylabel("Test RMSE (m\u00b3/day)")
    axes[1].set_title("Error (RMSE): lower is better")
    axes[1].set_xticks(range(1, 8))
    axes[1].legend(frameon=True, fontsize=8.5)

    plt.suptitle("Model comparison vs. naive persistence baseline (Q1 benchmarking)", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "fig3_q1_benchmarking_comparison.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: fig3_q1_benchmarking_comparison.png")
else:
    print("  [SKIP fig3] all_models_test_performance.csv not found.")

# =============================================================================
# FIGURE 4 -- RMSE/MAE improvement (%) over persistence baseline, headline model
# =============================================================================
if perf is not None:
    sub = perf[perf.Model == HEADLINE_MODEL].sort_values("H")
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(sub))
    width = 0.35 if HAS_MAE else 0.6

    ax.bar(x - width / 2 if HAS_MAE else x, sub["RMSE_improve_%"], width,
           label="RMSE improvement", color=HEADLINE_COLOR)
    if HAS_MAE:
        ax.bar(x + width / 2, sub["MAE_improve_%"], width,
               label="MAE improvement", color="#DD8452")
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(sub["H"])
    ax.set_xlabel("Forecast horizon (days)")
    ax.set_ylabel("Improvement over persistence baseline (%)")
    ax.set_title(f"{HEADLINE_MODEL} skill relative to naive persistence")
    ax.legend(frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "fig4_skill_vs_baseline.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: fig4_skill_vs_baseline.png")

# =============================================================================
# FIGURE 5 -- Walk-forward CV stability, headline model, mean +/- std
# =============================================================================
if cv is not None:
    cv_head = cv[cv.Model == HEADLINE_MODEL]
    summary = cv_head.groupby("H")["Model_NSE"].agg(["mean", "std"]).reset_index()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(summary["H"], summary["mean"], yerr=summary["std"], marker="o",
                color=HEADLINE_COLOR, capsize=4, linewidth=2)
    ax.axhline(0, color="black", linewidth=1, linestyle="--")
    ax.set_xlabel("Forecast horizon (days)")
    ax.set_ylabel("CV NSE (train block only)\nmean \u00b1 std across folds")
    ax.set_title(f"{HEADLINE_MODEL} walk-forward CV stability")
    ax.set_xticks(range(1, 8))
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "fig5_cv_stability.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: fig5_cv_stability.png")

# =============================================================================
# FIGURE 6 -- SHAP feature importance, headline model, one panel per horizon group
# =============================================================================
if shap_df is not None:
    sub = shap_df[shap_df.Model == HEADLINE_MODEL].copy()
    targets_sorted = sorted(sub["Target"].unique(), key=lambda x: int(x.split("=")[0][1:]))

    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    axes = axes.flatten()
    for i, tgt in enumerate(targets_sorted):
        ax = axes[i]
        s2 = sub[sub.Target == tgt].sort_values("mean_abs_shap", ascending=True).tail(7)
        ax.barh(s2["feature"], s2["mean_abs_shap"], color=HEADLINE_COLOR)
        ax.set_title(f"H{i+1}", fontsize=11)
        ax.tick_params(axis="y", labelsize=8)
    for j in range(len(targets_sorted), len(axes)):
        axes[j].axis("off")
    plt.suptitle(f"{HEADLINE_MODEL} SHAP feature importance (mean |SHAP|) by horizon", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "fig6_shap_feature_importance.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: fig6_shap_feature_importance.png")

# =============================================================================
# FIGURE 7 -- Hurdle vs single-stage, headline model only (optional)
# =============================================================================
if INCLUDE_HURDLE and hurdle is not None:
    sub = hurdle[hurdle.Model == HEADLINE_MODEL].sort_values("H")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(sub["H"], sub["SingleStage_NSE"], marker="o", color="gray", linewidth=2,
            label=f"{HEADLINE_MODEL} (single-stage)")
    ax.plot(sub["H"], sub["Hurdle_NSE"], marker="s", color=HEADLINE_COLOR, linewidth=2,
            label=f"{HEADLINE_MODEL} (hurdle)")
    ax.axhline(0, color="black", linewidth=1, linestyle="--")
    ax.set_xlabel("Forecast horizon (days)")
    ax.set_ylabel("Test NSE")
    ax.set_title(f"Single-stage vs. two-stage (hurdle) {HEADLINE_MODEL}")
    ax.set_xticks(range(1, 8))
    ax.legend(frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "fig7_hurdle_comparison.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: fig7_hurdle_comparison.png")
    print(f"  [NOTE] Per earlier diagnostics, hurdle results at longer horizons may be")
    print(f"         unreliable due to small zero-inflow sample size. Check")
    print(f"         stage2_in_train_cv_nse and zero_recall columns before reporting.")
elif INCLUDE_HURDLE:
    print("  [SKIP] hurdle_test_performance_all_models.csv not found.")

print("\n" + "=" * 78)
print(f" All available tables/figures written to: {OUTDIR}/")
print("=" * 78)
