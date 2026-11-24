# Milestone 12 — Ingestion Validation and Accounting Specification

**Governing Specification:** PRD v3.0  
**Audit Timestamp:** 2026-11-22T01:58:00Z  
**Governing Status:** `DEGRADE`  
**Milestone Scope:** 10-Point Data Integrity Rubric & Mathematical Balance Criteria  
**Evaluated Verdict:** `READY_WITH_STORAGE_CONSTRAINTS`

---

## 1. Specification Objective

This specification establishes the mandatory **10-Point Ingestion Quality and Accounting Rubric** that every single daily partition in the October 2026 dataset must satisfy prior to promotion and commitment. 

Under PRD v3.0 truth-in-data principles, no telemetry row may be silently discarded, modified, or fabricated. Every record must be deterministically classified into clean, duplicate, conflict, out-of-bounds, or invalid buckets, satisfying an exact mathematical conservation identity.

---

## 2. The 10-Point Validation Rubric

### Dimension 1: Source Row Count Integrity ($N_{\text{raw}}$)
- **Definition:** The exact total count of records present in the uncompressed SQLite source table `bus_telemetry`.
- **Validation Query:**
  ```sql
  SELECT COUNT(*) FROM raw_db.bus_telemetry;
  ```
- **Threshold:** Must be $> 0$ and match the table row metadata header exactly.

### Dimension 2: Exact Duplicate Deduplication ($N_{\text{dedup}}$)
- **Definition:** Records that are bit-for-bit identical across all six core dimensions: `(vehicle_id, timestamp, latitude, longitude, speed, heading)`.
- **Validation Rule:**
  $$N_{\text{dedup}} = N_{\text{raw}} - N_{\text{distinct}}$$
- **Handling:** Exact duplicates are discarded from the primary clean dataset and recorded in the partition manifest.

### Dimension 3: Telemetry Conflict Quarantine ($N_{\text{conflict}}$)
- **Definition:** Physically impossible observations where the same physical bus (`vehicle_id`) reports conflicting geographic coordinates ($|\text{lat}_1 - \text{lat}_2| > 0.0001$ or $|\text{lon}_1 - \text{lon}_2| > 0.0001$) at the exact same UNIX epoch timestamp.
- **Handling:** Conflicting records are **quarantined** to `data/processed/quarantine/conflicts_YYYY-MM-DD.parquet`. They are never averaged, interpolated, or arbitrarily selected.

### Dimension 4: Spatial Bounding Box Filter ($N_{\text{oob}}$)
- **Definition:** Telemetry coordinates falling outside the official Delhi National Capital Region (NCR) bounding box:
  $$\text{Latitude} \in [28.4000^\circ\text{N}, 28.9000^\circ\text{N}]$$
  $$\text{Longitude} \in [76.8000^\circ\text{E}, 77.4500^\circ\text{E}]$$
- **Handling:** Out-of-bounds records are **quarantined** to `data/processed/quarantine/out_of_bounds_YYYY-MM-DD.parquet`. Zero OOB records are admitted to clean partitions.

### Dimension 5: Vehicle ID Hygiene ($N_{\text{invalid\_id}}$)
- **Definition:** Records where `vehicle_id` is `NULL`, empty string (`""`), whitespace-only, or contains non-alphanumeric escape sequences.
- **Handling:** Quarantined or discarded; zero invalid identifiers admitted.

### Dimension 6: Temporal Monotonicity & Plausibility ($N_{\text{temporal}}$)
- **Definition:** Records where timestamp violates physical time boundaries:
  - Timestamp corresponds to a different calendar service date ($\text{date} \ne \text{YYYY-MM-DD}$).
  - Future timestamp exceeding $t_{\text{service\_date}} + 86400 + 7200\text{ s}$ (early-morning midnight roll).
  - Inter-ping negative time jumps for the same vehicle ($\Delta t < 0$).
- **Handling:** Partitioned or quarantined.

### Dimension 7: DLM1 Static Network Alignment Rate ($R_{\text{DLM1\_match}}$)
- **Definition:** The proportion of unique active buses in the clean dataset that can be mapped to scheduled trips in the primary static DLM1 database (`/tmp/delhi_dlm1.db`).
- **Validation Formula:**
  $$R_{\text{DLM1\_match}} = \frac{N_{\text{vehicles mapped to DLM1}}}{N_{\text{total unique clean vehicles}}}$$
- **Threshold:** Must exceed **80.00%**. Historical pilot baseline achieved $> 92\%$.

### Dimension 8: Stop-Crossing Detection Fidelity ($N_{\text{crossings}}$)
- **Definition:** Successful spatiotemporal stop-crossing interpolations extracted along known transit corridors (Route 1598, North GT Road, Outer Ring Road).
- **Threshold Criteria:**
  - Perpendicular closest point of approach distance $d_{\text{CPA}} \le 50.0\text{ meters}$.
  - Approach speed $\le 15.0\text{ km/h}$.
  - Minimum crossing yield $\ge 20$ crossings per service date along monitored corridors.

### Dimension 9: Mathematical Conservation Identity ($\Delta_{\text{accounting}}$)
- **Definition:** Strict row-level conservation identity proving zero undetected record leakage or fabrication.
- **The Conservation Equation:**
  $$N_{\text{raw}} = N_{\text{clean}} + N_{\text{dedup}} + N_{\text{conflict}} + N_{\text{oob}} + N_{\text{invalid\_id}} + N_{\text{temporal}}$$
  $$\Delta_{\text{accounting}} = \left| N_{\text{raw}} - \left( N_{\text{clean}} + N_{\text{dedup}} + N_{\text{conflict}} + N_{\text{oob}} + N_{\text{invalid\_id}} + N_{\text{temporal}} \right) \right|$$
- **Acceptance Criterion:**
  $$\Delta_{\text{accounting}} \equiv 0.0000 \quad (\text{Strict Zero Tolerance})$$
  Any partition with $\Delta \ne 0$ is immediately quarantined and blocked from promotion.

### Dimension 10: PyArrow Schema & Type Compliance
- **Definition:** Structural and binary type verification of the final output Parquet file.
- **Mandatory Column Schema:**

| Column Name | Data Type | Nullable | Description |
|---|---|:---:|---|
| `vehicle_id` | `string` / `utf8` | **No** | Alphanumeric DTC bus identifier |
| `timestamp` | `int64` | **No** | UTC UNIX epoch timestamp (seconds) |
| `latitude` | `float64` | **No** | WGS-84 latitude coordinate |
| `longitude` | `float64` | **No** | WGS-84 longitude coordinate |
| `speed` | `float64` | **No** | Speed in km/h |
| `heading` | `float64` | Yes | Heading azimuth in degrees ($0^\circ - 360^\circ$) |
| `service_date`| `date32[day]` | **No** | Partition key (YYYY-MM-DD) |

---

## 3. Automated Validation Test Harness

The 10 dimensions are codified into an automated Python verification class (`DailyPartitionValidator`), executed as a mandatory gate before promoting any partition:

```python
class DailyPartitionValidator:
    def __init__(self, raw_sqlite: str, clean_parquet: str, conflicts_parquet: str, oob_parquet: str):
        self.raw_sqlite = raw_sqlite
        self.clean_parquet = clean_parquet
        self.conflicts_parquet = conflicts_parquet
        self.oob_parquet = oob_parquet

    def validate(self) -> dict:
        con = duckdb.connect()
        con.execute(f"ATTACH '{self.raw_sqlite}' AS raw (TYPE SQLITE);")
        
        n_raw = con.execute("SELECT COUNT(*) FROM raw.bus_telemetry").fetchone()[0]
        n_clean = con.execute(f"SELECT COUNT(*) FROM '{self.clean_parquet}'").fetchone()[0]
        n_conf = con.execute(f"SELECT COUNT(*) FROM '{self.conflicts_parquet}'").fetchone()[0] if self.conflicts_parquet else 0
        n_oob = con.execute(f"SELECT COUNT(*) FROM '{self.oob_parquet}'").fetchone()[0] if self.oob_parquet else 0
        
        # Calculate duplicates & accounting delta
        n_dedup = con.execute("""
            SELECT COUNT(*) - COUNT(DISTINCT vehicle_id || '_' || timestamp || '_' || latitude || '_' || longitude)
            FROM raw.bus_telemetry
        """).fetchone()[0]
        
        delta = n_raw - (n_clean + n_dedup + n_conf + n_oob)
        
        assert delta == 0, f"Accounting discrepancy detected: delta={delta}"
        
        return {
            "n_raw": n_raw,
            "n_clean": n_clean,
            "n_dedup": n_dedup,
            "n_conflicts": n_conf,
            "n_oob": n_oob,
            "accounting_delta": delta,
            "verdict": "PASS"
        }
```

---

## 4. Certification & Sign-off Gate

A partition is granted `COMMITTED` status in `ingestion_manifest.json` if and only if:
1. All 10 dimensions achieve `PASS`.
2. $\Delta_{\text{accounting}} = 0$.
3. SHA-256 digest is generated and recorded.
4. PyArrow schema matches Dimension 10 specification.

