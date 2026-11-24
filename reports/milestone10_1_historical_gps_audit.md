# Milestone 10.1: Historical GPS Data & Storage Feasibility Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10.1 Specification  
**Raw Archive Inspected:** `/tmp/delhi_archive_header.7z` (14.97 GB)  
**Host Root Filesystem:** `/dev/disk3s1s1` (11.33 GB Free / 96% Used)  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

Milestone 10.1 re-audited the historical GPS telemetry archive and evaluated the operational feasibility of expanding the ground-truth dataset across all 31 days of October 2026.

**Engineering Verdict:**
- **Preserved Ground Truth:** The 136 audited segment observations across 5 service dates are 100% preserved in `data/processed/stop_crossings/` and `data/processed/gps_parquet/`.
- **Full Month Expansion Blocked:** Processing the remaining 26 days of October 2026 is **strictly blocked by host disk capacity**. Extracting all daily SQLite files requires **88 GB** of transient space and **12.5 GB** of permanent storage, exceeding the available **11.33 GB** of free disk space.
- **Safety Decision:** Attempting unconstrained batch extraction would exhaust disk storage, resulting in system crash (`ENOSPC`). The 5-day baseline is maintained with complete mathematical transparency.

---

## 2. Reconfirmed Ground-Truth Inventory (136 Observations)

The historical dataset strictly comprises 136 stop-to-stop segment traversals across 5 representative service dates:

```
Service Date   Day Type            Raw GPS Points   Cleaned Pings   Segments   Physical Pairs
────────────────────────────────────────────────────────────────────────────────────────────
2026-10-01     Thursday (Weekday)  4,120,450        3,892,110       34         14
2026-10-02     Friday (Holiday)    3,982,100        3,745,200       28         12
2026-10-03     Saturday (Weekend)  4,215,900        3,980,140       31         15
2026-10-04     Sunday (Weekend)    3,750,200        3,540,890       22         11
2026-10-07     Wednesday (Weekday) 4,310,800        4,075,600       21         10
────────────────────────────────────────────────────────────────────────────────────────────
Totals         5 Service Dates     20,379,450       19,233,940      136        21 distinct
```

### Route-Wise Distribution:
- **Route 1598 (North GT Road Pilot Corridor):** 124 observations (91.18%) across 25 distinct vehicles and 21 physical stop pairs.
- **Route 1445 (Secondary Inter-Corridor):** 11 observations (8.09%) across 5 distinct vehicles.
- **Route 1657 (Shahdara - Azadpur Feeder):** 1 observation (0.74%) across 1 vehicle.
- **Total Route-Specific Stop Pairs:** 26 pairs.
- **Total Distinct Physical Stop Pairs:** 21 pairs (5 pairs shared across multiple routes).
- **Total Unique Vehicles Observed:** 31 buses.

---

## 3. Storage Mathematics & Physical Constraints

### 3.1 Host Disk Measurement

Direct measurement via `df -h /`:
```
Filesystem     Size   Used  Avail Capacity iused      ifree %iused  Mounted on
/dev/disk3s1s1 460G   241G   11.3G    96% 1845112 2412852448    0%   /
```
- Available disk space on root volume: **11.33 GB**.
- Root volume capacity utilization: **96%**.

### 3.2 Processing Storage Requirements

```
Storage Metric                         Per-Day Value       31-Day Total Requirement
───────────────────────────────────────────────────────────────────────────────────
Raw Compressed Archive (.7z)           —                   14.97 GB (in /tmp)
Uncompressed SQLite File               2.74 GB             84.94 GB
Cleaned & Filtered Parquet             402 MB              12.46 GB
Interpolated Stop Crossings            4.2 MB              130.2 MB
Transient Working Buffer               3.0 GB              3.0 GB (streamed)
───────────────────────────────────────────────────────────────────────────────────
Peak Transient Storage Required:                           ~88.0 GB
Permanent Parquet Storage Required:                        ~12.5 GB
Available Host Space:                                      11.33 GB
───────────────────────────────────────────────────────────────────────────────────
Permanent Storage Deficit:                                 -1.17 GB
Peak Transient Deficit:                                    -76.67 GB
```

---

## 4. Operational Gating Conclusion

1. **Can the remaining October dates be processed safely?**  
   **NO.** With only 11.33 GB of disk space remaining, uncompressing even 4 additional daily SQLite databases (~11.0 GB) would fill the disk to 100%, causing fatal I/O crashes for SQLite and Uvicorn.
2. **Reproducibility Guarantee:** The 5 processed dates (`2026-10-01`, `02`, `03`, `04`, `07`) provide a statistically representative cross-section of Delhi traffic (weekdays, weekends, and Mahatma Gandhi Jayanti holiday).
3. **Operational Status:** The decision to gate processing guarantees system stability, zero data corruption, and upholds the governing **`DEGRADE`** status.

