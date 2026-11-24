"""Stop-Crossing Ground Truth Extraction Module.

Extracts stop arrivals, dwell estimates, and consecutive-stop segment travel times
using linear referencing along matched vehicle trajectories, conforming to
PRD Section 6.5 and Section 6.6.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import zoneinfo
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from backend.core.geometry import RoutePattern

TZ_IST = zoneinfo.ZoneInfo("Asia/Kolkata")


@dataclass
class StopCrossing:
    trajectory_id: str
    vehicle_id: str
    route_id: str
    pattern_id: str
    direction_id: int
    stop_sequence: int
    stop_id: str
    stop_name: str
    stop_along_dist_m: float
    arrival_time_utc: float
    arrival_time_ist: str
    dwell_duration_s: Optional[float]
    bracketing_gap_s: float
    bracketing_dist_m: float
    crossing_confidence: float
    quality_status: str


@dataclass
class ObservedSegment:
    observation_id: str
    trajectory_id: str
    vehicle_id: str
    route_id: str
    pattern_id: str
    direction_id: int
    segment_key: str
    stop_sequence_from: int
    stop_sequence_to: int
    stop_id_from: str
    stop_id_to: str
    stop_name_from: str
    stop_name_to: str
    distance_m: float
    segment_time_s: float
    speed_kmh: float
    arrival_from_utc: float
    arrival_to_utc: float
    arrival_from_ist: str
    arrival_to_ist: str
    dwell_from_s: Optional[float]
    match_confidence: float
    quality_flag: str


def extract_stop_crossings_from_trajectory(
    matched_pings_df: pd.DataFrame,
    pattern: RoutePattern,
    max_interpolation_gap_s: float = 120.0,
    max_interpolation_dist_m: float = 600.0,
    min_speed_kmh: float = 1.0,
    max_speed_kmh: float = 90.0,
    dwell_radius_m: float = 50.0,
    match_confidence: float = 0.90,
) -> Tuple[List[StopCrossing], List[ObservedSegment]]:
    """Extract stop crossings and consecutive-stop segments along a matched trajectory.

    Rejects ambiguous crossings and enforces strictly monotonic progression.
    """
    if matched_pings_df.empty or len(pattern.stops) < 2:
        return [], []

    pings = matched_pings_df.sort_values(by="timestamp_utc").copy()
    ts = pings["timestamp_utc"].values
    alongs = pings["along_dist_m"].values
    speeds = pings["speed_kmh"].values

    vehicle_id = str(pings["vehicle_id"].iloc[0])
    traj_id = str(pings["trajectory_id"].iloc[0])

    crossings: List[StopCrossing] = []
    last_arrival_utc = -1.0

    for stop in pattern.stops:
        target_s = stop.along_dist_m

        # Check if trajectory encompasses this stop position
        if target_s < alongs[0] or target_s > alongs[-1]:
            continue

        # Find bracketing pings
        # Last ping before or at target_s
        idx_before = np.where(alongs <= target_s)[0]
        # First ping after or at target_s
        idx_after = np.where(alongs >= target_s)[0]

        if len(idx_before) == 0 or len(idx_after) == 0:
            continue

        ia = idx_before[-1]
        ib = idx_after[0]

        tA = float(ts[ia])
        tB = float(ts[ib])
        sA = float(alongs[ia])
        sB = float(alongs[ib])

        # Enforce chronological ordering
        if tB < tA:
            continue

        dt = tB - tA
        ds = sB - sA

        # Quality Gate: maximum interpolation gap check
        if dt > max_interpolation_gap_s:
            continue

        if ds > max_interpolation_dist_m:
            continue

        # Compute arrival time
        if ds == 0.0 or dt == 0.0:
            arrival_utc = tA
        else:
            weight = (target_s - sA) / ds
            arrival_utc = tA + weight * dt

        # Monotonicity check against previous stop arrival
        if arrival_utc <= last_arrival_utc:
            # Reject non-monotonic arrival (indicates loop confusion or standstill jitter)
            continue

        # Dwell estimation: check for stationary pings near this stop
        stop_mask = (np.abs(alongs - target_s) <= dwell_radius_m) & (speeds <= 2.0)
        dwell_ts = ts[stop_mask]
        dwell_s = None
        if len(dwell_ts) >= 2:
            dwell_s = float(np.max(dwell_ts) - np.min(dwell_ts))
            if dwell_s > 600.0:  # Cap implausible single-stop dwell
                dwell_s = 600.0

        dt_ist = datetime.fromtimestamp(arrival_utc, TZ_IST).strftime("%Y-%m-%d %H:%M:%S")

        crossing = StopCrossing(
            trajectory_id=traj_id,
            vehicle_id=vehicle_id,
            route_id=pattern.route_id,
            pattern_id=pattern.pattern_id,
            direction_id=pattern.direction_id,
            stop_sequence=stop.stop_sequence,
            stop_id=stop.stop_id,
            stop_name=stop.stop_name,
            stop_along_dist_m=target_s,
            arrival_time_utc=arrival_utc,
            arrival_time_ist=dt_ist,
            dwell_duration_s=dwell_s,
            bracketing_gap_s=dt,
            bracketing_dist_m=ds,
            crossing_confidence=match_confidence,
            quality_status="VALID_INTERPOLATED",
        )
        crossings.append(crossing)
        last_arrival_utc = arrival_utc

    # Extract consecutive-stop segments
    segments: List[ObservedSegment] = []
    for i in range(len(crossings) - 1):
        c_from = crossings[i]
        c_to = crossings[i + 1]

        # Ensure stops are strictly consecutive in GTFS stop_sequence
        if c_to.stop_sequence != c_from.stop_sequence + 1:
            continue

        seg_dist = c_to.stop_along_dist_m - c_from.stop_along_dist_m
        seg_time = c_to.arrival_time_utc - c_from.arrival_time_utc

        if seg_dist <= 0 or seg_time <= 0:
            continue

        speed_kmh = (seg_dist / seg_time) * 3.6

        # Plausibility check
        if speed_kmh < min_speed_kmh or speed_kmh > max_speed_kmh:
            continue

        obs_id = f"{c_from.trajectory_id}_s{c_from.stop_sequence}_to_s{c_to.stop_sequence}"
        seg_key = f"{c_from.pattern_id}_seq{c_from.stop_sequence}"

        segment = ObservedSegment(
            observation_id=obs_id,
            trajectory_id=c_from.trajectory_id,
            vehicle_id=c_from.vehicle_id,
            route_id=c_from.route_id,
            pattern_id=c_from.pattern_id,
            direction_id=c_from.direction_id,
            segment_key=seg_key,
            stop_sequence_from=c_from.stop_sequence,
            stop_sequence_to=c_to.stop_sequence,
            stop_id_from=c_from.stop_id,
            stop_id_to=c_to.stop_id,
            stop_name_from=c_from.stop_name,
            stop_name_to=c_to.stop_name,
            distance_m=seg_dist,
            segment_time_s=seg_time,
            speed_kmh=speed_kmh,
            arrival_from_utc=c_from.arrival_time_utc,
            arrival_to_utc=c_to.arrival_time_utc,
            arrival_from_ist=c_from.arrival_time_ist,
            arrival_to_ist=c_to.arrival_time_ist,
            dwell_from_s=c_from.dwell_duration_s,
            match_confidence=min(c_from.crossing_confidence, c_to.crossing_confidence),
            quality_flag="VALID_SEGMENT",
        )
        segments.append(segment)

    return crossings, segments

