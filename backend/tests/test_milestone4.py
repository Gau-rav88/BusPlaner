"""Automated Tests for Milestone 4 Extended Model Validation.

Verifies:
1. Reporting corrections: exact MAPE/MedAPE filtering (n=27 included, n=3 excluded), identical filtering across models, unfiltered metric preservation.
2. Dataset readiness: 5 dates, 136 segments, 199 crossings, 31 vehicles, 26 stop pairs, storage capacity accounting.
3. Model validation: test evaluation (Oct 7), validation evaluation (Oct 4), route and period breakdowns, XGBoost omission justification.
4. Prediction interval validation: conformal radius and width, vehicle-run calibration limits.
5. Generalization & fallback: unseen stop pairs, sparse history link seq9, evening peak congestion outliers.
"""

import json
import os
import duckdb
import numpy as np
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
M4_METRICS_PATH = os.path.join(ROOT_DIR, "data", "processed", "milestone4_metrics.json")


@pytest.fixture(scope="module")
def m4_data():
    assert os.path.exists(M4_METRICS_PATH), f"Milestone 4 metrics file not found: {M4_METRICS_PATH}"
    with open(M4_METRICS_PATH, "r") as f:
        return json.load(f)


def test_reporting_corrections_mape_filtering(m4_data):
    """Verify exact filtering for percentage metrics: 27 included, 3 excluded, identical across models."""
    rep_corr = m4_data["reporting_corrections"]
    assert rep_corr["total_test_observations"] == 30
    assert rep_corr["included_in_mape_medape_count"] == 27
    assert rep_corr["excluded_from_mape_medape_count"] == 3
    assert rep_corr["identical_filtering_across_models"] is True
    assert rep_corr["unfiltered_error_metrics_preserved"] is True

    # Check excluded records
    excluded = rep_corr["excluded_observations_details"]
    assert len(excluded) == 3
    for exc in excluded:
        assert exc["actual_time_s"] < 30.0

    # Check model validation summary preserves both unfiltered and filtered counts
    test_eval = m4_data["model_validation_summary"]["test_partition_evaluation_october_7"]
    for m_key in ["M0_Historical_Median", "M1_Ridge_Regression", "M2_Random_Forest"]:
        m = test_eval[m_key]
        assert m["unfiltered_sample_count"] == 30
        assert m["filtered_mape_sample_count"] == 27
        assert m["excluded_mape_sample_count"] == 3


def test_dataset_readiness_and_storage_accounting(m4_data):
    """Verify dataset readiness inventory and storage constraint documentation."""
    readiness = m4_data["dataset_readiness"]
    assert readiness["usable_dates_count"] == 5
    assert readiness["usable_dates"] == ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-07"]
    assert readiness["total_observed_stop_crossings"] == 199
    assert readiness["total_observed_segments"] == 136
    assert readiness["total_distinct_stop_pairs"] == 26
    assert readiness["total_distinct_vehicles"] == 31
    assert readiness["total_distinct_routes"] == 3

    # Storage audit
    storage = readiness["storage_audit"]
    assert storage["can_safely_process_remaining_dates"] is False
    assert storage["host_disk_free_gb"] < 15.0  # Cannot fit 115 GB uncompressed archive
    assert "storage exhaustion" in storage["storage_justification"]


def test_model_validation_and_chronological_splits(m4_data):
    """Verify model performance on both test (Oct 7) and validation (Oct 4) partitions."""
    m_summary = m4_data["model_validation_summary"]

    # Test evaluation (Oct 7, Wednesday)
    test_m = m_summary["test_partition_evaluation_october_7"]
    assert test_m["sample_count"] == 30
    assert test_m["M0_Historical_Median"]["mae_s"] == 146.55
    assert test_m["M1_Ridge_Regression"]["mae_s"] == 142.64
    assert test_m["M2_Random_Forest"]["mae_s"] == 122.94
    assert test_m["M2_Random_Forest"]["improvement_over_m0_pct"] == 16.11

    # Validation evaluation (Oct 4, Sunday)
    val_m = m_summary["validation_partition_evaluation_october_4"]
    assert val_m["sample_count"] == 22
    assert val_m["M0_Historical_Median"]["mae_s"] == 128.81
    assert val_m["M2_Random_Forest"]["mae_s"] == 65.56
    assert val_m["M2_Random_Forest"]["improvement_over_m0_pct"] > 40.0  # Sunday weekend effect captured by RF

    # XGBoost status
    xgb_status = m_summary["xgboost_evaluation_status"]
    assert xgb_status["installed_in_environment"] is False
    assert "scientifically inappropriate" in xgb_status["scientific_justification"]


def test_granular_breakdowns(m4_data):
    """Verify breakdowns by route, period, tier, and stop pair."""
    breakdowns = m4_data["granular_breakdowns_on_held_out_test"]

    # Route breakdown
    routes = {r["route_id"]: r for r in breakdowns["route_performance"]}
    assert "1598" in routes and "1445" in routes
    assert routes["1598"]["sample_count"] == 22
    assert routes["1445"]["sample_count"] == 8

    # Period breakdown
    periods = {p["period"]: p for p in breakdowns["period_performance"]}
    assert "MORNING_PEAK" in periods and "EVENING_PEAK" in periods
    assert periods["MORNING_PEAK"]["sample_count"] == 16
    assert periods["EVENING_PEAK"]["sample_count"] == 9
    assert periods["OFF_PEAK"]["sample_count"] == 5

    # Fallback tier breakdown
    tiers = {t["tier"]: t for t in breakdowns["fallback_tier_performance"]}
    assert "TIER_4_ROUTE_BASELINE" in tiers and "TIER_3_TIMEPOINT_AGGREGATED" in tiers
    assert tiers["TIER_4_ROUTE_BASELINE"]["sample_count"] == 23
    assert tiers["TIER_3_TIMEPOINT_AGGREGATED"]["sample_count"] == 7

    # Stop pair breakdown
    stop_pairs = breakdowns["stop_pair_performance"]
    assert len(stop_pairs) == 14


def test_prediction_interval_validation_and_vehicle_run_limits(m4_data):
    """Verify conformal interval metrics and vehicle-run level calibration feasibility limits."""
    conf = m4_data["prediction_interval_validation"]
    assert conf["calibrated_conformal_radius_s"] == 349.10
    assert conf["average_clipped_width_s"] == 532.03
    assert conf["theoretical_unclipped_width_s"] == 698.20
    assert conf["empirical_coverage_pct"] == 86.67
    assert conf["covered_observations_count"] == 26
    assert conf["outside_observations_count"] == 4

    # Vehicle-run feasibility
    v_feas = conf["vehicle_run_calibration_feasibility"]
    assert v_feas["validation_unique_vehicles_count"] == 3
    assert v_feas["is_vehicle_run_conformal_statistically_feasible"] is False
    assert "impossible with n=3" in v_feas["feasibility_assessment"]


def test_generalization_and_fallback_diagnostics(m4_data):
    """Verify diagnostics for unseen stop pairs, sparse history link seq9, and evening congestion."""
    gen = m4_data["generalization_and_fallback_diagnostics"]

    # Unseen stop pairs
    unseen = {u["segment_key"]: u for u in gen["unseen_stop_pairs"]}
    assert "1445_dir0_pat0_seq2" in unseen
    assert "1445_dir0_pat0_seq3" in unseen
    assert unseen["1445_dir0_pat0_seq2"]["training_sample_count"] == 0

    # Sparse history link seq9
    seq9 = gen["sparse_history_links"]["link_1598_seq9"]
    assert seq9["training_sample_count"] == 2
    assert seq9["test_sample_count"] == 3
    assert seq9["m0_mae_s"] > 400.0
    assert seq9["m2_mae_s"] < 100.0

    # Peak hour congestion outlier
    outliers = gen["peak_hour_congestion_outliers"]
    assert len(outliers) >= 1
    assert outliers[0]["actual_time_s"] > 1600.0
    assert outliers[0]["hour_ist"] == 17

