"""Complete Training, Evaluation, and Diagnostic Pipeline for Milestone 3.

Executes:
1. Data readiness and independence audit on the 136 ground-truth segments.
2. Chronological whole-date splitting (Train: Oct 1-3, Val: Oct 4, Test: Oct 7).
3. Fits M0 (Hierarchical Historical Median), M1 (Ridge), M2 (Random Forest).
4. Inductive Split-Conformal prediction interval calibration.
5. Out-of-sample evaluation on held-out test data (Oct 7).
6. Performance breakdown by stop pair, hour, and fallback tier.
7. Publication plots in `reports/figures/`.
8. Saves `data/processed/milestone3_metrics.json`.
"""

import json
import os
import sys
import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.ml.baseline import HistoricalMedianBaseline
from backend.ml.conformal import SplitConformalCalibrator
from backend.ml.models import TrafficModelSuite, calculate_metrics

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_JSON = os.path.join(ROOT_DIR, "data", "processed", "milestone3_metrics.json")
FIGURES_DIR = os.path.join(ROOT_DIR, "reports", "figures")


def run_pipeline():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    con = duckdb.connect()

    # 1. Load Ground Truth Segments
    df = con.execute("""
        SELECT 
            observation_id, trajectory_id, vehicle_id, route_id, pattern_id,
            direction_id, segment_key, stop_sequence_from, stop_sequence_to,
            stop_id_from, stop_id_to, stop_name_from, stop_name_to,
            distance_m, segment_time_s, speed_kmh,
            arrival_from_utc, arrival_to_utc, arrival_from_ist, arrival_to_ist,
            service_date
        FROM read_parquet('data/processed/stop_crossings/service_date=*/observed_segments.parquet')
        ORDER BY arrival_from_utc;
    """).df()

    print(f"Loaded {len(df)} total observed segments.")
    df["service_date_str"] = df["service_date"].astype(str)
    df["hour_ist"] = pd.to_datetime(df["arrival_from_ist"]).dt.hour
    df["is_weekend"] = df["service_date_str"].apply(lambda x: 1 if pd.to_datetime(x).day_name() in ["Saturday", "Sunday"] else 0)
    df["is_holiday"] = df["service_date_str"].apply(lambda x: 1 if x == "2026-10-02" else 0)

    # 2. Chronological Whole-Date Splitting
    train_dates = ["2026-10-01", "2026-10-02", "2026-10-03"]
    val_dates = ["2026-10-04"]
    test_dates = ["2026-10-07"]

    train_df = df[df["service_date_str"].isin(train_dates)].reset_index(drop=True)
    val_df = df[df["service_date_str"].isin(val_dates)].reset_index(drop=True)
    test_df = df[df["service_date_str"].isin(test_dates)].reset_index(drop=True)

    print(f"\nChronological Splits:")
    print(f"  Train ({', '.join(train_dates)}): {len(train_df)} observations across {train_df['vehicle_id'].nunique()} vehicles, {train_df['segment_key'].nunique()} stop pairs")
    print(f"  Validation ({', '.join(val_dates)}): {len(val_df)} observations across {val_df['vehicle_id'].nunique()} vehicles, {val_df['segment_key'].nunique()} stop pairs")
    print(f"  Test ({', '.join(test_dates)}): {len(test_df)} observations across {test_df['vehicle_id'].nunique()} vehicles, {test_df['segment_key'].nunique()} stop pairs")

    # Leakage check assertion
    max_train_ts = train_df["arrival_to_utc"].max()
    min_val_ts = val_df["arrival_from_utc"].min()
    max_val_ts = val_df["arrival_to_utc"].max()
    min_test_ts = test_df["arrival_from_utc"].min()
    assert max_train_ts < min_val_ts, "Target leakage detected: train overlaps with validation!"
    assert max_val_ts < min_test_ts, "Target leakage detected: validation overlaps with test!"
    print("  [OK] Leakage check passed: max(train) < min(val) < min(test) strictly hold.")

    # 3. Fit Traffic Models on Train partition
    suite = TrafficModelSuite(min_samples_baseline=3)
    suite.fit(train_df)

    # 4. Predict on Validation and Calibrate Split-Conformal Intervals
    val_preds = suite.predict(val_df)
    y_val_true = val_df["segment_time_s"].values
    y_val_m0 = val_preds["M0_Historical_Median"]

    calibrator = SplitConformalCalibrator(target_coverage=0.90)
    calibrator.calibrate(y_val_true, y_val_m0)

    # 5. Evaluate on Held-Out Test Data (Oct 7)
    test_preds = suite.predict(test_df)
    y_test_true = test_df["segment_time_s"].values
    y_test_m0 = test_preds["M0_Historical_Median"]
    y_test_m1 = test_preds["M1_Ridge_Regression"]
    y_test_m2 = test_preds["M2_Random_Forest"]

    # Calculate metrics
    m0_metrics = calculate_metrics(y_test_true, y_test_m0)
    baseline_mae = m0_metrics["mae"]
    m1_metrics = calculate_metrics(y_test_true, y_test_m1, baseline_mae=baseline_mae)
    m2_metrics = calculate_metrics(y_test_true, y_test_m2, baseline_mae=baseline_mae)

    print("\n=======================================================")
    print("HELD-OUT TEST SET EVALUATION (Date: 2026-10-07, n=30)")
    print("=======================================================")
    print(f"M0 (Historical Median Baseline):  MAE={m0_metrics['mae']:.2f}s | RMSE={m0_metrics['rmse']:.2f}s | MedAE={m0_metrics['med_ae']:.2f}s | Bias={m0_metrics['bias']:.2f}s | MAPE={m0_metrics['mape']:.2f}% | MedAPE={m0_metrics['med_ape']:.2f}%")
    print(f"M1 (Ridge Regression on log T):  MAE={m1_metrics['mae']:.2f}s | RMSE={m1_metrics['rmse']:.2f}s | MedAE={m1_metrics['med_ae']:.2f}s | Bias={m1_metrics['bias']:.2f}s | MAPE={m1_metrics['mape']:.2f}% | Imp={m1_metrics['improvement_pct']:.2f}%")
    print(f"M2 (Random Forest Regressor):     MAE={m2_metrics['mae']:.2f}s | RMSE={m2_metrics['rmse']:.2f}s | MedAE={m2_metrics['med_ae']:.2f}s | Bias={m2_metrics['bias']:.2f}s | MAPE={m2_metrics['mape']:.2f}% | Imp={m2_metrics['improvement_pct']:.2f}%")

    # Evaluate Conformal Coverage on Test Set
    conformal_results = calibrator.evaluate_coverage(y_test_true, y_test_m0)
    print("\nSplit-Conformal Prediction Interval Results (Target 90%):")
    print(f"  Empirical Test Coverage: {conformal_results['empirical_coverage_pct']:.2f}%")
    print(f"  Conformal Radius (q): +/- {conformal_results['conformal_radius_s']:.2f} seconds")
    print(f"  Average Interval Width: {conformal_results['avg_interval_width_s']:.2f} seconds")

    # 6. Fallback Tier Utilization on Test Set
    m0_objs = test_preds["m0_objects"]
    tier_counts = {}
    for p in m0_objs:
        tier_counts[p.tier] = tier_counts.get(p.tier, 0) + 1
    print("\nFallback Tier Distribution on Test Queries:")
    for tier, count in sorted(tier_counts.items()):
        print(f"  {tier}: {count} ({count/len(m0_objs)*100:.1f}%)")

    # 7. Breakdown by Stop Pair and Hour on Test Set
    test_eval_df = test_df.copy()
    test_eval_df["pred_m0"] = y_test_m0
    test_eval_df["pred_m1"] = y_test_m1
    test_eval_df["pred_m2"] = y_test_m2
    test_eval_df["err_m0"] = np.abs(y_test_m0 - y_test_true)
    test_eval_df["err_m1"] = np.abs(y_test_m1 - y_test_true)
    test_eval_df["err_m2"] = np.abs(y_test_m2 - y_test_true)
    test_eval_df["tier"] = [p.tier for p in m0_objs]

    stop_pair_breakdown = test_eval_df.groupby("segment_key").agg(
        obs_count=("observation_id", "count"),
        actual_median_time=("segment_time_s", "median"),
        pred_median_time_m0=("pred_m0", "median"),
        mae_m0=("err_m0", "mean"),
        mae_m1=("err_m1", "mean"),
        mae_m2=("err_m2", "mean"),
    ).reset_index().sort_values(by="obs_count", ascending=False)

    hour_breakdown = test_eval_df.groupby("hour_ist").agg(
        obs_count=("observation_id", "count"),
        actual_median_time=("segment_time_s", "median"),
        mae_m0=("err_m0", "mean"),
        mae_m1=("err_m1", "mean"),
        mae_m2=("err_m2", "mean"),
    ).reset_index().sort_values(by="hour_ist")

    # 8. Generate Publication Figures
    generate_figures(test_df, y_test_true, y_test_m0, y_test_m1, y_test_m2, calibrator)

    # 9. Save Comprehensive JSON Artifact
    output_data = {
        "milestone": "3.0",
        "dataset_summary": {
            "total_ground_truth_segments": len(df),
            "train_observations": len(train_df),
            "val_observations": len(val_df),
            "test_observations": len(test_df),
            "train_dates": train_dates,
            "val_dates": val_dates,
            "test_dates": test_dates,
            "globally_distinct_vehicles": int(df["vehicle_id"].nunique()),
            "globally_distinct_stop_pairs": int(df["segment_key"].nunique()),
            "globally_distinct_routes": int(df["route_id"].nunique()),
        },
        "model_performance_on_held_out_test": {
            "M0_Historical_Median": m0_metrics,
            "M1_Ridge_Regression": m1_metrics,
            "M2_Random_Forest": m2_metrics,
        },
        "split_conformal_intervals": conformal_results,
        "fallback_tier_utilization_test": tier_counts,
        "stop_pair_performance": stop_pair_breakdown.to_dict(orient="records"),
        "hourly_performance": hour_breakdown.to_dict(orient="records"),
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output_data, f, indent=2, default=str)
    print(f"\nSaved metrics to {OUTPUT_JSON}")


def generate_figures(test_df, y_true, y_m0, y_m1, y_m2, calibrator):
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Figure 9: Actual vs Predicted Travel Time across Models
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), dpi=150, sharey=True, sharex=True)
    models = [("M0: Historical Median", y_m0, "#2563eb"),
              ("M1: Ridge Regression", y_m1, "#059669"),
              ("M2: Random Forest", y_m2, "#d97706")]

    max_val = max(np.max(y_true), np.max(y_m0), np.max(y_m1), np.max(y_m2)) * 1.05

    for ax, (title, pred, col) in zip(axes, models):
        ax.scatter(y_true, pred, color=col, alpha=0.8, edgecolors="none", s=45)
        ax.plot([0, max_val], [0, max_val], "k--", alpha=0.6, label="Perfect Prediction")
        ax.set_title(title, fontweight="bold", fontsize=10)
        ax.set_xlabel("Observed Segment Time (s)", fontweight="bold")
        ax.set_xlim(0, max_val)
        ax.set_ylim(0, max_val)
        mae = np.mean(np.abs(pred - y_true))
        ax.text(0.05, 0.90, f"MAE = {mae:.1f}s", transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8), fontweight="bold")

    axes[0].set_ylabel("Predicted Segment Time (s)", fontweight="bold")
    fig.suptitle("Observed vs. Predicted Travel Times on Held-Out Test Date (October 7, 2026)", fontweight="bold", y=0.98)
    fig.tight_layout()
    f9_path = os.path.join(FIGURES_DIR, "fig9_model_predictions_vs_actual.png")
    fig.savefig(f9_path)
    plt.close(fig)
    print(f"Saved {f9_path}")

    # Figure 10: Absolute Error Distributions
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    err_data = [np.abs(y_m0 - y_true), np.abs(y_m1 - y_true), np.abs(y_m2 - y_true)]
    bp = ax.boxplot(err_data, patch_artist=True, tick_labels=["M0 Baseline", "M1 Ridge", "M2 Random Forest"],
                    boxprops=dict(facecolor="#bae6fd", color="#0284c7"),
                    medianprops=dict(color="#b91c1c", linewidth=2))
    ax.set_ylabel("Absolute Error (seconds)", fontweight="bold")
    ax.set_title("Absolute Error Distribution on Held-Out Test Set (October 7, 2026)", fontweight="bold")
    fig.tight_layout()
    f10_path = os.path.join(FIGURES_DIR, "fig10_error_distribution.png")
    fig.savefig(f10_path)
    plt.close(fig)
    print(f"Saved {f10_path}")

    # Figure 11: Conformal Prediction Intervals
    lower, upper = calibrator.predict_intervals(y_m0)
    sorted_idx = np.argsort(y_true)
    y_true_s = y_true[sorted_idx]
    y_m0_s = y_m0[sorted_idx]
    lower_s = lower[sorted_idx]
    upper_s = upper[sorted_idx]

    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    idx = np.arange(len(y_true_s))
    ax.fill_between(idx, lower_s, upper_s, color="#93c5fd", alpha=0.4, label=f"90% Conformal Interval (+/- {calibrator.conformal_radius:.1f}s)")
    ax.plot(idx, y_m0_s, color="#1d4ed8", linewidth=1.5, label="M0 Point Prediction")
    ax.scatter(idx, y_true_s, color="#dc2626", s=35, zorder=5, label="Observed Ground Truth")
    ax.set_xlabel("Test Observations (Sorted by Actual Travel Time)", fontweight="bold")
    ax.set_ylabel("Travel Time (seconds)", fontweight="bold")
    ax.set_title(f"Split-Conformal Prediction Interval Coverage ({calibrator.target_coverage*100:.0f}% Target)", fontweight="bold")
    ax.legend(frameon=True)
    fig.tight_layout()
    f11_path = os.path.join(FIGURES_DIR, "fig11_conformal_coverage.png")
    fig.savefig(f11_path)
    plt.close(fig)
    print(f"Saved {f11_path}")


if __name__ == "__main__":
    run_pipeline()

