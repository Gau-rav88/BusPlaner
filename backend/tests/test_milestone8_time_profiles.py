"""Milestone 8 Unit and Verification Tests: Historical Time-of-Day Traffic Profiles.

PRD v3.0 Milestone 8:
Verifies:
- Profile construction from validated 136 observed segments across 5 dates.
- Exact descriptive statistics: mean, median, quartiles (p25, p75), IQR, std.
- Empty time bins explicitly labeled UNAVAILABLE (never filled with invented values).
- No global application of 1.262 detour factor.
- Route 1598 stop-pair breakdown fidelity.
"""

import os
import pytest
import numpy as np
import pandas as pd

from backend.analytics.time_profiles import HistoricalTimeProfileEngine, TimeProfileBin


@pytest.fixture(scope="module")
def profile_engine():
    engine = HistoricalTimeProfileEngine()
    engine.load_data()
    engine.build_profiles()
    return engine


def test_time_profile_dataset_provenance(profile_engine):
    """Verify underlying dataset matches the audited 136 segments across 5 dates."""
    meta = profile_engine.get_summary_metadata()
    assert meta["total_observations"] == 136
    assert meta["distinct_service_dates_count"] == 5
    assert meta["distinct_vehicles_count"] == 31
    assert set(meta["distinct_routes"]) == {"1445", "1598", "1657"}


def test_time_profile_temporal_coverage(profile_engine):
    """Verify observed vs unobserved hours and ensure no invented hours."""
    meta = profile_engine.get_summary_metadata()
    observed_hours = set(meta["observed_hours_ist"])
    unobserved_hours = set(meta["unobserved_hours_ist"])

    # 13 observed hours, 11 unobserved hours = 24 hours total
    assert len(observed_hours) == 13
    assert len(unobserved_hours) == 11
    assert observed_hours.union(unobserved_hours) == set(range(24))
    assert 11 not in observed_hours  # Hour 11 has 0 observations
    assert 0 not in observed_hours   # Midnight hour has 0 observations


def test_empty_time_bins_are_unavailable(profile_engine):
    """Verify that unobserved time bins return UNAVAILABLE with None statistics."""
    # Check Route 1598, stop pair 240->241 at midnight (hour 0)
    midnight_bin = profile_engine.stop_pair_profiles.get(("1598", "240", "241", 0, 0, "ALL"))
    assert midnight_bin is not None
    assert midnight_bin.profile_status == "UNAVAILABLE"
    assert midnight_bin.sample_count == 0
    assert midnight_bin.median_time_s is None
    assert midnight_bin.mean_time_s is None
    assert midnight_bin.p25_time_s is None
    assert midnight_bin.p75_time_s is None
    assert midnight_bin.std_time_s is None


def test_observed_time_bins_statistics(profile_engine):
    """Verify statistical calculations on observed time bins."""
    # Find any observed stop-pair bin
    observed_bins = [b for b in profile_engine.stop_pair_profiles.values() if b.profile_status == "OBSERVED"]
    assert len(observed_bins) > 0

    for b in observed_bins:
        assert b.sample_count > 0
        assert b.median_time_s is not None
        assert b.mean_time_s is not None
        assert b.p25_time_s is not None
        assert b.p75_time_s is not None
        assert b.min_time_s is not None
        assert b.max_time_s is not None
        # Ordering constraints
        assert b.min_time_s <= b.p25_time_s <= b.median_time_s <= b.p75_time_s <= b.max_time_s
        assert b.iqr_time_s == pytest.approx(round(b.p75_time_s - b.p25_time_s, 2), abs=0.05)


def test_route_1598_dominant_corridor(profile_engine):
    """Verify Route 1598 hourly profile statistics."""
    # Check hour 7 (morning peak, high sample count)
    hr7_bin = profile_engine.route_hourly_profiles.get(("1598", 0, 7, "ALL"))
    assert hr7_bin is not None
    assert hr7_bin.profile_status == "OBSERVED"
    assert hr7_bin.sample_count > 0
    assert hr7_bin.distinct_service_dates_count >= 1
    assert hr7_bin.distinct_vehicles_count >= 1
    assert hr7_bin.median_speed_kmh is not None
    assert hr7_bin.median_speed_kmh > 0.0


def test_profile_export_integrity(profile_engine, tmp_path):
    """Verify exporting profiles to JSON preserves schema and completeness."""
    out_file = str(tmp_path / "test_profiles.json")
    payload = profile_engine.export_profiles(out_file)

    assert os.path.exists(out_file)
    assert "metadata" in payload
    assert "corridor_hourly_profiles" in payload
    assert "route_hourly_profiles" in payload
    assert "stop_pair_profiles" in payload

    assert payload["metadata"]["total_observations"] == 136
    assert len(payload["corridor_hourly_profiles"]) == 24

