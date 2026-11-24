# Milestone 5 Routing Validation Report: Functional Correctness & Edge Cases

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5 – Journey Planner & RAPTOR Implementation  
**Status:** COMPLETE (Under Governing Status DEGRADE)  
**Date:** 2026-11-21  

---

## 1. Overview and Scope

This report documents the rigorous functional validation of the RAPTOR routing implementation across all required operational modes and edge cases, as defined in **PRD v3.0 Section 8** and the Milestone 5 specification:
1. **Direct journeys (Round 1 / 0 transfers)**
2. **One-transfer journeys (Round 2 / 1 transfer)**
3. **Two-transfer journeys (Round 3 / 2 transfers)**
4. **Coordinate-to-coordinate routing**
5. **Stop-to-stop routing**
6. **Departure time selection & time continuity**
7. **Strict transfer buffer enforcement ($\ge 120$ seconds)**
8. **Post-midnight GTFS departures ($t \ge 86400$ seconds)**
9. **No-service and unreachable destination handling**
10. **Mathematical Journey-Time Accounting Identity verification**

---

## 2. Validation Test Suite Summary

The evaluation was executed across 50 diverse queries spanning the Delhi transit network, producing 76 verified itineraries in `data/processed/milestone5_metrics.json`. All 12 automated unit and integration tests in `backend/tests/test_milestone5.py` passed with 100% compliance.

| Test Case | Description | Denominator | Violations / Failures | Pass Rate | Status |
|---|---|---:|---:|---:|:---:|
| `test_timetable_loading_and_patterns` | Timetable load, pattern grouping, KDTree | 6,342 stops | 0 | 100.0% | PASS |
| `test_direct_journey_routing` | Direct bus routing on North GT Road | 8 queries | 0 | 100.0% | PASS |
| `test_one_transfer_journey_routing` | Single-transfer connection | 12 queries | 0 | 100.0% | PASS |
| `test_two_transfer_journey_routing` | Two-transfer network routing | 10 queries | 0 | 100.0% | PASS |
| `test_coordinate_to_coordinate_routing` | End-to-end access/egress walking | 5 queries | 0 | 100.0% | PASS |
| `test_transfer_buffer_enforcement` | Minimum buffer $\ge 120$s | 44 transfers | 0 | 100.0% | PASS |
| `test_after_midnight_gtfs_trips` | Trips with $t \ge 86400$s | 3 queries | 0 | 100.0% | PASS |
| `test_no_service_and_unreachable_cases` | Invalid stop IDs & out-of-bounds coords | 4 queries | 0 | 100.0% | PASS |
| `test_journey_time_accounting_identity` | Discrepancy $\equiv 0.0$s | 76 journeys | 0 | 100.0% | PASS |
| `test_prediction_hierarchy_integration` | 4-tier prediction & confidence tags | 76 journeys | 0 | 100.0% | PASS |
| `test_detour_factor_safety_and_dwell` | 1.262 restricted, no double dwell | 76 journeys | 0 | 100.0% | PASS |
| `test_ranking_strategies_and_dedup` | Ranking & Pareto deduplication | 15 queries | 0 | 100.0% | PASS |

---

## 3. Case Studies and Detailed Trace Logs

### 3.1 Direct Corridor Journey (North GT Road)
- **Origin:** Stop 239 (*Azad Pur Terminal*)
- **Destination:** Stop 247 (*Mukarba Chowk*)
- **Departure Time:** $45,000.0\text{s}$ (12:30:00 IST)
- **Result:**
  - Route ID: `1026` (Trip `1026_12_33`, Pattern 29)
  - Boarding: Stop 239 at $45,180.0\text{s}$ (Initial Wait: $180.0\text{s}$)
  - Alighting: Stop 247 at $46,072.0\text{s}$ (Ride Time: $892.0\text{s}$)
  - Total Journey Time: $1,072.0\text{s}$ (17 min 52 sec)
  - Transfers: $0$
  - Accounting Discrepancy: $0.0000\text{s}$

### 3.2 One-Transfer Journey with Footpath Transfer
- **Origin:** Stop 239 (*Azad Pur Terminal*)
- **Destination:** Stop 1 (*Narela Sector A-9*)
- **Departure Time:** $30,000.0\text{s}$ (08:20:00 IST)
- **Result:**
  - **Leg 1 (Transit):** Board Route 124 (Trip `124_08_20`) at Stop 239 at $30,000.0\text{s}$, alight at Stop 240 (*New Sabzi Mandi*) at $30,215.0\text{s}$ (Ride Time: $215.0\text{s}$).
  - **Leg 2 (Transfer Wait):** Board connecting Route 111 (Trip `111_08_35`) at Stop 240 at $30,348.0\text{s}$.
    $$\text{TransferWait} = 30,348.0 - 30,215.0 = 133.0\text{s} \ge 120.0\text{s}$$
  - **Leg 3 (Transit):** Travel along Route 111 to Stop 1, alighting at $35,311.0\text{s}$.
  - Total Journey Time: $5,311.0\text{s}$ (88 min 31 sec)
  - Transfers: $1$
  - Accounting Discrepancy: $0.0000\text{s}$

### 3.3 Coordinate-to-Coordinate Journey
- **Origin Coordinate:** $(28.715^\circ\text{N}, 77.181^\circ\text{E})$ (Residential area near Azadpur)
- **Destination Coordinate:** $(28.735^\circ\text{N}, 77.165^\circ\text{E})$ (Commercial area near Mukarba Chowk)
- **Departure Time:** $45,000.0\text{s}$ (12:30:00 IST)
- **Result:**
  - **Access Walk:** Walk $718.6\text{ m}$ from origin coordinate to Stop *Azadpur*. Duration: $747.3\text{s}$ ($12\text{ min } 27\text{ sec}$). Reaches platform at $45,747.3\text{s}$.
  - **Initial Wait:** Bus departs platform at $46,381.0\text{s}$. Wait duration: $633.7\text{s}$.
  - **Transit Ride:** Travel to Stop *Jahangirpuri K Block*. Ride duration: $866.5\text{s}$ (Level 1 Direct Observed prediction).
  - **Egress Walk:** Walk $588.1\text{ m}$ from *Jahangirpuri K Block* to destination coordinate. Duration: $611.7\text{s}$ ($10\text{ min } 12\text{ sec}$).
  - **Total Journey Time:** $2,859.1\text{s}$ ($47\text{ min } 39\text{ sec}$).
  - **Accounting Check:**
    $$\begin{aligned}
    \text{Sum} &= 747.32 + 633.68 + 866.46 + 0.0 + 0.0 + 611.67 = 2,859.13\text{s} \\
    \text{Total} &= 2,859.13\text{s} \\
    \text{Discrepancy} &= 0.0000\text{s}
    \end{aligned}$$

---

## 4. Edge Cases and Defensive Boundaries

### 4.1 Post-Midnight Service Continuity
In GTFS, trips running past midnight record arrival and departure times exceeding $86,400\text{s}$ (e.g., $24:15:00 = 87,300\text{s}$; $25:30:00 = 91,800\text{s}$). A naive modulo $86,400$ implementation causes midnight departures to appear earlier than evening departures, creating negative wait times and broken backtrack paths.
- **Verification:** Evaluated Pattern 0, which boards at Stop 3127 at $82,800.0\text{s}$ (23:00:00) and crosses midnight to alight at Stop 238 at $86,901.0\text{s}$ (24:08:21 / 00:08:21).
- **Result:** Departure $82,680.0\text{s}$, Arrival $86,901.0\text{s}$, Total $4,221.0\text{s}$. The engine preserved linear time order across midnight without wraparound errors.

### 4.2 Minimum Transfer Buffer ($\ge 120\text{s}$) Enforcement
Under heavy traffic, tight 30-second transfers fail in reality. The planner guarantees that in Round $k > 1$, trip boarding strictly requires:
$$\text{dep}(t, i) \ge \tau_{k-1}(s) + \text{min\_transfer\_buffer\_s} \quad (120.0\text{s})$$
- **Verification:** Across all 44 multi-leg transfer connections evaluated in the benchmark, zero connections had transfer wait $< 120.0\text{s}$. The minimum observed transfer wait was $120.0\text{s}$, and the median was $295.5\text{s}$.

### 4.3 Unreachable and Out-of-Bounds Queries
- **Non-existent Stop:** Querying an invalid stop ID (e.g., `"999999"`) cleanly returns an empty list `[]` without unhandled exceptions.
- **Remote Out-of-Coverage Coordinate:** Querying coordinates in the Thar Desert $(25.0^\circ\text{N}, 70.0^\circ\text{E})$ where no transit stops exist within $1,500\text{m}$ returns `[]` immediately without failing.

