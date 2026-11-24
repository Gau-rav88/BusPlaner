# Milestone 4 Final Reliability Assessment & Validation Synthesis

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 4.0 – Extended Model Validation  
**Overall Recommendation:** **DEGRADE (AUDITED & ACCEPTED AS PILOT BASELINE)**  
**Date:** November 21, 2026  
**Artifact Reference:** `data/processed/milestone4_metrics.json`  

---

## 1. Executive Summary & Milestone 4 Scope Review

Milestone 4 completes the extended model validation of the historical traffic statistical baseline and machine learning candidate models across the 5 verified historical service dates of October 2026 ($N=136$ observed stop-to-stop segments, $199$ observed stop crossings, $31$ distinct vehicles, $26$ stop pairs, $3$ routes).

All objectives authorized in Milestone 4 have been achieved without breaching project scope boundaries:
1. **Reporting Corrections Resolved:** Exactly 27 test observations were included in MAPE and MedAPE denominators ($y_{\text{true}} \ge 30.0\text{s}$) and 3 observations were excluded ($y_{\text{true}} < 30.0\text{s}$). Identical filtering was strictly enforced across M0, M1, and M2. Unfiltered MAE, RMSE, and MedAE ($n=30$) were fully preserved.
2. **Dataset Readiness & Storage Constraints Documented:** Identified 5 usable historical dates. Formally documented that host APFS container free disk space ($11.54\text{ GiB}$) precludes uncompressing the remaining $115.5\text{ GiB}$ archive. Validated that the 5-date dataset is sufficient for corridor-level baseline evaluation.
3. **Comprehensive Model Validation:** Evaluated M0, M1, and M2 across both held-out test (Oct 7, $n=30$) and validation (Oct 4, $n=22$) partitions. Produced granular breakdowns by route, operating period, fallback tier, and stop pair. Justified the omission of XGBoost.
4. **Prediction Interval Validation:** Validated split-conformal prediction intervals ($86.67\%$ empirical coverage, $532.03\text{s}$ average width). Demonstrated mathematically that vehicle-run calibration is statistically infeasible on $n=3$ validation vehicles.
5. **Generalization & Fallback Diagnostics:** Evaluated zero-shot unseen stop pairs (`1445_seq2` and `seq3`), sparse-history links (`seq9`), evening peak gridlock ($1643.58\text{s}$ on `seq2`), and telemetry feed outages.
6. **Strict Stop Condition Observed:** No journey planner, RAPTOR algorithm, frontend UI, or live feed has been implemented.

---

## 2. Integrated Model Performance Synthesis

```
+---------------------------------------------------------------------------------------------------------------+
| Metric                      | M0: Historical Median | M1: Ridge Regression  | M2: Random Forest   | Sample Count |
+---------------------------------------------------------------------------------------------------------------+
| --- HELD-OUT TEST PARTITION (October 7, Wednesday: Outage & Rush Hour) ---                                    |
+---------------------------------------------------------------------------------------------------------------+
| Mean Absolute Error (MAE)   | 146.55 s              | 142.64 s              | 122.94 s            | n = 30       |
| Root Mean Squared Error     | 250.91 s              | 246.07 s              | 221.01 s            | n = 30       |
| Median Absolute Error       | 87.44 s               | 88.31 s               | 68.29 s             | n = 30       |
| Mean Signed Error (Bias)    | +67.00 s              | +60.45 s              | +47.48 s            | n = 30       |
| Filtered MAPE (>= 30s)      | 100.28%               | 125.10%               | 101.90%             | n = 27       |
| Filtered MedAPE (>= 30s)    | 92.99%                | 85.76%                | 51.64%              | n = 27       |
| Predictions within 10%      | 0.00%                 | 6.67%                 | 16.67%              | n = 30       |
| Predictions within 20%      | 10.00%                | 6.67%                 | 26.67%              | n = 30       |
| Improvement over M0         | 0.00% (Reference)     | +2.67%                | +16.11%             | n = 30       |
+---------------------------------------------------------------------------------------------------------------+
| --- VALIDATION PARTITION (October 4, Sunday: Weekend Free-Flow Traffic) ---                                   |
+---------------------------------------------------------------------------------------------------------------+
| Mean Absolute Error (MAE)   | 128.81 s              | 79.76 s               | 65.56 s             | n = 22       |
| Root Mean Squared Error     | 167.52 s              | 97.74 s               | 74.63 s             | n = 22       |
| Median Absolute Error       | 92.10 s               | 65.02 s               | 61.04 s             | n = 22       |
| Mean Signed Error (Bias)    | +128.81 s             | +78.24 s              | +64.00 s            | n = 22       |
| Filtered MAPE (>= 30s)      | 138.32%               | 90.87%                | 86.82%              | n = 20       |
| Filtered MedAPE (>= 30s)    | 141.15%               | 81.17%                | 80.08%              | n = 20       |
| Improvement over M0         | 0.00% (Reference)     | +38.08%               | +49.11%             | n = 22       |
+---------------------------------------------------------------------------------------------------------------+
```

---

## 3. Key Findings Across Validation Dimensions

### 3.1 Model Hierarchy & Roles
- **Primary Auditable Baseline (M0):** The Hierarchical Historical Median model provides fully deterministic, explainable, and transparent travel-time bounds. It serves as the primary system baseline for journey planning.
- **Experimental Benchmark (M2):** Random Forest achieves meaningful predictive improvements on long arterial segments (e.g. `seq9`, $61.94\text{s}$ MAE vs $427.98\text{s}$ for M0) and captures day-of-week velocity shifts (achieving a $49.11\%$ MAE reduction on Sunday). However, it tends to overpredict on short links ($< 40\text{s}$) and cannot extrapolate beyond observed feature bounds. It is retained strictly as an experimental benchmark under DEGRADE status.
- **XGBoost Omission:** XGBoost was not installed and was deemed scientifically inappropriate for an $n=84$ training sample.

### 3.2 Conformal Prediction Intervals
- **Sharpness & Coverage:** Conformal radius is $q = 349.10\text{s}$. Lower-bound truncation at $5.0\text{s}$ reduces average interval width to $532.03\text{s}$ without altering coverage status. Empirical test coverage is **$86.67\%$ (26 / 30)**.
- **Cluster Feasibility:** In the validation split, only 3 vehicles operated. Calibrating non-parametric quantiles at the vehicle-run level requires at least $K \ge 10\text{--}20$ clusters and is mathematically impossible with $n=3$.
- **Strict Limitation:** 90% coverage cannot be guaranteed on small clustered samples.

### 3.3 Generalization & Edge Cases
- **Sparse History:** On links with $n < 3$ training observations (such as `seq9`), M0 drops to Tier 4 route baseline, which can overestimate travel time if the link is faster than the corridor median.
- **Unseen Links:** On unseen stop pairs (`1445_seq2` and `seq3`), M0 provides predictable, conservative fallbacks, whereas ML models overpredicted on short segments.
- **Peak Standstill:** Unprecedented gridlock at 17:00 IST on October 7 ($1.69\text{ km/h}$) breached upper bounds across all models, demonstrating that static/historical models cannot substitute for live streaming speed deltas.

---

## 4. Scope & Provenance Levels

To prevent over-generalization across Delhi, every travel-time estimate must declare its provenance tier:

```
+---------------------------------------------------------------------------------------------------------------------+
| Level   | Classification                     | Operational Scope & Confidence Boundary                              |
+---------------------------------------------------------------------------------------------------------------------+
| LEVEL 1 | Directly Observed Ground Truth     | 136 segment observations from 199 crossings across 26 stop pairs.    |
|         |                                    | Strictly local to the North GT Road corridor (Route 1598, 1445, 1657)|
+---------------------------------------------------------------------------------------------------------------------+
| LEVEL 2 | Historical Statistical Baseline    | Hierarchical Median (M0) with Tiers 1–4 fallback.                   |
|         |                                    | Primary auditable baseline; transparent, deterministic bounds.      |
+---------------------------------------------------------------------------------------------------------------------+
| LEVEL 3 | Experimental Machine Learning      | Ridge (M1) and Random Forest (M2) on log travel time.                |
|         |                                    | Evaluated on Oct 7; retained strictly as experimental benchmark.     |
+---------------------------------------------------------------------------------------------------------------------+
| LEVEL 4 | Timetable & Synthetic Fallback     | Static GTFS scheduled times and corridor default velocity (18 km/h). |
|         |                                    | Mandatory fallback for unobserved routes outside North GT Road.      |
+---------------------------------------------------------------------------------------------------------------------+
```

### Detour Factor Spatial Restriction
The calibrated detour factor ($k = 1.262$) was derived exclusively on North GT Road (ISBT Kashmiri Gate to Jahangirpuri). **It must NOT be applied network-wide.**

---

## 5. Deliverables & Verification Inventory

The following artifacts have been authored, verified, and placed in the project repository:
1. **Data Readiness Report:** [milestone4_data_readiness.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone4_data_readiness.md)
2. **Model Validation Report:** [milestone4_model_validation.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone4_model_validation.md)
3. **Generalization Report:** [milestone4_generalization.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone4_generalization.md)
4. **Prediction Intervals Report:** [milestone4_prediction_intervals.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone4_prediction_intervals.md)
5. **Final Assessment Report:** [milestone4_final_assessment.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone4_final_assessment.md)
6. **Validation Metrics JSON:** [milestone4_metrics.json](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/processed/milestone4_metrics.json)
7. **Validation Pipeline Script:** [compile_milestone4_validation.py](file:///Users/gauravchauhan/Downloads/delhi_hacks/scripts/compile_milestone4_validation.py)
8. **Automated Test Suite:** [test_milestone4.py](file:///Users/gauravchauhan/Downloads/delhi_hacks/backend/tests/test_milestone4.py) (6 new automated tests; all passing)
9. **Full Project Test Suite:** `pytest -v backend/tests/` passed all **39/39 tests** in 4.25 seconds.

---

## 6. Recommendation: DEGRADE

Milestone 4 Extended Model Validation is **complete, mathematically verified, and fully tested**.

We recommend approving Milestone 4 under **DEGRADE** status with the following operational constraints:
- **Corridor Scope:** Evaluated models and calibrated parameters are certified strictly for the North GT Road pilot corridor.
- **Baseline Primacy:** Hierarchical Historical Median (M0) remains the primary auditable baseline for subsequent journey planning. Random Forest (M2) remains an experimental benchmark.
- **Strict Stop Condition:** Milestone 5 (RAPTOR Journey Planner, multi-modal routing, and frontend UI) remains unstarted pending explicit authorization.

**STOPPING HERE AS DIRECTED. Awaiting explicit user review and approval.**

