"""RAPTOR Transit Routing Engine Module.

Implements Round-Based Public Transit Routing (RAPTOR) according to
PRD v3.0 Section 8:
- Round 1: Direct transit journeys (0 transfers)
- Round 2: One-transfer transit journeys (1 transfer)
- Round 3: Two-transfer transit journeys (2 transfers)
- Footpath relaxation for transfer connections (<= 400m)
- Strict minimum transfer buffer enforcement (>= 120 seconds)
- Coordinate-to-coordinate and stop-to-stop routing
- Linear timeline support for post-midnight trips (t >= 86400s)
- Exact journey-time accounting identity verification
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from backend.core.raptor_data import Footpath, RoutePattern, Stop, Timetable, Trip, TimetableStatus


@dataclass
class RaptorQuery:
    origin_stop_id: Optional[str] = None
    origin_coord: Optional[Tuple[float, float]] = None  # (lat, lon)
    dest_stop_id: Optional[str] = None
    dest_coord: Optional[Tuple[float, float]] = None  # (lat, lon)
    departure_time_s: float = 28800.0  # 08:00:00 default
    service_date: str = "2026-10-01"
    max_transfers: int = 3  # K=3 rounds: direct, 1-transfer, 2-transfers
    min_transfer_buffer_s: float = 120.0
    walking_speed_kmh: float = 4.5
    detour_factor: float = 1.3
    max_access_radius_m: float = 800.0
    expanded_access_radius_m: float = 1500.0
    max_transfer_distance_m: float = 400.0
    allow_assumed_recurring: bool = True


@dataclass
class WalkingLeg:
    leg_type: str  # "ACCESS", "TRANSFER", "EGRESS"
    from_name: str
    to_name: str
    from_stop_id: Optional[str]
    to_stop_id: Optional[str]
    start_time_s: float
    end_time_s: float
    duration_s: float
    distance_m: float


@dataclass
class TransitLeg:
    route_id: str
    trip_id: str
    pattern_id: int
    board_stop_id: str
    board_stop_name: str
    alight_stop_id: str
    alight_stop_name: str
    board_time_s: float
    alight_time_s: float
    ride_duration_s: float
    intermediate_stops: List[str]
    stop_segments: List[Tuple[str, str]]
    # Scheduled timetable attributes
    sched_departure_s: float = 0.0
    sched_arrival_s: float = 0.0
    sched_duration_s: float = 0.0
    # Prediction attributes to be populated by journey planner
    prediction_tier: str = "LEVEL_4_GTFS_SCHEDULED"
    prediction_source: str = "GTFS_TIMETABLE"
    confidence_score: float = 0.3
    heuristic_confidence_score: float = 0.3
    confidence_score_type: str = "HEURISTIC"
    confidence_explanation: str = "Heuristic score representing operational and empirical data support; NOT a calibrated probability."
    is_fallback: bool = True
    fallback_reason: Optional[str] = None
    warning: Optional[str] = None
    timetable_status: str = "ASSUMED_RECURRING"
    is_verified_current_service: bool = False


@dataclass
class JourneyAccounting:
    access_walk_s: float
    initial_wait_s: float
    total_ride_s: float
    total_transfer_walk_s: float
    total_transfer_wait_s: float
    egress_walk_s: float
    sum_components_s: float
    total_journey_time_s: float
    discrepancy_s: float

    @property
    def is_valid(self) -> bool:
        return abs(self.discrepancy_s) < 1e-4 and self.initial_wait_s >= -1e-4 and self.total_transfer_wait_s >= -1e-4


@dataclass
class PlannedJourney:
    round_k: int
    num_transfers: int
    departure_time_s: float
    arrival_time_s: float
    total_journey_time_s: float
    legs: List[Any]  # WalkingLeg and TransitLeg
    accounting: JourneyAccounting
    confidence_score: float = 1.0
    heuristic_confidence_score: float = 1.0
    confidence_score_type: str = "HEURISTIC"
    confidence_explanation: str = "Heuristic score representing operational and empirical data support; NOT a calibrated probability."
    ranking_score: float = 0.0
    timetable_status: str = "ASSUMED_RECURRING"
    timetable_warning: Optional[str] = None
    is_verified_current_service: bool = False


class RaptorEngine:
    """Core RAPTOR transit routing engine."""

    def __init__(self, timetable: Timetable):
        self.timetable = timetable
        self.config = timetable.config

    def route(self, query: RaptorQuery) -> List[PlannedJourney]:
        """Execute RAPTOR algorithm and return Pareto-optimal journeys."""
        # Check timetable freshness
        status, warning = self.timetable.check_freshness(
            service_date=query.service_date,
            allow_assumed_recurring=query.allow_assumed_recurring,
        )
        if status in [TimetableStatus.UNAVAILABLE, TimetableStatus.EXPIRED]:
            return []

        # 1. Resolve Access & Egress Stops
        access_stops: Dict[str, Tuple[float, float]] = {}  # stop_id -> (dist_m, walk_s)
        egress_stops: Dict[str, Tuple[float, float]] = {}  # stop_id -> (dist_m, walk_s)

        effective_speed = (
            (query.walking_speed_kmh / 3.6) / query.detour_factor
        )

        # Origin resolution
        if query.origin_stop_id:
            sid = str(query.origin_stop_id)
            if sid in self.timetable.stops:
                access_stops[sid] = (0.0, 0.0)
            else:
                return []
        elif query.origin_coord:
            lat, lon = query.origin_coord
            nearby = self.timetable.find_nearby_stops(
                lat=lat,
                lon=lon,
                radius_m=query.max_access_radius_m,
                expand_radius_m=query.expanded_access_radius_m,
            )
            for stop, dist, walk_s in nearby:
                access_stops[stop.stop_id] = (dist, walk_s)
            if not access_stops:
                return []
        else:
            raise ValueError("Query must specify either origin_stop_id or origin_coord")

        # Destination resolution
        if query.dest_stop_id:
            sid = str(query.dest_stop_id)
            if sid in self.timetable.stops:
                egress_stops[sid] = (0.0, 0.0)
            else:
                return []
        elif query.dest_coord:
            lat, lon = query.dest_coord
            nearby = self.timetable.find_nearby_stops(
                lat=lat,
                lon=lon,
                radius_m=query.max_access_radius_m,
                expand_radius_m=query.expanded_access_radius_m,
            )
            for stop, dist, walk_s in nearby:
                egress_stops[stop.stop_id] = (dist, walk_s)
            if not egress_stops:
                return []
        else:
            raise ValueError("Query must specify either dest_stop_id or dest_coord")

        # Check for direct origin-destination walk
        journeys: List[PlannedJourney] = []
        if query.origin_coord and query.dest_coord:
            direct_dist = float(
                math.hypot(
                    (query.origin_coord[0] - query.dest_coord[0]) * 111320.0,
                    (query.origin_coord[1] - query.dest_coord[1])
                    * 111320.0
                    * math.cos(math.radians(query.origin_coord[0])),
                )
            )
            if direct_dist <= query.max_access_radius_m:
                walk_s = direct_dist / effective_speed
                leg = WalkingLeg(
                    leg_type="DIRECT_WALK",
                    from_name="Origin",
                    to_name="Destination",
                    from_stop_id=None,
                    to_stop_id=None,
                    start_time_s=query.departure_time_s,
                    end_time_s=query.departure_time_s + walk_s,
                    duration_s=walk_s,
                    distance_m=direct_dist,
                )
                acct = JourneyAccounting(
                    access_walk_s=walk_s,
                    initial_wait_s=0.0,
                    total_ride_s=0.0,
                    total_transfer_walk_s=0.0,
                    total_transfer_wait_s=0.0,
                    egress_walk_s=0.0,
                    sum_components_s=walk_s,
                    total_journey_time_s=walk_s,
                    discrepancy_s=0.0,
                )
                journeys.append(
                    PlannedJourney(
                        round_k=0,
                        num_transfers=0,
                        departure_time_s=query.departure_time_s,
                        arrival_time_s=query.departure_time_s + walk_s,
                        total_journey_time_s=walk_s,
                        legs=[leg],
                        accounting=acct,
                        confidence_score=1.0,
                    )
                )

        # 2. RAPTOR State Initialization
        # Rounds 0..K (K = max_transfers)
        K = query.max_transfers
        tau: Dict[int, Dict[str, float]] = {k: {} for k in range(K + 1)}
        tau_best: Dict[str, float] = {}

        # Backtrack pointers:
        # backtrack[k][stop_id] = pointer dict describing how stop_id was reached in round k
        backtrack: Dict[int, Dict[str, Dict[str, Any]]] = {k: {} for k in range(K + 1)}

        # Round 0: Initial access walk to access stops
        marked_stops: Set[str] = set()
        for sid, (dist, walk_s) in access_stops.items():
            arr_0 = query.departure_time_s + walk_s
            tau[0][sid] = arr_0
            tau_best[sid] = arr_0
            marked_stops.add(sid)
            backtrack[0][sid] = {
                "type": "access",
                "stop_id": sid,
                "walk_dist_m": dist,
                "walk_time_s": walk_s,
                "start_time": query.departure_time_s,
                "end_time": arr_0,
            }

        # Track best overall arrival at destination
        tau_dest_best: float = float("inf")
        best_dest_stop: Optional[str] = None
        best_dest_round: Optional[int] = None

        # Check if destination reached via initial walk
        for sid, (dist, walk_s) in egress_stops.items():
            if sid in tau[0]:
                arr_dest = tau[0][sid] + walk_s
                if arr_dest < tau_dest_best:
                    tau_dest_best = arr_dest
                    best_dest_stop = sid
                    best_dest_round = 0

        # 3. Main RAPTOR Loop: Rounds 1 to K
        for k in range(1, K + 1):
            # Copy previous round arrival times as default
            for sid, t in tau[k - 1].items():
                tau[k][sid] = t

            if not marked_stops:
                break

            # Accumulate routes (patterns) serving marked stops
            routes_to_evaluate: Dict[int, int] = {}  # pattern_id -> earliest stop_idx
            for s in marked_stops:
                for pat_id, stop_idx in self.timetable.stop_to_patterns.get(s, []):
                    if pat_id not in routes_to_evaluate or stop_idx < routes_to_evaluate[pat_id]:
                        routes_to_evaluate[pat_id] = stop_idx

            marked_stops.clear()

            # Process each accumulated route pattern
            for pat_id, start_stop_idx in routes_to_evaluate.items():
                pattern = self.timetable.patterns[pat_id]
                stop_ids = pattern.stop_ids
                trips = pattern.trips
                deps_mat = pattern.deps_matrix
                arrs_mat = pattern.arrs_matrix

                boarded_trip_idx: Optional[int] = None
                boarded_trip: Optional[Trip] = None
                board_stop_idx: Optional[int] = None
                board_stop_id: Optional[str] = None
                board_time: Optional[float] = None

                for i in range(start_stop_idx, len(stop_ids)):
                    curr_stop = stop_ids[i]

                    # 1. Alight check: if we have a boarded trip, can we alight at curr_stop?
                    if boarded_trip_idx is not None:
                        arr_time = float(arrs_mat[boarded_trip_idx, i])
                        # Pruning condition: can only improve if arrives before tau_k and before best dest
                        if arr_time < tau[k].get(curr_stop, float("inf")) and arr_time < tau_dest_best:
                            tau[k][curr_stop] = arr_time
                            tau_best[curr_stop] = min(tau_best.get(curr_stop, float("inf")), arr_time)
                            marked_stops.add(curr_stop)

                            # Record backtrack pointer
                            backtrack[k][curr_stop] = {
                                "type": "transit",
                                "board_stop_id": board_stop_id,
                                "board_stop_name": self.timetable.stops[board_stop_id].stop_name,
                                "board_stop_idx": board_stop_idx,
                                "alight_stop_id": curr_stop,
                                "alight_stop_name": self.timetable.stops[curr_stop].stop_name,
                                "alight_stop_idx": i,
                                "board_time": board_time,
                                "alight_time": arr_time,
                                "trip": boarded_trip,
                                "pattern": pattern,
                                "round": k,
                            }

                            # Check destination arrival
                            if curr_stop in egress_stops:
                                e_dist, e_walk = egress_stops[curr_stop]
                                if arr_time + e_walk < tau_dest_best:
                                    tau_dest_best = arr_time + e_walk
                                    best_dest_stop = curr_stop
                                    best_dest_round = k

                    # 2. Boarding check: can we board an earlier or better trip at curr_stop?
                    prev_arr = tau[k - 1].get(curr_stop, float("inf"))
                    if prev_arr < float("inf"):
                        # In round 1: first boarding, so departure >= tau[0]
                        # In round > 1: transfer boarding! Must satisfy minimum transfer buffer (>= 120s)
                        min_dep_time = prev_arr + (0.0 if k == 1 else query.min_transfer_buffer_s)
                        
                        dep_col = deps_mat[:, i]
                        cand_idx = int(np.searchsorted(dep_col, min_dep_time))
                        if cand_idx < len(trips):
                            cand_dep = float(dep_col[cand_idx])
                            # If no trip currently boarded, or candidate departs earlier than boarded trip's dep at i
                            if boarded_trip_idx is None or cand_idx < boarded_trip_idx:
                                boarded_trip_idx = cand_idx
                                boarded_trip = trips[cand_idx]
                                board_stop_idx = i
                                board_stop_id = curr_stop
                                board_time = cand_dep

            # Footpath relaxation for round k
            stops_to_relax = list(marked_stops)
            for s in stops_to_relax:
                arr_s = tau[k][s]
                for fp in self.timetable.get_transfer_footpaths(s):
                    target_s = fp.to_stop_id
                    if target_s == s:
                        continue
                    walk_time = fp.walking_time_s
                    target_arr = arr_s + walk_time
                    if target_arr < tau[k].get(target_s, float("inf")) and target_arr < tau_dest_best:
                        tau[k][target_s] = target_arr
                        tau_best[target_s] = min(tau_best.get(target_s, float("inf")), target_arr)
                        marked_stops.add(target_s)
                        backtrack[k][target_s] = {
                            "type": "footpath",
                            "from_stop_id": s,
                            "from_stop_name": self.timetable.stops[s].stop_name,
                            "to_stop_id": target_s,
                            "to_stop_name": self.timetable.stops[target_s].stop_name,
                            "walk_dist_m": fp.distance_m,
                            "walk_time_s": walk_time,
                            "start_time": arr_s,
                            "end_time": target_arr,
                            "round": k,
                        }

                        # Check destination arrival from footpath destination
                        if target_s in egress_stops:
                            e_dist, e_walk = egress_stops[target_s]
                            if target_arr + e_walk < tau_dest_best:
                                tau_dest_best = target_arr + e_walk
                                best_dest_stop = target_s
                                best_dest_round = k

            # Reconstruct journey for round k if destination reached
            for e_stop, (e_dist, e_walk) in egress_stops.items():
                if e_stop in tau[k] and tau[k][e_stop] < float("inf"):
                    journey = self._reconstruct_journey(
                        k=k,
                        final_stop_id=e_stop,
                        egress_dist=e_dist,
                        egress_walk=e_walk,
                        backtrack=backtrack,
                        query=query,
                    )
                    if journey and journey.accounting.is_valid:
                        journeys.append(journey)

        # Filter to unique Pareto-optimal journeys
        unique_journeys = self._filter_pareto_journeys(journeys)
        return unique_journeys

    def _reconstruct_journey(
        self,
        k: int,
        final_stop_id: str,
        egress_dist: float,
        egress_walk: float,
        backtrack: Dict[int, Dict[str, Dict[str, Any]]],
        query: RaptorQuery,
    ) -> Optional[PlannedJourney]:
        """Reconstruct the sequence of legs backwards from destination."""
        legs_rev: List[Any] = []
        curr_stop = final_stop_id
        curr_round = k

        # 1. Egress leg
        dest_name = (
            self.timetable.stops[final_stop_id].stop_name
            if query.dest_stop_id
            else "Destination"
        )
        final_arr = backtrack[curr_round].get(curr_stop, {}).get("alight_time", None)
        if final_arr is None:
            # Reached by footpath?
            final_arr = backtrack[curr_round].get(curr_stop, {}).get("end_time", None)
        if final_arr is None:
            return None

        if egress_walk > 0:
            egress_leg = WalkingLeg(
                leg_type="EGRESS",
                from_name=self.timetable.stops[final_stop_id].stop_name,
                to_name=dest_name,
                from_stop_id=final_stop_id,
                to_stop_id=None,
                start_time_s=final_arr,
                end_time_s=final_arr + egress_walk,
                duration_s=egress_walk,
                distance_m=egress_dist,
            )
            legs_rev.append(egress_leg)

        # 2. Trace transit and footpath legs backwards
        while curr_round > 0:
            if curr_stop not in backtrack[curr_round]:
                # Fall back to previous round
                curr_round -= 1
                continue

            ptr = backtrack[curr_round][curr_stop]
            ptr_type = ptr["type"]

            if ptr_type == "footpath":
                from_sid = ptr["from_stop_id"]
                fp_leg = WalkingLeg(
                    leg_type="TRANSFER",
                    from_name=ptr["from_stop_name"],
                    to_name=ptr["to_stop_name"],
                    from_stop_id=from_sid,
                    to_stop_id=curr_stop,
                    start_time_s=ptr["start_time"],
                    end_time_s=ptr["end_time"],
                    duration_s=ptr["walk_time_s"],
                    distance_m=ptr["walk_dist_m"],
                )
                legs_rev.append(fp_leg)
                curr_stop = from_sid
                # Now curr_stop was reached by transit in curr_round
                continue

            elif ptr_type == "transit":
                trip = ptr["trip"]
                pattern = ptr["pattern"]
                b_stop = ptr["board_stop_id"]
                a_stop = ptr["alight_stop_id"]
                b_idx = ptr["board_stop_idx"]
                a_idx = ptr["alight_stop_idx"]
                b_time = ptr["board_time"]
                a_time = ptr["alight_time"]

                intermediate = list(pattern.stop_ids[b_idx + 1 : a_idx])
                stop_pairs = [
                    (pattern.stop_ids[m], pattern.stop_ids[m + 1])
                    for m in range(b_idx, a_idx)
                ]

                t_leg = TransitLeg(
                    route_id=pattern.route_id,
                    trip_id=trip.trip_id,
                    pattern_id=pattern.pattern_id,
                    board_stop_id=b_stop,
                    board_stop_name=ptr["board_stop_name"],
                    alight_stop_id=a_stop,
                    alight_stop_name=ptr["alight_stop_name"],
                    board_time_s=b_time,
                    alight_time_s=a_time,
                    ride_duration_s=a_time - b_time,
                    intermediate_stops=intermediate,
                    stop_segments=stop_pairs,
                    sched_departure_s=b_time,
                    sched_arrival_s=a_time,
                    sched_duration_s=a_time - b_time,
                )
                legs_rev.append(t_leg)
                curr_stop = b_stop
                curr_round -= 1

            elif ptr_type == "access":
                break
            else:
                break

        # 3. Access leg
        if curr_stop in backtrack[0]:
            acc_ptr = backtrack[0][curr_stop]
            acc_walk_s = acc_ptr["walk_time_s"]
            acc_dist = acc_ptr["walk_dist_m"]
            if acc_walk_s > 0:
                acc_leg = WalkingLeg(
                    leg_type="ACCESS",
                    from_name="Origin",
                    to_name=self.timetable.stops[curr_stop].stop_name,
                    from_stop_id=None,
                    to_stop_id=curr_stop,
                    start_time_s=query.departure_time_s,
                    end_time_s=query.departure_time_s + acc_walk_s,
                    duration_s=acc_walk_s,
                    distance_m=acc_dist,
                )
                legs_rev.append(acc_leg)

        legs = list(reversed(legs_rev))
        if not legs:
            return None

        # 4. Strict Accounting Identity Calculation
        access_walk_s = 0.0
        initial_wait_s = 0.0
        total_ride_s = 0.0
        total_transfer_walk_s = 0.0
        total_transfer_wait_s = 0.0
        egress_walk_s = 0.0

        num_transfers = 0
        first_transit = True
        last_alight_time: Optional[float] = None
        current_time = query.departure_time_s

        for leg in legs:
            if isinstance(leg, WalkingLeg):
                if leg.leg_type == "ACCESS":
                    access_walk_s += leg.duration_s
                    current_time += leg.duration_s
                elif leg.leg_type == "TRANSFER":
                    total_transfer_walk_s += leg.duration_s
                    current_time += leg.duration_s
                elif leg.leg_type == "EGRESS":
                    egress_walk_s += leg.duration_s
                    current_time += leg.duration_s
                elif leg.leg_type == "DIRECT_WALK":
                    access_walk_s += leg.duration_s
                    current_time += leg.duration_s
            elif isinstance(leg, TransitLeg):
                if first_transit:
                    # Initial wait: from reaching initial boarding stop to bus departure
                    wait = leg.board_time_s - current_time
                    initial_wait_s = max(wait, 0.0)
                    first_transit = False
                else:
                    # Transfer wait: from arriving at transfer platform to connecting bus departure
                    wait = leg.board_time_s - current_time
                    total_transfer_wait_s += max(wait, 0.0)
                    num_transfers += 1

                total_ride_s += leg.ride_duration_s
                current_time = leg.alight_time_s

        total_journey_time_s = (
            legs[-1].end_time_s if isinstance(legs[-1], WalkingLeg) else legs[-1].alight_time_s
        ) - query.departure_time_s

        sum_components_s = (
            access_walk_s
            + initial_wait_s
            + total_ride_s
            + total_transfer_walk_s
            + total_transfer_wait_s
            + egress_walk_s
        )

        discrepancy_s = total_journey_time_s - sum_components_s

        accounting = JourneyAccounting(
            access_walk_s=round(access_walk_s, 2),
            initial_wait_s=round(initial_wait_s, 2),
            total_ride_s=round(total_ride_s, 2),
            total_transfer_walk_s=round(total_transfer_walk_s, 2),
            total_transfer_wait_s=round(total_transfer_wait_s, 2),
            egress_walk_s=round(egress_walk_s, 2),
            sum_components_s=round(sum_components_s, 2),
            total_journey_time_s=round(total_journey_time_s, 2),
            discrepancy_s=round(discrepancy_s, 4),
        )

        dep_time = query.departure_time_s
        arr_time = query.departure_time_s + total_journey_time_s

        status, warning = self.timetable.check_freshness(
            service_date=query.service_date,
            allow_assumed_recurring=query.allow_assumed_recurring,
        )

        return PlannedJourney(
            round_k=k,
            num_transfers=num_transfers,
            departure_time_s=dep_time,
            arrival_time_s=arr_time,
            total_journey_time_s=total_journey_time_s,
            legs=legs,
            accounting=accounting,
            confidence_score=1.0,
            heuristic_confidence_score=1.0,
            confidence_score_type="HEURISTIC",
            confidence_explanation="Heuristic score representing operational and empirical data support; NOT a calibrated probability.",
            timetable_status=status.value,
            timetable_warning=warning,
            is_verified_current_service=(status == TimetableStatus.CURRENT_VERIFIED),
        )

    def _filter_pareto_journeys(self, journeys: List[PlannedJourney]) -> List[PlannedJourney]:
        """Filter to non-dominated journeys (transfers vs arrival time) and deduplicate."""
        if not journeys:
            return []

        # Sort by arrival time then transfers
        journeys.sort(key=lambda j: (j.arrival_time_s, j.num_transfers, j.total_journey_time_s))

        pareto: List[PlannedJourney] = []
        seen_signatures: Set[str] = set()

        min_transfers_seen = float("inf")
        for j in journeys:
            # Route signature for deduplication
            route_sig = "-".join(
                [leg.route_id for leg in j.legs if isinstance(leg, TransitLeg)]
            )
            sig = f"{route_sig}:{round(j.arrival_time_s / 60)}"

            if sig in seen_signatures:
                continue

            # Pareto check: strictly fewer transfers if arriving later
            if j.num_transfers < min_transfers_seen:
                pareto.append(j)
                seen_signatures.add(sig)
                min_transfers_seen = j.num_transfers

        return pareto if pareto else [journeys[0]]

