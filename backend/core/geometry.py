"""Route Geometry and Topological Reconstruction Module.

Builds linear referencing route patterns from GTFS stops and stop_times
in projected metric coordinates (EPSG:32643 UTM Zone 43N).
"""

import math
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from shapely.geometry import LineString, Point


def calculate_bearing(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate geographic/grid bearing in degrees (0 = North, 90 = East)."""
    dx = x2 - x1
    dy = y2 - y1
    angle_rad = math.atan2(dx, dy)
    deg = math.degrees(angle_rad)
    return (deg + 360.0) % 360.0


@dataclass
class StopOccurrence:
    stop_sequence: int
    stop_id: str
    stop_name: str
    utm_x: float
    utm_y: float
    lat: float
    lon: float
    along_dist_m: float
    segment_bearing_deg: Optional[float] = None


@dataclass
class RoutePattern:
    pattern_id: str
    route_id: str
    direction_id: int
    stops: List[StopOccurrence]
    total_length_m: float
    geometry_type: str = "STOP_TOPOLOGY"
    limitations: str = (
        "Reconstructed from sequential GTFS stop coordinates in EPSG:32643. "
        "Represents topological linear reference baseline; straight segments "
        "between stops underestimate true road curvature by an estimated 5-15% "
        "detour factor."
    )
    _line_string: Optional[LineString] = field(default=None, repr=False)

    def __post_init__(self):
        coords = [(s.utm_x, s.utm_y) for s in self.stops]
        if len(coords) >= 2:
            self._line_string = LineString(coords)
        elif len(coords) == 1:
            self._line_string = Point(coords[0])
        else:
            self._line_string = None

    def project_point(self, utm_x: float, utm_y: float) -> Tuple[float, float, int]:
        """Project a metric coordinate (utm_x, utm_y) onto the route polyline.

        Returns:
            Tuple of:
            - along_dist_m: Cumulative distance along route to the projection point (meters)
            - perp_dist_m: Perpendicular distance from (utm_x, utm_y) to the polyline (meters)
            - closest_segment_idx: Index k of the segment [Stop_k, Stop_k+1]
        """
        if self._line_string is None or len(self.stops) < 2:
            return 0.0, 999999.0, 0

        pt = Point(utm_x, utm_y)
        perp_dist = self._line_string.distance(pt)
        along_dist = self._line_string.project(pt)

        # Find closest segment index
        closest_seg = 0
        min_seg_dist = float("inf")
        for i in range(len(self.stops) - 1):
            s1 = self.stops[i]
            s2 = self.stops[i + 1]
            seg_line = LineString([(s1.utm_x, s1.utm_y), (s2.utm_x, s2.utm_y)])
            d = seg_line.distance(pt)
            if d < min_seg_dist:
                min_seg_dist = d
                closest_seg = i

        return along_dist, perp_dist, closest_seg

    def get_stop_by_sequence(self, seq: int) -> Optional[StopOccurrence]:
        for s in self.stops:
            if s.stop_sequence == seq:
                return s
        return None


def load_route_patterns(
    gtfs_db_path: str, route_id: Optional[str] = None
) -> Dict[str, List[RoutePattern]]:
    """Extract distinct route patterns from GTFS serving/MDB database.

    Groups trips by route and distinct stop sequence, computing along-shape
    metric distances in EPSG:32643.
    """
    conn = sqlite3.connect(gtfs_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    route_filter = "WHERE t.route_id = ?" if route_id else ""
    params = (route_id,) if route_id else ()

    # Discover patterns by grouping trips that share the identical stop sequence
    query = f"""
        SELECT 
            t.route_id,
            t.trip_id,
            GROUP_CONCAT(st.stop_id, '->') as stop_seq_key
        FROM trips t
        JOIN stop_times st ON t.trip_id = st.trip_id
        {route_filter}
        GROUP BY t.route_id, t.trip_id
    """
    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Map (route_id, stop_seq_key) -> representative trip_id
    pattern_trips: Dict[Tuple[str, str], str] = {}
    for r in rows:
        key = (str(r["route_id"]), str(r["stop_seq_key"]))
        if key not in pattern_trips:
            pattern_trips[key] = str(r["trip_id"])

    route_patterns: Dict[str, List[RoutePattern]] = {}

    # Build RoutePattern objects for each unique pattern
    for (r_id, seq_key), rep_trip_id in pattern_trips.items():
        stop_query = """
            SELECT 
                st.stop_sequence,
                st.stop_id,
                s.stop_name,
                s.stop_lat,
                s.stop_lon,
                s.utm_x,
                s.utm_y
            FROM stop_times st
            JOIN stops s ON st.stop_id = s.stop_id
            WHERE st.trip_id = ?
            ORDER BY st.stop_sequence ASC
        """
        cursor.execute(stop_query, (rep_trip_id,))
        stop_rows = cursor.fetchall()

        if len(stop_rows) < 2:
            continue

        stops: List[StopOccurrence] = []
        cum_dist = 0.0

        for i, s_row in enumerate(stop_rows):
            utm_x = float(s_row["utm_x"])
            utm_y = float(s_row["utm_y"])

            if i > 0:
                prev_x = stops[i - 1].utm_x
                prev_y = stops[i - 1].utm_y
                step_dist = math.hypot(utm_x - prev_x, utm_y - prev_y)
                cum_dist += step_dist
                bearing = calculate_bearing(prev_x, prev_y, utm_x, utm_y)
                stops[i - 1].segment_bearing_deg = bearing

            stop_occ = StopOccurrence(
                stop_sequence=int(s_row["stop_sequence"]),
                stop_id=str(s_row["stop_id"]),
                stop_name=str(s_row["stop_name"]),
                utm_x=utm_x,
                utm_y=utm_y,
                lat=float(s_row["stop_lat"]),
                lon=float(s_row["stop_lon"]),
                along_dist_m=cum_dist,
            )
            stops.append(stop_occ)

        # Set final bearing to match previous segment
        if len(stops) >= 2:
            stops[-1].segment_bearing_deg = stops[-2].segment_bearing_deg

        pattern_idx = len(route_patterns.get(r_id, []))
        # Direction 0 or 1 based on index or pattern count
        direction_id = 0 if pattern_idx % 2 == 0 else 1
        pat_id = f"{r_id}_dir{direction_id}_pat{pattern_idx}"

        rp = RoutePattern(
            pattern_id=pat_id,
            route_id=r_id,
            direction_id=direction_id,
            stops=stops,
            total_length_m=cum_dist,
        )

        if r_id not in route_patterns:
            route_patterns[r_id] = []
        route_patterns[r_id].append(rp)

    conn.close()
    return route_patterns

