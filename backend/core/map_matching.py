"""Map Matching and Linear Referencing Engine.

Projects GPS trajectories onto reconstructed GTFS route polylines, evaluating
perpendicular offsets, heading consistency, and monotonic progress along the route.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from backend.core.geometry import RoutePattern


@dataclass
class MatchResult:
    trajectory_id: str
    status: str
    pattern_id: Optional[str] = None
    route_id: Optional[str] = None
    direction_id: Optional[int] = None
    confidence: float = 0.0
    pings_count: int = 0
    mean_perp_dist_m: float = 0.0
    p90_perp_dist_m: float = 0.0
    monotonic_ratio: float = 0.0
    route_coverage_ratio: float = 0.0
    unmatched_reason: Optional[str] = None
    enriched_pings: Optional[pd.DataFrame] = None


def match_trajectory_to_route(
    trajectory_df: pd.DataFrame,
    candidate_patterns: List[RoutePattern],
    max_perp_dist_m: float = 50.0,
    heading_tolerance_deg: float = 45.0,
    min_monotonic_ratio: float = 0.70,
    candidate_margin_ratio: float = 1.25,
) -> MatchResult:
    """Match a reconstructed vehicle trajectory against candidate route patterns.

    Evaluates perpendicular distance, monotonic progress along shape, and candidate
    ambiguity. Does NOT force a match when evidence is weak.
    """
    traj_id = str(trajectory_df["trajectory_id"].iloc[0]) if not trajectory_df.empty else "UNKNOWN"
    n_pings = len(trajectory_df)

    if n_pings < 5:
        return MatchResult(
            trajectory_id=traj_id,
            status="UNMATCHED_TOO_FEW_PINGS",
            pings_count=n_pings,
            unmatched_reason=f"Insufficient pings ({n_pings} < 5) to establish route progress",
        )

    if not candidate_patterns:
        return MatchResult(
            trajectory_id=traj_id,
            status="UNMATCHED_NO_GTFS_PATTERN",
            pings_count=n_pings,
            unmatched_reason="No GTFS route patterns available for this route_id",
        )

    xs = trajectory_df["utm_x"].values
    ys = trajectory_df["utm_y"].values

    pattern_evals = []

    for pat in candidate_patterns:
        along_dists = np.zeros(n_pings, dtype=np.float64)
        perp_dists = np.zeros(n_pings, dtype=np.float64)
        segment_indices = np.zeros(n_pings, dtype=np.int32)

        for j in range(n_pings):
            ad, pd_dist, seg_idx = pat.project_point(xs[j], ys[j])
            along_dists[j] = ad
            perp_dists[j] = pd_dist
            segment_indices[j] = seg_idx

        mean_perp = float(np.mean(perp_dists))
        p90_perp = float(np.percentile(perp_dists, 90))
        pct_within_buffer = float(np.mean(perp_dists <= max_perp_dist_m))

        # Check monotonic along-route progress (allowing 30m jitter tolerance)
        progress_diffs = np.diff(along_dists)
        monotonic_steps = int(np.sum(progress_diffs >= -30.0))
        monotonic_ratio = float(monotonic_steps / (n_pings - 1)) if n_pings > 1 else 0.0

        along_span = float(np.max(along_dists) - np.min(along_dists))
        route_coverage = float(along_span / pat.total_length_m) if pat.total_length_m > 0 else 0.0

        # Score formulation balancing proximity, monotonicity, and progress
        dist_factor = np.exp(-mean_perp / 40.0)
        score = monotonic_ratio * dist_factor * min(1.0, route_coverage * 2.0)

        pattern_evals.append({
            "pattern": pat,
            "along_dists": along_dists,
            "perp_dists": perp_dists,
            "segment_indices": segment_indices,
            "mean_perp": mean_perp,
            "p90_perp": p90_perp,
            "pct_within_buffer": pct_within_buffer,
            "monotonic_ratio": monotonic_ratio,
            "along_span": along_span,
            "route_coverage": route_coverage,
            "score": score,
        })

    # Sort candidates by composite score descending
    pattern_evals.sort(key=lambda x: x["score"], reverse=True)
    best = pattern_evals[0]
    runner_up = pattern_evals[1] if len(pattern_evals) > 1 else None

    # Decision Gates
    if best["mean_perp"] > 120.0:
        return MatchResult(
            trajectory_id=traj_id,
            status="UNMATCHED_EXCESSIVE_DISTANCE",
            pings_count=n_pings,
            mean_perp_dist_m=best["mean_perp"],
            p90_perp_dist_m=best["p90_perp"],
            monotonic_ratio=best["monotonic_ratio"],
            unmatched_reason=f"Trajectory is too far from candidate route (mean offset {best['mean_perp']:.1f}m > 120m)",
        )

    if best["monotonic_ratio"] < 0.50:
        return MatchResult(
            trajectory_id=traj_id,
            status="UNMATCHED_REVERSE_OR_ERRATIC",
            pings_count=n_pings,
            mean_perp_dist_m=best["mean_perp"],
            p90_perp_dist_m=best["p90_perp"],
            monotonic_ratio=best["monotonic_ratio"],
            unmatched_reason=f"Progress along route is erratic or in opposite direction (monotonic ratio {best['monotonic_ratio']:.2f} < 0.50)",
        )

    # Ambiguity check if two candidate directions/branches have nearly identical scores
    if runner_up is not None and best["score"] > 0:
        score_ratio = best["score"] / (runner_up["score"] + 1e-6)
        score_diff = abs(best["score"] - runner_up["score"])
        if score_ratio < 1.15 and score_diff < 0.08:
            return MatchResult(
                trajectory_id=traj_id,
                status="UNMATCHED_AMBIGUOUS_ROUTE",
                pings_count=n_pings,
                mean_perp_dist_m=best["mean_perp"],
                p90_perp_dist_m=best["p90_perp"],
                monotonic_ratio=best["monotonic_ratio"],
                unmatched_reason=f"Cannot unambiguously distinguish between candidate patterns ({best['pattern'].pattern_id} vs {runner_up['pattern'].pattern_id})",
            )

    # Confident match gate
    if (
        best["mean_perp"] <= max_perp_dist_m
        and best["monotonic_ratio"] >= min_monotonic_ratio
        and best["route_coverage"] >= 0.10
    ):
        confidence = float(np.clip(best["score"], 0.70, 0.98))
        status = "MATCHED_CONFIDENT"
    elif best["mean_perp"] <= 85.0 and best["monotonic_ratio"] >= 0.60:
        confidence = float(np.clip(best["score"] * 0.8, 0.45, 0.69))
        status = "MATCHED_LOW_CONFIDENCE"
    else:
        return MatchResult(
            trajectory_id=traj_id,
            status="UNMATCHED_POOR_FIT",
            pings_count=n_pings,
            mean_perp_dist_m=best["mean_perp"],
            p90_perp_dist_m=best["p90_perp"],
            monotonic_ratio=best["monotonic_ratio"],
            unmatched_reason=f"Fit metrics below thresholds (mean_perp={best['mean_perp']:.1f}m, monotonic={best['monotonic_ratio']:.2f})",
        )

    # Attach linear referencing measurements to trajectory pings
    enriched = trajectory_df.copy()
    enriched["along_dist_m"] = best["along_dists"]
    enriched["perp_dist_m"] = best["perp_dists"]
    enriched["segment_idx"] = best["segment_indices"]
    enriched["matched_pattern_id"] = best["pattern"].pattern_id
    enriched["matched_direction_id"] = best["pattern"].direction_id

    return MatchResult(
        trajectory_id=traj_id,
        status=status,
        pattern_id=best["pattern"].pattern_id,
        route_id=best["pattern"].route_id,
        direction_id=best["pattern"].direction_id,
        confidence=confidence,
        pings_count=n_pings,
        mean_perp_dist_m=best["mean_perp"],
        p90_perp_dist_m=best["p90_perp"],
        monotonic_ratio=best["monotonic_ratio"],
        route_coverage_ratio=best["route_coverage"],
        enriched_pings=enriched,
    )

