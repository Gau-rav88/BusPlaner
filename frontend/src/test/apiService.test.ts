import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiService, ApiException } from '../services/api';

describe('apiService client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches health status successfully', async () => {
    const mockHealth = {
      application_status: 'ok',
      backend_version: '1.0.0',
      database_available: true,
      gtfs_loaded: true,
      overall_operational_status: 'DEGRADE',
      timestamp_utc: '2026-11-21T10:00:00Z',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHealth,
    } as any);

    const res = await apiService.getHealth();
    expect(res.application_status).toBe('ok');
    expect(res.overall_operational_status).toBe('DEGRADE');
  });

  it('searches stops by query string', async () => {
    const mockStops = {
      query: 'kashmere',
      total: 1,
      stops: [{ stop_id: '239', stop_name: 'ISBT Kashmere Gate', lat: 28.6675, lon: 77.2283 }],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockStops,
    } as any);

    const res = await apiService.searchStops('kashmere');
    expect(res.total).toBe(1);
    expect(res.stops[0].stop_name).toContain('Kashmere Gate');
  });

  it('throws ApiException with error envelope on 400 Expired Timetable', async () => {
    const mockError = {
      error: 'EXPIRED_TIMETABLE',
      detail: 'Requested service date 2026-10-01 is past feed validity.',
      action: 'Set allow_assumed_recurring: true in request body.',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => mockError,
    } as any);

    await expect(
      apiService.planJourney({
        origin_stop_id: '239',
        dest_stop_id: '2024',
        departure_date: '2026-10-01',
        departure_time: '12:37:40',
        max_walking_distance_m: 800,
        max_transfers: 3,
        num_alternatives: 3,
        ranking_strategy: 'earliest_arrival',
        use_experimental_ml: false,
        allow_assumed_recurring: false,
      })
    ).rejects.toThrow(ApiException);
  });
});

