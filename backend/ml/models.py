"""Candidate Traffic Models & Evaluation Engine.

Implements and evaluates:
- M0: Hierarchical Historical Median Baseline
- M1: Ridge Regression on log(segment_time_s)
- M2: Random Forest Regressor
- Split-Conformal Prediction Interval estimation
- PRD Section 9.2 metric computation (MAE, RMSE, MedAE, MeanSignedError, MAPE, MedAPE)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor

from backend.ml.baseline import HistoricalMedianBaseline
from backend.ml.features import TrafficFeatureExtractor


@dataclass
class ModelEvaluationReport:
    model_name: str
    mae_seconds: float
    rmse_seconds: float
    med_ae_seconds: float
    mean_signed_error_seconds: float
    mape_pct: float
    med_ape_pct: float
    pct_within_10pct: float
    pct_within_20pct: float
    improvement_over_m0_pct: float
    sample_count: int


def calculate_metrics(y_true_s: np.ndarray, y_pred_s: np.ndarray, baseline_mae: Optional[float] = None) -> Dict[str, float]:
    """Calculate PRD Section 9.2 performance metrics on travel time in seconds."""
    errors = y_pred_s - y_true_s
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    med_ae = float(np.median(abs_errors))
    bias = float(np.mean(errors))

    # MAPE with threshold actual > 30s to prevent division by near-zero artifact
    valid_mask = y_true_s >= 30.0
    if np.sum(valid_mask) > 0:
        mape = float(np.mean(abs_errors[valid_mask] / y_true_s[valid_mask]) * 100.0)
        med_ape = float(np.median(abs_errors[valid_mask] / y_true_s[valid_mask]) * 100.0)
    else:
        mape = float(np.mean(abs_errors / np.maximum(y_true_s, 1.0)) * 100.0)
        med_ape = float(np.median(abs_errors / np.maximum(y_true_s, 1.0)) * 100.0)

    rel_err = abs_errors / np.maximum(y_true_s, 1.0)
    within_10 = float(np.mean(rel_err <= 0.10) * 100.0)
    within_20 = float(np.mean(rel_err <= 0.20) * 100.0)

    imp = 0.0
    if baseline_mae is not None and baseline_mae > 0:
        imp = float((baseline_mae - mae) / baseline_mae * 100.0)

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "med_ae": round(med_ae, 2),
        "bias": round(bias, 2),
        "mape": round(mape, 2),
        "med_ape": round(med_ape, 2),
        "within_10": round(within_10, 2),
        "within_20": round(within_20, 2),
        "improvement_pct": round(imp, 2),
    }


class TrafficModelSuite:
    def __init__(self, min_samples_baseline: int = 3):
        self.baseline_m0 = HistoricalMedianBaseline(min_samples=min_samples_baseline)
        self.feature_extractor = TrafficFeatureExtractor()
        self.ridge_m1 = Ridge(alpha=10.0, random_state=42)
        self.rf_m2 = RandomForestRegressor(
            n_estimators=50,
            max_depth=4,
            min_samples_leaf=3,
            random_state=42
        )
        self.is_fitted = False

    def fit(self, train_df: pd.DataFrame):
        """Fit M0, M1, and M2 on training partition."""
        # 1. Fit M0 Baseline
        self.baseline_m0.fit(train_df)

        # 2. Fit Feature Extractor
        self.feature_extractor.fit(train_df)

        # 3. Transform features (OOF for training)
        X_train, y_train_log, _ = self.feature_extractor.transform(train_df, is_train=True)

        # 4. Fit M1 Ridge
        self.ridge_m1.fit(X_train, y_train_log)

        # 5. Fit M2 Random Forest
        self.rf_m2.fit(X_train, y_train_log)

        self.is_fitted = True

    def predict(self, test_df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Predict travel time in seconds for test partition across all models."""
        if not self.is_fitted:
            raise RuntimeError("Models must be fitted before predict")

        # M0 predictions
        m0_preds = self.baseline_m0.predict(test_df)
        y_pred_m0_s = np.array([p.predicted_time_s for p in m0_preds], dtype=np.float32)

        # Feature matrix for ML models (using train statistics strictly)
        X_test, _, _ = self.feature_extractor.transform(test_df, is_train=False)

        # M1 Ridge predictions: exp(log_pred)
        log_pred_m1 = self.ridge_m1.predict(X_test)
        y_pred_m1_s = np.exp(np.clip(log_pred_m1, 2.0, 8.0))

        # M2 RF predictions: exp(log_pred)
        log_pred_m2 = self.rf_m2.predict(X_test)
        y_pred_m2_s = np.exp(np.clip(log_pred_m2, 2.0, 8.0))

        return {
            "M0_Historical_Median": y_pred_m0_s,
            "M1_Ridge_Regression": y_pred_m1_s,
            "M2_Random_Forest": y_pred_m2_s,
            "m0_objects": m0_preds,
        }

