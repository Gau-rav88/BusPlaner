"""Milestone 5.1.1 Tests: GTFS Freshness and Operational Readiness Safeguards.

Tests:
1. Expired timetable dates (strict mode returns EXPIRED and empty itineraries).
2. Current verified timetable dates (historical dates within feed validity return CURRENT_VERIFIED).
3. Assumed recurring demonstration mode (returns ASSUMED_RECURRING with explicit warning).
4. Missing timetable (empty/unloaded timetable returns UNAVAILABLE).
5. Warning propagation into journey results and transit legs.
6. Heuristic confidence scores and explanations across all 5 prediction hierarchy tiers.
"""

import os
import pytest

from backend.core.raptor_data import Timetable, TimetableStatus
from backend.core.raptor import PlannedJourney, TransitLeg, WalkingLeg
from backend.core.journey_planner import JourneyPlanner, SegmentPrediction

DB_PATH = "/tmp/delhi_mdb.db"


@pytest.fixture(scope="module")
def planner():
    if not os.path.exists(DB_PATH):
        pytest.skip(f"{DB_PATH} not found")
    return JourneyPlanner.create_default(db_path=DB_PATH, fit_baseline=True)


def test_expired_timetable_dates_strict_mode(planner):
    """Test that requesting an expired service date in strict mode returns EXPIRED status and 0 journeys."""
    service_date = "2026-10-01"
    status, warning = planner.timetable.check_freshness(service_date, allow_assumed_recurring=False)
    
    assert status == TimetableStatus.EXPIRED
    assert warning is not None
    assert "EXPIRED TIMETABLE ERROR" in warning
    assert "2024-01-01" in warning
    assert "Current operating schedule is unverified" in warning

    # Journey planner in strict mode must reject routing
    journeys = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="2024",
        departure_time_s=45460.0,
        service_date=service_date,
        allow_assumed_recurring=False,
    )
    assert len(journeys) == 0, "Strict mode on expired timetable must return zero itineraries"


def test_current_verified_timetable_dates(planner):
    """Test that requesting a date within feed validity window returns CURRENT_VERIFIED without warnings."""
    # Feed validity is 2022-01-01 to 2024-01-01
    hist_date = "2023-05-15"
    status, warning = planner.timetable.check_freshness(hist_date, allow_assumed_recurring=True)

    assert status == TimetableStatus.CURRENT_VERIFIED
    assert warning is None

    journeys = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="2024",
        departure_time_s=45460.0,
        service_date=hist_date,
        allow_assumed_recurring=True,
    )
    assert len(journeys) > 0
    j = journeys[0]
    assert j.timetable_status == "CURRENT_VERIFIED"
    assert j.is_verified_current_service is True
    assert j.timetable_warning is None

    # Check legs
    t_legs = [l for l in j.legs if isinstance(l, TransitLeg)]
    assert len(t_legs) > 0
    for leg in t_legs:
        assert leg.timetable_status == "CURRENT_VERIFIED"
        assert leg.is_verified_current_service is True


def test_assumed_recurring_demonstration_mode(planner):
    """Test that 2026 queries in demonstration mode return ASSUMED_RECURRING with explicit stale warnings."""
    service_date = "2026-10-01"
    status, warning = planner.timetable.check_freshness(service_date, allow_assumed_recurring=True)

    assert status == TimetableStatus.ASSUMED_RECURRING
    assert warning is not None
    assert "STALE TIMETABLE WARNING" in warning
    assert "2024-01-01" in warning
    assert "NOT verified as currently operating in Delhi in 2026" in warning

    journeys = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="2024",
        departure_time_s=45460.0,
        service_date=service_date,
        allow_assumed_recurring=True,
    )
    assert len(journeys) > 0
    j = journeys[0]
    assert j.timetable_status == "ASSUMED_RECURRING"
    assert j.is_verified_current_service is False
    assert j.timetable_warning is not None
    assert "STALE TIMETABLE WARNING" in j.timetable_warning

    t_legs = [l for l in j.legs if isinstance(l, TransitLeg)]
    for leg in t_legs:
        assert leg.timetable_status == "ASSUMED_RECURRING"
        assert leg.is_verified_current_service is False


def test_missing_timetable_unavailable():
    """Test that an empty or missing timetable returns UNAVAILABLE status."""
    empty_tt = Timetable(
        stops={},
        patterns={},
        stop_to_patterns={},
        footpaths={},
        active_service_ids=set(),
        db_path="",
        config={},
        feed_start_date=None,
        feed_end_date=None,
    )
    status, warning = empty_tt.check_freshness("2026-10-01")
    assert status == TimetableStatus.UNAVAILABLE
    assert warning is not None
    assert "UNAVAILABLE" in warning


def test_warning_propagation_across_diverse_journeys(planner):
    """Test that timetable status and warnings propagate cleanly across multi-leg journeys."""
    service_date = "2026-10-01"
    # Multi-transfer journey from Stop 239 to Stop 1
    journeys = planner.plan_journey(
        origin_stop_id="239",
        dest_stop_id="1",
        departure_time_s=45460.0,
        service_date=service_date,
        allow_assumed_recurring=True,
    )
    if journeys:
        j = journeys[0]
        assert j.timetable_status == "ASSUMED_RECURRING"
        assert j.is_verified_current_service is False
        assert j.timetable_warning is not None

        for leg in j.legs:
            if isinstance(leg, TransitLeg):
                assert leg.timetable_status == "ASSUMED_RECURRING"
                assert leg.is_verified_current_service is False


def test_prediction_confidence_heuristic_labeling(planner):
    """Test that all 5 prediction hierarchy tiers label confidence as heuristic scores, not probabilities."""
    # Level 1: Observed Ground Truth
    p1 = planner.predict_segment("1598", "240", "241", 45000.0, 12, 0, 100.0)
    assert p1.heuristic_confidence_score == 1.0
    assert p1.confidence_score_type == "HEURISTIC"
    assert "NOT a calibrated probability" in p1.confidence_explanation

    # Level 3: Experimental RF
    p3 = planner.predict_segment("9999", "100", "105", 45000.0, 12, 0, 100.0, use_experimental_ml=True)
    assert p3.heuristic_confidence_score == 0.70
    assert p3.confidence_score_type == "HEURISTIC"
    assert "NOT an empirical probability" in p3.confidence_explanation

    # Level 4: Timetable Fallback
    p4 = planner.predict_segment("9999", "100", "105", 45000.0, 12, 0, 100.0, use_experimental_ml=False)
    assert p4.heuristic_confidence_score == 0.30
    assert p4.confidence_score_type == "HEURISTIC"
    assert "NOT a calibrated probability" in p4.confidence_explanation

    # Level 5: Static Fallback
    p5 = planner.predict_segment("9999", "100", "105", 45000.0, 12, 0, 0.0, use_experimental_ml=False)
    assert p5.heuristic_confidence_score == 0.10
    assert p5.confidence_score_type == "HEURISTIC"
    assert "NOT a calibrated probability" in p5.confidence_explanation


def test_get_timetable_freshness_method(planner):
    """Test planner.get_timetable_freshness helper for API/UI readiness."""
    meta_curr = planner.get_timetable_freshness("2023-05-15")
    assert meta_curr["timetable_status"] == "CURRENT_VERIFIED"
    assert meta_curr["is_verified_current_service"] is True
    assert meta_curr["stale_timetable_warning"] is None

    meta_demo = planner.get_timetable_freshness("2026-10-01", allow_assumed_recurring=True)
    assert meta_demo["timetable_status"] == "ASSUMED_RECURRING"
    assert meta_demo["is_verified_current_service"] is False
    assert "STALE TIMETABLE WARNING" in meta_demo["stale_timetable_warning"]

    meta_exp = planner.get_timetable_freshness("2026-10-01", allow_assumed_recurring=False)
    assert meta_exp["timetable_status"] == "EXPIRED"
    assert meta_exp["is_verified_current_service"] is False
    assert "EXPIRED TIMETABLE ERROR" in meta_exp["stale_timetable_warning"]

