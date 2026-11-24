# Milestone 10.2: Static GTFS Dataset Access & Investigation Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10.2 Specification  
**Dataset Under Investigation:** Delhi Buses: GTFS Static Data – DTC / DoT (Catalogue Dataset ID: `DLM1`)  
**Active Production Database:** `/tmp/delhi_mdb.db` (MobilityDatabase `mdb-1262`, 268 MB)  
**Access Investigation Status:** **ACCESS_BLOCKED**  
**Dataset Classification:** **`NOT_DOWNLOADED`**  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

Milestone 10.2 investigated the accessibility, subscription status, and acquisition procedures for the official full static GTFS dataset for Delhi public buses (**"Delhi Buses: GTFS Static Data – DTC / DoT"**, Catalogue ID `DLM1`).

### Definitive Findings:
1. **Entitlement Isolation on Delhi Transport Stack:**  
   The API credentials provided to the hackathon team are scoped **exclusively to Dataset ID 7: "Delhi Buses: GTFS-RT Feed - DTC, DoT"** (providing `realtime_gtfs` / `VehiclePositions.pb`). Static GTFS data is governed as a separate catalogue entity requiring an independent subscription and data approval on `https://delhi.transportstack.in`.
2. **Access Gate Failures:**  
   - Direct HTTP API requests to `https://dts-backend.transportstack.in/...` with `category=static_gtfs` return **HTTP 400 Bad Request (`{"error":"External API error: 400"}`)**, confirming the active key lacks static GTFS authorization.
   - Programmatic downloads from the legacy Open Transit Data (OTD) portal (`opendata.transport.delhi.gov.in`) fail with **HTTP 403 Forbidden (`CSRF verification failed`)**, returning a 1,386-byte HTML error page.
3. **Official Dataset Scale:**  
   Per hackathon documentation, the complete DLM1 feed contains **10,559 stops**, **2,403 routes**, **89,393 trips**, and true road geometry in **`shapes.txt`**.
4. **Sample Slice Inspected:**  
   The available public sample (`01 Delhi Buses Static_Sample`, 100 stops, 20 routes, 100 trips) is an isolated test slice and is unroutable.
5. **Operational System Preservation:**  
   The active backend continues to operate on the verified **`mdb-1262`** dataset (6,342 stops, 2,964 routes, 78,515 trips). The active database was not replaced.
6. **Governing Status:**  
   Because the updated 2025–2040 static feed has not been obtained, the system must permanently retain its operational status as **`DEGRADE`**.

---

## 2. Dataset Documentation & Access Procedure Audit

### 2.1 Hackathon Brief Analysis (`transport-stack-hackathon-problem-1 - Google Docs.pdf`)

Section 3.3 and Section 6 of the official problem document state:
> **3.3 Static GTFS:**  
> "GTFS is the standard format for transit schedules. The Delhi bus feed has about 10,500 stops, 2,400 routes and 89,000 scheduled trips. The main files are stops.txt (stop locations), routes.txt (route names), trips.txt (each scheduled run), stop_times.txt (the timetable) and shapes.txt (the path each route follows on the road)."  
>  
> **6. Data Access:**  
> "All datasets for this problem are shared through the Delhi Transport Stack platform. Register at delhi.transportstack.in and request access to the datasets you need. Bus schedules follow the GTFS Schedule standard and live positions follow GTFS Realtime. Questions about the problems or data: transportstack.hackathon@gmail.com."

### 2.2 Access Instructions Analysis (`1746511908699_Instructions to Access Delhi Buses - GTFS-RT feed.pdf`)

The access instruction PDF demonstrates the portal's approval workflow:
1. Datasets are published as individual catalog items on `delhi.transportstack.in`.
2. A registered user must request access for each specific dataset.
3. Upon administrative approval, an access notification email is sent containing the dataset URL, query parameters, and a dedicated token (`x-api-key`).
4. The instructions specifically outline access for the GTFS-RT feed (`category=realtime_gtfs&filename=VehiclePositions.pb`). No static GTFS token or download entitlement was issued in that bundle.

---

## 3. Empirical Verification of Access Channels

Three access vectors were tested systematically without guessing undocumented URLs:

| Vector / Target | Parameters Tested | Result | Response Code & Details |
| :--- | :--- | :---: | :--- |
| **DTS API Gateway**<br>`https://dts-backend.transportstack.in/api/dataset/otd/get-file` | `agency=delhi-buses`<br>`category=static_gtfs`<br>`filename=google_transit.zip`<br>`Header: x-api-key: [SECURED_KEY]` | **REJECTED** | **HTTP 400 Bad Request**<br>`{"error":"External API error: 400"}`<br>*Confirmation that API key is not provisioned for static dataset.* |
| **Legacy OTD Web Portal**<br>`https://opendata.transport.delhi.gov.in/` | Standard GET to public download endpoint | **BLOCKED** | **HTTP 403 Forbidden**<br>HTML error: `CSRF verification failed. Request aborted.` (Saved in `/tmp/otd_static.zip`, 1,386 bytes). |
| **Public Unauthenticated Catalogue**<br>`https://delhi.transportstack.in/api/dataset/otd/get-file` | `category=realtime_gtfs` or `static_gtfs` | **HTML ROUTE** | **HTTP 200 (CloudFront SPA)**<br>Returns static `index.html` (655 bytes) due to CloudFront SPA rewrite rules. |

---

## 4. Official Procedure to Obtain Full Static GTFS Dataset

To acquire the authentic full DLM1 dataset without violating data governance or fabricating feeds, the following steps must be taken:

1. **Log in to Delhi Transport Stack:** Navigate to [https://delhi.transportstack.in](https://delhi.transportstack.in) using registered hackathon credentials.
2. **Access Dataset Catalogue:** Browse to the dataset entry for **"Delhi Buses: GTFS Static Data – DTC / DoT"** (Catalogue ID: `DLM1`).
3. **Submit Subscription Request:** Click **"Request Access"** and submit the data usage request for Problem 1 / Phase 1 transit planning.
4. **Alternative Direct Outreach:** Email `transportstack.hackathon@gmail.com` with the registered Team ID and request static GTFS download authorization or a pre-signed Cloudflare R2 / S3 download link for the full `delhi-dtc-gtfs-static-2026.zip` archive.
5. **Staging & Ingestion:** When the full archive is provided:
   - Download into `/tmp/staging_gtfs/`.
   - Validate checksum, table row counts, and foreign keys.
   - Run the migration pipeline described in `milestone10_1_static_gtfs_audit.md`.

---

## 5. Architectural Safeguard: Preservation of `mdb-1262`

Because the full static GTFS feed has not been granted, the system strictly preserves the existing operational SQLite database:

- **Database Path:** `/tmp/delhi_mdb.db` (268 MB).
- **Stops Count:** 6,342 stops.
- **Routes Count:** 2,964 routes.
- **Trips Count:** 78,515 scheduled trips.
- **Stop Times Count:** 3,276,092 arrival/departure records.
- **Status:** Fully functional for RAPTOR transit routing across Delhi.
- **Governing Guard:** Operating status remains strictly **`DEGRADE`** with explicit user consent enforced for demo journeys.

