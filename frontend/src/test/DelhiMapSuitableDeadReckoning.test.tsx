import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { DelhiMap } from '../map/DelhiMap';
import { apiService } from '../services/api';

vi.mock('react-leaflet', async () => {
  const actual = await vi.importActual<any>('react-leaflet');
  return {
    ...actual,
    MapContainer: ({ children }: any) => <div data-testid="map-container">{children}</div>,
    TileLayer: () => <div data-testid="tile-layer" />,
    Marker: ({ children, position, icon }: any) => (
      <div data-testid="map-marker" data-lat={position[0]} data-lon={position[1]} data-icon-html={icon?.options?.html || ''}>
        {children}
      </div>
    ),
    Popup: ({ children }: any) => <div data-testid="map-popup">{children}</div>,
    Tooltip: ({ children }: any) => <div data-testid="marker-tooltip">{children}</div>,
    Polyline: () => <div data-testid="map-polyline" />,
    CircleMarker: () => <div data-testid="map-circle-marker" />,
    useMap: () => ({
      fitBounds: vi.fn(),
      setView: vi.fn(),
      getCenter: () => ({ lat: 28.7167, lng: 77.17 }),
      getZoom: () => 13,
      getBounds: () => ({
        getSouth: () => 28.65,
        getNorth: () => 28.75,
        getWest: () => 77.10,
        getEast: () => 77.25,
      }),
      invalidateSize: vi.fn(),
    }),
    useMapEvents: () => null,
  };
});

describe('DelhiMap Mode B and Dead Reckoning Tracking', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockJourney: any = {
    journey_id: 'J_MODE_B',
    total_travel_time_s: 1800,
    total_walking_time_s: 300,
    total_walking_distance_m: 250,
    transfers_count: 0,
    fare_rs: 15,
    departure_time_s: 36000,
    arrival_time_s: 37800,
    legs: [
      {
        leg_type: 'TRANSIT',
        route_id: '1598',
        board_stop_id: '284',
        board_stop_name: 'Adarsh Nagar / Bharola Village',
        alight_stop_id: '5146',
        alight_stop_name: 'GTK ByPass / Mukarba chowk',
        board_time_s: 36300,
        alight_time_s: 37500,
        num_stops: 5,
      },
    ],
    confidence_score_type: 'HIGH',
    timetable_status: 'CURRENT_VERIFIED',
    is_verified_current_service: true,
    actual_operations_verified: false,
    warnings: [],
  };

  it('renders verified suitable bus with live GPS gold star and GPS metadata in Mode B', async () => {
    vi.spyOn(apiService, 'getRouteDetail').mockResolvedValue({
      route_id: '1598',
      agency_id: 'DIMTS',
      route_short_name: '1598',
      route_long_name: 'Adarsh Nagar to Mukarba Chowk',
      trips_count: 5,
      patterns_count: 1,
      ordered_stops: [
        { stop_id: '284', stop_name: 'Adarsh Nagar', lat: 28.71598, lon: 77.1708, sequence: 34 },
        { stop_id: '5146', stop_name: 'Mukarba Chowk', lat: 28.7351, lon: 77.1556, sequence: 39 },
      ],
      has_shape_geometry: true,
      shape_coordinates: [[28.71598, 77.1708], [28.7351, 77.1556]],
    });

    vi.spyOn(apiService, 'getSuitableVehicles').mockResolvedValue({
      route_id: '1598',
      board_stop_id: '284',
      alight_stop_id: '5146',
      suitable_count: 1,
      vehicles: [
        {
          vehicle_id: 'DL1PC_GPS_01',
          route_id: '1598',
          trip_id: '1598_FULL_05_50',
          trip_headsign: 'Singhu Border GT Road',
          destination_stop_name: 'GTK ByPass / Mukarba chowk',
          progress_status: 'APPROACHING',
          distance_to_board_m: 520.0,
          stops_away: 1,
          speed_kmh: 32.0,
          latitude: 28.7120,
          longitude: 77.1750,
          bearing: 325,
          timestamp_utc: 1795510000,
          age_seconds: 6,
          is_fresh: true,
          is_current: true,
          is_verified_suitable: true,
          is_verified_destination: true,
          guidance_message: 'Verified candidate bus approaching Adarsh Nagar. Board when vehicle arrives.',
          position_source: 'GPS',
          is_dead_reckoned: false,
          uncertainty_meters: 15.0,
        },
      ],
      disclaimer: 'Candidate bus based on real-time GTFS-RT feed.',
      poll_interval_seconds: 15,
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

    await waitFor(() => {
      expect(screen.getByText('DL1PC_GPS_01')).toBeInTheDocument();
    });

    // Check Live GPS status badge
    expect(screen.getByText('Live GPS')).toBeInTheDocument();
    expect(screen.getByText(/Direct GPS fix \(uncertainty ±15m\)/i)).toBeInTheDocument();
    expect(screen.getByText(/✓ Verified to reach GTK ByPass \/ Mukarba chowk/i)).toBeInTheDocument();
  });

  it('renders dead-reckoned estimated bus with lightning icon and extrapolated corridor metadata in Mode B', async () => {
    vi.spyOn(apiService, 'getRouteDetail').mockResolvedValue({
      route_id: '1598',
      agency_id: 'DIMTS',
      route_short_name: '1598',
      route_long_name: 'Adarsh Nagar to Mukarba Chowk',
      trips_count: 5,
      patterns_count: 1,
      ordered_stops: [
        { stop_id: '284', stop_name: 'Adarsh Nagar', lat: 28.71598, lon: 77.1708, sequence: 34 },
        { stop_id: '5146', stop_name: 'Mukarba Chowk', lat: 28.7351, lon: 77.1556, sequence: 39 },
      ],
      has_shape_geometry: true,
      shape_coordinates: [[28.71598, 77.1708], [28.7351, 77.1556]],
    });

    vi.spyOn(apiService, 'getSuitableVehicles').mockResolvedValue({
      route_id: '1598',
      board_stop_id: '284',
      alight_stop_id: '5146',
      suitable_count: 1,
      vehicles: [
        {
          vehicle_id: 'DL1PC_DR_02',
          route_id: '1598',
          trip_id: '1598_FULL_05_50',
          trip_headsign: 'Singhu Border GT Road',
          destination_stop_name: 'GTK ByPass / Mukarba chowk',
          progress_status: 'APPROACHING',
          distance_to_board_m: 380.0,
          stops_away: 1,
          speed_kmh: 36.0,
          latitude: 28.7135,
          longitude: 77.1732,
          bearing: 325,
          timestamp_utc: 1795509960,
          age_seconds: 40,
          is_fresh: true,
          is_current: true,
          is_verified_suitable: true,
          is_verified_destination: true,
          guidance_message: 'Verified candidate bus approaching Adarsh Nagar (Dead Reckoned).',
          position_source: 'DEAD_RECKONED',
          is_dead_reckoned: true,
          last_gps_latitude: 28.7110,
          last_gps_longitude: 77.1760,
          last_gps_timestamp: 1795509960,
          prediction_age_seconds: 40,
          uncertainty_meters: 63.0,
        },
      ],
      disclaimer: 'Candidate bus based on real-time GTFS-RT feed.',
      poll_interval_seconds: 15,
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

    await waitFor(() => {
      expect(screen.getByText('DL1PC_DR_02')).toBeInTheDocument();
    });

    // Check Dead Reckoned status badge
    expect(screen.getByText('Estimated position (Dead Reckoned)')).toBeInTheDocument();
    expect(screen.getByText(/Extrapolated along corridor \(uncertainty ±63m\)/i)).toBeInTheDocument();
  });

  it('renders exact fallback banner and zero bus markers when no suitable buses are available in Mode B', async () => {
    vi.spyOn(apiService, 'getRouteDetail').mockResolvedValue({
      route_id: '1598',
      agency_id: 'DIMTS',
      route_short_name: '1598',
      route_long_name: 'Adarsh Nagar to Mukarba Chowk',
      trips_count: 5,
      patterns_count: 1,
      ordered_stops: [
        { stop_id: '284', stop_name: 'Adarsh Nagar', lat: 28.71598, lon: 77.1708, sequence: 34 },
        { stop_id: '5146', stop_name: 'Mukarba Chowk', lat: 28.7351, lon: 77.1556, sequence: 39 },
      ],
      has_shape_geometry: true,
      shape_coordinates: [[28.71598, 77.1708], [28.7351, 77.1556]],
    });

    vi.spyOn(apiService, 'getSuitableVehicles').mockResolvedValue({
      route_id: '1598',
      board_stop_id: '284',
      alight_stop_id: '5146',
      suitable_count: 0,
      vehicles: [],
      fallback_message: 'No verified live bus is currently available for this journey.',
      disclaimer: 'test',
      poll_interval_seconds: 15,
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

    await waitFor(() => {
      expect(
        screen.getByText('No verified live bus is currently available for this journey.')
      ).toBeInTheDocument();
    });

    // Verify no bus markers rendered in Mode B
    expect(screen.queryByText('Live GPS')).not.toBeInTheDocument();
    expect(screen.queryByText('Estimated position (Dead Reckoned)')).not.toBeInTheDocument();
    expect(screen.queryByText(/Verified candidate bus/i)).not.toBeInTheDocument();
  });
});
