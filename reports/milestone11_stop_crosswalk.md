# Milestone 11: Legacy-to-DLM1 Stop Crosswalk & Historical Compatibility Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 11 (Controlled DLM1 Static GTFS Migration)  
**Governing Status:** `DEGRADE`  
**Crosswalk Status:** Complete & Verified  
**Audit Date:** 2026-11-21  

---

## 1. Executive Summary

A core challenge in migrating from the legacy GTFS dataset (`mdb-1262`, extracted in 2023) to the official DLM1 dataset is that the Delhi Transport Corporation completely revised its internal stop indexing and spatial topology. 

Rather than attempting an unsafe blind replacement or silent merging of bus stops, Milestone 11 developed an evidence-based spatial and semantic crosswalk across all **6,342 legacy stops** evaluated against the **6,862 DLM1 stops**.

### Key Crosswalk Results
- **Total Legacy Stops Evaluated:** 6,342
- **`HIGH_CONFIDENCE` Matches:** 2,581 (40.70%)
- **`REVIEW_REQUIRED` Matches:** 3,413 (53.82%)
- **`UNMATCHED` Stops:** 348 (5.49%)
- **Historical Observations Compatibility (136 total):**
  - High Confidence: 29 observations (21.32%)
  - Review Required: 107 observations (78.68%)
  - Unmapped: 0 observations (0.00%)
- **Core Governance Decision:** Due to directional carriageway splitting and metro gate renumbering affecting 78.7% of historical observations, historical pilot data is preserved as a separately versioned dataset (`pilot_v1_legacy`). Legacy data is never silently force-mapped into DLM1.

---

## 2. Crosswalk Methodology & Matching Criteria

Matching between legacy and DLM1 stops was executed via a multi-stage spatial and string-similarity pipeline:

1. **Spatial Filtering ($k\text{-d}$ Tree in UTM Zone 43N):**
   Every legacy stop coordinate `(lat, lon)` was projected to metric coordinates (`EPSG:32643`). Candidates in DLM1 within a hard radius of **150.0 meters** were retrieved. Stops with no candidates within 150m were classified as `UNMATCHED`.
2. **String Similarity Scoring:**
   Stop names were normalized (lowercased, punctuation stripped, common abbreviations like `(t)`, `stn`, `isbt` standardized). Two similarity metrics were computed:
   - **Token Jaccard Similarity:** Set overlap of unique words.
   - **Sequence Matcher Ratio:** Levenshtein-like character subsequence alignment.
   - **Composite Name Score:** $\max(\text{Jaccard}, \text{Sequence})$.
3. **Platform & Directional Ambiguity Detection:**
   If multiple DLM1 stops exist within 30 meters of each other (e.g., opposite carriageway stops or adjacent terminal bays), the candidate was flagged as having platform ambiguity.
4. **Classification Thresholds:**
   - **`HIGH_CONFIDENCE`:** Distance $\le 80.0\text{ m}$, Composite Name Score $\ge 0.50$ (or exact name match with distance $\le 120.0\text{ m}$), and no conflicting ambiguous platform within 15 meters.
   - **`REVIEW_REQUIRED`:** Distance $\le 150.0\text{ m}$ but lower name similarity ($< 0.50$), or distance between $80\text{ m}$ and $150\text{ m}$, or presence of multiple competing platform candidates.
   - **`UNMATCHED`:** Distance to nearest DLM1 stop $> 150.0\text{ m}$.

---

## 3. Global Stop Crosswalk Distribution

| Classification | Stop Count | Percentage | Description |
| :--- | :--- | :--- | :--- |
| **`HIGH_CONFIDENCE`** | 2,581 | 40.70% | Direct spatial and semantic equivalence (<80m, clear name match) |
| **`REVIEW_REQUIRED`** | 3,413 | 53.82% | Directional carriageway splits, metro station gate re-keying, or terminal bays |
| **`UNMATCHED`** | 348 | 5.49% | Decommissioned stops, relocated stops (>150m), or rural terminal extensions |
| **Total** | **6,342** | **100.00%** | All legacy stops accounted for |

### Why 53.82% of Stops Require Review
In DLM1, Delhi bus stops underwent substantial modernization in modeling:
- In `mdb-1262`, many stops were recorded as a single centroid for both directions of travel (e.g. "Azadpur Terminal" or "Jahangir Puri GT Road").
- In DLM1, stops are split into distinct directional carriageway platforms (e.g. UP platform vs DOWN platform) separated by 25–60 meters across wide median-divided arterial roads.
- Major interchange stations have been split into specific metro gate access points (e.g. "ISBT Nitayanand Marg / KASHMERE GATE METRO STATION GATE 3" vs "ISBT Kashmere Gate City Bus Terminal").
- Automatically merging these stops would distort travel times and directional routing.

---

## 4. North GT Road Corridor Verification (Stops 239–247)

The table below documents the exact crosswalk results for the 9 sequential stops of the pilot corridor along North GT Road used in Route 1598:

| Legacy ID | Legacy Stop Name | DLM1 Match ID | DLM1 Stop Name | Distance (m) | Name Sim. | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **239** | Azad Pur Terminal | **7587** | Azadpur Terminal | 16.02 m | 0.90 | `HIGH_CONFIDENCE` |
| **240** | New Sabzi Mandi | **7595** | New Sabzi Mandi Azadpur | 39.31 m | 0.81 | `REVIEW_REQUIRED`* |
| **241** | Adarsh Nagar / Bharola Village | **284** | Adarsh Nagar / Bharola Village | 7.66 m | 0.98 | `HIGH_CONFIDENCE` |
| **242** | Sarai Peepal Thala | **285** | Sarai Peepal Thala | 0.00 m | 1.00 | `REVIEW_REQUIRED`* |
| **243** | Mahindra Park | **286** | Mahindra Park | 0.04 m | 1.00 | `HIGH_CONFIDENCE` |
| **244** | Jahangir Puri GT Road | **7598** | Jahangirpuri Metro Station GT Road | 61.97 m | 0.69 | `REVIEW_REQUIRED`* |
| **245** | Jahangir Puri Metro Station | **5085** | Jahangir Puri Crossing | 32.01 m | 0.58 | `HIGH_CONFIDENCE` |
| **246** | GTK Depot | **289** | GTK Depot | 0.00 m | 1.00 | `HIGH_CONFIDENCE` |
| **247** | Mukarba Chowk | **5146** | GTK ByPass / Mukarba chowk | 56.11 m | 0.53 | `REVIEW_REQUIRED`* |

*\*Note: Stops marked `REVIEW_REQUIRED` have adjacent counter-direction platforms or metro gate markers within 25–40m, requiring directional confirmation before automated routing assignment.*

---

## 5. Historical GPS Observations Compatibility

The historical training corpus from Milestones 2–9 consists of **136 stop-to-stop segment observations** across **26 route-specific stop pairs** (21 distinct physical stop pairs) over 5 service dates.

Each segment observation was mapped through the crosswalk:
- **`HIGH_CONFIDENCE` Observations:** 29 of 136 (21.32%)
- **`REVIEW_REQUIRED` Observations:** 107 of 136 (78.68%)
- **`UNMAPPED` Observations:** 0 of 136 (0.00%)

### Governance Decision: Dataset Versioning as `pilot_v1_legacy`
Because 78.68% of the historical observations involve stop pairs where DLM1 introduced platform or carriageway disambiguation:
1. Forcing the historical observations into DLM1 stop IDs without manual ground-truthing would introduce synthetic directional bias into the statistical profile.
2. Therefore, the historical dataset is formally classified and versioned as **`pilot_v1_legacy`**.
3. It remains attached to `/tmp/delhi_mdb.db` for the M0 historical baseline, while DLM1 serves as the forward-compatible foundation for real-time live feeds and future GPS collection.

---

## 6. Persisted Artifacts

The crosswalk has been persisted in three distinct formats for full reproducibility:
1. **SQLite Database Table:** `legacy_stop_crosswalk` in `/tmp/delhi_dlm1.db` (with B-Tree indexes on both legacy and DLM1 stop IDs).
2. **CSV Artifact:** `data/processed/legacy_stop_crosswalk.csv` (1.0 MB, 6,343 rows).
3. **Parquet Artifact:** `data/processed/legacy_stop_crosswalk.parquet` (429 KB, typed columnar storage).

