# Milestone 3.1 Final Reliability Assessment & Audit Synthesis (Revised)

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 3.1.1 – Statistical Audit Corrections  
**Overall Recommendation:** **DEGRADE (AUDITED & ACCEPTED AS EXPERIMENTAL BASELINE)**  
**Date:** November 21, 2026  
**Artifact Reference:** `data/processed/milestone3_1_audit_metrics.json`  

---

## 1. Executive Summary

Milestone 3.1.1 completes the statistical audit and corrections for the historical traffic baseline models, prediction interval calibrations, observation independence, feature engineering pipelines, and performance metrics across the verified 5-date pilot dataset ($N=136$ ground-truth stop-to-stop segment observations).

All statistical audit corrections requested by project leadership have been implemented:
1. **Ground-Truth Terminology & Accounting:** Formally distinguished **199 observed stop crossings**, **136 observed stop-to-stop segment observations**, and **26 distinct stop pairs**. Documented the exact operational status of **Route 1657** (1 segment on October 3 in Train; co-running corridor line).
2. **Conformal Lower-Bound Verification:** Inspected all calibration, validation, and test target values. Verified that global minimum segment time is $21.45\text{s}$ (zero values $< 5.0\text{s}$). Proved that lower-bound clipping at $5.0\text{s}$ has **zero impact on empirical coverage** (identically $26/30 = 86.67\%$ for both clipped and unclipped intervals). Preserved existing `backend/ml/conformal.py` implementation.
3. **Coverage Uncertainty & Clustered Variance:** Retained Clopper-Pearson bounds ($[69.28\%, 96.24\%]$) and binomial $p$-value ($0.61$) strictly as **illustrative calculations under an independence assumption**. Explicitly declared that clustered transit observations violate independent Bernoulli trials, and that **90% conformal coverage cannot be claimed as statistically demonstrated**. Recommended date/vehicle/stop-pair clustered evaluation strategies for future validation.
4. **M0 Fallback Tier Training Inventory & Test Errors:** Reported training observations available to each fallback tier (Tier 1: 3 obs, Tier 2: 3 obs, Tier 3: 77 obs, Tier 4: 84 obs). Quantified test errors by tier (Tier 3 MAE $= 221.87\text{s}$; Tier 4 MAE $= 123.63\text{s}$). Explicitly diagnosed link `seq9` failure as a **sparse-history fallback problem**.
5. **Architectural Roles Preserved:** Reaffirmed that **Hierarchical Historical Median (M0) serves as the primary auditable baseline**, while Random Forest (M2) is retained strictly as an **experimental benchmark under DEGRADE status**.

---

## 2. Ground-Truth Scope & Accounting

```
+----------------------------------------------------------------------------------------------------+
| Entity                               | Count | Description                                         |
+----------------------------------------------------------------------------------------------------+
| Observed Stop Crossings              | 199   | Arrival events at GTFS stops via linear interpolation|
| Observed Stop-to-Stop Segments       | 136   | Consecutive crossing intervals with valid metrics   |
| Distinct Physical Stop Pairs         | 26    | Unique (from_stop, to_stop) corridor road links     |
| Unique Vehicle Registrations         | 31    | 21 Train, 3 Val, 7 Test (strictly disjoint splits)  |
| Verified Route IDs                   | 3     | Route 1598 (124 obs), 1445 (11 obs), 1657 (1 obs)   |
+----------------------------------------------------------------------------------------------------+
```

### Route 1657 Accounting
- **Vehicle & Split:** `DL1PD9231`, October 3, 2026 (Assigned to Training Partition, $n=84$).
- **Segment:** `1657_dir0_pat0_seq3` (Sarai Peepal Thala $\to$ Jahangirpuri GT Road, $691.23\text{m}$, $273.26\text{s}$, $9.11\text{ km/h}$).
- **Status:** Co-running transit line sharing North GT Road corridor infrastructure. It contributes valid corridor ground truth to Tier 2 pooled stop-pair stats and route baselines. It had 0 observations in validation and test partitions and is properly accounted for in all metrics.

---

## 3. Conformal Lower-Bound Verification & Coverage Uncertainty

### 3.1 Lower-Bound Clipping Verification
- **Target Value Audit:** Minimum segment time across all 136 observations is **$21.45\text{ seconds}$**. Zero actual segment times fall below 5.0 seconds.
- **Coverage Impact:** Because $y_{\text{true}} \ge 21.45\text{s} > 5.0\text{s}$ everywhere:
  $$\text{Unclipped Coverage: } 26 / 30 \ (86.67\%) \quad \equiv \quad \text{Clipped Coverage: } 26 / 30 \ (86.67\%)$$
  Clipping the lower bound to $5.0\text{s}$ physically eliminates impossible negative travel times without altering the coverage status of any test observation.
- **Implementation Status:** The existing implementation in `backend/ml/conformal.py` is free of mathematical defects and is preserved.

### 3.2 Coverage Uncertainty & Non-Independent Clustering
- **Illustrative Independent Bounds:** Clopper-Pearson 95% CI is $[69.28\%, 96.24\%]$ with binomial $p=0.61$.
- **Clustered Reality:** Ordinary independent Bernoulli assumptions are violated by intra-vehicle trip clustering (e.g. `DL51EV4080` had 9 segments on Oct 7) and corridor-wide spatial correlation.
- **Strict Limitation:** **90% conformal coverage cannot be claimed as statistically demonstrated** from this 30-observation test sample.
- **Recommended Future Strategy:**
  1. *Date-Clustered Cross-Validation:* Leave-One-Date-Out (LODO) across all 31 October dates.
  2. *Vehicle-Run Block Conformal Prediction:* Grouping residuals by vehicle trips.
  3. *Cluster-Robust Variance Estimation:* Adjusting standard errors by $(\text{service\_date}, \text{segment\_key})$ clusters.

---

## 4. M0 Fallback Tier Reliability & `seq9` Failure Diagnosis

### 4.1 Training Inventory by Tier ($n_{\text{train}} = 84$)
- **Tier 1 (Direct Observed):** 1 cell ($n \ge 3$), 3 training observations ($3.57\%$).
- **Tier 2 (Corridor Pooled):** 1 cell ($n \ge 3$), 3 training observations ($3.57\%$).
- **Tier 3 (Timepoint Aggregated):** 10 cells ($n \ge 3$), 77 training observations ($91.67\%$).
- **Tier 4 (Route Baseline):** 1 global corridor baseline, 84 training observations ($100.0\%$).

### 4.2 Test Error Quantification by Tier ($n_{\text{test}} = 30$)
- **Tier 3 Queries ($n=7$):** M0 MAE $= 221.87\text{s}$, RMSE $= 411.16\text{s}$, MedAE $= 121.91\text{s}$ | M2 RF MAE $= 241.76\text{s}$, RMSE $= 384.16\text{s}$, MedAE $= 90.50\text{s}$. (Includes evening rush-hour standstill outlier on `seq2` with error $> 1000\text{s}$).
- **Tier 4 Queries ($n=23$):** M0 MAE $= 123.63\text{s}$, RMSE $= 175.12\text{s}$, MedAE $= 80.27\text{s}$ | M2 RF MAE $= \mathbf{86.78\text{s}}$, RMSE $= \mathbf{137.10\text{s}}$, MedAE $= \mathbf{48.23\text{s}}$.

### 4.3 `seq9` Sparse-History Fallback Failure
- Segment `1598_dir0_pat0_seq9` ($1634.72\text{m}$) had only 2 training observations, failing Tier 1 threshold ($n < 3$).
- M0 dropped to Tier 4 Route Baseline, predicting $674.87\text{s}$ based on the overall congested corridor speed ($11\text{ km/h} \times 1.262$).
- The actual link is a free-flowing arterial section where buses ran at $24\text{ km/h}$ ($239\text{--}252\text{s}$).
- The resulting $> 420\text{s}$ over-prediction shifted the conformal lower bound to $325.77\text{s}$, causing all 3 test observations to fall below the interval.
- This is explicitly a **sparse-history fallback failure**, which Random Forest mitigated by using continuous link distance ($\text{MAE} = 61.94\text{s}$ vs M0 $\text{MAE} = 427.98\text{s}$).

---

## 5. Recalculated Model Performance & Metric Verification

Directly recalculated from the 30 test observations on held-out October 7, adhering strictly to PRD Section 9.2:

```
+----------------------------------------------------------------------------------------------------------+
| Metric                     | M0: Historical Median | M1: Ridge Regression | M2: Random Forest | PRD Target |
+----------------------------------------------------------------------------------------------------------+
| Mean Absolute Error (MAE)  | 146.55 s              | 142.64 s             | 122.94 s          | Baseline   |
| Root Mean Squared Error    | 250.91 s              | 246.07 s             | 221.01 s          | —          |
| Median Absolute Error      | 87.44 s               | 88.31 s              | 68.29 s           | —          |
| Mean Signed Error (Bias)   | +67.00 s              | +60.45 s             | +47.48 s          | Towards 0  |
| MAPE (Actual >= 30s)       | 100.28%               | 125.10%              | 101.90%           | —          |
| MedAPE (Actual >= 30s)     | 92.99%                | 85.76%               | 51.64%            | Robust     |
| Predictions within 10%     | 0.00%                 | 6.67%                | 16.67%            | Maximized  |
| Predictions within 20%     | 10.00%                | 6.67%                | 26.67%            | Maximized  |
| Improvement over M0        | 0.00% (Reference)     | +2.67%               | +16.11%           | > 15%      |
+----------------------------------------------------------------------------------------------------------+
```

### Explanation of MAPE > 100%
- On short links ($20\text{--}40\text{s}$), predicting a conservative corridor travel time of $120\text{--}200\text{s}$ yields individual errors of $200\%\text{--}435\%$.
- Because MAPE is asymmetric and divides by small actual values, a few high-percentage outliers inflate the arithmetic mean above $100\%$.
- **MedAPE is robust to this skew:** M2 Random Forest achieved **$51.64\%$ MedAPE vs $92.99\%$ for M0** (a $44.5\%$ relative error reduction).

---

## 6. Scope & Provenance Levels

```
+---------------------------------------------------------------------------------------------------------------------+
| Level   | Classification                     | Operational Scope & Confidence Boundary                              |
+---------------------------------------------------------------------------------------------------------------------+
| LEVEL 1 | Directly Observed Ground Truth     | 136 segment observations from 199 crossings across 26 stop pairs.    |
|         |                                    | Confined strictly to North GT Road corridor (Routes 1598, 1445, 1657)|
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

### Detour Factor Restriction
The detour factor $k = 1.262$ was calibrated exclusively for North GT Road. **It must not be applied network-wide.**

---

## 7. Deliverables & Verification Inventory

| Deliverable | Path | Status |
| :--- | :--- | :---: |
| **Conformal Audit Report (Revised)** | `reports/milestone3_1_conformal_audit.md` | Verified & Updated |
| **Independence Audit Report (Revised)** | `reports/milestone3_1_independence_audit.md` | Verified & Updated |
| **Model Reliability Report (Revised)** | `reports/milestone3_1_model_reliability.md` | Verified & Updated |
| **Final Assessment Report (Revised)** | `reports/milestone3_1_final_assessment.md` | Verified & Updated |
| **Audit Metrics JSON** | `data/processed/milestone3_1_audit_metrics.json` | Verified & Updated |
| **Automated Verification Tests** | `backend/tests/test_milestone3_1.py` | 8/8 Passed |
| **Full Project Test Suite** | `backend/tests/` | **33/33 Passed** |

---

## 8. Recommendation: DEGRADE

The Milestone 3.1.1 Statistical Audit Corrections are **complete, mathematically proven, and fully tested**.

We recommend closing Milestone 3.1 under **DEGRADE** status with the following operational constraints:
- **Corridor Scope:** Traffic predictions and calibrated parameters apply strictly to the North GT Road corridor.
- **Baseline Primacy:** Hierarchical Historical Median (M0) serves as the primary auditable baseline. Random Forest (M2) remains an experimental benchmark.
- **Strict Stop Condition Adherence:** No journey planner, RAPTOR algorithm, frontend UI, or live feed has been implemented.

**STOPPING HERE AS DIRECTED. Awaiting explicit user approval before proceeding to Milestone 4.**
