# Milestone 5.1.1 — GTFS Freshness and Timetable Validity Audit Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5.1.1 (GTFS Freshness & Operational Readiness Correction)  
**Governing PRD:** v3.0  
**Governing Decision:** **DEGRADE**  
**Author:** Independent System Auditor  
**Date:** November 21, 2026  

---

## 1. Executive Summary & Critical Issue Identification

During the Milestone 5.1 independent audit, the Delhi transit journey planner was validated algorithmically against the supplied Mobility Database static GTFS dataset (`/tmp/delhi_mdb.db`). However, an audit of the calendar metadata revealed a critical operational limitation:

- **Feed Start Date:** `2022-01-01`
- **Feed Expiration Date:** `2024-01-01`
- **Current Project Horizon:** October – November 2026
- **Elapsed Time Since Expiration:** $\approx 35\text{ months}$ (nearly 3 years)

Treating an expired 2022–2024 timetable feed as a verified current operating schedule for Delhi in late 2026 constitutes schedule misrepresentation. In urban bus systems of Delhi's scale (DTC and DIMTS), route alignments, bus frequency adjustments, fleet additions (such as the widespread introduction of low-floor electric buses), and depot reassignments alter operational reality significantly over a three-year span.

This report establishes the architectural and operational safeguards implemented in Milestone 5.1.1 to handle timetable freshness explicitly, ensuring that stale data is never presented to callers as verified live or current transit service.

---

## 2. Source GTFS Calendar Provenance & Schema Audit

Inspection of the primary GTFS SQLite database (`/tmp/delhi_mdb.db`) confirms the following calendar structure:

```sql
SELECT service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date 
FROM calendar;
```

### Feed Provenance Table
| Field | Value | Operational Implication |
| :--- | :--- | :--- |
| **Data Provider** | Mobility Database (Feed ID: `mdb-1782`) | Sourced from official Delhi Transport Corporation (DTC) static feed archive. |
| **Service ID** | `'1'` | Universal service identifier covering all 2,840 trips and 436 route patterns. |
| **Day-of-Week Vector** | `[1, 1, 1, 1, 1, 1, 1]` | Homogeneous schedule template assigned across all 7 days of the week. |
| **Calendar Start Date**| `'20220101'` (Jan 1, 2022) | Opening boundary of feed validity. |
| **Calendar End Date**  | `'20240101'` (Jan 1, 2024) | Closing boundary of feed validity. Expired prior to project execution dates. |
| **`calendar_dates`**   | **NOT PRESENT** | No holiday exceptions or calendar service modifications are published. |

---

## 3. Four-State Timetable Freshness Architecture

To prevent silent assumption failures or false representations of service availability, the timetable ingestion and routing core now explicitly evaluate requested query dates against a formal state machine:

```
                      [Requested Service Date]
                                 │
                                 ▼
                    [Is Timetable Loaded in RAM?]
                        ├── NO  ──► UNAVAILABLE
                        └── YES
                                 │
                                 ▼
              [Is Date within [2022-01-01, 2024-01-01]?]
                        ├── YES ──► CURRENT_VERIFIED (Historical validity)
                        └── NO
                                 │
                                 ▼
                     [Is Demonstration Mode Allowed?]
                        ├── YES ──► ASSUMED_RECURRING (With mandatory stale warning)
                        └── NO  ──► EXPIRED (Strict rejection, 0 journeys)
```

### Definitions & Behavioral Safeguards

1. **`CURRENT_VERIFIED`:**
   - **Condition:** The requested service date falls strictly within the published validity window (`2022-01-01 <= date <= 2024-01-01`) and feed provenance is documented.
   - **Behavior:** Journeys are routed with `is_verified_current_service = True` and zero stale warnings. Valid for historical schedule reconstruction within the 2022–2023 archive window.

2. **`ASSUMED_RECURRING` (Demonstration Mode):**
   - **Condition:** The requested date is outside feed validity (e.g., October 2026 or November 2026), but demonstration mode is explicitly permitted (`allow_assumed_recurring = True`).
   - **Behavior:** Historical weekly timetable patterns are reused as an unverified demonstration template. Every generated `PlannedJourney` and constituent `TransitLeg` is tagged with `is_verified_current_service = False` and carries an explicit, mandatory caller warning:
     > `STALE TIMETABLE WARNING: The underlying GTFS schedule expired on 2024-01-01. Requested service date (YYYY-MM-DD) is outside feed validity [2022-01-01 to 2024-01-01]. Historical weekly service patterns are being reused under demonstration assumption (ASSUMED_RECURRING). Departures and trip times are NOT verified as currently operating in Delhi in 2026.`

3. **`EXPIRED` (Strict Operating Mode):**
   - **Condition:** The requested service date is outside feed validity and demonstration mode is disabled (`allow_assumed_recurring = False`).
   - **Behavior:** Routing strictly aborts, returning an empty itinerary list (`[]`) and error diagnostics stating that the feed expired and current operating schedules are unverified.

4. **`UNAVAILABLE`:**
   - **Condition:** The database file is missing, empty, or fails to contain active stops or route patterns.
   - **Behavior:** Clean failure returning `[]` and diagnostic state `UNAVAILABLE`.

---

## 4. End-to-End Warning Propagation Verification

To verify that stale timetable warnings cannot be lost during ranking, deduplication, or multi-criteria filtering, we audited journey objects generated across diverse corridors:

```python
# Evaluated via scripts/compile_milestone5_1_1_metrics.py
{
  "test_date": "2026-10-01",
  "timetable_status": "ASSUMED_RECURRING",
  "is_verified_current_service": false,
  "timetable_warning": "STALE TIMETABLE WARNING: The underlying GTFS schedule expired on 2024-01-01...",
  "transit_leg_statuses": ["ASSUMED_RECURRING", "ASSUMED_RECURRING"]
}
```

- **Top-Level Journey Guarantee:** Every `PlannedJourney` exposes `timetable_status`, `timetable_warning`, and `is_verified_current_service`.
- **Transit Leg Guarantee:** Every `TransitLeg` independently maintains `timetable_status` and `is_verified_current_service = False`.
- **API & UI Readiness:** Future API responses (Milestone 6) will serialize these flags at both root and leg levels, allowing client user interfaces to display warning banners without data modification.

---

## 5. Conclusion and Operational Status

The Delhi transit journey planner now enforces strict, transparent freshness boundaries. Expired schedules can no longer masquerade as current verified service. Historical and demonstration capabilities are preserved without compromising factual integrity.

**Operational Status:** **PASS (Governed under DEGRADE)**.

