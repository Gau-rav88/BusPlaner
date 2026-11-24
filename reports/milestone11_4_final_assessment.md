# Milestone 11.4 — Final Assessment & Quality Audit Synthesis

**Governing specification:** PRD v3.0  
**Current primary database:** DLM1 (`/tmp/delhi_dlm1.db`)  
**Current system status:** `DEGRADE`  
**Previous milestone:** M11.3 — `CUTOVER_SUCCESSFUL_WITH_LIMITATIONS`  
**Audit verdict:** `QUALITY_AUDIT_PASSED_WITH_LIMITATIONS`  
**Evaluation date:** 2026-11-21  

---

## 1. Milestone Overview & Audit Scope

Milestone 11.4 was convened to execute an empirical post-cutover audit of the newly active primary database (`/tmp/delhi_dlm1.db`). The audit investigated test-suite completeness, journey planning correctness and timing anomalies, live-feed vehicle matching, historical pilot observation integrity, and repository-wide credential security.

### Evaluated Milestone Verdict:
$$\mathbf{QUALITY\_AUDIT\_PASSED\_WITH\_LIMITATIONS}$$

### Overall System Operational Status:
$$\mathbf{DEGRADE}$$

---

## 2. Audit Findings Synthesis Across Workstreams

### 2.1 Backend Test-Suite Resolution (Section 1)
- **Inventory:** 151 total pytest tests defined across 12 test files.
- **DLM1 Pytest Run:** `pytest backend/tests/ -v` with `DB_PATH=/tmp/delhi_dlm1.db` resulted in **141 passed**, **10 failed**, 0 skipped, 0 errored (Exit code `1`).
- **Failure Root Cause:** The 10 failing tests are legacy-bound assertions expecting the legacy `mdb-1262` calendar validity dates (`2022-01-01` to `2024-01-01`) and legacy stop sequences (`239` $\to$ `2024`). In DLM1, the calendar is valid from `2025-01-01` to `2040-01-01`.
- **Targeted Legacy Verification:** `pytest` against `DB_PATH=/tmp/delhi_mdb.db` on all 3 legacy test files (`test_milestone6_api.py`, `test_milestone6_1_audit.py`, `test_milestone8_api.py`) passed **34 of 34 tests (100.0%)** with exit code `0`.
- **DLM1 Integration Tests:** `pytest backend/tests/test_milestone11_1_dlm1.py` passed **12 of 12 tests (100.0%)** with exit code `0`.

### 2.2 The 35,324-Second Transfer Journey (Section 2)
- **Reproduction:** Origin Stop `2280` (*Nehru Nagar*), Destination Stop `5321` (*Alipur Blk.(BDO Office)*), Departure `08:00:00`.
- **Timing & Accounting:** Total duration is $35,324.0\text{ s}$ ($9.81\text{ hours}$). Time conservation is exact:
  $$\Delta = 35,324.0 - (0.0 + 246.0 + 8,523.0 + 285.66 + 26,269.32 + 0.0) = 0.0000\text{ s}$$
- **Root Cause:** Route `3232` (GTB Nagar to Sonipat) is an intercity peak commuter service with no scheduled trips between 06:03 AM and 17:03 PM. Constrained to at most 1 transfer, the passenger must wait $26,269\text{ s}$ ($7.3\text{ hours}$) at GTB Nagar for the 17:03 PM departure.
- **Alternative:** Allowing 2 transfers (`max_transfers: 3`) discovers an alternative via Regal and GTK Depot taking only **8,516 seconds (2.37 hours)**.
- **Recommendation:** Display a UI advisory tag when `transfer_waiting_time_s > 7200` without artificially suppressing Pareto-optimal timetable results.

### 2.3 Direct & Transfer Journey Quality (Section 3)
- Tested representative corridors across DLM1 routes (`1598`, `284`, `2734`, `3232`).
- Direct Route `1598` correctly emits `LEVEL_1_DIRECT_OBSERVED` ($1,021.5\text{ s}$).
- Direct Route `284` correctly falls back to `LEVEL_4_GTFS_SCHEDULED` ($527.0\text{ s}$).
- Negative inputs (unknown stops, identical endpoints, invalid times $>28\text{h}$) correctly return HTTP 200 with empty arrays or HTTP 422 validation errors.

### 2.4 Live-Feed Telemetry Matching (Section 4)
- 3 independent snapshots from the authenticated DTS endpoint (`dts-backend.transportstack.in`) captured 667 active buses each with 0 rejected and 100% fresh timestamps ($\le 900\text{s}$). Latencies: 0.733s, 1.352s, 0.956s.
- **Observed Active Route Denominator:** Exactly **293 active routes** were present in the live stream.
- **DLM1 Match Rate:** **293 of 293 (100.0%)** matched DLM1 static routes. (This applies to the observed active denominator, not all 2,574 routes).

### 2.5 Historical Data Integrity (Section 5)
- All 136 observations in `data/processed/gps_parquet/observed_segments.parquet` remain intact across 5 service dates.
- Exactly 5 stop pairs (29 observations, 21.32%) have approved `HIGH_CONFIDENCE` mappings to DLM1.
- Exactly 16 stop pairs (107 observations, 78.68%) remain safely quarantined in `pilot_v1_legacy`.
- Zero ambiguous stop pairs were silently migrated.

### 2.6 Security & Credential Hygiene (Section 6)
- Scanned all configuration, code, logs, and reports.
- Detected and remediated 1 literal key leak in documentation (`reports/milestone11_3_post_cutover_validation.md` line 166). Redacted to `[REDACTED_DTS_API_KEY]`.
- Current leak count across repository: **0**.
- Recommended defensive rotation of the DTS API key on the official portal.

---

## 3. Explicit System Limitations Disclosure

Pursuant to PRD v3.0, the following limitations remain in effect:
1. **DEGRADE Operational Status:** The system operates in `DEGRADE` mode because:
   - Ground-truth GPS training data is confined to 5 service dates along the North GT Road corridor.
   - Non-pilot routes rely on static GTFS scheduled timetables (`LEVEL_4_GTFS_SCHEDULED`).
   - Live GTFS-RT feeds do not currently provide full trip-to-vehicle binding across all routes.
2. **Off-Peak Live Feed Denominator:** The 100% route match rate is validated against the 293 routes active at midnight in Delhi, not the entire daytime catalog.
3. **No Google Maps Equivalence Claim:** The system does not claim real-world road congestion accuracy outside observed pilot segments.
4. **Sparse Intercity Service Gaps:** Certain intercity DLM1 routes (such as Route `3232`) operate only in peak hours, resulting in large transfer wait times under low-transfer constraints.

---

## 4. Deliverables Index

The following deliverables were generated and verified during Milestone 11.4:
- [milestone11_4_backend_test_audit.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone11_4_backend_test_audit.md)
- [milestone11_4_journey_quality_audit.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone11_4_journey_quality_audit.md)
- [milestone11_4_live_feed_audit.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone11_4_live_feed_audit.md)
- [milestone11_4_historical_integrity.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone11_4_historical_integrity.md)
- [milestone11_4_security_audit.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone11_4_security_audit.md)
- [milestone11_4_final_assessment.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone11_4_final_assessment.md)
- [milestone11_4_metrics.json](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/processed/milestone11_4_metrics.json)

