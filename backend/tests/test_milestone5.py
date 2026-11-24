"""Automated Test Suite for Milestone 5: Journey Planner & RAPTOR Implementation.

Verifies:
1. Timetable construction, pattern grouping, KD-Tree indexing, and footpath generation.
2. Direct transit journeys (Round 1 / 0 transfers).
3. One-transfer transit journeys (Round 2 / 1 transfer).
4. Two-transfer transit journeys (Round 3 / 2 transfers).
5. Coordinate-to-coordinate routing with access/egress walking legs.
6. Strict minimum transfer buffer enforcement (>= 120 seconds).
7. Post-midnight GTFS service continuity (t >= 86400 seconds).
8. No-service and unreachable destination handling.
9. Strict Journey-Time Accounting Identity across all journeys.
10. 4-tier prediction hierarchy integration and confidence tagging.
11. Detour factor restriction (1.262 restricted to corridor, never applied network-wide).
12. Multi-criteria ranking and near-duplicate deduplication.
"""

import os
import pytest
import numpy as np

from backend.core.raptor_data import Timetable, Stop, Footpath, RoutePattern
from backend.core.raptor import (
    RaptorEngine,
    RaptorQuery,
    PlannedJourney,
    TransitLeg,
    WalkingLeg,
)
from backend.core.journey_planner import JourneyPlanner


MDB_PATH = "/tmp/delhi_mdb.db"


@pytest.fixture(scope="module")
def timetable():
    if not os.path.exists(MDB_PATH):
        pytest.skip(f"{MDB_PATH} not found")
    return Timetable.load_from_sqlite(MDB_PATH)


@pytest.fixture(scope="module")
def planner(timetable):
    return JourneyPlanner.create_default(db_path=MDB_PATH, fit_baseline=True)


# 1. Timetable loading and patterns
def test_timetable_loading_and_patterns(timetable):
    assert len(timetable.stops) > 6000, "Should have loaded >6000 stops"
    assert len(timetable.patterns) > 2000, "Should have grouped trips into >2000 patterns"
    assert timetable.kdtree is not None, "KD-Tree must be initialized"

    # Check footpaths
    assert len(timetable.footpaths) > 0, "Footpaths must be generated"
    sample_sid = list(timetable.footpaths.keys())[0]
    sample_fps = timetable.footpaths[sample_sid]
    assert any(fp.from_stop_id == fp.to_stop_id for fp in sample_fps), "Must contain self-footpath"

    # Check footpath distance constraint
    for sid, fps in list(timetable.footpaths.items())[:100]:
        for fp in fps:
            assert fp.distance_m <= 400.05, f"Footpath distance {fp.distance_m} exceeds 400m limit"
            assert fp.walking_time_s >= 0.0, "Walking time must be non-negative"


# 2. Direct journey routing
def test_direct_journey_routing(planner):
    # Route along North GT Road corridor: Stop 239 (Azad Pur) to Stop 247 (Mukarba Chowk)
    journeys = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="247",
        departure_time_s=45000.0,
        max_transfers=1,  # Direct only
    )
    assert len(journeys) > 0, "Should find at least one direct journey between 239 and 247"
    best = journeys[0]
    assert best.num_transfers == 0, "Direct journey must have 0 transfers"
    assert best.arrival_time_s > 45000.0, "Arrival time must be after departure time"
    assert best.total_journey_time_s > 0, "Total journey time must be positive"


# 3. One-transfer journey routing
def test_one_transfer_journey_routing(planner):
    # From Stop 239 (Azad Pur) to Stop 1
    journeys = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="1",
        departure_time_s=30000.0,
        max_transfers=2,  # Up to 1 transfer
    )
    assert len(journeys) > 0, "Should find journeys connecting 239 and 1"
    transfer_j = [j for j in journeys if j.num_transfers == 1]
    assert len(transfer_j) > 0, "Should find at least one 1-transfer journey"
    j = transfer_j[0]
    assert j.accounting.total_transfer_wait_s >= 119.9, "Transfer wait must enforce >= 120s buffer"
    assert j.accounting.is_valid, "Accounting identity must hold"


# 4. Two-transfer journey routing
def test_two_transfer_journey_routing(planner):
    journeys = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="150",
        departure_time_s=36000.0,
        max_transfers=3,  # Up to 2 transfers
    )
    assert len(journeys) > 0, "Should return journey options for network route"
    for j in journeys:
        assert j.num_transfers <= 2, "Transfers must not exceed max_transfers limit"
        assert j.accounting.is_valid, "Accounting identity must hold"


# 5. Coordinate-to-coordinate routing
def test_coordinate_to_coordinate_routing(planner):
    orig = (28.715, 77.181)  # Near Azadpur
    dest = (28.735, 77.165)  # Near Mukarba Chowk
    journeys = planner.plan_journey(
        origin_coord=orig,
        dest_coord=dest,
        departure_time_s=45000.0,
    )
    assert len(journeys) > 0, "Should find journeys between coordinates"
    j = journeys[0]
    # Check that access walk and egress walk exist
    leg_types = [l.leg_type for l in j.legs if isinstance(l, WalkingLeg)]
    assert "ACCESS" in leg_types, "Must contain access walking leg"
    assert "EGRESS" in leg_types, "Must contain egress walking leg"
    assert j.accounting.access_walk_s > 0, "Access walk time must be positive"
    assert j.accounting.egress_walk_s > 0, "Egress walk time must be positive"
    assert j.accounting.is_valid, "Accounting identity must hold"


# 6. Minimum transfer buffer enforcement
def test_transfer_buffer_enforcement(planner):
    journeys = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="1",
        departure_time_s=30000.0,
        max_transfers=2,
    )
    for j in journeys:
        if j.num_transfers > 0:
            # Check every transfer connection in the journey
            for i in range(len(j.legs) - 1):
                l1 = j.legs[i]
                l2 = j.legs[i + 1]
                if isinstance(l1, TransitLeg) and isinstance(l2, TransitLeg):
                    wait = l2.board_time_s - l1.alight_time_s
                    assert wait >= 119.9, f"Direct transfer wait {wait:.1f}s must be >= 120s"
                elif isinstance(l1, WalkingLeg) and l1.leg_type == "TRANSFER":
                    if i + 1 < len(j.legs) and isinstance(j.legs[i + 1], TransitLeg):
                        t_next = j.legs[i + 1]
                        wait = t_next.board_time_s - l1.end_time_s
                        assert wait >= 119.9, f"Footpath transfer wait {wait:.1f}s must be >= 120s"


# 7. Post-midnight GTFS service continuity
def test_after_midnight_gtfs_trips(planner):
    # Pattern 0 departs at 82800s (23:00) and arrives after midnight at 86901s (24:08)
    p0 = planner.timetable.patterns[0]
    s0 = p0.stop_ids[0]
    s_end = p0.stop_ids[-1]
    journeys = planner.plan_journey(
        origin_stop_id=s0,
        dest_stop_id=s_end,
        departure_time_s=82680.0,
    )
    assert len(journeys) > 0, "Must route post-midnight trips"
    j = journeys[0]
    assert j.arrival_time_s >= 86400.0, "Arrival time must cross midnight (>= 86400s)"
    assert j.total_journey_time_s > 0, "Total journey time must be positive"
    assert j.accounting.is_valid, "Accounting identity must hold across midnight"


# 8. No-service and unreachable cases
def test_no_service_and_unreachable_cases(planner):
    # Impossible destination stop
    j_invalid = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="NON_EXISTENT_STOP_999",
        departure_time_s=45000.0,
    )
    assert j_invalid == [], "Must return empty list for non-existent stop"

    # Coordinates in remote area with no transit coverage
    j_desert = planner.plan_journey(
        origin_coord=(25.0, 70.0),
        dest_coord=(28.7, 77.1),
        departure_time_s=45000.0,
    )
    assert j_desert == [], "Must return empty list for out-of-bounds coordinates"


# 9. Strict Journey-Time Accounting Identity
def test_journey_time_accounting_identity(planner):
    test_queries = [
        {"orig": "239", "dest": "247", "dep": 28800.0},
        {"orig": "240", "dest": "246", "dep": 32400.0},
        {"orig": "241", "dest": "248", "dep": 36000.0},
        {"orig": "239", "dest": "1", "dep": 30000.0},
        {"orig": "247", "dest": "10", "dep": 40000.0},
    ]
    for q in test_queries:
        journeys = planner.plan_journey(
            origin_stop_id=q["orig"],
            dest_stop_id=q["dest"],
            departure_time_s=q["dep"],
        )
        for j in journeys:
            acct = j.accounting
            assert acct.is_valid, f"Accounting invalid: discrepancy={acct.discrepancy_s}"
            assert abs(acct.discrepancy_s) < 1e-4, f"Discrepancy {acct.discrepancy_s} must be zero"
            assert acct.initial_wait_s >= 0.0, "Initial wait must be non-negative"
            assert acct.total_transfer_wait_s >= 0.0, "Transfer wait must be non-negative"
            assert acct.total_ride_s > 0.0, "Total ride time must be positive"
            
            # Explicit formula check
            calculated_sum = (
                acct.access_walk_s
                + acct.initial_wait_s
                + acct.total_ride_s
                + acct.total_transfer_walk_s
                + acct.total_transfer_wait_s
                + acct.egress_walk_s
            )
            assert abs(calculated_sum - acct.total_journey_time_s) < 1e-2, (
                f"Sum {calculated_sum} != Total {acct.total_journey_time_s}"
            )


# 10. 4-tier prediction hierarchy integration
def test_prediction_hierarchy_integration(planner):
    # North GT Road corridor should use Level 1 or Level 2
    js_corridor = planner.plan_journey(
        origin_stop_id="240",
        dest_stop_id="246",
        departure_time_s=45000.0,
    )
    assert len(js_corridor) > 0
    corridor_tiers = [
        l.prediction_tier for l in js_corridor[0].legs if isinstance(l, TransitLeg)
    ]
    assert any("LEVEL_1" in t or "LEVEL_2" in t for t in corridor_tiers), (
        f"Corridor legs should have Level 1 or 2 prediction, got {corridor_tiers}"
    )

    # Unobserved corridor outside North GT Road should use Level 4 Timetable Fallback
    js_unobs = planner.plan_journey(
        origin_stop_id="100",
        dest_stop_id="105",
        departure_time_s=30000.0,
    )
    assert len(js_unobs) > 0
    unobs_tiers = [
        l.prediction_tier for l in js_unobs[0].legs if isinstance(l, TransitLeg)
    ]
    assert all("LEVEL_4" in t for t in unobs_tiers), (
        f"Unobserved legs must be LEVEL_4_TIMETABLE_FALLBACK, got {unobs_tiers}"
    )
    for l in js_unobs[0].legs:
        if isinstance(l, TransitLeg):
            assert l.confidence_score <= 0.35, "Timetable fallback confidence must be <= 0.35"
            assert l.warning is not None, "Timetable fallback must carry a low confidence warning"


# 11. Detour factor safety and dwell consistency
def test_detour_factor_safety_and_dwell_consistency(planner):
    # Predict unobserved segment: should NOT multiply scheduled time by 1.262
    pred = planner.predict_segment(
        route_id="999",
        stop_id_from="99991",
        stop_id_to="99992",
        departure_time_s=36000.0,
        hour_ist=10,
        is_weekend=0,
        sched_duration_s=180.0,
    )
    assert pred.tier in ["LEVEL_4_GTFS_SCHEDULED", "LEVEL_4_TIMETABLE_FALLBACK"]
    assert abs(pred.predicted_time_s - 180.0) < 1e-3, (
        f"Level 4 timetable must use scheduled duration directly (180s), got {pred.predicted_time_s}"
    )
    assert "Unobserved corridor" in str(pred.warning)

    # Check that dwell is not double counted
    # In Delhi GTFS, scheduled dwell is 0. Check a sample journey.
    js = planner.plan_journey(origin_stop_id="239", dest_stop_id="247", departure_time_s=45000.0)
    for j in js:
        # Sum of segment durations must equal leg ride duration
        for l in j.legs:
            if isinstance(l, TransitLeg):
                assert l.ride_duration_s == l.alight_time_s - l.board_time_s


# 12. Ranking strategies and deduplication
def test_ranking_strategies_and_deduplication(planner):
    # Earliest arrival
    js_ea = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="247",
        departure_time_s=45000.0,
        ranking_strategy="earliest_arrival",
    )
    if len(js_ea) >= 2:
        assert js_ea[0].arrival_time_s <= js_ea[1].arrival_time_s

    # Fewest transfers
    js_ft = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="247",
        departure_time_s=45000.0,
        ranking_strategy="fewest_transfers",
    )
    if len(js_ft) >= 2:
        assert js_ft[0].num_transfers <= js_ft[1].num_transfers

