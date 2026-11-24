# Milestone 11.5 — Alternative Journey Recommendations & Multi-Transfer Verification

**Governing specification:** PRD v3.0  
**Current primary database:** DLM1 (`/tmp/delhi_dlm1.db`)  
**Current system status:** `DEGRADE`  
**Previous milestone:** M11.4 — `QUALITY_AUDIT_PASSED_WITH_LIMITATIONS`  
**Evaluation date:** 2026-11-21  

---

## 1. Executive Summary

This audit independently validates the 2-transfer alternative discovered by RAPTOR for travel between **Stop 2280** (*Nehru Nagar*) and **Stop 5321** (*Alipur Blk.(BDO Office)*). In Milestone 11.4, when query parameters permitted up to 2 bus transfers (`max_transfers: 3`), RAPTOR identified a dramatically faster connection taking **$8,516.0\text{ seconds}$ ($2.37\text{ hours}$)** compared to the 9.81-hour 1-transfer option.

This audit traces each constituent transit leg, verifying physical stop sequences, scheduled departure and arrival timestamps, transfer walking geometry, transfer waiting intervals, and strict time conservation without synthetic interpolation.

---

## 2. In-Depth Audit of the 2-Transfer Alternative (Option 1)

### 2.1 Complete Itinerary & Leg Accounting Table

| Leg # | Mode | Route | Trip ID | Board Stop | Alight Stop | Sched Dep | Sched Arr | Duration (s) | Transfer Wait (s) | Walk Dist (m) |
|:---:|:---:|:---:|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **0** | TRANSIT | Route `1965` | `1965_FULL_07_30` | `2280` (Nehru Nagar) | `4975` (Regal / Palika Kendra) | 08:04:48 | 08:42:44 | 2,276.0 | N/A (Init: 288s) | N/A |
| **Transfer 1** | WALK / NODE | N/A | N/A | `4975` (Same Stop) | `4975` (Same Stop) | 08:42:44 | 08:48:15 | 0.0 | **331.0 s** ($5.5\text{m}$) | 0.0 m |
| **1** | TRANSIT | Route `1506` | `1506_FULL_08_40` | `4975` (Regal / Palika Kendra) | `289` (GTK Depot) | 08:48:15 | 09:41:10 | 3,175.0 | N/A | N/A |
| **Transfer 2** | WALK / NODE | N/A | N/A | `289` (Same Stop) | `289` (Same Stop) | 09:41:10 | 10:01:00 | 0.0 | **1,190.0 s** ($19.8\text{m}$) | 0.0 m |
| **2** | TRANSIT | Route `276` | `276_FULL_10_01` | `289` (GTK Depot) | `5321` (Alipur BDO Office) | 10:01:00 | 10:21:56 | 1,256.0 | N/A | N/A |
| **Total** | | | | **2280** | **5321** | **08:00:00** | **10:21:56** | **8,516.0 s** | **1,521.0 s** | **0.0 m** |

### 2.2 Mathematical Accounting Conservation
- **Access Walk Time:** $0.00\text{ s}$
- **Initial Wait Time:** $29,088.0\text{ s} - 28,800.0\text{ s} = 288.00\text{ s}$ ($4.80\text{ min}$)
- **In-Vehicle Riding Time:** $2,276.0 + 3,175.0 + 1,256.0 = 6,707.00\text{ s}$ ($111.78\text{ min}$)
- **Transfer Walk Time:** $0.00\text{ s}$ (both transfers occur at co-located platforms at Regal and GTK Depot)
- **Transfer Wait Time:** $331.0 + 1,190.0 = 1,521.00\text{ s}$ ($25.35\text{ min}$)
- **Egress Walk Time:** $0.00\text{ s}$
- **Sum of All Components:**
  $$\sum T = 288.00 + 6,707.00 + 0.00 + 1,521.00 + 0.00 = \mathbf{8,516.00\text{ s}}$$
- **Reported Total Journey Duration:** **$8,516.00\text{ s}$**
- **Discrepancy ($\Delta$):** **$0.0000\text{ s}$** (Mathematically Exact Conservation)

### 2.3 Chronological Monotonicity & Operational Continuity
- **Leg 0 $\to$ Leg 1:** Passenger arrives at Stop `4975` at `08:42:44 AM`. Connecting Trip `1506_FULL_08_40` departs at `08:48:15 AM`. Buffer: $5.5\text{ minutes}$. Positive, physically viable transfer.
- **Leg 1 $\to$ Leg 2:** Passenger arrives at Stop `289` at `09:41:10 AM`. Connecting Trip `276_FULL_10_01` departs at `10:01:00 AM`. Buffer: $19.8\text{ minutes}$. Positive, physically viable transfer.
- **Stop Alignment:** Alighting stop of Leg 0 (`4975`) strictly equals boarding stop of Leg 1 (`4975`). Alighting stop of Leg 1 (`289`) strictly equals boarding stop of Leg 2 (`289`). No teleportation or invalid walking hops occur.

---

## 3. Comparison of Pareto-Optimal Journey Alternatives

### Table 2: Non-Dominated Pareto Front for Query (Stop 2280 $\to$ 5321 at 08:00:00)

| Metric | Option 1 (Multi-Transfer) | Option 2 (Minimal Transfers) | Comparison / Tradeoff |
|:---|:---:|:---:|:---|
| **Transfers** | **2 transfers** | **1 transfer** | Option 2 requires 1 fewer transfer |
| **Total Duration** | **$8,516.0\text{ s}$ ($2.37\text{ hours}$)** | **$35,324.0\text{ s}$ ($9.81\text{ hours}$)** | Option 1 arrives **7.44 hours earlier** |
| **Departure Time** | 08:04:48 | 08:04:06 | Approximately identical start |
| **Arrival Time** | **10:21:56 AM** | **17:48:44 PM** | Evening arrival vs Mid-morning arrival |
| **Total Transfer Wait** | **$1,521.0\text{ s}$ ($25.35\text{ min}$)** | **$26,269.32\text{ s}$ ($7.30\text{ hours}$)** | Option 2 has 17x longer transfer wait |
| **Advisory Emitted** | None (Below 7,200s) | **`has_long_transfer_wait: true`** | Option 2 triggers prominent advisory banner |
| **Pareto Dominance** | Non-dominated | Non-dominated | Legitimate bicriterion Pareto front |

---

## 4. Representative Sample Journey Audits on DLM1

### Table 3: Cross-Corridor Quality Sample

| Corridor Tested | Route / Mode | Origin $\to$ Dest | Status | Duration (s) | Prediction Tier | Verified Valid |
|:---|:---:|:---|:---:|:---:|:---:|:---:|
| **North GT Road Pilot** | Route `1598` (Direct) | Stop `239` $\to$ Stop `247` | 200 OK | 1,021.5 | `LEVEL_1_DIRECT_OBSERVED` | **YES** |
| **North Delhi Trunk** | Route `284` (Direct) | Stop `284` $\to$ Stop `5146` | 200 OK | 527.0 | `LEVEL_4_GTFS_SCHEDULED` | **YES** |
| **Trans-Yamuna Direct** | Route `214` (Direct) | Stop `310` $\to$ Stop `1805` | 200 OK | 1,840.0 | `LEVEL_4_GTFS_SCHEDULED` | **YES** |
| **Central Cross-City** | Route `1965` $\to$ `276` (1 Transfer) | Stop `2280` $\to$ Stop `289` | 200 OK | 6,340.0 | `LEVEL_4_GTFS_SCHEDULED` | **YES** |

---

## 5. Audit Conclusion
The alternative recommendation (Option 1) is thoroughly verified against official DLM1 timetables. It demonstrates that RAPTOR's Pareto optimization successfully identifies fast, practical multi-transfer alternatives while honestly surfacing the single-transfer alternative accompanied by the newly implemented extended-wait advisory.

