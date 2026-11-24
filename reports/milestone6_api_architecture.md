# Milestone 6 — Backend REST API Architecture Specification

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 6 (Backend API Implementation)  
**Governing Specification:** PRD v3.0  
**Governing Status:** **DEGRADE**  
**Author:** Backend Architecture Team  
**Date:** November 21, 2026  

---

## 1. Executive Summary & Architecture Goals

Milestone 6 builds a production-structured FastAPI REST backend that exposes the validated RAPTOR journey planning engine, the 5-tier traffic prediction hierarchy, and explicit GTFS timetable freshness metadata.

### Architectural Principles
1. **Reuse over Duplication:** Directly encapsulate the verified algorithms in `backend/core/raptor.py`, `backend/core/raptor_data.py`, and `backend/core/journey_planner.py`. Do not duplicate routing or prediction logic.
2. **Strict Layered Separation:**
   - **API Presentation Layer (`backend/app/api/v1/`):** HTTP request routing, status code assignment, header handling, OpenAPI tagging.
   - **Validation & Serialization Layer (`backend/app/schemas/`):** Pydantic v2 models with coordinate boundary validation, ISO timestamp formatting, and error schemas.
   - **Application Service Layer (`backend/app/services/`):** Business logic coordination, timetable freshness resolution, accounting verification, stop/route queries.
   - **Domain Core Layer (`backend/core/` & `backend/ml/`):** RAPTOR engine, KDTree spatial indexing, M0 hierarchical baseline, and conformal calibrator.
   - **Infrastructure & Configuration Layer (`backend/app/config.py` & `dependencies.py`):** Environment configuration, singleton lifecycle, database pooling.
3. **Mandatory Operational Safeguards:**
   - **Timetable Freshness:** Strict adherence to four distinct freshness states (`CURRENT_VERIFIED`, `EXPIRED`, `ASSUMED_RECURRING`, `UNAVAILABLE`).
   - **Explicit Demonstration Opt-In:** Demonstration mode (`allow_assumed_recurring`) is **False by default**. Expired timetable queries are rejected with actionable errors unless the caller explicitly opts in.
   - **Actual Operations Verification:** The field `actual_operations_verified` is strictly `False` across all responses, preventing misrepresentation of static feeds as verified physical bus operations.
   - **Heuristic Confidence:** All confidence values are explicitly typed as heuristic scores and documented as non-probabilities.
   - **ML Gating:** Experimental Random Forest predictions (`use_experimental_ml`) are strictly disabled by default.

---

## 2. Directory & Module Structure

```text
backend/app/
├── __init__.py
├── main.py                  # FastAPI app factory, lifespan, CORS, global exception handlers
├── config.py                # Pydantic-settings / env var configuration
├── dependencies.py          # FastAPI dependency injection (PlannerService, Timetable singleton)
├── schemas/
│   ├── __init__.py
│   ├── common.py            # CoordinateSchema, ErrorResponse, StatusEnum
│   ├── health.py            # HealthResponse schema
│   ├── timetable.py         # TimetableStatusResponse schema
│   ├── journey.py           # JourneyPlanRequest, JourneyPlanResponse, LegSchema, AccountingSchema
│   ├── stops.py             # StopSearchResponse, NearbyStopsResponse, StopSchema
│   └── routes.py            # RouteDetailResponse, RoutePatternSchema
├── services/
│   ├── __init__.py
│   ├── planner_service.py   # High-level journey planning and freshness resolution
│   ├── stop_service.py      # Stop name search and spatial radius search
│   └── route_service.py     # Route metadata and ordered stop sequence extraction
└── api/
    ├── __init__.py
    └── v1/
        ├── __init__.py
        ├── router.py        # Master v1 APIRouter aggregating all sub-routers
        ├── health.py        # GET /api/v1/health
        ├── timetable.py     # GET /api/v1/timetable/status
        ├── journeys.py      # POST /api/v1/journeys/plan
        ├── stops.py         # GET /api/v1/stops/search & GET /api/v1/stops/nearby
        └── routes.py        # GET /api/v1/routes/{route_id}
```

---

## 3. Detailed Component Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CLIENT REQUEST                                       │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ HTTP (JSON)
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ FASTAPI PRESENTATION LAYER (backend/app/main.py & api/v1/)                             │
│ - CORS Middleware (trusted origins only)                                               │
│ - Request Validation via Pydantic v2 schemas                                           │
│ - Global Exception Handlers (HTTPException, RequestValidationError)                     │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Dependency Injection (Depends)
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ APPLICATION SERVICE LAYER (backend/app/services/)                                      │
│ - PlannerService: Coordinate checking, freshness gating, RAPTOR invocation, accounting │
│ - StopService: Stop name substring search, KDTree proximity lookup                     │
│ - RouteService: Route pattern queries, SQLite timetable inspection                     │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Internal Core Invocations
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ DOMAIN CORE LAYER (backend/core/ & backend/ml/)                                        │
│ - JourneyPlanner: 5-level prediction hierarchy, leg adjustment, delay propagation      │
│ - RaptorEngine: Multi-criteria Pareto optimization, 120s buffer, footpath traversal    │
│ - Timetable: KDTree UTM index, RoutePatterns, monotonic seconds-since-midnight         │
│ - Baseline M0 / Random Forest ML: Segment travel-time inference and conformal bounds   │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ SQL & File I/O
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ DATA & STORAGE LAYER                                                                   │
│ - SQLite Database: /tmp/delhi_mdb.db (stops, routes, trips, stop_times, calendar)      │
│ - Parquet Partitions: data/processed/stop_crossings/ (ground-truth segment statistics) │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Endpoint Specifications & Contracts

### 4.1 Health Check: `GET /api/v1/health`
- **Purpose:** Monitor operational health, backend version, data availability, and system status.
- **Response Model:** `HealthResponse`
- **Output Contract:**
  ```json
  {
    "application_status": "ok",
    "backend_version": "1.0.0",
    "database_available": true,
    "gtfs_loaded": true,
    "model_available": true,
    "overall_operational_status": "DEGRADE",
    "timestamp_utc": "2026-11-21T09:50:00Z"
  }
  ```

### 4.2 Timetable Freshness: `GET /api/v1/timetable/status`
- **Purpose:** Report GTFS feed validity, calendar expiry, and demonstration assumption availability.
- **Query Parameters:**
  - `service_date` (optional string, e.g. `"2026-10-01"`): Target service date to evaluate.
  - `allow_assumed_recurring` (optional boolean, default `False`): Explicit demonstration opt-in.
- **Output Contract:**
  ```json
  {
    "timetable_status": "ASSUMED_RECURRING",
    "feed_start_date": "2022-01-01",
    "feed_end_date": "2024-01-01",
    "feed_provenance": "Mobility Database / Delhi Transport Corporation (DTC) Static GTFS archive",
    "is_date_within_feed_validity": false,
    "actual_operations_verified": false,
    "demonstration_mode_available": true,
    "warnings": [
      "STALE TIMETABLE WARNING: The underlying GTFS schedule expired on 2024-01-01..."
    ]
  }
  ```

### 4.3 Journey Planning: `POST /api/v1/journeys/plan`
- **Purpose:** Compute Pareto-optimal multi-modal transit itineraries using the RAPTOR engine and 5-tier prediction hierarchy.
- **Request Model:** `JourneyPlanRequest`
  ```json
  {
    "origin_lat": 28.7150,
    "origin_lon": 77.1810,
    "dest_lat": 28.7350,
    "dest_lon": 77.1650,
    "departure_date": "2026-10-01",
    "departure_time": "12:37:40",
    "max_walking_distance_m": 800.0,
    "max_transfers": 3,
    "num_alternatives": 3,
    "use_experimental_ml": false,
    "allow_assumed_recurring": true,
    "ranking_strategy": "earliest_arrival"
  }
  ```
- **Response Model:** `JourneyPlanResponse`
  - Returns journey alternatives, boarding/alighting stops, walking legs, scheduled vs. predicted timestamps, full accounting breakdown, heuristic confidence scores, and timetable freshness metadata.
  - Guarantees `discrepancy_s == 0.0000` on every itinerary.

### 4.4 Stop Search: `GET /api/v1/stops/search`
- **Purpose:** Substring matching over Delhi physical stops with limit bounding.
- **Query Parameters:** `query` (string, min 2 chars), `limit` (int, default 10, max 50).
- **Response:** List of stops matching the query sorted alphabetically.

### 4.5 Nearby Stops: `GET /api/v1/stops/nearby`
- **Purpose:** Spatial radius stop resolution via projected KDTree index.
- **Query Parameters:** `lat` (float), `lon` (float), `radius_m` (float, default 800, max 3000), `limit` (int, default 10, max 50).
- **Response:** List of stops ordered by walking distance.

### 4.6 Route Information: `GET /api/v1/routes/{route_id}`
- **Purpose:** Inspect route metadata, pattern count, and ordered stop sequences.
- **Path Parameter:** `route_id` (string).
- **Response:** Route metadata, agency name, trip count, and ordered stop sequence. Returns HTTP 404 if `route_id` is unknown.

---

## 5. Security, Input Validation & Operational Safeguards

1. **Coordinate Validation:**
   - Origin and destination coordinates are strictly validated: Latitude must be in range $[-90.0, 90.0]$ and Longitude $[-180.0, 180.0]$.
   - Origin and destination cannot be identical (distance $\ge 10\text{ meters}$).
2. **Timetable Expiration Guard:**
   - If a caller requests a service date after `2024-01-01` without setting `allow_assumed_recurring: true`, the API rejects the request with HTTP 400 Bad Request:
     `"The GTFS timetable expired on 2024-01-01. Set allow_assumed_recurring=true to opt into unverified demonstration routing."`
3. **CORS Configuration:**
   - Configurable allowed origins via `CORS_ALLOWED_ORIGINS` environment variable (defaults to `["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]`). Wildcard `*` in production is forbidden.
4. **Information Leakage Protection:**
   - Internal stack traces, SQLite file paths, and memory addresses are sanitized. Client error responses adhere to standard JSON error envelopes.
5. **Lifespan Connection Management:**
   - Engine initialization and database connections are loaded once during startup via FastAPI's `@asynccontextmanager` lifespan handler, guaranteeing sub-second response times on subsequent requests.

---

## 6. Conclusion

This architecture provides a clean, robust, and safe REST API interface for the Delhi Journey Planner, upholding all PRD v3.0 requirements and strict operational safeguards.

