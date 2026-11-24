# Milestone 8: Historical Time-of-Day Traffic Profiles Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Phase:** Milestone 8 — Empirical Traffic Profiles  
**Operational Status:** **DEGRADE**  
**Evidence Scope:** 136 observed segments, 5 service dates, 31 vehicles, 21 physical stop-pairs, predominantly Route 1598 (North GT Road)  
**Date:** November 2026  

---

## 1. Executive Summary

Milestone 8 built an empirical, evidence-backed time-of-day traffic profile engine (`backend/analytics/time_profiles.py`) using only the 136 validated consecutive-stop observations across the five processed pilot service dates (October 1, 2, 3, 4, 7, 2026).

### Adherence to PRD v3.0 Constraints:
1. **Zero Data Invention:** Unobserved time bins (e.g. night hours, midday gaps) are strictly classified as `UNAVAILABLE`. No synthetic values, cubic splines, or linear interpolations are used to fill missing bins.
2. **No Global Detour Scaling:** The empirical detour factor ($k = 1.262$) computed for Route 1598 is **not applied globally** to other Delhi routes or unobserved corridors.
3. **Rigorous Statistical Metrics:** For every profile bin, sample size, distinct service dates, distinct vehicles, quartiles ($p_{25}, p_{50}, p_{75}$), IQR, mean, and standard deviation are reported.
4. **No Delhi-Wide Generalization:** All empirical profiles are strictly scoped to the North GT Road pilot corridor.

---

## 2. Dataset Scope & Hourly Observation Distribution

The 136 ground-truth segment observations are distributed across 13 distinct hours in Indian Standard Time (IST):

| Hour Bin (IST) | Period of Day | Observation Count | Distinct Dates | Distinct Vehicles | Mean Travel Time (s) | Median Travel Time (s) | Std Dev (s) | Mean Speed (km/h) | Median Speed (km/h) | Status |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **00:00 - 06:59** | Late Night / Early Morning | 0 | 0 | 0 | — | — | — | — | — | `UNAVAILABLE` |
| **07:00 - 07:59** | Morning Early Peak | 24 | 5 | 8 | 185.12 | 102.50 | 258.42 | 18.42 | 17.50 | `OBSERVED` |
| **08:00 - 08:59** | Morning Peak | 17 | 4 | 5 | 231.40 | 115.20 | 312.15 | 16.10 | 15.80 | `OBSERVED` |
| **09:00 - 09:59** | Late Morning Peak | 4 | 2 | 2 | 265.80 | 198.40 | 184.20 | 14.50 | 14.20 | `OBSERVED` |
| **10:00 - 10:59** | Midday Shoulder | 1 | 1 | 1 | 98.40 | 98.40 | — | 18.20 | 18.20 | `OBSERVED` |
| **11:00 - 11:59** | Midday Gap | 0 | 0 | 0 | — | — | — | — | — | `UNAVAILABLE` |
| **12:00 - 12:59** | Afternoon Early | 1 | 1 | 1 | 86.40 | 86.40 | — | 19.50 | 19.50 | `OBSERVED` |
| **13:00 - 13:59** | Afternoon Early | 10 | 3 | 4 | 192.50 | 105.80 | 240.10 | 17.80 | 17.20 | `OBSERVED` |
| **14:00 - 14:59** | Afternoon Off-Peak | 17 | 4 | 5 | 198.60 | 99.40 | 265.40 | 18.10 | 17.60 | `OBSERVED` |
| **15:00 - 15:59** | Afternoon Shoulder | 12 | 4 | 4 | 215.30 | 110.60 | 275.80 | 16.90 | 16.50 | `OBSERVED` |
| **16:00 - 16:59** | Evening Early Peak | 13 | 4 | 4 | 245.80 | 122.40 | 320.10 | 15.60 | 15.10 | `OBSERVED` |
| **17:00 - 17:59** | Evening Peak | 17 | 5 | 5 | 278.40 | 135.80 | 358.90 | 14.20 | 13.80 | `OBSERVED` |
| **18:00 - 18:59** | Evening Peak | 14 | 4 | 5 | 260.10 | 128.50 | 335.40 | 14.80 | 14.50 | `OBSERVED` |
| **19:00 - 19:59** | Evening Gap | 0 | 0 | 0 | — | — | — | — | — | `UNAVAILABLE` |
| **20:00 - 20:59** | Night Shoulder | 3 | 2 | 2 | 142.50 | 95.20 | 85.10 | 20.40 | 21.00 | `OBSERVED` |
| **21:00 - 21:59** | Night | 3 | 2 | 2 | 135.20 | 89.60 | 78.40 | 21.20 | 22.10 | `OBSERVED` |
| **22:00 - 23:59** | Late Night | 0 | 0 | 0 | — | — | — | — | — | `UNAVAILABLE` |

### Key Temporal Takeaways:
- **Observed Hours:** 13 of 24 hours (54.17% temporal coverage).
- **Unobserved Hours:** 11 of 24 hours (45.83% temporal gap).
- **Congestion Peaks:** Lowest speeds and highest segment travel times occur during the evening peak (17:00 - 18:59, median speed 13.8 - 14.5 km/h) and morning peak (08:00 - 09:59, median speed 14.2 - 15.8 km/h).
- **Free-Flow Night:** Highest speeds occur late evening (20:00 - 21:59, median speed 21.0 - 22.1 km/h).

---

## 3. High-Density Stop-Pair Profiles (Route 1598)

Below are the detailed empirical profiles for the top 10 most observed stop pairs along Route 1598 on North GT Road:

| Origin Stop | Destination Stop | Distance (m) | Samples | Dates | Vehicles | Median (s) | Mean (s) | Std Dev (s) | 25th % (s) | 75th % (s) | IQR (s) | Min (s) | Max (s) | Median Speed (km/h) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **New Sabzi Mandi (240)** | **Adarsh Nagar (241)** | 358.2 | 12 | 5 | 12 | 103.04 | 131.93 | 118.76 | 72.10 | 128.45 | 56.35 | 43.12 | 485.84 | 12.52 |
| **Adarsh Nagar (241)** | **Sarai Peepal Thala (242)** | 632.1 | 13 | 5 | 13 | 304.06 | 584.95 | 578.53 | 145.20 | 780.12 | 634.92 | 64.32 | 1779.14 | 7.48 |
| **Sarai Peepal Thala (242)** | **Mahindra Park (243)** | 224.5 | 11 | 4 | 11 | 73.80 | 131.63 | 132.67 | 45.10 | 165.20 | 120.10 | 21.45 | 437.59 | 10.95 |
| **Mahindra Park (243)** | **Jahangir Puri GT Rd (244)** | 480.3 | 10 | 4 | 10 | 160.20 | 298.70 | 258.73 | 112.40 | 385.10 | 272.70 | 86.65 | 792.03 | 10.79 |
| **Jahangir Puri GT Rd (244)**| **Jahangir Puri Metro (245)**| 312.4 | 10 | 4 | 10 | 62.37 | 123.62 | 119.96 | 41.20 | 152.10 | 110.90 | 27.64 | 377.87 | 18.03 |
| **Jahangir Puri Metro (245)**| **GTK Depot (246)** | 694.0 | 15 | 5 | 15 | 160.24 | 376.99 | 438.07 | 98.40 | 420.50 | 322.10 | 66.03 | 1267.09 | 15.59 |
| **GTK Depot (246)** | **Mukarba Chowk (247)** | 412.8 | 11 | 5 | 11 | 78.62 | 137.71 | 122.61 | 64.20 | 148.50 | 84.30 | 58.16 | 395.68 | 18.90 |
| **Mukarba Chowk (247)** | **Sanjay Gandhi Tpt (248)** | 490.1 | 9 | 4 | 8 | 99.95 | 140.75 | 79.43 | 82.10 | 185.40 | 103.30 | 64.46 | 249.52 | 17.65 |
| **Sanjay Gandhi Tpt (248)** | **Libas Pur GT Rd (249)** | 820.5 | 6 | 4 | 6 | 214.66 | 216.96 | 33.13 | 192.40 | 238.10 | 45.70 | 185.05 | 252.06 | 13.76 |
| **Libas Pur GT Rd (249)** | **Swaroop Nagar GT (250)** | 395.2 | 5 | 3 | 5 | 86.97 | 91.13 | 20.69 | 75.40 | 105.20 | 29.80 | 63.38 | 119.93 | 16.36 |

---

## 4. Bottleneck Identification: Adarsh Nagar to Sarai Peepal Thala

The empirical profile highlights a severe, recurring traffic bottleneck on North GT Road between **Stop 241 (Adarsh Nagar)** and **Stop 242 (Sarai Peepal Thala)**:
- Distance: 632.1 meters.
- Observations: 13 segments across all 5 dates and 13 distinct vehicles.
- Median Duration: 304.06 seconds (~5.1 minutes).
- Mean Duration: 584.95 seconds (~9.7 minutes).
- Maximum Observed Delay: **1,779.14 seconds (~29.7 minutes)** on Oct 1 during evening congestion.
- Interquartile Range (IQR): 634.92 seconds, reflecting massive day-to-day variance during peak hours.
- Effective Travel Speed: Median 7.48 km/h, dropping to < 2.0 km/h during heavy congestion.

---

## 5. Machine-Readable Profile Export

All 624 stop-pair hourly bins, 72 route hourly bins, and 24 corridor hourly bins were compiled and exported to:
- [`data/processed/historical_time_profiles.json`](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/processed/historical_time_profiles.json)

---

## 6. Audit Conclusion

The historical time profile engine strictly obeys PRD v3.0 rules. Unobserved time bins are faithfully marked `UNAVAILABLE`, data variance is fully disclosed through quartiles and standard deviation, and observations remain bound to the verified North GT Road corridor under **DEGRADE** operational status.

