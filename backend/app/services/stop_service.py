"""Transit Stop Application Service."""

import os
import sqlite3
from typing import List, Optional
from backend.core.raptor_data import Timetable
from backend.app.schemas.stops import NearbyStopSchema, StopCrosswalkResponse, StopSchema


class StopService:
    """Service providing search and proximity queries over GTFS stops."""

    def __init__(self, timetable: Timetable):
        self.timetable = timetable

    def search_stops(self, query: str, limit: int = 10) -> List[StopSchema]:
        """Search stops by case-insensitive name substring matching."""
        q = query.strip().lower()
        if not q:
            return []

        matched = []
        for stop in self.timetable.stops.values():
            if q in stop.stop_name.lower():
                matched.append(
                    StopSchema(
                        stop_id=stop.stop_id,
                        stop_name=stop.stop_name,
                        lat=stop.lat,
                        lon=stop.lon,
                    )
                )
                if len(matched) >= limit:
                    break

        # Sort matches: prefix matches first, then alphabetical
        matched.sort(
            key=lambda s: (0 if s.stop_name.lower().startswith(q) else 1, s.stop_name)
        )
        return matched[:limit]

    def find_nearby_stops(
        self, lat: float, lon: float, radius_m: float = 800.0, limit: int = 10
    ) -> List[NearbyStopSchema]:
        """Find stops within spatial walking radius using KDTree."""
        nearby = self.timetable.find_nearby_stops(
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            expand_radius_m=radius_m,
        )

        results = []
        for stop, dist_m, walk_s in nearby[:limit]:
            results.append(
                NearbyStopSchema(
                    stop_id=stop.stop_id,
                    stop_name=stop.stop_name,
                    lat=stop.lat,
                    lon=stop.lon,
                    distance_m=round(dist_m, 1),
                    walking_time_s=round(walk_s, 1),
                )
            )
        return results

    def get_crosswalk(self, legacy_stop_id: str) -> Optional[StopCrosswalkResponse]:
        """Lookup legacy stop mapping in crosswalk catalog if available."""
        lid = str(legacy_stop_id).strip()
        
        # Check timetable db path first, then fallback to staged DLM1 db
        db_candidates = [self.timetable.db_path, "/tmp/delhi_dlm1.db"]
        
        for db_p in db_candidates:
            if not db_p or not os.path.exists(db_p):
                continue
            conn = sqlite3.connect(db_p)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='legacy_stop_crosswalk';")
            if not cur.fetchone():
                conn.close()
                continue
            cur.execute(
                """
                SELECT legacy_stop_id, legacy_stop_name, dlm1_stop_id, dlm1_stop_name,
                       distance_m, name_similarity, match_classification, notes
                FROM legacy_stop_crosswalk
                WHERE legacy_stop_id = ?;
                """,
                (lid,),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                return StopCrosswalkResponse(
                    legacy_stop_id=str(row[0]),
                    legacy_stop_name=str(row[1]),
                    dlm1_stop_id=str(row[2]) if row[2] else None,
                    dlm1_stop_name=str(row[3]) if row[3] else None,
                    distance_m=round(float(row[4]), 2) if row[4] is not None else None,
                    name_similarity=round(float(row[5]), 4) if row[5] is not None else None,
                    match_classification=str(row[6]),
                    notes=str(row[7]) if row[7] else None,
                )
        return None

