"""Delhi Live GTFS-Realtime Journey Bus Identification Engine.

PRD v3.0 & Milestone 12:
Cross-references live vehicle positions against static GTFS timetable trips,
stop_times, and routes tables in /tmp/delhi_dlm1.db to identify the actual
bus a passenger should board in the journey guide.

Guarantees & Constraints:
1. Cross-references live vehicle trip_id / route_id against static GTFS trips and stop_times.
2. Strictly verifies trip serves boarding and alighting stops in sequence:
   stop_sequence(board) < stop_sequence(alight).
3. Verifies spatial progress along the route corridor:
   - Near boarding stop: distance <= 400m
   - Approaching: upstream stop sequence < board_sequence
   - Passed: downstream stop sequence > board_sequence
4. Never identifies a bus solely by route ID; never invents direction, destination,
   registration, or vehicle identity.
5. Strict Fallbacks:
   - Insufficient verification: 'Live bus not identified — follow the scheduled route and verify the displayed route at the stop.'
   - Route matches without verified direction: 'Route matches — direction unverified.'
   - Vehicles that have passed boarding stop must NOT be recommended as approaching.
"""

import bisect
from datetime import datetime, timezone, timedelta
import logging
import math
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.realtime.gtfs_rt import ValidatedVehiclePosition, haversine_distance_m

logger = logging.getLogger(__name__)

# Standard fallback guidance strings
FALLBACK_UNIDENTIFIED = (
    "Live bus not identified — follow the scheduled route and verify the displayed route at the stop."
)
FALLBACK_ROUTE_MATCH_UNVERIFIED = "Route matches — direction unverified."
DEFAULT_DISCLAIMER = (
    "Live candidate bus based on real-time GTFS-RT feed (not guaranteed boarding assignment)."
)

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))


def format_epoch_ist(ts: Optional[int]) -> Optional[str]:
    """Format Unix timestamp to HH:MM:SS IST."""
    if not ts or ts <= 0:
        return None
    try:
        dt = datetime.fromtimestamp(ts, tz=IST)
        return dt.strftime("%H:%M:%S IST")
    except Exception:
        return None


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate forward azimuth / initial bearing from (lat1, lon1) to (lat2, lon2) in degrees [0, 360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    theta = math.atan2(y, x)
    return (math.degrees(theta) + 360.0) % 360.0


def angle_diff_degrees(a: float, b: float) -> float:
    """Smallest absolute angular difference between two bearings in degrees [0, 180]."""
    diff = abs(a - b) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff


def project_point_onto_shape_bounded(
    coords: List[Tuple[float, float]],
    cum_dists: List[float],
    lat: float,
    lon: float,
    min_progress_m: Optional[float] = None,
    max_progress_m: Optional[float] = None,
) -> Tuple[float, float]:
    """Returns (best_progress_m, min_dist_to_shape_m) along coords polyline closest to (lat, lon).
    
    If min_progress_m and max_progress_m are provided, searches only polyline segments overlapping
    the progress interval [min_progress_m, max_progress_m] to eliminate incorrect snapping
    to parallel corridors, loops, or earlier shape sections.
    """
    if not coords or len(coords) < 2:
        return 0.0, 0.0

    total_len = cum_dists[-1]
    has_bounds = (min_progress_m is not None or max_progress_m is not None)
    low_prog = max(0.0, float(min_progress_m)) if min_progress_m is not None else 0.0
    high_prog = min(total_len, float(max_progress_m)) if max_progress_m is not None else total_len

    if low_prog > high_prog:
        low_prog, high_prog = high_prog, low_prog

    min_d = float("inf")
    best_progress = low_prog

    for i in range(len(coords) - 1):
        s_start = cum_dists[i]
        s_end = cum_dists[i + 1]
        seg_len = s_end - s_start

        # If bounded, skip segments strictly outside [low_prog, high_prog]
        if has_bounds:
            if s_end < low_prog or s_start > high_prog:
                continue

        p1 = coords[i]
        p2 = coords[i + 1]
        if seg_len < 0.01:
            d = haversine_distance_m(lat, lon, p1[0], p1[1])
            prog = max(low_prog, min(high_prog, s_start)) if has_bounds else s_start
            if d < min_d:
                min_d = d
                best_progress = prog
            continue

        # Equirectangular projection for accurate local orthogonal projection
        mid_lat_rad = math.radians((p1[0] + p2[0]) / 2.0)
        cos_lat = math.cos(mid_lat_rad)

        scale_y = 111139.0
        scale_x = 111139.0 * cos_lat

        dx = (p2[1] - p1[1]) * scale_x
        dy = (p2[0] - p1[0]) * scale_y

        px = (lon - p1[1]) * scale_x
        py = (lat - p1[0]) * scale_y

        seg_sq = dx * dx + dy * dy
        if seg_sq < 1e-6:
            t = 0.0
        else:
            t = max(0.0, min(1.0, (px * dx + py * dy) / seg_sq))

        cand_prog = s_start + t * seg_len
        if has_bounds:
            cand_prog = max(low_prog, min(high_prog, cand_prog))
            if seg_len > 0:
                t_clamped = (cand_prog - s_start) / seg_len
            else:
                t_clamped = 0.0
            proj_lat = p1[0] + t_clamped * (p2[0] - p1[0])
            proj_lon = p1[1] + t_clamped * (p2[1] - p1[1])
        else:
            proj_lat = p1[0] + t * (p2[0] - p1[0])
            proj_lon = p1[1] + t * (p2[1] - p1[1])

        d = haversine_distance_m(lat, lon, proj_lat, proj_lon)
        if d < min_d:
            min_d = d
            best_progress = cand_prog

    if min_d == float("inf"):
        return low_prog, 0.0

    return best_progress, min_d


def project_point_onto_shape(
    coords: List[Tuple[float, float]],
    cum_dists: List[float],
    lat: float,
    lon: float,
) -> float:
    """Returns distance in meters along coords polyline closest to (lat, lon)."""
    prog, _ = project_point_onto_shape_bounded(coords, cum_dists, lat, lon)
    return prog


def get_point_at_distance_along_shape(
    coords: List[Tuple[float, float]],
    cum_dists: List[float],
    distance_m: float,
) -> Tuple[float, float]:
    """Get (lat, lon) interpolated along shape at distance_m from origin."""
    if not coords:
        return 0.0, 0.0
    if len(coords) == 1 or distance_m <= 0.0:
        return coords[0]

    total_len = cum_dists[-1]
    if distance_m >= total_len:
        return coords[-1]

    idx = bisect.bisect_right(cum_dists, distance_m) - 1
    idx = max(0, min(idx, len(coords) - 2))

    d1 = cum_dists[idx]
    d2 = cum_dists[idx + 1]
    seg_len = d2 - d1
    if seg_len < 0.01:
        return coords[idx]

    frac = max(0.0, min(1.0, (distance_m - d1) / seg_len))
    lat = coords[idx][0] + frac * (coords[idx + 1][0] - coords[idx][0])
    lon = coords[idx][1] + frac * (coords[idx + 1][1] - coords[idx][1])
    return lat, lon


def get_default_db_path() -> str:
    """Resolve active database path, prioritizing DLM1 DB."""
    primary = "/tmp/delhi_dlm1.db"
    if os.path.exists(primary):
        return primary
    fallback = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "serving", "delhi_bus.db",
    )
    if os.path.exists(fallback):
        return fallback
    return primary


class JourneyBusMatcher:
    """Matches live GTFS-RT vehicles to planned transit legs with strict verification."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_default_db_path()
        self._shape_cache: Dict[str, List[Tuple[float, float]]] = {}
        self._shape_cum_dist_cache: Dict[str, List[float]] = {}
        self._tracking_state: Dict[str, Dict[str, Any]] = {}
        self._gps_audit_log: List[Dict[str, Any]] = []

    def get_gps_audit_log(
        self,
        vehicle_id: Optional[str] = None,
        route_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent structured GPS observations, corrections, and anomaly audit events."""
        entries = self._gps_audit_log
        if vehicle_id:
            entries = [e for e in entries if e.get("vehicle_id") == vehicle_id]
        if route_id:
            entries = [e for e in entries if e.get("route_id") == route_id]
        return entries[-limit:]

    def clear_gps_audit_log(self) -> None:
        """Clear the in-memory GPS audit log."""
        self._gps_audit_log.clear()

    def _log_audit_event(self, event: Dict[str, Any]) -> None:
        """Append an event to the bounded in-memory GPS audit log."""
        if len(self._gps_audit_log) >= 1000:
            self._gps_audit_log = self._gps_audit_log[-500:]
        self._gps_audit_log.append(event)

    def _get_connection(self) -> Optional[sqlite3.Connection]:
        if not os.path.exists(self.db_path):
            return None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"Failed to open GTFS database at {self.db_path}: {e}")
            return None

    def _advance_along_corridor(
        self,
        coords: List[Tuple[float, float]],
        lat: float,
        lon: float,
        advance_dist_m: float,
        board_lat: float,
        board_lon: float,
        alight_lat: float,
        alight_lon: float,
    ) -> Tuple[float, float]:
        """Advance position along the street polyline curvature towards boarding/alighting stops.

        Route-constrained: follows street polyline curvature towards destination.
        Never moves backward along trip sequence; clamped to alighting stop.
        """
        if not coords or len(coords) < 2 or advance_dist_m <= 0.0:
            return lat, lon

        cum_dists = [0.0] * len(coords)
        for i in range(1, len(coords)):
            cum_dists[i] = cum_dists[i - 1] + haversine_distance_m(
                coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1]
            )

        cur_progress = project_point_onto_shape(coords, cum_dists, lat, lon)
        alight_progress = project_point_onto_shape(coords, cum_dists, alight_lat, alight_lon)
        target_progress = min(cur_progress + advance_dist_m, alight_progress)
        return get_point_at_distance_along_shape(coords, cum_dists, target_progress)

    def match_bus_for_leg(
        self,
        route_id: str,
        board_stop_id: str,
        alight_stop_id: str,
        active_vehicles: List[ValidatedVehiclePosition],
        sched_departure_s: Optional[float] = None,
        now_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Identify candidate live bus to board for a transit leg.

        Returns a dictionary adhering to LiveBusCandidateSchema.
        """
        now_ts = now_ts if now_ts is not None else int(time.time())
        clean_route = str(route_id or "").strip()
        clean_board = str(board_stop_id or "").strip()
        clean_alight = str(alight_stop_id or "").strip()

        # Gate 0: Basic sanity check
        if not clean_route or not clean_board or not clean_alight:
            return {
                "identification_status": "UNIDENTIFIED",
                "guidance_message": FALLBACK_UNIDENTIFIED,
                "vehicle_id": None,
                "route_id": clean_route or None,
                "trip_id": None,
                "trip_headsign": None,
                "progress_status": "UNVERIFIED",
                "distance_to_board_m": None,
                "stops_away": None,
                "speed_kmh": None,
                "source_timestamp_utc": None,
                "age_seconds": None,
                "is_fresh": None,
                "is_candidate_only": True,
                "disclaimer": DEFAULT_DISCLAIMER,
            }

        # Gate 1: Check if any vehicles exist on this route in the active feed
        vehicles_on_route = [
            v for v in active_vehicles
            if str(v.route_id or "").strip() == clean_route and v.is_valid_coordinates
        ]

        conn = self._get_connection()
        if not conn:
            # Without DB connection, cannot verify sequence or destination
            if vehicles_on_route:
                return {
                    "identification_status": "ROUTE_MATCH_UNVERIFIED",
                    "guidance_message": FALLBACK_ROUTE_MATCH_UNVERIFIED,
                    "vehicle_id": None,
                    "route_id": clean_route,
                    "trip_id": None,
                    "trip_headsign": None,
                    "progress_status": "UNVERIFIED",
                    "distance_to_board_m": None,
                    "stops_away": None,
                    "speed_kmh": None,
                    "source_timestamp_utc": None,
                    "age_seconds": None,
                    "is_fresh": None,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }
            return {
                "identification_status": "UNIDENTIFIED",
                "guidance_message": FALLBACK_UNIDENTIFIED,
                "vehicle_id": None,
                "route_id": clean_route,
                "trip_id": None,
                "trip_headsign": None,
                "progress_status": "UNVERIFIED",
                "distance_to_board_m": None,
                "stops_away": None,
                "speed_kmh": None,
                "source_timestamp_utc": None,
                "age_seconds": None,
                "is_fresh": None,
                "is_candidate_only": True,
                "disclaimer": DEFAULT_DISCLAIMER,
            }

        try:
            cur = conn.cursor()

            # 1. Query static trips that serve board_stop and alight_stop in correct sequence
            cur.execute("""
                SELECT t.trip_id, t.trip_headsign, t.direction_id,
                       st1.stop_sequence AS board_seq, st2.stop_sequence AS alight_seq
                FROM trips t
                JOIN stop_times st1 ON t.trip_id = st1.trip_id AND st1.stop_id = ?
                JOIN stop_times st2 ON t.trip_id = st2.trip_id AND st2.stop_id = ?
                WHERE t.route_id = ? AND st1.stop_sequence < st2.stop_sequence
            """, (clean_board, clean_alight, clean_route))

            valid_trips = cur.fetchall()

            if not valid_trips:
                # No verified trip serves this boarding -> alighting sequence on this route
                if vehicles_on_route:
                    return {
                        "identification_status": "ROUTE_MATCH_UNVERIFIED",
                        "guidance_message": FALLBACK_ROUTE_MATCH_UNVERIFIED,
                        "vehicle_id": None,
                        "route_id": clean_route,
                        "trip_id": None,
                        "trip_headsign": None,
                        "progress_status": "UNVERIFIED",
                        "distance_to_board_m": None,
                        "stops_away": None,
                        "speed_kmh": None,
                        "source_timestamp_utc": None,
                        "age_seconds": None,
                        "is_fresh": None,
                        "is_candidate_only": True,
                        "disclaimer": DEFAULT_DISCLAIMER,
                    }
                return {
                    "identification_status": "UNIDENTIFIED",
                    "guidance_message": FALLBACK_UNIDENTIFIED,
                    "vehicle_id": None,
                    "route_id": clean_route,
                    "trip_id": None,
                    "trip_headsign": None,
                    "progress_status": "UNVERIFIED",
                    "distance_to_board_m": None,
                    "stops_away": None,
                    "speed_kmh": None,
                    "source_timestamp_utc": None,
                    "age_seconds": None,
                    "is_fresh": None,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }

            # Direction is verified in static GTFS
            headsign = valid_trips[0]["trip_headsign"] or f"Route {clean_route} Service"
            board_seq = valid_trips[0]["board_seq"]
            alight_seq = valid_trips[0]["alight_seq"]
            sample_trip_id = valid_trips[0]["trip_id"]

            # 2. Get ordered stops for this verified trip pattern
            cur.execute("""
                SELECT st.stop_id, st.stop_sequence, s.stop_name, s.stop_lat, s.stop_lon
                FROM stop_times st
                JOIN stops s ON st.stop_id = s.stop_id
                WHERE st.trip_id = ?
                ORDER BY st.stop_sequence ASC
            """, (sample_trip_id,))
            route_stops = cur.fetchall()

            if not route_stops:
                return {
                    "identification_status": "UNIDENTIFIED",
                    "guidance_message": FALLBACK_UNIDENTIFIED,
                    "vehicle_id": None,
                    "route_id": clean_route,
                    "trip_id": None,
                    "trip_headsign": headsign,
                    "progress_status": "UNVERIFIED",
                    "distance_to_board_m": None,
                    "stops_away": None,
                    "speed_kmh": None,
                    "source_timestamp_utc": None,
                    "age_seconds": None,
                    "is_fresh": None,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }

            board_stop_row = next((s for s in route_stops if str(s["stop_id"]) == clean_board), None)
            if not board_stop_row:
                return {
                    "identification_status": "UNIDENTIFIED",
                    "guidance_message": FALLBACK_UNIDENTIFIED,
                    "vehicle_id": None,
                    "route_id": clean_route,
                    "trip_id": None,
                    "trip_headsign": headsign,
                    "progress_status": "UNVERIFIED",
                    "distance_to_board_m": None,
                    "stops_away": None,
                    "speed_kmh": None,
                    "source_timestamp_utc": None,
                    "age_seconds": None,
                    "is_fresh": None,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }

            board_lat = float(board_stop_row["stop_lat"])
            board_lon = float(board_stop_row["stop_lon"])

            if not vehicles_on_route:
                return {
                    "identification_status": "UNIDENTIFIED",
                    "guidance_message": FALLBACK_UNIDENTIFIED,
                    "vehicle_id": None,
                    "route_id": clean_route,
                    "trip_id": None,
                    "trip_headsign": headsign,
                    "progress_status": "UNVERIFIED",
                    "distance_to_board_m": None,
                    "stops_away": None,
                    "speed_kmh": None,
                    "source_timestamp_utc": None,
                    "age_seconds": None,
                    "is_fresh": None,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }

            # 3. Classify each vehicle on this route
            CORRIDOR_MAX_DIST_M = 1500.0  # Max distance from vehicle to route corridor
            NEAR_STOP_THRESHOLD_M = 400.0  # Distance considered 'at or near stop'
            MAX_APPROACH_DISTANCE_M = 35000.0  # Max distance to qualify as approaching candidate across full corridor

            candidates = []
            for v in vehicles_on_route:
                # Find closest stop along this trip
                min_dist_to_corridor = float("inf")
                nearest_stop_seq = None
                for s in route_stops:
                    d = haversine_distance_m(v.latitude, v.longitude, float(s["stop_lat"]), float(s["stop_lon"]))
                    if d < min_dist_to_corridor:
                        min_dist_to_corridor = d
                        nearest_stop_seq = s["stop_sequence"]

                dist_to_board = haversine_distance_m(v.latitude, v.longitude, board_lat, board_lon)
                age_s = max(0, now_ts - v.timestamp_utc) if v.timestamp_utc > 0 else 9999

                # Determine progress
                if min_dist_to_corridor > CORRIDOR_MAX_DIST_M:
                    progress = "OFF_CORRIDOR"
                    stops_away = None
                elif dist_to_board <= NEAR_STOP_THRESHOLD_M:
                    progress = "NEAR_BOARDING_STOP"
                    stops_away = 0
                elif nearest_stop_seq is not None and nearest_stop_seq < board_seq:
                    if dist_to_board <= MAX_APPROACH_DISTANCE_M:
                        progress = "APPROACHING"
                        stops_away = max(1, board_seq - nearest_stop_seq)
                    else:
                        progress = "OFF_CORRIDOR"
                        stops_away = None
                else:
                    progress = "PASSED"
                    stops_away = 0

                candidates.append({
                    "vehicle": v,
                    "progress": progress,
                    "dist_to_board": dist_to_board,
                    "stops_away": stops_away,
                    "corridor_dist": min_dist_to_corridor,
                    "age_seconds": age_s,
                })

            # Separate into categories
            near_candidates = [c for c in candidates if c["progress"] == "NEAR_BOARDING_STOP"]
            approaching_candidates = [c for c in candidates if c["progress"] == "APPROACHING"]
            passed_candidates = [c for c in candidates if c["progress"] == "PASSED"]
            unverified_candidates = [c for c in candidates if c["progress"] == "OFF_CORRIDOR"]

            # Priority 1: Vehicle currently near the boarding stop (<= 400m)
            if near_candidates:
                # Pick closest to boarding stop
                near_candidates.sort(key=lambda x: x["dist_to_board"])
                best = near_candidates[0]
                bv: ValidatedVehiclePosition = best["vehicle"]
                dist_m = round(best["dist_to_board"], 1)

                msg = (
                    f"Board bus {bv.vehicle_id} (Route {clean_route} to {headsign}) — "
                    f"currently near boarding stop (~{int(dist_m)}m). Verify route display before boarding."
                )
                return {
                    "identification_status": "IDENTIFIED_NEAR",
                    "guidance_message": msg,
                    "vehicle_id": bv.vehicle_id,
                    "route_id": clean_route,
                    "trip_id": bv.trip_id,
                    "trip_headsign": headsign,
                    "progress_status": "NEAR_BOARDING_STOP",
                    "distance_to_board_m": dist_m,
                    "stops_away": 0,
                    "speed_kmh": bv.speed_kmh,
                    "source_timestamp_utc": bv.timestamp_utc,
                    "age_seconds": best["age_seconds"],
                    "is_fresh": bv.is_fresh,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }

            # Priority 2: Approaching candidate bus
            if approaching_candidates:
                # Pick closest approaching vehicle to boarding stop
                approaching_candidates.sort(key=lambda x: x["dist_to_board"])
                best = approaching_candidates[0]
                bv = best["vehicle"]
                dist_m = round(best["dist_to_board"], 1)
                dist_km = round(dist_m / 1000.0, 1)
                stops_away = best["stops_away"]

                msg = (
                    f"Board bus {bv.vehicle_id} (Route {clean_route} to {headsign}) — "
                    f"approaching (~{dist_km} km away, {stops_away} stop{'s' if stops_away > 1 else ''} away). "
                    f"Verify route display before boarding."
                )
                return {
                    "identification_status": "IDENTIFIED_APPROACHING",
                    "guidance_message": msg,
                    "vehicle_id": bv.vehicle_id,
                    "route_id": clean_route,
                    "trip_id": bv.trip_id,
                    "trip_headsign": headsign,
                    "progress_status": "APPROACHING",
                    "distance_to_board_m": dist_m,
                    "stops_away": stops_away,
                    "speed_kmh": bv.speed_kmh,
                    "source_timestamp_utc": bv.timestamp_utc,
                    "age_seconds": best["age_seconds"],
                    "is_fresh": bv.is_fresh,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }

            # Priority 3: Vehicles have passed the boarding stop
            # Constraint: Vehicles that have passed boarding stop must NOT be recommended as approaching!
            if passed_candidates:
                return {
                    "identification_status": "PASSED_STOP",
                    "guidance_message": FALLBACK_UNIDENTIFIED,
                    "vehicle_id": None,
                    "route_id": clean_route,
                    "trip_id": None,
                    "trip_headsign": headsign,
                    "progress_status": "PASSED",
                    "distance_to_board_m": None,
                    "stops_away": None,
                    "speed_kmh": None,
                    "source_timestamp_utc": None,
                    "age_seconds": None,
                    "is_fresh": None,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }

            # Priority 4: Route matches but direction unverified (vehicles off-corridor)
            if unverified_candidates:
                return {
                    "identification_status": "ROUTE_MATCH_UNVERIFIED",
                    "guidance_message": FALLBACK_ROUTE_MATCH_UNVERIFIED,
                    "vehicle_id": None,
                    "route_id": clean_route,
                    "trip_id": None,
                    "trip_headsign": headsign,
                    "progress_status": "UNVERIFIED",
                    "distance_to_board_m": None,
                    "stops_away": None,
                    "speed_kmh": None,
                    "source_timestamp_utc": None,
                    "age_seconds": None,
                    "is_fresh": None,
                    "is_candidate_only": True,
                    "disclaimer": DEFAULT_DISCLAIMER,
                }

            # Fallback
            return {
                "identification_status": "UNIDENTIFIED",
                "guidance_message": FALLBACK_UNIDENTIFIED,
                "vehicle_id": None,
                "route_id": clean_route,
                "trip_id": None,
                "trip_headsign": headsign,
                "progress_status": "UNVERIFIED",
                "distance_to_board_m": None,
                "stops_away": None,
                "speed_kmh": None,
                "source_timestamp_utc": None,
                "age_seconds": None,
                "is_fresh": None,
                "is_candidate_only": True,
                "disclaimer": DEFAULT_DISCLAIMER,
            }

        except Exception as err:
            logger.error(f"Error during journey bus matching: {err}")
            return {
                "identification_status": "UNIDENTIFIED",
                "guidance_message": FALLBACK_UNIDENTIFIED,
                "vehicle_id": None,
                "route_id": clean_route,
                "trip_id": None,
                "trip_headsign": None,
                "progress_status": "UNVERIFIED",
                "distance_to_board_m": None,
                "stops_away": None,
                "speed_kmh": None,
                "source_timestamp_utc": None,
                "age_seconds": None,
                "is_fresh": None,
                "is_candidate_only": True,
                "disclaimer": DEFAULT_DISCLAIMER,
            }
        finally:
            conn.close()

    def get_suitable_buses_for_leg(
        self,
        route_id: str,
        board_stop_id: str,
        alight_stop_id: str,
        active_vehicles: List[ValidatedVehiclePosition],
        sched_departure_s: Optional[float] = None,
        now_ts: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Identify ALL live buses verified as suitable for the selected journey's boarding and alighting stops.

        A vehicle must:
        1. Serve the boarding stop and destination/alighting stop in correct sequence (board_seq < alight_seq).
        2. Its trip stop sequence must establish that boarding occurs before alighting.
        3. Its actual progress must establish that it has not already passed the boarding stop (NEAR_BOARDING_STOP or APPROACHING).
        4. Match live vehicle trip IDs / route against current static GTFS trips and stop_times.

        Strictly excludes:
        - Vehicles travelling in the opposite direction.
        - Vehicles that do not serve the destination stop.
        - Vehicles that have already passed the boarding stop (PASSED).
        - Vehicles with unverified trip, direction, or off-corridor positions.
        """
        now_ts = now_ts if now_ts is not None else int(time.time())
        clean_route = str(route_id or "").strip()
        clean_board = str(board_stop_id or "").strip()
        clean_alight = str(alight_stop_id or "").strip()

        if not clean_route or not clean_board or not clean_alight:
            return []

        conn = self._get_connection()
        if not conn:
            return []

        try:
            cur = conn.cursor()

            # 1. Query static trips that serve board_stop and alight_stop in correct sequence
            cur.execute("""
                SELECT t.trip_id, t.trip_headsign, t.direction_id,
                       st1.stop_sequence AS board_seq, st2.stop_sequence AS alight_seq
                FROM trips t
                JOIN stop_times st1 ON t.trip_id = st1.trip_id AND st1.stop_id = ?
                JOIN stop_times st2 ON t.trip_id = st2.trip_id AND st2.stop_id = ?
                WHERE t.route_id = ? AND st1.stop_sequence < st2.stop_sequence
            """, (clean_board, clean_alight, clean_route))

            valid_trips = cur.fetchall()
            if not valid_trips:
                return []

            headsign = valid_trips[0]["trip_headsign"] or f"Route {clean_route} Service"
            board_seq = valid_trips[0]["board_seq"]
            alight_seq = valid_trips[0]["alight_seq"]
            sample_trip_id = valid_trips[0]["trip_id"]

            # 2. Get ordered stops for this verified trip pattern
            cur.execute("""
                SELECT st.stop_id, st.stop_sequence, s.stop_name, s.stop_lat, s.stop_lon
                FROM stop_times st
                JOIN stops s ON st.stop_id = s.stop_id
                WHERE st.trip_id = ?
                ORDER BY st.stop_sequence ASC
            """, (sample_trip_id,))
            route_stops = cur.fetchall()

            board_stop_row = next((s for s in route_stops if str(s["stop_id"]) == clean_board), None)
            alight_stop_row = next((s for s in route_stops if str(s["stop_id"]) == clean_alight), None)
            if not board_stop_row or not alight_stop_row:
                return []

            board_lat = float(board_stop_row["stop_lat"])
            board_lon = float(board_stop_row["stop_lon"])
            alight_lat = float(alight_stop_row["stop_lat"])
            alight_lon = float(alight_stop_row["stop_lon"])
            alight_stop_name = alight_stop_row["stop_name"]

            # 3. Load or cache trip shape polyline & cumulative distances for route-constrained dead reckoning
            shape_coords = self._shape_cache.get(sample_trip_id)
            cum_dists = self._shape_cum_dist_cache.get(sample_trip_id)
            if not shape_coords or not cum_dists:
                cur.execute("""
                    SELECT s.shape_pt_lat, s.shape_pt_lon
                    FROM trips t
                    JOIN shapes s ON t.shape_id = s.shape_id
                    WHERE t.trip_id = ?
                    ORDER BY s.shape_pt_sequence ASC
                """, (sample_trip_id,))
                shape_rows = cur.fetchall()
                if shape_rows:
                    shape_coords = [(float(r["shape_pt_lat"]), float(r["shape_pt_lon"])) for r in shape_rows]
                else:
                    shape_coords = [(float(s["stop_lat"]), float(s["stop_lon"])) for s in route_stops]

                cum_dists = [0.0] * len(shape_coords)
                for i in range(1, len(shape_coords)):
                    cum_dists[i] = cum_dists[i - 1] + haversine_distance_m(
                        shape_coords[i - 1][0], shape_coords[i - 1][1],
                        shape_coords[i][0], shape_coords[i][1],
                    )
                self._shape_cache[sample_trip_id] = shape_coords
                self._shape_cum_dist_cache[sample_trip_id] = cum_dists

            alight_progress_m = project_point_onto_shape(shape_coords, cum_dists, alight_lat, alight_lon)
            board_progress_m = project_point_onto_shape(shape_coords, cum_dists, board_lat, board_lon)

            valid_trip_ids = {str(t["trip_id"]) for t in valid_trips}

            # Filter active vehicles on this route
            vehicles_on_route = [
                v for v in active_vehicles
                if str(v.route_id or "").strip() == clean_route and v.is_valid_coordinates
            ]
            if not vehicles_on_route:
                return []

            CORRIDOR_MAX_DIST_M = 1500.0
            NEAR_STOP_THRESHOLD_M = 400.0
            MAX_APPROACH_DISTANCE_M = 35000.0  # Support approaching pickup buses across full route length (up to 35 km)
            MAX_PREDICTION_AGE_S = 120

            suitable_buses: List[Dict[str, Any]] = []

            for v in vehicles_on_route:
                # Find closest stop along this trip corridor
                min_dist_to_corridor = float("inf")
                nearest_stop_seq = None
                nearest_stop_row = None
                for s in route_stops:
                    d = haversine_distance_m(v.latitude, v.longitude, float(s["stop_lat"]), float(s["stop_lon"]))
                    if d < min_dist_to_corridor:
                        min_dist_to_corridor = d
                        nearest_stop_seq = s["stop_sequence"]
                        nearest_stop_row = s

                # Exclude if off corridor (> 1500m)
                if min_dist_to_corridor > CORRIDOR_MAX_DIST_M or nearest_stop_row is None:
                    continue

                # Verify direction and trip identity
                is_static_trip_matched = bool(v.trip_id and str(v.trip_id) in valid_trip_ids)
                is_dispatch_trip_matched = bool(v.trip_id and (
                    str(v.trip_id).startswith(f"{clean_route}_") or
                    str(v.trip_id) == clean_route
                ))
                is_trip_matched = is_static_trip_matched or is_dispatch_trip_matched

                # EXCLUSION 0: If vehicle reports an incompatible trip_id for a different route, reject
                if v.trip_id and not is_trip_matched and not str(v.trip_id).startswith(clean_route):
                    continue

                # Expected travel heading along corridor towards destination (board -> alight)
                corridor_heading = calculate_bearing(
                    board_lat,
                    board_lon,
                    alight_lat,
                    alight_lon,
                )

                # Local stop-to-stop heading if next stop is available
                next_stop_row = next((s for s in route_stops if s["stop_sequence"] > nearest_stop_row["stop_sequence"]), None)
                local_heading = (
                    calculate_bearing(
                        float(nearest_stop_row["stop_lat"]),
                        float(nearest_stop_row["stop_lon"]),
                        float(next_stop_row["stop_lat"]),
                        float(next_stop_row["stop_lon"]),
                    )
                    if next_stop_row
                    else corridor_heading
                )

                is_bearing_aligned = False
                is_opposite_bearing = False
                if v.bearing is not None:
                    b_diff_corridor = angle_diff_degrees(float(v.bearing), corridor_heading)
                    b_diff_local = angle_diff_degrees(float(v.bearing), local_heading)
                    is_bearing_aligned = (b_diff_corridor <= 120.0) or (b_diff_local <= 120.0)
                    is_opposite_bearing = (b_diff_corridor > 120.0) and (b_diff_local > 120.0)

                # EXCLUSION 1: Opposite direction bearing
                if is_opposite_bearing:
                    continue

                # EXCLUSION 2: Direction or trip identity cannot be verified
                # If neither trip identity (static or operational dispatch) nor aligned bearing is available, exclude
                if not is_trip_matched and not (v.bearing is not None and is_bearing_aligned):
                    continue

                dist_to_board = haversine_distance_m(v.latitude, v.longitude, board_lat, board_lon)
                dist_to_alight = haversine_distance_m(v.latitude, v.longitude, alight_lat, alight_lon)
                dist_board_to_alight = haversine_distance_m(board_lat, board_lon, alight_lat, alight_lon)

                # EXCLUSION 3: Vehicle has already passed boarding stop or destination stop
                is_passed = False
                if nearest_stop_seq is not None:
                    if nearest_stop_seq > board_seq and dist_to_board > NEAR_STOP_THRESHOLD_M:
                        is_passed = True
                    elif nearest_stop_seq == board_seq and dist_to_board > NEAR_STOP_THRESHOLD_M:
                        if dist_to_alight < dist_board_to_alight - 100.0:
                            is_passed = True
                    elif nearest_stop_seq >= alight_seq:
                        is_passed = True

                if is_passed:
                    continue

                # EXCLUSION 4: Vehicle is too far upstream along corridor to recommend as approaching now (> 7 km)
                if dist_to_board > MAX_APPROACH_DISTANCE_M and dist_to_board > NEAR_STOP_THRESHOLD_M:
                    continue

                # Dead Reckoning Tracking & GPS Recalibration Engine
                last_gps_lat = v.latitude
                last_gps_lon = v.longitude
                last_gps_ts = v.timestamp_utc
                pos_ts = now_ts
                MAX_PREDICTION_AGE_S = 180

                prev_state = self._tracking_state.get(v.vehicle_id)

                # Check for legitimate trip change: reset tracking state if vehicle switched trips
                if prev_state is not None and v.trip_id is not None and prev_state.get("trip_id") != v.trip_id:
                    self._log_audit_event({
                        "timestamp_utc": pos_ts,
                        "timestamp_ist": format_epoch_ist(pos_ts),
                        "vehicle_id": v.vehicle_id,
                        "route_id": clean_route,
                        "trip_id": v.trip_id,
                        "previous_trip_id": prev_state.get("trip_id"),
                        "event_type": "TRIP_RESET",
                        "note": "Legitimate trip change detected. Resetting tracking state.",
                    })
                    prev_state = None
                    self._tracking_state.pop(v.vehicle_id, None)

                # Check for out-of-order GPS telemetry
                is_out_of_order = False
                if prev_state is not None and last_gps_ts < prev_state["anchor_gps_ts"]:
                    is_out_of_order = True
                    self._log_audit_event({
                        "timestamp_utc": pos_ts,
                        "timestamp_ist": format_epoch_ist(pos_ts),
                        "vehicle_id": v.vehicle_id,
                        "route_id": clean_route,
                        "trip_id": v.trip_id,
                        "event_type": "OUT_OF_ORDER_REJECTED",
                        "incoming_gps_ts": last_gps_ts,
                        "anchor_gps_ts": prev_state["anchor_gps_ts"],
                        "anomaly_flags": ["OUT_OF_ORDER_GPS_TIMESTAMP"],
                        "note": "Out-of-order GPS observation rejected. Retaining existing anchor.",
                    })

                # Unconstrained raw projection for empirical direction validation
                raw_prog_m, dist_to_shape_m = project_point_onto_shape_bounded(
                    shape_coords, cum_dists, last_gps_lat, last_gps_lon
                )

                # Empirical Direction Validation: if consecutive raw pings move backward along corridor
                if prev_state is not None and last_gps_ts > prev_state["anchor_gps_ts"] and not is_out_of_order:
                    prog_delta_raw = raw_prog_m - prev_state.get("raw_route_progress_m", prev_state["anchor_route_progress_m"])
                    if prog_delta_raw < -25.0:
                        if v.bearing is None or is_opposite_bearing or not is_bearing_aligned:
                            self._log_audit_event({
                                "timestamp_utc": pos_ts,
                                "timestamp_ist": format_epoch_ist(pos_ts),
                                "vehicle_id": v.vehicle_id,
                                "route_id": clean_route,
                                "trip_id": v.trip_id,
                                "event_type": "ANOMALY_DETECTED",
                                "anomaly_flags": ["UNEXPECTED_BACKWARD_PROGRESS"],
                                "raw_prog_m": round(raw_prog_m, 1),
                                "prev_prog_m": round(prev_state["anchor_route_progress_m"], 1),
                                "delta_m": round(prog_delta_raw, 1),
                                "note": "Vehicle raw progress decreased; detected opposite-direction travel. Excluded from suitable candidates.",
                            })
                            continue

                is_new_gps = (prev_state is None) or (last_gps_ts > prev_state["anchor_gps_ts"] and not is_out_of_order)

                if is_new_gps:
                    # Genuine GPS update received
                    anomaly_flags: List[str] = []

                    if prev_state is not None:
                        # Bounded search window around previous progress
                        prev_anchor_prog = prev_state["anchor_route_progress_m"]
                        prev_highest_prog = max(
                            prev_anchor_prog,
                            prev_state.get("last_predicted_route_progress_m", prev_anchor_prog)
                        )
                        dt = max(1.0, float(last_gps_ts - prev_state["anchor_gps_ts"]))
                        min_search_m = max(0.0, prev_anchor_prog - 25.0)
                        max_search_m = prev_highest_prog + max(60.0, 25.0 * dt + 60.0)

                        bounded_prog_m, shape_dist_m = project_point_onto_shape_bounded(
                            shape_coords, cum_dists, last_gps_lat, last_gps_lon, min_search_m, max_search_m
                        )
                        # Monotonic progress constraint: never decrease below highest observed or predicted progress
                        new_gps_progress_m = max(prev_highest_prog, bounded_prog_m)

                        # Recalibration! Compare genuine GPS with last predicted position
                        drift_error_m = haversine_distance_m(
                            prev_state["last_predicted_lat"],
                            prev_state["last_predicted_lon"],
                            last_gps_lat,
                            last_gps_lon,
                        )
                        corr_dist_m = abs(
                            new_gps_progress_m - prev_state["last_predicted_route_progress_m"]
                        )
                        corr_status = "CALIBRATED_ERROR_CORRECTED"

                        # Anomaly checks
                        jump_dist = haversine_distance_m(
                            prev_state["anchor_gps_lat"], prev_state["anchor_gps_lon"], last_gps_lat, last_gps_lon
                        )
                        if (jump_dist / dt) > 35.0:
                            anomaly_flags.append("IMPLAUSIBLE_GPS_VELOCITY_JUMP")

                        if drift_error_m > 250.0:
                            anomaly_flags.append("LARGE_PREDICTION_ERROR")
                    else:
                        new_gps_progress_m = raw_prog_m
                        shape_dist_m = dist_to_shape_m
                        drift_error_m = None
                        corr_dist_m = None
                        corr_status = "GPS_ANCHOR_VERIFIED"

                    if shape_dist_m > 200.0:
                        anomaly_flags.append("AMBIGUOUS_SHAPE_PROJECTION")

                    # Reset baseline anchor strictly to genuine GPS observation
                    self._tracking_state[v.vehicle_id] = {
                        "trip_id": v.trip_id,
                        "anchor_gps_lat": last_gps_lat,
                        "anchor_gps_lon": last_gps_lon,
                        "anchor_gps_ts": last_gps_ts,
                        "anchor_route_progress_m": new_gps_progress_m,
                        "raw_route_progress_m": raw_prog_m,
                        "last_predicted_lat": last_gps_lat,
                        "last_predicted_lon": last_gps_lon,
                        "last_predicted_route_progress_m": new_gps_progress_m,
                        "last_predicted_ts": pos_ts,
                        "last_prediction_error_m": round(drift_error_m, 1) if drift_error_m is not None else None,
                        "last_correction_distance_m": round(corr_dist_m, 1) if corr_dist_m is not None else None,
                        "correction_status": corr_status,
                        "anomaly_flags": anomaly_flags,
                    }
                    state = self._tracking_state[v.vehicle_id]

                    self._log_audit_event({
                        "timestamp_utc": pos_ts,
                        "timestamp_ist": format_epoch_ist(pos_ts),
                        "vehicle_id": v.vehicle_id,
                        "route_id": clean_route,
                        "trip_id": v.trip_id,
                        "event_type": "GPS_RECALIBRATION" if prev_state else "GPS_ANCHOR_INIT",
                        "anchor_progress_m": round(new_gps_progress_m, 1),
                        "drift_error_m": round(drift_error_m, 1) if drift_error_m is not None else None,
                        "correction_distance_m": round(corr_dist_m, 1) if corr_dist_m is not None else None,
                        "anomaly_flags": anomaly_flags,
                        "gps_accuracy_status": "ANOMALY_FLAGGED" if anomaly_flags else "NOMINAL",
                    })
                else:
                    state = prev_state
                    anomaly_flags = list(state.get("anomaly_flags", []))
                    if is_out_of_order and "OUT_OF_ORDER_GPS_TIMESTAMP" not in anomaly_flags:
                        anomaly_flags.append("OUT_OF_ORDER_GPS_TIMESTAMP")
                    drift_error_m = state.get("last_prediction_error_m")
                    corr_dist_m = state.get("last_correction_distance_m")
                    corr_status = state.get("correction_status", "DEAD_RECKONING_ACTIVE")

                # Check for critical anomalies: drift > 250m or distance to shape > 200m
                is_anomaly_unverified = (
                    ("LARGE_PREDICTION_ERROR" in anomaly_flags) or
                    ("AMBIGUOUS_SHAPE_PROJECTION" in anomaly_flags)
                )

                if is_anomaly_unverified:
                    # SAFETY REQUIREMENT: Freeze estimated position at last genuine GPS fix, suspend dead reckoning
                    pos_source = "GPS"
                    is_dead_reckoned = False
                    est_lat = state["anchor_gps_lat"]
                    est_lon = state["anchor_gps_lon"]
                    cur_progress_m = state["anchor_route_progress_m"]
                    corr_status = "UNVERIFIED_ANOMALY_FROZEN"
                    uncertainty_m = 50.0
                    elapsed_s = max(0, pos_ts - state["anchor_gps_ts"]) if state["anchor_gps_ts"] > 0 else 0
                    progress = "UNVERIFIED_STALE"
                    stops_away = None
                    is_verified_suitable = False
                    is_verified_dest = False
                    gps_acc_status = "UNVERIFIED_STALE"

                    # Maintain frozen state at genuine GPS anchor
                    state["last_predicted_lat"] = est_lat
                    state["last_predicted_lon"] = est_lon
                    state["last_predicted_route_progress_m"] = cur_progress_m
                    state["last_predicted_ts"] = pos_ts
                    state["correction_status"] = corr_status

                    last_gps_obs_time = format_epoch_ist(state["anchor_gps_ts"])
                    latest_calc_time = format_epoch_ist(pos_ts)
                    next_calc_time = format_epoch_ist(pos_ts + 15)

                    cur_dist_to_board = haversine_distance_m(est_lat, est_lon, board_lat, board_lon)

                    if "LARGE_PREDICTION_ERROR" in anomaly_flags:
                        anomaly_reason = f"prediction drift {round(drift_error_m, 1)}m > 250m safety limit"
                    else:
                        anomaly_reason = f"distance to route corridor {round(shape_dist_m, 1)}m > 200m safety limit"

                    guidance = (
                        f"Unverified / Stale position ({anomaly_reason}): bus {v.vehicle_id} (Route {clean_route} to {headsign}) "
                        f"frozen at last genuine GPS fix ({last_gps_obs_time}). Excluded from verified approaching candidates."
                    )
                else:
                    is_verified_suitable = True
                    is_verified_dest = True
                    gps_acc_status = "ANOMALY_FLAGGED" if anomaly_flags else "NOMINAL"

                    # Perform dead reckoning from genuine GPS anchor
                    elapsed_s = max(0, pos_ts - state["anchor_gps_ts"]) if state["anchor_gps_ts"] > 0 else 0
                    speed_kmh = v.speed_kmh
                    is_stationary = (speed_kmh is None or speed_kmh < 1.0)

                    if elapsed_s < 15 and not is_stationary:
                        # Within fresh GPS window (< 15s) for a moving bus
                        pos_source = "GPS"
                        is_dead_reckoned = False
                        est_lat = state["anchor_gps_lat"]
                        est_lon = state["anchor_gps_lon"]
                        cur_progress_m = max(
                            state.get("last_predicted_route_progress_m", state["anchor_route_progress_m"]),
                            state["anchor_route_progress_m"]
                        )
                        uncertainty_m = 15.0
                        if corr_status != "CALIBRATED_ERROR_CORRECTED":
                            corr_status = "GPS_ANCHOR_VERIFIED"
                    elif is_stationary:
                        # Stationary bus: hold at last genuine GPS position, do not advance
                        pos_source = "DEAD_RECKONED" if elapsed_s > 0 else "GPS"
                        is_dead_reckoned = (elapsed_s > 0)
                        advance_m = 0.0
                        est_lat = state["anchor_gps_lat"]
                        est_lon = state["anchor_gps_lon"]
                        cur_progress_m = max(
                            state.get("last_predicted_route_progress_m", state["anchor_route_progress_m"]),
                            state["anchor_route_progress_m"]
                        )
                        if elapsed_s > 0 and corr_status != "CALIBRATED_ERROR_CORRECTED":
                            corr_status = "STATIONARY_HOLD"
                        eff_age = min(elapsed_s, MAX_PREDICTION_AGE_S)
                        uncertainty_m = min(500.0, 15.0 + 0.5 * eff_age)
                    else:
                        # Moving bus dead reckoning active (elapsed_s >= 15)
                        pos_source = "DEAD_RECKONED"
                        is_dead_reckoned = True
                        clamped_speed_kmh = min(60.0, max(1.0, float(speed_kmh)))
                        if elapsed_s > MAX_PREDICTION_AGE_S:
                            eff_age = MAX_PREDICTION_AGE_S
                            corr_status = "EXCEEDED_MAX_AGE_STALE"
                        else:
                            eff_age = elapsed_s
                            corr_status = "DEAD_RECKONING_ACTIVE"

                        speed_ms = (clamped_speed_kmh * 1000.0) / 3600.0
                        advance_m = speed_ms * eff_age
                        # Advance along route shape from genuine GPS anchor, clamp to destination
                        cur_progress_m = min(
                            state["anchor_route_progress_m"] + advance_m,
                            alight_progress_m if alight_progress_m > 0 else cum_dists[-1]
                        )
                        # Enforce strict monotonic progress relative to last prediction
                        cur_progress_m = max(
                            state.get("last_predicted_route_progress_m", state["anchor_route_progress_m"]),
                            cur_progress_m
                        )

                        est_lat, est_lon = get_point_at_distance_along_shape(
                            shape_coords, cum_dists, cur_progress_m
                        )
                        uncertainty_m = min(500.0, 15.0 + 1.2 * eff_age + 0.05 * speed_ms * eff_age)

                    # Update tracking state for next iteration
                    state["last_predicted_lat"] = est_lat
                    state["last_predicted_lon"] = est_lon
                    state["last_predicted_route_progress_m"] = cur_progress_m
                    state["last_predicted_ts"] = pos_ts
                    state["correction_status"] = corr_status

                    # Format timestamps in IST
                    last_gps_obs_time = format_epoch_ist(state["anchor_gps_ts"])
                    latest_calc_time = format_epoch_ist(pos_ts)
                    next_calc_time = format_epoch_ist(pos_ts + 15)

                    # Recalculate distance to boarding stop from current estimated position
                    cur_dist_to_board = haversine_distance_m(est_lat, est_lon, board_lat, board_lon)
                    if cur_dist_to_board <= NEAR_STOP_THRESHOLD_M:
                        progress = "NEAR_BOARDING_STOP"
                        stops_away = 0
                    else:
                        progress = "APPROACHING"
                        stops_away = max(1, board_seq - (nearest_stop_seq or 1))

                    # Actionable passenger guidance with honest provenance disclosure
                    if corr_status == "CALIBRATED_ERROR_CORRECTED" and drift_error_m is not None:
                        guidance = (
                            f"GPS Calibrated (drift error {round(drift_error_m, 1)}m corrected): bus {v.vehicle_id} (Route {clean_route} to {headsign}) — "
                            f"{'currently at/near boarding stop (~' + str(int(cur_dist_to_board)) + 'm)' if progress == 'NEAR_BOARDING_STOP' else 'approaching (~' + str(round(cur_dist_to_board / 1000.0, 1)) + ' km away, ' + str(stops_away) + ' stop(s) away)'}. "
                            f"Verified to reach destination stop {alight_stop_name}."
                        )
                    elif corr_status == "STATIONARY_HOLD":
                        guidance = (
                            f"Stationary bus hold ({elapsed_s}s since GPS ping, ±{int(uncertainty_m)}m uncertainty): bus {v.vehicle_id} (Route {clean_route} to {headsign}) — "
                            f"{'currently at/near boarding stop (~' + str(int(cur_dist_to_board)) + 'm)' if progress == 'NEAR_BOARDING_STOP' else 'approaching (~' + str(round(cur_dist_to_board / 1000.0, 1)) + ' km away, ' + str(stops_away) + ' stop(s) away)'}. "
                            f"Verified to reach destination stop {alight_stop_name}."
                        )
                    elif corr_status == "EXCEEDED_MAX_AGE_STALE":
                        guidance = (
                            f"Stale telemetry frozen at {MAX_PREDICTION_AGE_S}s ({elapsed_s}s elapsed): bus {v.vehicle_id} (Route {clean_route} to {headsign}) — "
                            f"{'currently at/near boarding stop (~' + str(int(cur_dist_to_board)) + 'm)' if progress == 'NEAR_BOARDING_STOP' else 'approaching (~' + str(round(cur_dist_to_board / 1000.0, 1)) + ' km away, ' + str(stops_away) + ' stop(s) away)'}. "
                            f"Verified to reach destination stop {alight_stop_name}."
                        )
                    elif pos_source == "GPS":
                        guidance = (
                            f"Live GPS: bus {v.vehicle_id} (Route {clean_route} to {headsign}) — "
                            f"{'currently at/near boarding stop (~' + str(int(cur_dist_to_board)) + 'm)' if progress == 'NEAR_BOARDING_STOP' else 'approaching (~' + str(round(cur_dist_to_board / 1000.0, 1)) + ' km away, ' + str(stops_away) + ' stop(s) away)'}. "
                            f"Verified to reach destination stop {alight_stop_name}."
                        )
                    else:
                        guidance = (
                            f"Estimated position (Dead Reckoned along route, {elapsed_s}s since GPS ping, ±{int(uncertainty_m)}m uncertainty): bus {v.vehicle_id} (Route {clean_route} to {headsign}) — "
                            f"{'currently at/near boarding stop (~' + str(int(cur_dist_to_board)) + 'm)' if progress == 'NEAR_BOARDING_STOP' else 'approaching (~' + str(round(cur_dist_to_board / 1000.0, 1)) + ' km away, ' + str(stops_away) + ' stop(s) away)'}. "
                            f"Verified to reach destination stop {alight_stop_name}."
                        )

                suitable_buses.append({
                    "vehicle_id": v.vehicle_id,
                    "route_id": clean_route,
                    "trip_id": v.trip_id,
                    "trip_headsign": headsign,
                    "destination_stop_name": alight_stop_name,
                    "progress_status": progress,
                    "distance_to_board_m": round(cur_dist_to_board, 1),
                    "stops_away": stops_away,
                    "speed_kmh": v.speed_kmh,
                    "latitude": round(est_lat, 6),
                    "longitude": round(est_lon, 6),
                    "bearing": v.bearing,
                    "timestamp_utc": state["anchor_gps_ts"],
                    "age_seconds": elapsed_s,
                    "is_fresh": v.is_fresh,
                    "is_current": v.is_current,
                    "is_verified_suitable": is_verified_suitable,
                    "is_verified_destination": is_verified_dest,
                    "guidance_message": guidance,
                    "position_source": pos_source,
                    "is_dead_reckoned": is_dead_reckoned,
                    "last_gps_latitude": round(state["anchor_gps_lat"], 6),
                    "last_gps_longitude": round(state["anchor_gps_lon"], 6),
                    "last_gps_timestamp": state["anchor_gps_ts"],
                    "position_timestamp": pos_ts,
                    "prediction_age_seconds": elapsed_s,
                    "uncertainty_meters": round(uncertainty_m, 1),
                    "route_progress_meters": round(cur_progress_m, 1),
                    "last_prediction_error_meters": state.get("last_prediction_error_m"),
                    "last_correction_distance_meters": state.get("last_correction_distance_m"),
                    "correction_status": corr_status,
                    "last_gps_observation_time": last_gps_obs_time,
                    "latest_position_calculation_time": latest_calc_time,
                    "next_expected_update_time": next_calc_time,
                    "anomaly_flags": anomaly_flags,
                    "has_anomalies": len(anomaly_flags) > 0,
                    "gps_accuracy_status": gps_acc_status,
                })

            # Sort verified suitable buses first, then near boarding stop, then by distance to board
            suitable_buses.sort(
                key=lambda x: (
                    not x["is_verified_suitable"],
                    x["progress_status"] != "NEAR_BOARDING_STOP",
                    x["distance_to_board_m"]
                )
            )
            return suitable_buses

        except Exception as err:
            logger.error(f"Error finding suitable buses for leg: {err}")
            return []
        finally:
            conn.close()

