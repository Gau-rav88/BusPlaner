# Milestone 11.4 — Historical Pilot Data Integrity & Crosswalk Audit

**Governing specification:** PRD v3.0  
**Current primary database:** DLM1 (`/tmp/delhi_dlm1.db`)  
**Current system status:** `DEGRADE`  
**Previous milestone:** M11.3 — `CUTOVER_SUCCESSFUL_WITH_LIMITATIONS`  
**Evaluation date:** 2026-11-21  

---

## 1. Executive Summary

This audit verifies that the primary database cutover to DLM1 preserved the historical GPS pilot dataset without data loss, artificial expansion, or silent misattribution of ambiguous stop crosswalk mappings. 

### Key Findings
1. **Total Historical Observations:** Exactly **136** observation records remain preserved in `data/processed/gps_parquet/observed_segments.parquet` across all 5 service dates.
2. **Date Distribution:** Observations are strictly partitioned across:
   - `2026-10-01`: 27 records
   - `2026-10-02`: 30 records
   - `2026-10-05`: 28 records
   - `2026-10-06`: 25 records
   - `2026-10-07`: 26 records
   - **Total:** **136 records** (100% accounted for, 0 added, 0 removed).
3. **Route Coverage:** Route `1598` accounts for 124 records (91.18%), Route `1445` for 11 records (8.09%), and Route `1657` for 1 record (0.74%).
4. **Controlled Crosswalk Migration:**
   - **29 observations (21.32%)** across 5 stop pairs met strict `HIGH_CONFIDENCE` 1:1 crosswalk criteria and are mapped to DLM1 IDs.
   - **107 observations (78.68%)** across 16 stop pairs exhibit platform or multi-candidate ambiguity and remain strictly confined to `pilot_v1_legacy`.
   - **Zero ambiguous stop pairs** were silently migrated or forced into DLM1.

---

## 2. Historical Observation Inventory & Verification

### Table 1: Historical Segment Observations by Service Date & Route

| Service Date | Route 1598 | Route 1445 | Route 1657 | Daily Total | Unique Vehicles |
|:---:|:---:|:---:|:---:|:---:|:---:|
| `2026-10-01` | 27 | 0 | 0 | 27 | 7 |
| `2026-10-02` | 27 | 3 | 0 | 30 | 7 |
| `2026-10-05` | 28 | 0 | 0 | 28 | 6 |
| `2026-10-06` | 22 | 3 | 0 | 25 | 6 |
| `2026-10-07` | 20 | 5 | 1 | 26 | 5 |
| **Total** | **124** | **11** | **1** | **136** | **31 (overall)** |

---

## 3. Stop Crosswalk Partitioning & Boundary Enforcement

The legacy-to-DLM1 crosswalk (`data/processed/legacy_stop_crosswalk.csv`) established a strict safety policy: only unambiguous 1:1 stop matches with distance $< 50\text{m}$ and name similarity $\ge 0.70$ were approved for DLM1 query mapping.

### Table 2: The 5 Approved DLM1 Historical Stop Pairs (29 Observations)

| From Stop (Legacy) | To Stop (Legacy) | From Stop (DLM1) | To Stop (DLM1) | Matched Observations | Confidence | Match Criteria |
|:---|:---|:---|:---|:---:|:---:|:---|
| `239` (Kewal Park) | `247` (Azadpur Terminal) | `239` | `247` | 8 | `HIGH_CONFIDENCE` | $0.0\text{m}$ dist, $1.00$ sim, 1:1 |
| `247` (Azadpur Terminal) | `249` (Model Town III) | `247` | `249` | 6 | `HIGH_CONFIDENCE` | $0.0\text{m}$ dist, $1.00$ sim, 1:1 |
| `249` (Model Town III) | `251` (Model Town II) | `249` | `251` | 5 | `HIGH_CONFIDENCE` | $0.0\text{m}$ dist, $1.00$ sim, 1:1 |
| `251` (Model Town II) | `253` (Model Town I) | `251` | `253` | 5 | `HIGH_CONFIDENCE` | $0.0\text{m}$ dist, $1.00$ sim, 1:1 |
| `253` (Model Town I) | `255` (Alpana Cinema) | `253` | `255` | 5 | `HIGH_CONFIDENCE` | $0.0\text{m}$ dist, $1.00$ sim, 1:1 |
| **Total Approved** | | | | **29** | | |

### Table 3: Quarantined Ambiguous Historical Stop Pairs (107 Observations)

The remaining 16 physical stop pairs (representing 107 observations) involve platform splits, opposite-direction shelters, or multiple nearby DLM1 pole IDs within 50 meters (e.g. Stop `2024`, `2280`, `257` pairs).
- **Enforced Policy:** These 107 records are quarantined in `data/processed/quarantine/` and are only queryable when `DB_PATH=/tmp/delhi_mdb.db`.
- **Query Behavior in DLM1:** When a journey query traverses these unmapped segments in DLM1, the journey planner does **NOT** fabricate travel time predictions. It transparently falls back to `LEVEL_4_GTFS_SCHEDULED` / `GTFS_TIMETABLE`.

---

## 4. Hierarchy & Ground-Truth Transparency Audit

| Scenario | Journey Segment | Serving DB | Prediction Tier Emitted | Prediction Source Emitted | Fallback Flag |
|:---|:---|:---:|:---:|:---:|:---:|
| **Approved Pilot Corridor** | Stop `239` $\to$ Stop `247` | DLM1 (`delhi_dlm1.db`) | `LEVEL_1_DIRECT_OBSERVED` | `GROUND_TRUTH_OBSERVED` | `False` |
| **Ambiguous Legacy Corridor** | Stop `239` $\to$ Stop `2024` | DLM1 (`delhi_dlm1.db`) | `LEVEL_4_GTFS_SCHEDULED` | `GTFS_TIMETABLE` | `True` |
| **Legacy DB Execution** | Stop `239` $\to$ Stop `2024` | Legacy (`delhi_mdb.db`) | `LEVEL_1_DIRECT_OBSERVED` | `GROUND_TRUTH_OBSERVED` | `False` |
| **DLM1 Non-Pilot Route** | Stop `284` $\to$ Stop `5146` | DLM1 (`delhi_dlm1.db`) | `LEVEL_4_GTFS_SCHEDULED` | `GTFS_TIMETABLE` | `True` |

### Audit Conclusion
The separation between empirical pilot ground-truth and scheduled timetable fallback is strictly maintained. Zero synthetic or extrapolated travel times were injected into unmapped DLM1 corridors.

