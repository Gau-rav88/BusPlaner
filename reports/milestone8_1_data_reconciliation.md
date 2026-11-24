# Milestone 8.1 — Historical Data Reconciliation Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Operational Status:** **`DEGRADE`**  
**Audit Milestone:** Milestone 8.1  
**Date:** November 21, 2026  

---

## 1. Executive Summary & Objective

In Milestone 8, the report text summarized the empirical dataset as having *136 observations on Route 1598 across 21 physical stop pairs*, creating an apparent conflict with earlier audited reports (Milestones 2.2.1, 3, 4) which documented *136 total observations across 26 stop pairs (124 on Route 1598, 11 on Route 1445, 1 on Route 1657)*.

This independent audit inspected the raw ground-truth Parquet files in `data/processed/stop_crossings/service_date=*/observed_segments.parquet` and the profile generation code in `backend/analytics/time_profiles.py`.

### Primary Finding
The underlying ground-truth data has remained **100% stable, identical, and unaltered** across all milestones. The apparent discrepancy is entirely mathematical and terminological:
1. **Route Attribution:** The 136 observations consist of **124 on Route 1598**, **11 on Route 1445**, and **1 on Route 1657**. The Milestone 8 code actually loaded all 136 observations across all three routes, but the report prose colloquially referred to the entire North GT Road corridor as "Route 1598".
2. **Stop Pairs (Physical vs. Route-Specific):** There are **26 route-specific segment pairs** (`(route_id, stop_id_from, stop_id_to)`). Because Route 1445 co-runs along the North GT Road corridor and shares 5 stop pairs with Route 1598, these 26 route-specific segment pairs map to exactly **21 distinct physical stop pairs** (`(stop_id_from, stop_id_to)`). Earlier reports labeled the 26 route pairs as "physical stop pairs", whereas Milestone 8 counted the 21 deduplicated physical pairs and expanded the 26 route pairs into $26 \times 24 = 624$ hourly bins.

No ground-truth records were modified to force agreement.

---

## 2. Reconciled Global Dataset Inventory

The following table presents the verified, independently reproducible reconciliation of all 136 historical observations across the 5 pilot dates:

| Dimension | Earlier Audited Figure (M2.2.1 / M3) | Milestone 8 Text | Verified Source Parquet Ground Truth | Status & Reconciliation |
|---|:---:|:---:|:---:|---|
| **Total Consecutive Segments** | 136 | 136 | **136** | **Exact Match.** Ground truth unchanged. |
| **Route 1598 Segments** | 124 (91.18%) | 136 | **124 (91.18%)** | Clarified: M8 text loosely referred to corridor by primary route. |
| **Route 1445 Segments** | 11 (8.09%) | Omitted from prose | **11 (8.09%)** | Loaded in code; now explicitly surfaced in metadata. |
| **Route 1657 Segments** | 1 (0.74%) | Omitted from prose | **1 (0.74%)** | Loaded in code; now explicitly surfaced in metadata. |
| **Route-Specific Stop Pairs** | 26 | 26 ($26 \times 24 = 624$ bins) | **26** | **Exact Match.** 20 on 1598, 5 on 1445, 1 on 1657. |
| **Distinct Physical Stop Pairs** | 26 (labeled "physical") | 21 | **21** | Earlier reports conflated route-pairs (26) with physical pairs (21). |
| **Shared Physical Stop Pairs** | 5 | Unspecified | **5** | All 5 pairs on 1445 are identical to 1598 stop pairs. |
| **Globally Distinct Vehicles** | 31 | 31 | **31** | **Exact Match.** 25 on 1598, 5 on 1445, 1 on 1657 (zero overlap). |
| **Distinct Service Dates** | 5 | 5 | **5** | **Exact Match.** Oct 1, 2, 3, 4, 7, 2026. |
| **Observed Hourly Bins** | 13 | 13 | **13** | 07:00–10:00, 12:00–18:00, 20:00–21:00 (IST). |
| **Unobserved Hourly Bins** | 11 | 11 | **11** | 00:00–06:00, 11:00, 19:00, 22:00–23:00 (IST). |
| **Core Field Null Count** | 0 | 0 | **0** | Segment time, distance, speed, coords all 100% complete. |

---

## 3. Discrepancy Breakdown & Detailed Explanation

### Discrepancy A: Observation Counts by Route
- **Finding:** The source parquet files across the 5 dates contain 136 total rows:
  - `data/processed/stop_crossings/service_date=2026-10-01/observed_segments.parquet`: 34 rows (all Route 1598)
  - `data/processed/stop_crossings/service_date=2026-10-02/observed_segments.parquet`: 20 rows (all Route 1598)
  - `data/processed/stop_crossings/service_date=2026-10-03/observed_segments.parquet`: 30 rows (26 Route 1598, 3 Route 1445, 1 Route 1657)
  - `data/processed/stop_crossings/service_date=2026-10-04/observed_segments.parquet`: 22 rows (all Route 1598)
  - `data/processed/stop_crossings/service_date=2026-10-07/observed_segments.parquet`: 30 rows (22 Route 1598, 8 Route 1445)
- **Explanation:** In Milestone 8, the profile generation engine `HistoricalTimeProfileEngine` dynamically read `data/processed/stop_crossings/service_date=*/observed_segments.parquet`. It ingested all 136 rows and properly generated route profiles for 1445, 1598, and 1657. However, the human-written M8 report text used "Route 1598" as shorthand for the entire pilot corridor because Route 1598 constitutes 91.18% of the data. The M8.1 metadata now strictly reports `observations_by_route: {"1598": 124, "1445": 11, "1657": 1}`.

### Discrepancy B: 26 Stop Pairs vs. 21 Stop Pairs
- **Finding:**
  - When grouping by `["route_id", "stop_id_from", "stop_id_to", "direction_id"]`, there are **26 groups**.
  - When grouping by `["stop_id_from", "stop_id_to"]` (physical bus stops), there are **21 groups**.
- **Explanation:**
  Route 1445 is an arterial sibling route running along North GT Road. The 5 stop pairs observed for Route 1445 are:
  1. `240 -> 241` (New Sabzi Mandi $\to$ Adarsh Nagar / Bharola Village)
  2. `241 -> 242` (Adarsh Nagar / Bharola Village $\to$ Sarai Peepal Thala)
  3. `242 -> 243` (Sarai Peepal Thala $\to$ Mahindra Park)
  4. `243 -> 244` (Mahindra Park $\to$ Jahangir Puri GT Road)
  5. `245 -> 246` (Jahangir Puri Metro Station $\to$ GTK Depot)

  All 5 of these stop pairs are **geometrically and physically identical** to 5 of the 20 stop pairs on Route 1598.
  Route 1657 has 1 observed stop pair:
  - `242 -> 1245` (Sarai Peepal Thala $\to$ Jahangirpuri GT Road), which skips stop 243 (Mahindra Park).

  Therefore:
  $$\text{Physical Stop Pairs} = 20 \ (\text{Route 1598}) + 0 \ (\text{New on 1445}) + 1 \ (\text{Route 1657}) = 21$$
  $$\text{Route-Specific Pairs} = 20 \ (\text{Route 1598}) + 5 \ (\text{Route 1445}) + 1 \ (\text{Route 1657}) = 26$$

  Milestone 2.2.1 and Milestone 3 labeled the 26 `segment_key` entries as "26 globally unique physical stop pairs", when they were actually 26 route-specific pairs. Milestone 8 accurately recognized the 21 underlying physical stop pairs while generating $26 \times 24 = 624$ route-stop hourly bins.

---

## 4. Hourly Distribution by Route

The temporal breakdown by hour of day (IST) demonstrates why corridor-level aggregation differs from individual route coverage:

| Hour (IST) | Route 1445 | Route 1598 | Route 1657 | Corridor Total | Status |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **00:00–06:00** | 0 | 0 | 0 | **0** | `UNAVAILABLE` |
| **07:00** | 0 | 24 | 0 | **24** | `OBSERVED` |
| **08:00** | 4 | 13 | 0 | **17** | `OBSERVED` |
| **09:00** | 0 | 4 | 0 | **4** | `OBSERVED` |
| **10:00** | 0 | 1 | 0 | **1** | `OBSERVED` |
| **11:00** | 0 | 0 | 0 | **0** | `UNAVAILABLE` |
| **12:00** | 1 | 0 | 0 | **1** | `OBSERVED` (1445 only) |
| **13:00** | 5 | 4 | 1 | **10** | `OBSERVED` (All 3 routes) |
| **14:00** | 0 | 17 | 0 | **17** | `OBSERVED` |
| **15:00** | 0 | 12 | 0 | **12** | `OBSERVED` |
| **16:00** | 0 | 13 | 0 | **13** | `OBSERVED` |
| **17:00** | 0 | 17 | 0 | **17** | `OBSERVED` |
| **18:00** | 0 | 14 | 0 | **14** | `OBSERVED` |
| **19:00** | 0 | 0 | 0 | **0** | `UNAVAILABLE` |
| **20:00** | 0 | 3 | 0 | **3** | `OBSERVED` |
| **21:00** | 1 | 2 | 0 | **3** | `OBSERVED` |
| **22:00–23:00** | 0 | 0 | 0 | **0** | `UNAVAILABLE` |
| **Total** | **11** | **124** | **1** | **136** | **13 Observed / 11 Unavailable** |

**Crucial Note on Hour 12:** Notice that Route 1598 has 0 observations at 12:00 IST. The single observation at 12:00 IST was contributed by Route 1445. Therefore, Route 1598 alone has 12 observed hours, but the corridor as a whole has **13 observed hours** (coverage ratio: $13/24 = 54.17\%$).

---

## 5. Vehicle and Service Date Independence

- **Vehicle Allocation:**
  - Route 1598: 25 distinct vehicles
  - Route 1445: 5 distinct vehicles
  - Route 1657: 1 distinct vehicle
  - **Cross-Route Vehicle Overlap:** Exactly 0. No vehicle in the pilot sample operated on multiple routes.
  - Total Globally Unique Vehicles: $25 + 5 + 1 = 31$.

- **Service Dates:**
  - Route 1598 was observed across all 5 dates.
  - Route 1445 was observed on Oct 3 and Oct 7.
  - Route 1657 was observed on Oct 3.
  - Total Globally Unique Service Dates: 5 (`2026-10-01`, `2026-10-02`, `2026-10-03`, `2026-10-04`, `2026-10-07`).

---

## 6. Data Integrity & Missing Values

- Across all 136 rows, null counts were verified:
  - `observation_id`, `trajectory_id`, `vehicle_id`, `route_id`, `direction_id`: **0 nulls**
  - `stop_id_from`, `stop_id_to`, `stop_name_from`, `stop_name_to`: **0 nulls**
  - `distance_m`, `segment_time_s`, `speed_kmh`: **0 nulls**
  - `arrival_from_ist`, `arrival_to_ist`, `service_date`: **0 nulls**
  - `dwell_from_s`: **130 nulls** (Dwell times are only computed when a vehicle stopped for multiple GPS pings; 6 observations had non-zero dwell).

All 136 records are valid, consecutive, physical ground-truth segment traversals. No synthetic records exist.

