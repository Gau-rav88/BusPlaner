# Milestone 10: Static GTFS Feeds Comparative Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10 Specification  
**Feeds Compared:** MobilityDatabase `mdb-1262` vs Delhi Transport Stack Catalogue (DLM1)  
**Live RT Cross-Reference Snapshot:** 1,413 active routes  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

This report provides a comparative audit between the static GTFS feed currently loaded in the backend database (`/tmp/delhi_mdb.db`, sourced from MobilityDatabase `mdb-1262`) and the official Open Transit Data / Delhi Transport Stack catalogue feed specification (Dataset ID: `DLM1`).

In addition, an empirical cross-reference was executed between the active routes in the live GTFS-RT protobuf stream and the static GTFS route tables.

Key findings:
1. **Feed Provenance & Temporal Expiry:** The loaded feed (`mdb-1262`) represents the Delhi Transport Corporation (DTC) schedule, which expired on **January 1, 2024**.
2. **Entity Scale Comparison:** The newer DLM1 catalogue feed covers 10,559 stops and 2,403 routes (including DIMTS Cluster routes), compared to 6,342 stops and 2,964 routes in `mdb-1262`.
3. **Live Route Overlap:** Of the 1,413 active routes currently observed in the live GTFS-RT feed, **658 routes (46.64%)** match route identifiers in `delhi_mdb.db`, including key study corridors (Route `1598` and Route `1657`).
4. **Missing Road Geometry:** Neither feed contains `shapes.txt`. Both feeds require straight-line stop-to-stop interpolation for map rendering.

---

## 2. Quantitative Feed Comparison

| Dimension | Loaded Database (`mdb-1262`) | DTS Catalogue Specification (`DLM1`) | Delta / Notes |
| :--- | :---: | :---: | :--- |
| **Primary Agency** | Delhi Transport Corporation (DTC) | Mixed (Cluster included, DTC planned) | DLM1 includes private concessionaires. |
| **Total Stops (`stops.txt`)** | 6,342 | 10,559 | +4,217 stops (+66.5%) in DLM1 catalogue. |
| **Total Routes (`routes.txt`)** | 2,964 | 2,403 | -561 route variants (consolidation in DLM1). |
| **Total Trips (`trips.txt`)** | 78,515 | 89,393 | +10,878 trips (+13.9%) in DLM1. |
| **Stop Times (`stop_times.txt`)** | 3,116,420 | 3,600,000+ | Estimated ~15% increase in total arrivals. |
| **Road Geometry (`shapes.txt`)** | **0 (Absent)** | **0 (Absent)** | Neither feed provides road curvature coordinates. |
| **Calendar Validity Start** | 2022-01-01 | Circa 2023–2024 | Historical schedule baseline. |
| **Calendar Validity End** | **2024-01-01 (EXPIRED)** | Unverified continuous updates | Requires Assumed Recurring consent in M6/M7. |

---

## 3. Live GTFS-RT to Static GTFS Route Overlap

During the Milestone 10 live feed validation, all 4,980 vehicle entities were analyzed for route identification:

```
Metric                                         Value       Percentage
──────────────────────────────────────────────────────────────────────
Total Active Live Vehicles Parsed              4,980       100.00%
Unique Transit Routes in Live Stream           1,413       100.00%
Live Routes Matching Static GTFS Database        658        46.64%
Live Routes Not Found in Static GTFS Database    755        53.36%
──────────────────────────────────────────────────────────────────────
Pilot Corridors Status:
- Route 1598 (North GT Road Study Corridor)   MATCHED     ACTIVE (3 buses)
- Route 1657 (Azadpur - Shahdara Corridor)    MATCHED     ACTIVE (2 buses)
- Route 1445 (Historical Pilot Route)          ABSENT      INACTIVE in live snap
──────────────────────────────────────────────────────────────────────
```

### Explanation of the 53.36% Non-Overlap:
1. **Cluster vs DTC Feed Segregation:** The static feed `mdb-1262` is exclusively a DTC schedule export from 2022. The live GTFS-RT feed includes private Cluster routes operated under DIMTS contracts which were never indexed in the DTC static feed.
2. **Post-2024 Network Restructuring:** The Delhi government and Transport Department introduced new electric feeder routes (`DL51EV`), Mohalla bus routes, and adjusted route numbering after January 2024.
3. **Route Suffixing:** The live feed reports raw scheduling trip codes where some route numbers include directional or branch letters (e.g. `3961_20_56_8321`).

---

## 4. Frontend Map Geometry Implications

Because neither `mdb-1262` nor the live GTFS-RT feed contains `shapes.txt`:
1. **Straight-Line Segments:** Bus legs displayed on the Leaflet map connect sequential stop coordinates using straight lines.
2. **Disclaimers:** The frontend UI explicitly labels geometry as "Approximate geometry: Road curvature unrepresented (no shapes.txt in GTFS)" in popups and the floating map legend.
3. **Live Bus Pins:** Live vehicle positions reflect raw GPS coordinates from `VehiclePositions.pb`. Vehicles appear along actual roadways, occasionally deviating visually from the straight-line transit polyline. This distinction is clearly disclosed to hackathon evaluators.

---

## 5. Architectural Recommendations

1. **Retain `delhi_mdb.db` for Hackathon Demonstration:** Replacing the underlying GTFS database mid-project would invalidate existing RAPTOR indexing, baseline model training on Route 1598, and test fixtures.
2. **Preserve `is_matched_to_gtfs` Flag:** The `LiveVehicleItem` schema correctly flags whether a vehicle's `route_id` exists in the local static schedule, allowing clients to distinguish between fully scheduled buses and untracked feeder lines.
3. **Governing Status Confirmation:** The 46.64% static route match and expired calendar validity reinforce the strict governing status of **`DEGRADE`**.

