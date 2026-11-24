"""Transit Journey Planning Application Service."""

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.core.journey_planner import JourneyPlanner
from backend.core.raptor import PlannedJourney, TransitLeg, WalkingLeg
from backend.core.raptor_data import TimetableStatus
from backend.app.schemas.journey import (
    JourneyAccountingSchema,
    JourneyAlternativeSchema,
    JourneyPlanRequest,
    JourneyPlanResponse,
    TransitLegSchema,
    WalkingLegSchema,
)
from backend.app.schemas.live import LiveBusCandidateSchema
from backend.realtime.matcher import JourneyBusMatcher


class ExpiredTimetableException(Exception):
    """Raised when an expired timetable date is requested without demonstration opt-in."""
    def __init__(self, message: str, feed_end_date: str, requested_date: str):
        super().__init__(message)
        self.message = message
        self.feed_end_date = feed_end_date
        self.requested_date = requested_date


class TimetableUnavailableException(Exception):
    """Raised when timetable data is unavailable in memory."""
    pass


class PlannerService:
    """Service orchestrating journey planning, timetable gating, and accounting."""

    def __init__(
        self,
        planner: JourneyPlanner,
        collector: Optional[Any] = None,
        matcher: Optional[JourneyBusMatcher] = None,
    ):
        self.planner = planner
        self.collector = collector
        self.matcher = matcher or JourneyBusMatcher()

    def get_timetable_status(
        self, service_date: str = "2026-10-01", allow_assumed_recurring: bool = False
    ) -> Dict[str, Any]:
        """Query GTFS feed freshness metadata."""
        status_meta = self.planner.get_timetable_freshness(
            service_date=service_date,
            allow_assumed_recurring=allow_assumed_recurring,
        )
        feed_start = status_meta["feed_start_date"]
        feed_end = status_meta["feed_end_date"]
        clean_date = service_date.replace("/", "-").strip()

        is_valid_date = False
        if feed_start and feed_end:
            is_valid_date = feed_start <= clean_date <= feed_end

        warnings = []
        if status_meta["stale_timetable_warning"]:
            warnings.append(status_meta["stale_timetable_warning"])

        return {
            "timetable_status": status_meta["timetable_status"],
            "feed_start_date": feed_start,
            "feed_end_date": feed_end,
            "feed_provenance": status_meta["feed_provenance"],
            "is_date_within_feed_validity": is_valid_date,
            "actual_operations_verified": False,  # Strictly False per PRD & M5.1.1
            "demonstration_mode_available": True,
            "service_date_evaluated": service_date,
            "warnings": warnings,
        }

    def plan_journey(self, req: JourneyPlanRequest) -> JourneyPlanResponse:
        """Execute RAPTOR transit journey planning with strict safeguards."""
        start_wall_time = time.perf_counter()

        # 1. Parse departure time into integer seconds since midnight
        t_match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", req.departure_time)
        if not t_match:
            raise ValueError(f"Invalid departure_time: {req.departure_time}")
        hh, mm, ss = int(t_match.group(1)), int(t_match.group(2)), int(t_match.group(3) or 0)
        departure_time_s = float(hh * 3600 + mm * 60 + ss)

        # 2. Check timetable freshness and enforce demonstration opt-in
        status_meta = self.get_timetable_status(
            service_date=req.departure_date,
            allow_assumed_recurring=req.allow_assumed_recurring,
        )
        tt_status = status_meta["timetable_status"]

        if tt_status == TimetableStatus.UNAVAILABLE.value:
            raise TimetableUnavailableException("GTFS timetable data is not available.")

        if tt_status == TimetableStatus.EXPIRED.value:
            feed_end = status_meta["feed_end_date"] or "2024-01-01"
            raise ExpiredTimetableException(
                message=(
                    f"The requested service date ({req.departure_date}) is outside feed validity. "
                    f"The GTFS timetable expired on {feed_end} and current operating schedules are unverified. "
                    f"To evaluate historical template schedules under demonstration mode, set "
                    f"'allow_assumed_recurring: true' in your request."
                ),
                feed_end_date=feed_end,
                requested_date=req.departure_date,
            )

        # 3. Resolve coordinate endpoints
        orig_coord = (
            (req.origin_lat, req.origin_lon)
            if req.origin_lat is not None and req.origin_lon is not None
            else None
        )
        dest_coord = (
            (req.dest_lat, req.dest_lon)
            if req.dest_lat is not None and req.dest_lon is not None
            else None
        )

        # 4. Invoke core RAPTOR Journey Planner
        raw_journeys = self.planner.plan_journey(
            origin_stop_id=req.origin_stop_id,
            origin_coord=orig_coord,
            dest_stop_id=req.dest_stop_id,
            dest_coord=dest_coord,
            departure_time_s=departure_time_s,
            service_date=req.departure_date,
            ranking_strategy=req.ranking_strategy,
            use_experimental_ml=req.use_experimental_ml,
            max_transfers=req.max_transfers,
            allow_assumed_recurring=req.allow_assumed_recurring,
        )

        elapsed_ms = (time.perf_counter() - start_wall_time) * 1000.0

        # 5. Transform PlannedJourney objects into API schemas
        journey_alternatives: List[JourneyAlternativeSchema] = []
        for idx, pj in enumerate(raw_journeys[: req.num_alternatives]):
            # Leg transformation
            legs_schema = []
            for leg in pj.legs:
                if isinstance(leg, WalkingLeg):
                    legs_schema.append(
                        WalkingLegSchema(
                            leg_type=leg.leg_type,
                            from_name=leg.from_name,
                            to_name=leg.to_name,
                            from_stop_id=leg.from_stop_id,
                            to_stop_id=leg.to_stop_id,
                            start_time_s=leg.start_time_s,
                            end_time_s=leg.end_time_s,
                            duration_s=round(leg.duration_s, 1),
                            distance_m=round(leg.distance_m, 1),
                        )
                    )
                elif isinstance(leg, TransitLeg):
                    # Match candidate live bus for this transit leg
                    live_bus_schema = None
                    try:
                        active_list = list(self.collector.active_vehicles.values()) if self.collector else []
                        live_bus_dict = self.matcher.match_bus_for_leg(
                            route_id=leg.route_id,
                            board_stop_id=leg.board_stop_id,
                            alight_stop_id=leg.alight_stop_id,
                            active_vehicles=active_list,
                            sched_departure_s=leg.sched_departure_s,
                        )
                        live_bus_schema = LiveBusCandidateSchema(**live_bus_dict)
                    except Exception as match_err:
                        logger.warning(f"Failed to match live bus for leg {leg.route_id}: {match_err}")

                    legs_schema.append(
                        TransitLegSchema(
                            leg_type="TRANSIT",
                            route_id=leg.route_id,
                            trip_id=leg.trip_id,
                            pattern_id=leg.pattern_id,
                            board_stop_id=leg.board_stop_id,
                            board_stop_name=leg.board_stop_name,
                            alight_stop_id=leg.alight_stop_id,
                            alight_stop_name=leg.alight_stop_name,
                            sched_departure_s=round(leg.sched_departure_s, 1),
                            sched_arrival_s=round(leg.sched_arrival_s, 1),
                            sched_duration_s=round(leg.sched_duration_s, 1),
                            board_time_s=round(leg.board_time_s, 1),
                            alight_time_s=round(leg.alight_time_s, 1),
                            ride_duration_s=round(leg.ride_duration_s, 1),
                            intermediate_stops=leg.intermediate_stops,
                            prediction_tier=leg.prediction_tier,
                            prediction_source=leg.prediction_source,
                            heuristic_confidence_score=round(leg.heuristic_confidence_score, 2),
                            confidence_score_type=leg.confidence_score_type,
                            confidence_explanation=leg.confidence_explanation,
                            is_fallback=leg.is_fallback,
                            fallback_reason=leg.fallback_reason,
                            warning=leg.warning,
                            timetable_status=leg.timetable_status,
                            is_verified_current_service=leg.is_verified_current_service,
                            live_bus=live_bus_schema,
                        )
                    )

            # Accounting transformation & strict validation
            acct = pj.accounting
            accounting_schema = JourneyAccountingSchema(
                access_walking_time_s=acct.access_walk_s,
                initial_waiting_time_s=acct.initial_wait_s,
                in_vehicle_duration_s=acct.total_ride_s,
                transfer_walking_time_s=acct.total_transfer_walk_s,
                transfer_waiting_time_s=acct.total_transfer_wait_s,
                egress_walking_time_s=acct.egress_walk_s,
                total_duration_s=acct.total_journey_time_s,
                discrepancy_s=acct.discrepancy_s,
                is_valid_identity=acct.is_valid,
            )

            journey_warnings = []
            if pj.timetable_warning:
                journey_warnings.append(pj.timetable_warning)

            # Milestone 11.5: Long transfer waiting advisory (> 7200s / 2 hours)
            LONG_TRANSFER_THRESHOLD_S = 7200.0
            has_long_transfer_wait = False
            long_transfer_advisory = None
            if acct.total_transfer_wait_s > LONG_TRANSFER_THRESHOLD_S:
                has_long_transfer_wait = True
                wait_hours = round(acct.total_transfer_wait_s / 3600.0, 1)
                long_transfer_advisory = (
                    f"Extended transfer wait time: {int(round(acct.total_transfer_wait_s))}s ({wait_hours:.1f} hours). "
                    f"This connection has a long scheduled wait between connecting bus services. "
                    f"Consider comparing other available journey options or selecting a different departure time."
                )
                journey_warnings.append(long_transfer_advisory)

            journey_alternatives.append(
                JourneyAlternativeSchema(
                    journey_id=f"journey_{idx + 1}",
                    num_transfers=pj.num_transfers,
                    departure_time_s=round(pj.departure_time_s, 1),
                    arrival_time_s=round(pj.arrival_time_s, 1),
                    total_journey_duration_s=round(pj.total_journey_time_s, 1),
                    legs=legs_schema,
                    accounting=accounting_schema,
                    heuristic_confidence_score=round(pj.heuristic_confidence_score, 2),
                    confidence_score_type=pj.confidence_score_type,
                    timetable_status=pj.timetable_status,
                    is_verified_current_service=pj.is_verified_current_service,
                    actual_operations_verified=False,  # Strictly False
                    long_transfer_advisory=long_transfer_advisory,
                    has_long_transfer_wait=has_long_transfer_wait,
                    warnings=journey_warnings,
                )
            )

        stale_warning = status_meta["warnings"][0] if status_meta["warnings"] else None

        return JourneyPlanResponse(
            query_summary={
                "departure_date": req.departure_date,
                "departure_time": req.departure_time,
                "departure_time_s": departure_time_s,
                "max_walking_distance_m": req.max_walking_distance_m,
                "max_transfers": req.max_transfers,
                "ranking_strategy": req.ranking_strategy,
                "use_experimental_ml": req.use_experimental_ml,
                "allow_assumed_recurring": req.allow_assumed_recurring,
                "execution_time_ms": round(elapsed_ms, 2),
            },
            journeys_count=len(journey_alternatives),
            journeys=journey_alternatives,
            timetable_status=tt_status,
            stale_timetable_warning=stale_warning,
        )

