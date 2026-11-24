"""Feature Engineering Pipeline for Delhi Transit Traffic Models.

Ensures strict leakage prevention:
- Training rows use Out-Of-Fold (leave-one-day-out) historical statistics.
- Validation and Test rows use statistics computed strictly from the Training period.
- No future timestamp or target leakage.
- Target variable: log(segment_time_s).
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


class TrafficFeatureExtractor:
    def __init__(self, default_speed_kmh: float = 18.0):
        self.default_speed_kmh = default_speed_kmh
        self.train_stop_pair_stats: Dict[str, Dict[str, float]] = {}
        self.train_hour_stats: Dict[int, Dict[str, float]] = {}
        self.is_fitted = False

    def fit(self, train_df: pd.DataFrame) -> "TrafficFeatureExtractor":
        """Compute training-period summary statistics for stop pairs and hourly traffic."""
        df = self._prepare_base_cols(train_df)

        # Stop pair stats on train set
        for seg_key, grp in df.groupby("segment_key"):
            self.train_stop_pair_stats[seg_key] = {
                "hist_median_log_time": float(np.median(np.log(grp["segment_time_s"]))),
                "hist_mean_log_time": float(np.mean(np.log(grp["segment_time_s"]))),
                "hist_std_log_time": float(np.std(np.log(grp["segment_time_s"]))) if len(grp) > 1 else 0.2,
                "hist_count": float(len(grp)),
            }

        # Hourly speed stats on train set
        for hr, grp in df.groupby("hour_ist"):
            self.train_hour_stats[int(hr)] = {
                "hour_median_speed": float(grp["speed_kmh"].median()),
                "hour_mean_speed": float(grp["speed_kmh"].mean()),
                "hour_count": float(len(grp)),
            }

        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame, is_train: bool = False) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Transform dataframe into feature matrix X and target vector y.
        
        If is_train=True, uses out-of-fold (leave-one-day-out) historical statistics
        to eliminate target leakage.
        """
        df = self._prepare_base_cols(df)
        feature_names = [
            "log_distance_m",
            "distance_m",
            "stop_sequence_from",
            "hour_sin",
            "hour_cos",
            "is_weekend",
            "is_holiday",
            "hist_median_log_time",
            "hist_sample_count",
            "hour_median_speed",
        ]

        X_rows = []
        y_vals = []

        dates = df["service_date"].astype(str).values

        for idx, row in df.iterrows():
            d = str(row["service_date"])
            seg_key = str(row["segment_key"])
            hr = int(row["hour_ist"])
            dist = float(row["distance_m"])
            seq = float(row["stop_sequence_from"])
            is_wk = float(row["is_weekend"])
            is_hol = float(row["is_holiday"])

            # Compute out-of-fold stats if training
            if is_train:
                # OOF: leave out current service date
                mask_other_dates = (dates != d)
                sub = df[mask_other_dates]
                seg_sub = sub[sub["segment_key"] == seg_key]
                if len(seg_sub) >= 2:
                    h_med = float(np.median(np.log(seg_sub["segment_time_s"])))
                    h_cnt = float(len(seg_sub))
                else:
                    # fallback to expected geometric log time
                    expected_time = dist / (self.default_speed_kmh / 3.6)
                    h_med = float(np.log(max(expected_time, 1.0)))
                    h_cnt = 0.0

                hr_sub = sub[sub["hour_ist"] == hr]
                if len(hr_sub) >= 2:
                    hr_spd = float(hr_sub["speed_kmh"].median())
                else:
                    hr_spd = self.default_speed_kmh
            else:
                # Use strictly training-period stats
                if seg_key in self.train_stop_pair_stats:
                    s_info = self.train_stop_pair_stats[seg_key]
                    h_med = s_info["hist_median_log_time"]
                    h_cnt = s_info["hist_count"]
                else:
                    expected_time = dist / (self.default_speed_kmh / 3.6)
                    h_med = float(np.log(max(expected_time, 1.0)))
                    h_cnt = 0.0

                if hr in self.train_hour_stats:
                    hr_spd = self.train_hour_stats[hr]["hour_median_speed"]
                else:
                    hr_spd = self.default_speed_kmh

            # Cyclical hour encoding
            hr_sin = float(np.sin(2 * np.pi * hr / 24.0))
            hr_cos = float(np.cos(2 * np.pi * hr / 24.0))

            feat_row = [
                float(np.log(max(dist, 1.0))),
                dist,
                seq,
                hr_sin,
                hr_cos,
                is_wk,
                is_hol,
                h_med,
                h_cnt,
                hr_spd,
            ]
            X_rows.append(feat_row)
            y_vals.append(float(np.log(max(row["segment_time_s"], 1.0))))

        return np.array(X_rows, dtype=np.float32), np.array(y_vals, dtype=np.float32), feature_names

    def _prepare_base_cols(self, df: pd.DataFrame) -> pd.DataFrame:
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

        if "is_holiday" not in df.columns:
            df["is_holiday"] = df["service_date"].astype(str).apply(
                lambda x: 1 if x == "2026-10-02" else 0
            )

        return df

