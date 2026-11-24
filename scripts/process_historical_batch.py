"""Streaming Batch Ingestion and Ground-Truth Extraction for Milestone 2.2.

Safely extracts selected historical daily SQLite databases from Cloudflare R2
using HTTP Range requests, converts them into typed Parquet partitions with
Rule E01-E03 quarantine, runs trajectory map-matching and stop-crossing extraction,
and deletes raw temporary SQLite files immediately to maintain host disk safety.
"""

from dataclasses import asdict
import io
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer
import py7zr
import requests

from backend.core.geometry import load_route_patterns
from backend.core.map_matching import match_trajectory_to_route
from backend.core.stop_crossings import extract_stop_crossings_from_trajectory
from backend.core.trajectory import reconstruct_vehicle_trajectories
from scripts.ingest_gps import process_daily_db

ARCHIVE_URL = "https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z"
TEMP_EXTRACT_DIR = "/tmp/gps_extract_m22"
GTFS_DB = "/tmp/delhi_mdb.db"
STOP_CROSSING_BASE_DIR = "data/processed/stop_crossings"

EXPANDED_CORRIDORS = {
    "1598": ["1598", "1578"],
    "1616": ["1616", "1445"],
    "1657": ["1657"],
    "1547": ["1547"],
    "1515": ["1515", "1734"],
}


class HttpRangeReader(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        resp = self.session.head(url)
        self.total_size = int(resp.headers["Content-Length"])
        self.pos = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.total_size + offset
        return self.pos

    def tell(self):
        return self.pos

    def readinto(self, b):
        length = len(b)
        if self.pos >= self.total_size:
            return 0
        end = min(self.pos + length - 1, self.total_size - 1)
        headers = {"Range": f"bytes={self.pos}-{end}"}
        resp = self.session.get(self.url, headers=headers)
        if resp.status_code not in (200, 206):
            raise IOError(f"HTTP error {resp.status_code}")
        data = resp.content
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def get_free_disk_mb() -> float:
    total, used, free = shutil.disk_usage("/")
    return free / (1024 * 1024)


def extract_stop_crossings_for_date(service_date: str, parquet_path: str):
    """Run trajectory map-matching and stop-crossing extraction on a clean parquet date partition."""
    out_dir = os.path.join(STOP_CROSSING_BASE_DIR, f"service_date={service_date}")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n--- Extracting Stop Crossings for {service_date} ---")

    # Load patterns
    patterns = {}
    for c_id, related in EXPANDED_CORRIDORS.items():
        combined = []
        for r_id in related:
            p = load_route_patterns(GTFS_DB, route_id=r_id)
            if r_id in p:
                combined.extend(p[r_id])
        patterns[c_id] = combined

    con = duckdb.connect()
    r_list = ", ".join(f"'{r}'" for r in EXPANDED_CORRIDORS.keys())
    df = con.execute(f"""
        SELECT 
            vehicle_id, lat, lng, speed_kmh, route_id, trip_id_raw, trip_id_canonical,
            timestamp_utc, timestamp_ist, service_date, hour_ist
        FROM '{parquet_path}'
        WHERE route_id IN ({r_list})
        ORDER BY route_id, vehicle_id, timestamp_utc;
    """).df()

    t_proj = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
    df["utm_x"], df["utm_y"] = t_proj.transform(df["lng"].values, df["lat"].values)

    all_crossings = []
    all_segments = []

    for (c_id, v_id), v_df in df.groupby(["route_id", "vehicle_id"]):
        cand_pats = patterns.get(c_id, [])
        if not cand_pats:
            continue

        v_df = v_df.sort_values(by="timestamp_utc").reset_index(drop=True)
        ts = v_df["timestamp_utc"].values
        xs = v_df["utm_x"].values
        ys = v_df["utm_y"].values
        spds = v_df["speed_kmh"].values
        trips = v_df["trip_id_canonical"].values

        splits = [0]
        n_p = len(v_df)
        stat_start_idx = 0

        for i in range(1, n_p):
            dt = ts[i] - ts[i - 1]
            dx = xs[i] - xs[i - 1]
            dy = ys[i] - ys[i - 1]
            dist = np.hypot(dx, dy)
            speed = (dist / dt * 3.6) if dt > 0 else 0.0

            if dt > 300.0 or dt <= 0 or (speed > 90.0 and dist > 500.0):
                splits.append(i)
                stat_start_idx = i
                continue
            if trips[i] != trips[i - 1] and trips[i] != "" and trips[i - 1] != "":
                splits.append(i)
                stat_start_idx = i
                continue
            if spds[i] <= 1.0 and dist < 30.0:
                if (ts[i] - ts[stat_start_idx]) > 300.0:
                    splits.append(i)
                    stat_start_idx = i
            else:
                stat_start_idx = i

        splits.append(n_p)

        for s_idx in range(len(splits) - 1):
            sub_df = v_df.iloc[splits[s_idx]:splits[s_idx + 1]].copy()
            if len(sub_df) < 5:
                continue

            traj_id = f"{v_id}_c{c_id}_seg{s_idx:04d}"
            sub_df["trajectory_id"] = traj_id

            res = match_trajectory_to_route(sub_df, cand_pats, max_perp_dist_m=65.0, min_monotonic_ratio=0.65)
            if res.status == "MATCHED_CONFIDENT":
                matched_pat = next(p for p in cand_pats if p.pattern_id == res.pattern_id)
                crossings, segments = extract_stop_crossings_from_trajectory(res.enriched_pings, matched_pat, match_confidence=res.confidence)
                all_crossings.extend(crossings)
                all_segments.extend(segments)

    crossings_file = os.path.join(out_dir, "stop_crossings.parquet")
    segments_file = os.path.join(out_dir, "observed_segments.parquet")

    crossings_df = pd.DataFrame([asdict(c) for c in all_crossings])
    segments_df = pd.DataFrame([asdict(s) for s in all_segments])

    con.register("cross_v", crossings_df)
    con.register("segs_v", segments_df)
    con.execute(f"COPY cross_v TO '{crossings_file}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    con.execute(f"COPY segs_v TO '{segments_file}' (FORMAT PARQUET, COMPRESSION ZSTD);")

    print(f"   {service_date}: Saved {len(crossings_df)} crossings and {len(segments_df)} segments.")
    return len(crossings_df), len(segments_df)


def process_target_dates(target_dates: list):
    os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)

    print("Connecting to remote 7z archive via HTTP range reader...")
    reader = io.BufferedReader(HttpRangeReader(ARCHIVE_URL), buffer_size=8 * 1024 * 1024)
    archive = py7zr.SevenZipFile(reader, mode="r")

    summary_results = {}

    for s_date in target_dates:
        db_name = f"bus_movements_{s_date.replace('-', '_')}.db"
        local_db_path = os.path.join(TEMP_EXTRACT_DIR, db_name)

        free_mb = get_free_disk_mb()
        print(f"\n=======================================================")
        print(f"Processing Date: {s_date} | Target: {db_name}")
        print(f"Current Free Disk Space: {free_mb:.1f} MB")
        print(f"=======================================================")

        if free_mb < 4000:
            print(f"[STOP] Insufficient free disk space ({free_mb:.1f} MB < 4000 MB). Stopping safely.")
            break

        # 1. Extract from archive
        t_ext0 = time.time()
        print(f"1. Extracting {db_name} from remote 7z archive...")
        archive.extract(path=TEMP_EXTRACT_DIR, targets=[db_name])
        ext_time = time.time() - t_ext0
        print(f"   Extraction completed in {ext_time:.1f}s.")

        # 2. Ingest into Parquet
        ingest_res = process_daily_db(local_db_path, s_date)

        # 3. Stop-Crossing Extraction
        pq_path = ingest_res["parquet_path"]
        n_cross, n_segs = extract_stop_crossings_for_date(s_date, pq_path)

        # 4. Remove temporary SQLite DB to preserve disk space
        if os.path.exists(local_db_path):
            os.remove(local_db_path)
            print(f"4. Cleaned up temporary {local_db_path}. Free space now: {get_free_disk_mb():.1f} MB.")

        summary_results[s_date] = {
            "service_date": s_date,
            "raw_records": ingest_res["raw_records"],
            "clean_records": ingest_res["clean_records_retained"],
            "stop_crossings": n_cross,
            "observed_segments": n_segs,
            "status": "SUCCESS",
        }

    out_metrics = "data/processed/batch_expansion_summary.json"
    with open(out_metrics, "w") as f:
        json.dump(summary_results, f, indent=2)
    print(f"\nBatch processing complete. Summary saved to {out_metrics}")
    return summary_results


if __name__ == "__main__":
    # Target representative days:
    # 2026-10-03 (Saturday - Weekend)
    # 2026-10-04 (Sunday - Weekend)
    # 2026-10-07 (Wednesday - Anomalous partial day)
    targets = ["2026-10-03", "2026-10-04", "2026-10-07"]
    process_target_dates(targets)

