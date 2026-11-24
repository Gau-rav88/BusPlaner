/**
 * Formatting and Helper Utilities for Transit Journey Display.
 */

import { PredictionTier } from '../types/api';

/**
 * Format seconds since midnight into 12-hour or 24-hour HH:MM format.
 * Supports post-midnight times (e.g. t >= 86400s -> 25:10 -> 01:10 AM next day).
 */
export function formatSecondsToTime(sec: number): string {
  if (isNaN(sec)) return '--:--';
  const totalSec = Math.round(sec);
  const normalizedSec = totalSec % 86400;
  const h24 = Math.floor(normalizedSec / 3600);
  const m = Math.floor((normalizedSec % 3600) / 60);

  const period = h24 >= 12 ? 'PM' : 'AM';
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
  const mStr = m.toString().padStart(2, '0');

  const nextDaySuffix = totalSec >= 86400 ? ' (+1d)' : '';
  return `${h12}:${mStr} ${period}${nextDaySuffix}`;
}

/**
 * Format elapsed duration in seconds into human-readable string.
 */
export function formatDuration(sec: number): string {
  if (isNaN(sec) || sec <= 0) return '0 min';
  const totalMin = Math.round(sec / 60);
  if (totalMin < 60) {
    return `${totalMin} min`;
  }
  const h = Math.floor(totalMin / 60);
  const remM = totalMin % 60;
  return remM > 0 ? `${h}h ${remM}m` : `${h}h`;
}

/**
 * Format distance in meters into m or km.
 */
export function formatDistance(meters: number): string {
  if (isNaN(meters) || meters <= 0) return '0 m';
  if (meters < 1000) {
    return `${Math.round(meters)} m`;
  }
  return `${(meters / 1000).toFixed(1)} km`;
}

/**
 * Format UTC unix epoch timestamp into Asia/Kolkata (IST) time string HH:MM:SS.
 */
export function formatEpochToIST(epochSec: number | null | undefined): string {
  if (!epochSec || epochSec <= 0) return 'N/A';
  try {
    return new Date(epochSec * 1000).toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour12: false,
    });
  } catch {
    return 'N/A';
  }
}

/**
 * Format prediction tier into human-readable description and visual badge styling.
 */
export function formatPredictionTier(tier: PredictionTier): {
  label: string;
  shortLabel: string;
  badgeClass: string;
  description: string;
} {
  switch (tier) {
    case 'LEVEL_1_DIRECT_OBSERVED':
      return {
        label: 'Observed Historical Ground Truth',
        shortLabel: 'Observed Traffic (Level 1)',
        badgeClass: 'bg-emerald-100 text-emerald-800 border-emerald-300',
        description: 'Empirical bus travel-time observations from North GT Road pilot corridor.',
      };
    case 'LEVEL_2_HISTORICAL_BASELINE_M0':
      return {
        label: 'Hierarchical Historical Median Baseline (M0)',
        shortLabel: 'Historical Median (Level 2)',
        badgeClass: 'bg-teal-100 text-teal-800 border-teal-300',
        description: 'Observed route/time-of-day median with empirical shrinkage fallback.',
      };
    case 'LEVEL_3_EXPERIMENTAL_RF':
      return {
        label: 'Experimental Machine Learning (Random Forest)',
        shortLabel: 'Experimental ML (Level 3)',
        badgeClass: 'bg-purple-100 text-purple-800 border-purple-300',
        description: 'Candidate ML model evaluated in Milestone 3–4 (gated, experimental only).',
      };
    case 'LEVEL_4_GTFS_SCHEDULED':
      return {
        label: 'GTFS Scheduled Timetable',
        shortLabel: 'Scheduled Timetable (Level 4)',
        badgeClass: 'bg-amber-100 text-amber-800 border-amber-300',
        description: 'Unobserved corridor running time derived from published timetable (not traffic-adjusted).',
      };
    case 'LEVEL_5_STATIC_FALLBACK':
    default:
      return {
        label: 'Static Speed Fallback (15 km/h)',
        shortLabel: 'Static Fallback (Level 5)',
        badgeClass: 'bg-slate-100 text-slate-800 border-slate-300',
        description: 'Default conservative velocity assumption when timetable segments are missing.',
      };
  }
}

