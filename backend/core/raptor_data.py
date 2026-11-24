"""RAPTOR Timetable & Data Structures Module.

Implements the data representation for Round-Based Public Transit Routing (RAPTOR)
as specified in PRD v3.0 Section 8:
- Route patterns grouping trips with identical ordered stop sequences.
- Stop-to-pattern spatial and topological indexing.
- Spatial KD-Tree indexing in EPSG:32643 UTM Zone 43N coordinates.
- Precomputed transfer footpaths (max 400m, effective walking speed 4.5 km/h with 1.3 detour).
- Active service calendar logic and post-midnight GTFS timestamp handling.
"""

import math
import os
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.spatial import KDTree
import pyproj
import yaml


class TimetableStatus(str, Enum):
    """Timetable validity and freshness state per PRD v3.0 & Milestone 5.1.1."""
    CURRENT_VERIFIED = "CURRENT_VERIFIED"
    EXPIRED = "EXPIRED"
    ASSUMED_RECURRING = "ASSUMED_RECURRING"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class Stop:
    stop_id: str
    stop_name: str
    lat: float
    lon: float
    utm_x: float
    utm_y: float


@dataclass
class Footpath:
    from_stop_id: str
    to_stop_id: str
    distance_m: float
    walking_time_s: float


@dataclass
class Trip:
    trip_id: str
    route_id: str
    service_id: str
    pattern_id: int
    stop_ids: Tuple[str, ...]
    arrival_sec: np.ndarray
    departure_sec: np.ndarray


@dataclass
class RoutePattern:
    pattern_id: int
    route_id: str
    stop_ids: Tuple[str, ...]
    trips: List[Trip]
    deps_matrix: np.ndarray = field(repr=False)
    arrs_matrix: np.ndarray = field(repr=False)


class Timetable:
    """In-memory timetable representation optimized for RAPTOR queries."""

    def __init__(
        self,
        stops: Dict[str, Stop],
        patterns: Dict[int, RoutePattern],
        stop_to_patterns: Dict[str, List[Tuple[int, int]]],
        footpaths: Dict[str, List[Footpath]],
        active_service_ids: Set[str],
        db_path: str,
        config: Dict[str, Any],
        service_activation_assumed: bool = False,
        feed_start_date: Optional[str] = "2022-01-01",
        feed_end_date: Optional[str] = "2024-01-01",
        feed_provenance: str = "Mobility Database / Delhi Transport Corporation (DTC) Static GTFS archive",
    ):
        self.stops = stops
        self.patterns = patterns
        self.stop_to_patterns = stop_to_patterns
        self.footpaths = footpaths
        self.active_service_ids = active_service_ids
        self.db_path = db_path
        self.config = config
        self.service_activation_assumed = service_activation_assumed
        self.feed_start_date = feed_start_date
        self.feed_end_date = feed_end_date
        self.feed_provenance = feed_provenance

        # Build spatial KD-Tree over stop UTM coordinates
        self.stop_id_list = list(stops.keys())
        self.coords_array = np.array(
            [[stops[sid].utm_x, stops[sid].utm_y] for sid in self.stop_id_list],
            dtype=np.float64,
        )
        if len(self.coords_array) > 0:
            self.kdtree = KDTree(self.coords_array)
        else:
            self.kdtree = None

        # Transformer for coordinate queries (WGS84 -> UTM Zone 43N)
        self.proj_transformer = pyproj.Transformer.from_crs(
            "EPSG:4326", "EPSG:32643", always_xy=True
        )

    @classmethod
    def load_from_sqlite(
        cls,
        db_path: Optional[str] = None,
        config_path: Optional[str] = None,
        target_route_id: Optional[str] = None,
    ) -> "Timetable":
        """Load GTFS timetable from SQLite database into memory."""
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(root_dir, "config", "planner.yaml")
        
        config: Dict[str, Any] = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}

        # Resolve DB path
        if db_path is None:
            # Check full Mobility Database first, then serving DB
            mdb_db = "/tmp/delhi_mdb.db"
            serving_db = os.path.join(root_dir, "data", "serving", "delhi_bus.db")
            if os.path.exists(mdb_db):
                db_path = mdb_db
            elif os.path.exists(serving_db):
                db_path = serving_db
            else:
                raise FileNotFoundError(f"Neither {mdb_db} nor {serving_db} exists")

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # 1. Load active services from calendar
        cur.execute("SELECT service_id, start_date, end_date FROM calendar;")
        calendar_rows = cur.fetchall()
        active_service_ids = {str(r[0]) for r in calendar_rows}
        
        feed_start_date = None
        feed_end_date = None
        if calendar_rows:
            s_raw = str(calendar_rows[0][1]).strip()
            e_raw = str(calendar_rows[0][2]).strip()
            feed_start_date = f"{s_raw[:4]}-{s_raw[4:6]}-{s_raw[6:]}" if len(s_raw) == 8 and s_raw.isdigit() else s_raw
            feed_end_date = f"{e_raw[:4]}-{e_raw[4:6]}-{e_raw[6:]}" if len(e_raw) == 8 and e_raw.isdigit() else e_raw

        # If calendar expired (e.g. 2024 calendar for 2026 queries), assume active with flag
        service_activation_assumed = True

        # 2. Load Stops
        cur.execute("SELECT stop_id, stop_name, stop_lat, stop_lon, utm_x, utm_y FROM stops;")
        stops: Dict[str, Stop] = {}
        transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
        for sid, name, lat, lon, utm_x, utm_y in cur.fetchall():
            sid_str = str(sid)
            if utm_x is None or utm_y is None or utm_x == 0 or utm_y == 0:
                ux, uy = transformer.transform(float(lon), float(lat))
            else:
                ux, uy = float(utm_x), float(utm_y)
            stops[sid_str] = Stop(
                stop_id=sid_str,
                stop_name=str(name),
                lat=float(lat),
                lon=float(lon),
                utm_x=ux,
                utm_y=uy,
            )

        # 3. Load Trips and Stop Times
        route_filter = "WHERE t.route_id = ?" if target_route_id else ""
        params = (target_route_id,) if target_route_id else ()

        cur.execute(
            f"""
            SELECT st.trip_id, t.route_id, t.service_id, st.stop_id, st.arrival_sec, st.departure_sec
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.trip_id
            {route_filter}
            ORDER BY st.trip_id, st.stop_sequence;
            """,
            params,
        )

        trip_stops: Dict[str, List[str]] = {}
        trip_arrs: Dict[str, List[int]] = {}
        trip_deps: Dict[str, List[int]] = {}
        trip_meta: Dict[str, Tuple[str, str]] = {}

        for tid, rid, s_id, stop_id, arr, dep in cur.fetchall():
            tid_str = str(tid)
            sid_str = str(stop_id)
            if tid_str not in trip_stops:
                trip_stops[tid_str] = []
                trip_arrs[tid_str] = []
                trip_deps[tid_str] = []
                trip_meta[tid_str] = (str(rid), str(s_id))
            trip_stops[tid_str].append(sid_str)
            trip_arrs[tid_str].append(int(arr))
            trip_deps[tid_str].append(int(dep))

        # 4. Group trips into distinct Route Patterns
        pattern_dict: Dict[Tuple[str, ...], List[str]] = {}
        for tid, s_list in trip_stops.items():
            pat_key = tuple(s_list)
            if pat_key not in pattern_dict:
                pattern_dict[pat_key] = []
            pattern_dict[pat_key].append(tid)

        patterns: Dict[int, RoutePattern] = {}
        stop_to_patterns: Dict[str, List[Tuple[int, int]]] = {sid: [] for sid in stops}
        
        for pat_id, (pat_stop_ids, tids) in enumerate(pattern_dict.items()):
            # Sort trips in pattern by departure at the first stop
            tids_sorted = sorted(tids, key=lambda t: trip_deps[t][0])
            
            trips_in_pattern: List[Trip] = []
            deps_matrix_list: List[List[int]] = []
            arrs_matrix_list: List[List[int]] = []

            for tid in tids_sorted:
                rid, s_id = trip_meta[tid]
                arr_arr = np.array(trip_arrs[tid], dtype=np.int32)
                dep_arr = np.array(trip_deps[tid], dtype=np.int32)
                trip_obj = Trip(
                    trip_id=tid,
                    route_id=rid,
                    service_id=s_id,
                    pattern_id=pat_id,
                    stop_ids=pat_stop_ids,
                    arrival_sec=arr_arr,
                    departure_sec=dep_arr,
                )
                trips_in_pattern.append(trip_obj)
                deps_matrix_list.append(trip_deps[tid])
                arrs_matrix_list.append(trip_arrs[tid])

            pattern_obj = RoutePattern(
                pattern_id=pat_id,
                route_id=trip_meta[tids_sorted[0]][0],
                stop_ids=pat_stop_ids,
                trips=trips_in_pattern,
                deps_matrix=np.array(deps_matrix_list, dtype=np.int32),
                arrs_matrix=np.array(arrs_matrix_list, dtype=np.int32),
            )
            patterns[pat_id] = pattern_obj

            for stop_idx, sid in enumerate(pat_stop_ids):
                if sid in stop_to_patterns:
                    stop_to_patterns[sid].append((pat_id, stop_idx))

        # 5. Precompute Transfer Footpaths using spatial KD-Tree
        walking_cfg = config.get("walking", {})
        walk_speed_kmh = float(walking_cfg.get("walking_speed_kmh", 4.5))
        detour_factor = float(walking_cfg.get("detour_factor", 1.3))
        max_transfer_dist = float(walking_cfg.get("max_transfer_walk_distance_m", 400.0))

        # Effective walking speed in m/s = (speed_kmh / 3.6) / detour_factor
        effective_walk_speed_mps = (walk_speed_kmh / 3.6) / detour_factor

        footpaths: Dict[str, List[Footpath]] = {sid: [] for sid in stops}
        stop_ids_list = list(stops.keys())
        coords_arr = np.array(
            [[stops[sid].utm_x, stops[sid].utm_y] for sid in stop_ids_list],
            dtype=np.float64,
        )

        if len(coords_arr) > 0:
            tree = KDTree(coords_arr)
            # Self-footpaths (distance = 0, time = 0)
            for sid in stop_ids_list:
                footpaths[sid].append(
                    Footpath(from_stop_id=sid, to_stop_id=sid, distance_m=0.0, walking_time_s=0.0)
                )

            # Query pairs within max transfer distance
            pairs = tree.query_pairs(r=max_transfer_dist)
            for i, j in pairs:
                sid_i = stop_ids_list[i]
                sid_j = stop_ids_list[j]
                dist = float(
                    math.hypot(
                        coords_arr[i, 0] - coords_arr[j, 0],
                        coords_arr[i, 1] - coords_arr[j, 1],
                    )
                )
                walk_time = dist / effective_walk_speed_mps
                footpaths[sid_i].append(
                    Footpath(
                        from_stop_id=sid_i,
                        to_stop_id=sid_j,
                        distance_m=dist,
                        walking_time_s=walk_time,
                    )
                )
                footpaths[sid_j].append(
                    Footpath(
                        from_stop_id=sid_j,
                        to_stop_id=sid_i,
                        distance_m=dist,
                        walking_time_s=walk_time,
                    )
                )

        conn.close()

        return cls(
            stops=stops,
            patterns=patterns,
            stop_to_patterns=stop_to_patterns,
            footpaths=footpaths,
            active_service_ids=active_service_ids,
            db_path=db_path,
            config=config,
            service_activation_assumed=service_activation_assumed,
            feed_start_date=feed_start_date,
            feed_end_date=feed_end_date,
        )

    def check_freshness(
        self,
        service_date: str,
        allow_assumed_recurring: bool = True,
    ) -> Tuple[TimetableStatus, Optional[str]]:
        """Check timetable freshness for a requested service date.

        Supports states:
        - CURRENT_VERIFIED: Feed validity covers the requested service date and its provenance is documented.
        - EXPIRED: Requested service date is outside the supplied feed's validity period (when assumed recurring is not allowed).
        - ASSUMED_RECURRING: Historical weekly service patterns are being reused as an explicit demonstration assumption.
        - UNAVAILABLE: No usable timetable is available.
        """
        if not self.stops or not self.patterns or self.kdtree is None:
            return (
                TimetableStatus.UNAVAILABLE,
                "UNAVAILABLE: No usable timetable is available or transit network is empty.",
            )

        clean_date = str(service_date).replace("/", "-").strip()
        if len(clean_date) == 8 and clean_date.isdigit():
            clean_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:]}"

        if self.feed_start_date and self.feed_end_date:
            if self.feed_start_date <= clean_date <= self.feed_end_date:
                return (TimetableStatus.CURRENT_VERIFIED, None)
            else:
                if allow_assumed_recurring:
                    warning = (
                        f"STALE TIMETABLE WARNING: The underlying GTFS schedule expired on {self.feed_end_date}. "
                        f"Requested service date ({service_date}) is outside feed validity [{self.feed_start_date} to {self.feed_end_date}]. "
                        f"Historical weekly service patterns are being reused under demonstration assumption (ASSUMED_RECURRING). "
                        f"Departures and trip times are NOT verified as currently operating in Delhi in 2026."
                    )
                    return (TimetableStatus.ASSUMED_RECURRING, warning)
                else:
                    warning = (
                        f"EXPIRED TIMETABLE ERROR: The underlying GTFS schedule expired on {self.feed_end_date}. "
                        f"Requested service date ({service_date}) is outside feed validity period "
                        f"[{self.feed_start_date} to {self.feed_end_date}]. "
                        f"Current operating schedule is unverified."
                    )
                    return (TimetableStatus.EXPIRED, warning)

        return (
            TimetableStatus.UNAVAILABLE,
            "UNAVAILABLE: Calendar date boundaries are missing from timetable.",
        )

    def find_nearby_stops(
        self,
        lat: float,
        lon: float,
        radius_m: Optional[float] = None,
        expand_radius_m: Optional[float] = None,
    ) -> List[Tuple[Stop, float, float]]:
        """Find stops within walking radius of given lat/lon.

        Returns:
            List of (Stop, distance_m, walking_time_s) sorted by distance.
        """
        if self.kdtree is None or len(self.stop_id_list) == 0:
            return []

        walking_cfg = self.config.get("walking", {})
        walk_speed_kmh = float(walking_cfg.get("walking_speed_kmh", 4.5))
        detour_factor = float(walking_cfg.get("detour_factor", 1.3))
        effective_speed = (walk_speed_kmh / 3.6) / detour_factor

        r_default = radius_m or float(walking_cfg.get("default_access_egress_radius_m", 800.0))
        r_expand = expand_radius_m or float(
            walking_cfg.get("expanded_access_egress_radius_m", 1500.0)
        )

        ux, uy = self.proj_transformer.transform(lon, lat)
        indices = self.kdtree.query_ball_point([ux, uy], r=r_default)
        
        # If no stops found within default radius, expand radius
        if len(indices) == 0 and r_expand > r_default:
            indices = self.kdtree.query_ball_point([ux, uy], r=r_expand)

        results = []
        for idx in indices:
            sid = self.stop_id_list[idx]
            stop = self.stops[sid]
            dist = float(math.hypot(stop.utm_x - ux, stop.utm_y - uy))
            walk_time = dist / effective_speed
            results.append((stop, dist, walk_time))

        results.sort(key=lambda x: x[1])
        return results

    def get_transfer_footpaths(self, stop_id: str) -> List[Footpath]:
        """Return precomputed transfer footpaths starting from stop_id."""
        return self.footpaths.get(str(stop_id), [])

