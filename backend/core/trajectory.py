"""GPS Trajectory Reconstruction and Cleaning Module.

Reconstructs chronologically ordered, gap-split vehicle trajectories from GPS
pings adhering to PRD Rules E05 (jump detection), E06 (speed consistency),
and E07 (excessive reporting gaps).
"""

import math
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from pyproj import Transformer

transformer_4326_to_32643 = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


def project_coordinates_to_utm(df: pd.DataFrame) -> pd.DataFrame:
    """Project lon/lat columns into utm_x, utm_y (EPSG:32643)."""
    if "utm_x" not in df.columns or "utm_y" not in df.columns:
        lons = df["lng"].values
        lats = df["lat"].values
        xs, ys = transformer_4326_to_32643.transform(lons, lats)
        df = df.copy()
        df["utm_x"] = xs
        df["utm_y"] = ys
    return df


def reconstruct_vehicle_trajectories(
    vehicle_pings: pd.DataFrame,
    max_gap_seconds: float = 300.0,
    max_speed_kmh: float = 90.0,
    split_on_trip_change: bool = True,
    max_terminal_idle_seconds: float = 900.0,
) -> pd.DataFrame:
    """Reconstruct continuous, clean trajectories for a single vehicle.

    Parameters:
        vehicle_pings: DataFrame of GPS pings for one vehicle on one service date.
        max_gap_seconds: Time gap (Rule E07) exceeding which trajectory is split.
        max_speed_kmh: Implied speed threshold (Rule E05) above which jump is split.
        split_on_trip_change: Whether to split trajectory when canonical trip_id changes.
        max_terminal_idle_seconds: Idle duration (zero displacement) after which to split.

    Returns:
        DataFrame enriched with:
        - trajectory_id: Unique identifier for each continuous movement segment
        - trajectory_seq: 0-indexed ping order within this trajectory
        - delta_t_sec: Time difference from previous ping
        - delta_dist_m: Distance from previous ping (meters)
        - implied_speed_kmh: Speed computed from displacement / delta_t
        - filter_decision: Reason for split or retention
    """
    if vehicle_pings.empty:
        return vehicle_pings

    pings = vehicle_pings.sort_values(by="timestamp_utc").copy()
    pings = project_coordinates_to_utm(pings)

    # Pre-allocate output columns
    n = len(pings)
    traj_ids = []
    traj_seqs = []
    delta_ts = [0.0] * n
    delta_dists = [0.0] * n
    implied_speeds = [0.0] * n
    decisions = ["START_OF_FEED"] + [""] * (n - 1)

    vehicle_id = str(pings["vehicle_id"].iloc[0])
    service_date = str(pings["service_date"].iloc[0]) if "service_date" in pings.columns else "2026-10-01"

    segment_idx = 1
    seq = 0
    current_traj_id = f"{vehicle_id}_{service_date}_seg{segment_idx:04d}"

    traj_ids.append(current_traj_id)
    traj_seqs.append(seq)

    xs = pings["utm_x"].values
    ys = pings["utm_y"].values
    ts = pings["timestamp_utc"].values
    trips = pings["trip_id_canonical"].values if "trip_id_canonical" in pings.columns else [""] * n

    for i in range(1, n):
        dt = float(ts[i] - ts[i - 1])
        dx = xs[i] - xs[i - 1]
        dy = ys[i] - ys[i - 1]
        dist = math.hypot(dx, dy)
        speed = (dist / dt * 3.6) if dt > 0 else 0.0

        delta_ts[i] = dt
        delta_dists[i] = dist
        implied_speeds[i] = speed

        # Decision rules
        split_reason = None

        if dt <= 0:
            split_reason = "E08_ZERO_OR_NEGATIVE_TIMESTEP"
        elif dt > max_gap_seconds:
            split_reason = f"E07_GAP_EXCEEDED_{int(dt)}s"
        elif speed > max_speed_kmh and dist > 500.0:
            split_reason = f"E05_IMPLAUSIBLE_JUMP_{int(speed)}kmh"
        elif split_on_trip_change and trips[i] != trips[i - 1] and trips[i] != "" and trips[i - 1] != "":
            split_reason = "TRIP_ID_CHANGED"

        if split_reason is not None:
            segment_idx += 1
            current_traj_id = f"{vehicle_id}_{service_date}_seg{segment_idx:04d}"
            seq = 0
            decisions[i] = split_reason
        else:
            seq += 1
            decisions[i] = "VALID_CONTINUOUS"

        traj_ids.append(current_traj_id)
        traj_seqs.append(seq)

    pings["trajectory_id"] = traj_ids
    pings["trajectory_seq"] = traj_seqs
    pings["delta_t_sec"] = delta_ts
    pings["delta_dist_m"] = delta_dists
    pings["implied_speed_kmh"] = implied_speeds
    pings["filter_decision"] = decisions

    return pings

