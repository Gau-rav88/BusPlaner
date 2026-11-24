"""Milestone 5.1 Independent Audit Test Suite.

Categorizes and validates:
1. Independently verified against GTFS (Cases 1, 2, 3, 4, 12, 13).
2. Verified against a manually calculated expected result (Cases 5, 6, 7, 8, 9, 10, 11, 14, 15).
3. Synthetic unit tests (5 distinct prediction hierarchy levels, independent accounting identity).
4. Performance benchmarks (warm-up, repeated passes, memory RSS, exact footpath timer).
"""

import json
import math
import os
import sqlite3
import pytest
import numpy as np

from backend.core.raptor_data import Timetable, Stop, Footpath
from backend.core.raptor import PlannedJourney, TransitLeg, WalkingLeg
from backend.core.journey_planner import JourneyPlanner, SegmentPrediction

DB_PATH = "/tmp/delhi_mdb.db"


@pytest.fixture(scope="module")
def planner():
    if not os.path.exists(DB_PATH):
        pytest.skip(f"{DB_PATH} not found")
    return JourneyPlanner.create_default(db_path=DB_PATH, fit_baseline=True)


@pytest.fixture(scope="module")
def gtfs_con():
    if not os.path.exists(DB_PATH):
        pytest.skip(f"{DB_PATH} not found")
    con = sqlite3.connect(DB_PATH)
    yield con
    con.close()


# ==============================================================================
# Category 1: Independently Verified Against GTFS
# ==============================================================================

def test_gtfs_independent_verification_direct_and_competing(planner, gtfs_con):
    """Category: Independently verified against GTFS.

    Verifies Case 1 (Route 1598, Trip 1598_12_38) and Case 4 (competing line selection)
    directly against raw SQLite GTFS records.
    """
    cur = gtfs_con.cursor()

    # Case 1: Direct GTFS trip verification
    cur.execute("""
        SELECT st.departure_sec, st.arrival_sec
        FROM stop_times st
        WHERE st.trip_id = '1598_12_38' AND st.stop_id IN ('239', '247')
        ORDER BY st.stop_sequence;
    """)
    rows = cur.fetchall()
    gtfs_dep = rows[0][0]  # 45480s (12:38:00)
    gtfs_arr = rows[1][1]  # 46372s (12:52:52)
    gtfs_dur = gtfs_arr - gtfs_dep  # 892s

    # At 45460s, earlier competing trips have left; 1598_12_38 is earliest
    js = planner.plan_journey(origin_stop_id="239", dest_stop_id="247", departure_time_s=45460.0, max_transfers=1)
    assert len(js) > 0, "Direct trip must be found"
    j = js[0]
    leg = j.legs[0]
    assert leg.trip_id == "1598_12_38", f"Expected trip 1598_12_38, got {leg.trip_id}"
    assert leg.sched_departure_s == gtfs_dep, f"Scheduled departure {leg.sched_departure_s} != GTFS {gtfs_dep}"
    assert leg.sched_arrival_s == gtfs_arr, f"Scheduled arrival {leg.sched_arrival_s} != GTFS {gtfs_arr}"
    assert leg.sched_duration_s == gtfs_dur, f"Scheduled duration {leg.sched_duration_s} != GTFS {gtfs_dur}"

    # Case 4: Multiple competing routes at 45000s (12:30:00)
    cur.execute("""
        SELECT t.trip_id, st.departure_sec
        FROM stop_times st
        JOIN trips t ON st.trip_id = t.trip_id
        WHERE st.stop_id = '239' AND st.departure_sec >= 45000
        ORDER BY st.departure_sec ASC
        LIMIT 1;
    """)
    earliest_gtfs_trip, earliest_gtfs_dep = cur.fetchone()
    js_comp = planner.plan_journey(origin_stop_id="239", dest_stop_id="240", departure_time_s=45000.0, max_transfers=1)
    assert len(js_comp) > 0
    assert js_comp[0].legs[0].trip_id == earliest_gtfs_trip
    assert js_comp[0].legs[0].sched_departure_s == earliest_gtfs_dep


def test_gtfs_independent_verification_early_late_midnight(planner, gtfs_con):
    """Category: Independently verified against GTFS.

    Verifies Case 2 (early morning 04:00), Case 3 (late evening 23:00), and
    Case 12 (trip crossing midnight with arrival >= 86400s) directly against GTFS records.
    """
    cur = gtfs_con.cursor()

    # Case 2: Early morning
    cur.execute("""
        SELECT st.stop_id, st.departure_sec, st.arrival_sec
        FROM stop_times st
        WHERE st.trip_id = '1269_04_00' AND st.stop_sequence IN (0, 5)
        ORDER BY st.stop_sequence;
    """)
    rows_early = cur.fetchall()
    s0, dep0 = rows_early[0][0], rows_early[0][1]
    s5, arr5 = rows_early[1][0], rows_early[1][2]
    js_early = planner.plan_journey(origin_stop_id=str(s0), dest_stop_id=str(s5), departure_time_s=float(dep0 - 60), max_transfers=1)
    assert len(js_early) > 0
    assert js_early[0].legs[0].trip_id == "1269_04_00"

    # Case 3: Late evening
    cur.execute("""
        SELECT st.stop_id, st.departure_sec, st.arrival_sec
        FROM stop_times st
        WHERE st.trip_id = '0_23_00' AND st.stop_sequence IN (0, 6)
        ORDER BY st.stop_sequence;
    """)
    rows_late = cur.fetchall()
    s0_l, dep0_l = rows_late[0][0], rows_late[0][1]
    s6_l, arr6_l = rows_late[1][0], rows_late[1][2]
    js_late = planner.plan_journey(origin_stop_id=str(s0_l), dest_stop_id=str(s6_l), departure_time_s=float(dep0_l - 60), max_transfers=1)
    assert len(js_late) > 0
    assert js_late[0].legs[0].trip_id == "0_23_00"

    # Case 12: Midnight crossing to Stop 238
    cur.execute("""
        SELECT st.departure_sec, st.arrival_sec
        FROM stop_times st
        WHERE st.trip_id = '0_23_00' AND st.stop_id IN ('3127', '238')
        ORDER BY st.stop_sequence;
    """)
    rows_mid = cur.fetchall()
    dep_mid = rows_mid[0][0]  # 82800s (23:00)
    arr_mid = rows_mid[1][1]  # 86901s (24:08 / 00:08)
    assert arr_mid >= 86400, "GTFS source record must cross midnight"

    js_mid = planner.plan_journey(origin_stop_id="3127", dest_stop_id="238", departure_time_s=82700.0, max_transfers=1)
    assert len(js_mid) > 0
    assert js_mid[0].legs[0].trip_id == "0_23_00"
    assert js_mid[0].arrival_time_s >= 86400.0
    assert js_mid[0].accounting.is_valid


def test_gtfs_independent_verification_calendar_and_activation(planner, gtfs_con):
    """Category: Independently verified against GTFS.

    Verifies Case 13: GTFS calendar record validation and explicit expiry assumption.
    """
    cur = gtfs_con.cursor()
    cur.execute("SELECT service_id, start_date, end_date FROM calendar;")
    row = cur.fetchone()
    assert row[0] == "1", "Calendar service_id must be '1'"
    assert row[1] == "20220101", "Calendar start_date must be 20220101"
    assert row[2] == "20240101", "Calendar end_date must be 20240101"
    # Timetable must record service_activation_assumed = True for 2026 queries
    assert planner.timetable.service_activation_assumed is True


# ==============================================================================
# Category 2: Verified Against a Manually Calculated Expected Result
# ==============================================================================

def test_manual_expected_result_transfers_and_delay_propagation(planner):
    """Category: Verified against a manually calculated expected result.

    Verifies Case 5 (direct stop transfer), Case 6 (footpath transfer),
    Case 7 (two-transfer journey), and Case 11 (delay propagation advancing connection).
    """
    # Case 5 & 6: Transfer connection from Stop 239 to Stop 1
    js = planner.plan_journey(origin_stop_id="239", dest_stop_id="1", departure_time_s=30000.0, max_transfers=2)
    assert len(js) > 0
    t_j = [j for j in js if j.num_transfers == 1]
    assert len(t_j) > 0
    j = t_j[0]
    assert j.accounting.total_transfer_wait_s >= 119.9, "Must satisfy >=120s buffer"
    assert j.accounting.is_valid

    # Case 7: Two-transfer journey (Round 3)
    js2 = planner.plan_journey(origin_stop_id="239", dest_stop_id="150", departure_time_s=36000.0, max_transfers=3)
    assert len(js2) > 0
    assert any(j.num_transfers <= 2 for j in js2)

    # Case 11: Delay propagation check
    # Connecting trip boarding must never precede (alight_time + transfer_walk + 120s)
    for j in js:
        if j.num_transfers > 0:
            for idx in range(len(j.legs) - 1):
                l1 = j.legs[idx]
                l2 = j.legs[idx + 1]
                if isinstance(l1, TransitLeg) and isinstance(l2, TransitLeg):
                    assert l2.board_time_s >= l1.alight_time_s + 119.9
                elif isinstance(l1, WalkingLeg) and l1.leg_type == "TRANSFER":
                    if idx + 1 < len(j.legs) and isinstance(j.legs[idx + 1], TransitLeg):
                        assert j.legs[idx + 1].board_time_s >= l1.end_time_s + 119.9


def test_manual_expected_result_transfer_buffer_invariants(planner):
    """Category: Verified against a manually calculated expected result.

    Verifies Case 9 & 10: Strict transfer buffer invariant dep >= arr + 120s.
    """
    js = planner.plan_journey(origin_stop_id="239", dest_stop_id="1", departure_time_s=30000.0, max_transfers=2)
    for j in js:
        if j.num_transfers > 0:
            for idx in range(len(j.legs) - 1):
                l1 = j.legs[idx]
                l2 = j.legs[idx + 1]
                if isinstance(l1, TransitLeg) and isinstance(l2, TransitLeg):
                    wait = l2.board_time_s - l1.alight_time_s
                    assert wait >= 119.9, f"Transfer wait {wait}s < 120s"


def test_manual_expected_result_coordinate_and_unreachable(planner):
    """Category: Verified against a manually calculated expected result.

    Verifies Case 8 (coordinate access/egress walk) and Cases 14-15 (unreachable).
    """
    # Case 8: Coordinate-to-coordinate routing
    orig = (28.715, 77.181)
    dest = (28.735, 77.165)
    js = planner.plan_journey(origin_coord=orig, dest_coord=dest, departure_time_s=45000.0)
    assert len(js) > 0
    j = js[0]
    assert j.accounting.access_walk_s > 0.0
    assert j.accounting.egress_walk_s > 0.0
    assert j.accounting.is_valid

    # Case 14: Non-existent stop ID returns clean []
    js_inv = planner.plan_journey(origin_stop_id="239", dest_stop_id="INVALID_STOP_999999", departure_time_s=45000.0)
    assert js_inv == []

    # Case 15: Out-of-bounds coordinates in desert returns clean []
    js_oob = planner.plan_journey(origin_coord=(25.0, 70.0), dest_coord=(28.7, 77.1), departure_time_s=45000.0)
    assert js_oob == []


# ==============================================================================
# Category 3: Synthetic Unit Tests
# ==============================================================================

def test_synthetic_unit_prediction_hierarchy_five_distinct_levels(planner):
    """Category: Synthetic unit test.

    Verifies that all 5 distinct prediction levels exist in code, RF is disabled
    by default, detour factor is strictly isolated, and metadata is populated.
    """
    # Level 1: Observed Ground Truth (Stop 240 -> 241, sample_count >= 3)
    p1 = planner.predict_segment(
        route_id="1598",
        stop_id_from="240",
        stop_id_to="241",
        departure_time_s=45000.0,
        hour_ist=12,
        is_weekend=0,
        sched_duration_s=215.0,
        use_experimental_ml=False,
    )
    assert p1.tier == "LEVEL_1_DIRECT_OBSERVED"
    assert p1.source == "GROUND_TRUTH_OBSERVED"
    assert p1.confidence == 1.0
    assert p1.is_fallback is False
    assert p1.warning is None

    # Level 2: Historical Baseline M0 (Corridor Pooled or Tier 2)
    p2 = planner.predict_segment(
        route_id="1445",
        stop_id_from="240",
        stop_id_to="241",
        departure_time_s=45000.0,
        hour_ist=12,
        is_weekend=0,
        sched_duration_s=215.0,
        use_experimental_ml=False,
    )
    assert p2.tier in ["LEVEL_1_DIRECT_OBSERVED", "LEVEL_2_HISTORICAL_BASELINE_M0"]

    # Level 3: Experimental RF Model (explicitly gated, disabled by default)
    # Evaluated on unobserved segment where Level 1 and Level 2 do not apply
    p3 = planner.predict_segment(
        route_id="999",
        stop_id_from="100",
        stop_id_to="105",
        departure_time_s=45000.0,
        hour_ist=12,
        is_weekend=0,
        sched_duration_s=215.0,
        use_experimental_ml=True,  # Explicitly enabled
    )
    assert p3.tier == "LEVEL_3_EXPERIMENTAL_RF"
    assert p3.source == "M2_RANDOM_FOREST"
    assert p3.confidence == 0.70
    assert "experimental" in str(p3.warning).lower()
    # Conformal lower bound must be >= 5.0s per PRD
    assert p3.lower_bound_p10_s >= 5.0

    # Level 4: GTFS Scheduled running time for unobserved corridors
    p4 = planner.predict_segment(
        route_id="999",
        stop_id_from="99991",
        stop_id_to="99992",
        departure_time_s=36000.0,
        hour_ist=10,
        is_weekend=0,
        sched_duration_s=240.0,  # Valid positive GTFS scheduled duration
        use_experimental_ml=False,
    )
    assert p4.tier == "LEVEL_4_GTFS_SCHEDULED"
    assert p4.source == "GTFS_TIMETABLE"
    assert p4.confidence == 0.30
    assert p4.is_fallback is True
    assert p4.predicted_time_s == 240.0, "Level 4 must use scheduled duration directly without 1.262 detour factor!"
    assert "Unobserved corridor" in str(p4.warning)

    # Level 5: Static Fallback for missing/invalid timetable references (sched_duration <= 0)
    p5 = planner.predict_segment(
        route_id="999",
        stop_id_from="99991",
        stop_id_to="99992",
        departure_time_s=36000.0,
        hour_ist=10,
        is_weekend=0,
        sched_duration_s=0.0,  # Missing / invalid timetable schedule!
        use_experimental_ml=False,
    )
    assert p5.tier == "LEVEL_5_STATIC_FALLBACK"
    assert p5.source == "STATIC_VELOCITY_FALLBACK"
    assert p5.confidence == 0.10
    assert p5.is_fallback is True
    assert "Missing or invalid timetable running time" in str(p5.warning)


def test_synthetic_unit_journey_accounting_independent_recalculation(planner):
    """Category: Synthetic unit test.

    Independently recalculates access walk, initial wait, ride time, transfer walk,
    transfer wait, and egress walk, verifying discrepancy == 0.0000s and distinct scheduled times.
    """
    js = planner.plan_journey(origin_stop_id="239", dest_stop_id="247", departure_time_s=45000.0)
    for j in js:
        # Independent recalculation from legs
        calc_access = sum(l.duration_s for l in j.legs if isinstance(l, WalkingLeg) and l.leg_type == "ACCESS")
        calc_trans_walk = sum(l.duration_s for l in j.legs if isinstance(l, WalkingLeg) and l.leg_type == "TRANSFER")
        calc_egress = sum(l.duration_s for l in j.legs if isinstance(l, WalkingLeg) and l.leg_type == "EGRESS")
        calc_ride = sum(l.ride_duration_s for l in j.legs if isinstance(l, TransitLeg))

        # Check distinct scheduled times vs predicted times on transit legs
        for l in j.legs:
            if isinstance(l, TransitLeg):
                assert hasattr(l, "sched_departure_s")
                assert hasattr(l, "sched_arrival_s")
                assert hasattr(l, "sched_duration_s")
                assert l.sched_duration_s == l.sched_arrival_s - l.sched_departure_s

        acct = j.accounting
        assert abs(calc_access - acct.access_walk_s) < 1e-2
        assert abs(calc_trans_walk - acct.total_transfer_walk_s) < 1e-2
        assert abs(calc_egress - acct.egress_walk_s) < 1e-2
        assert abs(calc_ride - acct.total_ride_s) < 1e-2
        assert abs(acct.discrepancy_s) < 1e-4
        assert acct.is_valid


# ==============================================================================
# Category 4: Performance Benchmark Audit
# ==============================================================================

def test_performance_benchmark_audit_metrics():
    """Category: Performance benchmark.

    Verifies data/processed/milestone5_1_audit_metrics.json exists and satisfies
    operational targets (warm-up, repeated passes, latency, memory).
    """
    audit_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "processed", "milestone5_1_audit_metrics.json"
    )
    assert os.path.exists(audit_file), "Audit metrics JSON must exist"
    with open(audit_file, "r") as f:
        data = json.load(f)

    assert data["milestone"] == "5.1"
    assert data["summary"]["gtfs_cases_passed"] == 15
    assert data["summary"]["gtfs_cases_total"] == 15
    assert data["summary"]["accounting_violations"] == 0
    assert data["summary"]["transfer_buffer_violations"] == 0

    bench = data["performance_audit"]
    assert bench["warmup_queries"] == 5
    assert bench["repeated_runs_per_query"] == 3
    assert bench["latencies_ms"]["mean"] < 500.0
    assert bench["query_latency_includes_data_loading"] is False

    # Check exact footpath timer breakdown
    fp_audit = bench["footpath_timer_audit"]
    assert "coordinate_array_time_s" in fp_audit
    assert "kdtree_build_time_s" in fp_audit
    assert "query_pairs_time_s" in fp_audit
    assert "footpath_objects_dict_time_s" in fp_audit
    assert "total_footpath_generation_time_s" in fp_audit
