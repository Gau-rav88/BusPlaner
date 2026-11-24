# Milestone 11.5 — Long-Transfer Journey Advisory & Timetable Transparency

**Governing specification:** PRD v3.0  
**Current primary database:** DLM1 (`/tmp/delhi_dlm1.db`)  
**Current system status:** `DEGRADE`  
**Previous milestone:** M11.4 — `QUALITY_AUDIT_PASSED_WITH_LIMITATIONS`  
**Evaluation date:** 2026-11-21  

---

## 1. Executive Summary

In Milestone 11.4, journey planning between Stop `2280` (*Nehru Nagar*) and Stop `5321` (*Alipur Blk.(BDO Office)*) at `08:00:00` under a 1-transfer constraint produced an unusually long journey of **$35,324.0\text{ s}$ ($9.81\text{ hours}$)**, driven by a **$26,269.32\text{ s}$ ($7.30\text{ hours}$)** transfer wait at GTB Nagar.

Pursuant to Section 2 requirements, an automated **Extended Transfer Wait Advisory** mechanism has been implemented across both the FastAPI backend and React frontend. This feature detects when any transfer waiting duration exceeds **$7,200.0\text{ seconds}$ ($2.0\text{ hours}$)** and surfaces a prominent advisory banner while strictly preserving the authenticity, duration, and mathematical accounting of the connection.

---

## 2. Timetable Verification: Route 3232 & Trip Connection

### 2.1 Route Characteristics & Service Frequency
Inspection of DLM1's `trips.txt`, `stop_times.txt`, and `routes.txt` confirms the operational characteristics of Route `3232`:
- **Route Name / Type:** Intercity Express Commuter Bus (GTB Nagar Metro Station to Sonipat / Haryana border).
- **Service Headways:** Unlike high-frequency urban trunk routes running at 10–15 minute intervals, Route `3232` operates exclusively during commuter peak hours:
  - Morning Outbound Runs: 05:00 AM, 05:30 AM, 06:03 AM.
  - Midday Service: **0 departures between 06:03 AM and 17:03 PM** (an 11-hour service gap).
  - Afternoon / Evening Peak Runs: Departures commence at **17:03:24 PM** (Trip `3232_FULL_16_50`).

### 2.2 Reconstructed Connection Timeline
1. Passenger departs Stop `2280` (*Nehru Nagar*) on Route `2734` (Trip `2734_FULL_07_55`) at `08:04:06 AM`.
2. Passenger alights at Stop `257` (*GTB Nagar*) at `09:44:12 AM` (ride: $6,006\text{s}$).
3. Passenger walks $79.5\text{ m}$ to connecting Stop `568` (*GTB Nagar Metro Station*), arriving at `09:45:34 AM` ($35,134.68\text{ s}$).
4. Under a 1-transfer constraint, the next scheduled DLM1 service departing Stop `568` toward Alipur is Trip `3232_FULL_16_50` departing at **`17:03:24 PM`** ($61,404.0\text{ s}$).
5. **Exact Transfer Wait:**
   $$T_{\text{wait}} = 61,404.0\text{ s} - 35,134.68\text{ s} = \mathbf{26,269.32\text{ s}} \quad (7.297\text{ hours})$$

---

## 3. Implementation of the Long-Transfer Advisory

### 3.1 Architectural Principles
1. **Never Silently Suppress Valid Routes:** A long journey is an authentic Pareto-optimal alternative in bicriterion RAPTOR (it minimizes transfer count to 1). Artificially filtering it would break network reachability.
2. **Never Alter Journey Duration:** The total duration remains strictly $35,324.0\text{ s}$ ($\Delta = 0.0000\text{ s}$).
3. **Transparent Advisory Communication:** Surface a clear advisory in both the JSON API response and the user interface.

### 3.2 Backend Implementation
1. **Schema Updates (`backend/app/schemas/journey.py`):**
   ```python
   long_transfer_advisory: Optional[str] = Field(
       default=None,
       description=(
           "Advisory message when transfer waiting time exceeds 7,200s (2"
           " hours)"
       ),
   )
   has_long_transfer_wait: bool = Field(
       default=False,
       description=(
           "Whether any transfer waiting period exceeds 7,200s (2 hours)"
       ),
   )
```
2. **Evaluation Logic (`backend/app/services/planner_service.py`):**
   ```python
   LONG_TRANSFER_THRESHOLD_S = 7200.0  # 2 hours
   has_long_transfer_wait = False
   long_transfer_advisory = None
   if acct.total_transfer_wait_s > LONG_TRANSFER_THRESHOLD_S:
     has_long_transfer_wait = True
     wait_hours = round(acct.total_transfer_wait_s / 3600.0, 1)
     long_transfer_advisory = (
         f"Extended transfer wait time:"
         f" {int(round(acct.total_transfer_wait_s))}s ({wait_hours:.1f} hours)."
         " This connection has a long scheduled wait between connecting bus"
         " services. Consider comparing other available journey options or"
         " selecting a different departure time."
     )
     journey_warnings.append(long_transfer_advisory)
```

### 3.3 Frontend Implementation
1. **TypeScript Definitions (`frontend/src/types/api.ts`):** Added `long_transfer_advisory` and `has_long_transfer_wait` to `JourneyAlternative`.
2. **UI Component (`frontend/src/components/JourneyCard.tsx`):**
   Renders an orange advisory card with a `Clock` icon when `journey.has_long_transfer_wait` is true:
   ```tsx
   {(journey.long_transfer_advisory || journey.has_long_transfer_wait || accounting.transfer_waiting_time_s > 7200) && (
     <div className="mt-2.5 p-2.5 bg-orange-50 border border-orange-300 rounded-lg text-xs text-orange-900 flex items-start space-x-2 shadow-sm">
       <Clock className="w-4 h-4 text-orange-600 flex-shrink-0 mt-0.5" />
       <div className="space-y-1">
         <span className="font-semibold block text-[12px] text-orange-800">
           Extended Transfer Wait Advisory
         </span>
         <p className="text-[11px] leading-snug text-orange-950">
           {journey.long_transfer_advisory}
         </p>
       </div>
     </div>
   )}
   ```

---

## 4. Multi-Condition Threshold Validation

The advisory behavior was verified across test conditions below, at, and above the $7,200\text{ s}$ threshold:

| Test Scenario | Transfer Wait Time | Condition | `has_long_transfer_wait` | `long_transfer_advisory` | Journey Preserved |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Option 1 (2-Transfer Alternative)** | $1,521.0\text{ s}$ ($25.3\text{ min}$) | $< 7,200\text{ s}$ | `False` | `None` | **Yes** ($8,516\text{s}$) |
| **Boundary Threshold Unit Test** | $7,200.0\text{ s}$ ($2.0\text{ hours}$) | $== 7,200\text{ s}$ | `False` | `None` | **Yes** |
| **Option 2 (1-Transfer Route 3232)** | $26,269.32\text{ s}$ ($7.3\text{ hours}$) | $> 7,200\text{ s}$ | `True` | **Emitted with duration & recommendation** | **Yes** ($35,324\text{s}$) |

---

## 5. Audit Conclusion
The advisory provides actionable guidance to users without hiding valid timetable options or corrupting travel time math. Both automated pytest assertions (`test_transfer_advisory_above_threshold`, `test_transfer_advisory_below_threshold`) and frontend Vitest component tests pass with 100% compliance.

