# Milestone 10: Multi-Dataset Inventory & Integration Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10 Specification  
**Reference Document:** `1732254443852_7. Delhi Buses GTFS Feed_Metadata.pdf`  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

This report establishes a comprehensive inventory and feasibility audit of all datasets associated with the Delhi Transit ecosystem, Open Transit Data (OTD), and the Delhi Transport Stack (DTS). Each dataset is evaluated for schema format, access protocol, integration status within the current system architecture, and technical justification for its adoption or deferral.

---

## 2. Comprehensive Dataset Inventory

| Dataset Identifier | Dataset Name & Scope | Format & Protocol | Access Requirement | Current Integration Status | Technical Justification / Disposition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DS-1 (DLM1)** | **Delhi Buses Static GTFS Feed**<br>Scheduled timetables, routes, stops, trips, calendar. | GTFS Specification (ZIP: CSV tables) | Open download via OTD portal | **Partially Integrated** (via `mdb-1262` DTC mirror) | Loaded into `/tmp/delhi_mdb.db` (6,342 stops, 2,964 routes). Feed expired on 2024-01-01; requires user consent for Assumed Recurring planning. |
| **DS-2 (DLM2)** | **Delhi Buses Real-Time GTFS Feed (`VehiclePositions.pb`)**<br>Live GPS positions, speeds, timestamps. | GTFS-RT Protobuf v2.0 (HTTP GET) | `x-api-key` via Delhi Transport Stack | **Fully Integrated** (Milestone 10) | Active polling in `LiveFeedCollector`. 4,600+ vehicles tracked in real-time, rendered on Leaflet frontend map. |
| **DS-3** | **Historical Bus GPS Archive (October 2026)**<br>31 daily SQLite files with timestamped bus trajectories. | 7z compressed archive of SQLite3 DBs | Local file `/tmp/delhi_archive_header.7z` | **Partially Integrated** (5-day pilot baseline) | 136 ground-truth segment observations across 5 dates (Oct 1–4, 7). Expansion to all 31 days safely gated due to host disk constraints (11.33 GB free vs 88 GB required). |
| **DS-4** | **GTFS-RT Trip Updates Feed (`TripUpdates.pb`)**<br>Real-time arrival delays and stop ETAs. | GTFS-RT Protobuf v2.0 | Not provided by DTS endpoint | **Deferred / Unavailable** | Upstream OTD endpoint only provides `VehiclePositions.pb`. The journey planner predicts arrivals using historical M0 time profiles instead. |
| **DS-5** | **GTFS-RT Service Alerts Feed (`ServiceAlerts.pb`)**<br>Disruptions, diversions, station closures. | GTFS-RT Protobuf v2.0 | Not provided by DTS endpoint | **Deferred / Unavailable** | Upstream DTS feed does not publish service alerts. UI alerts reflect timetable freshness and data limitations instead. |
| **DS-6** | **Delhi Metro Static GTFS / Station Data**<br>DMRC metro train schedules and interchange stations. | GTFS / Open Data CSV | Open download | **Out of Scope** | Project scope governed by PRD v3.0 focuses exclusively on road bus transit and traffic congestion. Multi-modal bus-metro transfer routing reserved for future milestones. |
| **DS-7** | **OpenStreetMap (OSM) Road Network & Footways**<br>Street centerlines, pedestrian paths, and nodes. | OSM XML / PBF / Overpass API | OpenStreetMap API / Tile servers | **Integrated via Approximation** | Standard OSM raster tiles rendered in React-Leaflet. Walking legs calculated using Euclidean distance scaled by 1.3 pedestrian detour factor at 4.5 km/h. |

---

## 3. Deep-Dive Analysis on Critical Datasets

### 3.1 Dataset 1 (Static GTFS: DLM1 vs `mdb-1262`)
- **Strengths:** Provides foundational topology for the RAPTOR multi-criteria routing algorithm. Includes stop sequences and scheduled headways.
- **Limitations:** Completely lacks road geometry (`shapes.txt`). Valid calendar dates ended January 1, 2024.
- **Architectural Handling:** Milestone 6 and 7 introduced the explicit 4-state freshness engine (`CURRENT_VERIFIED`, `EXPIRED`, `ASSUMED_RECURRING`, `UNAVAILABLE`). Under Milestone 10, the static schedule continues to provide route topology while clearly warning users that scheduled departure times reflect recurring historical templates.

### 3.2 Dataset 2 (Live GTFS-RT: `VehiclePositions.pb`)
- **Strengths:** Sub-minute latency, high vehicle density (4,600+ active buses), highly accurate WGS84 coordinates.
- **Limitations:** No compass bearing ($0\%$), no vehicle occupancy or crowd density, no explicit agency tagging in message fields.
- **Architectural Handling:** The backend ingests the raw protobuf stream, validates spatial bounding boxes, flags stale updates ($>900\text{s}$), and renders live buses on the map with clear disclaimers of mixed agency attribution.

### 3.3 Dataset 3 (Historical GPS Trajectories)
- **Strengths:** High-frequency ($10\text{s}$) telemetry enabling empirically calculated segment travel times and hourly speed profiles.
- **Limitations:** Massive storage footprint (~2.7 GB uncompressed per daily SQLite file).
- **Architectural Handling:** Filtered down to 5 representative service dates (weekdays, weekends, national holiday) on the North GT Road pilot corridor. The resulting 136 segment observations power the 5-tier prediction hierarchy (Level 1: Direct Observed; Level 2: Historical M0; Level 3: Experimental RF; Level 4: Scheduled GTFS; Level 5: Static Fallback).

---

## 4. Summary Matrix of Dataset Adoption

```
Dataset                         Status               Reason for Status
─────────────────────────────────────────────────────────────────────────────
Static GTFS (mdb-1262)          ACTIVE (Core)        Provides RAPTOR graph topology.
Live GTFS-RT (Positions)        ACTIVE (Stream)      Provides live bus markers on map.
Historical GPS (5 Days)         ACTIVE (Model)       Powers M0 baseline traffic model.
Historical GPS (Remaining 26d)  GATED (Storage)      Prevent host disk overflow (11.3 GB).
Trip Updates (ETAs)             UNAVAILABLE          Upstream feed omits TripUpdates.pb.
Service Alerts                  UNAVAILABLE          Upstream feed omits ServiceAlerts.pb.
Metro Timetables                EXCLUDED             Out of hackathon scope (Bus focus).
OSM Street Geometries           APPROXIMATED         Geodesic * 1.3 detour factor.
─────────────────────────────────────────────────────────────────────────────
```

---

## 5. Conclusion

The system achieves maximum technical utility from available and accessible datasets:
1. Live vehicle positions (DS-2) successfully complement static routing topology (DS-1).
2. Missing upstream features (TripUpdates and shapes.txt) are replaced by verified historical baseline models and transparent UI geometry disclosures.
3. Storage limitations are handled through rigorous mathematical gating, avoiding system degradation.

