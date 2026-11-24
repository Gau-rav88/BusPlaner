# Milestone 8: Live GTFS-RT Feed Readiness & Access Gate Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Phase:** Milestone 8 — Live Feed Readiness, Time Profiles & Conditional Integration  
**Operational Status:** **DEGRADE**  
**Feed Availability Classification:** **`AUTH_REQUIRED`**  
**Date:** November 2026  

---

## 1. Executive Summary

In accordance with PRD v3.0 Milestone 8, the **Live Feed Access Gate** was executed as a mandatory first step to investigate whether the official Delhi GTFS-Realtime (GTFS-RT) vehicle positions feed is genuinely accessible and operational.

### Mandatory Investigation Checklist:
1. **API Key Requirement:** **YES**. The live GTFS-RT feed endpoint requires an authenticated `x-api-key` header.
2. **Environment Variable Availability:** **NO**. `DELHI_TRANSPORTSTACK_API_KEY` is not configured in the execution environment or `.env`.
3. **Endpoint Probing Response:**
   - Probing the upstream backend endpoint (`https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb`) without credentials returned:
     `HTTP/2 401 Unauthorized`  
     `{"error":"API key is required. Please provide x-api-key header."}`
   - Probing with an invalid or dummy key returned:
     `HTTP/2 401 Unauthorized`  
     `{"error":"Invalid API key"}`
   - Probing the portal alias (`https://delhi.transportstack.in/...`) returned the React portal HTML wrapper, confirming that the actual data stream is served strictly via `dts-backend.transportstack.in` with API key enforcement.
4. **Protobuf Data Availability:** **UNAVAILABLE** due to authentication requirement.
5. **Coverage & Freshness:** **UNAVAILABLE** without credentials.
6. **Bypass / Fake Data Policy:** **Zero bypass attempted.** No credentials were asked to be committed to version control, and no fake live vehicle positions were generated.

**Official Classification: `AUTH_REQUIRED`**

Per Section 2 of Milestone 8 instructions:  
> *"If authentication is required and no valid credential is configured, do not attempt to bypass authentication. If the feed is unavailable, continue with historical time-profile work. Do not implement fake live data or claim live integration."*

---

## 2. Technical Evidence & Network Probe Logs

### 2.1 Live Network Probe without Credentials
```http
GET /api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb HTTP/2
Host: dts-backend.transportstack.in
User-Agent: curl/8.7.1
Accept: */*

HTTP/2 401 
date: Sat, 21 Nov 2026 12:18:20 GMT
content-type: application/json
content-length: 65
server: gunicorn
vary: Accept, origin
allow: GET, HEAD, OPTIONS
x-frame-options: DENY
x-content-type-options: nosniff
x-xss-protection: 1; mode=block
referrer-policy: same-origin

{"error":"API key is required. Please provide x-api-key header."}
```

### 2.2 Live Network Probe with Invalid Credentials
```http
GET /api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb HTTP/2
Host: dts-backend.transportstack.in
x-api-key: test_invalid_key_probe
User-Agent: curl/8.7.1
Accept: */*

HTTP/2 401 
date: Sat, 21 Nov 2026 12:18:27 GMT
content-type: application/json
content-length: 27
server: gunicorn

{"error":"Invalid API key"}
```

---

## 3. Feed Availability Classification Matrix

| Feed State | Definition | Observed Reality | Classification Verdict |
| :--- | :--- | :--- | :--- |
| `AVAILABLE_VALIDATED` | Endpoint operational, returns valid binary protobuf, fresh timestamps, GTFS match verified. | Not reached (Requires valid x-api-key). | **NO** |
| `AVAILABLE_PARTIAL` | Endpoint operational, but partial vehicle coverage or empty feed message. | Not reached. | **NO** |
| `AUTH_REQUIRED` | Upstream endpoint requires authentication header (`x-api-key`); missing or rejected with HTTP 401. | **Observed**: Upstream returns HTTP 401 with `"API key is required"`. | **YES (CONFIRMED)** |
| `UNAVAILABLE` | Endpoint down, timeout, connection refused, or HTTP 5xx. | Endpoint is reachable and healthy (Gunicorn responds in 340ms). | **NO** |
| `INVALID_DATA` | Endpoint returns HTTP 200 but payload is HTML, corrupt bytes, or unparseable protobuf. | Not reached without auth. | **NO** |

---

## 4. Setup Instructions & Environment Configuration

To enable live GTFS-RT streaming when deploying in an environment with authorized credentials:

1. **Obtain API Key:**
   - Register a free developer account at [https://delhi.transportstack.in](https://delhi.transportstack.in).
   - Navigate to **Dataset 7: Delhi Buses (GTFS-RT feed)**.
   - Request API access. The API key is issued by the Delhi Transport Department via email.
2. **Configure Environment:**
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Set the following variables:
     ```env
     DELHI_TRANSPORTSTACK_API_KEY=<your_transportstack_api_key>
     DELHI_GTFS_RT_URL=https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb
     LIVE_FEED_ENABLED=true
     LIVE_POLL_INTERVAL_SECONDS=30
     ```
3. **Operational Safeguard:**
   - Never commit `.env` or API keys to git. `.gitignore` is configured to exclude `.env`.
   - In the absence of `DELHI_TRANSPORTSTACK_API_KEY`, the platform automatically operates in **Historical Baseline Mode (DEGRADE)**.

---

## 5. Architectural Decision

Because the feed is classified as **`AUTH_REQUIRED`**, the system:
1. Leaves live polling and real-time speed fusion **disabled**.
2. Exposes live status honestly via `GET /api/v1/live/status` returning `feed_availability_status: "AUTH_REQUIRED"`, `feed_enabled: false`.
3. Displays `Live Feed: Auth Required (Disabled)` on the web interface header.
4. Executes all journey planning and transit predictions using the validated historical baseline and RAPTOR timetable engine under **DEGRADE** operational status.

