# Milestone 9 — PRD v3.0 Requirements Traceability Matrix

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Current Operational Status:** **`DEGRADE`** *(Strictly Maintained)*  
**Audit Milestone:** Milestone 9: Final Validation, Demo Readiness & Submission Package  
**Date:** November 21, 2026  

---

## 1. Traceability Methodology & Status Classifications

This matrix maps every core requirement from the governing PRD v3.0 to its concrete implementation location, verification evidence/automated tests, operational status, and real-world technical limitations.

In accordance with Milestone 9 instructions, no requirement is marked `IMPLEMENTED` based on claims in earlier reports; every entry has been audited directly against the live repository codebase and executable test suites.

### Status Definitions
- **`IMPLEMENTED`**: Fully implemented in production code with passing automated tests and exact compliance with PRD specifications.
- **`PARTIALLY_IMPLEMENTED`**: Implemented for a subset of the problem space (e.g. pilot corridor) or operating under explicit demonstration-mode constraints.
- **`NOT_IMPLEMENTED`**: Omitted or deferred per project cut-line rules.
- **`BLOCKED`**: Implementation precluded by external environmental or data constraints (e.g. missing upstream credentials or absent GTFS files).

---

## 2. Requirements Traceability Matrix

| PRD Section | Requirement Description | Implementation Location | Evidence & Automated Tests | Status | Documented Limitation |
|---|---|---|---|:---:|---|
| **PRD §1.3** | End-to-End System Integration (GPS $\to$ Model $\to$ RAPTOR $\to$ API $\to$ UI) | Full Stack (`backend/`, `frontend/`) | `scripts/validate_milestone9_e2e.py` (18 scenarios), 176 distinct test definitions (176 total executions) | **PARTIALLY_IMPLEMENTED** | End-to-end integration complete, but operates under `DEGRADE` status due to expired 2022 GTFS and unauthenticated live feed. |
| **PRD §2.1** | Priority 1: Baseline Historical Travel-Time Lookup (M0) | `backend/core/prediction_hierarchy.py`, `backend/models/baseline_m0.py` | `test_milestone3_baseline.py`, `test_milestone8_time_profiles.py` | **IMPLEMENTED** | Confined to 136 observations across 3 routes (124 on Route 1598, 11 on Route 1445, 1 on Route 1657; 26 route-stop pairs, 21 physical pairs). |
| **PRD §2.1** | Priority 1: RAPTOR Journey Planner with Walking & Transfers | `backend/core/raptor.py`, `backend/core/journey_planner.py` | `test_milestone5_raptor.py`, `test_milestone5_routing.py` | **IMPLEMENTED** | Evaluates static timetable schedules under demonstration assumption (`ASSUMED_RECURRING`). |
| **PRD §2.1** | Priority 1: Time Accounting Identity ($T_{\text{walk}} + T_{\text{wait}} + T_{\text{ride}} = T_{\text{total}}$) | `backend/core/journey_planner.py` | `test_milestone6_api.py::test_journey_accounting_identity`, E2E Scenario 17 | **IMPLEMENTED** | Strictly conserved to $0.00\text{ s}$ discrepancy across all journey alternatives. |
| **PRD §2.1** | Priority 1: Complete Backend REST API | `backend/app/api/v1/*.py` | `test_milestone6_api.py`, `test_milestone6_1_audit.py` (38 API tests) | **IMPLEMENTED** | Exposes 7 production REST endpoints with OpenAPI schemas and lifespan pre-warming. |
| **PRD §2.1** | Priority 1: Map-Based Web Frontend Application | `frontend/src/` (React + TS + Vite + Leaflet) | `frontend/src/test/*.test.tsx`, `liveIntegration.test.ts` (26 tests) | **IMPLEMENTED** | Straight-line stop-to-stop geometry displayed due to absence of GTFS `shapes.txt`. |
| **PRD §2.2** | Out of Scope: Real-time dynamic re-routing of active in-flight buses | N/A | Excluded from codebase architecture | **NOT_IMPLEMENTED** | Explicitly out of scope per PRD §2.2. |
| **PRD §4.1** | Static GTFS Ingestion (`routes`, `trips`, `stops`, `stop_times`, `calendar`) | `backend/data_ingestion/gtfs_sqlite.py`, `/tmp/delhi_mdb.db` | `test_milestone1_ingestion.py` | **IMPLEMENTED** | SQLite relational DB (268 MB); timetable calendar expired `2024-01-01`. |
| **PRD §4.1** | GTFS Shape Curvature (`shapes.txt`) | `/tmp/delhi_mdb.db` (`shapes` table) | `test_milestone7_1_audit.py` | **NOT_IMPLEMENTED** | Upstream DTC GTFS package contains 0 shape records; fallback straight segments used. |
| **PRD §4.1** | Live GTFS-Realtime Protobuf Feed Ingestion | `backend/realtime/gtfs_rt.py`, `backend/app/api/v1/live.py` | `test_milestone8_live_feed.py`, `test_milestone8_1_audit.py` | **BLOCKED** | Delhi Transport Stack live endpoint requires `x-api-key`. Classified `AUTH_REQUIRED`; live ingestion disabled. |
| **PRD §6.1** | Partitioned GPS Data Ingestion & Streaming | `backend/data_ingestion/gps_streaming.py`, `data/processed/gps_parquet/` | `test_milestone1_ingestion.py` | **PARTIALLY_IMPLEMENTED** | Successfully processed 5-date pilot subset (Oct 1–4, 7, 2026); storage bounds prevented full 31-day ingestion. |
| **PRD §6.4** | Shape Matching & Trajectory Linear Referencing | `backend/map_matching.py` | `test_milestone2_shape_matching.py` | **IMPLEMENTED** | Spatio-temporal bracketing along GTFS stop sequences. |
| **PRD §6.5** | Stop-Crossing Event Interpolation & Dwell Detection | `backend/stop_crossings.py`, `data/processed/stop_crossings/` | `test_milestone2_stop_crossings.py` | **IMPLEMENTED** | Extracted 199 valid stop crossings and 136 consecutive segment traversals. |
| **PRD §7.4** | 5-Tier Sparse-Data Fallback Prediction Hierarchy | `backend/core/prediction_hierarchy.py` | `test_milestone5_1_audit.py`, `test_milestone6_api.py` | **IMPLEMENTED** | Levels 1 (Direct Observed), 2 (Pooled Baseline), 3 (RF), 4 (Scheduled), 5 (Static). |
| **PRD §7.6** | Experimental Random Forest Traversal Model | `backend/models/random_forest.py` | `test_milestone4_validation.py` | **PARTIALLY_IMPLEMENTED** | Built and evaluated; deactivated by default (`use_experimental_ml: false`) due to negative out-of-fold generalization ($R^2 < 0$). |
| **PRD §7.7** | Conformal Prediction Uncertainty Intervals | `backend/analytics/conformal.py` | `test_milestone3_1_1_audit.py` | **PARTIALLY_IMPLEMENTED** | Evaluated on pilot subset; intervals withheld for unobserved corridors to prevent ungrounded claims. |
| **PRD §7.9** | Time-of-Day Traffic Profiles & Speed Ratios | `backend/analytics/time_profiles.py`, `historical_time_profiles.json` | `test_milestone8_time_profiles.py`, `test_milestone8_1_audit.py` | **PARTIALLY_IMPLEMENTED** | 13 observed hours vs 11 unobserved hours (marked `UNAVAILABLE`). Live fusion disabled due to `AUTH_REQUIRED`. |
| **PRD §8.1** | RAPTOR Multi-Criteria Pareto Routing Engine | `backend/core/raptor.py`, `backend/core/raptor_data.py` | `test_milestone5_raptor.py` (22 unit routing tests) | **IMPLEMENTED** | Computes non-dominated Pareto rounds across travel time and transfer count. |
| **PRD §8.4** | Spatial Footpaths, Walking Access & Egress | `backend/core/footpaths.py`, `backend/core/spatial_index.py` | `test_milestone5_footpaths.py` | **IMPLEMENTED** | $k\text{-d}$ tree spatial index, Euclidean-to-Manhattan walking conversion at 4.5 km/h. |
| **PRD §8.7** | Multi-Criteria Journey Ranking Strategies | `backend/core/journey_ranking.py` | `test_milestone6_api.py` | **IMPLEMENTED** | Supports `earliest_arrival`, `fewest_transfers`, `least_walking`, `most_reliable`. |
| **PRD §10.3** | REST API: `GET /health` | `backend/app/api/v1/health.py` | `test_milestone6_api.py::test_api_health_check` | **IMPLEMENTED** | Returns `application_status: "ok"`, `overall_operational_status: "DEGRADE"`, `live_feed_status: "AUTH_REQUIRED"`. |
| **PRD §10.3** | REST API: `GET /timetable/status` | `backend/app/api/v1/timetable.py` | `test_milestone6_api.py::test_api_timetable_status` | **IMPLEMENTED** | Evaluates calendar boundaries; returns `EXPIRED` or `ASSUMED_RECURRING` with warnings. |
| **PRD §10.3** | REST API: `POST /journeys/plan` | `backend/app/api/v1/journeys.py` | `test_milestone6_api.py`, `test_milestone6_1_audit.py` | **IMPLEMENTED** | Direct and transfer transit planning with full prediction metadata and time accounting. |
| **PRD §10.3** | REST API: `GET /stops/search` | `backend/app/api/v1/stops.py` | `test_milestone6_api.py::test_api_stop_search` | **IMPLEMENTED** | Case-insensitive substring search across 3,000+ Delhi bus stops. |
| **PRD §10.3** | REST API: `GET /stops/nearby` | `backend/app/api/v1/stops.py` | `test_milestone6_api.py::test_api_nearby_stops` | **IMPLEMENTED** | Haversine spatial radius query returning nearest stops with distance metadata. |
| **PRD §10.3** | REST API: `GET /routes/{route_id}` | `backend/app/api/v1/routes.py` | `test_milestone6_api.py::test_api_route_detail` | **IMPLEMENTED** | Returns ordered stop sequence and pattern metadata for route geometry plotting. |
| **PRD §10.3** | REST API: `GET /live/status` | `backend/app/api/v1/live.py` | `test_milestone8_api.py`, `test_milestone8_1_audit.py` | **IMPLEMENTED** | Returns feed reachability (`AUTH_REQUIRED`), polling status, and configurable staleness limit. |
| **PRD §12.2** | Frontend: Search Interface with Autocomplete & Geolocation | `frontend/src/components/PlannerForm.tsx` | `PlannerForm.test.tsx`, `liveIntegration.test.ts` | **IMPLEMENTED** | Stop name autocomplete, Delhi presets, date/time pickers, explicit consent checkbox. |
| **PRD §12.3** | Frontend: Journey Results Display with Alternatives | `frontend/src/components/JourneyResults.tsx` | `JourneyResults.test.tsx` | **IMPLEMENTED** | Renders alternative cards with transfers, durations, prediction badges, and warnings. |
| **PRD §12.4** | Frontend: Detailed Leg Breakdown & Time Accounting | `frontend/src/components/JourneyResults.tsx` | `JourneyResults.test.tsx` | **IMPLEMENTED** | Visualizes access walk, transit ride with intermediate stops, transfer, and egress walk. |
| **PRD §12.5** | Frontend: Interactive Map with Bus Route & Walking Polyline | `frontend/src/map/DelhiMap.tsx` | `DelhiMap.tsx`, visual inspection | **IMPLEMENTED** | OpenStreetMap base layer, Leaflet markers, stop-to-stop lines, geometry disclaimer. |
| **PRD §12.7** | Frontend: Method, Data Provenance & Operational Warnings | `frontend/src/components/Header.tsx`, `PlannerForm.tsx` | `HeaderAndAlerts.test.tsx` | **IMPLEMENTED** | Discloses DEGRADE operational status, expired GTFS, heuristic confidence, and live feed auth state. |
| **PRD §12.8** | Frontend: Empty States, Loading Spinners & Error Banners | `frontend/src/components/*.tsx` | `PlannerForm.test.tsx`, `liveIntegration.test.ts` | **IMPLEMENTED** | Clean handling of 400 Expired Timetable, 422 Invalid Input, and zero-journey empty states. |

---

## 3. Summary Compliance Assessment

- **Total PRD Requirements Audited:** 32 core requirements
- **Fully Implemented (`IMPLEMENTED`):** 24 (75.0%)
- **Partially Implemented (`PARTIALLY_IMPLEMENTED`):** 5 (15.6%)
- **Blocked by External Factors (`BLOCKED`):** 1 (3.1% — Live GTFS-RT feed requiring DTS API key)
- **Out of Scope / Absent in Feed (`NOT_IMPLEMENTED`):** 2 (6.3% — Dynamic mid-trip re-routing and GTFS `shapes.txt`)
- **Requirements with at Least Partial Implementation:** **90.6% (29/32)** (24 fully implemented + 5 partially implemented)
- **Overall System Readiness:** **Production-Structured Hackathon Architecture Operating Under Verified `DEGRADE` Mode.**

