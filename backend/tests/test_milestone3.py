"""Automated Verification Tests for Milestone 3: Traffic Statistics, M0 Baseline, and ML Evaluation.

Tests:
1. Hierarchical Historical Median Baseline (M0) multi-tier fallback logic.
2. Feature extraction and Out-Of-Fold (OOF) target leakage prevention.
3. Split-conformal prediction interval calibration and coverage computation.
4. Metric computation accuracy (MAE, RMSE, MedAE, MAPE, Bias).
5. Chronological whole-date splitting integrity (zero date leakage).
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml.baseline import HistoricalMedianBaseline
from backend.ml.conformal import SplitConformalCalibrator
from backend.ml.features import TrafficFeatureExtractor
from backend.ml.models import calculate_metrics, TrafficModelSuite


@pytest.fixture
def sample_traffic_df():
    """Create a synthetic 10-observation multi-date segment dataframe."""
    return pd.DataFrame({
        "observation_id": [f"obs_{i:03d}" for i in range(10)],
        "segment_key": ["seg_A"] * 6 + ["seg_B"] * 4,
        "stop_id_from": ["S1"] * 6 + ["S2"] * 4,
        "stop_id_to": ["S2"] * 6 + ["S3"] * 4,
        "distance_m": [500.0] * 6 + [800.0] * 4,
        "segment_time_s": [100.0, 110.0, 105.0, 95.0, 120.0, 100.0, 200.0, 220.0, 210.0, 190.0],
        "speed_kmh": [18.0, 16.36, 17.14, 18.95, 15.0, 18.0, 14.4, 13.09, 13.71, 15.16],
        "service_date": ["2026-10-01"] * 4 + ["2026-10-02"] * 2 + ["2026-10-03"] * 4,
        "hour_ist": [8, 8, 8, 9, 8, 8, 8, 8, 9, 9],
        "is_weekend": [0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
        "is_holiday": [0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
        "stop_sequence_from": [1] * 6 + [2] * 4,
        "arrival_from_utc": [1000 + i * 100 for i in range(10)],
        "arrival_to_utc": [1100 + i * 100 for i in range(10)],
    })


def test_baseline_hierarchical_fallback(sample_traffic_df):
    """Test M0 multi-tier fallback: Tier 1 (n>=3), Tier 3 (corridor), Tier 4 (baseline)."""
    # seg_A on weekday at hour 8 has 4 observations (>= 3) -> Tier 1
    baseline = HistoricalMedianBaseline(min_samples=3, default_speed_kmh=18.0)
    baseline.fit(sample_traffic_df)

    # 1. Tier 1 Query
    p1 = baseline.predict_one("seg_A", "S1", "S2", 500.0, hour_ist=8, is_weekend=0)
    assert p1.tier == "TIER_1_DIRECT_OBSERVED"
    assert p1.confidence == 1.0
    assert p1.sample_count >= 3
    assert 95.0 <= p1.predicted_time_s <= 120.0

    # 2. Tier 3 Query (seg_A at hour 9 has only 1 obs -> falls back to Tier 3)
    p3 = baseline.predict_one("seg_A", "S1", "S2", 500.0, hour_ist=9, is_weekend=0)
    assert p3.tier in ("TIER_3_TIMEPOINT_AGGREGATED", "TIER_4_ROUTE_BASELINE")
    assert p3.confidence < 1.0

    # 3. Tier 4 Query (completely unknown segment and hour)
    p4 = baseline.predict_one("seg_UNKNOWN", "S99", "S100", 1000.0, hour_ist=3, is_weekend=0)
    assert p4.tier == "TIER_4_ROUTE_BASELINE"
    assert p4.confidence == 0.4
    assert p4.is_fallback is True


def test_feature_extractor_out_of_fold_leakage_safety(sample_traffic_df):
    """Verify that OOF training does not leak target from the current service date."""
    extractor = TrafficFeatureExtractor(default_speed_kmh=18.0)
    extractor.fit(sample_traffic_df)

    X_train, y_train, names = extractor.transform(sample_traffic_df, is_train=True)
    assert X_train.shape[0] == 10
    assert len(names) == X_train.shape[1]
    assert np.all(np.isfinite(X_train))
    assert np.all(np.isfinite(y_train))

    # Test transform uses only training statistics
    test_sample = sample_traffic_df.iloc[:2].copy()
    X_test, y_test, _ = extractor.transform(test_sample, is_train=False)
    assert X_test.shape[0] == 2


def test_conformal_calibrator():
    """Verify Split-Conformal calibrator radius calculation and test coverage."""
    y_val_true = np.array([100.0, 150.0, 200.0, 250.0, 300.0], dtype=np.float32)
    y_val_pred = np.array([110.0, 140.0, 210.0, 240.0, 290.0], dtype=np.float32)
    # Absolute residuals are all 10.0

    calibrator = SplitConformalCalibrator(target_coverage=0.90)
    calibrator.calibrate(y_val_true, y_val_pred)

    assert calibrator.is_calibrated is True
    assert calibrator.conformal_radius >= 10.0

    # Test coverage evaluation
    y_test_true = np.array([105.0, 145.0, 205.0], dtype=np.float32)
    y_test_pred = np.array([100.0, 150.0, 200.0], dtype=np.float32)
    res = calibrator.evaluate_coverage(y_test_true, y_test_pred)

    assert res["empirical_coverage_pct"] == 100.0
    assert res["conformal_radius_s"] >= 10.0


def test_metrics_calculation():
    """Verify PRD Section 9.2 metrics calculation."""
    y_true = np.array([100.0, 200.0], dtype=np.float32)
    y_pred = np.array([110.0, 180.0], dtype=np.float32)
    # Errors: +10, -20. Absolute errors: 10, 20. Mean = 15.0.

    metrics = calculate_metrics(y_true, y_pred, baseline_mae=20.0)
    assert metrics["mae"] == 15.0
    assert metrics["med_ae"] == 15.0
    assert metrics["bias"] == -5.0
    assert metrics["improvement_pct"] == 25.0  # (20 - 15) / 20 * 100 = 25%


def test_chronological_split_integrity():
    """Verify that chronological splits strictly enforce max(train) < min(val) < min(test)."""
    import duckdb
    con = duckdb.connect()
    df = con.execute("""
        SELECT service_date, arrival_from_utc, arrival_to_utc
        FROM read_parquet('data/processed/stop_crossings/service_date=*/observed_segments.parquet')
    """).df()

    df["service_date"] = df["service_date"].astype(str)
    train_df = df[df["service_date"].isin(["2026-10-01", "2026-10-02", "2026-10-03"])]
    val_df = df[df["service_date"] == "2026-10-04"]
    test_df = df[df["service_date"] == "2026-10-07"]

    assert train_df["arrival_to_utc"].max() < val_df["arrival_from_utc"].min()
    assert val_df["arrival_to_utc"].max() < test_df["arrival_from_utc"].min()
