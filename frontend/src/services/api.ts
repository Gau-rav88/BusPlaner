/**
 * API Service Client for Delhi Bus Transit & Real-Time Traffic Journey Planner.
 * Interacts with FastAPI backend at /api/v1 (or VITE_API_BASE_URL).
 */

import {
  HealthResponse,
  TimetableStatusResponse,
  StopSearchResponse,
  NearbyStopsResponse,
  RouteDetailResponse,
  JourneyPlanRequest,
  JourneyPlanResponse,
  LiveVehiclesResponse,
  LiveBusCandidate,
  SuitableVehiclesResponse,
  ApiError,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export class ApiException extends Error {
  public status: number;
  public errorData: ApiError;

  constructor(status: number, errorData: ApiError) {
    super(errorData.detail || errorData.error || `API request failed with status ${status}`);
    this.name = 'ApiException';
    this.status = status;
    this.errorData = errorData;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errData: ApiError;
    try {
      errData = await res.json();
    } catch {
      errData = {
        error: 'HTTP_ERROR',
        detail: `Server returned error status ${res.status}: ${res.statusText}`,
      };
    }
    throw new ApiException(res.status, errData);
  }
  return res.json() as Promise<T>;
}

export const apiService = {
  /**
   * Health Check
   */
  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE_URL}/health`, {
      headers: { Accept: 'application/json' },
    });
    return handleResponse<HealthResponse>(res);
  },

  /**
   * Live GTFS-RT Feed Status
   */
  async getLiveStatus(probe: boolean = false): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/live/status?probe=${probe}`, {
      headers: { Accept: 'application/json' },
    });
    return handleResponse<any>(res);
  },

  /**
   * Live Bus Positions with optional Route, Proximity, and Viewport Bounding Box Filters
   * Defaults to limit=5000 to retrieve the complete active fleet across Delhi.
   */
  async getLiveVehicles(
    routeId?: string,
    limit?: number,
    lat?: number,
    lon?: number,
    radiusM?: number,
    includeStale: boolean = true,
    includeOutOfArea: boolean = true,
    signal?: AbortSignal,
    minLat?: number,
    maxLat?: number,
    minLon?: number,
    maxLon?: number
  ): Promise<LiveVehiclesResponse> {
    const params = new URLSearchParams();
    if (routeId) params.append('route_id', routeId);
    if (limit !== undefined) params.append('limit', String(limit));
    if (includeStale !== undefined) params.append('include_stale', String(includeStale));
    if (includeOutOfArea !== undefined) params.append('include_out_of_area', String(includeOutOfArea));
    if (lat !== undefined && lon !== undefined) {
      params.append('lat', String(lat));
      params.append('lon', String(lon));
      if (radiusM !== undefined) params.append('radius_m', String(radiusM));
    }
    if (minLat !== undefined && maxLat !== undefined && minLon !== undefined && maxLon !== undefined) {
      params.append('min_lat', String(minLat));
      params.append('max_lat', String(maxLat));
      params.append('min_lon', String(minLon));
      params.append('max_lon', String(maxLon));
    }
    const res = await fetch(`${API_BASE_URL}/live/vehicles?${params.toString()}`, {
      headers: { Accept: 'application/json' },
      signal,
    });
    return handleResponse<LiveVehiclesResponse>(res);
  },

  /**
   * Verified Suitable Vehicles for a specific journey transit leg
   * Filters strictly to buses moving towards the alighting stop that have not passed boarding.
   */
  async getSuitableVehicles(
    routeId: string,
    boardStopId: string,
    alightStopId: string,
    signal?: AbortSignal
  ): Promise<SuitableVehiclesResponse> {
    const params = new URLSearchParams({
      route_id: routeId,
      board_stop_id: boardStopId,
      alight_stop_id: alightStopId,
    });
    const res = await fetch(`${API_BASE_URL}/live/suitable-vehicles?${params.toString()}`, {
      headers: { Accept: 'application/json' },
      signal,
    });
    return handleResponse<SuitableVehiclesResponse>(res);
  },

  /**
   * Timetable Status
   */
  async getTimetableStatus(
    serviceDate: string = '2026-10-01',
    allowAssumedRecurring: boolean = false
  ): Promise<TimetableStatusResponse> {
    const params = new URLSearchParams({
      service_date: serviceDate,
      allow_assumed_recurring: String(allowAssumedRecurring),
    });
    const res = await fetch(`${API_BASE_URL}/timetable/status?${params.toString()}`, {
      headers: { Accept: 'application/json' },
    });
    return handleResponse<TimetableStatusResponse>(res);
  },

  /**
   * Stop Search by Name
   */
  async searchStops(query: string, limit: number = 10): Promise<StopSearchResponse> {
    if (!query.trim()) {
      return { query, total: 0, stops: [] };
    }
    const params = new URLSearchParams({
      query: query.trim(),
      limit: String(limit),
    });
    const res = await fetch(`${API_BASE_URL}/stops/search?${params.toString()}`, {
      headers: { Accept: 'application/json' },
    });
    return handleResponse<StopSearchResponse>(res);
  },

  /**
   * Nearby Stops Spatial Query
   */
  async getNearbyStops(
    lat: number,
    lon: number,
    radiusM: number = 800,
    limit: number = 10
  ): Promise<NearbyStopsResponse> {
    const params = new URLSearchParams({
      lat: String(lat),
      lon: String(lon),
      radius_m: String(radiusM),
      limit: String(limit),
    });
    const res = await fetch(`${API_BASE_URL}/stops/nearby?${params.toString()}`, {
      headers: { Accept: 'application/json' },
    });
    return handleResponse<NearbyStopsResponse>(res);
  },

  /**
   * Route Details and Stops
   */
  async getRouteDetail(routeId: string): Promise<RouteDetailResponse> {
    const res = await fetch(`${API_BASE_URL}/routes/${encodeURIComponent(routeId)}`, {
      headers: { Accept: 'application/json' },
    });
    return handleResponse<RouteDetailResponse>(res);
  },

  /**
   * Plan Multi-Criteria Transit Journey
   */
  async planJourney(req: JourneyPlanRequest): Promise<JourneyPlanResponse> {
    const res = await fetch(`${API_BASE_URL}/journeys/plan`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(req),
    });
    return handleResponse<JourneyPlanResponse>(res);
  },

  /**
   * Cross-reference live GTFS-RT vehicles against static GTFS to identify candidate bus to board.
   */
  async matchLiveBus(
    routeId: string,
    boardStopId: string,
    alightStopId: string,
    schedDepartureS?: number
  ): Promise<LiveBusCandidate> {
    const params = new URLSearchParams({
      route_id: routeId,
      board_stop_id: boardStopId,
      alight_stop_id: alightStopId,
    });
    if (schedDepartureS !== undefined) {
      params.append('sched_departure_s', schedDepartureS.toString());
    }
    const res = await fetch(`${API_BASE_URL}/live/match-bus?${params.toString()}`, {
      headers: { Accept: 'application/json' },
    });
    return handleResponse<LiveBusCandidate>(res);
  },
};

