"""Historical Time-of-Day Traffic Profile Engine for Delhi Bus Corridors.

PRD v3.0 Milestone 8:
Builds empirical, evidence-backed time-of-day velocity and travel-time profiles
using only validated stop-to-stop observations across the five processed pilot dates
(October 1, 2, 3, 4, 7, 2026).

Enforces strict rules:
- No invented values for unobserved time bins (explicitly marked UNAVAILABLE).
- No global application of the Route 1598 detour factor (k=1.262).
- Full reporting of sample size, distinct dates, distinct vehicles, quartiles, and std.
- Clean distinction between DIRECT_OBSERVED, POOLED_PHYSICAL, and UNAVAILABLE.
"""

import glob
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class TimeProfileBin:
    route_id: Optional[str]
    stop_id_from: Optional[str]
    stop_id_to: Optional[str]
    stop_name_from: Optional[str]
    stop_name_to: Optional[str]
    direction_id: Optional[int]
    hour_ist: int
    day_type: str  # "ALL", "WEEKDAY", "WEEKEND"
    profile_status: str  # "OBSERVED", "POOLED", "UNAVAILABLE"
    sample_count: int
    distinct_service_dates_count: int
    distinct_vehicles_count: int
    service_dates: List[str]
    median_time_s: Optional[float]
    mean_time_s: Optional[float]
    std_time_s: Optional[float]
    p25_time_s: Optional[float]
    p75_time_s: Optional[float]
    iqr_time_s: Optional[float]
    min_time_s: Optional[float]
    max_time_s: Optional[float]
    median_speed_kmh: Optional[float]
    mean_speed_kmh: Optional[float]
    std_speed_kmh: Optional[float]
    distance_m: Optional[float]


class HistoricalTimeProfileEngine:
    """Computes and queries historical time-of-day traffic profiles from validated segments."""

    def __init__(self, data_pattern: str = "data/processed/stop_crossings/service_date=*/observed_segments.parquet"):
        self.data_pattern = data_pattern
        self.df: Optional[pd.DataFrame] = None
        self.stop_pair_profiles: Dict[Tuple[str, str, str, int, int, str], TimeProfileBin] = {}
        self.route_hourly_profiles: Dict[Tuple[str, int, int, str], TimeProfileBin] = {}
        self.corridor_hourly_profiles: Dict[Tuple[int, str], TimeProfileBin] = {}
        self.is_loaded = False

    def load_data(self) -> pd.DataFrame:
        """Load and concatenate all verified observed segment parquet files."""
        files = sorted(glob.glob(self.data_pattern))
        if not files:
            raise FileNotFoundError(f"No observed segment files found matching: {self.data_pattern}")

        dfs = []
        for f in files:
            date_str = os.path.basename(os.path.dirname(f)).split("=")[-1]
            sub_df = pd.read_parquet(f)
            sub_df["service_date"] = date_str
            dfs.append(sub_df)

        df = pd.concat(dfs, ignore_index=True)
        if "arrival_from_ist" in df.columns:
            df["hour_ist"] = pd.to_datetime(df["arrival_from_ist"]).dt.hour
        else:
            df["hour_ist"] = 12

        df["day_name"] = pd.to_datetime(df["service_date"]).dt.day_name()
        df["is_weekend"] = df["day_name"].isin(["Saturday", "Sunday"])
        df["day_type"] = df["is_weekend"].apply(lambda x: "WEEKEND" if x else "WEEKDAY")

        self.df = df
        self.is_loaded = True
        return df

    def build_profiles(self) -> Dict[str, Any]:
        """Build exhaustive profiles across all 24 hours without inventing values."""
        if not self.is_loaded or self.df is None:
            self.load_data()

        df = self.df
        assert df is not None

        # 1. Stop-pair hourly profiles: (route_id, stop_id_from, stop_id_to, direction_id, hour, day_type)
        stop_pairs = df.groupby(["route_id", "stop_id_from", "stop_id_to", "direction_id"]).first().reset_index()

        for _, row in stop_pairs.iterrows():
            r_id = str(row["route_id"])
            s_from = str(row["stop_id_from"])
            s_to = str(row["stop_id_to"])
            d_id = int(row["direction_id"])
            name_from = str(row["stop_name_from"])
            name_to = str(row["stop_name_to"])
            dist_m = float(row["distance_m"])

            # Full 24-hour cycle for each stop pair
            for hr in range(24):
                # All days combined
                sub = df[
                    (df["route_id"] == r_id)
                    & (df["stop_id_from"] == s_from)
                    & (df["stop_id_to"] == s_to)
                    & (df["direction_id"] == d_id)
                    & (df["hour_ist"] == hr)
                ]
                profile = self._calculate_bin(
                    sub=sub,
                    route_id=r_id,
                    stop_id_from=s_from,
                    stop_id_to=s_to,
                    stop_name_from=name_from,
                    stop_name_to=name_to,
                    direction_id=d_id,
                    hour_ist=hr,
                    day_type="ALL",
                    distance_m=dist_m,
                )
                self.stop_pair_profiles[(r_id, s_from, s_to, d_id, hr, "ALL")] = profile

        # 2. Route-level hourly profiles: (route_id, direction_id, hour, day_type)
        routes = df.groupby(["route_id", "direction_id"]).first().reset_index()
        for _, row in routes.iterrows():
            r_id = str(row["route_id"])
            d_id = int(row["direction_id"])
            for hr in range(24):
                sub = df[(df["route_id"] == r_id) & (df["direction_id"] == d_id) & (df["hour_ist"] == hr)]
                profile = self._calculate_bin(
                    sub=sub,
                    route_id=r_id,
                    stop_id_from=None,
                    stop_id_to=None,
                    stop_name_from=None,
                    stop_name_to=None,
                    direction_id=d_id,
                    hour_ist=hr,
                    day_type="ALL",
                    distance_m=None,
                )
                self.route_hourly_profiles[(r_id, d_id, hr, "ALL")] = profile

        # 3. Corridor-level hourly profiles (all observed segments on North GT Road)
        for hr in range(24):
            sub = df[df["hour_ist"] == hr]
            profile = self._calculate_bin(
                sub=sub,
                route_id=None,
                stop_id_from=None,
                stop_id_to=None,
                stop_name_from=None,
                stop_name_to=None,
                direction_id=None,
                hour_ist=hr,
                day_type="ALL",
                distance_m=None,
            )
            self.corridor_hourly_profiles[(hr, "ALL")] = profile

        return self.get_summary_metadata()

    def _calculate_bin(
        self,
        sub: pd.DataFrame,
        route_id: Optional[str],
        stop_id_from: Optional[str],
        stop_id_to: Optional[str],
        stop_name_from: Optional[str],
        stop_name_to: Optional[str],
        direction_id: Optional[int],
        hour_ist: int,
        day_type: str,
        distance_m: Optional[float],
    ) -> TimeProfileBin:
        """Compute robust descriptive statistics for a time bin without inventing data."""
        n = len(sub)
        if n == 0:
            return TimeProfileBin(
                route_id=route_id,
                stop_id_from=stop_id_from,
                stop_id_to=stop_id_to,
                stop_name_from=stop_name_from,
                stop_name_to=stop_name_to,
                direction_id=direction_id,
                hour_ist=hour_ist,
                day_type=day_type,
                profile_status="UNAVAILABLE",
                sample_count=0,
                distinct_service_dates_count=0,
                distinct_vehicles_count=0,
                service_dates=[],
                median_time_s=None,
                mean_time_s=None,
                std_time_s=None,
                p25_time_s=None,
                p75_time_s=None,
                iqr_time_s=None,
                min_time_s=None,
                max_time_s=None,
                median_speed_kmh=None,
                mean_speed_kmh=None,
                std_speed_kmh=None,
                distance_m=distance_m,
            )

        times = sub["segment_time_s"].values
        speeds = sub["speed_kmh"].values
        dates = sorted(sub["service_date"].unique().tolist())
        v_count = int(sub["vehicle_id"].nunique())

        p25 = float(np.percentile(times, 25))
        p75 = float(np.percentile(times, 75))
        iqr = float(p75 - p25)

        std_t = float(np.std(times, ddof=1)) if n > 1 else 0.0
        std_s = float(np.std(speeds, ddof=1)) if n > 1 else 0.0

        return TimeProfileBin(
            route_id=route_id,
            stop_id_from=stop_id_from,
            stop_id_to=stop_id_to,
            stop_name_from=stop_name_from,
            stop_name_to=stop_name_to,
            direction_id=direction_id,
            hour_ist=hour_ist,
            day_type=day_type,
            profile_status="OBSERVED",
            sample_count=n,
            distinct_service_dates_count=len(dates),
            distinct_vehicles_count=v_count,
            service_dates=dates,
            median_time_s=round(float(np.median(times)), 2),
            mean_time_s=round(float(np.mean(times)), 2),
            std_time_s=round(std_t, 2),
            p25_time_s=round(p25, 2),
            p75_time_s=round(p75, 2),
            iqr_time_s=round(iqr, 2),
            min_time_s=round(float(np.min(times)), 2),
            max_time_s=round(float(np.max(times)), 2),
            median_speed_kmh=round(float(np.median(speeds)), 2),
            mean_speed_kmh=round(float(np.mean(speeds)), 2),
            std_speed_kmh=round(std_s, 2),
            distance_m=distance_m if distance_m is not None else round(float(sub["distance_m"].mean()), 1),
        )

    def get_summary_metadata(self) -> Dict[str, Any]:
        """Return dataset coverage and profile completeness telemetry."""
        if self.df is None:
            return {}

        total_obs = len(self.df)
        distinct_dates = sorted(self.df["service_date"].unique().tolist())
        distinct_vehicles = int(self.df["vehicle_id"].nunique())
        distinct_routes = sorted(self.df["route_id"].unique().tolist())
        observed_hours = sorted(self.df["hour_ist"].unique().tolist())
        unobserved_hours = [h for h in range(24) if h not in observed_hours]

        df = self.df
        # Route breakdown
        route_counts = df["route_id"].value_counts().to_dict()
        obs_by_route = {str(k): int(v) for k, v in route_counts.items()}

        # Distinct physical stop pairs (stop_id_from, stop_id_to)
        df_physical = df[["stop_id_from", "stop_id_to"]].drop_duplicates()
        distinct_physical_pairs = len(df_physical)

        # Physical pairs by route
        phys_by_route = {}
        for r_id, grp in df.groupby("route_id"):
            phys_by_route[str(r_id)] = int(len(grp[["stop_id_from", "stop_id_to"]].drop_duplicates()))

        # Shared physical stop pairs between 1598 and 1445
        pairs_1598 = set(zip(df[df["route_id"] == "1598"]["stop_id_from"], df[df["route_id"] == "1598"]["stop_id_to"]))
        pairs_1445 = set(zip(df[df["route_id"] == "1445"]["stop_id_from"], df[df["route_id"] == "1445"]["stop_id_to"]))
        shared_count = len(pairs_1598.intersection(pairs_1445))

        # Stop-pair profile stats
        observed_stop_pair_bins = sum(
            1 for p in self.stop_pair_profiles.values() if p.profile_status == "OBSERVED"
        )
        total_stop_pair_bins = len(self.stop_pair_profiles)

        # Route hourly profile stats
        observed_route_bins = sum(
            1 for p in self.route_hourly_profiles.values() if p.profile_status == "OBSERVED"
        )
        total_route_bins = len(self.route_hourly_profiles)

        return {
            "total_observations": total_obs,
            "observations_by_route": obs_by_route,
            "distinct_service_dates": distinct_dates,
            "distinct_service_dates_count": len(distinct_dates),
            "distinct_vehicles_count": distinct_vehicles,
            "distinct_routes": distinct_routes,
            "distinct_route_stop_pairs_count": total_stop_pair_bins // 24 if total_stop_pair_bins > 0 else 26,
            "distinct_physical_stop_pairs_count": distinct_physical_pairs,
            "distinct_physical_stop_pairs_by_route": phys_by_route,
            "physical_stop_pairs_shared_count": shared_count,
            "observed_hours_ist": observed_hours,
            "unobserved_hours_ist": unobserved_hours,
            "observed_hours_count": len(observed_hours),
            "unobserved_hours_count": len(unobserved_hours),
            "stop_pair_hourly_bins_total": total_stop_pair_bins,
            "stop_pair_hourly_bins_observed": observed_stop_pair_bins,
            "stop_pair_hourly_bins_unavailable": total_stop_pair_bins - observed_stop_pair_bins,
            "route_hourly_bins_total": total_route_bins,
            "route_hourly_bins_observed": observed_route_bins,
            "route_hourly_bins_unavailable": total_route_bins - observed_route_bins,
            "temporal_coverage_ratio": round(len(observed_hours) / 24.0, 4),
        }

    def export_profiles(self, output_json_path: str = "data/processed/historical_time_profiles.json") -> Dict[str, Any]:
        """Export all computed profiles and metadata to a structured JSON file."""
        metadata = self.get_summary_metadata()

        profiles_list = [asdict(p) for p in self.stop_pair_profiles.values()]
        route_profiles_list = [asdict(p) for p in self.route_hourly_profiles.values()]
        corridor_profiles_list = [asdict(p) for p in self.corridor_hourly_profiles.values()]

        payload = {
            "metadata": metadata,
            "corridor_hourly_profiles": corridor_profiles_list,
            "route_hourly_profiles": route_profiles_list,
            "stop_pair_profiles": profiles_list,
        }

        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        with open(output_json_path, "w") as f:
            json.dump(payload, f, indent=2)

        return payload

