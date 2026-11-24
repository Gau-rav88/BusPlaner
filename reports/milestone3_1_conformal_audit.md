# Milestone 3.1 Conformal Prediction Audit Report (Revised)

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 3.1.1 – Statistical Audit Corrections  
**Status:** **AUDITED & VERIFIED (DEGRADE STATUS)**  
**Date:** November 21, 2026  
**Artifact Reference:** `data/processed/milestone3_1_audit_metrics.json`  

---

## 1. Executive Summary & Audit Objective

In Milestone 3.0, Inductive Split-Conformal Prediction was introduced in `backend/ml/conformal.py` to provide distribution-free, non-parametric prediction intervals for transit travel times. The initial report documented:
- Conformal Radius ($q$): **349.10 seconds**
- Average Prediction Interval Width: **532.03 seconds**

This revision addresses the Milestone 3.1.1 audit requirements:
1. Formally resolve the mathematical discrepancy between radius $q$ and average interval width.
2. Inspect target values and verify whether the 5.0-second lower-bound clipping impacts empirical test coverage.
3. Clarify that coverage confidence intervals are purely illustrative under independence assumptions, explicitly acknowledging that clustered observations violate ordinary independent Bernoulli trials.
4. Recommend a rigorous clustered evaluation strategy for future multi-date validation.
5. Preserve the sound existing implementation in `backend/ml/conformal.py`.

---

## 2. Mathematical Resolution of the Width Discrepancy

### 2.1 The Code Implementation
Inspection of `backend/ml/conformal.py` (lines 35–42) reveals the prediction interval generation logic:

```python
def predict_intervals(self, y_pred_s: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Produce lower and upper bounds [pred - q, pred + q] (clipped at >= 5s)."""
    if not self.is_calibrated:
        raise RuntimeError("Calibrator must be fitted before predict_intervals")
    lower = np.maximum(y_pred_s - self.conformal_radius, 5.0)
    upper = y_pred_s + self.conformal_radius
    return lower, upper
```

### 2.2 Mathematical Cause of Truncation
1. **Theoretical Unclipped Interval:**  
   If intervals were unconstrained, bounds would be:
   $$\mathcal{C}_{\text{unclipped}}(X) = [\hat{y} - q, \hat{y} + q]$$
   The theoretical width would be constant across all predictions:
   $$\text{Width}_{\text{unclipped}} = (\hat{y} + q) - (\hat{y} - q) = 2q = 2 \times 349.10 = 698.20 \text{ seconds}$$

2. **Physical Boundary Enforcement:**  
   Transit segment travel time is strictly positive ($t > 0$). In `conformal.py`, a physical non-negativity constraint clips the lower bound at a minimum threshold of $5.0\text{ seconds}$:
   $$\text{lower} = \max(\hat{y} - q, 5.0)$$
   $$\text{upper} = \hat{y} + q$$

3. **Width Under Lower-Bound Truncation:**  
   Whenever $\hat{y} - q < 5.0$ (or equivalently, $\hat{y} < q + 5.0 = 354.10\text{ seconds}$), the lower bound collapses to $5.0\text{s}$. The effective interval width becomes:
   $$\text{Width}_{\text{clipped}} = (\hat{y} + q) - 5.0 = \hat{y} + 344.10 \text{ seconds}$$

4. **Exact Breakdown across the 30 Test Predictions:**  
   - Along the North GT Road corridor, typical link travel times range between 25 and 260 seconds under non-congested conditions.
   - Of the 30 held-out test predictions on October 7, **25 predictions (83.33%) had point predictions $\hat{y} < 354.10\text{ seconds}$**.
   - For these 25 predictions, the lower bound was clipped to $5.0\text{s}$, producing widths ranging from $364.26\text{s}$ to $589.65\text{s}$ (mean $= 498.80\text{s}$).
   - Only **5 predictions (16.67%) had $\hat{y} \ge 354.10\text{ seconds}$**, maintaining the full unclipped width of $698.20\text{s}$.
   - The overall average interval width is:
   $$\overline{\text{Width}} = \frac{25 \times 498.80\text{s} + 5 \times 698.20\text{s}}{30} = 532.03 \text{ seconds}$$

| Metric | Unclipped Interval | Implemented Clipped Interval | Difference |
| :--- | :---: | :---: | :---: |
| **Formula** | $[\hat{y} - q, \hat{y} + q]$ | $[\max(\hat{y} - q, 5.0), \hat{y} + q]$ | Truncation at $5.0\text{s}$ |
| **Mean Width** | $698.20\text{ s}$ | $532.03\text{ s}$ | $-166.17\text{ s}$ |
| **Median Width** | $698.20\text{ s}$ | $539.70\text{ s}$ | $-158.50\text{ s}$ |
| **Minimum Width** | $698.20\text{ s}$ | $364.26\text{ s}$ | $-333.94\text{ s}$ |
| **Maximum Width** | $698.20\text{ s}$ | $698.20\text{ s}$ | $0.00\text{ s}$ |
| **Clipped Observations** | $0 / 30$ ($0.0\%$) | $25 / 30$ ($83.3\%$) | $+25$ observations |

---

## 3. Conformal Lower-Bound Verification & Target Distribution

An exhaustive audit of all target travel times across the dataset was performed to determine whether any ground-truth observation fell near or below the 5.0-second clipping boundary.

### 3.1 Empirical Target Distribution
```
+--------------------------------------------------------------------------------------------------+
| Partition              | Sample Count ($n$) | Min Actual Time ($s$) | 1st Percentile ($s$) | Median Time ($s$) |
+--------------------------------------------------------------------------------------------------+
| Entire Dataset (Global)| 136                | 21.45                 | 27.93                | 107.93            |
| Training (Oct 1–3)     | 84                 | 32.56                 | 35.80                | 113.68            |
| Validation (Oct 4)     | 22                 | 27.64                 | 29.80                | 100.28            |
| Test (Oct 7)           | 30                 | 21.45                 | 23.95                | 100.32            |
+--------------------------------------------------------------------------------------------------+
```

### 3.2 Verification of Coverage Impact
- **Are any actual segment times below 5.0 seconds?**  
  **No.** Across all 136 observations, the minimum actual segment time is **$21.45\text{ seconds}$**. Zero actual segment times fall below 5.0 seconds.
- **Does clipping at 5.0s change empirical test coverage?**  
  **No.** For every test observation $i$:
  $$y_{\text{true}, i} \ge 21.45\text{s} > 5.0\text{s}$$
  - For unclipped intervals where $\hat{y}_i - q < 5.0\text{s}$ (often negative, e.g. $-199.1\text{s}$), $y_{\text{true}, i} \ge \hat{y}_i - q$ is automatically satisfied.
  - When clipped to $5.0\text{s}$, because $y_{\text{true}, i} \ge 21.45\text{s} > 5.0\text{s}$, the condition $y_{\text{true}, i} \ge \text{lower}_i$ remains **100% satisfied**.
  - **Empirical Coverage Identity:**
    - Unclipped Coverage: **26 / 30 (86.67%)**
    - Clipped Coverage: **26 / 30 (86.67%)**
    - Difference in Coverage Status: **Exactly 0 observations.**

> [!NOTE]
> The 5.0-second lower-bound truncation removes unphysical negative travel times without altering the empirical coverage status of any prediction. The implementation in `backend/ml/conformal.py` is mathematically and physically sound and is preserved without modification.

---

## 4. Test Set Coverage & Outside Observations Audit ($n_{\text{test}} = 30$)

### 4.1 Summary of Test Evaluation
- **Covered Observations:** 26 / 30 (**86.67%**)
- **Miscoverage Count:** 4 / 30 (**13.33%**)

### 4.2 Exhaustive Breakdown of the 4 Outside Observations

```
+------------------------------------------------------------------------------------------------------------------+
| Idx | Segment Key           | Vehicle ID  | Hour | Actual (s) | Pred M0 (s)| Lower (s) | Upper (s) | Miss Type   |
+------------------------------------------------------------------------------------------------------------------+
| 7   | 1598_dir0_pat0_seq9   | DL1PD7932   | 08   | 252.06     | 674.87     | 325.77    | 1023.97   | BELOW_LOWER |
| 12  | 1598_dir0_pat0_seq9   | DL1PD5198   | 09   | 239.02     | 674.87     | 325.77    | 1023.97   | BELOW_LOWER |
| 22  | 1598_dir0_pat0_seq2   | DL51EV4080  | 17   | 1643.58    | 595.85     | 246.76    | 944.95    | ABOVE_UPPER |
| 29  | 1598_dir0_pat0_seq9   | DL51EV4080  | 18   | 249.59     | 674.87     | 325.77    | 1023.97   | BELOW_LOWER |
+------------------------------------------------------------------------------------------------------------------+
```

### 4.3 Root Cause Analysis
1. **Link `seq9` Over-Prediction (Idx 7, 12, 29):**  
   Link `1598_dir0_pat0_seq9` ($1634.72\text{m}$) had only 2 training observations, failing the Tier 1 threshold ($n \ge 3$). M0 fell back to **Tier 4 Route Baseline** ($674.87\text{s}$, derived from corridor congested speeds $\approx 11\text{ km/h} \times 1.262$). Because `seq9` is a free-flowing arterial section ($24\text{ km/h}$, $239\text{--}252\text{s}$), M0 over-predicted travel time by $> 420\text{s}$, shifting the lower bound to $325.77\text{s}$. All 3 test traversals fell below this lower bound.
2. **Evening Gridlock Standstill (Idx 22):**  
   At 17:00 IST on October 7, heavy peak congestion on `seq2` caused a 27.4-minute crawl ($1643.58\text{s}$), exceeding the upper bound of $944.95\text{s}$.

---

## 5. Coverage Uncertainty & Clustered Variance

### 5.1 Illustrative Independence Bounds
Under an ordinary independent Bernoulli trials assumption:
- **Sample Proportion:** $\hat{p} = 26 / 30 = 86.67\%$
- **Illustrative Clopper-Pearson 95% CI:** **$[69.28\%, 96.24\%]$**
- **Illustrative Binomial Test:** $H_0: p = 0.90 \implies p\text{-value} = 0.61$.

> [!WARNING]
> **Ordinary Independence Assumption Violated:**
> The Clopper-Pearson interval and $p$-value are strictly illustrative. In transit operations, observations are **clustered**:
> 1. Consecutive stop segments traversed by the same vehicle (`DL51EV4080` had 9 segments on Oct 7) share common driver behavior and vehicle performance.
> 2. Buses traversing the same physical corridor at the same time share common signal cycles and congestion waves.
> 3. Temporal events (such as the October 7 GPS feed outage and evening peak gridlock) shock all corridor observations simultaneously.
> 
> Because clustered variance significantly exceeds independent binomial variance, **90% conformal coverage CANNOT be claimed as statistically demonstrated** from this 30-observation test sample.

### 5.2 Recommended Clustered Evaluation Strategy for Future Validation
To establish statistically defensible conformal guarantees across the full October historical dataset, the following clustered evaluation framework is recommended:
1. **Date-Clustered Cross-Validation:** Group observations into 31 daily clusters. Implement Leave-One-Date-Out (LODO) evaluation so validation residuals and test observations never share calendar dates.
2. **Vehicle-Run Block Conformal Prediction:** Calibrate non-conformity scores at the level of complete vehicle trips (trajectories) rather than isolated individual segments, ensuring that within-trip correlation does not inflate empirical coverage estimates.
3. **Cluster-Robust Variance Estimation:** Report confidence intervals adjusted for two-way clustering by $(\text{service\_date}, \text{segment\_key})$ using sandwich variance estimators.
