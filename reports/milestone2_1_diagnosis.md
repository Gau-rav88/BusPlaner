# Milestone 2.1 Diagnosis Report: Matching Rate Analysis & Root Causes

**Service Date Audited:** October 1, 2026 (`2026-10-01`)  
**Evaluated Data:** 467,413 GPS pings across 481 vehicles over 10 transit corridors  
**Pipeline Module:** `backend/core/map_matching.py` & `backend/core/trajectory.py`  
**Underlying Metrics Source:** `data/processed/stop_crossings/service_date=2026-10-01/m2_1_expansion_metrics.json`  
**Date of Audit:** November 21, 2026  

---

## 1. Executive Summary: Reconciled Matching & Rejection Breakdown

The Milestone 2.1 expanded evaluation processed 1,624 candidate trajectories segmented from 467,413 raw GPS pings across 10 transit corridors on October 1, 2026. A diagnostic review of the matching outcomes was conducted without loosening quality thresholds.

### Complete Status Reconciliation (Denominator: 1,624 Candidate Trajectories)
- **Total Candidate Trajectories Segmented:** **1,624** ($100.00\%$)
- **Matched Trajectories:** **21** ($1.29\%$)
  - `MATCHED_CONFIDENT` ($\bar{d}_\perp \le 35\text{m}$, monotonic $\ge 95\%$): **8** ($0.49\%$ of total trajectories, $38.10\%$ of matches)
  - `MATCHED_LOW_CONFIDENCE` ($50\text{m} < \bar{d}_\perp \le 65\text{m}$): **13** ($0.80\%$ of total trajectories, $61.90\%$ of matches)
- **Total Rejected Trajectories:** **1,603** ($98.71\%$ of total trajectories)
  - `UNMATCHED_EXCESSIVE_DISTANCE` ($\bar{d}_\perp > 65\text{m}$, mean offset 7–23 km): **1,601** (**$98.58\%$ of all candidate trajectories**, **$99.88\%$ of all rejections**)
  - `UNMATCHED_POOR_FIT` (route coverage $< 10\%$): **2** ($0.12\%$ of all candidate trajectories, $0.12\%$ of all rejections)
  - Other rejection categories (`TOO_FEW_PINGS`, `REVERSE_DIRECTION`, `AMBIGUOUS`): **0** ($0.00\%$)
- **Reconciliation Check:** $21 \text{ matched} + 1,601 \text{ excessive distance} + 2 \text{ poor fit} = 1,624 \text{ total}$ ($1.29\% + 98.58\% + 0.12\% = 100.00\%$).

The investigation demonstrated that this low matching rate across the entire fleet is **not an algorithmic failure of the map matcher**, but the result of three physical and operational realities in the Delhi transit network:
1. **Timetable Version Skew (2022 Static GTFS vs. October 2026 GPS Telemetry):**
   Inspection of `calendar.txt` in the open MobilityData GTFS (`mdb-1262`) revealed validity dates of `2022-01-01` to `2024-01-01`. The GPS archive is from **October 2026**—representing an operational network after major DTC fleet restructuring and large-scale electric bus induction (`DL51EV` series). While stable legacy corridors (such as Route 129A / `1598`, Route 126A / `1616`, Route 103STL / `1657`, and Route 127 / `1547`) maintain direct identifier alignment, many route numbers in 2026 (e.g. cluster series `2182`, `2203`, `2246`) do not exist in the 2022 static GTFS.
2. **Depot Deadheading Under Un-cleared In-Vehicle Identifiers:**
   In Delhi DTC operations, drivers frequently sign into an Electronic Ticket Machine (ETM) at the bus depot (e.g., Bawana, Wazirpur, Mayapuri, Srinivaspuri) and drive a 10–25 km deadhead / pull-out run to their assigned terminal under the same route ID.
3. **Stationary Depot Yard Dwell Emitting Live Telemetry:**
   Buses parked inside depot yards for 1 to 4 hours continuously emit GPS pings every 10 seconds. When mapped against the assigned route, these pings exhibit perpendicular offsets of 1.5 km to 25.0 km.
4. **Strict Quality Gating Enforced by the System:**
   The map matcher correctly rejected off-route and depot observations as `UNMATCHED_EXCESSIVE_DISTANCE`. Loosening the distance threshold would have projected off-route depot parking onto bus corridors, corrupting the travel-time ground truth.

---

## 2. Exhaustive Rejection Breakdown by Route

The table below provides the complete, mathematically reconciled breakdown across all 10 evaluated corridors on October 1, 2026, calculated directly from `data/processed/stop_crossings/service_date=2026-10-01/m2_1_expansion_metrics.json`:

| Route ID | Corridor / Name | Total Trajectories | Matched Confident | Matched Low Conf | Total Matched | Off-Route Dist (`> 65m`) | Poor Fit (`< 10%`) | Match Rate (%) | Primary Operational Cause |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1598** | 129A (Azadpur <-> Jhingola, North GT Road) | 164 | 5 | 9 | **14** | 149 | 1 | **8.54%** | Stable legacy corridor along North GT Road; active revenue trips cleanly matched |
| **1657** | 103STL (Old Delhi Rly <-> Narela, North Arterial) | 198 | 3 | 3 | **6** | 191 | 1 | **3.03%** | North arterial corridor; high off-route deadhead volume from Bawana Depot |
| **1515** | 721 (Manglapuri <-> Kashmere Gate, West-Central) | 148 | 0 | 1 | **1** | 147 | 0 | **0.68%** | Most vehicles reporting `1515` were physically in Bawana/Narela (23 km off-corridor) |
| **1407** | 427 (South Delhi <-> Central Delhi) | 163 | 0 | 0 | **0** | 163 | 0 | **0.00%** | Vehicles operated on non-matching road alignments in South Delhi |
| **1551** | 751 (Dwarka <-> Central Delhi, Southwest) | 123 | 0 | 0 | **0** | 123 | 0 | **0.00%** | Telemetry coordinates located in East Delhi / Kashmere Gate (11 km off-corridor) |
| **1552** | 354 (East Delhi <-> Central Delhi) | 118 | 0 | 0 | **0** | 118 | 0 | **0.00%** | Telemetry coordinates in North-West Delhi |
| **1656** | 534 (Anand Vihar <-> Mehrauli, East-South Ring Road) | 198 | 0 | 0 | **0** | 198 | 0 | **0.00%** | Cross-town deadheading between Wazirpur and Srinivaspuri depots |
| **1714** | 611D (Dhaula Kuan <-> Lajpat Nagar, South Ring Road) | 139 | 0 | 0 | **0** | 139 | 0 | **0.00%** | Bus fleet stationed at Okhla Depot |
| **1830** | 480 (Badarpur <-> Central Delhi, South) | 208 | 0 | 0 | **0** | 208 | 0 | **0.00%** | Telemetry coordinates located in East Delhi (Anand Vihar), 9 km off-corridor |
| **1931** | 125 (Kashmere Gate <-> Alipur, North) | 165 | 0 | 0 | **0** | 165 | 0 | **0.00%** | 2022 GTFS alignment differs from 2026 Alipur highway deviation |
| **Total** | **All 10 Corridors Combined** | **1,624** | **8** | **13** | **21** | **1,601** | **2** | **1.29%** | **Rigorous rejection of false-positive depot/deadhead telemetry** |

### Denominator & Percentage Consistency Verification
- Sum of Total Trajectories across routes: $164 + 198 + 148 + 163 + 123 + 118 + 198 + 139 + 208 + 165 = \mathbf{1,624}$
- Sum of Matched Trajectories across routes: $14 + 6 + 1 + 0 + 0 + 0 + 0 + 0 + 0 + 0 = \mathbf{21}$
- Sum of Off-Route Rejections across routes: $149 + 191 + 147 + 163 + 123 + 118 + 198 + 139 + 208 + 165 = \mathbf{1,601}$
- Sum of Poor Fit Rejections across routes: $1 + 1 + 0 + 0 + 0 + 0 + 0 + 0 + 0 + 0 = \mathbf{2}$
- Overall Match Rate: $21 / 1,624 = \mathbf{1.29\%}$
- Overall Excessive Distance Rate (relative to all candidate trajectories): $1,601 / 1,624 = \mathbf{98.58\%}$
- Overall Excessive Distance Rate (relative to all rejections): $1,601 / 1,603 = \mathbf{99.88\%}$
- Overall Poor Fit Rate (relative to all candidate trajectories): $2 / 1,624 = \mathbf{0.12\%}$
- Overall Poor Fit Rate (relative to all rejections): $2 / 1,603 = \mathbf{0.12\%}$

---

## 3. Vehicle-Level Case Diagnosis

### Case A: Vehicle `DL1PD4213` (Reporting `route_id = 1515`)
- **Reported Route:** 1515 (`721UP`, Manglapuri to Kashmere Gate in West/Central Delhi).
- **Physical Telemetry Location:** Lat `28.8044` to `28.8317`, Lon `76.9592` to `76.9758` (Bawana / Narela Industrial Area in Northwest Delhi).
- **Perpendicular Distance to GTFS Route:** **10,159 meters to 23,673 meters** (10 km to 23.6 km off-route).
- **Root Cause:** The bus was physically assigned to Bawana Depot and operated Northwest feeder runs, but its onboard unit retained `1515` as its static route profile.
- **Evaluation:** Matcher correctly rejected this vehicle. Forcing a match would have caused false-positive travel-time observations.

### Case B: Vehicle `DL1PD6842` (Reporting `route_id = 1656`)
- **Reported Route:** 1656 (`534UP`, Anand Vihar to Mehrauli via Ring Road in East/South Delhi).
- **Physical Telemetry Location:**
  - 04:29 – 05:48: Wazirpur Depot in North Delhi (`lat = 28.6901, lng = 77.1923`).
  - 05:48 – 07:05: Driving south through Central Delhi (Delhi Gate, ITO, India Gate, Lodhi Road).
  - 07:05 – 08:19: Parked at Srinivaspuri / Nehru Nagar Depot in South Delhi (`lat = 28.5863, lng = 77.2516`).
- **Evaluation:** Anand Vihar is on the eastern border of Delhi. The bus never traversed the Anand Vihar corridor, but operated a cross-town depot deadhead. The matcher correctly rejected all 1,720 pings as off-route.

### Case C: Vehicle `DL51EV8634` (Route 1598, `129AUP`) — Genuine Revenue Operation
- **Physical Telemetry Location:** Originating at Azadpur Terminal, proceeding along GT Road through New Sabzi Mandi, Bharola Village, Mahindra Park, Jahangirpuri, GTK Depot, Mukarba Chowk, and Budhpur.
- **Mean Perpendicular Distance:** **33.28 meters**.
- **Monotonic Progression Ratio:** **98.5%**.
- **Evaluation:** Matched with high confidence ($0.70$–$0.85$). Produced 17 stop crossings and 15 consecutive-stop observed segments with verified speeds of 1.3 to 11.6 km/h.

---

## 4. Methodological Conclusions

1. **Thresholds Must Not Be Loosened:** Expanding the lateral acceptance distance from 65m to 500m would not convert depot runs (which are 10–25 km away) into valid revenue trips; it would only introduce lateral noise and corrupt downstream models.
2. **Corridor-Specific Ground Truth:** Reliable stop-crossing ground truth must be derived from verified corridors where contemporary GPS pings align with static GTFS polylines.
3. **Granularity Recommendation:** As evaluated in Section 6.5 of the PRD, because stop-level extraction is strong on aligned corridors but limited across unaligned routes due to timetable version skew, Milestone 3 must operate under the **DEGRADE** strategy (corridor and timepoint aggregation) rather than assuming 100% stop-to-stop network completeness.
