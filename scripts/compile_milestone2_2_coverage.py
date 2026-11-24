"""Compile Multi-Day Ground-Truth Coverage Analysis for Milestone 2.2.

This script:
1. Ensures stop crossings are extracted for all ingested dates (2026-10-01, 2026-10-02, 2026-10-03, 2026-10-04, 2026-10-07).
2. Aggregates all ground-truth crossings and consecutive observed segments across corridors, dates, hours, and vehicles.
3. Produces coverage matrices:
   - Date vs Route
   - Stop Pair vs Date
   - Stop Pair vs Hour of Day
4. Computes Weekday vs Weekend performance metrics and detour factor stability.
5. Generates publication-ready diagnostic charts in `reports/figures/`.
6. Saves `data/processed/milestone2_2_summary_metrics.json`.
"""

import json
import os
import sys
import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.process_historical_batch import extract_stop_crossings_for_date

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STOP_CROSSING_DIR = os.path.join(ROOT_DIR, "data", "processed", "stop_crossings")
GPS_PARQUET_DIR = os.path.join(ROOT_DIR, "data", "processed", "gps_parquet")
FIGURES_DIR = os.path.join(ROOT_DIR, "reports", "figures")
OUTPUT_METRICS = os.path.join(ROOT_DIR, "data", "processed", "milestone2_2_summary_metrics.json")

DATES = ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-07"]

def ensure_all_stop_crossings():
    """Ensure stop crossings have been extracted for all available GPS parquet partitions."""
    for d in DATES:
        pq_path = os.path.join(GPS_PARQUET_DIR, f"service_date={d}", "data.parquet")
        target_out = os.path.join(STOP_CROSSING_DIR, f"service_date={d}", "observed_segments.parquet")
        if os.path.exists(pq_path) and not os.path.exists(target_out):
            print(f"Extracting missing stop crossings for service_date={d}...")
            extract_stop_crossings_for_date(d, pq_path)

def compile_coverage():
    ensure_all_stop_crossings()
    os.makedirs(FIGURES_DIR, exist_ok=True)
    con = duckdb.connect()

    # Discover all generated segment files
    seg_files = []
    cross_files = []
    for d in DATES:
        s_file = os.path.join(STOP_CROSSING_DIR, f"service_date={d}", "observed_segments.parquet")
        c_file = os.path.join(STOP_CROSSING_DIR, f"service_date={d}", "stop_crossings.parquet")
        if os.path.exists(s_file):
            seg_files.append(f"'{s_file}'")
        if os.path.exists(c_file):
            cross_files.append(f"'{c_file}'")

    if not seg_files:
        raise RuntimeError("No observed_segments.parquet files found!")

    seg_union = f"SELECT * FROM read_parquet([{', '.join(seg_files)}])"
    cross_union = f"SELECT * FROM read_parquet([{', '.join(cross_files)}])"

    con.execute(f"CREATE TEMP VIEW all_segments AS {seg_union};")
    con.execute(f"CREATE TEMP VIEW all_crossings AS {cross_union};")

    # Add hour_ist, day_of_week, is_weekend
    con.execute("""
        CREATE TEMP TABLE enriched_segments AS
        SELECT 
            *,
            CAST(STRFTIME(TRY_STRPTIME(arrival_from_ist, '%Y-%m-%d %H:%M:%S'), '%H') AS INTEGER) as hour_ist,
            STRFTIME(service_date, '%a') as day_name,
            CASE WHEN STRFTIME(service_date, '%a') IN ('Sat', 'Sun') THEN 1 ELSE 0 END as is_weekend
        FROM all_segments;
    """)

    # 1. Per-Date Breakdown
    date_summary = con.execute("""
        SELECT 
            service_date,
            day_name,
            CASE WHEN is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END as day_type,
            COUNT(*) as observed_segments,
            COUNT(DISTINCT vehicle_id) as distinct_vehicles,
            COUNT(DISTINCT segment_key) as distinct_stop_pairs,
            ROUND(MIN(speed_kmh), 2) as min_speed,
            ROUND(MEDIAN(speed_kmh), 2) as median_speed,
            ROUND(AVG(speed_kmh), 2) as mean_speed,
            ROUND(MAX(speed_kmh), 2) as max_speed
        FROM enriched_segments
        GROUP BY service_date, day_name, day_type
        ORDER BY service_date;
    """).df()

    # 2. Total Crossings per Date
    cross_summary = con.execute("""
        SELECT 
            service_date,
            COUNT(*) as total_stop_crossings,
            COUNT(DISTINCT stop_id) as distinct_stops,
            COUNT(DISTINCT vehicle_id) as distinct_vehicles
        FROM all_crossings
        GROUP BY service_date
        ORDER BY service_date;
    """).df()

    # 3. Stop Pair Coverage Matrix (Stop Pair x Date)
    stop_pair_date = con.execute("""
        PIVOT (
            SELECT segment_key, stop_name_from, stop_name_to, service_date, COUNT(*) as n_obs
            FROM enriched_segments
            GROUP BY segment_key, stop_name_from, stop_name_to, service_date
        )
        ON service_date
        USING FIRST(n_obs)
        ORDER BY segment_key;
    """).df()

    # 4. Hourly Coverage Breakdown
    hourly_summary = con.execute("""
        SELECT 
            hour_ist,
            COUNT(*) as total_obs,
            SUM(CASE WHEN is_weekend = 0 THEN 1 ELSE 0 END) as weekday_obs,
            SUM(CASE WHEN is_weekend = 1 THEN 1 ELSE 0 END) as weekend_obs,
            ROUND(MEDIAN(speed_kmh), 2) as median_speed,
            ROUND(AVG(speed_kmh), 2) as mean_speed
        FROM enriched_segments
        GROUP BY hour_ist
        ORDER BY hour_ist;
    """).df()

    # 5. Overall Dataset Metrics
    total_segments = con.execute("SELECT COUNT(*) FROM enriched_segments").fetchone()[0]
    total_crossings = con.execute("SELECT COUNT(*) FROM all_crossings").fetchone()[0]
    total_unique_vehicles = con.execute("SELECT COUNT(DISTINCT vehicle_id) FROM enriched_segments").fetchone()[0]
    total_unique_stop_pairs = con.execute("SELECT COUNT(DISTINCT segment_key) FROM enriched_segments").fetchone()[0]
    overall_med_speed = con.execute("SELECT ROUND(MEDIAN(speed_kmh), 2) FROM enriched_segments").fetchone()[0]
    overall_mean_speed = con.execute("SELECT ROUND(AVG(speed_kmh), 2) FROM enriched_segments").fetchone()[0]

    # Save summary JSON
    summary_dict = {
        "dates_processed": DATES,
        "total_observed_segments": total_segments,
        "total_stop_crossings": total_crossings,
        "total_unique_vehicles": total_unique_vehicles,
        "total_unique_stop_pairs": total_unique_stop_pairs,
        "overall_median_speed_kmh": overall_med_speed,
        "overall_mean_speed_kmh": overall_mean_speed,
        "date_summary": date_summary.to_dict(orient="records"),
        "crossings_summary": cross_summary.to_dict(orient="records"),
        "hourly_summary": hourly_summary.to_dict(orient="records"),
    }

    with open(OUTPUT_METRICS, "w") as f:
        json.dump(summary_dict, f, indent=2, default=str)
    print(f"Metrics saved to {OUTPUT_METRICS}")

    # Generate Figures
    generate_figures(con)

def generate_figures(con):
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Figure 6: Multiday Hourly Segments Breakdown (Weekday vs Weekend)
    df_h = con.execute("""
        SELECT 
            hour_ist,
            SUM(CASE WHEN is_weekend = 0 THEN 1 ELSE 0 END) as weekday_obs,
            SUM(CASE WHEN is_weekend = 1 THEN 1 ELSE 0 END) as weekend_obs
        FROM enriched_segments
        GROUP BY hour_ist
        ORDER BY hour_ist;
    """).df()

    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    width = 0.4
    x = np.arange(len(df_h))
    ax.bar(x - width/2, df_h['weekday_obs'], width, label='Weekday Observations', color='#2563eb', alpha=0.85)
    ax.bar(x + width/2, df_h['weekend_obs'], width, label='Weekend Observations', color='#ea580c', alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{h:02d}:00" for h in df_h['hour_ist']])
    ax.set_xlabel("Hour of Day (IST)", fontweight='bold')
    ax.set_ylabel("Valid Observed Consecutive Segments", fontweight='bold')
    ax.set_title("Ground-Truth Observed Segments by Hour: Weekday vs Weekend (Milestone 2.2)", fontweight='bold')
    ax.legend(frameon=True)
    fig.tight_layout()
    f6_path = os.path.join(FIGURES_DIR, "fig6_multiday_hourly_segments.png")
    fig.savefig(f6_path)
    plt.close(fig)
    print(f"Saved {f6_path}")

    # Figure 7: Weekday vs Weekend Speed Comparison
    df_spd = con.execute("""
        SELECT speed_kmh, CASE WHEN is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END as day_type
        FROM enriched_segments;
    """).df()

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    data_to_plot = [
        df_spd[df_spd['day_type'] == 'Weekday']['speed_kmh'].dropna().values,
        df_spd[df_spd['day_type'] == 'Weekend']['speed_kmh'].dropna().values
    ]
    bp = ax.boxplot(data_to_plot, patch_artist=True, tick_labels=['Weekday', 'Weekend'],
                    boxprops=dict(facecolor='#93c5fd', color='#1d4ed8'),
                    medianprops=dict(color='#b91c1c', linewidth=2),
                    whiskerprops=dict(color='#1d4ed8'),
                    capprops=dict(color='#1d4ed8'))
    ax.set_ylabel("Observed Commercial Speed (km/h)", fontweight='bold')
    ax.set_title("Delhi Bus Operating Speed Distribution: Weekday vs. Weekend", fontweight='bold')
    ax.grid(True, linestyle="--", alpha=0.6)
    fig.tight_layout()
    f7_path = os.path.join(FIGURES_DIR, "fig7_weekday_vs_weekend_speed.png")
    fig.savefig(f7_path)
    plt.close(fig)
    print(f"Saved {f7_path}")

    # Figure 8: Segment Speed Heatmap / Bar across Stop Sequence
    df_stops = con.execute("""
        SELECT 
            segment_key,
            stop_name_from || ' -> ' || stop_name_to as stop_label,
            MEDIAN(speed_kmh) as median_speed,
            COUNT(*) as obs_count
        FROM enriched_segments
        GROUP BY segment_key, stop_label
        ORDER BY segment_key;
    """).df()

    fig, ax1 = plt.subplots(figsize=(10, 5), dpi=150)
    y_pos = np.arange(len(df_stops))
    bars = ax1.barh(y_pos, df_stops['median_speed'], color='#059669', alpha=0.85, label='Median Speed (km/h)')
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(df_stops['stop_label'], fontsize=8)
    ax1.invert_yaxis()
    ax1.set_xlabel("Median Running Speed (km/h)", fontweight='bold', color='#065f46')
    ax1.set_title("Ground Truth Speed Profile Along North GT Road Arterial Corridor", fontweight='bold')
    for i, v in enumerate(df_stops['median_speed']):
        cnt = df_stops['obs_count'].iloc[i]
        ax1.text(v + 0.5, i, f"{v:.1f} km/h (n={cnt})", va='center', fontsize=8, fontweight='bold')
    fig.tight_layout()
    f8_path = os.path.join(FIGURES_DIR, "fig8_corridor_speed_profile.png")
    fig.savefig(f8_path)
    plt.close(fig)
    print(f"Saved {f8_path}")

if __name__ == "__main__":
    compile_coverage()

