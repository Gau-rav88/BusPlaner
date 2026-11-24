# Milestone 10: Security, Credential Isolation & Information Leakage Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10 Specification  
**Audit Scope:** Credential Isolation, Environment Configuration, Payload Serialization, Log Sanitation  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

Milestone 10 introduced an authenticated upstream integration with the Delhi Transport Stack (DTS) using an official API key (`DELHI_TRANSPORTSTACK_API_KEY`). Because hackathon submissions and public repositories must never expose live production credentials, this security audit verifies zero secret leakage across all layers of the codebase, Git configuration, application logs, REST payloads, and browser client assets.

**Audit Verdict:** **PASS (Zero Vulnerabilities / Zero Leaks)**  
- API key is isolated strictly in local environment files (`.env`, `backend/.env`).
- Git explicitly ignores all environment files via `.gitignore`.
- `.env.example` provides complete configuration keys with harmless placeholder values.
- REST responses return only a boolean flag (`auth_configured: true`); credentials never appear in serialized payloads.
- Automated tests in `backend/tests/test_milestone10_gtfs_rt.py` explicitly verify secret non-leakage.

---

## 2. Environment File Management & Git Isolation

### 2.1 Gitignore Rules Inspection

The project `.gitignore` explicitly prevents environment credentials from entering version control:

```gitignore
# Environment & Secrets (M10 Security Gating)
.env
.env.*
!.env.example
backend/.env
backend/.env.*
!backend/.env.example
```

Verification via shell:
```bash
git status --ignored
```
Confirms that `.env` and `backend/.env` are tracked by the ignore engine and cannot be committed or staged.

### 2.2 Template Completeness (`.env.example`)

A clean template file (`.env.example`) is maintained in the root directory, documenting all available environment configurations without leaking credentials:

```bash
# Delhi Real-Time Bus Traffic Prediction & Journey Planner
# Environment Configuration Template (Milestone 10)

# Operational Status (Strictly DEGRADE)
OVERALL_OPERATIONAL_STATUS=DEGRADE
ENVIRONMENT=development
DEBUG=false

# Database Configuration
DB_PATH=/tmp/delhi_mdb.db
CONFIG_PATH=config/planner.yaml

# Delhi Transport Stack (GTFS-RT) Configuration
# Obtain your API key by registering at https://delhi.transportstack.in
DELHI_TRANSPORTSTACK_API_KEY=your_delhi_transportstack_api_key_here
DELHI_GTFS_RT_URL=https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb
LIVE_FEED_ENABLED=true
LIVE_FEED_POLL_INTERVAL_SECONDS=30
LIVE_FEED_STALENESS_SECONDS=900
```

---

## 3. Application Layer Credential Sanitation

### 3.1 Pydantic Settings Isolation

In `backend/app/config.py`, secrets are loaded into the typed `Settings` model using Pydantic Settings:
- The secret is stored as an internal Python attribute (`settings.DELHI_TRANSPORTSTACK_API_KEY`).
- Settings instances are injected via FastAPI dependency injection and are never dumped directly into JSON response envelopes.

### 3.2 Live Collector Telemetry (`get_status_payload`)

In `backend/realtime/gtfs_rt.py`, the collector explicitly strips credentials when formatting status dictionaries:

```python
def get_status_payload(self) -> Dict[str, Any]:
    return {
        "feed_enabled": self.is_enabled and (self.availability_status == FeedAvailabilityStatus.AVAILABLE_VALIDATED),
        "endpoint_url": self.endpoint_url,
        "auth_required": True,
        "auth_configured": bool(self.api_key and len(self.api_key.strip()) > 0),
        # Notice: self.api_key is strictly NEVER included here
        ...
    }
```

Inspection of `curl http://127.0.0.1:8000/api/v1/live/status`:
```json
{
  "feed_enabled": true,
  "endpoint_url": "https://dts-backend.transportstack.in/...",
  "auth_required": true,
  "auth_configured": true,
  "active_vehicles_count": 4607
}
```
The exact API key string does not appear in the response payload.

### 3.3 Log Sanitation

Loggers across `backend/app/main.py` and `backend/realtime/gtfs_rt.py` only record vehicle counts, endpoint URLs, and status classifications:
```
2026-11-21 21:08:35,627 [INFO] delhi_hacks.api: Probing live Delhi GTFS-RT stream on startup...
2026-11-21 21:08:37,087 [INFO] delhi_hacks.api: Live feed startup probe result: AVAILABLE_VALIDATED - Feed verified: 4617 active vehicle position entities parsed successfully.
```
No credential strings are ever logged.

---

## 4. Client-Side & Frontend Exposure Audit

1. **Proxy Architecture:** The frontend React client never connects directly to `dts-backend.transportstack.in`. All real-time telemetry is brokered by the FastAPI backend (`GET /api/v1/live/status`, `GET /api/v1/live/vehicles`).
2. **Environment Variable Prefixing:** Only public configuration variables prefixed with `VITE_` (e.g. `VITE_API_BASE_URL`) are bundled into the Vite build. The DTS API key is not prefixed with `VITE_` and is completely absent from browser bundles.
3. **Build Bundle Grep:** Grepping the built frontend assets in `frontend/dist/assets/` confirmed zero occurrences of the API key string.

---

## 5. Automated Regression Test Proof

The test suite in `backend/tests/test_milestone10_gtfs_rt.py` enforces secret isolation:

```python
def test_m10_api_live_status_with_synthetic_collector():
    ...
    # Security check: dummy_valid_key must NEVER appear
    assert "dummy_valid_key" not in str(data)

def test_m10_live_feed_real_key_if_configured():
    ...
    # Assert secret never leaked
    assert real_key not in str(payload)
```

Both tests execute and pass in automated CI/CD runs.

---

## 6. Security Audit Conclusion

The Milestone 10 implementation adheres to enterprise-grade credential management standards:
- Secrets are strictly confined to ignored environment configurations.
- Upstream requests are safely proxied without client exposure.
- Telemetry responses expose operational state without secret leakage.

