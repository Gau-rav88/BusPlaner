# GTFS Validation Report
## Delhi Real-Time Bus Traffic Model & Journey Planner

**Date:** 21 November 2026  
**Milestone:** 1 – GTFS and GPS Data Ingestion  
**Status:** Ingested & Validated  
**Database Output:** [`data/serving/delhi_bus.db`](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/serving/delhi_bus.db)

---

## 1. Executive Summary: Sample vs. Full Dataset Verification

In accordance with Milestone 1 directives, we investigated whether the locally discovered GTFS files were sample slices or complete datasets.

1. **Transport Stack Sample Slice (`data/raw/gtfs/`):**
   - The file `1739952971309_01 Delhi Buses Static_Sample.zip` available from `https://delhi.transportstack.in` without authentication is explicitly a **sample test slice**.
   - Contains: 20 routes, 100 trips, 100 stops, 100 stop-times, and 1 shape (`shp_3_1`).
   - Tables within the sample slice do not join cleanly across foreign keys because each table was truncated independently by head-slicing.
2. **Complete Full-Scale GTFS Feed (`mdb-1262` / IIIT-Delhi DTC Release):**
   - Sourced from open transit archives (MobilityData feed `mdb-1262` / IIIT-Delhi DTC open transit data release, 19.8 MB ZIP / 120.3 MB uncompressed).
   - Contains: **2,964 routes**, **78,515 trips**, **6,342 stops**, and **3,276,092 stop-times**.
   - **Referential integrity across all foreign keys is 100.0% perfect** (zero orphan trips, zero orphan stop_times).
3. **Official Delhi Transport Stack DLM1 Metadata:**
   - Catalog totals: 10,559 stops, 2,403 routes, 89,393 trips.
   - Requires registered user authentication on `https://delhi.transportstack.in` for direct download.
   - The ingestion pipeline is built modularly to ingest and validate either feed seamlessly.

---

## 2. Table-by-Table Row Counts & Field Completeness

### A. Complete GTFS Dataset (`/tmp/delhi_mdb.db`)
| Table Name | Record Count | Key Fields Verified | Status |
|---|---:|---|:---:|
| `agency` | 2 | `agency_id`, `agency_name`, `agency_timezone` (`Asia/Kolkata`) | Validated |
| `calendar` | 1 | `service_id=1`, active all 7 days (M-Su: 1) | Validated |
| `routes` | 2,964 | `route_id` (normalized integer string), `route_long_name`, bus type `3` | Validated |
| `stops` | 6,342 | `stop_id`, `stop_name`, coordinates, projected `utm_x`, `utm_y` (`EPSG:32643`) | Validated |
| `trips` | 78,515 | `trip_id` (`{route_id}_{HH}_{MM}` format), `route_id`, `service_id` | Validated |
| `stop_times` | 3,276,092 | `trip_id`, `stop_id`, `stop_sequence`, `arrival_sec`, `departure_sec` | Validated |
| `shapes` | 0 | Not included in `mdb-1262` release | Documented |

### B. Transport Stack Sample Dataset (`data/serving/delhi_bus.db`)
| Table Name | Record Count | Key Fields Verified | Status |
|---|---:|---|:---:|
| `agency` | 2 | DTC, DOT (`Asia/Kolkata`) | Validated |
| `calendar` | 1 | `service_id=1`, active all 7 days | Validated |
| `routes` | 20 | Route long names, type 3 | Validated |
| `stops` | 100 | Coordinates within Delhi NCR | Validated |
| `trips` | 100 | `trip_id` (`1000_*` through `1006_*`) | Validated |
| `stop_times` | 100 | Stop sequences 0 to 40 | Validated |
| `shapes` | 100 | `shape_id: shp_3_1` (100 projected points) | Validated |

---

## 3. Referential Integrity Analysis

| Foreign Key Relationship | Complete Feed Orphan Count | Sample Feed Orphan Count | Validation Assessment |
|---|---:|---:|---|
| `trips.route_id` $\to$ `routes.route_id` | **0 orphans** (100.0% valid) | 100 orphans | Complete feed has flawless foreign key integrity. Sample feed trips were sliced from different route numbers. |
| `stop_times.trip_id` $\to$ `trips.trip_id` | **0 orphans** (100.0% valid) | 3 orphans | Complete feed stop_times all link to existing trips. |
| `stop_times.stop_id` $\to$ `stops.stop_id` | **0 orphans** (100.0% valid) | 0 orphans | All stop_times link to valid physical bus stops. |
| `trips.shape_id` $\to$ `shapes.shape_id` | N/A (shapes omitted) | 100 orphans | In the sample, trips reference `shp_3_2247` while shapes only has `shp_3_1`. |

---

## 4. Time Formatting & Midnight Boundary Handling

1. **Format:** Standard `HH:MM:SS` parsed to seconds from service midnight.
2. **Post-Midnight Service ($\ge$ 24:00:00 / $\ge 86,400\text{s}$):**
   - In the complete dataset, **20,505 stop-time rows** exceed `24:00:00` (e.g., `24:05:00`, `25:30:00`).
   - These represent late-night and owl bus trips belonging to the current operational service day.
   - The parser correctly stores these as values exceeding 86,400 seconds (e.g., `25:30:00` = 91,800s), fully satisfying PRD Section 6.1 requirement #9.

---

## 5. Spatial Coordinate Validation & Metric Projections

- All bus stop coordinates fall within the Delhi NCR bounding box (`[28.0°N, 29.2°N]`, `[76.5°E, 77.8°E]`).
- Projected coordinates `utm_x` and `utm_y` are computed and stored in the database using **`EPSG:32643` (UTM Zone 43N)**.
- Indexes created:
  - `idx_routes_id` on `routes(route_id)`
  - `idx_stops_id` on `stops(stop_id)`
  - `idx_trips_id` on `trips(trip_id)`
  - `idx_trips_route` on `trips(route_id)`
  - `idx_stop_times_trip` on `stop_times(trip_id, stop_sequence)`
  - `idx_stop_times_stop` on `stop_times(stop_id)`
  - `idx_shapes_id` on `shapes(shape_id, shape_pt_sequence)`

---

## 6. Recommendations for Milestone 2

1. Use the complete dataset for route and timetable graph construction in RAPTOR.
2. For shape matching, candidate shape trajectories will be associated with route geometries from `shapes.txt` where available, or constructed directly from stop sequence lines where shapes are omitted.

