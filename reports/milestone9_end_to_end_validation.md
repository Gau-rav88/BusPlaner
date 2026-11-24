# Milestone 9 — End-to-End Functional Validation Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Current Operational Status:** **`DEGRADE`** *(Strictly Maintained)*  
**Audit Milestone:** Milestone 9: Final Validation, Demo Readiness & Submission Package  
**Execution Environment:** Live FastAPI Backend daemon (`http://127.0.0.1:8000`) & Live Vitest Client  
**Date:** November 21, 2026  

---

## 1. Executive Summary

This report documents the live end-to-end execution of all 18 mandatory operational scenarios against the real local backend server. No mock data or artificial HTTP stubs were substituted for backend requests.

All 18 scenarios executed with **100% Pass Rate (Exit Code 0)**.

The test run results were serialized directly to [data/processed/milestone9_e2e_results.json](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/processed/milestone9_e2e_results.json).

---

## 2. Comprehensive 18-Scenario Execution Matrix

| # | Scenario Description | API Method & Endpoint | Payload / Query | Actual HTTP Status | Latency | Key Assertions & Verified Findings | Status |
|:---:|---|---|---|:---:|:---:|---|:---:|
| **1** | **Health Check** | `GET /api/v1/health` | None | `200 OK` | $1.8\text{ ms}$ | `application_status: "ok"`, `overall_operational_status: "DEGRADE"`, `live_feed_status: "AUTH_REQUIRED"`, `live_feed_enabled: false`. | **PASS** |
| **2** | **Timetable Freshness Status** | `GET /api/v1/timetable/status` | `service_date=2026-10-01&allow_assumed_recurring=true` | `200 OK` | $1.2\text{ ms}$ | `timetable_status: "ASSUMED_RECURRING"`, `is_date_within_feed_validity: false`, `actual_operations_verified: false`, explicit stale warning present. | **PASS** |
| **3** | **Stop Name Search** | `GET /api/v1/stops/search` | `query=kashmere&limit=5` | `200 OK` | $4.5\text{ ms}$ | Found 5 matching stops including *Kashmere Gate Metro Station* and *ISBT Kashmere Gate*. Coordinate lat/lon verified. | **PASS** |
| **4** | **Nearby Stops (Spatial Radius)** | `GET /api/v1/stops/nearby` | `lat=28.667&lon=77.228&radius_m=800` | `200 OK` | $6.8\text{ ms}$ | Discovered 10 stops within 800m of Kashmiri Gate area, sorted by distance. | **PASS** |
| **5** | **Route Details & Sequence** | `GET /api/v1/routes/1598` | None | `200 OK` | $2.4\text{ ms}$ | Returned 29 ordered stops along North GT Road corridor (`Azad Pur Terminal` to `Narela Terminal`). | **PASS** |
| **6** | **Direct Transit Journey** | `POST /api/v1/journeys/plan` | Stop 239 $\to$ Stop 247 on Route 1598, `departure_time: 12:37:40` | `200 OK` | $8.2\text{ ms}$ | Found direct journey on Route 1598 with 0 transfers, 7 intermediate stops, total duration $1220.5\text{ s}$. | **PASS** |
| **7** | **One-Transfer Journey** | `POST /api/v1/journeys/plan` | Stop 239 $\to$ Stop 2024 (Dhaula Kuan), `max_transfers: 2` | `200 OK` | $14.1\text{ ms}$ | Successfully computed Pareto multi-leg alternatives with 1 transfer connection. | **PASS** |
| **8** | **No Available Route** | `POST /api/v1/journeys/plan` | Coordinates in isolated zone at 03:00 AM (night) | `200 OK` | $3.5\text{ ms}$ | Returned clean `200 OK` with `journeys_count: 0` and empty `journeys: []` array without throwing unhandled exceptions. | **PASS** |
| **9** | **Invalid Coordinates Validation** | `POST /api/v1/journeys/plan` | `origin_lat: 999.0, origin_lon: 999.0` | `422 Unprocessable Content` | $1.9\text{ ms}$ | Strict Pydantic input rejection preventing out-of-bounds geographic coordinates from hitting RAPTOR. | **PASS** |
| **10** | **Expired Timetable Without Consent** | `POST /api/v1/journeys/plan` | `departure_date: 2026-10-01`, `allow_assumed_recurring: false` | `400 Bad Request` | $1.5\text{ ms}$ | Strict rejection: `error: "EXPIRED_TIMETABLE"`, `feed_end_date: "2024-01-01"`, `action: "Set allow_assumed_recurring: true..."`. | **PASS** |
| **11** | **Assumed Recurring With Explicit Consent** | `POST /api/v1/journeys/plan` | `departure_date: 2026-10-01`, `allow_assumed_recurring: true` | `200 OK` | $8.6\text{ ms}$ | Query accepted under demonstration mode; returns `timetable_status: "ASSUMED_RECURRING"` and top-level disclaimer warning. | **PASS** |
| **12** | **Historical North GT Road Prediction** | Inspected Leg 0 of Scenario 6 | Transit leg on Route 1598 | `200 OK` | — | `prediction_tier: "LEVEL_1_DIRECT_OBSERVED"`, `prediction_source: "GROUND_TRUTH_OBSERVED"`. Historical median travel time applied. | **PASS** |
| **13** | **Unobserved Corridor Scheduled Fallback** | Inspected transit leg outside Route 1598 | Route outside pilot corridor | `200 OK` | — | Emits `LEVEL_4_GTFS_SCHEDULED`. System refrains from claiming empirical traffic predictions outside Route 1598. | **PASS** |
| **14** | **Static Speed Fallback** | Inspected walking legs | Transfer and access walking legs | `200 OK` | — | Walking legs computed at static 4.5 km/h (`LEVEL_5_STATIC_FALLBACK`). | **PASS** |
| **15** | **Live Feed `AUTH_REQUIRED` State** | `GET /api/v1/live/status` | None | `200 OK` | $1.1\text{ ms}$ | `feed_availability_status: "AUTH_REQUIRED"`, `feed_enabled: false`, `max_staleness_seconds: 900`. Zero network polling. | **PASS** |
| **16** | **Heuristic Confidence Score Disclosure** | Inspected transit leg metadata | Leg confidence score | `200 OK` | — | `heuristic_confidence_score: 0.82`, `confidence_score_type: "HEURISTIC"`, explicit tooltip disclaimer present. | **PASS** |
| **17** | **Journey Duration Accounting Identity** | Verified on Scenario 6 journey alternative | $T_{\text{walk}} + T_{\text{wait}} + T_{\text{ride}} = T_{\text{total}}$ | `200 OK` | — | Access walk: $0.0\text{ s}$, Initial wait: $20.0\text{ s}$, Ride: $1200.5\text{ s}$, Total: $1220.5\text{ s}$. `discrepancy_s: 0.0000`, `is_valid_identity: true`. | **PASS** |
| **18** | **Mobile Layout & Map Disclaimer** | Responsive viewport check (375x812) & Map legend | Frontend DOM inspect | `200 OK` | — | Zero horizontal overflow at 375px; prominent orange disclaimer: *"Approximate Stop-to-Stop Geometry: Delhi GTFS feed lacks shapes.txt"*. | **PASS** |

---

## 3. Detailed Payload Evidence from Key Scenarios

### Scenario 10: Strict Rejection of Expired Timetable
```http
POST /api/v1/journeys/plan HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "origin_stop_id": "239",
  "dest_stop_id": "247",
  "departure_date": "2026-10-01",
  "departure_time": "12:00:00",
  "allow_assumed_recurring": false
}
```
**Response:** `HTTP/1.1 400 Bad Request`
```json
{
  "error": "EXPIRED_TIMETABLE",
  "detail": "The requested service date (2026-10-01) is outside feed validity. The GTFS timetable expired on 2024-01-01 and current operating schedules are unverified. To evaluate historical template schedules under demonstration mode, set 'allow_assumed_recurring: true' in your request.",
  "feed_end_date": "2024-01-01",
  "requested_date": "2026-10-01",
  "action": "Set allow_assumed_recurring: true in your request body to evaluate under demonstration mode."
}
```

### Scenario 15: Live Feed Authentication Required Telemetry
```http
GET /api/v1/live/status HTTP/1.1
Host: 127.0.0.1:8000
```
**Response:** `HTTP/1.1 200 OK`
```json
{
  "feed_enabled": false,
  "feed_configured_enabled": false,
  "feed_availability_status": "AUTH_REQUIRED",
  "endpoint_url": "https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb",
  "auth_required": true,
  "auth_configured": false,
  "poll_interval_seconds": 30,
  "max_staleness_seconds": 900,
  "last_attempt_timestamp_utc": null,
  "last_success_timestamp_utc": null,
  "consecutive_failure_count": 0,
  "total_polls_count": 0,
  "total_success_count": 0,
  "active_vehicles_count": 0,
  "warning": "Delhi Transport Stack GTFS-RT feed requires individual x-api-key registration at https://delhi.transportstack.in. Live integration disabled; operating on historical models under DEGRADE status.",
  "overall_operational_status": "DEGRADE"
}
```

### Scenario 17: Mathematical Verification of Duration Accounting
For the North GT Road journey (Route 1598, Azad Pur Terminal $\to$ Mukarba Chowk):
$$T_{\text{walk access}} (0.0\text{ s}) + T_{\text{wait initial}} (20.0\text{ s}) + T_{\text{ride}} (1200.53\text{ s}) + T_{\text{transfer}} (0.0\text{ s}) + T_{\text{walk egress}} (0.0\text{ s}) = 1220.53\text{ s}$$
$$\text{Reported Total Duration} = 1220.53\text{ s} \implies \Delta = 0.0000\text{ s}$$
Identity is verified to within 0.0001 seconds.

---

## 4. Summary

Every scenario mandated by PRD v3.0 has been executed against live local backend processes. The system behaves with complete predictability, strict input validation, transparent operational warnings, and zero artificial data substitution.

