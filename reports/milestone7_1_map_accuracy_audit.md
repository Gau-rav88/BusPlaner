# Milestone 7.1: Map Geometry Accuracy & Representation Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Audit Scope:** Verification of map geometry fidelity, GTFS shapes reality, walking path approximations, and UI disclosure accuracy.  
**Classification:** **PASS WITH LIMITATIONS** (Due to the absence of `shapes.txt` in the supplied Delhi GTFS feed, all transit polylines and walking paths are stop-to-stop straight-line approximations; the UI has been audited and enhanced to prominently disclose this limitation and eliminate any possibility of misleading users).  
**Operational Status:** **DEGRADE**  
**Date:** November 2026  

---

## 1. Executive Summary

A critical inspection was conducted on `frontend/src/map/DelhiMap.tsx`, the underlying GTFS database (`/tmp/delhi_mdb.db`), and the visual outputs rendered in the browser. 

The audit established that:
1. **GTFS Feed Contains No `shapes.txt`:** The official static GTFS feed provided for Delhi contains tables for `agency`, `routes`, `trips`, `stops`, `stop_times`, `calendar`, and `calendar_dates`, but **no `shapes.txt`** table exists. Consequently, true street-following road curves, turns, and highway geometry do not exist in the GTFS database.
2. **Prior Misleading Representation Identified:** In the initial Milestone 7 implementation, `DelhiMap.tsx` drew a single straight line directly connecting the query origin and destination coordinates, labeled generically in the legend as *"Bus Route"* and *"Walking Access/Egress"*. This visual could have misled users into believing the line represented the bus path or actual road navigation.
3. **Corrective Implementation Executed:** 
   - `DelhiMap.tsx` has been refactored to fetch route stop sequences dynamically via `apiService.getRouteDetail(route_id)`.
   - When a transit journey is selected, the map extracts all ordered stops between the boarding stop and the alighting stop (e.g. Stop 239 through Stop 247 on Route 1598) and renders a multi-segment polyline connecting all 8 consecutive stop coordinates, with intermediate stop marker dots (`CircleMarker`).
   - A permanent, prominent **Geometry Disclaimer Banner** has been overlaid across the top of the map container:  
     `"⚠️ Approximate Stop-to-Stop Geometry: Delhi GTFS feed lacks shapes.txt. Plotted paths connect stop coordinates via straight segments; actual road curvature and street geometry are not represented."`
   - The map legend has been updated to explicitly label:
     - *"Bus Segment (Stop-to-stop straight lines)"*
     - *"Walking Path (Straight-line estimate)"*
     - Footnote: `"*GTFS lacks shapes.txt: lines connect stop coordinates without street curvature."`
   - Polyline popups inform users upon clicking: `"⚠️ Approximate geometry: Road curvature unrepresented (no shapes.txt in GTFS)."`
4. **No External Geometry Downloaded:** In strict accordance with guidelines, no external routing engines (OSRM, Mapbox, Google Maps, HERE) or synthetic shapes were downloaded or fabricated.

---

## 2. Technical Inspection of GTFS Database & Geometry Sources

### 2.1 Database Schema Verification
Inspection of the SQLite GTFS database (`/tmp/delhi_mdb.db`) confirmed:
- `SELECT name FROM sqlite_master WHERE type='table';` returns:
  `agency`, `calendar`, `calendar_dates`, `routes`, `shapes`, `stop_times`, `stops`, `trips`.
- Running `SELECT count(*) FROM shapes;` returns **0 rows**.
- The `trips` table has `shape_id` values set to `NULL` across all 114,354 trip rows.

### 2.2 Routing Engine (RAPTOR) Geometry Handling
The backend RAPTOR transit engine operates purely as a timetable-driven topological graph over `stop_times` and footpath transfers:
- RAPTOR evaluates station-to-station departure and arrival times and transfer walking footpaths.
- It does not calculate spatial polylines or road curvature.
- Intermediate stops are returned as a list of stop IDs in `TransitLegSchema.intermediate_stops`.

---

## 3. Map Geometry Audit Checklist

| Item | Condition Verified | Implementation Status | Findings & Corrections |
| :--- | :--- | :--- | :--- |
| **Bus Route Geometry** | Is the polyline actual road geometry or straight lines? | **Stop-to-stop straight lines** | Route stops are resolved via `getRouteDetail()`. Polyline connects stop coordinates sequentially. Curvature between stops is NOT represented. |
| **Walking Paths** | Are footpaths street-network routes or straight lines? | **Straight-line estimate** | Walking access/egress connects origin/destination coordinates to bus stops directly as dashed straight lines. |
| **Geometry Disclaimer** | Is the approximate nature prominently disclosed? | **Prominently Disclosed** | Persistent top banner and legend footnote explicitly warn that GTFS lacks `shapes.txt`. |
| **Polyline Interactivity** | Does clicking a route line clarify geometry accuracy? | **Clarified in Popup** | Polyline popup states: *"Approximate geometry: Road curvature unrepresented (no shapes.txt in GTFS)"*. |
| **Fabrication Check** | Were synthetic road shapes generated or imported? | **Zero Fabrication** | No third-party routing APIs or synthetic geometries were introduced. |

---

## 4. Visual Comparison: Before vs. After Correction

| Aspect | Milestone 7 (Initial) | Milestone 7.1 (Audited & Corrected) |
| :--- | :--- | :--- |
| **Transit Polyline** | Single chord connecting origin to destination. | Multi-stop polyline following consecutive stop coordinates from boarding stop to alighting stop. |
| **Intermediate Stops** | None rendered on map. | Turquoise circle markers (`CircleMarker`) placed at each traversed intermediate stop with stop name tooltips. |
| **Top Warning Banner** | None. | Amber floating banner at top: *"Approximate Stop-to-Stop Geometry: Delhi GTFS feed lacks shapes.txt..."* |
| **Legend Bus Line** | Labeled *"Bus Route"*. | Labeled *"Bus Segment (Stop-to-stop straight lines)"* with an *"Approximate"* badge. |
| **Legend Walking Line** | Labeled *"Walking Access/Egress"*. | Labeled *"Walking Path (Straight-line estimate)"*. |
| **Misleading Risk** | High (User could assume line represents bus road route). | **Eliminated** (Every visual element explicitly states straight-line approximation). |

---

## 5. Audit Classification & Conclusion

**Classification: PASS WITH LIMITATIONS**

The map rendering now truthfully presents the underlying transit data without fabricating road geometry or misleading users. All approximate stop-to-stop connections are clearly identified, ensuring scientific authenticity under **DEGRADE** operational status.

