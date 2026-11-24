#!/usr/bin/env python3
"""
Controlled DLM1 Static GTFS Migration Script (Phase 1, 2, 3)
Builds staged database /tmp/delhi_dlm1.db, validates all records,
builds legacy-to-DLM1 stop crosswalk, and checks historical GPS compatibility.
"""

import os
import sys
import zipfile
import sqlite3
import pandas as pd
import numpy as np
from pyproj import Transformer
from difflib import SequenceMatcher
import json

DLM1_ZIP = "/Users/gauravchauhan/Downloads/delhi_buses_static_gtfs_v1.zip"
STAGED_DB = "/tmp/delhi_dlm1.db"
OLD_DB = "/tmp/delhi_mdb.db"
OUTPUT_CROSSWALK_CSV = "data/processed/legacy_stop_crosswalk.csv"
OUTPUT_CROSSWALK_PARQUET = "data/processed/legacy_stop_crosswalk.parquet"

transformer = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


def parse_time_to_seconds(time_str: str) -> int:
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(float(parts[2]))
            return h * 3600 + m * 60 + s
    except Exception:
        pass
    return -1


def normalize_stop_name(name: str) -> str:
    if not name:
        return ""
    import re
    s = name.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    # common abbreviations in Delhi transit
    replacements = {
        "stn": "station",
        "mtr": "metro",
        "sec": "sector",
        "vill": "village",
        "opp": "opposite",
        "nr": "near",
        "rd": "road",
        "col": "colony",
        "hosp": "hospital",
        "term": "terminal",
        "t": "terminal",
        "chowk": "crossing",
        "ps": "police station"
    }
    tokens = [replacements.get(t, t) for t in s.split()]
    return " ".join(tokens)


def string_similarity(s1: str, s2: str) -> float:
    n1 = normalize_stop_name(s1)
    n2 = normalize_stop_name(s2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    # Jaccard on tokens
    set1, set2 = set(n1.split()), set(n2.split())
    if set1 and set2:
        jaccard = len(set1 & set2) / len(set1 | set2)
    else:
        jaccard = 0.0
    seq = SequenceMatcher(None, n1, n2).ratio()
    return max(jaccard, seq)


def haversine(lat1, lon1, lat2, lon2):
    import math
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def run_phase1_ingest(z: zipfile.ZipFile, conn: sqlite3.Connection) -> dict:
    print("=== PHASE 1: INGESTING DLM1 INTO STAGED DATABASE ===")
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    counts = {}

    # 1. Agency
    print("1. Ingesting agency.txt...")
    df_agency = pd.read_csv(z.open("agency.txt"), dtype=str)
    df_agency.to_sql("agency", conn, if_exists="replace", index=False)
    counts["agency"] = len(df_agency)

    # 2. Calendar
    print("2. Ingesting calendar.txt...")
    df_cal = pd.read_csv(z.open("calendar.txt"), dtype=str)
    df_cal.to_sql("calendar", conn, if_exists="replace", index=False)
    counts["calendar"] = len(df_cal)

    # 3. Feed Info
    print("3. Ingesting feed_info.txt...")
    df_feed = pd.read_csv(z.open("feed_info.txt"), dtype=str)
    df_feed.to_sql("feed_info", conn, if_exists="replace", index=False)
    counts["feed_info"] = len(df_feed)

    # 4. Routes
    print("4. Ingesting routes.txt...")
    df_routes = pd.read_csv(z.open("routes.txt"), dtype=str)
    df_routes["route_id"] = df_routes["route_id"].str.strip()
    df_routes.to_sql("routes", conn, if_exists="replace", index=False)
    cur.execute("CREATE INDEX idx_routes_id ON routes(route_id);")
    counts["routes"] = len(df_routes)

    # 5. Stops
    print("5. Ingesting stops.txt...")
    df_stops = pd.read_csv(z.open("stops.txt"))
    df_stops["stop_id"] = df_stops["stop_id"].astype(str).str.strip()
    df_stops["stop_lat"] = pd.to_numeric(df_stops["stop_lat"], errors="coerce")
    df_stops["stop_lon"] = pd.to_numeric(df_stops["stop_lon"], errors="coerce")
    lons, lats = df_stops["stop_lon"].values, df_stops["stop_lat"].values
    xs, ys = transformer.transform(lons, lats)
    df_stops["utm_x"] = xs
    df_stops["utm_y"] = ys
    df_stops.to_sql("stops", conn, if_exists="replace", index=False)
    cur.execute("CREATE INDEX idx_stops_id ON stops(stop_id);")
    counts["stops"] = len(df_stops)

    # 6. Shapes
    print("6. Ingesting shapes.txt...")
    df_shapes = pd.read_csv(z.open("shapes.txt"))
    df_shapes["shape_id"] = df_shapes["shape_id"].astype(str).str.strip()
    df_shapes["shape_pt_lat"] = pd.to_numeric(df_shapes["shape_pt_lat"], errors="coerce")
    df_shapes["shape_pt_lon"] = pd.to_numeric(df_shapes["shape_pt_lon"], errors="coerce")
    df_shapes["shape_pt_sequence"] = pd.to_numeric(df_shapes["shape_pt_sequence"], errors="coerce").astype(int)
    slons, slats = df_shapes["shape_pt_lon"].values, df_shapes["shape_pt_lat"].values
    sxs, sys_ = transformer.transform(slons, slats)
    df_shapes["utm_x"] = sxs
    df_shapes["utm_y"] = sys_
    df_shapes.to_sql("shapes", conn, if_exists="replace", index=False)
    cur.execute("CREATE INDEX idx_shapes_id ON shapes(shape_id, shape_pt_sequence);")
    counts["shapes"] = len(df_shapes)

    # 7. Trips
    print("7. Ingesting trips.txt...")
    df_trips = pd.read_csv(z.open("trips.txt"), dtype=str)
    df_trips["trip_id"] = df_trips["trip_id"].str.strip()
    df_trips["route_id"] = df_trips["route_id"].str.strip()
    df_trips["shape_id"] = df_trips["shape_id"].str.strip()
    df_trips.to_sql("trips", conn, if_exists="replace", index=False)
    cur.execute("CREATE INDEX idx_trips_id ON trips(trip_id);")
    cur.execute("CREATE INDEX idx_trips_route ON trips(route_id);")
    cur.execute("CREATE INDEX idx_trips_shape ON trips(shape_id);")
    counts["trips"] = len(df_trips)

    # 8. Stop Times
    print("8. Ingesting stop_times.txt (chunked)...")
    first = True
    total_st = 0
    chunk_size = 300000
    for chunk in pd.read_csv(z.open("stop_times.txt"), chunksize=chunk_size, dtype={"trip_id": str, "stop_id": str}):
        chunk["trip_id"] = chunk["trip_id"].str.strip()
        chunk["stop_id"] = chunk["stop_id"].str.strip()
        chunk["arrival_sec"] = chunk["arrival_time"].apply(parse_time_to_seconds)
        chunk["departure_sec"] = chunk["departure_time"].apply(parse_time_to_seconds)
        chunk.to_sql("stop_times", conn, if_exists="replace" if first else "append", index=False)
        first = False
        total_st += len(chunk)
        print(f"    ... loaded {total_st:,} stop_time rows")

    cur.execute("CREATE INDEX idx_stop_times_trip ON stop_times(trip_id, stop_sequence);")
    cur.execute("CREATE INDEX idx_stop_times_stop ON stop_times(stop_id);")
    counts["stop_times"] = total_st

    conn.commit()
    print("Phase 1 ingestion complete. Checking referential integrity...")

    cur.execute("SELECT count(*) FROM trips WHERE route_id NOT IN (SELECT route_id FROM routes);")
    orphan_trips = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM stop_times WHERE trip_id NOT IN (SELECT trip_id FROM trips);")
    orphan_st_trips = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM stop_times WHERE stop_id NOT IN (SELECT stop_id FROM stops);")
    orphan_st_stops = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM trips WHERE shape_id NOT IN (SELECT DISTINCT shape_id FROM shapes);")
    orphan_shapes = cur.fetchone()[0]

    integrity = {
        "orphan_trips": orphan_trips,
        "orphan_st_trips": orphan_st_trips,
        "orphan_st_stops": orphan_st_stops,
        "orphan_shapes": orphan_shapes
    }
    print("Integrity verification:", integrity)
    return {"counts": counts, "integrity": integrity}


def run_phase2_crosswalk(conn_dlm1: sqlite3.Connection, conn_old: sqlite3.Connection) -> pd.DataFrame:
    print("\n=== PHASE 2: BUILDING LEGACY-TO-DLM1 STOP CROSSWALK ===")
    from scipy.spatial import cKDTree

    # Load legacy stops
    df_old_stops = pd.read_sql_query("SELECT stop_id, stop_name, stop_lat, stop_lon, utm_x, utm_y FROM stops", conn_old)
    print(f"Loaded {len(df_old_stops):,} legacy stops from {OLD_DB}")

    # Load DLM1 stops
    df_new_stops = pd.read_sql_query("SELECT stop_id, stop_name, stop_lat, stop_lon, utm_x, utm_y FROM stops", conn_dlm1)
    print(f"Loaded {len(df_new_stops):,} DLM1 stops from {STAGED_DB}")

    # Build k-d tree on DLM1 UTM coordinates
    coords_new = np.vstack([df_new_stops["utm_x"].values, df_new_stops["utm_y"].values]).T
    tree = cKDTree(coords_new)

    coords_old = np.vstack([df_old_stops["utm_x"].values, df_old_stops["utm_y"].values]).T

    # Query all neighbors within 150 meters
    radius_m = 150.0
    neighbors_list = tree.query_ball_point(coords_old, r=radius_m)

    crosswalk_rows = []

    high_conf = 0
    review_req = 0
    unmatched = 0

    for idx, old_row in df_old_stops.iterrows():
        old_id = str(old_row["stop_id"]).strip()
        old_name = str(old_row["stop_name"])
        old_lat = float(old_row["stop_lat"])
        old_lon = float(old_row["stop_lon"])

        candidate_indices = neighbors_list[idx]

        if not candidate_indices:
            unmatched += 1
            crosswalk_rows.append({
                "legacy_stop_id": old_id,
                "legacy_stop_name": old_name,
                "legacy_lat": old_lat,
                "legacy_lon": old_lon,
                "dlm1_stop_id": None,
                "dlm1_stop_name": None,
                "dlm1_lat": None,
                "dlm1_lon": None,
                "distance_m": None,
                "name_similarity": 0.0,
                "candidate_count": 0,
                "match_classification": "UNMATCHED",
                "notes": "No DLM1 stop within 150m radius"
            })
            continue

        # Score all candidates within 150m
        candidates = []
        for c_idx in candidate_indices:
            c_row = df_new_stops.iloc[c_idx]
            c_id = str(c_row["stop_id"]).strip()
            c_name = str(c_row["stop_name"])
            c_lat = float(c_row["stop_lat"])
            c_lon = float(c_row["stop_lon"])
            dist = haversine(old_lat, old_lon, c_lat, c_lon)
            sim = string_similarity(old_name, c_name)
            candidates.append({
                "dlm1_stop_id": c_id,
                "dlm1_stop_name": c_name,
                "dlm1_lat": c_lat,
                "dlm1_lon": c_lon,
                "distance_m": dist,
                "name_similarity": sim
            })

        # Sort candidates: combined score (favoring distance and similarity)
        # score = 0.5 * (1 - min(dist, 100)/100) + 0.5 * sim
        for c in candidates:
            c["score"] = 0.5 * (1.0 - min(c["distance_m"], 150.0) / 150.0) + 0.5 * c["name_similarity"]

        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]

        cand_count = len(candidates)
        # Check platform ambiguity: another candidate within 30m with high similarity
        ambiguous = False
        if len(candidates) > 1:
            second = candidates[1]
            if abs(best["distance_m"] - second["distance_m"]) < 20.0 and second["name_similarity"] > 0.6:
                ambiguous = True

        # Classification rules:
        # HIGH_CONFIDENCE: distance <= 45m AND name_similarity >= 0.70 AND NOT ambiguous
        # REVIEW_REQUIRED: distance <= 150m but fails high-confidence or is ambiguous
        if best["distance_m"] <= 45.0 and best["name_similarity"] >= 0.70 and not ambiguous:
            classification = "HIGH_CONFIDENCE"
            notes = f"Strong 1:1 match within {best['distance_m']:.1f}m (sim: {best['name_similarity']:.2f})"
            high_conf += 1
        elif best["distance_m"] <= 150.0:
            classification = "REVIEW_REQUIRED"
            reasons = []
            if ambiguous:
                reasons.append("Platform/multi-candidate ambiguity")
            if best["distance_m"] > 45.0:
                reasons.append(f"Distance {best['distance_m']:.1f}m > 45m")
            if best["name_similarity"] < 0.70:
                reasons.append(f"Name similarity {best['name_similarity']:.2f} < 0.70")
            notes = "; ".join(reasons)
            review_req += 1
        else:
            classification = "UNMATCHED"
            notes = "Distance exceeded threshold"
            unmatched += 1

        crosswalk_rows.append({
            "legacy_stop_id": old_id,
            "legacy_stop_name": old_name,
            "legacy_lat": old_lat,
            "legacy_lon": old_lon,
            "dlm1_stop_id": best["dlm1_stop_id"],
            "dlm1_stop_name": best["dlm1_stop_name"],
            "dlm1_lat": best["dlm1_lat"],
            "dlm1_lon": best["dlm1_lon"],
            "distance_m": round(best["distance_m"], 2),
            "name_similarity": round(best["name_similarity"], 4),
            "candidate_count": cand_count,
            "match_classification": classification,
            "notes": notes
        })

    df_crosswalk = pd.DataFrame(crosswalk_rows)
    print(f"\nCrosswalk Classification Summary across {len(df_crosswalk):,} legacy stops:")
    print(f"  HIGH_CONFIDENCE: {high_conf:,} ({high_conf/len(df_crosswalk)*100:.2f}%)")
    print(f"  REVIEW_REQUIRED: {review_req:,} ({review_req/len(df_crosswalk)*100:.2f}%)")
    print(f"  UNMATCHED:       {unmatched:,} ({unmatched/len(df_crosswalk)*100:.2f}%)")

    # Save to SQLite table in DLM1 database
    df_crosswalk.to_sql("legacy_stop_crosswalk", conn_dlm1, if_exists="replace", index=False)
    conn_dlm1.cursor().execute("CREATE INDEX idx_cw_legacy ON legacy_stop_crosswalk(legacy_stop_id);")
    conn_dlm1.cursor().execute("CREATE INDEX idx_cw_dlm1 ON legacy_stop_crosswalk(dlm1_stop_id);")
    conn_dlm1.commit()

    # Save to disk artifacts
    os.makedirs(os.path.dirname(OUTPUT_CROSSWALK_CSV), exist_ok=True)
    df_crosswalk.to_csv(OUTPUT_CROSSWALK_CSV, index=False)
    df_crosswalk.to_parquet(OUTPUT_CROSSWALK_PARQUET, index=False)
    print(f"Saved crosswalk table to {OUTPUT_CROSSWALK_CSV} and {OUTPUT_CROSSWALK_PARQUET}")

    return df_crosswalk


def run_phase3_historical_compatibility(df_crosswalk: pd.DataFrame, conn_dlm1: sqlite3.Connection) -> dict:
    print("\n=== PHASE 3: EVALUATING HISTORICAL GPS COMPATIBILITY ===")
    import glob

    # Read all verified historical segment observations (136 total)
    obs_files = sorted(glob.glob("data/processed/stop_crossings/service_date=*/observed_segments.parquet"))
    all_obs = []
    for f in obs_files:
        df_obs = pd.read_parquet(f)
        all_obs.append(df_obs)
    df_all_obs = pd.concat(all_obs, ignore_index=True)
    print(f"Total historical segment observations loaded: {len(df_all_obs):,}")

    cw_map = {row["legacy_stop_id"]: row for _, row in df_crosswalk.iterrows()}

    # Check mapping for each observation
    mapped_obs = 0
    high_conf_obs = 0
    review_obs = 0
    unmapped_obs = 0

    route_stats = {"1598": {"total": 0, "high_conf": 0, "review": 0, "unmapped": 0},
                   "1445": {"total": 0, "high_conf": 0, "review": 0, "unmapped": 0},
                   "1657": {"total": 0, "high_conf": 0, "review": 0, "unmapped": 0}}

    segment_pairs = set()

    for _, row in df_all_obs.iterrows():
        from_id = str(row["stop_id_from"]).strip()
        to_id = str(row["stop_id_to"]).strip()
        rid = str(row["route_id"]).strip()
        segment_pairs.add((rid, from_id, to_id))

        if rid not in route_stats:
            route_stats[rid] = {"total": 0, "high_conf": 0, "review": 0, "unmapped": 0}
        route_stats[rid]["total"] += 1

        if from_id not in cw_map or to_id not in cw_map:
            unmapped_obs += 1
            route_stats[rid]["unmapped"] += 1
            continue

        from_cw = cw_map[from_id]
        to_cw = cw_map[to_id]

        if from_cw["match_classification"] == "UNMATCHED" or to_cw["match_classification"] == "UNMATCHED":
            unmapped_obs += 1
            route_stats[rid]["unmapped"] += 1
        elif from_cw["match_classification"] == "HIGH_CONFIDENCE" and to_cw["match_classification"] == "HIGH_CONFIDENCE":
            high_conf_obs += 1
            route_stats[rid]["high_conf"] += 1
        else:
            review_obs += 1
            route_stats[rid]["review"] += 1

    print(f"Historical Segment Pairs: {len(segment_pairs)} distinct pairs across {len(df_all_obs)} observations")
    print(f"  HIGH_CONFIDENCE Observations: {high_conf_obs:,} ({high_conf_obs/len(df_all_obs)*100:.1f}%)")
    print(f"  REVIEW_REQUIRED Observations: {review_obs:,} ({review_obs/len(df_all_obs)*100:.1f}%)")
    print(f"  UNMAPPED Observations:        {unmapped_obs:,} ({unmapped_obs/len(df_all_obs)*100:.1f}%)")
    print("Route breakdown:", route_stats)

    # Detailed inspection of Route 1598 stop pairs
    print("\nInspecting Route 1598 historical stop pairs:")
    r1598_pairs = [p for p in segment_pairs if p[0] == "1598"]
    for rid, fid, tid in sorted(r1598_pairs):
        fcw = cw_map.get(fid)
        tcw = cw_map.get(tid)
        print(f"  Pair {fid} -> {tid}:")
        print(f"    From: {fcw['legacy_stop_name']} -> {fcw['dlm1_stop_name']} (DLM1 ID: {fcw['dlm1_stop_id']}, {fcw['distance_m']}m, {fcw['match_classification']})")
        print(f"    To:   {tcw['legacy_stop_name']} -> {tcw['dlm1_stop_name']} (DLM1 ID: {tcw['dlm1_stop_id']}, {tcw['distance_m']}m, {tcw['match_classification']})")

    return {
        "total_obs": len(df_all_obs),
        "high_conf_obs": high_conf_obs,
        "review_obs": review_obs,
        "unmapped_obs": unmapped_obs,
        "route_stats": route_stats
    }


def main():
    skip_ingest = False
    if os.path.exists(STAGED_DB):
        c = sqlite3.connect(STAGED_DB).cursor()
        tbls = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "stops" in tbls and "stop_times" in tbls and "shapes" in tbls:
            st_count = c.execute("SELECT count(*) FROM stop_times").fetchone()[0]
            if st_count == 2737136:
                print(f"Staged database {STAGED_DB} already populated ({st_count:,} stop_times). Skipping re-ingestion.")
                skip_ingest = True

    conn_dlm1 = sqlite3.connect(STAGED_DB)
    if not skip_ingest:
        with zipfile.ZipFile(DLM1_ZIP, "r") as z:
            phase1_res = run_phase1_ingest(z, conn_dlm1)

    conn_old = sqlite3.connect(OLD_DB)
    df_cw = run_phase2_crosswalk(conn_dlm1, conn_old)
    phase3_res = run_phase3_historical_compatibility(df_cw, conn_dlm1)

    conn_dlm1.close()
    conn_old.close()

    print("\n=== M11 PHASES 1-3 EXECUTION COMPLETE ===")


if __name__ == "__main__":
    main()
