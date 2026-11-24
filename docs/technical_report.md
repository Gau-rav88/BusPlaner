# Technical Report — Delhi Bus Real-Time Traffic Model & Journey Planner

## Executive Summary

The Delhi Bus Real-Time Journey Planner provides multi-modal route planning and live bus tracking across the Delhi bus network (~2,574 routes, 40,000+ stops). Built upon FastAPI and React/Leaflet, it combines static GTFS schedule data, historical empirical stop-crossing speeds, and upstream live GTFS-RT vehicle telemetry into a production-grade transit solution.

---

## 1. System Engineering & Components

### 1.1 GTFS Data Pipeline (DLM1 Database)
- **Database Engine**: SQLite 3 with spatial indexing and composite foreign key indices.
- **Coverage**: Full Delhi bus network containing 2,574 routes, 59,481 trips, and 40,892 stop locations.
- **True Road Geometry**: Shape polylines (`shapes.txt`) are preserved and indexed by sequence, eliminating straight-line Euclidean artifacts.

### 1.2 Routing Engine: RAPTOR (Round-Based Public Transit Routing)
- **Algorithm**: Round-Based Public Transit Routing (Delling et al.), modified for multi-modal walking transfers.
- **Rounds**:
  - Round 0: Walking from origin coordinate to all accessible boarding stops within walking radius (default 1,500m).
  - Round $k$: Scan routes serving marked stops from Round $k-1$; board earliest feasible trip; update arrival times at subsequent stops.
  - Transfer Phase: Traverse footpath graph between connecting stops within transfer radius (default 500m).
- **Pareto Criteria**:
  1. Earliest arrival time ($t_{arr}$).
  2. Number of transfers ($k$).
  3. Total walking duration ($t_{walk}$).

### 1.3 Prediction Tier Classification Engine
Travel-time estimates for transit legs are tagged with one of four empirical prediction tiers:
1. **Tier 1 (Segment Historical Model)**: Derived from empirical historical stop-crossing observations on the corridor (e.g. North GT Road pilot dataset).
2. **Tier 2 (Corridor Historical Average)**: Corridor-level time-of-day speed profiles when fine-grained segment data is sparse.
3. **Tier 3 (Timetable + Empirical Factor)**: Static timetable adjusted by global empirical peak/off-peak velocity factors.
4. **Tier 4 (Scheduled Timetable Baseline)**: Scheduled timetable duration when no historical observations exist for the corridor.

---

## 2. Real-Time Tracking & Dead Reckoning Engine

### 2.1 Upstream GTFS-RT Telemetry Ingestion
- **Source**: Delhi Transport Stack (DTS) Open Transit Data feed (`VehiclePositions.pb`).
- **Cadence**: 30-second background polling cycle.
- **Validation**:
  - Coordinate range sanity check: Latitude $[28.40, 28.90]$, Longitude $[76.80, 77.40]$.
  - Staleness tagging: $\Delta t \le 20\text{s}$ (Fresh), $20\text{s} < \Delta t \le 120\text{s}$ (Last-Known), $\Delta t > 900\text{s}$ (Stale).

### 2.2 Journey-Specific Matching Pipeline
Candidate vehicles undergo a 5-stage verification gate:
1. **Route Identity**: Vehicle `route_id` must match transit leg route.
2. **Corridor Proximity**: Distance from vehicle coordinates to nearest stop on trip shape must be $\le 1,500\text{m}$.
3. **Direction & Bearing**: Angular difference between vehicle heading and corridor direction must be $\le 120^\circ$.
4. **Sequence & Progress Verification**:
   - Boarding stop sequence must precede alighting stop sequence (`board_seq < alight_seq`).
   - Vehicle must be upstream of boarding stop (`nearest_seq <= board_seq` or within 400m stopping threshold).
   - Approaching distance must be $\le 35\text{km}$ along corridor.
5. **Trip ID Compatibility**: Recognizes operational dispatch IDs (`<route>_<hh>_<mm>_<id>`) and resolves them against static timetable shape sequences.

### 2.3 15-Second Dead Reckoning and GPS Recalibration
- **Step-Ahead Extrapolation**: In between 30-second upstream GPS updates, vehicle positions are advanced every 15 seconds along the route shape polyline according to reported speed.
- **GPS Correction**:
  - When genuine GPS fixes arrive, error ($\epsilon$) between predicted position and observed position is computed.
  - If $\epsilon > 250\text{m}$, the anomaly flag `LARGE_PREDICTION_ERROR` is raised, forward extrapolation is frozen, and the marker snaps to the genuine GPS anchor.
- **Monotonic Progress Safeguard**: Forward movement along the shape polyline is constrained to prevent backward jumps or loop reversal artifacts.

---

## 3. Operational Governance & Integrity

The system enforces operational governance under `DEGRADE` status:
- Discloses that static GTFS calendar dates expired 2024-01-01 and operates under `allow_assumed_recurring=true`.
- Discloses mixed agency fleet attribution (`UNKNOWN_MIXED` across DTC and DIMTS Cluster).
- Clearly distinguishes genuine hardware GPS observations (solid emerald icons) from mathematical dead-reckoned extrapolations (amber lightning icons).
