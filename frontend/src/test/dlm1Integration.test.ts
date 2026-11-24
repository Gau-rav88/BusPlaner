import { describe, it, expect } from 'vitest';

/**
 * DLM1-specific Frontend-to-Backend Live Integration Suite.
 * Executes genuine network HTTP requests against the separate DLM1 backend
 * running on http://127.0.0.1:8001/api/v1.
 * 
 * Verifies that the DLM1 database correctly powers:
 * - Health check & DEGRADE operational status
 * - CURRENT_VERIFIED timetable status (2025-2040)
 * - DLM1 stop search with official DLM1 stop IDs
 * - Route 1598 road geometry shape points (416 coordinates)
 * - Direct journey planning on DLM1 corridor
 * - Multi-leg transfer journey on DLM1
 * - Real-time vehicle positions from Delhi Transport Stack
 */
describe('DLM1 Backend Live Integration Suite (Port 8001)', () => {
  // Use primary cutover DLM1 backend URL (Port 8000) or env override
  const DLM1_BACKEND_URL = process.env.DLM1_BACKEND_URL || 'http://127.0.0.1:8000/api/v1';

  it('verifies DLM1 backend /health status and DEGRADE operational state', async () => {
    const res = await fetch(`${DLM1_BACKEND_URL}/health`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.application_status).toBe('ok');
    expect(data.overall_operational_status).toBe('DEGRADE');
    expect(data.database_available).toBe(true);
    expect(data.gtfs_loaded).toBe(true);
  });

  it('verifies DLM1 /timetable/status returns CURRENT_VERIFIED with 2025-2040 calendar', async () => {
    const res = await fetch(`${DLM1_BACKEND_URL}/timetable/status?service_date=2026-10-01`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.timetable_status).toBe('CURRENT_VERIFIED');
    expect(data.feed_start_date).toBe('2025-01-01');
    expect(data.feed_end_date).toBe('2040-01-01');
    expect(data.is_date_within_feed_validity).toBe(true);
  });

  it('verifies DLM1 /stops/search returns official DLM1 stop IDs', async () => {
    const res = await fetch(`${DLM1_BACKEND_URL}/stops/search?query=kashmere&limit=6`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.total).toBeGreaterThan(0);
    const stopIds = data.stops.map((s: { stop_id: string }) => s.stop_id);
    // DLM1 stops for Kashmere Gate
    expect(stopIds.some((id: string) => ['1025', '1046', '7571', '271', '267', '4822', '4232'].includes(id))).toBe(true);
  });

  it('verifies DLM1 /routes/1598 returns 59 stops and 416 road geometry coordinates', async () => {
    const res = await fetch(`${DLM1_BACKEND_URL}/routes/1598`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.route_id).toBe('1598');
    expect(data.route_short_name).toBe('144UP');
    expect(data.ordered_stops.length).toBe(59);
    expect(data.has_shape_geometry).toBe(true);
    expect(Array.isArray(data.shape_coordinates)).toBe(true);
    expect(data.shape_coordinates.length).toBe(416);
  });

  it('verifies direct journey planning on DLM1 corridor (Stop 284 -> 5146)', async () => {
    const res = await fetch(`${DLM1_BACKEND_URL}/journeys/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin_stop_id: '284',
        dest_stop_id: '5146',
        departure_date: '2026-10-01',
        departure_time: '08:00:00',
        max_transfers: 0,
        allow_assumed_recurring: true,
      }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.journeys_count).toBeGreaterThanOrEqual(1);
    expect(data.journeys[0].num_transfers).toBe(0);
    expect(data.journeys[0].legs[0].leg_type).toBe('TRANSIT');
    expect(data.journeys[0].legs[0].board_stop_id).toBe('284');
    expect(data.journeys[0].legs[0].alight_stop_id).toBe('5146');
  });

  it('verifies transfer journey planning on DLM1 network (Stop 2280 -> 5321)', async () => {
    const res = await fetch(`${DLM1_BACKEND_URL}/journeys/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin_stop_id: '2280',
        dest_stop_id: '5321',
        departure_date: '2026-10-01',
        departure_time: '08:00:00',
        max_transfers: 2,
        allow_assumed_recurring: true,
      }),
    });
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.journeys_count).toBeGreaterThanOrEqual(1);
    expect(data.journeys[0].num_transfers).toBeGreaterThanOrEqual(1);
  });

  it('verifies DLM1 /live/vehicles returns real active telemetry matching DLM1 routes', async () => {
    const res = await fetch(`${DLM1_BACKEND_URL}/live/vehicles`);
    expect(res.ok).toBe(true);
    const data = await res.json();
    expect(data.feed_availability_status).toBe('AVAILABLE_VALIDATED');
    expect(Array.isArray(data.vehicles)).toBe(true);
    expect(data.vehicles.length).toBeGreaterThan(0);
    const v0 = data.vehicles[0];
    expect(v0.vehicle_id).toBeDefined();
    expect(v0.latitude).toBeGreaterThan(28.0);
    expect(v0.longitude).toBeGreaterThan(76.0);
  }, 15000);
});

