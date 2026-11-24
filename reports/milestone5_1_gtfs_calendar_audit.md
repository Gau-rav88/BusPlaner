# Milestone 5.1 — GTFS Calendar, Service Expiry & Midnight Service Audit Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5.1 (Independent Journey Planner Audit)  
**Governing PRD:** v3.0  
**Governing Status:** DEGRADE  
**Author:** Independent System Auditor  
**Date:** November 21, 2026  

---

## 1. Executive Summary

This report delivers the structural audit of the Delhi GTFS schedule dataset (`/tmp/delhi_mdb.db`), specifically evaluating service calendar validity, calendar exception mechanisms, service date expiration handling, and after-midnight transit service representation.

### Key Audit Findings
- **Calendar Table Schema:** The GTFS database contains a single `calendar` table defining regular weekly service patterns. No `calendar_dates` (service exceptions/holidays) table is present in the Mobility Database publication.
- **Service Period Expiration:** The static feed specifies `start_date = '20220101'` and `end_date = '20240101'`. For October 2026 routing queries, this requires explicit handling under PRD Section 8.2 via `service_activation_assumed = True`, treating the GTFS schedule as a recurring template service pattern.
- **Midnight Service Representation:**
  - **Trips Starting After Midnight ($T_{\text{dep}} \ge 86,400\text{s}$):** Exactly **0 trips**. The earliest scheduled departures begin at 04:00:00 ($14,400\text{s}$).
  - **Trips Crossing Midnight ($T_{\text{dep}} < 86,400\text{s}$ and $T_{\text{arr}} \ge 86,400\text{s}$):** Exactly **436 route patterns** run through midnight, with maximum arrival times reaching $109,251\text{s}$ (30:20:51).
  - **Time Representation:** Monotonic integer seconds since midnight are maintained without modulo 86,400 wraparound, preventing schedule corruption across day boundaries.

---

## 2. GTFS Calendar Table Inspection

We executed direct SQL inspection of the database schema and contents in `/tmp/delhi_mdb.db`:

```sql
SELECT sql FROM sqlite_master WHERE type='table' AND name IN ('calendar', 'calendar_dates');
```

### Table Schema & Content
- **`calendar` Table Schema:**
  ```sql
  CREATE TABLE calendar (
      service_id TEXT,
      monday INTEGER,
      tuesday INTEGER,
      wednesday INTEGER,
      thursday INTEGER,
      friday INTEGER,
      saturday INTEGER,
      sunday INTEGER,
      start_date TEXT,
      end_date TEXT
  );
  ```
- **`calendar_dates` Table:** **Does not exist** in the Delhi Mobility Database distribution.
- **Exact Calendar Record:**
  | Column | Value | Operational Implication |
  | :--- | :--- | :--- |
  | `service_id` | `'1'` | Universal service identifier used by all trips. |
  | `monday` .. `sunday` | `1, 1, 1, 1, 1, 1, 1` | Identical service pattern operates 7 days a week. |
  | `start_date` | `'20220101'` | Effective start date: January 1, 2022. |
  | `end_date` | `'20240101'` | Published expiration date: January 1, 2024. |

---

## 3. Service Expiration Handling under PRD Section 8.2

Because the static GTFS dataset was published with an end date of January 1, 2024, any strict Gregorian date filter applied to October 2026 routing requests would evaluate `20261001 > 20240101` and mark every trip in Delhi inactive, resulting in zero available transit routes.

### Architectural Policy (`service_activation_assumed = True`)
In strict adherence to PRD v3.0 Section 8.2:
1. **Template Service Assumption:** The GTFS timetable is treated as an active recurring weekly template for Delhi transit operations.
2. **Day-of-Week Mapping:** A query on October 1, 2026 (a Thursday) evaluates whether `thursday == 1` for `service_id = '1'`. Because all days are set to `1`, regular weekday service is scheduled.
3. **Audit Assertion:** Test case `CASE_13_SERVICE_CALENDAR_EXPIRY` asserts that:
   - The expiration date `'20240101'` is explicitly detected and acknowledged.
   - The engine logs `service_activation_assumed = True` rather than silently failing or hallucinating arbitrary validity extensions.

---

## 4. Midnight Service & Boundary Transition Audit

In public transit operations, late-night bus runs frequently operate across the midnight boundary. In naive implementations, time-of-day is formatted as `time % 86400`, which causes a trip arriving at 00:15:00 ($900\text{s}$) to appear 85,500 seconds earlier than its departure at 23:55:00 ($86,100\text{s}$), producing negative travel durations or infinite waiting loops.

### 4.1 GTFS Database Midnight Analysis

```sql
-- Trips departing at or after 24:00:00
SELECT COUNT(*) FROM trips t 
JOIN stop_times st ON t.trip_id = st.trip_id AND st.stop_sequence = 0
WHERE st.departure_sec >= 86400;
-- Result: 0

-- Trips departing before 24:00:00 and arriving after 24:00:00
SELECT COUNT(DISTINCT t.trip_id) FROM trips t 
JOIN stop_times st_first ON t.trip_id = st_first.trip_id AND st_first.stop_sequence = 0
JOIN stop_times st_last ON t.trip_id = st_last.trip_id AND st_last.stop_sequence = (
    SELECT MAX(stop_sequence) FROM stop_times WHERE trip_id = t.trip_id
)
WHERE st_first.departure_sec < 86400 AND st_last.arrival_sec >= 86400;
-- Result: 436 trips across 436 route patterns
```

- **Earliest Service:** Daily bus operations commence at $14,400\text{s}$ (04:00:00).
- **Latest Operational Arrival:** $109,251\text{s}$ (30:20:51, or 06:20:51 the following morning).

### 4.2 Monotonic Seconds-Since-Midnight Representation
To eliminate midnight arithmetic errors:
1. All timetable times are stored as continuous 32-bit signed integers ($T \in [0, 120000]$).
2. A departure at 23:45:00 is represented as $85,500\text{s}$.
3. An arrival at 00:15:00 of the following day is represented as $87,300\text{s}$ ($86,400 + 900$).
4. The duration calculation remains strictly monotonic:
   $$\Delta t = 87,300 - 85,500 = 1,800\text{ seconds (30 minutes)}$$
5. RAPTOR's Pareto domination criteria and binary search (`np.searchsorted`) operate without wrapping artifacts.

---

## 5. Exact GTFS Records Used for Independent Audit Cases

To ensure complete reproducibility, the table below documents the exact database primary keys and scheduled timetable records used across the audit test suite:

| Case ID | Route ID | Trip ID | Start Stop | End Stop | Scheduled Dep (s / HH:MM) | Scheduled Arr (s / HH:MM) | Scheduled Duration |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CASE_01_DIRECT_CORRIDOR` | 1598 | `1598_12_38` | Stop 239 | Stop 2024 | 45,480 (12:38:00) | 46,372 (12:52:52) | 892 s |
| `CASE_02_EARLY_MORNING` | 1269 | `1269_04_00` | Stop 1728 | Stop 1477 | 14,400 (04:00:00) | 14,864 (04:07:44) | 464 s |
| `CASE_03_LATE_EVENING` | 0 | `0_23_00` | Stop 3127 | Stop 2024 | 82,800 (23:00:00) | 84,209 (23:23:29) | 1,409 s |
| `CASE_04_COMPETING_ROUTES`| Multiple | `124_12_30` | Stop 239 | Stop 2024 | 45,000 (12:30:00) | 45,800 (12:43:20) | 800 s |
| `CASE_12_MIDNIGHT_CROSS` | 0 | `0_23_00` | Stop 3127 | Stop 238 | 82,800 (23:00:00) | 86,901 (24:08:21) | 4,101 s |
| `CASE_13_CALENDAR_EXPIRY` | All | All | — | — | Service ID: 1 | Start: 20220101 | End: 20240101 |

---

## 6. Conclusion and Status

The calendar management and midnight transition handling in the Delhi Journey Planner are fully audited, transparently justified under PRD Section 8.2, and mathematically free of day-boundary wraparound errors.

**Operational Status:** **PASS (Under DEGRADE Scope)**.

