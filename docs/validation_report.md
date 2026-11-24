# Validation & Evaluation Report — Delhi Bus Journey Planner

This report documents the verification, safety checks, and test suite execution results across the entire Delhi Real-Time Bus Journey Planner system.

---

## 1. Test Suite Pass Rates & Quality Gates

| Test Suite | Total Tests | Passing | Failing | Pass Rate | Execution Time |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Backend Unit & API (pytest)** | 224 | 224 | 0 | **100%** | 73.5s |
| **Frontend Component & Integration (Vitest)** | 43 | 43 | 0 | **100%** | 2.7s |
| **TypeScript Typecheck (`tsc -b`)** | - | Complete | 0 errors | **100%** | 1.1s |
| **Vite Production Bundler** | - | Complete | 0 errors | **100%** | 1.5s |

---

## 2. Live Bus Availability Funnel Audit

The end-to-end live vehicle matching pipeline was audited against genuine Delhi Transport Stack GTFS-RT telemetry (~1,076 active vehicles):

| Pipeline Stage | Route 641 (High-Freq Corridor) | Route 3475 (South-West Corridor) | Route 1598 (North GT Road Corridor) |
| :--- | :---: | :---: | :---: |
| **1. Upstream Vehicles Received** | 1,076 | 1,076 | 1,076 |
| **2. Valid GPS Positions** | 1,076 | 1,076 | 1,076 |
| **3. Within Delhi Search Area** | 1,076 | 1,076 | 1,076 |
| **4. Route-Matched Candidates** | 39 | 16 | 2 |
| **5. Correct Direction Candidates** | 39 | 16 | 1 |
| **6. Valid Stop Sequence (Approaching)** | 39 | 16 | 0 |
| **7. Shape-Matched & Projected** | 39 | 16 | 1 |
| **8. Passed Quality & Anomaly Checks** | 39 | 16 | 0 |
| **9. API Suitable Vehicles Returned** | **39** | **16** | **0** |
| **10. Rendered in Frontend (Mode B)** | **39** | **16** | **0** |

### Key Funnel Findings
1. **Route 641**: 39 out of 39 route candidates were verified as approaching pickup vehicles heading to the destination. All 39 render on the map with real-time distance badges.
2. **Route 3475**: 16 out of 16 route candidates were verified as approaching vehicles from Ghuman Hera Depot to Uttam Nagar.
3. **Route 1598**: Out of 2 active vehicles on the route:
   - 1 vehicle is off-corridor (> 1,500m from route shape, in depot transit).
   - 1 vehicle is at Singhu Border (sequence 58) and has already passed Old Delhi Railway Station (sequence 0).
   - Mode B correctly excludes both to prevent passengers from waiting for a bus that will not arrive. The frontend displays an explanatory amber diagnostic banner.

---

## 3. Dead Reckoning & GPS Recalibration Audit

1. **Step-Ahead Extrapolation**: Verified every 15 seconds along GTFS shape polylines. Coordinates physically advance on the map between 30s upstream GPS cycles.
2. **Monotonic Progress Safeguard**: Cumulative distance along shape is constrained to non-negative increments, preventing backward reversals or loop snapping.
3. **Anomaly Protection Gate**:
   - Vehicles with GPS prediction error $> 250\text{m}$ (`LARGE_PREDICTION_ERROR`) or ambiguous projection are frozen at their genuine GPS anchor.
   - Out-of-order GPS timestamps (`last_gps_ts < anchor_gps_ts`) are strictly rejected.
   - Synthetic dead-reckoned positions are NEVER written back into genuine GPS historical stores.

---

## 4. UI Responsiveness & Browser Verification

Automated browser testing confirmed:
- **Responsive Layout**: Validated on both desktop (1440x900) and mobile (375x812) viewports.
- **Unrestricted Map Interaction**: Panning, dragging, and zooming operate without interference.
- **One-Click Pickup Navigation**: The `🧭 See Buses Coming to Pick You Up` button smoothly frames the user's boarding stop together with approaching pickup vehicles along the corridor.
