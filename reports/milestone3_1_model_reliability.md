# Milestone 3.1 Model Reliability & Feature Audit Report (Revised)

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 3.1.1 – Statistical Audit Corrections  
**Status:** **AUDITED & VERIFIED (DEGRADE STATUS)**  
**Date:** November 21, 2026  
**Artifact Reference:** `data/processed/milestone3_1_audit_metrics.json`  

---

## 1. Executive Summary & Audit Objective

This report details the audit of the Machine Learning candidate models and feature engineering:
- **M0:** Hierarchical Historical Median Baseline (`backend/ml/baseline.py`)
- **M1:** Regularized Ridge Regression on $\log(\text{Time})$ (`backend/ml/models.py`)
- **M2:** Constrained Random Forest Regressor (`backend/ml/models.py`)
- **Feature Engineering Pipeline:** `backend/ml/features.py`

### Key Audit Goals:
1. Verify strict data leakage prevention and out-of-fold feature generation.
2. Quantify training observations available to each M0 hierarchical fallback tier.
3. Quantify test performance by fallback tier and diagnose sparse-history link failures (specifically `seq9`).
4. Inspect Random Forest tree complexity, hyperparameters, and feature importances.
5. Reiterate that **M0 serves as the primary auditable baseline**, while Random Forest remains strictly classified as **experimental under DEGRADE status**.

---

## 2. Feature Engineering & Data Leakage Verification

### 2.1 Audit Checklist

```
+--------------------------------------------------------------------------------------------------+
| Verification Item                                               | Status | Audit Evidence        |
+--------------------------------------------------------------------------------------------------+
| Target-derived features in input matrix                         | NONE   | Verified clean        |
| Test information used during training                           | NONE   | Verified clean        |
| Preprocessing fitted on validation or test sets                 | NONE   | Train partition only  |
| Duplicate or synthetic samples injected                         | NONE   | 136 original rows only|
| Out-of-fold (leave-one-day-out) historical stats during training| ACTIVE | features.py line 82   |
| Target transformation consistency                               | LOG(T) | np.log(segment_time_s)|
+--------------------------------------------------------------------------------------------------+
```

### 2.2 Out-Of-Fold (OOF) Training Protection
In `backend/ml/features.py`, historical features (e.g., `hist_median_log_time`, `hour_median_speed`) must not use the target of the observation being predicted:
- During training (`is_train=True`), for any observation on date $D$, historical aggregations are computed strictly over dates $\{D' \in \text{Train} \mid D' \neq D\}$. The observation's own service date is excluded.
- During inference (`is_train=False`), validation and test observations use static aggregations computed across the entire training partition ($D \in \{\text{Oct 1, Oct 2, Oct 3}\}$). No validation or test data is ever used to calculate historical priors.

---

## 3. M0 Fallback Tier Reliability & Training Inventory

The Hierarchical Historical Median model (M0) organizes historical knowledge into 4 cascading tiers with minimum sample thresholds ($n \ge 3$):
- **Tier 1:** Direct Observed Stop-Pair by `(segment_key, is_weekend, hour_ist)`.
- **Tier 2:** Physical Stop-Pair Pooled across co-running lines by `(stop_id_from, stop_id_to, is_weekend, hour_ist)`.
- **Tier 3:** Corridor-Level Velocity by `(is_weekend, hour_ist)`.
- **Tier 4:** Calibrated Route Baseline with empirical detour scaling ($k_{\text{detour}} = 1.262$).

### 3.1 Training Observations Available by Fallback Tier ($n_{\text{train}} = 84$)

```
+--------------------------------------------------------------------------------------------------+
| Fallback Tier             | Min Sample Threshold | Fitted Cells | Training Obs | Share of Train  |
+--------------------------------------------------------------------------------------------------+
| TIER 1: Direct Observed   | n >= 3               | 1 cell       | 3 obs        | 3.57%           |
| TIER 2: Corridor Pooled   | n >= 3               | 1 cell       | 3 obs        | 3.57%           |
| TIER 3: Timepoint Aggr    | n >= 3               | 10 cells     | 77 obs       | 91.67%          |
| TIER 4: Route Baseline    | n >= 0 (Global)      | 1 corridor   | 84 obs       | 100.0%          |
+--------------------------------------------------------------------------------------------------+
```

**Interpretation:** Because the training dataset consists of only 84 observations spread across 23 stop pairs and 24 hours, specific `(stop_pair, day_type, hour)` cells are sparse. Only 1 cell (`1598_dir0_pat0_seq6`, weekday, 08:00 IST) reached the 3-sample threshold for Tier 1. The vast majority of historical statistical power resides in Tier 3 (hourly corridor velocity, 77 obs) and Tier 4 (route baseline, 84 obs).

### 3.2 Test Set Performance Quantified by Fallback Tier ($n_{\text{test}} = 30$)

When tested on the held-out October 7 partition:
- **0 test queries** matched Tier 1 or Tier 2 cells (due to different operating hours and sparse training history).
- **7 test queries** resolved via **Tier 3 (Timepoint Aggregated)**.
- **23 test queries** resolved via **Tier 4 (Route Baseline)**.

| Metric | Tier 3: Timepoint Aggregated ($n=7$) | Tier 4: Route Baseline ($n=23$) | Full Test Set ($N=30$) |
| :--- | :---: | :---: | :---: |
| **M0 MAE** | $221.87\text{ s}$ | $123.63\text{ s}$ | $146.55\text{ s}$ |
| **M0 RMSE** | $411.16\text{ s}$ | $175.12\text{ s}$ | $250.91\text{ s}$ |
| **M0 MedAE** | $121.91\text{ s}$ | $80.27\text{ s}$ | $87.44\text{ s}$ |
| **M1 Ridge MAE** | $242.43\text{ s}$ | $112.27\text{ s}$ | $142.64\text{ s}$ |
| **M2 RF MAE** | $241.76\text{ s}$ | **$86.78\text{ s}$** | **$122.94\text{ s}$** |
| **M2 RF RMSE** | **$384.16\text{ s}$** | **$137.10\text{ s}$** | **$221.01\text{ s}$** |
| **M2 RF MedAE** | **$90.50\text{ s}$** | **$48.23\text{ s}$** | **$68.29\text{ s}$** |

*Note: Tier 3 includes the severe evening peak gridlock outlier at 17:00 IST on `seq2` (actual $= 1643.58\text{s}$), which inflates both M0 and ML errors.*

### 3.3 Root Cause of the `seq9` Failure: A Sparse-History Fallback Problem
The audit explicitly identified link `1598_dir0_pat0_seq9` ($1634.72\text{m}$) as a failure mode driven by sparse training history:
1. In the training set, `seq9` had only 2 observations ($n=2 < 3$). It was therefore disqualified from Tier 1.
2. For test queries on `seq9` (at hours 08:00, 09:00, and 18:00 IST), training data had no matching Tier 3 cells, forcing M0 to drop to **Tier 4 (Route Baseline)**.
3. Tier 4 applies the overall corridor median speed ($\approx 11.0\text{ km/h}$) scaled by the local detour factor ($k=1.262$):
   $$\hat{y}_{\text{Tier 4}} = \frac{1634.72 \times 1.262}{11.0 / 3.6} = 674.87 \text{ seconds}$$
4. However, `seq9` is physically a wide, free-flowing arterial segment where buses operated at $23\text{--}25\text{ km/h}$ on October 7 (actual times $239.02\text{s}, 249.59\text{s}, 252.06\text{s}$).
5. **Consequence:** M0 over-predicted travel time by over $420\text{ seconds}$, shifting the conformal prediction interval lower bound up to $325.77\text{s}$. All three test observations fell below the interval.
6. **Contrast with Machine Learning:** Random Forest (M2) utilized the continuous link distance feature ($1634.72\text{m}$) and learned that longer arterial sections operate at higher speeds, predicting $224\text{--}280\text{s}$ ($\text{MAE} = 61.94\text{s}$ vs M0 $\text{MAE} = 427.98\text{s}$).

---

## 4. Random Forest Architecture & Feature Importance

### 4.1 Hyperparameters & Regularization
To prevent overfitting on the small training sample ($n_{\text{train}} = 84$):
- `n_estimators`: 50
- `max_depth`: 4 (strictly enforced; mean tree depth $= 4.00$)
- `min_samples_leaf`: 3 (requires at least 3 historical observations per leaf)
- `random_state`: 42
- `mean_leaves_per_tree`: $10.76$ (minimum 8, maximum 13)

### 4.2 Feature Importances
```
Feature Importance Ranking (M2 Random Forest):
1. hist_median_log_time :  29.52%  [Prior stop-pair speed profile]
2. hour_median_speed    :  28.80%  [Corridor diurnal traffic velocity]
3. hour_sin             :  18.01%  [Time-of-day cyclical component]
4. hist_sample_count    :   4.65%  [Reliability of historical data]
5. log_distance_m       :   4.38%  [Physical segment distance scale]
6. is_holiday           :   4.32%  [Special traffic condition (Gandhi Jayanti)]
7. distance_m           :   3.79%  [Physical link length]
8. hour_cos             :   3.12%  [Diurnal phase component]
9. stop_sequence_from   :   2.20%  [Route progression position]
10. is_weekend          :   1.22%  [Day-type indicator]
```

---

## 5. Architectural Role & Recommendation: M0 as Primary Baseline

While Random Forest demonstrates superior performance on long arterial segments by interpolating link distance, it **must remain classified strictly as an experimental candidate benchmark**:
1. **M0 Primary Role:** The Hierarchical Historical Median model (M0) provides deterministic, auditable, and transparent bounds with explicit fallback tier tagging. It serves as the primary auditable baseline.
2. **Experimental ML Role:** Random Forest is retained under DEGRADE status as an experimental benchmark to evaluate nonlinear spatial-temporal gains. It will not replace M0 until multi-corridor data across all 31 October dates is extracted and validated.
