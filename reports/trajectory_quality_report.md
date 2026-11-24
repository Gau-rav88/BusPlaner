# GPS Trajectory Reconstruction and Quality Report

**Service Date:** October 1, 2026 (`2026-10-01`)  
**Pipeline Module:** `backend/core/trajectory.py`  
**Cleaning Rules Enforced:** PRD Rules E05 (Movement Jumps), E06 (Speed Consistency), E07 (Reporting Gaps), E08 (Non-increasing Timestamps)  
**Evaluated Dataset:** 231,619 clean observations across 397 vehicles operating on pilot corridors  

---

## 1. Trajectory Reconstruction Methodology

The raw GPS stream arrives as discrete, asynchronous pings. To transform these observations into physically coherent vehicle trajectories, `reconstruct_vehicle_trajectories()` executes the following pipeline:

1. **Partition & Chronological Ordering:**
   - Group observations strictly by `(vehicle_id, service_date)`.
   - Sort observations chronologically by `timestamp_utc`.
2. **Coordinate Metric Projection:**
   - Project geographic coordinates $(lat, lng)$ into UTM Zone 43N coordinates $(utm\_x, utm\_y)$ using `EPSG:32643`.
3. **Step-by-Step Displacement & Speed Derivation:**
   - For every consecutive ping pair $(i-1, i)$:
     $$\Delta t = t_i - t_{i-1} \quad (\text{seconds})$$
     $$\Delta d = \sqrt{(x_i - x_{i-1})^2 + (y_i - y_{i-1})^2} \quad (\text{meters})$$
     $$v_{\text{implied}} = 3.6 \times \frac{\Delta d}{\Delta t} \quad (\text{km/h})$$
4. **Trajectory Splitting Rules:**
   - **Rule E07 (Excessive Reporting Gap):** If $\Delta t > 300\text{ seconds}$ (5 minutes), the trajectory is split into a new continuous segment. Pings are **never linearly interpolated across large temporal gaps**.
   - **Rule E05 (Implausible Movement Jump):** If $v_{\text{implied}} > 90.0\text{ km/h}$ and $\Delta d > 500\text{ meters}$, the point is flagged as a spatial teleportation artifact and triggers an immediate trajectory split.
   - **Trip Boundary Changes:** If `trip_id_canonical` changes, the active segment is closed and a new trajectory begins.
   - **Rule E08 (Zero or Negative Timestamps):** Handled during deduplication; any non-increasing timestamps trigger a split/rejection.
5. **Stationary Bus Preservation:**
   - Buses with zero reported speed and zero displacement ($\Delta d \approx 0$) are valid observations (bus held at traffic signal or stop) and are preserved without deletion.
   - Idle depot rest exceeding 15 minutes is segregated by the gap/trip splitting logic so stationary depot dwell does not pollute revenue service analysis.

---

## 2. Trajectory Segmentation Statistics (Pilot Corridors)

| Metric | Value |
| :--- | :--- |
| **Total GPS Pings Processed** | **231,619** |
| **Distinct Vehicles** | **397** |
| **Total Reconstructed Trajectories** | **1,040** |
| **Average Trajectories per Vehicle-Day** | **2.62** |
| **Median Trajectory Ping Count** | **148 pings** |
| **Median Ping Sampling Interval** | **10.0 seconds** (p95 = 22.0s) |
| **Trajectories Split Due to Gap > 300s (Rule E07)** | **428 splits** |
| **Trajectories Split Due to Jump > 90 km/h (Rule E05)** | **14 splits** |
| **Trajectories Split on Trip Identifier Change** | **201 splits** |

---

## 3. Handling of Trajectory Anomalies and Discontinuities

### Implausible Jumps (Rule E05)
GPS multipath reflection from flyovers, high-rise commercial corridors, and dense tree cover occasionally produces sudden single-ping jumps of several kilometers within 10 seconds (implied speed $> 500\text{ km/h}$).
- *Action Taken:* The pipeline detects the jump, tags the offending record with `E05_IMPLAUSIBLE_JUMP`, closes the current trajectory segment, and begins a new trajectory segment at the next stable observation.
- *Guarantee:* No stop crossing or segment travel time can span across an E05 jump.

### Reporting Gaps (Rule E07)
When a bus passes through cellular dead zones or the driver turns off the ignition during lunch/rest breaks, reporting intervals can exceed 10–30 minutes.
- *Action Taken:* The pipeline enforces a strict 300-second cut-off. Any gap exceeding 300 seconds terminates the active segment.
- *Guarantee:* Ground-truth travel times are only calculated from continuously tracked movements with dense ping support.

---

## 4. Preserved Decision Audit Trail

Every individual ping in the processed trajectory dataset retains an explicit `filter_decision` column:
- `START_OF_FEED`: First observation of the vehicle day.
- `VALID_CONTINUOUS`: Normal continuous ping advancing within plausible physical bounds.
- `E07_GAP_EXCEEDED_{dt}s`: Split triggered by temporal discontinuity.
- `E05_IMPLAUSIBLE_JUMP_{v}kmh`: Split triggered by teleportation jump.
- `TRIP_ID_CHANGED`: Split triggered by schedule trip transition.

Zero observations were deleted from the raw store, and all filtering actions are 100% reproducible.

