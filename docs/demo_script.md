# Evaluator Demonstration Script — Delhi Bus Journey Planner

This guide provides a structured 5-minute walkthrough for hackathon judges and evaluators to test all features of the Delhi Bus Real-Time Journey Planner.

---

## 1. Quick Launch

From the repository root:

```bash
# 1. Automatic environment & database setup (if first time)
bash scripts/setup.sh

# 2. Automated API and corridor demonstration
bash scripts/run_demo.sh
```

Ensure the services are running:
- **Frontend Web UI**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 2. Walkthrough Steps

### Step 1: Open the Application (Mode A — Fleet Discovery)
1. Navigate to [http://localhost:3000](http://localhost:3000).
2. Notice the clean layout: origin/destination inputs on the left, an expansive Leaflet map on the right.
3. Observe live buses appearing across Delhi (~1,000+ vehicles from Delhi Transport Stack).
4. Pan across Delhi (e.g. from Najafgarh to Connaught Place to Singhu Border) to verify smooth map exploration.

### Step 2: High-Frequency Corridor Test (Route 641 — 35+ Live Buses)
1. In the sidebar under **Quick Live Corridors**, click the preset:
   **⭐ Route 641: Ghuman Hera ➔ Janakpuri (30+ Live Buses)**.
2. Click the prominent **Plan Journey** button.
3. Observe the result:
   - Journey results card shows **Bus 641** direct transit.
   - The map switches to **Mode B (Destination-Specific Verification)**: only buses heading to your destination along the corridor are rendered.
   - Live count badge displays: `Showing 35 verified live buses for Route 641 heading to your destination`.
   - Each bus marker displays a permanent badge showing its distance to boarding (e.g., `Pickup Bus • 575m to boarding`).

### Step 3: One-Click Pickup Camera Alignment
1. Click the button: **🧭 See Buses Coming to Pick You Up** (available on both the journey card and the map floating toolbar).
2. The map camera smoothly pans and zooms directly to frame your boarding stop and approaching buses.
3. Watch the bus markers physically advance every 15 seconds along the road geometry using GPS-anchored dead reckoning.

### Step 4: Historic Corridor & Diagnostic Fallback Test (Route 1598)
1. Click the preset: **North GT Road Corridor (Route 1598)**.
2. Click **Plan Journey**.
3. Observe how the system handles routes where active vehicles are downstream:
   - Notice the amber diagnostic banner:
     *`2 bus(es) active on Route 1598, but none currently approaching your boarding stop in this direction.`*
   - Rather than presenting misleading buses traveling away from you or past your stop, the system explains the operational reason.
4. Click **"Show All Nearby Buses on Map"** to view general fleet traffic around the corridor.

### Step 5: Advanced Telemetry & Technical Details
1. In any journey card, expand **View Technical & Telemetry Details**.
2. Inspect the mathematical duration accounting:
   - Identity verification: `is_valid_identity: Yes` ($\sum \Delta t_{\text{components}} = t_{\text{total}}$).
   - Breakdown of in-vehicle ride, access walk, transfer walk, and wait times.
3. Expand **View Step-by-Step Route** to review each intermediate stop sequence and scheduled arrival times.
