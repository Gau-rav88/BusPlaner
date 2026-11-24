import { describe, it, expect } from 'vitest';
import { apiService, ApiException } from '../services/api';

/**
 * Live Frontend-to-Backend Integration Tests.
 * Executes genuine network HTTP requests against the FastAPI backend
 * running on http://127.0.0.1:8000 (proxied via Vite / direct API base URL).
 * 
 * Verifies live endpoint contracts without mocking fetch.
 */
describe('Live Backend Integration Suite (No Mocks)', () => {
  // Use direct legacy rollback backend URL (Port 8001) or env override
  const BACKEND_URL = process.env.LEGACY_BACKEND_URL || 'http://127.0.0.1:8001/api/v1';

  it('verifies live backend /health status and DEGRADE operational state', async () => {
    const res = await fetch(`${BACKEND_URL}/health`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.application_status).toBe('ok');
    expect(data.overall_operational_status).toBe('DEGRADE');
    expect(data.gtfs_loaded).toBe(true);
  });

  it('verifies live /timetable/status with expired GTFS calendar disclosure', async () => {
    const res = await fetch(`${BACKEND_URL}/timetable/status?service_date=2026-10-01&allow_assumed_recurring=true`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.timetable_status).toBe('ASSUMED_RECURRING');
    expect(data.feed_end_date).toBe('2024-01-01');
    expect(data.actual_operations_verified).toBe(false);
    expect(data.demonstration_mode_available).toBe(true);
  });

  it('verifies strict 400 EXPIRED_TIMETABLE rejection when allow_assumed_recurring=false', async () => {
    const res = await fetch(`${BACKEND_URL}/journeys/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin_stop_id: '239',
        dest_stop_id: '247',
        departure_date: '2026-10-01',
        departure_time: '12:37:40',
        allow_assumed_recurring: false,
      }),
    });
    expect(res.status).toBe(400);
    const err = await res.json();
    expect(err.error).toBe('EXPIRED_TIMETABLE');
    expect(err.feed_end_date).toBe('2024-01-01');
    expect(err.action).toContain('allow_assumed_recurring');
  });

  it('verifies live North GT Road journey planning (Route 1598, Stop 239 -> 247)', async () => {
    const res = await fetch(`${BACKEND_URL}/journeys/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin_stop_id: '239',
        dest_stop_id: '247',
        departure_date: '2026-10-01',
        departure_time: '12:37:40',
        allow_assumed_recurring: true,
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.journeys_count).toBeGreaterThanOrEqual(1);
    
    const journey = data.journeys[0];
    expect(journey.num_transfers).toBe(0);
    expect(journey.actual_operations_verified).toBe(false);
    expect(journey.timetable_status).toBe('ASSUMED_RECURRING');
    expect(journey.confidence_score_type).toBe('HEURISTIC');

    // Transit leg checks
    const transitLeg = journey.legs.find((l: any) => l.leg_type === 'TRANSIT');
    expect(transitLeg).toBeDefined();
    expect(transitLeg.route_id).toBe('1598');
    expect(transitLeg.board_stop_id).toBe('239');
    expect(transitLeg.alight_stop_id).toBe('247');
    expect(transitLeg.prediction_tier).toBe('LEVEL_1_DIRECT_OBSERVED');
    expect(transitLeg.confidence_score_type).toBe('HEURISTIC');

    // Accounting identity validation
    expect(journey.accounting.is_valid_identity).toBe(true);
    expect(Math.abs(journey.accounting.discrepancy_s)).toBeLessThan(1.0);
  });

  it('verifies live /routes/1598 returns all 29 ordered stops for geometry mapping', async () => {
    const res = await fetch(`${BACKEND_URL}/routes/1598`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.route_id).toBe('1598');
    expect(data.ordered_stops.length).toBe(29);
    expect(data.ordered_stops[0].stop_id).toBe('239');
    expect(data.ordered_stops[8].stop_id).toBe('247');
  });

  it('verifies live /stops/search finds stops with coordinates', async () => {
    const res = await fetch(`${BACKEND_URL}/stops/search?query=Azad%20Pur&limit=5`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.total).toBeGreaterThanOrEqual(1);
    expect(data.stops[0].stop_name.toUpperCase()).toContain('AZAD');
  });

  it('verifies live /stops/nearby discovers spatial stops within 800m', async () => {
    const res = await fetch(`${BACKEND_URL}/stops/nearby?lat=28.7075&lon=77.1782&radius_m=800`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.total).toBeGreaterThanOrEqual(1);
    expect(data.stops.some((s: any) => s.stop_id === '239')).toBe(true);
  });

  it('verifies live /live/status reports telemetry with DEGRADE operational status', async () => {
    const res = await fetch(`${BACKEND_URL}/live/status`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(['AUTH_REQUIRED', 'AVAILABLE_VALIDATED']).toContain(data.feed_availability_status);
    expect(data.auth_required).toBe(true);
    expect(data.overall_operational_status).toBe('DEGRADE');
    if (data.feed_availability_status === 'AVAILABLE_VALIDATED') {
      expect(data.feed_enabled).toBe(true);
      expect(data.auth_configured).toBe(true);
      expect(data.active_vehicles_count).toBeGreaterThan(0);
    } else {
      expect(data.feed_enabled).toBe(false);
      expect(data.auth_configured).toBe(false);
      expect(data.warning).toContain('Transport Stack');
    }
  }, 15000);
});
