"""Automated Verification Tests for Milestone 2.2.1 Audit & Corrections.

Verifies:
1. Exact mutually exclusive duplicate/quarantine accounting across all pilot dates.
2. Global distinct vehicle, stop pair, route, and segment counts from underlying Parquet files.
3. 24-hour coverage table consistency and zero-observation hour detection.
4. October 7 outage gap timestamps and resumption interval.
5. Detour factor calibration metadata and corridor constraints.
"""

import json
import os
import duckdb
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AUDIT_METRICS_PATH = os.path.join(ROOT_DIR, "data", "processed", "milestone2_2_1_audit_metrics.json")
STOP_CROSSING_DIR = os.path.join(ROOT_DIR, "data", "processed", "stop_crossings")

@pytest.fixture(scope="module")
def audit_metrics():
    assert os.path.exists(AUDIT_METRICS_PATH), "Audit metrics JSON missing"
    with open(AUDIT_METRICS_PATH, "r") as f:
        return json.load(f)

def test_date_inventory_accounting(audit_metrics):
    """Verify that all 31 October days are inventoried with exact status."""
    inv = audit_metrics["date_inventory_summary"]
    assert inv["total_archive_dates"] == 31
    assert inv["pilot_dates_processed"] == 5
    assert inv["unprocessed_dates"] == 26
    assert len(inv["dates"]) == 31

    pilot_dates = {"2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-07"}
    for d in inv["dates"]:
        if d["service_date"] in pilot_dates:
            assert d["ingestion_successful"] is True
        else:
            assert d["ingestion_successful"] is False
            assert "disk" in d["reason_if_unprocessed"].lower()

def test_mutually_exclusive_quarantine_accounting(audit_metrics):
    """Verify that every raw observation is accounted for with zero double-counting."""
    q_audit = audit_metrics["reconciled_quarantine_accounting"]
    assert q_audit["accounting_is_exact"] is True

    total_raw = q_audit["total_raw_observations"]
    total_clean = q_audit["clean_retained_rows"]
    total_ident = q_audit["metadata_identical_telemetry_repeats"]
    total_gen = q_audit["genuine_conflicting_telemetry"]
    total_peer = q_audit["rule_e02_peer_oob_drops"]
    total_oob = q_audit["rule_e03_spatial_out_of_bounds"]

    assert total_raw == 147869768
    assert total_clean + total_ident + total_gen + total_peer + total_oob == total_raw

    # Verify per-day exact sum
    for day in q_audit["daily_accounting"]:
        assert day["matches_raw"] is True
        assert (day["clean_retained"] + day["identical_telemetry_repeats"] +
                day["genuine_conflicting_telemetry"] + day["rule_e02_peer_oob_drops"] +
                day["rule_e03_out_of_bounds"]) == day["raw_observations"]

def test_global_ground_truth_counts(audit_metrics):
    """Verify true global unique entities against combined underlying Parquet files."""
    gt = audit_metrics["global_ground_truth"]
    con = duckdb.connect()

    # Query directly from Parquet files
    res = con.execute("""
        SELECT 
            COUNT(*) as total_segs,
            COUNT(DISTINCT vehicle_id) as n_vehicles,
            COUNT(DISTINCT segment_key) as n_stop_pairs,
            COUNT(DISTINCT route_id) as n_routes
        FROM read_parquet('data/processed/stop_crossings/service_date=*/observed_segments.parquet')
    """).fetchone()

    assert gt["total_observed_segments"] == res[0] == 136
    assert gt["globally_distinct_vehicles"] == res[1] == 31
    assert gt["globally_distinct_physical_stop_pairs"] == res[2] == 26
    assert gt["globally_distinct_routes"] == res[3] == 3

def test_hourly_coverage_zero_hours(audit_metrics):
    """Verify hourly observations and detection of unobserved hours."""
    h_audit = audit_metrics["hourly_coverage"]
    zero_hours = set(h_audit["zero_observation_hours"])
    expected_zero = {0, 1, 2, 3, 4, 5, 6, 11, 19, 22, 23}
    assert zero_hours == expected_zero

    # Ensure all 24 hours are accounted for
    assert len(h_audit["table"]) == 24

def test_october_7_outage_bounds(audit_metrics):
    """Verify October 7 outage gap calculation and resumption interval."""
    o7 = audit_metrics["october_7_outage"]
    assert o7["outage_duration_seconds"] == 22127
    assert pytest.approx(o7["outage_duration_hours"], 0.01) == 6.15
    assert o7["pings_after_142323_utc_in_oct7_partition"] == 0
    assert o7["segments_before_142323_ist"] == 20
    assert o7["segments_after_142323_ist"] == 10

def test_detour_calibration_constraints(audit_metrics):
    """Verify detour calibration limitations and corridor specificity."""
    detour = audit_metrics["detour_calibration"]
    assert len(detour["sections"]) == 8
    for sec in detour["sections"]:
        assert sec["ratio"] > 1.0
        assert "status" in sec
    assert "cannot be applied as a validated network-wide median" in detour["limitations"]

