"""Statistical Baseline (M0): Hierarchical Historical Median Traffic Model.

Implements the PRD Section 7.4 & 7.5 Hierarchical Historical Median Model:
- Tier 1: Direct Observed Stop-Pair by (segment_key, day_type, hour_ist) [min_samples = 3]
- Tier 2: Physical Stop-Pair Pooled across co-running lines [min_samples = 3]
- Tier 3: Corridor-level velocity by (day_type, hour_ist) [min_samples = 3]
- Tier 4: Calibrated Route Baseline with empirical detour scaling (k_detour = 1.262)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


@dataclass
class BaselinePrediction:
    predicted_time_s: float
    predicted_speed_kmh: float
    lower_bound_p10_s: float
    upper_bound_p90_s: float
    tier: str
    sample_count: int
    confidence: float
    is_fallback: bool
    warning: Optional[str] = None


class HistoricalMedianBaseline:
    def __init__(self, min_samples: int = 3, default_speed_kmh: float = 18.0, detour_factor: float = 1.262):
        self.min_samples = min_samples
        self.default_speed_kmh = default_speed_kmh
        self.detour_factor = detour_factor
        self.tier1_stats: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
        self.tier2_stats: Dict[Tuple[str, str, int, int], Dict[str, Any]] = {}
        self.tier3_stats: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self.overall_corridor_speed_kmh: float = default_speed_kmh
        self.is_fitted = False

    def fit(self, df: pd.DataFrame) -> "HistoricalMedianBaseline":
        """Fit hierarchical baseline statistics using only historical training data."""
        if len(df) == 0:
            raise ValueError("Training dataframe is empty")

        df = df.copy()
        if "hour_ist" not in df.columns:
            if "arrival_from_ist" in df.columns:
                df["hour_ist"] = pd.to_datetime(df["arrival_from_ist"]).dt.hour
            else:
                df["hour_ist"] = 12

        if "is_weekend" not in df.columns:
            df["is_weekend"] = df["service_date"].astype(str).apply(
                lambda x: 1 if pd.to_datetime(x).day_name() in ["Saturday", "Sunday"] else 0
            )

        # 1. Tier 1: (segment_key, is_weekend, hour_ist)
        for (seg_key, is_wk, hr), grp in df.groupby(["segment_key", "is_weekend", "hour_ist"]):
            if len(grp) >= self.min_samples:
                self.tier1_stats[(seg_key, int(is_wk), int(hr))] = self._compute_group_stats(grp)

        # 2. Tier 2: Pooled by physical stops (stop_id_from, stop_id_to, is_weekend, hour_ist)
        for (s_from, s_to, is_wk, hr), grp in df.groupby(["stop_id_from", "stop_id_to", "is_weekend", "hour_ist"]):
            if len(grp) >= self.min_samples:
                self.tier2_stats[(str(s_from), str(s_to), int(is_wk), int(hr))] = self._compute_group_stats(grp)

        # 3. Tier 3: Corridor-level velocity by (is_weekend, hour_ist)
        for (is_wk, hr), grp in df.groupby(["is_weekend", "hour_ist"]):
            if len(grp) >= self.min_samples:
                self.tier3_stats[(int(is_wk), int(hr))] = {
                    "sample_count": len(grp),
                    "median_speed_kmh": float(grp["speed_kmh"].median()),
                    "mean_speed_kmh": float(grp["speed_kmh"].mean()),
                    "p10_speed_kmh": float(np.percentile(grp["speed_kmh"], 10)),
                    "p90_speed_kmh": float(np.percentile(grp["speed_kmh"], 90)),
                }

        # 4. Global Corridor Baseline
        self.overall_corridor_speed_kmh = float(df["speed_kmh"].median())
        self.is_fitted = True
        return self

    def _compute_group_stats(self, grp: pd.DataFrame) -> Dict[str, Any]:
        times = grp["segment_time_s"].values
        speeds = grp["speed_kmh"].values
        return {
            "sample_count": len(grp),
            "median_time_s": float(np.median(times)),
            "mean_time_s": float(np.mean(times)),
            "p10_time_s": float(np.percentile(times, 10)),
            "p25_time_s": float(np.percentile(times, 25)),
            "p50_time_s": float(np.median(times)),
            "p75_time_s": float(np.percentile(times, 75)),
            "p90_time_s": float(np.percentile(times, 90)),
            "std_time_s": float(np.std(times)),
            "median_speed_kmh": float(np.median(speeds)),
            "mean_speed_kmh": float(np.mean(speeds)),
        }

    def predict_one(
        self,
        segment_key: str,
        stop_id_from: str,
        stop_id_to: str,
        distance_m: float,
        hour_ist: int,
        is_weekend: int,
    ) -> BaselinePrediction:
        """Predict travel time for a single stop segment using hierarchical fallback."""
        if not self.is_fitted:
            raise RuntimeError("Baseline model must be fitted before predict")

        # Tier 1 Check
        t1_key = (segment_key, is_weekend, hour_ist)
        if t1_key in self.tier1_stats:
            stats = self.tier1_stats[t1_key]
            return BaselinePrediction(
                predicted_time_s=stats["median_time_s"],
                predicted_speed_kmh=stats["median_speed_kmh"],
                lower_bound_p10_s=stats["p10_time_s"],
                upper_bound_p90_s=stats["p90_time_s"],
                tier="TIER_1_DIRECT_OBSERVED",
                sample_count=stats["sample_count"],
                confidence=1.0,
                is_fallback=False,
            )

        # Tier 2 Check (Pooled Stop Pair)
        t2_key = (str(stop_id_from), str(stop_id_to), is_weekend, hour_ist)
        if t2_key in self.tier2_stats:
            stats = self.tier2_stats[t2_key]
            return BaselinePrediction(
                predicted_time_s=stats["median_time_s"],
                predicted_speed_kmh=stats["median_speed_kmh"],
                lower_bound_p10_s=stats["p10_time_s"],
                upper_bound_p90_s=stats["p90_time_s"],
                tier="TIER_2_CORRIDOR_POOLED",
                sample_count=stats["sample_count"],
                confidence=0.8,
                is_fallback=True,
                warning="Pooled across co-running routes on matching physical stop pair.",
            )

        # Tier 3 Check (Corridor-level speed for this hour)
        t3_key = (is_weekend, hour_ist)
        if t3_key in self.tier3_stats:
            stats = self.tier3_stats[t3_key]
            speed_kmh = stats["median_speed_kmh"]
            pred_time = (distance_m / (speed_kmh / 3.6)) if speed_kmh > 0 else 60.0
            p10_spd = stats["p90_speed_kmh"]  # faster speed -> lower time
            p90_spd = max(stats["p10_speed_kmh"], 1.0)  # slower speed -> higher time
            lower_s = (distance_m / (p10_spd / 3.6)) if p10_spd > 0 else pred_time * 0.7
            upper_s = (distance_m / (p90_spd / 3.6)) if p90_spd > 0 else pred_time * 1.5
            return BaselinePrediction(
                predicted_time_s=pred_time,
                predicted_speed_kmh=speed_kmh,
                lower_bound_p10_s=lower_s,
                upper_bound_p90_s=upper_s,
                tier="TIER_3_TIMEPOINT_AGGREGATED",
                sample_count=stats["sample_count"],
                confidence=0.6,
                is_fallback=True,
                warning="Corridor-level hourly speed fallback applied.",
            )

        # Tier 4 Fallback (Calibrated Route Baseline)
        effective_speed = max(self.overall_corridor_speed_kmh, 5.0)
        pred_time = (distance_m * self.detour_factor) / (effective_speed / 3.6)
        return BaselinePrediction(
            predicted_time_s=pred_time,
            predicted_speed_kmh=effective_speed,
            lower_bound_p10_s=pred_time * 0.6,
            upper_bound_p90_s=pred_time * 1.6,
            tier="TIER_4_ROUTE_BASELINE",
            sample_count=0,
            confidence=0.4,
            is_fallback=True,
            warning=f"Default corridor baseline scaled with local detour factor k={self.detour_factor:.3f}.",
        )

    def predict(self, df: pd.DataFrame) -> List[BaselinePrediction]:
        """Batch predict for a dataframe of segment queries."""
        df = df.copy()
        if "hour_ist" not in df.columns:
            df["hour_ist"] = pd.to_datetime(df["arrival_from_ist"]).dt.hour
        if "is_weekend" not in df.columns:
            df["is_weekend"] = df["service_date"].astype(str).apply(
                lambda x: 1 if pd.to_datetime(x).day_name() in ["Saturday", "Sunday"] else 0
            )

        preds = []
        for _, row in df.iterrows():
            p = self.predict_one(
                segment_key=str(row["segment_key"]),
                stop_id_from=str(row["stop_id_from"]),
                stop_id_to=str(row["stop_id_to"]),
                distance_m=float(row["distance_m"]),
                hour_ist=int(row["hour_ist"]),
                is_weekend=int(row["is_weekend"]),
            )
            preds.append(p)
        return preds

