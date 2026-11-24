# Milestone 3 Model Comparison Report: Statistical Baseline (M0) vs. Machine Learning Candidates (M1, M2)

**Evaluated Models:**
- **M0:** Hierarchical Historical Median Baseline (PRD Section 7.4)
- **M1:** Regularized Linear Ridge Regression on $\log(\text{segment\_time\_s})$ (PRD Section 7.5)
- **M2:** Non-Linear Random Forest Regressor on $\log(\text{segment\_time\_s})$ (PRD Section 7.5)
- *(M3: XGBoost — excluded because XGBoost library is not installed in the environment, and a high-capacity gradient booster is not justified on 84 training rows)*

**Evaluation Partition:** Held-Out Historical Test Date: **October 7, 2026** ($n = 30$ independent observations)  
**Evaluation Target:** Segment Running Travel Time in seconds ($\tau_{\text{seg}}$)  
**Diagnostic Visualizations:**  
- [fig9_model_predictions_vs_actual.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig9_model_predictions_vs_actual.png)  
- [fig10_error_distribution.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig10_error_distribution.png)  
**Date of Report:** November 21, 2026  

---

## 1. Comparative Performance on Held-Out Test Data

To guarantee zero data leakage, all models were trained strictly on **October 1–3, 2026** ($n = 84$ observations), with out-of-fold historical feature generation. They were evaluated on the held-out **October 7, 2026** test partition ($n = 30$ observations):

| Performance Metric (PRD Section 9.2) | M0: Hierarchical Median Baseline | M1: Ridge Regression ($\alpha=10$) | M2: Random Forest ($d=4, n=50$) | Best Model | Relative Improvement Over M0 (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Mean Absolute Error (MAE)** | **146.55 s** | 142.64 s | **122.94 s** | **M2 (Random Forest)** | **+16.11% MAE Reduction** |
| **Root Mean Squared Error (RMSE)** | 250.91 s | 246.07 s | **221.01 s** | **M2 (Random Forest)** | **+11.92% RMSE Reduction** |
| **Median Absolute Error (MedAE)** | 87.44 s | 88.31 s | **68.29 s** | **M2 (Random Forest)** | **+21.90% MedAE Reduction** |
| **Mean Signed Error (Bias)** | +67.00 s (over-predicts) | +60.45 s | **+47.48 s** | **M2 (Random Forest)** | **+29.13% Lower Bias** |
| **Mean Absolute Percentage Error (MAPE)** | **100.28%** | 125.10% | 101.90% | **M0 (Baseline)** | M0 has lowest percentage error |
| **Median Absolute Percentage Error (MedAPE)** | 92.99% | 85.76% | **51.64%** | **M2 (Random Forest)** | **+41.35% MedAPE Reduction** |
| **Predictions within 10% of Actual** | 0.00% | 6.67% | **16.67%** | **M2 (Random Forest)** | +16.67 percentage points |
| **Predictions within 20% of Actual** | 10.00% | 6.67% | **26.67%** | **M2 (Random Forest)** | +16.67 percentage points |

---

## 2. Model-by-Model Analysis

### Model M0: Hierarchical Historical Median Baseline
- **Role:** Primary non-parametric baseline and system fallback.
- **Test Performance:** MAE = 146.55 s, MedAE = 87.44 s, Bias = +67.00 s.
- **Characteristics:** Highly robust against extreme outliers. On the held-out test date, because individual stop pairs at specific hours had fewer than 3 training samples, M0 appropriately routed 23.3% of queries to Tier 3 (corridor hourly velocity) and 76.7% to Tier 4 (calibrated route baseline).
- **Residual Distribution:** Exhibits a positive bias (+67s) because October 7 had moderate traffic flow during midday hours compared to the severe gridlock observed on October 1.

### Model M1: Regularized Ridge Regression
- **Role:** Parametric linear model on log travel time.
- **Test Performance:** MAE = 142.64 s (2.67% improvement over M0), RMSE = 246.07 s, Bias = +60.45 s.
- **Characteristics:** Ridge regression captures the continuous relationship between segment distance and log travel time, but its linear assumption cannot model the sharp non-linear velocity drops at cloverleaf flyover bottlenecks (Mukarba Chowk). Its MAPE rose to 125.10% on short segments.

### Model M2: Random Forest Regressor
- **Role:** Non-linear decision tree ensemble on log travel time.
- **Test Performance:** MAE = **122.94 s** (16.11% improvement over M0), MedAE = **68.29 s**, MedAPE = **51.64%**.
- **Characteristics:** Random Forest successfully partitions observations by distance thresholds and time-of-day features. It reduced large over-predictions on long tangent segments (e.g. Mukarba Chowk $\to$ Sanjay Gandhi Transport Nagar, reducing MAE from 427.9s to 61.9s).
- **PRD Gate Target Met:** PRD Section 7.6 states a target of *"at least 3% relative MAE improvement over M0 before selecting a more complex model."* M2 achieves **16.11% relative MAE improvement**, surpassing the 3% target.

---

## 3. Does Machine Learning Genuinely Improve on M0?

A balanced scientific evaluation:

1. **Empirical Improvement:** Yes, on the held-out chronological test date, Random Forest (M2) reduces MAE by **23.6 seconds** (from 146.55s to 122.94s) and cuts Median Absolute Percentage Error in half (from 92.99% to 51.64%).
2. **Sample-Size Caveat:** The test set consists of **30 observations from a single service date (October 7)**. While the whole-date split eliminates leakage, 30 observations cannot prove statistical generalization across all weather, seasonal, and holiday scenarios in Delhi.
3. **Engineering Synthesis:** 
   - **Ship M0 as the Primary Production Baseline:** The Hierarchical Historical Median model must remain the default backbone because of its guaranteed monotonicity, sub-millisecond lookup latency, and zero dependency on external inference runtimes.
   - **Retain M2 as an Experimental Scoring Option:** M2 can be selectively applied on verified corridor segments where feature completeness is assured, while all unaligned routes fall back strictly to M0 Tiers 3 and 4.

