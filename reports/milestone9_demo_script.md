# Milestone 9 — Evaluator Demo Script & Walkthrough

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Current Operational Status:** **`DEGRADE`** *(Strictly Maintained)*  
**Demo Scenario:** North GT Road Corridor (Route 1598)  
**Primary Stops:** Origin: Stop 239 (*Azad Pur Terminal*) $\to$ Destination: Stop 247 (*Mukarba Chowk*)  
**Date:** November 21, 2026  

---

## 1. Important Evaluator Notice: What This Demo Is and Is Not

> [!IMPORTANT]
> **What This Demo Demonstrates:**
> - A data-driven multi-modal transit journey planner for Delhi using the RAPTOR Pareto routing algorithm.
> - Empirical travel-time prediction derived from 136 ground-truth historical bus traversals on North GT Road.
> - Transparent disclosure of timetable expiry (2024-01-01) and explicit demonstration consent handling.
> - Conservative 5-level prediction fallback hierarchy with heuristic confidence scoring.
> 
> **What This Demo Does NOT Claim:**
> - This is **NOT** a live bus-tracking system (no GPS pings from moving buses are active).
> - This does **NOT** predict traffic Delhi-wide (predictions are confined to the Route 1598 pilot corridor).
> - This does **NOT** show exact road navigation curves (lines are approximate stop-to-stop straight segments).

---

## 2. Step-by-Step Evaluator Demo Walkthrough

### Step 1: Launch Application & Verify System Status
1. **Action:** Open Google Chrome or any modern browser and navigate to:
   ```text
   http://localhost:3000
   ```
2. **Observe in UI Header:**
   - **System Status Badge:** Orange badge reading `Status: DEGRADE`.
   - **Live Feed Badge:** Gray badge reading `Live Feed: Auth Required (Disabled)`.
   - **Top Alert Strip:** Yellow/Orange banner:
     > *"Demonstration Mode Active: Static GTFS timetable expired on 2024-01-01. Live Feed: Inactive (Auth Required). Historical ground-truth models active."*
3. **Explanation for Evaluator:**
   The application honestly communicates its operational constraints immediately upon load. The live feed is gated behind an API key from Delhi Transport Stack (`x-api-key`), which is unavailable; hence, the system operates in fail-closed historical mode under `DEGRADE` status.

---

### Step 2: Test Timetable Expiry Rejection (Strict Consent Gate)
1. **Action:**
   - Under *Trip Planner*, click the quick-preset button: **"North GT Road (Route 1598)"**.
   - Notice that Origin is set to **Azad Pur Terminal (Stop 239)** and Destination is set to **Mukarba Chowk (Stop 247)**.
   - **Uncheck** the box labeled: *"Allow Demonstration Mode (Evaluate expired 2024 schedule as assumed recurring template)"*.
   - Click **"Find Journeys"**.
2. **Observe in UI:**
   - The query is strictly rejected by the backend.
   - A red error banner appears:
     > *"Timetable Expired: The underlying GTFS schedule expired on 2024-01-01. Current 2026 operations are unverified. Please check 'Allow Demonstration Mode' to evaluate recurring weekly patterns."*
3. **Explanation for Evaluator:**
   The planner refuses to silently evaluate expired schedules as current reality. It demands explicit, conscious user consent before using historical timetables in demonstration mode.

---

### Step 3: Execute North GT Road Journey Planning (Consent Enabled)
1. **Action:**
   - Re-check the box: *"Allow Demonstration Mode"*.
   - Ensure Departure Time is set to **12:37:40** (or any daytime hour) on Date **2026-10-01**.
   - Click **"Find Journeys"**.
2. **Observe in Results Panel:**
   - A journey card appears immediately (sub-15ms backend response).
   - **Route Badge:** `Route 1598` (Direct, 0 transfers).
   - **Departure / Arrival Times:** e.g., Depart `12:38:00` $\to$ Arrive `12:58:00`.
   - **Prediction Badge:** Green badge: `Level 1: Ground Truth Observed`.
   - **Confidence Score:** `Confidence: 0.93 (Heuristic)`.
   - **Timetable Warning:** Yellow warning icon: `Timetable: ASSUMED_RECURRING (Unverified 2026 service)`.
3. **Explanation for Evaluator:**
   Because Route 1598 is our validated empirical corridor, the planner bypasses theoretical timetable durations and applies Level 1 historical ground truth (median segment duration computed from GPS crossings). The confidence score is labeled `HEURISTIC` so users know it is not a calibrated probability.

---

### Step 4: Expand Journey Details & Inspect Time Accounting
1. **Action:**
   - Click on the journey card to expand the detailed leg view.
2. **Observe:**
   - **Time Accounting Bar:** Shows separate durations for:
     - Initial Waiting Time: $\approx 20\text{ seconds}$
     - In-Vehicle Riding Time: $\approx 1,200.5\text{ seconds}$ (20.0 minutes)
     - Total Duration: $\approx 1,220.5\text{ seconds}$
     - Discrepancy: $0.0000\text{ seconds}$ (identity strictly conserved).
   - **Intermediate Stops List:** Click to expand the 7 intermediate stops:
     1. Stop 240: *New Sabzi Mandi*
     2. Stop 241: *Adarsh Nagar / Bharola Village*
     3. Stop 242: *Sarai Peepal Thala*
     4. Stop 243: *Mahindra Park*
     5. Stop 244: *Jahangir Puri GT Road*
     6. Stop 245: *Jahangir Puri Metro Station*
     7. Stop 246: *GTK Depot*

---

### Step 5: Inspect Interactive Map & Geometry Disclaimer
1. **Action:**
   - Inspect the interactive Leaflet map in the right-hand panel.
2. **Observe:**
   - Stop markers for Origin (Green) and Destination (Red) with numbered intermediate stop dots along North GT Road.
   - The route is drawn connecting stops.
   - **Prominent Geometry Disclaimer Banner:** Located directly above the map:
     > *"Approximate Stop-to-Stop Geometry: Delhi GTFS feed lacks shapes.txt. Plotted paths connect stop coordinates via straight segments; actual road curvature and street geometry are not represented."*
3. **Explanation for Evaluator:**
   The Delhi GTFS feed contains no `shapes.txt` table. Rather than drawing fake road curves that could mislead passengers, the application openly displays straight stop-to-stop lines with an unmissable disclaimer.

---

### Step 6: Test Unobserved Corridor Scheduled Fallback
1. **Action:**
   - In the Search panel, click the preset **"Central Corridor (Route 429)"** or search Origin: *Kashmere Gate* $\to$ Destination: *Dhaula Kuan*.
   - Click **"Find Journeys"**.
2. **Observe:**
   - Journey results render, but the prediction badge is now Blue: **`Level 4: GTFS Scheduled`**.
3. **Explanation for Evaluator:**
   The system proves it does not claim Delhi-wide traffic prediction. When navigating outside the North GT Road pilot corridor, it gracefully falls back to GTFS scheduled running times with lower heuristic confidence.

---

## 3. Demo Summary Checklist for Evaluators

| Demo Element | Evaluator Check | Result |
|---|---|:---:|
| **Status Transparency** | System prominently asserts `DEGRADE` and `Live Feed: Auth Required` | **Observed** |
| **Strict Expiry Rejection** | Query fails with 400 Bad Request if consent is not granted | **Observed** |
| **Empirical Prediction** | Route 1598 journey displays `Level 1: Ground Truth Observed` | **Observed** |
| **Heuristic Confidence** | Confidence score is explicitly qualified as `HEURISTIC` | **Observed** |
| **Exact Time Accounting** | Walking + Waiting + Ride exactly equals Total Duration ($\Delta = 0$) | **Observed** |
| **Geometry Truth** | Orange banner discloses lack of `shapes.txt` | **Observed** |
| **Graceful Fallback** | Unobserved corridors cleanly fall back to `Level 4: Scheduled` | **Observed** |

