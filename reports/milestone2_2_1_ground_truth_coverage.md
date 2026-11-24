# Milestone 2.2.1 Ground-Truth Vehicle, Route & Hourly Coverage Audit Report

**Service Dates Analyzed:** October 1, 2, 3, 4, and 7, 2026 (`2026-10-01` to `2026-10-07`, Pilot Subset)  
**Underlying Data Source:** `data/processed/stop_crossings/service_date=*/observed_segments.parquet`  
**Pipeline Modules:** `backend/core/map_matching.py`, `backend/core/stop_crossings.py`, DuckDB  
**Audit Artifact:** `data/processed/milestone2_2_1_audit_metrics.json`  
**Date of Audit:** November 21, 2026  

---

## 1. Global Entity Audit (Direct Combined Calculation)

All metrics below are calculated directly across the union of all 5 underlying daily Parquet partitions (`observed_segments.parquet` and `stop_crossings.parquet`) using DuckDB, ensuring strict global deduplication:

| Entity Category | True Globally Distinct Count | Description |
| :--- | :---: | :--- |
| **Total Consecutive-Stop Observed Segments** | **136** | Verified physical $(S_k \to S_{k+1})$ running instances |
| **Total Valid Stop Crossings** | **199** | Interpolated arrivals bracketed by pings ($\Delta t \le 120\text{s}$, $\Delta s \le 600\text{m}$) |
| **Globally Distinct Active Vehicles** | **31** | Unique bus registration IDs appearing in ground truth |
| **Globally Distinct Physical Stop Pairs** | **26** | Unique sequential stop-to-stop links on North GT Road |
| **Globally Distinct Routes with Valid Segments** | **3** | Routes with $\ge 1$ verified consecutive stop-pair run |
| **Globally Distinct Directional Route Patterns** | **3** | Unique GTFS pattern trajectories represented |

---

## 2. Route List Reconciliation & Script Discrepancy Diagnosis

In earlier milestone reports, the list of evaluated routes showed apparent discrepancies between iterations:
- In Milestone 2 pilot tables: Routes **1616** (`126A`) and **1547** (`127`) were listed.
- In Milestone 2.1 tables: Routes **1616** and **1547** disappeared, while Routes **1407** (`427`) and **1714** (`611D`) appeared.
- In Milestone 2.2 multi-day ground truth: Route **1445** appeared with 11 segments, Route **1657** with 1 segment, and Route **1598** with 124 segments.

### Root Cause Audit
Inspection of the underlying source code revealed the exact origin of these variations:

1. **Milestone 2 Exploratory Pilot:**
   Preliminary scripts evaluated five legacy routes: `1598`, `1616`, `1657`, `1547`, and `1515`.
2. **Milestone 2.1 Geographic Expansion:**
   In [scripts/run_expansion_m2_1.py](file:///Users/gauravchauhan/Downloads/delhi_hacks/scripts/run_expansion_m2_1.py), the `EXPANDED_CORRIDORS` dictionary was rewritten to enforce a ten-corridor geographic spread across Delhi NCR. To include South Delhi, the author manually replaced short North feeders (`1616` and `1547`) with South Ring Road corridors: Route `1407` (427, South Delhi) and Route `1714` (611D, Dhaula Kuan to Lajpat Nagar).
3. **Milestone 2.2 Batch Processing:**
   In [scripts/process_historical_batch.py](file:///Users/gauravchauhan/Downloads/delhi_hacks/scripts/process_historical_batch.py), `EXPANDED_CORRIDORS` paired Route `1616` with its co-running physical sibling **`1445`** (`126AUP` Badli to Azadpur). On October 2 and 3, vehicles reporting `1445` traversed the common North GT Road corridor between New Sabzi Mandi and GTK Depot, producing 11 valid consecutive stop segments.

---

## 3. Segment Yields by Date, Route, Vehicle, and Stop Pair

### A. Observed Segments by Service Date
| Service Date | Day Name | Operating Regime | Valid Observed Segments | Share of Total |
| :---: | :---: | :--- | :---: | :---: |
| **2026-10-01** | Thu | Regular Weekday | 34 | 25.00% |
| **2026-10-02** | Fri | Gandhi Jayanti (Public Holiday) | 20 | 14.71% |
| **2026-10-03** | Sat | Weekend (High Commercial) | 30 | 22.06% |
| **2026-10-04** | Sun | Weekend (Free Flow) | 22 | 16.18% |
| **2026-10-07** | Wed | Weekday (Truncated by Outage) | 30 | 22.06% |
| **Total** | | **All 5 Dates** | **136** | **100.00%** |

### B. Observed Segments by Route
| Route ID | Route Name | Operating Zone | Observed Segments | Share of Total |
| :---: | :--- | :--- | :---: | :---: |
| **1598** | 129AUP (Azadpur <-> Jhingola) | North GT Road (NH-44) | **124** | 91.18% |
| **1445** | 126AUP (Badli <-> Azadpur) | North GT Road / Badli | **11** | 8.09% |
| **1657** | 103STLUP (Old Delhi <-> Narela) | North Arterial Corridor | **1** | 0.74% |
| **Total** | | | **136** | **100.00%** |

### C. Top Active Vehicles in Ground Truth
| Vehicle ID | Fuel / Fleet Type | Total Observed Segments | Operating Dates Observed |
| :---: | :--- | :---: | :--- |
| `DL51EV3788` | Electric Low-Floor DTC | 12 | 2026-10-03, 2026-10-04 |
| `DL51EV8634` | Electric Low-Floor DTC | 9 | 2026-10-01, 2026-10-03 |
| `DL51EV3776` | Electric Low-Floor DTC | 9 | 2026-10-02, 2026-10-03 |
| `DL51EV4080` | Electric Low-Floor DTC | 9 | 2026-10-07 |
| `DL51EV3533` | Electric Low-Floor DTC | 8 | 2026-10-03, 2026-10-04 |
| `DL51EV3114` | Electric Low-Floor DTC | 7 | 2026-10-02 |
| `DL51EV3618` | Electric Low-Floor DTC | 6 | 2026-10-01 |
| `DL51EV3761` | Electric Low-Floor DTC | 6 | 2026-10-01 |
| `DL51EV3524` | Electric Low-Floor DTC | 6 | 2026-10-03 |
| `DL1PD5209` | Conventional CNG DTC | 6 | 2026-10-04 |
| *Other (21 buses)*| Mixed Fleet | 48 | Distributed across all dates |
| **Total (31 buses)**| | **136** | |

### D. Complete Physical Stop-Pair Breakdown (All 26 Stop Pairs)
| Rank | Segment Key | Origin Stop ($S_k$) | Destination Stop ($S_{k+1}$) | Stop Distance | Observed Count |
| :---: | :--- | :--- | :--- | :---: | :---: |
| 1 | `1598_dir0_pat0_seq6` | Jahangir Puri Metro Station | GTK Depot | 518.9 m | **15** |
| 2 | `1598_dir0_pat0_seq2` | Adarsh Nagar / Bharola Village | Sarai Peepal Thala | 626.8 m | **13** |
| 3 | `1598_dir0_pat0_seq1` | New Sabzi Mandi | Adarsh Nagar / Bharola Village | 274.7 m | **12** |
| 4 | `1598_dir0_pat0_seq3` | Sarai Peepal Thala | Mahindra Park | 156.6 m | **11** |
| 5 | `1598_dir0_pat0_seq7` | GTK Depot | Mukarba Chowk | 474.5 m | **11** |
| 6 | `1598_dir0_pat0_seq4` | Mahindra Park | Jahangir Puri GT Road | 479.8 m | **10** |
| 7 | `1598_dir0_pat0_seq5` | Jahangir Puri GT Road | Jahangir Puri Metro Station | 291.5 m | **10** |
| 8 | `1598_dir0_pat0_seq8` | Mukarba Chowk | Sanjay Gandhi Transport Nagar | 434.7 m | **9** |
| 9 | `1598_dir0_pat0_seq9` | Sanjay Gandhi Transport Nagar | Libas Pur GT Road | 1,024.1 m | **6** |
| 10 | `1598_dir0_pat0_seq10`| Libas Pur GT Road | Swaroop Nagar GT Road | 425.6 m | **5** |
| 11 | `1598_dir0_pat0_seq11`| Swaroop Nagar GT Road | Gurudwara Siraspur GT Road | 788.6 m | **4** |
| 12 | `1598_dir0_pat0_seq12`| Gurudwara Siraspur GT Road | Nangli Puna | 512.3 m | **4** |
| 13 | `1598_dir0_pat0_seq15`| Budhpur GT Road | Bdo Office | 1,258.8 m | **4** |
| 14 | `1598_dir0_pat0_seq16`| Bdo Office | Alipur Village GT Road | 412.5 m | **3** |
| 15 | `1445_dir0_pat0_seq1` | New Sabzi Mandi | Adarsh Nagar / Bharola Village | 274.7 m | **3** |
| 16 | `1445_dir0_pat0_seq4` | Mahindra Park | Jahangir Puri GT Road | 479.8 m | **3** |
| 17 | `1445_dir0_pat0_seq2` | Adarsh Nagar / Bharola Village | Sarai Peepal Thala | 626.8 m | **2** |
| 18 | `1445_dir0_pat0_seq3` | Sarai Peepal Thala | Mahindra Park | 156.6 m | **2** |
| 19 | `1598_dir0_pat0_seq18`| Pwd Office | Palla More | 761.5 m | **2** |
| 20 | `1445_dir0_pat0_seq6` | Jahangir Puri Metro Station | GTK Depot | 518.9 m | **1** |
| 21 | `1598_dir0_pat0_seq13`| Nangli Puna | Jain Mandir | 441.2 m | **1** |
| 22 | `1598_dir0_pat0_seq14`| Jain Mandir | Budhpur GT Road | 586.3 m | **1** |
| 23 | `1598_dir0_pat0_seq17`| Alipur Village GT Road | Pwd Office | 605.9 m | **1** |
| 24 | `1598_dir0_pat0_seq19`| Palla More | Bakhtawar Pur School | 682.1 m | **1** |
| 25 | `1598_dir0_pat0_seq20`| Bakhtawar Pur School | Triveni Colony | 512.0 m | **1** |
| 26 | `1657_dir0_pat0_seq3` | Sarai Peepal Thala | Jahangirpuri GT Road | 636.4 m | **1** |
| **Total**| **All 26 Pairs** | | | | **136** |

---

## 4. Corrected 24-Hour Coverage Table & Zero-Observation Hours

The table below presents the exhaustive 24-hour distribution derived directly from the ground-truth arrival timestamps, explicitly categorizing day types and reporting sample size $n$ for every speed metric:

| Hour of Day (IST) | Regular Weekdays (Thu Oct 1, Wed Oct 7) | Public Holiday (Fri Oct 2 - Gandhi Jayanti) | Weekends (Sat Oct 3, Sun Oct 4) | Total Valid Segments ($n$) | Sample-Backed Median Speed (km/h) | Mean Speed (km/h) | Speed Range (Min – Max km/h) | Empirical Observation Character |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **00:00 – 00:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **01:00 – 01:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **02:00 – 02:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **03:00 – 03:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **04:00 – 04:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **05:00 – 05:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **06:00 – 06:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **07:00 – 07:59** | 0 | 0 | 24 | **24** | 23.37 | 23.28 | 3.81 – 44.84 | Early morning weekend free-flow |
| **08:00 – 08:59** | 12 | 0 | 5 | **17** | 18.61 | 17.35 | 7.64 – 26.30 | Morning commute corridor flow |
| **09:00 – 09:59** | 4 | 0 | 0 | **4** | 23.01 | 23.66 | 19.26 – 29.37 | Post-peak morning arterial speed |
| **10:00 – 10:59** | 0 | 1 | 0 | **1** | 20.78 | 20.78 | 20.78 – 20.78 | *Small sample ($n=1$): Single bus on holiday* |
| **11:00 – 11:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **12:00 – 12:59** | 0 | 0 | 1 | **1** | 1.80 | 1.80 | 1.80 – 1.80 | *Small sample ($n=1$): Localized bus stop dwell* |
| **13:00 – 13:59** | 4 | 4 | 2 | **10** | 21.67 | 20.46 | 9.11 – 34.40 | Midday arterial transit |
| **14:00 – 14:59** | 6 | 5 | 6 | **17** | 21.67 | 21.21 | 4.81 – 36.62 | Steady afternoon transit flow |
| **15:00 – 15:59** | 4 | 8 | 0 | **12** | 21.69 | 19.01 | 4.32 – 32.08 | Afternoon building traffic |
| **16:00 – 16:59** | 8 | 2 | 3 | **13** | 7.30 | 13.24 | 2.13 – 30.24 | Evening congestion building |
| **17:00 – 17:59** | 14 | 0 | 3 | **17** | **4.88** | 10.00 | 1.37 – 32.03 | **Severe peak gridlock (Mukarba Chowk bottleneck)** |
| **18:00 – 18:59** | 7 | 0 | 7 | **14** | 12.07 | 11.69 | 2.04 – 23.61 | Evening peak Ring Road approach |
| **19:00 – 19:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **20:00 – 20:59** | 3 | 0 | 0 | **3** | 1.29 | 1.58 | 1.27 – 2.18 | *Small sample ($n=3$): Local signal crawl at Jahangirpuri* |
| **21:00 – 21:59** | 2 | 0 | 1 | **3** | 20.83 | 17.24 | 6.62 – 24.28 | *Small sample ($n=3$): Nighttime speed recovery* |
| **22:00 – 22:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **23:00 – 23:59** | 0 | 0 | 0 | **0** | — | — | — | **Zero observations** |
| **Total** | **64 (47.1%)** | **20 (14.7%)** | **52 (38.2%)** | **136** | **18.17** | **17.11** | **1.27 – 44.84** | **13 active hours / 11 unobserved hours** |

### Critical Coverage Findings
1. **Unobserved Operating Hours:**
   Across all 5 processed dates, **11 out of 24 hours have ZERO observations**:
   $$\text{Zero-Observation Hours: } [0, 1, 2, 3, 4, 5, 6, 11, 19, 22, 23]$$
   The phrase *"Full operating day covered"* from previous drafts was incorrect and is officially retracted. Ground-truth coverage is active between 07:00 and 21:59, with mid-morning (11:00) and early evening (19:00) gaps.
2. **Small-Sample Context:**
   The reported speed of `1.80 km/h` at 12:00 IST ($n=1$) and `1.29 km/h` at 20:00 IST ($n=3$) represent **localized signal delays and dwell at specific North GT Road intersections**, NOT a network-wide traffic state across Delhi. Downstream models must not extrapolate single-bus observations across the city.

