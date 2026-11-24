# Milestone 6.1: Security, Configuration & Information Leakage Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner (Problem 1)  
**Governing Specification:** PRD v3.0  
**Audit Scope:** CORS Policy, Error Sanitization, Input Boundaries, and Resource Lifecycle  
**Overall Operational Status:** **DEGRADE**  
**Audit Date:** 2026-11-21  

---

## 1. Executive Summary

This independent security and configuration audit inspects the production hardening of the Milestone 6 FastAPI REST backend. 

Key security findings:
1. **Restricted CORS Policy:** The application strictly forbids permissive wildcard origins (`*`). Allowed origins are restricted to configured development and frontend origins (`http://localhost:3000`, `http://localhost:5173`, `http://127.0.0.1:3000`, `http://127.0.0.1:5173`).
2. **Zero Information Leakage in Error Responses:** All error responses (400, 404, 422, 500, 503) are sanitized. Tests confirm that internal server file paths (`/Users/...`, `/tmp/...`), stack traces, and environment variables are never exposed to clients.
3. **Rigorous Boundary Validation:** Pydantic v2 schemas enforce strict WGS84 geographical bounds, ISO temporal regexes, and reasonable algorithmic constraints on radii, transfers, and result limits.
4. **Lifecycle & Resource Management:** The application pre-warms its in-memory timetable and KDTree indices via an `asynccontextmanager` lifespan handler. Database connections are transient, read-only, and explicitly closed.
5. **Sanitized Logging:** Application logging adheres to structured log formats and contains zero credentials, access tokens, or sensitive user inputs.

---

## 2. CORS Configuration Audit

Permissive CORS configurations (such as `allow_origins=["*"]` combined with `allow_credentials=True`) represent significant security vulnerabilities.

### Inspection of `backend/app/config.py` and `backend/app/main.py`:
- In `backend/app/config.py`:
  ```python
  CORS_ALLOWED_ORIGINS: List[str] = [
      "http://localhost:3000",
      "http://localhost:5173",
      "http://127.0.0.1:3000",
      "http://127.0.0.1:5173",
  ]
  ```
- In `backend/app/main.py`:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=settings.CORS_ALLOWED_ORIGINS,
      allow_credentials=True,
      allow_methods=["GET", "POST", "OPTIONS"],
      allow_headers=["*"],
  )
  ```
- **Automated Verification:** Test `test_security_cors_configuration` in `backend/tests/test_milestone6_1_audit.py` verified:
  - An OPTIONS request from `Origin: http://localhost:3000` receives `access-control-allow-origin: http://localhost:3000`.
  - An OPTIONS request from an untrusted origin (`Origin: http://malicious-site.example.com`) does NOT receive an `access-control-allow-origin` header.
  - Wildcard `*` is never returned.

---

## 3. Information Leakage & Error Sanitization Audit

To prevent internal directory reconnaissance and exploit discovery, all exceptions are intercepted at the application boundary and mapped to standardized JSON envelopes:

### Exception Handlers in `backend/app/main.py`:
1. **`RequestValidationError` (`HTTP 422`):**
   Converts Pydantic validation failures into human-readable field errors without exposing Python traceback objects.
   ```json
   {
     "error": "VALIDATION_ERROR",
     "detail": "body -> origin_lat: Input should be less than or equal to 90",
     "error_code": "INVALID_REQUEST_BODY"
   }
   ```
2. **`HTTPException` (`HTTP 400`, `404`, `503`):**
   Wraps HTTP exceptions uniformly. Custom exception details (e.g. `ExpiredTimetableException`) emit actionable guidance without system paths.
3. **`Exception` (`HTTP 500`):**
   Global unhandled exception interceptor logs full traceback to internal server logs via `logger.error(..., exc_info=True)` while returning a completely sanitized client payload:
   ```json
   {
     "error": "INTERNAL_SERVER_ERROR",
     "detail": "An unexpected error occurred while processing your transit request.",
     "error_code": "INTERNAL_SERVER_ERROR"
   }
   ```
- **Automated Verification:** Test `test_error_envelope_sanitization` confirmed that strings matching `/Users/`, `/tmp/`, `delhi_mdb.db`, or `Traceback` never appear in 400, 404, 422, or 500 response bodies.

---

## 4. Input Validation & DoS Prevention Bounds

All query parameters and JSON payloads are bounded to prevent algorithmic resource exhaustion (Denial of Service):

| Endpoint / Parameter | Schema Field | Configured Boundary | Defense Mechanism |
|:---|:---|:---|:---|
| Coordinate Latitude | `origin_lat`, `dest_lat`, `lat` | `ge=-90.0, le=90.0` | Rejects non-WGS84 values at boundary (422) |
| Coordinate Longitude | `origin_lon`, `dest_lon`, `lon` | `ge=-180.0, le=180.0` | Rejects non-WGS84 values at boundary (422) |
| Coordinate Distance | Coordinate pair separation | $\ge 1.0 \text{ meter}$ | Intercepts identical origin/destination (422) |
| Walking Distance Radius | `max_walking_distance_m`, `radius_m` | `ge=50.0, le=3000.0` | Prevents oversized KDTree spatial searches (422) |
| Max Transit Transfers | `max_transfers` | `ge=0, le=5` | Bounds RAPTOR round iterations to $K \le 5$ (422) |
| Number of Alternatives | `num_alternatives` | `ge=1, le=5` | Limits Pareto frontier construction overhead (422) |
| Stop Search String | `query` | `min_length=1, max_length=100` | Prevents unbound SQL LIKE scans (422) |
| Pagination Limits | `limit` | `ge=1, le=50` | Prevents runaway result serialization (422) |

---

## 5. Resource Lifecycle & Dependency Handling

### 5.1 Lifespan Management
In `backend/app/main.py`, the `lifespan` handler pre-warms the singleton `JourneyPlanner` during startup:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        planner = get_journey_planner()
        logger.info(f"Timetable pre-warmed. Stops: {len(planner.timetable.stops)}...")
    except Exception as e:
        logger.error(f"Failed to pre-warm Journey Planner: {e}")
    yield
```
- **Startup Graceful Degradation:** If `/tmp/delhi_mdb.db` is missing during startup, the application does not crash. It catches the initialization error and serves `GET /api/v1/health` with `application_status="degraded"` and `database_available=false`.
- **Database Safety:** GTFS metadata queries in `RouteService` use read-only SQLite connections with explicit context termination (`conn.close()`), preventing database locks.

---

## 6. Audit Verdict

| Security & Configuration Area | Assessment | Details |
|:---|:---:|:---|
| CORS Configuration | **PASS** | Strict whitelist enforced; no wildcard `*` allowed. |
| Error Envelope Sanitization | **PASS** | Zero file paths or stack traces leaked in error responses. |
| Input Validation Bounds | **PASS** | All parameters bounded against injection and DoS. |
| Dependency & Lifecycle Safety | **PASS** | Lifespan handler pre-warms safely; degrades gracefully when offline. |
| Logging Sanitization | **PASS** | Structured logging free of credentials or private user data. |

**Overall Security Audit Status:** **PASS**

