# System Limitations & Known Constraints — Delhi Bus Journey Planner

This document provides transparent disclosure of known limitations, environmental constraints, and edge-case behaviors in the Delhi Bus Real-Time Journey Planner.

---

## 1. Static GTFS Schedule Expiration (Calendar Dates)

- **Root Cause**: The official static GTFS schedule released by the Delhi Government specifies service calendar availability ending on `2024-01-01`.
- **Mitigation & Disclosure**:
  - The system operates under the explicit operational governance status: `DEGRADE`.
  - Queries for current or future dates (e.g. 2026) require `allow_assumed_recurring=true`.
  - When `allow_assumed_recurring=false`, the API returns a strict `400 EXPIRED_TIMETABLE` with explanatory diagnostic disclosure.
  - The UI displays an amber warning banner on every journey card disclosing the assumed recurring calendar basis.

---

## 2. GTFS-RT Trip ID Discrepancy (Operational Dispatch vs Timetable)

- **Root Cause**: The Delhi Transport Stack (DTS) live GTFS-RT feed emits operational dispatch identifiers for `trip_id` (e.g. `3667_23_41_6484`), whereas the static GTFS schedule uses timetable trip IDs (e.g. `1000_FULL_06_10`).
- **Impact**: Strict string equality matching between live `trip_id` and static `trip_id` yields 0% matches across the fleet.
- **Resolution**:
  - The matching engine (`JourneyBusMatcher`) projects vehicle coordinates directly onto GTFS route shape polylines and validates progress against stop sequences (`stop_times.txt`).
  - Operational dispatch IDs prefixed with the route number (e.g. `3667_*`) are verified as dispatch trips on that route.

---

## 3. Real-Time Fleet Coverage & Temporal Density

- **Root Cause**: The live GTFS-RT feed typically reports ~1,000 to ~2,200 active vehicles across Delhi at any given time. However, Delhi operates over 2,500 distinct route patterns.
- **Impact**:
  - High-frequency trunk corridors (e.g., Route 641, 101, 113, 1558, 3475) have 15 to 40 verified live buses active concurrently.
  - Minor branch routes or routes operating late at night / during off-peak hours may have 0 active buses transmitting GPS.
- **Handling**:
  - When zero verified live buses are available for a planned journey, the system avoids generating false recommendations.
  - An amber diagnostic banner clearly informs the user why no live buses appear (e.g., *0 active buses reporting in live feed*, or *buses active on route but already past boarding stop*).
  - Users can click **"Show All Nearby Buses on Map"** to inspect all general fleet traffic in the surrounding area.

---

## 4. Mixed Agency Fleet Attribution

- **Observation**: Vehicles in the live feed are operated across DTC (Delhi Transport Corporation) and DIMTS (Delhi Integrated Multi-Modal Transit System Cluster).
- **Limitation**: The upstream GTFS-RT feed does not consistently segregate vehicle telemetry by agency.
- **Attribution**: The system designates agency coverage as `UNKNOWN_MIXED` across status payloads and API envelopes.

---

## 5. Dead Reckoning Drift During Congestion

- **Mechanism**: The 15-second dead reckoning engine advances vehicles along the GTFS shape polyline using the vehicle's last reported speed.
- **Limitation**: If a vehicle encounters sudden, unpredicted traffic congestion between 30-second GPS fixes, estimated coordinates may lead actual vehicle progress by up to 100–200 meters.
- **Safeguard**:
  - Predictions are constrained to a maximum age of 120 seconds.
  - When a genuine GPS fix arrives, accumulated error is calculated; if error exceeds 250m (`LARGE_PREDICTION_ERROR`), forward extrapolation is halted and the marker is pinned to the genuine GPS anchor.
