import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { DelhiMap } from '../map/DelhiMap';
import { apiService } from '../services/api';
import { LiveVehicleItem, LiveVehiclesResponse } from '../types/api';

// Mock Leaflet and React-Leaflet
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: any) => <div data-testid="map-container">{children}</div>,
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: ({ children, position, icon }: any) => (
    <div data-testid="map-marker" data-lat={position[0]} data-lon={position[1]}>
      {children}
    </div>
  ),
  Popup: ({ children }: any) => <div data-testid="marker-popup">{children}</div>,
  Tooltip: ({ children }: any) => <div data-testid="marker-tooltip">{children}</div>,
  Polyline: () => <div data-testid="map-polyline" />,
  CircleMarker: () => <div data-testid="map-circle-marker" />,
  Circle: ({ children, center, radius }: any) => (
    <div data-testid="map-circle" data-radius={radius} data-lat={center[0]} data-lon={center[1]}>
      {children}
    </div>
  ),
  useMap: () => ({ fitBounds: vi.fn(), invalidateSize: vi.fn(), getCenter: () => ({ lat: 28.6139, lng: 77.209 }) }),
  useMapEvents: () => null,
}));

describe('DelhiMap Full Fleet Live Display', () => {
  it('renders all vehicles returned by the backend without restricting to journey route', async () => {
    const mockVehicles: LiveVehicleItem[] = [
      {
        vehicle_id: 'BUS_CORE_1',
        route_id: '1598',
        trip_id: 'T1',
        latitude: 28.7075,
        longitude: 77.1782,
        bearing: 90.0,
        speed_kmh: 40.0,
        timestamp_utc: 1795510000,
        age_seconds: 30,
        is_fresh: true,
        is_current: true,
        is_matched_to_gtfs: true,
        agency: 'UNKNOWN_MIXED',
      },
      {
        vehicle_id: 'BUS_UNMATCHED_ROUTE',
        route_id: null, // Unknown route
        trip_id: null, // No trip ID
        latitude: 28.6500,
        longitude: 77.2000,
        bearing: null, // Unknown direction
        speed_kmh: 0.0,
        timestamp_utc: 1795510010,
        age_seconds: 20,
        is_fresh: true,
        is_current: true,
        is_matched_to_gtfs: false,
        agency: 'UNKNOWN_MIXED',
      },
      {
        vehicle_id: 'BUS_STALE_LAST_KNOWN',
        route_id: '925',
        trip_id: 'T925',
        latitude: 28.6000,
        longitude: 77.1000,
        bearing: 180.0,
        speed_kmh: 25.0,
        timestamp_utc: 1795509500,
        age_seconds: 530,
        is_fresh: false,
        is_current: false, // Stale / retained
        is_matched_to_gtfs: true,
        agency: 'UNKNOWN_MIXED',
      },
      {
        vehicle_id: 'BUS_NCR_INTERSTATE',
        route_id: '2543',
        trip_id: 'T2543',
        latitude: 28.9624, // Outside Delhi Core, in Sonipat NCR
        longitude: 77.0919,
        bearing: null,
        speed_kmh: 55.0,
        timestamp_utc: 1795510020,
        age_seconds: 10,
        is_fresh: true,
        is_current: true,
        is_out_of_area: true,
        area_classification: 'NCR_OUT_OF_BOUNDS',
        is_matched_to_gtfs: false,
        agency: 'UNKNOWN_MIXED',
      },
    ];

    const mockResponse: LiveVehiclesResponse = {
      total_active_vehicles: 4,
      returned_vehicles_count: 4,
      current_vehicles_count: 3,
      last_known_vehicles_count: 1,
      out_of_area_count: 1,
      route_filter: null,
      vehicles: mockVehicles,
      latest_timestamp_utc: '2026-11-24T09:00:00Z',
      feed_availability_status: 'AVAILABLE_VALIDATED',
      disclaimer: 'Test disclaimer',
    };

    vi.spyOn(apiService, 'getLiveVehicles').mockResolvedValue(mockResponse);

    render(
      <DelhiMap
        originStop={null}
        destStop={null}
        originCoord={null}
        destCoord={null}
        selectedJourney={null}
        nearbyStops={[]}
        onMapClick={vi.fn()}
        onSelectStopAsOrigin={vi.fn()}
        onSelectStopAsDest={vi.fn()}
      />
    );

    // Wait for markers to render
    await waitFor(() => {
      const markers = screen.getAllByTestId('map-marker');
      expect(markers.length).toBe(4);
    });

    // Verify all vehicle IDs are present in the DOM
    expect(screen.getByText('BUS_CORE_1')).toBeInTheDocument();
    expect(screen.getByText('BUS_UNMATCHED_ROUTE')).toBeInTheDocument();
    expect(screen.getByText('BUS_STALE_LAST_KNOWN')).toBeInTheDocument();
    expect(screen.getByText('BUS_NCR_INTERSTATE')).toBeInTheDocument();

    // Verify unknown route label
    expect(screen.getByText('Route Unknown route')).toBeInTheDocument();

    // Verify unknown direction label
    expect(screen.getAllByText(/Direction unverified/i).length).toBeGreaterThanOrEqual(1);

    // Verify current vs stale telemetry labels
    expect(screen.getAllByText('Current Snapshot').length).toBe(3);
    expect(screen.getByText('Last Known / Stale Position')).toBeInTheDocument();

    // Verify NCR interstate corridor label
    expect(screen.getByText(/NCR Interstate Corridor/i)).toBeInTheDocument();

    // Verify button counter displays all 4 buses
    expect(screen.getByText('🚌 Buses (4)')).toBeInTheDocument();

    // Verify radius discovery visual circle is completely removed (clean map)
    expect(screen.queryByTestId('map-circle')).not.toBeInTheDocument();
    expect(screen.getByText('Radius:')).toBeInTheDocument();
    expect(screen.getByText('2km')).toBeInTheDocument();
    expect(screen.getByText(/3 Live/i)).toBeInTheDocument();
    expect(screen.getByText(/1 Stale/i)).toBeInTheDocument();
  });

  it('excludes vehicles whose distance_m exceeds the active radius', async () => {
    const mockVehiclesWithDist: LiveVehicleItem[] = [
      {
        vehicle_id: 'BUS_NEAR_500M',
        route_id: '1598',
        trip_id: 'T1',
        latitude: 28.6140,
        longitude: 77.2091,
        bearing: 90.0,
        speed_kmh: 30.0,
        timestamp_utc: 1795510000,
        age_seconds: 15,
        is_fresh: true,
        is_current: true,
        is_matched_to_gtfs: true,
        agency: 'UNKNOWN_MIXED',
        distance_m: 450.0, // Inside 2000m
      },
      {
        vehicle_id: 'BUS_FAR_3500M',
        route_id: '1598',
        trip_id: 'T2',
        latitude: 28.6500,
        longitude: 77.2500,
        bearing: 45.0,
        speed_kmh: 20.0,
        timestamp_utc: 1795510000,
        age_seconds: 20,
        is_fresh: true,
        is_current: true,
        is_matched_to_gtfs: true,
        agency: 'UNKNOWN_MIXED',
        distance_m: 3500.0, // Outside 2000m
      },
    ];

    const mockResponse: LiveVehiclesResponse = {
      total_active_vehicles: 2,
      returned_vehicles_count: 1,
      current_vehicles_count: 1,
      last_known_vehicles_count: 0,
      out_of_area_count: 0,
      route_filter: null,
      vehicles: mockVehiclesWithDist,
      latest_timestamp_utc: '2026-11-24T09:00:00Z',
      feed_availability_status: 'AVAILABLE_VALIDATED',
      disclaimer: 'Test disclaimer',
      search_radius_m: 2000,
      current_matching_count: 1,
      stale_matching_count: 0,
    };

    vi.spyOn(apiService, 'getLiveVehicles').mockResolvedValue(mockResponse);

    render(
      <DelhiMap
        originStop={null}
        destStop={null}
        originCoord={null}
        destCoord={null}
        selectedJourney={null}
        nearbyStops={[]}
        onMapClick={vi.fn()}
        onSelectStopAsOrigin={vi.fn()}
        onSelectStopAsDest={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('BUS_NEAR_500M')).toBeInTheDocument();
    });

    // BUS_FAR_3500M should be filtered out by radius
    expect(screen.queryByText('BUS_FAR_3500M')).not.toBeInTheDocument();
  });

  it('in journey mode, displays verified suitable buses with ⭐ and other nearby buses with unverified label', async () => {
    const mockJourney: any = {
      journey_id: 'J1',
      legs: [
        {
          leg_type: 'TRANSIT',
          route_id: '1598',
          board_stop_id: '284',
          board_stop_name: 'Azadpur Terminal',
          alight_stop_id: '5146',
          alight_stop_name: 'Mori Gate Terminal',
          board_time_s: 36000,
          alight_time_s: 37200,
        },
      ],
    };

    // Unrelated fleet buses
    vi.spyOn(apiService, 'getLiveVehicles').mockResolvedValue({
      total_active_vehicles: 2,
      returned_vehicles_count: 2,
      route_filter: null,
      latest_timestamp_utc: null,
      vehicles: [
        {
          vehicle_id: 'UNRELATED_BUS_999',
          route_id: '999',
          trip_id: 'T999',
          latitude: 28.71,
          longitude: 77.18,
          bearing: 90,
          speed_kmh: 30,
          timestamp_utc: 1795510000,
          age_seconds: 20,
          is_fresh: true,
          is_current: true,
          is_matched_to_gtfs: true,
          agency: 'UNKNOWN_MIXED',
        },
      ],
      feed_availability_status: 'AVAILABLE_VALIDATED',
      disclaimer: 'test',
    });

    // Verified suitable bus response
    vi.spyOn(apiService, 'getSuitableVehicles').mockResolvedValue({
      route_id: '1598',
      board_stop_id: '284',
      alight_stop_id: '5146',
      suitable_count: 1,
      vehicles: [
        {
          vehicle_id: 'SUITABLE_BUS_1598',
          route_id: '1598',
          trip_id: 'TRIP_1598_FWD',
          trip_headsign: 'Mori Gate Terminal',
          destination_stop_name: 'Mori Gate Terminal',
          progress_status: 'APPROACHING',
          distance_to_board_m: 650.0,
          stops_away: 2,
          speed_kmh: 28.5,
          latitude: 28.712,
          longitude: 77.175,
          bearing: 140,
          timestamp_utc: 1795510000,
          age_seconds: 18,
          is_fresh: true,
          is_current: true,
          is_verified_suitable: true,
          is_verified_destination: true,
          guidance_message: 'Verified candidate bus approaching Azadpur Terminal. Board when vehicle arrives.',
        },
      ],
      disclaimer: 'Candidate bus based on real-time GTFS-RT feed.',
    });

    render(
      <DelhiMap
        originStop={null}
        destStop={null}
        originCoord={null}
        destCoord={null}
        selectedJourney={mockJourney}
        nearbyStops={[]}
        onMapClick={vi.fn()}
        onSelectStopAsOrigin={vi.fn()}
        onSelectStopAsDest={vi.fn()}
      />
    );

    // Verify suitable bus renders
    await waitFor(() => {
      expect(screen.getByText('SUITABLE_BUS_1598')).toBeInTheDocument();
    });

    // Verify destination reach verification badge
    expect(screen.getByText(/✓ Verified to reach Mori Gate Terminal/i)).toBeInTheDocument();

    // Verify distance to boarding stop
    expect(screen.getByText(/650m to boarding stop/i)).toBeInTheDocument();

    // In Mode B, strictly hides unrelated buses (no cluttering of journey map)
    expect(screen.queryByText('UNRELATED_BUS_999')).not.toBeInTheDocument();

    // Verify banner explains verified buses for the active route
    expect(screen.getByText(/Showing 1 verified live bus/i)).toBeInTheDocument();
  });

  it('in journey mode (Mode B) with 0 suitable buses, displays exact fallback banner and leaves map clean without unrelated buses', async () => {
    const mockJourney: any = {
      journey_id: 'J2',
      legs: [
        {
          leg_type: 'TRANSIT',
          route_id: '1598',
          board_stop_id: '284',
          board_stop_name: 'Azadpur Terminal',
          alight_stop_id: '5146',
          alight_stop_name: 'Mori Gate Terminal',
          board_time_s: 36000,
          alight_time_s: 37200,
        },
      ],
    };

    // Unrelated fleet buses available
    vi.spyOn(apiService, 'getLiveVehicles').mockResolvedValue({
      total_active_vehicles: 1,
      returned_vehicles_count: 1,
      route_filter: null,
      latest_timestamp_utc: null,
      vehicles: [
        {
          vehicle_id: 'NEARBY_BUS_UNVERIFIED_100',
          route_id: '888',
          trip_id: 'T888',
          latitude: 28.71,
          longitude: 77.18,
          bearing: 90,
          speed_kmh: 22,
          timestamp_utc: 1795510000,
          age_seconds: 15,
          is_fresh: true,
          is_current: true,
          is_matched_to_gtfs: true,
          agency: 'UNKNOWN_MIXED',
        },
      ],
      feed_availability_status: 'AVAILABLE_VALIDATED',
      disclaimer: 'test',
    });

    vi.spyOn(apiService, 'getSuitableVehicles').mockResolvedValue({
      route_id: '1598',
      board_stop_id: '284',
      alight_stop_id: '5146',
      suitable_count: 0,
      vehicles: [],
      fallback_message: 'No verified live bus is currently available for this journey.',
      disclaimer: 'test',
    });

    render(
      <DelhiMap
        originStop={null}
        destStop={null}
        originCoord={null}
        destCoord={null}
        selectedJourney={mockJourney}
        nearbyStops={[]}
        onMapClick={vi.fn()}
        onSelectStopAsOrigin={vi.fn()}
        onSelectStopAsDest={vi.fn()}
      />
    );

    // Verify exact fallback guidance banner
    await waitFor(() => {
      expect(
        screen.getByText(/No verified live bus is currently available for this journey\./i)
      ).toBeInTheDocument();
    });

    // Verify unrelated buses are NOT displayed as fallback in Mode B (clean map)
    expect(screen.queryByText('NEARBY_BUS_UNVERIFIED_100')).not.toBeInTheDocument();
  });

  it('stabilizes bounds fitting so repeated state changes and re-renders do not repeatedly lock or fit bounds', async () => {
    const mockFitBounds = vi.fn();
    // Override useMap mock to track fitBounds calls
    const reactLeaflet = await import('react-leaflet');
    vi.spyOn(reactLeaflet, 'useMap').mockReturnValue({
      fitBounds: mockFitBounds,
      invalidateSize: vi.fn(),
      getCenter: () => ({ lat: 28.6139, lng: 77.209 }),
    } as any);

    const originStop: any = { stop_id: 'S1', stop_name: 'Origin Stop', lat: 28.7, lon: 77.1 };
    const destStop: any = { stop_id: 'S2', stop_name: 'Dest Stop', lat: 28.6, lon: 77.2 };

    const { rerender } = render(
      <DelhiMap
        originStop={originStop}
        destStop={destStop}
        originCoord={[28.7, 77.1]}
        destCoord={[28.6, 77.2]}
        selectedJourney={null}
        nearbyStops={[]}
        onMapClick={vi.fn()}
        onSelectStopAsOrigin={vi.fn()}
        onSelectStopAsDest={vi.fn()}
      />
    );

    // Initial fitBounds called once for origin/dest selection
    expect(mockFitBounds).toHaveBeenCalledTimes(1);

    // Re-rendering with identical selection (e.g. vehicle polling or map panning state change) does NOT call fitBounds again
    rerender(
      <DelhiMap
        originStop={originStop}
        destStop={destStop}
        originCoord={[28.7, 77.1]}
        destCoord={[28.6, 77.2]}
        selectedJourney={null}
        nearbyStops={[]}
        onMapClick={vi.fn()}
        onSelectStopAsOrigin={vi.fn()}
        onSelectStopAsDest={vi.fn()}
      />
    );

    expect(mockFitBounds).toHaveBeenCalledTimes(1);
  });
});

