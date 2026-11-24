# Map Matching and Linear Referencing Report

**Service Date:** October 1, 2026 (`2026-10-01`)  
**Pilot Corridors Evaluated:** Route 1515 (`721UP`), Route 1656 (`534UP`), Route 1598 (`129AUP`), Route 1616 (`126ADOWN`)  
**Total Observations Evaluated:** 231,619 GPS pings across 397 vehicles  
**Output Datasets:** `data/processed/stop_crossings/service_date=2026-10-01/`  
**Diagnostic Plot:** [fig1_map_match_route1515.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig1_map_match_route1515.png)  

---

## 1. Methodology and Linear Referencing Architecture

Because the full GTFS release contains zero shapes (`shapes.txt` is empty), route geometry was reconstructed as a **Topological Polyline Baseline** in metric UTM coordinates (`EPSG:32643` Zone 43N) directly connecting sequential GTFS stops: $(S_1, S_2, \dots, S_N)$.

As defined in PRD Section 6.4:
> *"A full road-network HMM map matcher is not required. The bus follows a known GTFS shape, so the main matching task is to estimate progress along that shape."*

For each candidate route pattern, an along-route cumulative metric distance array is constructed:
$$d_1 = 0, \quad d_k = d_{k-1} + \sqrt{(x_k - x_{k-1})^2 + (y_k - y_{k-1})^2}$$
Every GPS observation $(x_p, y_p)$ is projected onto the route polyline using Shapely linear referencing to determine:
1. **Along-Route Distance ($s_p$):** Metric distance along the polyline from the route origin.
2. **Perpendicular Offset ($d_{\perp, p}$):** Euclidean distance from the GPS ping to the polyline segment.
3. **Segment Index ($k$):** The index of the stop-to-stop segment $[S_k, S_{k+1}]$ closest to the ping.

### Directional Route Pairing in Delhi GTFS

A critical domain discovery from our audit is that Delhi static GTFS represents inbound and outbound directions as **separate numeric route IDs**:
- **Route 721:** `1515` (721UP) and `1734` (721DOWN)
- **Route 534:** `1656` (534UP) and `1719` (534DOWN)
- **Route 129A:** `1598` (129AUP) and `1578` (129ADOWN)
- **Route 126A:** `1445` (126AUP) and `1616` (126ADOWN)

In accordance with PRD Section 6.4 Rule 2 (*"evaluate candidate shapes for the GPS route, including both directions"*), our matcher evaluates candidate patterns for both directions and selects the candidate that maximizes monotonic progression and minimizes perpendicular offset.

---

## 2. Match Decision Gates and Quality Criteria

To prevent bogus matches from corrupting the travel-time ground truth, trajectories are evaluated against strict multi-criteria gates:

| Decision Gate | Metric / Formula | Threshold | Action if Failed |
| :--- | :--- | :--- | :--- |
| **Ping Sufficiency** | Ping count $N$ | $N \ge 5$ | Reject as `UNMATCHED_TOO_FEW_PINGS` |
| **Lateral Proximity** | Mean perpendicular distance $\bar{d}_\perp$ | $\bar{d}_\perp \le 50.0\text{ m}$ (confident) $\le 85.0\text{ m}$ (low) | Reject as `UNMATCHED_EXCESSIVE_DISTANCE` |
| **Monotonic Progression** | Non-decreasing along-distance steps ($s_i \ge s_{i-1} - 30\text{m}$) | $\text{ratio} \ge 70.0\%$ | Reject as `UNMATCHED_REVERSE_OR_ERRATIC` |
| **Route Coverage** | Along-distance span: $\Delta s / L_{\text{route}}$ | $\ge 10.0\%$ | Reject as `UNMATCHED_POOR_FIT` |
| **Candidate Ambiguity** | Score ratio between top candidate and runner-up | $\text{Score}_1 / \text{Score}_2 \ge 1.15$ | Reject as `UNMATCHED_AMBIGUOUS_ROUTE` |

---

## 3. Quantitative Map-Matching Results (Pilot Run)

| Outcome Category | Trajectory Count | % of Trajectories | Description & Operational Reason |
| :--- | :--- | :--- | :--- |
| **Confident Matches (`MATCHED_CONFIDENT`)** | **9** | 0.87% | High-confidence matches ($\bar{d}_\perp \le 35\text{m}$, monotonic $\ge 95\%$) advancing along corridor |
| **Low Confidence Matches (`MATCHED_LOW_CONFIDENCE`)** | **11** | 1.06% | Valid corridor progress with higher lateral GPS noise ($50\text{m} < \bar{d}_\perp \le 85\text{m}$) |
| **Rejected: Excessive Distance (`UNMATCHED_EXCESSIVE_DISTANCE`)** | **841** | 80.87% | Off-route buses (mean offset $10\text{ km} - 25\text{ km}$): depot deadheads or static profile mismatch |
| **Rejected: Sparse Observations (`UNMATCHED_TOO_FEW_PINGS`)** | **175** | 16.83% | Fragments with $< 5$ pings resulting from trip transitions or tracking reboots |
| **Rejected: Reverse / Erratic (`UNMATCHED_REVERSE_OR_ERRATIC`)** | **3** | 0.29% | Pings advancing counter to route direction or oscillating at terminal |
| **Rejected: Route Ambiguity (`UNMATCHED_AMBIGUOUS_ROUTE`)** | **0** | 0.00% | No overlapping pattern collisions survived proximity checks |
| **Rejected: Poor Fit (`UNMATCHED_POOR_FIT`)** | **1** | 0.10% | Did not clear minimum 10% route coverage threshold |
| **Total Trajectories Evaluated** | **1,040** | **100.00%** | Reconstructed continuous segments from 231,619 clean pings |

### Why Are 80.9% of Trajectories Rejected for Excessive Distance?

Our audit of individual vehicle histories (e.g. `DL1PD4213` and `DL1PD4180`) revealed that Delhi buses frequently report a static `route_id` (e.g. `1515`) on their Electronic Ticket Machine (ETM) while operating depot deadhead runs in North-West Delhi (Bawana/Narela, 23 km away from the Route 1515 corridor between Manglapuri and Kashmere Gate).

**Core System Principle Enforced:** The map matcher **refuses to force a match** when a bus is 23 km off-route. This strict gate guarantees that only buses genuinely traversing the physical route corridor contribute to the ground-truth stop-crossing dataset.

---

## 4. Visual Diagnostics

1. **Spatial Overlay:** [fig1_map_match_route1515.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig1_map_match_route1515.png) illustrates vehicle GPS pings (crimson) projected onto the reconstructed GTFS route polyline (navy) and stops (orange).
2. **Along-Route Progress Curve:** [fig2_stop_crossing_interpolation.png](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/figures/fig2_stop_crossing_interpolation.png) displays along-distance vs time, showing clean monotonic progression and the linear interpolation of stop arrival times.

