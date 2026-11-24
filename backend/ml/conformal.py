"""Split-Conformal Prediction Interval Estimation.

Implements inductive split-conformal prediction as specified in PRD Section 7.7:
1. Calculates non-conformity residuals on a held-out calibration/validation set.
2. Derives distribution-free interval radius for target coverage level (e.g. 90%).
3. Evaluates empirical coverage and interval sharpness on the held-out test partition.
"""

from typing import Dict, Tuple
import numpy as np


class SplitConformalCalibrator:
    def __init__(self, target_coverage: float = 0.90):
        self.target_coverage = target_coverage
        self.conformal_radius: float = 0.0
        self.val_sample_count: int = 0
        self.is_calibrated = False

    def calibrate(self, y_val_true_s: np.ndarray, y_val_pred_s: np.ndarray) -> "SplitConformalCalibrator":
        """Compute conformal radius q using validation absolute residuals."""
        n = len(y_val_true_s)
        if n == 0:
            raise ValueError("Validation set is empty for conformal calibration")

        residuals = np.abs(y_val_true_s - y_val_pred_s)
        self.val_sample_count = n

        # Finite-sample conformal quantile level
        level = min(np.ceil((n + 1) * self.target_coverage) / n, 1.0)
        self.conformal_radius = float(np.quantile(residuals, level))
        self.is_calibrated = True
        return self

    def predict_intervals(self, y_pred_s: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Produce lower and upper bounds [pred - q, pred + q] (clipped at >= 5s)."""
        if not self.is_calibrated:
            raise RuntimeError("Calibrator must be fitted before predict_intervals")
        lower = np.maximum(y_pred_s - self.conformal_radius, 5.0)
        upper = y_pred_s + self.conformal_radius
        return lower, upper

    def evaluate_coverage(self, y_test_true_s: np.ndarray, y_test_pred_s: np.ndarray) -> Dict[str, float]:
        """Evaluate empirical test-set coverage and average interval width."""
        lower, upper = self.predict_intervals(y_test_pred_s)
        covered = (y_test_true_s >= lower) & (y_test_true_s <= upper)
        empirical_coverage = float(np.mean(covered) * 100.0)
        avg_width = float(np.mean(upper - lower))
        median_width = float(np.median(upper - lower))

        return {
            "target_coverage_pct": round(self.target_coverage * 100.0, 1),
            "empirical_coverage_pct": round(empirical_coverage, 2),
            "conformal_radius_s": round(self.conformal_radius, 2),
            "avg_interval_width_s": round(avg_width, 2),
            "median_interval_width_s": round(median_width, 2),
            "calibration_samples_n": self.val_sample_count,
            "test_samples_n": len(y_test_true_s),
        }

