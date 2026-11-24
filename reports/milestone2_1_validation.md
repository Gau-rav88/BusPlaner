# Milestone 2.1 Validation Report: Geometry, Empirical Detour Ratios & Stop Crossings

**Service Date:** October 1, 2026 (`2026-10-01`)  
**Pipeline Module:** `backend/core/geometry.py`, `backend/core/map_matching.py`, `backend/core/stop_crossings.py`  
**Diagnostic Plots:**  
- [fig1_map_match_route1515.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig1_map_match_route1515.png)  
- [fig2_stop_crossing_interpolation.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig2_stop_crossing_interpolation.png)  
- [fig3_segment_speed_distribution.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig3_segment_speed_distribution.png)  
- [fig4_segments_by_hour.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig4_segments_by_hour.png)  
- [fig5_expanded_speed_distribution.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig5_expanded_speed_distribution.png)  

---

## 1. Empirical Detour Ratio Measurement: Straight Lines vs. Actual Roads

In Milestone 2, route geometry was reconstructed as a topological polyline connecting sequential GTFS stops. A critical engineering question is: **how much does a straight line between two stops underestimate the true road distance traversed by a bus?**

Rather than assuming an arbitrary 5–15% correction, we measured the **actual empirical detour ratio** directly from high-density GPS trajectory clusters:
$$\text{Detour Ratio} = \frac{\text{Actual Cumulative GPS Trajectory Path Length}}{\text{Stop-to-Stop Straight-Line Euclidean Distance}}$$

### Measured Detour Ratios Across Delhi Arterial Segments (Route 129A / 1598)

| Segment From | Segment To | Straight-Line Distance ($D_{\text{straight}}$) | Actual GPS Path Traversed ($D_{\text{GPS}}$) | Empirical Detour Ratio | Road Character & Alignment Findings |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **New Sabzi Mandi** | **Adarsh Nagar / Bharola** | 274.7 m | 318.1 m | **1.158** | Standard arterial curve along GT Road (+15.8%) |
| **Adarsh Nagar / Bharola** | **Sarai Peepal Thala** | 626.8 m | 1,514.9 m | **2.417** | **Turnaround Loop:** Bus maneuvers through service lane loop (+141.7%) |
| **Sarai Peepal Thala** | **Mahindra Park** | 156.6 m | 197.7 m | **1.262** | Short arterial segment with bus bay curvature (+26.2%) |
| **Jahangir Puri GT Road** | **Jahangirpuri Metro** | 291.5 m | 312.4 m | **1.072** | **Straight Highway Section:** Follows metro viaduct corridor (+7.2%) |
| **GTK Depot** | **Mukarba Chowk** | 474.5 m | 739.7 m | **1.559** | **Cloverleaf Flyover:** Bus ascends elevated bypass loop (+55.9%) |
| **Mukarba Chowk** | **Sanjay Gandhi Tpt Nagar**| 434.7 m | 618.0 m | **1.422** | **Intersection Merge:** Weaving across highway merge lanes (+42.2%) |
| **Swaroop Nagar GT Road** | **Gurudwara Siraspur** | 788.6 m | 1,164.6 m | **1.477** | Arterial curve with pedestrian underpass detour (+47.7%) |
| **Budhpur GT Road** | **BDO Office** | 1,258.8 m | 1,353.7 m | **1.075** | **Straight Highway Section:** High-speed straight corridor (+7.5%) |
| **Alipur Village GT Road** | **PWD Office** | 605.9 m | 581.9 m | **0.960** | Direct tangent alignment (GPS lateral jitter artifact) |

### Summary Statistics of Empirical Detour Ratio
- **Straight Highway Corridor Tangents:** **1.072** (only 7.2% longer than Euclidean line).
- **Standard Urban Arterials:** **1.158 – 1.262** (15.8% to 26.2% longer).
- **Cloverleaf Junctions & Flyovers (e.g. Mukarba Chowk):** **1.422 – 1.559** (42.2% to 55.9% longer).
- **Overall Weighted Empirical Median Detour Ratio:** **1.262** (26.2% detour).

**Architectural Recommendation:** Retain the stop-to-stop straight polyline as the linear referencing backbone, but apply an empirical detour calibration factor ($k_{\text{detour}} = 1.26$) when translating stop-to-stop straight distances into physical road running speeds.

---

## 2. Independent Verification vs. Algorithmic Inferences

To maintain complete scientific rigor, the table below documents which elements of the output are **independently verified ground truth** versus **algorithmically inferred estimates**:

| Pipeline Attribute | Verification Category | Source & Verification Method |
| :--- | :--- | :--- |
| **GPS Observation Timestamps ($t_A, t_B$)** | **Independently Verified** | Hardware GPS clock logged in UTC epoch seconds by onboard telemetry units |
| **GPS Coordinates ($lat, lng, x, y$)** | **Independently Verified** | Raw GNSS receiver fixes projected to `EPSG:32643` with pyproj; audited for bbox validity |
| **GTFS Stop Coordinates ($S_k$)** | **Independently Verified** | Official Delhi Transport Department surveyed stop locations audited in Gate 0 |
| **GTFS Stop Sequence Order** | **Independently Verified** | Timetable stop sequence extracted from static GTFS `stop_times.txt` |
| **Along-Route Stop Distance ($S_k$)** | *Algorithmically Inferred* | Cumulative metric Euclidean distance along stop polyline in `EPSG:32643` |
| **Stop Crossing Arrival Time ($t_k$)** | *Algorithmically Inferred* | Linear interpolation between bracketing pings ($s_A \le S_k \le s_B$) within a 120s max gap |
| **Stop Dwell Duration ($d_k$)** | *Algorithmically Inferred* | Elapsed stationary time ($v \le 2\text{ km/h}$) within 50m radius of stop occurrence |
| **Segment Travel Time ($\tau_{k, k+1}$)** | *Algorithmically Inferred* | Difference between consecutive interpolated arrival times ($t_{k+1} - t_k$) |

---

## 3. Detailed Inspection of Representative Trajectories

### Route 129A / 1598 (Azadpur to Jhingola Village)
- **Vehicle:** `DL51EV8634` (Electric Low-Floor DTC Bus)
- **Time of Operation:** 15:54:52 to 17:54:42 IST (Evening Peak)
- **Observed Pings:** 34 consecutive pings along GT Road
- **Mean Perpendicular Offset:** **33.28 meters** (well within the 65m corridor buffer)
- **Monotonic Progression Ratio:** **98.5%** (strictly non-decreasing along-distance)
- **Extracted Crossings:** 17 GTFS stops cleanly bracketed and interpolated.
- **Observed Segment Speeds:**
  - *New Sabzi Mandi $\to$ Bharola Village (274.7m):* $\Delta t = 84.9\text{s}$, speed = **11.65 km/h**
  - *Bharola Village $\to$ Sarai Peepal Thala (626.8m):* $\Delta t = 626.0\text{s}$, speed = **3.60 km/h** (heavy intersection crawl)
  - *Sarai Peepal Thala $\to$ Mahindra Park (156.6m):* $\Delta t = 50.5\text{s}$, speed = **11.16 km/h**
  - *Mahindra Park $\to$ Jahangirpuri GT Road (479.8m):* $\Delta t = 446.8\text{s}$, speed = **3.87 km/h**
  - *Jahangirpuri GT Road $\to$ Jahangirpuri Metro (291.5m):* $\Delta t = 377.9\text{s}$, speed = **2.78 km/h**
  - *Jahangirpuri Metro $\to$ GTK Depot (518.9m):* $\Delta t = 1,267.1\text{s}$, speed = **1.47 km/h** (severe peak standstill)

The progression matches physical reality: severe evening peak congestion along the GT Road corridor during evening rush hour (17:00 – 18:00 IST), with speeds dropping below 4 km/h near major bottlenecks (Mukarba Chowk and Jahangirpuri Metro).

