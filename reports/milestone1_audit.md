# Milestone 1 Ingestion Audit Report

**Service Date Audited:** October 1, 2026 (`2026-10-01`)  
**Raw Source Database:** `data/raw/gps/bus_movements_2026_10_01.db` (3.18 GiB SQLite)  
**GTFS Validation Reference:** MobilityData DTC Feed (`mdb-1262` / IIIT-Delhi release, 2,964 routes, 78,515 trips, 6,342 stops)  
**Date of Audit:** November 21, 2026  

---

## 1. Executive Summary: The Duplicate Discrepancy Resolved

A key question was raised regarding an apparent discrepancy between the initial Milestone 0 discovery report (which cited **23,310 conflicting duplicate rows**) and the Milestone 1 ingestion pipeline (which quarantined **12,071,325 rows** with reason `E02_CONFLICTING_TIMESTAMP_POSITION`).

### Root Cause Analysis

The difference is completely explained by the difference in column grouping between **raw telemetry payload** and **upstream crawler metadata**:

1. **Upstream Crawler Polling Architecture:**
   The Delhi Transport Department real-time vehicle positions were crawled every 10 seconds. The crawler recorded the current system time in a `time` column (e.g., `00:00:01`, `00:00:11`, `00:00:21`) alongside the bus's internal GPS `timestamp` (Unix epoch seconds). If a bus had not transmitted a new GPS ping during that 10-second window, the GTFS-RT feed simply repeated the previous GPS observation with the **exact same latitude, longitude, speed, route_id, and trip_id**.
2. **Discovery Script Definition (Telemetry Payload Only):**
   In `scripts/discover_data.py`, duplicate records were analyzed by grouping strictly on the 7 core telemetry fields:
   `GROUP BY vehicle_id, lat, lng, speed, route_id, trip_id, timestamp` (excluding crawler `date` and `time`).
   - Exact payload duplicates identified: **17,508,859 rows** (99.87% of all multi-row keys).
   - Conflicting payload rows (differing lat/lng/speed for same vehicle & timestamp): **23,310 rows** (0.13%).
3. **Milestone 1 Ingestion Script Definition (All 9 Table Columns):**
   In `scripts/ingest_gps.py`, Rule E01 deduplicated with:
   `SELECT DISTINCT vehicle_id, lat, lng, speed, route_id, trip_id, timestamp, date, time FROM sqlite.vehicle_feed;`
   Because crawler `time` changed every 10 seconds (`00:00:01` vs `00:00:11`), DuckDB considered all 31,290,299 rows distinct across all 9 columns (`e01_dropped = 0`).
   Subsequently, Rule E02 partitioned on `(vehicle_id, timestamp)`:
   Any row with `conflict_rank > 1` (a total of **12,071,325 rows**) was routed to quarantine.
   
**Empirical Proof:** Of the 12,071,325 quarantined rows:
- **11,874,816 rows (98.37%)** are **100% identical in GPS payload** (`lat`, `lng`, `speed`, `route_id`, `trip_id`) and represent harmless scraper re-polls.
- **196,509 rows (1.63%)** across **25,307 distinct keys** represent **true telemetry conflicts** (where position or speed differed at the identical epoch second).

---

## 2. Comprehensive Accounting of Observations (Day 1: 2026-10-01)

The table below breaks down the complete dataset into mutually exclusive categories using reproducible SQL queries:

| Metric Category | Count / Cardinality | % of Raw Records | Description / Explanation |
| :--- | :--- | :--- | :--- |
| **Total Raw Records** | **31,290,299** | 100.00% | Total rows in `sqlite.vehicle_feed` |
| **Distinct `(vehicle_id, timestamp)` Keys** | **19,218,974** | 61.42% | Unique vehicle-epoch instances |
| ├─ Single-Ping Keys (no duplicate) | 13,758,130 | 43.97% | Bus observed exactly once at this epoch |
| └─ Multi-Row Keys (duplicate instances) | 5,460,844 | 17.45% | Vehicle appeared multiple times at identical epoch |
| &nbsp;&nbsp;&nbsp;&nbsp;├─ Identical Payload Keys | 5,435,537 | 99.54% of dupes | All payloads (`lat, lng, spd, rte, trip`) are 100% identical |
| &nbsp;&nbsp;&nbsp;&nbsp;└─ Conflicting Payload Keys | 25,307 | 0.46% of dupes | Differing `lat`, `lng`, or `speed` at identical epoch |
| **Total Multi-Row Observations** | **17,532,169** | 56.03% | Total rows belonging to multi-row keys |
| ├─ First Instance (Retained in Clean) | 5,460,844 | 17.45% | One canonical observation kept per key |
| ├─ Repeated Identical Payload Extra Rows | 11,874,816 | 37.95% | Harmless crawler poll repeats quarantined |
| └─ Conflicting Payload Extra Rows | 196,509 | 0.63% | True telemetry conflicts quarantined |
| **Total Quarantined Records (Rule E02)** | **12,071,325** | 38.58% | Exported to `conflicts_2026-10-01.parquet` |
| **Out-of-Bounds Coordinate Rows (Rule E03)** | **3,466** | 0.01% | Lat/Lon outside NCR bounding box |
| **Final Clean Retained Records** | **19,215,508** | **61.41%** | Stored in `gps_parquet/service_date=2026-10-01/` |

### Reproducible SQL Logic

```sql
-- Query to reproduce key categories:
WITH key_counts AS (
    SELECT 
        vehicle_id, 
        timestamp,
        COUNT(*) as total_rows,
        COUNT(DISTINCT (
            CAST(lat AS VARCHAR) || '_' || 
            CAST(lng AS VARCHAR) || '_' || 
            CAST(speed AS VARCHAR) || '_' || 
            COALESCE(CAST(route_id AS VARCHAR), '') || '_' || 
            COALESCE(trip_id, '')
        )) as distinct_payloads
    FROM sqlite.vehicle_feed
    GROUP BY vehicle_id, timestamp
)
SELECT 
    COUNT(*) as total_distinct_keys,                    -- 19,218,974
    SUM(CASE WHEN total_rows = 1 THEN 1 ELSE 0 END) as single_ping_keys,             -- 13,758,130
    SUM(CASE WHEN total_rows > 1 THEN 1 ELSE 0 END) as multi_row_keys,                -- 5,460,844
    SUM(CASE WHEN total_rows > 1 AND distinct_payloads = 1 THEN 1 ELSE 0 END) as repeated_identical_payload_keys, -- 5,435,537
    SUM(CASE WHEN distinct_payloads > 1 THEN 1 ELSE 0 END) as conflicting_payload_keys, -- 25,307
    SUM(total_rows) as total_rows,                      -- 31,290,299
    SUM(CASE WHEN total_rows > 1 AND distinct_payloads = 1 THEN total_rows - 1 ELSE 0 END) as repeated_identical_extra_rows, -- 11,874,816
    SUM(CASE WHEN distinct_payloads > 1 THEN total_rows - 1 ELSE 0 END) as conflicting_extra_rows -- 196,509
FROM key_counts;
```

---

## 3. Evaluation of Duplicate-Resolution Speed Bias

In Milestone 1, Rule E02 resolved multi-row groups using `ORDER BY speed DESC, lat, lng`. We evaluated whether selecting the highest speed observation introduces systematic speed bias into the clean dataset.

### Quantitative Findings

An audit comparing the maximum speed observation vs the minimum speed observation across all 5,460,844 duplicate groups revealed:

- **Duplicate Groups with Speed Difference = 0:** **5,458,864 groups (99.964%)**  
  In 99.964% of duplicate groups, the speed across all records was identical. Selecting `speed DESC` had zero mathematical effect on speed in these groups.
- **Duplicate Groups with Speed Difference > 0:** **1,980 groups (0.036%)**  
  In only 1,980 groups across the entire day did reported speeds differ at the same timestamp.
- **Mean Speed Difference across ALL 5.46M Duplicate Groups:** **0.00318 km/h**  
  The overall bias introduced by `speed DESC` across the dataset is less than 0.004 km/h—statistically negligible.
- **Among the 1,980 Conflicting Groups:**
  - Mean speed difference: **8.77 km/h**
  - Median speed difference: **6.94 km/h**
  - 90th percentile speed difference: **18.79 km/h**
  - Maximum speed difference: **50.00 km/h**

### Evaluation of Alternative Policies

1. **Policy A (`speed DESC`, Current Milestone 1 Implementation):**
   - *Pros:* Deterministic, prevents spurious stationary pings (`speed = 0`) when the bus is actively moving in traffic.
   - *Cons:* Slightly favors higher speeds in the 1,980 true conflict instances (+8.77 km/h for those 1,980 rows).
2. **Policy B (`median speed` / `first-seen crawler ping`):**
   - *Pros:* Completely neutral with respect to speed magnitude.
   - *Cons:* "First seen" depends on crawler thread scheduling; median requires floating-point interpolation if group size is even.
3. **Policy C (Trajectory Consistency Quality Rule - PRD Rule E06):**
   - Compare reported speed with implied displacement speed from the preceding ping: $v_{\text{implied}} = \Delta d / \Delta t$.
   - Select the observation whose reported speed minimizes $|v_{\text{reported}} - v_{\text{implied}}|$.
   - *Recommendation:* Keep the existing Milestone 1 output intact (as instructed: do not silently modify outputs), and apply Policy C during Trajectory Reconstruction (Milestone 2) when preceding and succeeding pings are known.

---

## 4. GPS Route Identifier Matching Against Full GTFS

We performed an exhaustive cross-match between the normalized GPS route IDs in `gps_parquet/service_date=2026-10-01/data.parquet` and the full Mobility Database GTFS catalog (`/tmp/delhi_mdb.db`):

| Route Metric | Value |
| :--- | :--- |
| **Total Distinct GPS Route IDs (Day 1)** | **2,201** |
| **Total GTFS Routes in Full Catalog** | **2,964** |
| **Directly Matched Route IDs** | **979** |
| **Unmatched GPS Route IDs** | **1,222** |
| **Exact Matching Percentage** | **44.48%** |

### Why Are 1,222 GPS Routes Unmatched?

Inspection of unmatched GPS route IDs indicates three distinct operational categories:
1. **Cluster Bus Schemes:** Private concessionaire cluster routes operated under different internal numeric route IDs (e.g. routes starting with `18xx`, `19xx`, `20xx`).
2. **Depot and Deadhead Runs:** Special depot pull-out/pull-in runs (e.g. `9999`, `0`, or internal fleet rebalancing).
3. **Feeder and Shuttle Services:** Feeder buses to metro stations that use internal transport department numbering not included in the primary DTC static schedule.

For the **979 matched routes**, full GTFS topology, stop sequences, and stop locations are available to construct route polylines and extract stop crossings.

---

## 5. Scheduled-Trip ID Extraction Rule Validation

In Milestone 1, we implemented the regex rule `^(\d+_\d+_\d+)` to extract the scheduled trip prefix from raw GPS trip identifiers (e.g., `"712_08_54_5381"` $\to$ `"712_08_54"`).

### Validation Results Against MDB GTFS Trips

| Metric | Count | Percentage |
| :--- | :--- | :--- |
| **Total Distinct Raw GPS Trip IDs** | **80,325** | 100.0% |
| **Valid Canonical Prefixes Extracted** | **80,325** | **100.0%** (0 invalid/malformed) |
| **Distinct Canonical Prefixes** | **76,249** | - |
| **Exact Matches to GTFS `trips.trip_id`** | **1,003** | 1.32% |
| **Unmatched Canonical Prefixes** | **75,246** | 98.68% |

### Sample Matches & Unmatched Analysis

- **Matched Examples:**
  - Raw: `941_14_15` $\to$ Canonical: `941_14_15` $\to$ GTFS Trip: `941_14_15` (Route 941, scheduled departure 14:15)
  - Raw: `712_08_54_5381` $\to$ Canonical: `712_08_54` $\to$ GTFS Trip: `712_08_54` (Route 712, scheduled departure 08:54)
  - Raw: `1598_13_44` $\to$ Canonical: `1598_13_44` $\to$ GTFS Trip: `1598_13_44` (Route 1598, scheduled departure 13:44)
- **Unmatched Examples:**
  - Raw: `1966_08_13_5250` $\to$ Canonical: `1966_08_13` (Route 1966 is not in static GTFS)
  - Raw: `2008_15_26_6274` $\to$ Canonical: `2008_15_26` (Route 2008 is not in static GTFS)

### Core Architectural Implication for Milestone 2

As specified in PRD Section 6.3 & 6.4:
> *"If trip_id is unavailable or does not join to GTFS, mark trip resolution as inferred. Evaluate candidate shapes for the GPS route, including both directions."*

We cannot rely solely on static GTFS `trip_id` joins to determine the route pattern. Instead, for the 979 matched routes, we evaluate the candidate route patterns (directions 0 and 1) and match trajectories based on **spatial proximity, heading, and monotonic stop sequence order**.

---

## 6. Archive Processing Status Disclosure

> [!IMPORTANT]
> **Only October 1, 2026 (`2026-10-01`) has been processed.**  
> The remaining 30 days of the October 2026 archive have NOT been extracted or ingested into Parquet. The non-solid 7z archive structure (`Solid = -`) was verified during Milestone 0 and 1, confirming that each day can be extracted and converted independently in a streaming loop without exhausting local host disk space. All Milestone 2 analyses and pilots operate strictly on the validated October 1 dataset.

