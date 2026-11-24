# Milestone 6: REST API Endpoint Documentation

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner (Problem 1)  
**Governing PRD:** v3.0  
**Overall Operational Status:** **DEGRADE**  
**API Version:** `1.0.0`  
**Base URL:** `http://localhost:8000/api/v1`  
**Interactive Documentation:** `http://localhost:8000/docs` (Swagger UI), `http://localhost:8000/redoc` (ReDoc)

---

## 1. Overview and Design Principles

The Milestone 6 FastAPI REST backend exposes the core capabilities developed in Milestones 1 through 5.1.1:
- **RAPTOR Journey Planner:** Fast multi-criteria Pareto transit routing with walking access/egress, scheduled timetable lookups, and transfer buffer constraints.
- **5-Tier Prediction Hierarchy:** Safe travel time estimation prioritizing observed corridor empirical data (Route 1598 North GT Road), falling back through M0 historical medians, GTFS scheduled times, and static speed fallbacks. Candidate machine learning models (Random Forest) remain strictly gated.
- **Timetable Freshness Protection:** Protection against silent timetable staleness (expired feed 2022–2024 vs. current project date November 2026), requiring explicit client opt-in for demonstration routing while asserting `actual_operations_verified = false`.

### Standard Headers & Content Types
- `Content-Type: application/json`
- `Accept: application/json`
- All responses include standard CORS headers allowing verified frontend origins (`http://localhost:3000`, `http://localhost:5173`).

---

## 2. API Endpoints Reference

### 2.1 Health & Operational Status

#### `GET /api/v1/health`
Checks service health, database connectivity, timetable loading status, and global operational status.

- **Query Parameters:** None
- **Response Status Codes:**
  - `200 OK`: Service operational (under DEGRADE governance).
  - `503 Service Unavailable`: Database or critical subsystem offline.
- **Response Schema:**
```json
{
  "status": "healthy",
  "backend_version": "1.0.0",
  "database_available": true,
  "gtfs_loaded": true,
  "overall_operational_status": "DEGRADE",
  "timestamp_utc": "2026-11-21T10:00:00Z"
}
```
- **Example cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/health" -H "Accept: application/json"
```

---

### 2.2 Timetable Freshness & Operational Readiness

#### `GET /api/v1/timetable/status`
Inspects GTFS timetable freshness for a specific query date and provides clear operational readiness disclosures.

- **Query Parameters:**
  - `service_date` *(optional, string, YYYY-MM-DD)*: Target date to check. Defaults to today's date (`2026-11-21`).
  - `allow_assumed_recurring` *(optional, boolean)*: Set to `true` to acknowledge demonstration mode for expired timetables. Defaults to `false`.
- **Response Status Codes:**
  - `200 OK`: Freshness evaluation returned.
  - `422 Unprocessable Content`: Invalid date format.
- **Response Schema:**
```json
{
  "service_date": "2026-10-01",
  "feed_start_date": "2022-01-01",
  "feed_end_date": "2024-01-01",
  "timetable_status": "ASSUMED_RECURRING",
  "is_date_within_feed_validity": false,
  "actual_operations_verified": false,
  "requires_user_opt_in": true,
  "warnings": [
    "STALE TIMETABLE WARNING: Service date 2026-10-01 is outside GTFS feed validity (2022-01-01 to 2024-01-01). Demonstrating schedule using assumed recurring calendar patterns. Actual on-street operations are unverified."
  ]
}
```
- **Freshness States:**
  - `CURRENT_VERIFIED`: Date within `2022-01-01` to `2024-01-01`.
  - `EXPIRED`: Date outside feed validity and `allow_assumed_recurring=false`.
  - `ASSUMED_RECURRING`: Date outside feed validity with explicit `allow_assumed_recurring=true`.
  - `UNAVAILABLE`: Timetable files missing, corrupt, or unreadable (triggers HTTP 503 with error code `TIMETABLE_UNAVAILABLE`).
- **Example cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/timetable/status?service_date=2026-10-01&allow_assumed_recurring=true"
```

---

### 2.3 Journey Planning

#### `POST /api/v1/journeys/plan`
Computes Pareto-optimal transit journeys between stop IDs or geographical coordinates using the RAPTOR algorithm, incorporating the 5-tier traffic prediction hierarchy.

- **Request Headers:** `Content-Type: application/json`
- **Request Body Fields:**
  - `origin_stop_id` *(optional, string)*: Origin GTFS Stop ID.
  - `dest_stop_id` *(optional, string)*: Destination GTFS Stop ID.
  - `origin_lat`, `origin_lon` *(optional, float)*: Origin WGS84 coordinates (latitude [-90, 90], longitude [-180, 180]).
  - `dest_lat`, `dest_lon` *(optional, float)*: Destination WGS84 coordinates.
  - `departure_date` *(optional, string)*: Date in `YYYY-MM-DD` format. Defaults to `2026-10-01`.
  - `departure_time` *(optional, string)*: Time in `HH:MM:SS` format. Defaults to `08:00:00`.
  - `max_walking_distance_m` *(optional, float)*: Maximum access/egress walking radius in meters (50m to 3000m, default `800.0`).
  - `max_transfers` *(optional, integer)*: Maximum transfers allowed (0 to 5, default `3`).
  - `num_alternatives` *(optional, integer)*: Maximum Pareto alternatives to return (1 to 5, default `3`).
  - `ranking_strategy` *(optional, string)*: Strategy for ordering results: `earliest_arrival` (default), `fewest_transfers`, `least_walking`, `most_reliable`.
  - `use_experimental_ml` *(optional, boolean)*: Explicit opt-in for experimental Random Forest candidate predictions. Defaults to `false`.
  - `allow_assumed_recurring` *(optional, boolean)*: Explicit opt-in to demonstrate routing on dates past GTFS feed validity. Defaults to `false`.

- **Strict Validation Rules:**
  - Must specify either `(origin_lat, origin_lon)` or `origin_stop_id`.
  - Must specify either `(dest_lat, dest_lon)` or `dest_stop_id`.
  - Origin and destination stop IDs cannot be identical.
  - If date is outside feed validity and `allow_assumed_recurring` is `false`, returns `400 Bad Request` with `EXPIRED_TIMETABLE`.

- **Response Status Codes:**
  - `200 OK`: Journeys found (or empty list if unreachable).
  - `400 Bad Request`: Expired timetable queried without opt-in flag.
  - `404 Not Found`: Specific stop ID not found in database.
  - `422 Unprocessable Content`: Validation failure on coordinates, date, or time.
  - `503 Service Unavailable`: GTFS database or timetable data missing.

- **Response Body Structure:**
```json
{
  "origin_stop_id": "239",
  "dest_stop_id": "2024",
  "departure_date": "2026-10-01",
  "departure_time": "12:37:40",
  "timetable_status": "ASSUMED_RECURRING",
  "stale_timetable_warning": "STALE TIMETABLE WARNING: Service date 2026-10-01 is outside GTFS feed validity...",
  "journeys_count": 1,
  "journeys": [
    {
      "journey_id": "journey_0",
      "departure_time": "12:37:40",
      "arrival_time": "13:06:00",
      "total_journey_duration_s": 1700.0,
      "total_walking_duration_s": 0.0,
      "total_transit_duration_s": 1700.0,
      "total_waiting_duration_s": 0.0,
      "num_transfers": 0,
      "is_verified_current_service": false,
      "actual_operations_verified": false,
      "legs": [
        {
          "leg_type": "TRANSIT",
          "route_id": "1598",
          "trip_id": "trip_1598_down_1237",
          "from_stop_id": "239",
          "to_stop_id": "2024",
          "departure_time": "12:37:40",
          "arrival_time": "13:06:00",
          "duration_s": 1700.0,
          "distance_m": 8200.0,
          "prediction_metadata": {
            "prediction_source": "CORRIDOR_OBSERVED_M0",
            "fallback_tier": "SEQ9_STATIONARY",
            "confidence_score": 0.85,
            "confidence_score_type": "HEURISTIC",
            "is_experimental_ml": false,
            "empirical_corridor": "North GT Road"
          }
        }
      ],
      "accounting": {
        "access_walk_s": 0.0,
        "initial_wait_s": 0.0,
        "ride_duration_s": 1700.0,
        "transfer_walk_s": 0.0,
        "transfer_wait_s": 0.0,
        "egress_walk_s": 0.0,
        "total_duration_s": 1700.0,
        "discrepancy_s": 0.0,
        "is_valid_identity": true
      }
    }
  ]
}
```

- **Example cURL (Stop ID to Stop ID):**
```bash
curl -X POST "http://localhost:8000/api/v1/journeys/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "origin_stop_id": "239",
    "dest_stop_id": "2024",
    "departure_date": "2026-10-01",
    "departure_time": "12:37:40",
    "allow_assumed_recurring": true
  }'
```

- **Example cURL (Coordinate to Coordinate):**
```bash
curl -X POST "http://localhost:8000/api/v1/journeys/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "origin_lat": 28.667,
    "origin_lon": 77.228,
    "dest_lat": 28.720,
    "dest_lon": 77.210,
    "departure_date": "2026-10-01",
    "departure_time": "12:37:40",
    "max_walking_distance_m": 1000.0,
    "allow_assumed_recurring": true
  }'
```

---

### 2.4 Stop Search & Discovery

#### `GET /api/v1/stops/search`
Performs case-insensitive substring search on stop names and stop IDs.

- **Query Parameters:**
  - `query` *(required, string, 2 to 100 chars)*: Stop name or ID fragment.
  - `limit` *(optional, integer, 1 to 100, default `20`)*: Maximum results.
- **Response Schema:**
```json
{
  "query": "kashmere",
  "count": 4,
  "stops": [
    {
      "stop_id": "stop_167",
      "stop_name": "ISBT Kashmere Gate",
      "stop_lat": 28.6675,
      "stop_lon": 77.2283
    }
  ]
}
```
- **Example cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/stops/search?query=kashmere&limit=5"
```

---

### 2.5 Nearby Stops (Spatial Lookup)

#### `GET /api/v1/stops/nearby`
Finds bus stops within a specified radial distance from WGS84 coordinates using a KDTree spatial index.

- **Query Parameters:**
  - `lat` *(required, float, -90 to 90)*: Latitude.
  - `lon` *(required, float, -180 to 180)*: Longitude.
  - `radius_m` *(optional, float, 50 to 5000, default `800.0`)*: Search radius in meters.
  - `limit` *(optional, integer, 1 to 50, default `20`)*: Maximum results.
- **Response Schema:**
```json
{
  "center_lat": 28.667,
  "center_lon": 77.228,
  "radius_m": 800.0,
  "count": 6,
  "stops": [
    {
      "stop_id": "stop_167",
      "stop_name": "ISBT Kashmere Gate",
      "stop_lat": 28.6675,
      "stop_lon": 77.2283,
      "distance_meters": 62.4,
      "estimated_walking_time_s": 49.9
    }
  ]
}
```
- **Example cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/stops/nearby?lat=28.667&lon=77.228&radius_m=800"
```

---

### 2.6 Route Inspection

#### `GET /api/v1/routes/{route_id}`
Returns route metadata, direction headsigns, and the ordered sequence of physical stops served by the route.

- **Path Parameters:**
  - `route_id` *(required, string)*: GTFS route ID (e.g., `1598`).
- **Response Status Codes:**
  - `200 OK`: Route details found.
  - `404 Not Found`: Route ID does not exist in GTFS database.
- **Response Schema:**
```json
{
  "route_id": "1598",
  "route_short_name": "1598",
  "route_long_name": "Mori Gate Terminal to Narela Terminal",
  "agency_id": "DIMTS",
  "total_stops": 42,
  "stops": [
    {
      "stop_sequence": 1,
      "stop_id": "stop_167",
      "stop_name": "ISBT Kashmere Gate",
      "stop_lat": 28.6675,
      "stop_lon": 77.2283
    }
  ]
}
```
- **Example cURL:**
```bash
curl -X GET "http://localhost:8000/api/v1/routes/1598"
```

---

## 3. Error Responses and Sanitization

All errors return uniform JSON structures matching the `ErrorResponse` schema, avoiding raw internal stack traces or filesystem path exposure:

```json
{
  "error": "EXPIRED_TIMETABLE",
  "detail": "Requested service date 2026-10-01 is past feed validity (2022-01-01 to 2024-01-01). Demonstrating journeys on expired timetables requires explicit opt-in.",
  "action": "Set allow_assumed_recurring=true in your request to proceed in demonstration mode.",
  "error_code": "EXPIRED_TIMETABLE"
}
```

### Standard Status Codes
| HTTP Status | Error Code | Description |
|:---|:---|:---|
| `400 Bad Request` | `EXPIRED_TIMETABLE` | Service date outside GTFS validity and `allow_assumed_recurring=false`. |
| `404 Not Found` | `STOP_NOT_FOUND` / `ROUTE_NOT_FOUND` | Specified GTFS entity does not exist in database. |
| `422 Unprocessable Content` | `VALIDATION_ERROR` / `INVALID_QUERY_PARAMETERS` | Coordinates out of range, malformed date/time strings. |
| `500 Internal Server Error` | `INTERNAL_SERVER_ERROR` | Sanitized server error without filesystem path leakage. |
| `503 Service Unavailable` | `TIMETABLE_UNAVAILABLE` | GTFS SQLite database offline or unreadable. |

