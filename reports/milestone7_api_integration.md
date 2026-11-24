# Milestone 7: Frontend API Integration Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Backend:** FastAPI audited through Milestone 6.1  
**Frontend Architecture:** React 18 + TypeScript + Vite + Tailwind CSS  
**Operational Status:** **DEGRADE** (Timetable expired `2024-01-01`; actual operations unverified; traffic prediction pilot confined to North GT Road corridor)  
**Date:** November 2026  

---

## 1. Executive Summary

Milestone 7 delivers a production-grade React/TypeScript frontend that connects directly to the audited Milestone 6.1 FastAPI backend (`/api/v1`). The frontend adheres strictly to PRD v3.0 requirements:
1. **Zero Logic Duplication:** The web client implements no independent RAPTOR graph traversal, timetable evaluation, or traffic machine learning models in TypeScript. All transit routing, timetable validation, and hierarchical predictions originate from the backend API.
2. **Type Safety & Schema Fidelity:** Frontend TypeScript models (`frontend/src/types/api.ts`) mirror backend Pydantic schemas 1:1, including timetable freshness enums, prediction tier discriminators, confidence tiers, and journey accounting breakdowns.
3. **Robust Error & Freshness Handling:** All HTTP status codes (200, 400, 404, 422, 503) are gracefully intercepted with actionable user guidance, notably for expired timetables where users can enable demonstration mode (`allow_assumed_recurring=true`).
4. **Honest Operational Disclosures:** Every screen enforces the `DEGRADE` status banner, labels confidence scores as heuristic indicators, and displays prediction tier badges for observed corridor vs. scheduled vs. static fallback segments.

---

## 2. API Endpoint Mapping & Integration Matrix

The frontend integrates all six REST endpoints defined in the Milestone 6 OpenAPI specification:

| Endpoint | Method | Frontend Service Function | Purpose & Data Handling | Status Codes Handled |
| :--- | :--- | :--- | :--- | :--- |
| `/api/v1/health` | `GET` | `apiClient.getHealth()` | Verifies backend connectivity, database status, loaded models, memory usage, and operational status. Polled on initial mount and every 30s. | `200` (OK), Network failure / `503` (Degraded/Offline indicator). |
| `/api/v1/timetables/status` | `GET` | `apiClient.getTimetableStatus()` | Inspects GTFS calendar coverage, date ranges (`2022-01-01` to `2024-01-01`), and canonical freshness state. Rendered in header and status modal. | `200` (OK). |
| `/api/v1/stops/search` | `GET` | `apiClient.searchStops(query, limit)` | Stop autocomplete by name substring. Debounced by 300ms on frontend to minimize network overhead. Populates origin/destination selectors and stop discovery. | `200` (Matches), `422` (Query length < 2). |
| `/api/v1/stops/nearby` | `GET` | `apiClient.getNearbyStops(lat, lon, radius, limit)` | Spatial terminal discovery using Euclidean/Haversine bounding box. Integrated with map click and geolocation controls. | `200` (Stops found), `422` (Invalid lat/lon coords). |
| `/api/v1/stops/{stop_id}` | `GET` | `apiClient.getStop(stop_id)` | Fetches single stop metadata, exact coordinates, and served routes. Used for route inspection and map popups. | `200` (Stop details), `404` (Stop not found). |
| `/api/v1/journeys/plan` | `POST` | `apiClient.planJourney(req)` | Multi-modal transit routing via RAPTOR. Accepts origin/destination coordinates or stop IDs, departure time, routing preferences, and experimental flags. | `200` (Journeys returned), `400` (Expired timetable / Invalid time), `404` (No route possible), `422` (Validation error), `503` (Backend service unready). |

---

## 3. End-to-End Request & Response Payloads

### 3.1 Journey Planning: Standard Query (North GT Road Pilot Corridor)

#### Request Payload (`POST /api/v1/journeys/plan`):
```json
{
  "origin_stop_id": "stop_881",
  "destination_stop_id": "stop_883",
  "departure_date": "2026-11-21",
  "departure_time": "08:30:00",
  "allow_assumed_recurring": true,
  "use_experimental_ml": false,
  "max_transfers": 2,
  "max_walking_distance_m": 1000,
  "max_alternatives": 3
}
```

#### Response Handling (`200 OK`):
The response conforms to `JourneyPlanResponseSchema`:
```json
{
  "query": {
    "origin_stop_id": "stop_881",
    "destination_stop_id": "stop_883",
    "departure_date": "2026-11-21",
    "departure_time": "08:30:00",
    "allow_assumed_recurring": true,
    "use_experimental_ml": false
  },
  "timetable_freshness": {
    "status": "ASSUMED_RECURRING",
    "requested_date": "2026-11-21",
    "feed_start_date": "2022-01-01",
    "feed_end_date": "2024-01-01",
    "actual_operations_verified": false,
    "warning_message": "Timetable expired on 2024-01-01. Using recurring weekly schedule for demonstration only. Actual 2026 bus operations are unverified."
  },
  "alternatives": [
    {
      "alternative_index": 0,
      "departure_time": "08:30:00",
      "arrival_time": "08:42:30",
      "total_duration_s": 750,
      "scheduled_duration_s": 720,
      "predicted_duration_s": 750,
      "accounting": {
        "scheduled_in_vehicle_time_s": 600,
        "predicted_in_vehicle_time_s": 630,
        "walking_time_s": 120,
        "waiting_time_s": 0,
        "transfer_time_s": 0,
        "total_travel_time_s": 750,
        "walking_distance_m": 140
      },
      "legs": [
        {
          "leg_type": "WALKING",
          "from_stop": { "stop_id": "origin", "stop_name": "Current Location", "stop_lat": 28.7152, "stop_lon": 77.1910 },
          "to_stop": { "stop_id": "stop_881", "stop_name": "Azadpur Terminal", "stop_lat": 28.7154, "stop_lon": 77.1912 },
          "walking_distance_m": 140,
          "walking_duration_s": 120
        },
        {
          "leg_type": "TRANSIT",
          "route_id": "1598",
          "route_short_name": "1598",
          "trip_id": "trip_1598_0830",
          "from_stop": { "stop_id": "stop_881", "stop_name": "Azadpur Terminal", "stop_lat": 28.7154, "stop_lon": 77.1912 },
          "to_stop": { "stop_id": "stop_883", "stop_name": "Model Town II", "stop_lat": 28.7028, "stop_lon": 77.1935 },
          "scheduled_departure": "08:32:00",
          "scheduled_arrival": "08:42:00",
          "scheduled_duration_s": 600,
          "predicted_duration_s": 630,
          "prediction_tier": "TIER_1_HISTORICAL_OBSERVED",
          "prediction_source": "M0 Historical Segment Median (North GT Road)",
          "prediction_confidence": 0.82,
          "confidence_tier": "HIGH",
          "conformal_lower_s": 540,
          "conformal_upper_s": 720,
          "intermediate_stops": []
        }
      ],
      "number_of_transfers": 0,
      "prediction_summary": {
        "tier_1_segments": 1,
        "tier_2_segments": 0,
        "tier_3_segments": 0,
        "tier_4_segments": 0,
        "tier_5_segments": 0,
        "overall_confidence": 0.82,
        "confidence_tier": "HIGH"
      }
    }
  ],
  "total_alternatives_found": 1,
  "computation_time_ms": 14.2
}
```

---

## 4. Error Handling & Edge Cases

The frontend implements a unified `ApiException` class that catches both HTTP error responses and network anomalies:

### 4.1 400 Bad Request — Timetable Expiration Guard
When a user queries a 2026 date without checking "Allow Assumed Recurring Timetable":
- **Backend response:** `400 Bad Request` with `{"error": "TIMETABLE_EXPIRED", "detail": "Requested service date 2026-11-21 is outside GTFS validity (2022-01-01 to 2024-01-01). Set allow_assumed_recurring=true to plan using historical recurring service patterns."}`
- **Frontend handling:** Intercepts `TIMETABLE_EXPIRED` error, renders an alert banner with a prominent button: **"Enable Demonstration Mode & Retry"**. Clicking this toggles `allow_assumed_recurring` in state and immediately re-triggers the query.

### 4.2 404 Not Found — No Viable Transit Route
- **Backend response:** `404 Not Found` with `{"error": "NO_JOURNEY_FOUND", "detail": "No transit alternatives found within maximum walking distance and transfer constraints."}`
- **Frontend handling:** Displays an informative empty state informing the user that no direct or transfer bus connections exist at that departure time, suggesting widening the walking radius or adjusting the departure time.

### 4.3 422 Unprocessable Entity — Validation Failure
- **Backend response:** `422 Unprocessable Entity` containing field validation details (e.g. invalid latitude/longitude, start time formatted improperly).
- **Frontend handling:** Displays inline input validation errors highlighting the offending field.

### 4.4 503 Service Unavailable — Server Cold Start / Model Unready
- **Backend response:** `503 Service Unavailable` with `{"error": "SERVICE_DEGRADED", "detail": "Backend RAPTOR service initializing."}`
- **Frontend handling:** Automatically retries with exponential backoff while showing a "Connecting to Transit Engine..." status banner.

---

## 5. Frontend-to-Backend Verification Suite

The integration was verified through automated Vitest tests executing against mock and real backend payloads:

1. **`api.test.ts` (7 tests):**
   - Verified successful health check extraction.
   - Verified timetable status extraction and canonical status typing.
   - Verified stop search parameter serialization and debounce.
   - Verified nearby stops spatial radius queries.
   - Verified single stop retrieval.
   - Verified journey planning payload serialization and response parsing.
   - Verified `ApiException` propagation on HTTP 400, 404, and 500.

2. **`formatters.test.ts` (7 tests):**
   - Verified duration formatting (e.g., `750s` -> `12 min 30 s`).
   - Verified seconds-since-midnight conversion (e.g., `30600s` -> `08:30`).
   - Verified distance formatting (meters and kilometers).
   - Verified prediction tier badge colors and human-readable names.

3. **`AlertBanner.test.ts` (4 tests):**
   - Verified rendering of warning, error, and info styles.
   - Verified actionable retry callbacks.
   - Verified dismissible alerts.

---

## 6. Conclusion & Operational Truthfulness

The frontend API integration is complete, fully typed, and strictly aligned with backend specifications. At no point does the frontend create artificial realism or misrepresent the underlying transit intelligence:
- Timetable expiration is surfaced explicitly on every query.
- Confidence scores are designated as heuristic indicators.
- Traffic predictions are restricted to North GT Road pilot segments, falling back honestly to scheduled timetables elsewhere.
- Operational status remains firmly at **DEGRADE**.

