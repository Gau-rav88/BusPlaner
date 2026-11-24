# Milestone 10: GTFS-RT Telemetry & Schema Validation Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10 Specification  
**Dataset Analyzed:** `VehiclePositions.pb` (Delhi Transport Stack)  
**Sample Entity Count:** 4,980 entities  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

This report presents an empirical protobuf schema audit of the Delhi Transport Stack live GTFS-RT stream (`VehiclePositions.pb`), collected using the authenticated API key. The feed was probed, decoded, and analyzed across coordinate boundaries, temporal freshness, speed profiles, fleet registration patterns, and agency attributions.

Key findings:
- **Vehicle Count:** 4,980 vehicle positions parsed in a single snapshot.
- **Geographic Precision:** 99.8% of coordinates fall strictly within the Delhi NCT bounding box ($28.30^\circ\text{N} \le \text{lat} \le 28.95^\circ\text{N}$, $76.80^\circ\text{E} \le \text{lon} \le 77.45^\circ\text{E}$).
- **Temporal Freshness:** 98.9% of telemetry pings are fresher than 5 minutes; 99.96% are fresher than 15 minutes.
- **Speed Reporting:** Speeds are reported in m/s (mean 10.8 m/s = 38.9 km/h), but compass bearing is completely absent ($0 / 4,980$).
- **Agency Attribution:** Explicit agency metadata is absent from the protobuf feed. Due to mixed electric and CNG fleet operations across DIMTS and DTC, agency coverage is categorized as `UNKNOWN_MIXED`.

---

## 2. Protobuf Schema Fields Audit

Each entity in the decoded protobuf was inspected against the standard GTFS-RT specification (`google.transit.gtfs_realtime_pb2`):

| Schema Field | Path in Protobuf | Present in Feed? | Completeness | Observational Characteristics |
| :--- | :--- | :---: | :---: | :--- |
| `entity.id` | `FeedEntity.id` | **Yes** | 100.0% (4,980/4,980) | Identical to vehicle registration number (e.g. `DL1PD5209`). |
| `vehicle.id` | `VehicleDescriptor.id` | **Yes** | 100.0% (4,980/4,980) | Standard Delhi vehicle registration string. |
| `trip.route_id` | `TripDescriptor.route_id` | **Yes** | 100.0% (4,980/4,980) | Transit route identifier (e.g. `1598`, `1657`, `3961`). |
| `trip.trip_id` | `TripDescriptor.trip_id` | **Yes** | 100.0% (4,980/4,980) | Scheduled trip ID (e.g. `1598_20_36_2011`). |
| `position.latitude` | `Position.latitude` | **Yes** | 100.0% (4,980/4,980) | WGS84 decimal degrees (6 decimal place precision). |
| `position.longitude`| `Position.longitude` | **Yes** | 100.0% (4,980/4,980) | WGS84 decimal degrees (6 decimal place precision). |
| `position.speed` | `Position.speed` | **Yes** | 100.0% (4,980/4,980) | Speed in meters per second (m/s). |
| `position.bearing` | `Position.bearing` | **No** | **0.0% (0/4,980)** | Completely unpopulated in feed. |
| `position.odometer`| `Position.odometer` | **No** | 0.0% (0/4,980) | Absent. |
| `timestamp` | `VehiclePosition.timestamp` | **Yes** | 100.0% (4,980/4,980) | UTC Unix timestamp of device GPS fix. |
| `congestion_level`| `VehiclePosition.congestion_level`| **No** | 0.0% (0/4,980) | Absent. |
| `occupancy_status`| `VehiclePosition.occupancy_status` | **No** | 0.0% (0/4,980) | Absent. |
| `agency_id` | `TripDescriptor.agency_id` | **No** | 0.0% (0/4,980) | Absent; not encoded in protobuf. |

---

## 3. Geographic Coordinate Validation

The backend filters coordinates against the official Delhi NCT bounding box:
- **Latitude limits:** $28.30^\circ\text{N}$ to $28.95^\circ\text{N}$
- **Longitude limits:** $76.80^\circ\text{E}$ to $77.45^\circ\text{E}$

### Spatial Distribution Statistics:
- **Min Latitude:** $28.3090^\circ\text{N}$
- **Max Latitude:** $28.8789^\circ\text{N}$
- **Min Longitude:** $76.8407^\circ\text{E}$
- **Max Longitude:** $77.4419^\circ\text{E}$
- **Valid In-Bounds Coordinates:** 4,970 / 4,980 (99.80%)
- **Out-of-Bounds Coordinates:** 10 / 4,980 (0.20%) — Buses situated in outer NCR satellite extensions (e.g. Faridabad, Gurugram border crossings, or Kundli border). These are safely filtered out by the collector.

---

## 4. Temporal Freshness & Staleness Analysis

The PRD establishes a strict staleness threshold: pings older than **900 seconds (15 minutes)** must be rejected from active real-time operational status.

```
Age Bracket                 Count     Percentage    Cumulative %
─────────────────────────────────────────────────────────────────
0 – 60 seconds (Very Fresh) 3,745       75.20%         75.20%
61 – 180 seconds (Fresh)     988       19.84%         95.04%
181 – 300 seconds (Moderate)  192        3.86%         98.90%
301 – 900 seconds (Aging)      53        1.06%         99.96%
> 900 seconds (Stale)           1        0.02%        100.00%
Future Timestamp (Clock Drift)  1        0.02%        100.00%
─────────────────────────────────────────────────────────────────
Total Parsed Entities:      4,980      100.00%
```

- **Median Ping Age:** 38 seconds.
- **Mean Ping Age:** 54.3 seconds.
- **Clock Drift Detected:** 1 ping showed a timestamp 4 seconds ahead of server UTC clock; bounded and tolerated as harmless network drift.
- **Conclusion:** The live stream demonstrates exceptional temporal freshness, with over 95% of positions under 3 minutes old.

---

## 5. Speed Distribution

Speed is transmitted in meters per second ($m/s$) and converted by the collector to kilometers per hour ($km/h$):

- **Stationary Vehicles ($0\text{ km/h}$):** 412 vehicles (8.27%) — buses at terminals, traffic lights, or depot layovers.
- **City Transit Speeds ($1\text{ to }40\text{ km/h}$):** 2,341 vehicles (47.01%) — standard urban mixed traffic.
- **Arterial Corridor Speeds ($41\text{ to }60\text{ km/h}$):** 1,819 vehicles (36.53%) — Ring Road, Outer Ring Road, and GT Road segments.
- **High-Speed Bypass Corridors ($>60\text{ km/h}$):** 408 vehicles (8.19%) — elevated corridors (Barapullah, Delhi-Meerut Expressway).
- **Mean Operational Speed:** $38.9\text{ km/h}$ ($10.8\text{ m/s}$).
- **Maximum Observed Speed:** $90.7\text{ km/h}$ ($25.2\text{ m/s}$).

---

## 6. Fleet Registration & Agency Analysis

### 6.1 Registration Prefix Distribution

Vehicle identifiers correspond directly to Delhi Transport Department registration plates:

| Registration Prefix | Sample Format | Count | Share | Fleet Vehicle Category |
| :--- | :--- | :---: | :---: | :--- |
| **`DL1PD`** | `DL1PD5209` | 3,477 | 69.82% | Standard 12-meter low/semi-low floor CNG buses (DIMTS Cluster & DTC fleets). |
| **`DL51EV`** | `DL51EV3741` | 871 | 17.49% | Zero-emission low-floor Electric buses (Tata/JBM operating across DTC and DIMTS). |
| **`DL51GD`** | `DL51GD1024` | 501 | 10.06% | Midi CNG buses deployed on narrow/feeder routes. |
| **`DL1PE`** | `DL1PE0412` | 130 | 2.61% | Inter-state and express cluster services. |
| **Other** | Miscellaneous | 1 | 0.02% | Maintenance / auxiliary vehicle. |

### 6.2 Agency Coverage Audit (`UNKNOWN_MIXED`)

The hackathon documentation claims the feed covers the Cluster fleet with DTC data coming soon. However:
1. `agency_id` is **not present** anywhere in the protobuf messages.
2. The registration series `DL51EV` represents modern electric buses operated by both DTC and private concessionaires under the DIMTS Cluster model.
3. No external official lookup table mapping registration plate to operating concessionaire or depot was provided in the hackathon bundle.

**Governing Determination:** The backend reports `agency_coverage: "UNKNOWN_MIXED"` across all API endpoints and UI displays. Claiming exclusive Cluster or complete DTC coverage would be empirically unsupported.

