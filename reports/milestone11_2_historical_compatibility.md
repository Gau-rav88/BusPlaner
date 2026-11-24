# Milestone 11.2: Historical Prediction Compatibility & Service Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 11.2 (DLM1 Primary Database Cutover Preparation)  
**Governing Status:** `DEGRADE`  
**Dataset Version:** `pilot_v1_legacy`  
**Audit Date:** 2026-11-21  

---

## 1. Executive Summary

A transit prediction system must strictly avoid silent data contamination. Because the Delhi Transport Corporation re-keyed stop identifiers and decomposed single centroid stops into distinct directional platforms in DLM1, blindly translating historical GPS observations would inject false directional bias into empirical statistical models.

This audit maps every prediction endpoint, background service, and data pipeline to determine exact data provenance, identifies the safe boundary for DLM1 identifiers, and proves that fallback mechanisms operate without hallucinating historical ground truth.

---

## 2. Codebase Audit: Database and Parquet Dependencies

### 2.1 Services Currently Querying the Legacy Database (`/tmp/delhi_mdb.db`)
1. **`backend/core/raptor_data.py` (`Timetable.load_from_sqlite`):**
   - Loads stops, trips, routes, stop times, and service calendars into RAM.
   - Computes metric UTM Zone 43N coordinates and constructs the transfer footpath spatial $k\text{-d}$ tree.
   - When configured with `DB_PATH=/tmp/delhi_mdb.db`, loads 6,342 stops and 2,473 route patterns.
2. **`backend/app/services/route_service.py` (`RouteService`):**
   - Directly connects to `self.timetable.db_path` via SQLite to query route metadata, trip counts, and shapes.
3. **`backend/app/services/stop_service.py` (`StopService`):**
   - Performs in-memory stop substring searches and spatial radius queries over `self.timetable.stops`.
4. **`backend/app/api/v1/health.py`:**
   - Verifies SQLite database file existence via `os.path.exists(settings.DB_PATH)`.

### 2.2 Services Querying Historical Parquet Data (`observed_segments.parquet`)
1. **`backend/core/journey_planner.py` (`_load_ground_truth_cache`):**
   - Connects an in-memory DuckDB engine to scan `data/processed/stop_crossings/service_date=*/observed_segments.parquet`.
   - Populates `self.observed_ground_truth` keyed by `(stop_id_from, stop_id_to)`.
   - Computes empirical sample counts, median travel times, p10 bounds, and p90 bounds for Level 1 predictions.
2. **`backend/core/journey_planner.py` (`create_default`):**
   - Scans training partition dates (`2026-10-01`, `2026-10-02`, `2026-10-03`) from Parquet files to fit `HistoricalMedianBaseline` (M0 model).
3. **`backend/analytics/time_profiles.py` (`HistoricalTimeProfiles`):**
   - Aggregates the 720 hourly travel-time and speed profiles from historical stop-crossing Parquet partitions.

---

## 3. Classification of Historical Ground Truth Observations

The historical ground truth corpus consists of **136 stop-to-stop segment observations** across **26 route-specific stop pairs** (21 unique physical stop pairs) collected across 5 pilot dates in October 2026:

| Observation Category | Observation Count | Percentage | Provenance & Mapping Policy |
| :--- | :---: | :---: | :--- |
| **Safely Mappable to DLM1 Identifiers** | 29 | 21.32% | Both origin and destination stops have direct 1:1 `HIGH_CONFIDENCE` matches (<8m distance, name similarity >0.90, 0 platform ambiguity). |
| **Must Remain Bound to `pilot_v1_legacy`** | 107 | 78.68% | Involves stop pairs where DLM1 split stops into separate directional platforms across wide medians or specific metro station gates. |
| **Unmapped Observations** | 0 | 0.00% | All 136 observations are fully accounted for. |
| **TOTAL** | **136** | **100.00%** | Governed under truth-in-data principles |

### Why 78.68% Must Remain Attached to `pilot_v1_legacy`
- **Median-Divided Arterials:** On North GT Road (National Highway 44), bus stops were recorded as single road centroids in `mdb-1262`. In DLM1, stops are split into distinct UP and DOWN carriageway platforms separated by 25 to 60 meters.
- **Directional Ambiguity:** In the historical GPS data, buses traveled northwards (UP direction). Forcing these observations onto a general stop ID without platform-level coordinate validation could assign northward bus travel times to southward carriageway stops.
- **Governance Invariant:** To prevent synthetic distortion, the historical training and evaluation corpus is frozen and versioned as **`pilot_v1_legacy`**.

---

## 4. Unobserved Stop Pair Fallback Behavior

A core requirement is that the application must operate correctly when historical predictions are unavailable for an unobserved or unmatched stop pair, **without silently substituting scheduled travel times for observed ground truth**.

### Prediction Hierarchy Attribution Matrix

| Tier Name | Prediction Source Key | Condition Triggered | Fallback Flag | Transparent Attribution Disclosure |
| :--- | :--- | :--- | :---: | :--- |
| **`LEVEL_1_DIRECT_OBSERVED`** | `GROUND_TRUTH_OBSERVED` | Direct historical GPS observations available on North GT Road ($n \ge 3$) | `false` | Direct empirical GPS stop-crossing median. |
| **`LEVEL_2_HISTORICAL_BASELINE_M0`** | `M0_TIER1_ROUTE_HOUR` / `M0_TIER2_STOPPAIR_HOUR` | Direct or pooled historical baseline available | `false` / `true` | M0 hierarchical median baseline. |
| **`LEVEL_3_EXPERIMENTAL_RF`** | `M2_RANDOM_FOREST` | Opt-in experimental Random Forest model enabled | `false` | Experimental candidate ML model. |
| **`LEVEL_4_GTFS_SCHEDULED`** | `GTFS_TIMETABLE` | **Unobserved corridor / unmapped DLM1 pair** | `true` | **Official GTFS scheduled running time (explicitly disclaimed as scheduled).** |
| **`LEVEL_5_STATIC_FALLBACK`** | `STATIC_WALK` | Walking footpaths or unmatched legs | `true` | Static 4.5 km/h Euclidean-Manhattan walking speed. |

### Negative & Edge Case Validation
When a journey is planned on DLM1 between stops that have no historical observations (e.g. Stop `284` $\to$ Stop `5146`):
1. `JourneyPlanner` looks up `("284", "5146")` in `self.observed_ground_truth`.
2. The key is absent, so Level 1 and Level 2 are skipped.
3. Level 3 is disabled by default.
4. Level 4 evaluates the scheduled arrival and departure times from DLM1 `stop_times`.
5. The leg prediction returns:
   - `prediction_tier: "LEVEL_4_GTFS_SCHEDULED"`
   - `prediction_source: "GTFS_TIMETABLE"`
   - `is_fallback: true`
   - `fallback_reason: "GTFS scheduled timetable fallback"`
6. The application returns `200 OK`, duration accounting is conserved ($\Delta = 0.0\text{s}$), and no synthetic historical ground truth is claimed.

