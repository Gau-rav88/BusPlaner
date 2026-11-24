"""Transit Route Application Service."""

import sqlite3
from typing import List, Optional
from backend.core.raptor_data import Timetable
from backend.app.schemas.routes import OrderedStopSchema, RouteDetailResponse


class RouteService:
    """Service providing metadata and stop sequence queries for transit routes."""

    def __init__(self, timetable: Timetable):
        self.timetable = timetable

    def get_route_detail(self, route_id: str) -> Optional[RouteDetailResponse]:
        """Fetch route metadata and primary stop sequence from GTFS database."""
        rid_str = str(route_id).strip()
        conn = sqlite3.connect(self.timetable.db_path)
        cur = conn.cursor()

        # Query route metadata
        cur.execute(
            """
            SELECT route_id, agency_id, route_short_name, route_long_name 
            FROM routes 
            WHERE route_id = ?;
            """,
            (rid_str,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return None

        r_id, agency_id, short_name, long_name = row

        # Count trips for this route
        cur.execute("SELECT count(*) FROM trips WHERE route_id = ?;", (rid_str,))
        trips_count = int(cur.fetchone()[0])

        # Check for shapes geometry if shapes table exists
        has_shape_geometry = False
        shape_coordinates = None
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shapes';")
        if cur.fetchone():
            cur.execute(
                """
                SELECT shape_id 
                FROM trips 
                WHERE route_id = ? AND shape_id IS NOT NULL AND shape_id != ''
                GROUP BY shape_id
                ORDER BY count(*) DESC
                LIMIT 1;
                """,
                (rid_str,),
            )
            shp_row = cur.fetchone()
            if shp_row and shp_row[0]:
                cur.execute(
                    """
                    SELECT shape_pt_lat, shape_pt_lon
                    FROM shapes
                    WHERE shape_id = ?
                    ORDER BY shape_pt_sequence;
                    """,
                    (shp_row[0],),
                )
                pts = cur.fetchall()
                if pts:
                    has_shape_geometry = True
                    shape_coordinates = [[float(p[0]), float(p[1])] for p in pts]

        conn.close()

        # Count patterns from in-memory timetable
        matching_patterns = [
            pat for pat in self.timetable.patterns.values() if str(pat.route_id) == rid_str
        ]
        patterns_count = len(matching_patterns)

        # Primary ordered stop list from the first matching pattern
        ordered_stops: List[OrderedStopSchema] = []
        if matching_patterns:
            primary_pat = matching_patterns[0]
            for seq_idx, sid in enumerate(primary_pat.stop_ids):
                if sid in self.timetable.stops:
                    stop = self.timetable.stops[sid]
                    ordered_stops.append(
                        OrderedStopSchema(
                            sequence=seq_idx,
                            stop_id=stop.stop_id,
                            stop_name=stop.stop_name,
                            lat=stop.lat,
                            lon=stop.lon,
                        )
                    )

        return RouteDetailResponse(
            route_id=str(r_id),
            agency_id=str(agency_id) if agency_id else None,
            route_short_name=str(short_name) if short_name else None,
            route_long_name=str(long_name) if long_name else None,
            patterns_count=patterns_count,
            trips_count=trips_count,
            ordered_stops=ordered_stops,
            has_shape_geometry=has_shape_geometry,
            shape_coordinates=shape_coordinates,
        )

