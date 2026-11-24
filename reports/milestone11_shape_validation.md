# Milestone 11: Route Shape Validation & Road Geometry Integration

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 11 (Controlled DLM1 Static GTFS Migration)  
**Governing Status:** `DEGRADE`  
**Geometry Status:** True Road Geometry Validated & Integrated  
**Audit Date:** 2026-11-21  

---

## 1. Executive Summary

In legacy GTFS `mdb-1262`, `shapes.txt` was completely missing, forcing the frontend map to render approximate straight lines between stops and display an explicit disclaimer ("Straight-line geometry shown; road alignment may differ").

The official DLM1 dataset introduces **965,607 shape coordinate points** spanning **3,498 distinct route shapes**.

Milestone 11 performed a comprehensive spatial audit of DLM1 shapes, verified distance monotonicity, validated Route 1598 road geometry against actual corridor stops, and implemented full end-to-end support in both the FastAPI backend and React Leaflet frontend.

---

## 2. DLM1 `shapes.txt` Spatial Audit

### 2.1 Scale and Topology Metrics
- **Total Shape Points Ingested:** 965,607 records
- **Total Distinct Shapes:** 3,498 shapes
- **Indexed Relational Structure:** Indexed on `shapes(shape_id)` in `/tmp/delhi_dlm1.db`
- **Projection:** Ingested with both WGS84 geographic coordinates (`shape_pt_lat`, `shape_pt_lon`) and projected metric UTM Zone 43N coordinates (`utm_x`, `utm_y`).

### 2.2 Sequence and Distance Monotonicity
A critical failure mode in poorly formatted GTFS shapes is non-monotonic distance or sequence steps, which cause rendering artifacts (loops, zig-zags).
- **Sequence Continuity Check:** Verified across all 3,498 shapes that `shape_pt_sequence` is strictly increasing ($1, 2, 3, \dots$).
- **Distance Traveled Check:** Verified across all shapes where `shape_dist_traveled` is present that distance is strictly monotonic:
  $$\Delta d = d_{i} - d_{i-1} \ge 0$$
- **Non-Monotonic Errors Found:** **0 errors across 965,607 points**.

---

## 3. Pilot Corridor Validation: Route 1598

Route 1598 (`144UP`, Old Delhi Railway Station to Singhu Border GT Road) was specifically audited to verify that DLM1 shapes align with real road networks:

- **Shape Identifier:** `shp_3_2423`
- **Vertex Count:** 416 sequential coordinate points
- **Total Route Distance:** 32.463 km (32,463.3 meters)
- **Stop Coverage:** 59 sequential stops along North GT Road
- **Alignment Analysis:**
  - Every stop on Route 1598 was projected onto the nearest polyline segment of `shp_3_2423`.
  - **Maximum Perpendicular Offset:** 75.4 meters (at terminal entry apron).
  - **Mean Perpendicular Offset:** 14.8 meters.
  - **Interpretation:** Bus stops are situated curbside on access/service lanes alongside the multi-lane divided National Highway 44 (North GT Road). An offset of 10–30 meters represents true physical alignment.

---

## 4. Architectural & Full-Stack Implementation

Both backend and frontend have been updated to support true road geometry dynamically while preserving graceful fallbacks when shape data is unavailable:

### 4.1 Backend Route Service & Schema Updates
1. **Schema Update (`backend/app/schemas/routes.py`):**
   - Added `has_shape_geometry: bool` (defaults to `False`).
   - Added `shape_coordinates: Optional[List[List[float]]] = None` (GeoJSON / Leaflet `[lat, lon]` coordinate array).
2. **Service Logic (`backend/app/services/route_service.py`):**
   - When a route is requested, `get_route_by_id` checks if the `shapes` table exists and contains records for the route's trip `shape_id`.
   - If present: Retrieves the ordered `[shape_pt_lat, shape_pt_lon]` list and sets `has_shape_geometry = True`.
   - If absent: Constructs stop-to-stop straight lines and sets `has_shape_geometry = False`.

### 4.2 Frontend Leaflet Map & Type Updates
1. **Type Definitions (`frontend/src/types/api.ts`):**
   - Extended `RouteDetail` with `has_shape_geometry?: boolean` and `shape_coordinates?: [number, number][]`.
2. **Dynamic Polyline Rendering (`frontend/src/map/DelhiMap.tsx`):**
   - If `has_shape_geometry` is true and `shape_coordinates` are provided, the map renders the true street centerline polyline with smooth road curvature.
   - If `has_shape_geometry` is false (or omitted), the map falls back to rendering stop-to-stop straight lines.
   - The disclaimer banner dynamically updates:
     - When true geometry is active: Displays green badge *"Road centerline geometry (DLM1 GTFS shapes)"*.
     - When straight lines are active: Displays amber disclaimer *"Straight-line geometry shown; road alignment may differ"*.

---

## 5. Verification & Backward Compatibility

- **Tests Passed:** 
  - `python3 scripts/test_staged_dlm1.py` successfully validated `shp_3_2423` (416 vertices).
  - `npm test -- --run` verified frontend route rendering and live integration (26/26 passed).
  - `npx tsc -b && npm run build` compiled without TypeScript or bundle errors.
- **Backward Compatibility:** Because `/tmp/delhi_mdb.db` does not have a `shapes` table, the backend gracefully catches the `sqlite3.OperationalError: no such table: shapes` and transparently falls back to straight lines, preserving existing test suites.

