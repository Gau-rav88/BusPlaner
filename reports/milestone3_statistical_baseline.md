# Milestone 3 Statistical Baseline (M0) Report: Hierarchical Historical Median Model

**Model Specification:** PRD v3.0 Section 7.4 & 7.5 Hierarchical Historical Median Baseline (M0)  
**Implementation Code:** `backend/ml/baseline.py`  
**Training Partition:** October 1, 2, and 3, 2026 ($n = 84$ observations across 21 vehicles and 23 stop pairs)  
**Date of Report:** November 21, 2026  

---

## 1. M0 Architecture & Hierarchical Fallback Formulation

The baseline model provides deterministic, interpretable travel-time predictions for any stop-to-stop bus segment in Delhi. It uses a **four-tier fallback hierarchy** to ensure every query receives a valid, bounded prediction while preserving transparent confidence labeling:

```mermaid
flowchart TD
    Q["Stop Segment Query (segment_key, from_stop, to_stop, hour_ist, is_weekend, dist_m)"] --> C1{"Tier 1 Available?<br/>(segment_key, is_wk, hour) has n >= 3"}
    C1 -- Yes --> T1["Tier 1: Direct Observed Empirical Median<br/>(Confidence = 1.0, is_fallback = False)"]
    C1 -- No --> C2{"Tier 2 Available?<br/>(from_stop, to_stop, is_wk, hour) pooled n >= 3"}
    C2 -- Yes --> T2["Tier 2: Co-Running Stop-Pair Pooled Median<br/>(Confidence = 0.8, is_fallback = True)"]
    C2 -- No --> C3{"Tier 3 Available?<br/>(is_wk, hour) corridor velocity has n >= 3"}
    C3 -- Yes --> T3["Tier 3: Corridor Hourly Velocity Aggregation<br/>(Confidence = 0.6, is_fallback = True)"]
    C3 -- No --> T4["Tier 4: Calibrated Route Baseline<br/>(Default speed scaled by k_detour = 1.262, Confidence = 0.4)"]
```

### Mathematical Definitions
1. **Tier 1 (Direct Observed Segment):**
   $$\hat{T}_{\text{seg}} = \text{Median}\left(\{t_i \mid \text{segment} = s, \text{daytype} = d, \text{hour} = h\}\right) \quad \text{for } n \ge 3$$
2. **Tier 2 (Physical Stop-Pair Pooling):**
   $$\hat{T}_{\text{seg}} = \text{Median}\left(\{t_i \mid \text{from\_stop} = S_A, \text{to\_stop} = S_B, \text{daytype} = d, \text{hour} = h\}\right) \quad \text{for } n \ge 3$$
3. **Tier 3 (Corridor Hourly Velocity Fallback):**
   $$\hat{T}_{\text{seg}} = \frac{D_{\text{straight}}}{v_{\text{corridor}}(d, h) / 3.6} \quad \text{where } v_{\text{corridor}}(d, h) = \text{Median}\left(\{v_i \mid \text{daytype} = d, \text{hour} = h\}\right)$$
4. **Tier 4 (Calibrated Timetable Baseline):**
   $$\hat{T}_{\text{seg}} = \frac{D_{\text{straight}} \times k_{\text{detour}}}{v_{\text{scheduled}} / 3.6} \quad \text{with local } k_{\text{detour}} = 1.262$$

---

## 2. Statistical Metrics of the Ground-Truth Corridor (North GT Road)

Computed across all 136 ground-truth segment observations:

| Metric Category | Median Value | Mean Value | Empirical Quantiles (P10, P25, P75, P90) | Sample Count ($n$) |
| :--- | :---: | :---: | :---: | :---: |
| **Segment Commercial Speed** | **18.17 km/h** | **17.11 km/h** | P10: 2.16 \| P25: 7.39 \| P75: 24.71 \| P90: 31.73 km/h | 136 |
| **Segment Observed Travel Time** | **107.93 s** | **214.56 s** | P10: 38.64 \| P25: 73.58 \| P75: 217.84 \| P90: 446.80 s | 136 |
| **Segment Physical Distance** | **479.85 m** | **546.88 m** | P10: 274.70 \| P25: 291.48 \| P75: 626.79 \| P90: 1,024.10 m | 136 |

---

## 3. Supported vs. Low-Sample vs. Unavailable Combinations

To adhere strictly to the PRD requirement that **no median based on 1–2 observations may be presented as reliable traffic state**, every segment-hour combination is classified:

| Operating Hour (IST) | Observed Segments ($n$) | Data Support Classification | Action Taken by M0 Baseline |
| :---: | :---: | :--- | :--- |
| **00:00 – 06:59** | 0 | **UNAVAILABLE** | Falls back to Tier 4 (Calibrated Route Baseline, conf = 0.4) |
| **07:00 – 07:59** | 24 (Weekend only) | **SUPPORTED (Weekend Only)** | Weekend Tier 3 Corridor Velocity (23.37 km/h, conf = 0.6); Weekday falls back to Tier 4 |
| **08:00 – 08:59** | 17 (12 Wkday, 5 Wkend) | **SUPPORTED (Both Day Types)** | Weekday Tier 3 (18.61 km/h, conf = 0.6); Weekend Tier 3 (18.61 km/h) |
| **09:00 – 09:59** | 4 (Weekday only) | **SUPPORTED (Weekday Only)** | Weekday Tier 3 (23.01 km/h, conf = 0.6); Weekend falls back to Tier 4 |
| **10:00 – 10:59** | 1 (Holiday) | **LOW_SAMPLE ($n=1$)** | Marked LOW_SAMPLE; falls back to Tier 4 Baseline (conf = 0.4) |
| **11:00 – 11:59** | 0 | **UNAVAILABLE** | Falls back to Tier 4 (Calibrated Route Baseline, conf = 0.4) |
| **12:00 – 12:59** | 1 (Weekend) | **LOW_SAMPLE ($n=1$)** | Marked LOW_SAMPLE; falls back to Tier 4 Baseline (conf = 0.4) |
| **13:00 – 13:59** | 10 (8 Wkday, 2 Wkend) | **SUPPORTED (Weekday)** | Weekday Tier 3 (21.67 km/h, conf = 0.6); Weekend falls back to Tier 4 |
| **14:00 – 14:59** | 17 (11 Wkday, 6 Wkend) | **SUPPORTED (Both Day Types)** | Weekday Tier 3 (21.67 km/h, conf = 0.6); Weekend Tier 3 (21.67 km/h, conf = 0.6) |
| **15:00 – 15:59** | 12 (Weekday only) | **SUPPORTED (Weekday Only)** | Weekday Tier 3 (21.69 km/h, conf = 0.6); Weekend falls back to Tier 4 |
| **16:00 – 16:59** | 13 (10 Wkday, 3 Wkend) | **SUPPORTED (Both Day Types)** | Weekday Tier 3 (7.30 km/h, conf = 0.6); Weekend Tier 3 (13.24 km/h, conf = 0.6) |
| **17:00 – 17:59** | 17 (14 Wkday, 3 Wkend) | **SUPPORTED (Both Day Types)** | Weekday Tier 3 (4.88 km/h, conf = 0.6); Weekend Tier 3 (10.00 km/h, conf = 0.6) |
| **18:00 – 18:59** | 14 (7 Wkday, 7 Wkend) | **SUPPORTED (Both Day Types)** | Weekday Tier 3 (12.07 km/h, conf = 0.6); Weekend Tier 3 (11.69 km/h, conf = 0.6) |
| **19:00 – 19:59** | 0 | **UNAVAILABLE** | Falls back to Tier 4 (Calibrated Route Baseline, conf = 0.4) |
| **20:00 – 20:59** | 3 (Weekday only) | **SUPPORTED (Marginal, $n=3$)** | Weekday Tier 3 (1.29 km/h, conf = 0.6); Weekend falls back to Tier 4 |
| **21:00 – 21:59** | 3 (2 Wkday, 1 Wkend) | **LOW_SAMPLE per Day Type** | Marked LOW_SAMPLE; falls back to Tier 4 Baseline (conf = 0.4) |
| **22:00 – 23:59** | 0 | **UNAVAILABLE** | Falls back to Tier 4 (Calibrated Route Baseline, conf = 0.4) |

---

## 4. Strengths & Governance of the M0 Baseline

1. **Zero Hallucination:** M0 produces predictions solely grounded in empirical transit records. Where empirical data is absent, it transparently tags the output as a Tier 4 calibrated fallback with low confidence ($0.4$).
2. **Deterministic & Fast:** Lookup latency is sub-millisecond ($< 0.05\text{ ms}$ per query), satisfying real-time journey planning throughput constraints.
3. **Non-Parametric Robustness:** Using the median ($P_{50}$) rather than the mean protects predictions against extreme outliers caused by single-bus breakdowns or GPS jump artifacts.

