# Milestone 10.1: Static GTFS Dataset Audit & Integration Feasibility Assessment

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10.1 Specification  
**Dataset Under Audit:** Delhi Buses: GTFS Static Data – DTC / DoT (Catalogue Dataset DLM1)  
**Baseline Database in Production:** `/tmp/delhi_mdb.db` (MobilityDatabase `mdb-1262`)  
**Official Classification:** **`NOT_DOWNLOADED`** (Direct Programmatic Access: **`ACCESS_BLOCKED`**)  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

A comprehensive investigation was conducted to determine the availability, authenticity, schema validity, and integration status of the official hackathon dataset **"Delhi Buses: GTFS Static Data – DTC / DoT"** (Catalogue ID: `DLM1`).

**Definitive Findings:**
1. **Classification:** The full production dataset is classified as **`NOT_DOWNLOADED`**.
2. **Access Barrier:** Programmatic download attempts via `opendata.transport.delhi.gov.in` failed with **HTTP 403 Forbidden (`CSRF verification failed`)**, saving an HTML error page to `/tmp/otd_static.zip` (1,386 bytes). The Delhi Transport Stack backend endpoint (`category=static_gtfs`) returned HTTP 400 (`{"error":"External API error: 400"}`), confirming that the current API key is authorized exclusively for the real-time feed (`VehiclePositions.pb`).
3. **Bundled Sample Inspected:** The repository contains a 100-record sample dataset (`01 Delhi Buses Static_Sample`) covering 20 routes, 100 stops, and 100 trips with valid 2025–2040 calendar dates and genuine `shapes.txt` geometry.
4. **Preservation of Working System:** The active backend continues to operate reliably on the fully audited **`mdb-1262`** SQLite database (`/tmp/delhi_mdb.db`, 6,342 stops, 2,964 routes, 78,515 trips). No unverified database replacement was attempted.

---

## 2. Access Investigation & Download Status

### 2.1 Download Methods Attempted

Three distinct access channels were evaluated to retrieve the full static GTFS feed:

| Channel / URL | Protocol / Authentication | Response Status | Observed Result |
| :--- | :--- | :---: | :--- |
| **Legacy OTD Portal**<br>`https://opendata.transport.delhi.gov.in/...` | HTTPS GET / Form submission | **403 Forbidden** | Returns CSRF error HTML (saved to `/tmp/otd_static.zip`, 1,386 bytes). Requires authenticated browser session cookies. |
| **DTS Backend Gateway**<br>`https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=static_gtfs&filename=...` | HTTPS GET / `x-api-key` | **400 Bad Request** | Returns `{"error":"External API error: 400"}`. Static GTFS category not provisioned under GTFS-RT key. |
| **MobilityDatabase (mdb-1262)**<br>`https://files.mobilitydatabase.org/mdb-1262/...` | HTTPS GET (Direct ZIP) | **200 OK** | 19.8 MB ZIP successfully downloaded and loaded into `/tmp/delhi_mdb.db` (Milestone 1). |

**Classification Verdict:** **`NOT_DOWNLOADED`** (Full catalogue feed) / **`ACCESS_BLOCKED`** (Legacy OTD portal).

---

## 3. Detailed Audit of Available Sample Feed

Inspection of the bundled sample (`/tmp/gtfs_sample/01 Delhi Buses Static_Sample/`):

### 3.1 Metadata & Temporal Validity (`feed_info.txt`, `calendar.txt`)
- **Feed Publisher:** Delhi Transport Corporation (DTC) and Delhi Transport Department (DOT).
- **Feed Version:** `v1`
- **Validity Window:** `20250101` to `20400101` (Active future-proof calendar).
- **Service ID:** Single uniform calendar (`service_id=1`, active all 7 days of the week).

### 3.2 File-by-File Inventory of Sample:

| GTFS File | Row Count | Core Columns Present | Schema Observations |
| :--- | :---: | :--- | :--- |
| `agency.txt` | 3 | `agency_id`, `agency_name`, `agency_url`, `agency_timezone`, `agency_lang` | DTC and DOT explicitly defined. |
| `calendar.txt` | 2 | `service_id`, `monday`..`sunday`, `start_date`, `end_date` | Continuous service from Jan 1, 2025 to Jan 1, 2040. |
| `feed_info.txt` | 3 | `feed_publisher_name`, `feed_start_date`, `feed_end_date`, `feed_version` | Valid 2025–2040 validity window. |
| `routes.txt` | 21 | `route_id`, `route_short_name`, `route_long_name`, `route_type` | 20 route definitions. |
| `trips.txt` | 101 | `trip_id`, `route_id`, `service_id`, `shape_id` | 100 trips; includes `shape_id` references. |
| `stop_times.txt`| 101 | `trip_id`, `arrival_time`, `departure_time`, `stop_id`, `stop_sequence` | 100 arrivals matching stops. |
| `stops.txt` | 101 | `stop_id`, `stop_name`, `stop_lat`, `stop_lon` | 100 stops with clean WGS84 coordinates. |
| `shapes.txt` | 101 | `shape_id`, `shape_pt_lat`, `shape_pt_lon`, `shape_pt_sequence` | **Present!** Provides true road curvature coordinates. |

---

## 4. Head-to-Head Comparison: Sample vs `mdb-1262`

```
Dimension                      Active Database (mdb-1262)     Static Sample (DTS Sample)
──────────────────────────────────────────────────────────────────────────────────────────
Dataset Scale                  Full Network (DTC)             Micro-Sample (20 Routes)
Total Stops                    6,342                          100
Total Routes                   2,964                          20
Total Trips                    78,515                         100
Total Stop Times               3,116,420                      100
Road Geometry (shapes.txt)     ABSENT (0 lines)               PRESENT (100 points)
Calendar Expiry                2024-01-01 (EXPIRED)           2040-01-01 (ACTIVE)
RAPTOR Graph Readiness         Full Delhi Coverage            Unroutable (Disconnected 100 stops)
RAPTOR Transfer Feasibility    High (thousands of footpaths)   Zero (isolated fragments)
Baseline Model Compatibility   Route 1598 (29 stops mapped)   Route 1598 not in sample
Live RT Route Overlap          658 routes match (46.64%)      16 routes match (1.13%)
──────────────────────────────────────────────────────────────────────────────────────────
```

### Critical Finding on Routing Feasibility:
While the sample feed demonstrates that the official Department of Transport specification includes active 2025–2040 calendars and `shapes.txt`, replacing `mdb-1262` with the 100-record sample would **collapse the RAPTOR journey planner**:
- Over 99% of origin/destination pairs in Delhi would fail to find any route.
- The North GT Road pilot corridor (Route 1598, Stop 239 to 247) would be completely lost.
- All 139 backend tests and 18 E2E scenarios would fail immediately.

---

## 5. Migration Plan for Future Full DLM1 Dataset

When the complete DLM1 feed (10,559 stops, 2,403 routes, 89,393 trips) becomes accessible via authenticated bulk download, the following staged migration plan must be executed:

```
[Phase 1: Ingestion & Geometry]
  ├── Update scripts/ingest_gtfs.py to parse shapes.txt into a spatial SQLite R*Tree.
  ├── Load DLM1 stops, routes, trips, calendar into a staged database (/tmp/delhi_dlm1.db).
  └── Verify referential integrity (zero orphan stop_times or trips).

[Phase 2: Spatial Indexing & Footpaths]
  ├── Compute all-pairs walking transfers between DLM1 stops (radius <= 800m).
  └── Verify k-d tree transfer graph connectivity.

[Phase 3: Model Alignment & Corridor Mapping]
  ├── Map Route 1598 stop IDs between mdb-1262 and DLM1 using spatial nearest-neighbor (< 50m).
  └── Retrain M0 baseline model on DLM1 stop pair IDs.

[Phase 4: Test Suite & Frontend Verification]
  ├── Run backend pytest suite with staged database override.
  ├── Update frontend Leaflet renderer to display shapes.txt road geometries.
  └── Execute 18 E2E validation scenarios.

[Phase 5: Atomic Promotion & Status Update]
  ├── Atomically swap DB_PATH from /tmp/delhi_mdb.db to /tmp/delhi_dlm1.db.
  └── Transition timetable freshness from ASSUMED_RECURRING to CURRENT_VERIFIED.
```

---

## 6. Audit Conclusion & Acceptance Integrity

1. The full new static GTFS dataset is **`NOT_DOWNLOADED`**.
2. Claiming that the new static feed is integrated would be false; the system honestly and transparently continues to serve the full `mdb-1262` network under **`DEGRADE`** status.
3. The sample feed proves that official Delhi GTFS includes road curvature (`shapes.txt`) and extended validity, providing an exact blueprint for post-hackathon migration.

