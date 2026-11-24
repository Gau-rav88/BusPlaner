# Milestone 11.5 — Real-Time Live Feed Temporal Audit (5-Minute Separation)

**Governing specification:** PRD v3.0  
**Current primary database:** DLM1 (`/tmp/delhi_dlm1.db`)  
**Current system status:** `DEGRADE`  
**Previous milestone:** M11.4 — `QUALITY_AUDIT_PASSED_WITH_LIMITATIONS`  
**Evaluation date:** 2026-11-21  

---

## 1. Executive Summary

In Milestone 11.4, three live snapshots were collected only 7 seconds apart. To establish genuine temporal stability without diurnal conflation, this audit collected three independent authenticated GTFS-Realtime (GTFS-RT) snapshots from the Delhi Transport Stack (DTS) separated by **at least 5 minutes (305–322 seconds)**.

### Key Outcomes
- **Temporal Window:** Total observation span of **10.5 minutes (627 seconds)** between 19:46:45 UTC and 19:57:12 UTC.
- **Payload & Vehicle Counts:** Active vehicles fluctuated naturally between **552 and 576 vehicles** ($+2.3\%$ to $-4.2\%$), reflecting authentic operational polling dynamics.
- **Route Matching Denominator:** Between **217 and 227 unique active routes** were observed operating in the live stream.
- **DLM1 Route Alignment:** Across all three snapshots, **100.00% of observed active routes** matched DLM1 static routes in `/tmp/delhi_dlm1.db`.
- **Zero Positions Rejected:** All telemetry satisfied WGS84 bounding box bounds ($[28.2, 29.0]^\circ\text{N}$, $[76.6, 77.6]^\circ\text{E}$) and freshness constraints ($\le 900\text{ s}$).
- **Scope Limitation:** Stability across a 10.5-minute window during off-peak night operations confirms short-term operational health, but does not prove round-the-clock daytime reliability across all peak hours.

---

## 2. Independent Temporal Snapshot Evidence

### Table 1: Temporal Snapshot Telemetry Comparison (Separated by $\ge 5$ Minutes)

| Telemetry Dimension | Snapshot 1 | Snapshot 2 | Snapshot 3 |
|:---|:---:|:---:|:---:|
| **Timestamp (UTC)** | `2026-11-21T19:46:45Z` | `2026-11-21T19:51:50Z` | `2026-11-21T19:57:12Z` |
| **Elapsed Since Previous** | Baseline ($t_0$) | **$305\text{ s}$ ($5.08\text{ min}$)** | **$322\text{ s}$ ($5.37\text{ min}$)** |
| **HTTP Status Code** | 200 OK | 200 OK | 200 OK |
| **Payload Size (Bytes)** | 61,734 bytes | 63,144 bytes | 60,515 bytes |
| **Request Latency** | **0.693 s** | **0.751 s** | **0.685 s** |
| **Raw Protobuf Entities** | 563 | 576 | 552 |
| **Valid Vehicle Positions** | 563 | 576 | 552 |
| **Rejected Positions** | 0 | 0 | 0 |
| **Fresh Vehicles ($\le 900\text{s}$)** | 563 (100.0%) | 576 (100.0%) | 552 (100.0%) |
| **Stale Vehicles ($> 900\text{s}$)** | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| **Min Timestamp Age** | 23 s | 17 s | 29 s |
| **Median Timestamp Age** | 57 s | 124 s | 142 s |
| **Max Timestamp Age** | 899 s | 836 s | 856 s |
| **Observed Active Routes** | **217** | **227** | **218** |
| **DLM1 Matched Routes** | **217** | **227** | **218** |
| **DLM1 Unmatched Routes** | **0** | **0** | **0** |
| **Route Match % (Observed)** | **100.00%** | **100.00%** | **100.00%** |

---

## 3. Analysis of Temporal Differences & Feed Stability

### 3.1 Fleet Dynamics Across the 10.5-Minute Window
1. **Vehicle Churn:** Between Snapshot 1 and Snapshot 2, active vehicles increased from 563 to 576 ($+13$ buses), while between Snapshot 2 and Snapshot 3, active vehicles decreased to 552 ($-24$ buses). This reflects normal depot turn-ins and GPS polling cycles at approximately 01:15 AM to 01:30 AM local time in Delhi.
2. **Route Variations:**
   - In Snapshot 1: 217 active routes.
   - In Snapshot 2: 227 active routes (10 additional routes entered active reporting).
   - In Snapshot 3: 218 active routes.
   - **Static Match Consistency:** Every newly appearing active route was successfully matched in `/tmp/delhi_dlm1.db`. Zero orphaned route IDs appeared across any snapshot.
3. **Median Age Drift:** The median timestamp age shifted from $57\text{ seconds}$ in Snapshot 1 to $124\text{ seconds}$ in Snapshot 2 and $142\text{ seconds}$ in Snapshot 3, confirming that upstream GPS pings are updated in asynchronous batches by the transport authority.

### 3.2 Clarification of the Denominator
The match rate calculation uses the **observed active route denominator**:
$$\text{Route Match \%} = \frac{\text{DLM1 Matched Routes}}{\text{Unique Active Routes in Live Stream}} \times 100\%$$
- Snapshot 1: $\frac{217}{217} = 100.00\%$
- Snapshot 2: $\frac{227}{227} = 100.00\%$
- Snapshot 3: $\frac{218}{218} = 100.00\%$

This demonstrates that DLM1 contains the static definitions for all bus services currently operating on the road. It is **not** a claim that all 2,574 routes in DLM1 operate active vehicles 24 hours a day.

---

## 4. Operational Risk & Degradation Notice

Pursuant to PRD v3.0, the live feed collector operates under governing status **`DEGRADE`**:
1. **Off-Peak Nighttime Limitation:** Night operations capture $\sim 8\%$ of the total Delhi bus fleet (~550 of ~7,000 buses). Day-peak volume and daytime route coverage remain unverified.
2. **Temporal Window Constraint:** Three snapshots across 10.5 minutes prove immediate connectivity and schema stability, but do not guarantee long-term upstream API uptime or uninterrupted daily availability.
3. **Trip Matching Gaps:** The upstream protobuf feed populates `route_id` reliably, but frequently leaves `trip_id` empty or assigned to transient dispatch identifiers, requiring spatial-temporal heuristics for schedule linking.

