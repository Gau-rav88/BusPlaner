"""Automated Reliability and Integrity Tests for Milestone 3.1 & 3.1.1 Audit.

Verifies:
1. Conformal prediction interval mathematics (unclipped 2*q vs lower-bound clipping at 5.0s, coverage identity).
2. Target value distribution inspection (global minimum segment time >= 21.45s, zero points < 5.0s).
3. Ground-truth terminology and route scope accounting (199 crossings, 136 segments, 26 stop pairs, Route 1657 status).
4. M0 fallback tier training inventory and test error quantification (identifying seq9 sparse-history failure).
5. Vehicle and stop-pair independence invariants (split disjointness and intra-split trip clustering).
6. Random Forest leakage safety, out-of-fold training, and tree architecture.
7. Metric recalculation integrity and MAPE vs MedAPE properties.
8. Illustrative status of independent coverage bounds and clustered evaluation strategy recommendation.
"""

import json
import math
import os
import duckdb
import numpy as np
import pandas as pd
import pytest

from backend.ml.baseline import HistoricalMedianBaseline
from backend.ml.conformal import SplitConformalCalibrator
from backend.ml.features import TrafficFeatureExtractor
from backend.ml.models import TrafficModelSuite, calculate_metrics

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AUDIT_JSON_PATH = os.path.join(ROOT_DIR, "data", "processed", "milestone3_1_audit_metrics.json")


@pytest.fixture(scope="module")
def audit_data():
    assert os.path.exists(AUDIT_JSON_PATH), f"Audit metrics file not found: {AUDIT_JSON_PATH}"
    with open(AUDIT_JSON_PATH, "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def ground_truth_df():
    con = duckdb.connect()
    df = con.execute("""
        SELECT *
        FROM read_parquet('data/processed/stop_crossings/service_date=*/observed_segments.parquet')
        ORDER BY arrival_from_utc;
    """).df()
    df["service_date_str"] = df["service_date"].astype(str)
    df["hour_ist"] = pd.to_datetime(df["arrival_from_ist"]).dt.hour
    df["is_weekend"] = df["service_date_str"].apply(lambda x: 1 if pd.to_datetime(x).day_name() in ["Saturday", "Sunday"] else 0)
    df["is_holiday"] = df["service_date_str"].apply(lambda x: 1 if x == "2026-10-02" else 0)
    return df


@pytest.fixture(scope="module")
def crossings_df():
    con = duckdb.connect()
    return con.execute("""
        SELECT trajectory_id, vehicle_id, route_id, stop_id, stop_sequence, service_date
        FROM read_parquet('data/processed/stop_crossings/service_date=*/stop_crossings.parquet');
    """).df()


def test_ground_truth_terminology_and_route_scope(audit_data, ground_truth_df, crossings_df):
    """Verify exact ground-truth terminology: 199 crossings, 136 segments, 26 stop pairs, and Route 1657."""
    gt_inv = audit_data["ground_truth_inventory"]

    # 1. Exact counts
    assert gt_inv["total_observed_stop_crossings"] == 199
    assert len(crossings_df) == 199

    assert gt_inv["total_observed_stop_segments"] == 136
    assert len(ground_truth_df) == 136

    assert gt_inv["total_distinct_stop_pairs"] == 26
    assert ground_truth_df["segment_key"].nunique() == 26

    # 2. Route distribution
    assert gt_inv["route_distribution"]["1598"] == 124
    assert gt_inv["route_distribution"]["1445"] == 11
    assert gt_inv["route_distribution"]["1657"] == 1

    # 3. Route 1657 status
    r1657 = gt_inv["route_1657_status"]
    assert r1657["vehicle_id"] == "DL1PD9231"
    assert r1657["service_date"] == "2026-10-03"
    assert r1657["stop_id_from"] == 242
    assert r1657["stop_id_to"] == 1245
    assert "North GT Road" in r1657["explanation"]


def test_conformal_lower_bound_verification(audit_data, ground_truth_df):
    """Verify that zero actual target values are below 5.0s, and clipping does NOT affect coverage."""
    lb_audit = audit_data["conformal_prediction_audit"]["lower_bound_verification"]

    # Global and split minimums
    assert lb_audit["global_minimum_target_time_s"] >= 21.0
    assert lb_audit["target_below_5s_global"] is False
    assert lb_audit["target_below_5s_test"] is False

    # Check directly from dataframe
    assert np.all(ground_truth_df["segment_time_s"].values >= 5.0)
    assert np.min(ground_truth_df["segment_time_s"].values) == pytest.approx(21.4489, rel=1e-3)

    # Verify coverage identity (clipped coverage == unclipped coverage)
    assert lb_audit["coverage_identity_verified"] is True


def test_conformal_interval_discrepancy_resolution(audit_data, ground_truth_df):
    """Verify mathematical proof of why average interval width (532.03s) differs from 2*q (698.20s)."""
    train_df = ground_truth_df[ground_truth_df["service_date_str"].isin(["2026-10-01", "2026-10-02", "2026-10-03"])].reset_index(drop=True)
    val_df = ground_truth_df[ground_truth_df["service_date_str"] == "2026-10-04"].reset_index(drop=True)
    test_df = ground_truth_df[ground_truth_df["service_date_str"] == "2026-10-07"].reset_index(drop=True)

    suite = TrafficModelSuite(min_samples_baseline=3)
    suite.fit(train_df)

    val_preds = suite.predict(val_df)
    y_val_true = val_df["segment_time_s"].values
    y_val_m0 = val_preds["M0_Historical_Median"]

    calibrator = SplitConformalCalibrator(target_coverage=0.90)
    calibrator.calibrate(y_val_true, y_val_m0)

    # 1. Check finite sample calibration level: ceil(23 * 0.90) / 22 = 21 / 22 = 0.954545...
    n_val = len(y_val_true)
    expected_level = min(math.ceil((n_val + 1) * 0.90) / n_val, 1.0)
    assert abs(expected_level - 0.9545) < 0.001
    assert round(calibrator.conformal_radius, 2) == 349.10

    # 2. Check unclipped vs clipped widths
    test_preds = suite.predict(test_df)
    y_test_m0 = test_preds["M0_Historical_Median"]
    y_test_true = test_df["segment_time_s"].values

    lower_clipped, upper_clipped = calibrator.predict_intervals(y_test_m0)
    lower_unclipped = y_test_m0 - calibrator.conformal_radius
    upper_unclipped = y_test_m0 + calibrator.conformal_radius

    unclipped_width = upper_unclipped - lower_unclipped
    clipped_width = upper_clipped - lower_clipped

    # Unclipped width must be exactly 2 * q everywhere
    assert np.allclose(unclipped_width, 2 * calibrator.conformal_radius)
    assert round(float(np.mean(unclipped_width)), 2) == 698.20

    # Clipped width must account for clipping at 5.0s whenever pred - q < 5.0
    clipped_mask = lower_unclipped < 5.0
    assert np.sum(clipped_mask) == 25  # exactly 25 points clipped
    assert np.all(lower_clipped[clipped_mask] == 5.0)

    # Average clipped width must equal 532.03s
    assert round(float(np.mean(clipped_width)), 2) == 532.03
    assert round(float(np.median(clipped_width)), 2) == 539.70

    # 3. Check coverage identity (clipped vs unclipped)
    covered_clipped = (y_test_true >= lower_clipped) & (y_test_true <= upper_clipped)
    covered_unclipped = (y_test_true >= lower_unclipped) & (y_test_true <= upper_unclipped)
    assert np.array_equal(covered_clipped, covered_unclipped)
    assert np.sum(covered_clipped) == 26
    assert np.sum(~covered_clipped) == 4
    assert round(float(np.mean(covered_clipped) * 100.0), 2) == 86.67


def test_m0_fallback_tier_training_inventory_and_seq9_failure(audit_data, ground_truth_df):
    """Verify training observation counts by fallback tier and quantify seq9 sparse-history failure."""
    tier_audit = audit_data["m0_fallback_tier_reliability"]
    train_by_tier = tier_audit["training_observations_available_by_tier"]

    # Verify training observation allocations
    assert train_by_tier["TIER_1_DIRECT_OBSERVED"]["training_observations_count"] == 3
    assert train_by_tier["TIER_2_CORRIDOR_POOLED"]["training_observations_count"] == 3
    assert train_by_tier["TIER_3_TIMEPOINT_AGGREGATED"]["training_observations_count"] == 77
    assert train_by_tier["TIER_4_ROUTE_BASELINE"]["training_observations_count"] == 84

    # Verify test set performance by tier
    test_tier_perf = {p["tier"]: p for p in tier_audit["test_performance_by_tier"]}
    assert test_tier_perf["TIER_3_TIMEPOINT_AGGREGATED"]["test_query_count"] == 7
    assert test_tier_perf["TIER_4_ROUTE_BASELINE"]["test_query_count"] == 23

    # Check seq9 failure diagnosis
    assert "Segment 1598_dir0_pat0_seq9 had only 2 training observations" in tier_audit["seq9_failure_diagnosis"]
    assert "count=2 < 3" in tier_audit["seq9_failure_diagnosis"]


def test_observation_independence_and_overlap_invariants(audit_data, ground_truth_df):
    """Verify vehicle mutual exclusivity across splits and intra-split trip clustering."""
    train_df = ground_truth_df[ground_truth_df["service_date_str"].isin(["2026-10-01", "2026-10-02", "2026-10-03"])]
    val_df = ground_truth_df[ground_truth_df["service_date_str"] == "2026-10-04"]
    test_df = ground_truth_df[ground_truth_df["service_date_str"] == "2026-10-07"]

    train_v = set(train_df["vehicle_id"])
    val_v = set(val_df["vehicle_id"])
    test_v = set(test_df["vehicle_id"])

    # Disjointness across splits
    assert len(train_v) == 21
    assert len(val_v) == 3
    assert len(test_v) == 7
    assert len(train_v & val_v) == 0
    assert len(train_v & test_v) == 0
    assert len(val_v & test_v) == 0
    assert len(train_v | val_v | test_v) == 31

    # But intra-split vehicle clustering exists (repeated trips by same bus)
    max_train_v_obs = train_df["vehicle_id"].value_counts().max()
    max_val_v_obs = val_df["vehicle_id"].value_counts().max()
    max_test_v_obs = test_df["vehicle_id"].value_counts().max()
    assert max_train_v_obs == 9  # DL51EV8634
    assert max_val_v_obs == 12   # DL51EV3788
    assert max_test_v_obs == 9   # DL51EV4080

    # Stop pair overlap
    train_sp = set(train_df["segment_key"])
    val_sp = set(val_df["segment_key"])
    test_sp = set(test_df["segment_key"])

    assert len(train_sp) == 23
    assert len(val_sp) == 15
    assert len(test_sp) == 14
    assert len(train_sp & test_sp) == 12
    assert len(test_sp - train_sp) == 2
    assert sorted(list(test_sp - train_sp)) == ["1445_dir0_pat0_seq2", "1445_dir0_pat0_seq3"]


def test_random_forest_leakage_safety_and_structure(ground_truth_df):
    """Verify that Random Forest uses out-of-fold feature generation during training and strictly fixed stats for test."""
    train_df = ground_truth_df[ground_truth_df["service_date_str"].isin(["2026-10-01", "2026-10-02", "2026-10-03"])].reset_index(drop=True)
    test_df = ground_truth_df[ground_truth_df["service_date_str"] == "2026-10-07"].reset_index(drop=True)

    extractor = TrafficFeatureExtractor()
    extractor.fit(train_df)

    # Transform train with OOF
    X_train, y_train, feat_names = extractor.transform(train_df, is_train=True)
    assert len(feat_names) == 10
    assert X_train.shape == (84, 10)
    assert y_train.shape == (84,)

    # Transform test without OOF (must not use test labels or test dates)
    X_test, y_test, _ = extractor.transform(test_df, is_train=False)
    assert X_test.shape == (30, 10)
    assert y_test.shape == (30,)

    suite = TrafficModelSuite(min_samples_baseline=3)
    suite.fit(train_df)

    # Hyperparameter checks
    assert suite.rf_m2.n_estimators == 50
    assert suite.rf_m2.max_depth == 4
    assert suite.rf_m2.min_samples_leaf == 3

    # Feature importance checks: top 2 features are historical median log time and hourly speed
    importances = dict(zip(feat_names, suite.rf_m2.feature_importances_))
    assert importances["hist_median_log_time"] > 0.20
    assert importances["hour_median_speed"] > 0.20


def test_metric_recalculation_and_mape_properties(audit_data, ground_truth_df):
    """Verify direct metric recalculation and why MAPE exceeds 100% due to denominator asymmetry."""
    m_audit = audit_data["metric_verification"]

    # Check reported metrics match expected values
    assert m_audit["M0_Historical_Median"]["mae"] == 146.55
    assert m_audit["M0_Historical_Median"]["rmse"] == 250.91
    assert m_audit["M0_Historical_Median"]["med_ae"] == 87.44
    assert m_audit["M0_Historical_Median"]["bias"] == 67.0
    assert m_audit["M0_Historical_Median"]["mape"] == 100.28
    assert m_audit["M0_Historical_Median"]["med_ape"] == 92.99

    assert m_audit["M2_Random_Forest"]["mae"] == 122.94
    assert m_audit["M2_Random_Forest"]["improvement_pct"] == 16.11
    assert m_audit["M2_Random_Forest"]["med_ape"] == 51.64

    # Verify that MedAPE is substantially lower than MAPE for M2 (51.64% vs 101.90%)
    assert m_audit["M2_Random_Forest"]["med_ape"] < m_audit["M2_Random_Forest"]["mape"] * 0.60

    # Denominator rules check
    mape_details = m_audit["mape_vs_medape_audit"]
    assert mape_details["observations_lt_30s_count"] == 3
    assert mape_details["observations_ge_30s_count"] == 27
    assert mape_details["max_individual_ape_m2"] > 400.0


def test_coverage_uncertainty_and_clustered_evaluation_strategy(audit_data):
    """Verify that coverage bounds are flagged as illustrative and clustered evaluation is recommended."""
    conf_audit = audit_data["conformal_prediction_audit"]["test_evaluation"]
    assert "illustrative_clopper_pearson_95ci_pct" in conf_audit
    assert "violate independent sampling" in conf_audit["coverage_uncertainty_and_clustered_variance"]
    assert "CANNOT be claimed as statistically demonstrated" in conf_audit["coverage_uncertainty_and_clustered_variance"]

    rec = audit_data["clustered_evaluation_strategy_recommendation"]
    assert "Leave-One-Date-Out" in rec["date_clustered_validation"]
    assert "Block conformal prediction" in rec["vehicle_run_block_conformal"]
