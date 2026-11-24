import { describe, it, expect } from 'vitest';
import {
  formatSecondsToTime,
  formatDuration,
  formatDistance,
  formatPredictionTier,
} from '../utils/formatters';

describe('formatters utility', () => {
  it('formats seconds since midnight correctly', () => {
    // 08:00:00 -> 28800s
    expect(formatSecondsToTime(28800)).toBe('8:00 AM');
    // 12:37:40 -> 45460s
    expect(formatSecondsToTime(45460)).toBe('12:37 PM');
    // 13:00:00 -> 46800s
    expect(formatSecondsToTime(46800)).toBe('1:00 PM');
    // 00:00:00 -> 0s
    expect(formatSecondsToTime(0)).toBe('12:00 AM');
    // Post-midnight (next day): 25:10:00 -> 90600s
    expect(formatSecondsToTime(90600)).toBe('1:10 AM (+1d)');
  });

  it('formats duration in seconds into human-readable minutes and hours', () => {
    expect(formatDuration(0)).toBe('0 min');
    expect(formatDuration(300)).toBe('5 min');
    expect(formatDuration(1700)).toBe('28 min');
    expect(formatDuration(3600)).toBe('1h');
    expect(formatDuration(4500)).toBe('1h 15m');
  });

  it('formats distance in meters into m or km', () => {
    expect(formatDistance(0)).toBe('0 m');
    expect(formatDistance(450)).toBe('450 m');
    expect(formatDistance(1200)).toBe('1.2 km');
    expect(formatDistance(8200)).toBe('8.2 km');
  });

  it('formats prediction tiers with accurate truthfulness badges and descriptions', () => {
    const l1 = formatPredictionTier('LEVEL_1_DIRECT_OBSERVED');
    expect(l1.shortLabel).toContain('Level 1');
    expect(l1.description).toContain('North GT Road');

    const l2 = formatPredictionTier('LEVEL_2_HISTORICAL_BASELINE_M0');
    expect(l2.shortLabel).toContain('Level 2');

    const l3 = formatPredictionTier('LEVEL_3_EXPERIMENTAL_RF');
    expect(l3.shortLabel).toContain('Experimental ML');

    const l4 = formatPredictionTier('LEVEL_4_GTFS_SCHEDULED');
    expect(l4.shortLabel).toContain('Scheduled');
    expect(l4.description).toContain('not traffic-adjusted');

    const l5 = formatPredictionTier('LEVEL_5_STATIC_FALLBACK');
    expect(l5.shortLabel).toContain('Static');
  });
});

