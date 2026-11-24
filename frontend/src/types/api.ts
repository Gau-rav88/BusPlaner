/**
 * TypeScript API Definitions for Delhi Bus Traffic Prediction & Journey Planner.
 * Aligns strictly with FastAPI Pydantic schemas in backend/app/schemas/.
 */

export type TimetableStatusType = 'CURRENT_VERIFIED' | 'EXPIRED' | 'ASSUMED_RECURRING' | 'UNAVAILABLE';

export interface HealthResponse {
  application_status: string;
  backend_version: string;
  database_available: boolean;
  gtfs_loaded: boolean;
  model_available?: boolean;
  overall_operational_status: string; // strictly "DEGRADE"
  live_feed_status?: string;
  live_feed_enabled?: boolean;
  timestamp_utc: string;
}

export interface LiveFeedStatusResponse {
  feed_enabled: boolean;
  feed_configured_enabled: boolean;
  feed_availability_status: string;
  endpoint_url: string;
  auth_required: boolean;
  auth_configured: boolean;
  poll_interval_seconds: number;
  max_staleness_seconds?: number;
  last_attempt_timestamp_utc: string | null;
  last_success_timestamp_utc: string | null;
  consecutive_failure_count: number;
  total_polls_count: number;
  total_success_count: number;
  active_vehicles_count: number;
  warning: string;
  overall_operational_status: string;
}

export interface TimetableStatusResponse {
  timetable_status: TimetableStatusType;
  feed_start_date: string | null;
  feed_end_date: string | null;
  feed_provenance: string;
  is_date_within_feed_validity: boolean;
  actual_operations_verified: boolean; // strictly false
  demonstration_mode_available: boolean;
  service_date_evaluated: string;
  warnings: string[];
}

export interface Stop {
  stop_id: string;
  stop_name: string;
  lat: number;
  lon: number;
  distance_m?: number;
  walking_time_s?: number;
}

export interface StopSearchResponse {
  query: string;
  total: number;
  stops: Stop[];
}

export interface NearbyStopsResponse {
  origin_lat: number;
  origin_lon: number;
  radius_m: number;
  total: number;
  stops: Stop[];
}

export interface OrderedStop {
  sequence: number;
  stop_id: string;
  stop_name: string;
  lat: number;
  lon: number;
}

export interface RouteDetailResponse {
  route_id: string;
  agency_id: string | null;
  route_short_name: string | null;
  route_long_name: string | null;
  trips_count: number;
  patterns_count: number;
  ordered_stops: OrderedStop[];
  has_shape_geometry?: boolean;
  shape_coordinates?: [number, number][];
}

export interface WalkingLeg {
  leg_type: 'ACCESS' | 'TRANSFER' | 'EGRESS' | 'DIRECT_WALK';
  from_name: string;
  to_name: string;
  from_stop_id?: string | null;
  to_stop_id?: string | null;
  start_time_s: number;
  end_time_s: number;
  duration_s: number;
  distance_m: number;
}

export type PredictionTier =
  | 'LEVEL_1_DIRECT_OBSERVED'
  | 'LEVEL_2_HISTORICAL_BASELINE_M0'
  | 'LEVEL_3_EXPERIMENTAL_RF'
  | 'LEVEL_4_GTFS_SCHEDULED'
  | 'LEVEL_5_STATIC_FALLBACK';

export type LiveBusIdentificationStatus =
  | 'IDENTIFIED_APPROACHING'
  | 'IDENTIFIED_NEAR'
  | 'ROUTE_MATCH_UNVERIFIED'
  | 'PASSED_STOP'
  | 'UNIDENTIFIED';

export interface LiveBusCandidate {
  identification_status: LiveBusIdentificationStatus;
  guidance_message: string;
  vehicle_id?: string | null;
  route_id?: string | null;
  trip_id?: string | null;
  trip_headsign?: string | null;
  progress_status?: 'APPROACHING' | 'NEAR_BOARDING_STOP' | 'PASSED' | 'UNVERIFIED' | null;
  distance_to_board_m?: number | null;
  stops_away?: number | null;
  speed_kmh?: number | null;
  source_timestamp_utc?: number | null;
  age_seconds?: number | null;
  is_fresh?: boolean | null;
  is_candidate_only: boolean;
  disclaimer: string;
}

export interface TransitLeg {
  leg_type: 'TRANSIT';
  route_id: string;
  trip_id: string;
  pattern_id: number;
  board_stop_id: string;
  board_stop_name: string;
  alight_stop_id: string;
  alight_stop_name: string;
  sched_departure_s: number;
  sched_arrival_s: number;
  sched_duration_s: number;
  board_time_s: number;
  alight_time_s: number;
  ride_duration_s: number;
  intermediate_stops: string[];
  prediction_tier: PredictionTier;
  prediction_source: string;
  heuristic_confidence_score: number;
  confidence_score_type: 'HEURISTIC';
  confidence_explanation: string;
  is_fallback: boolean;
  fallback_reason?: string | null;
  warning?: string | null;
  timetable_status: string;
  is_verified_current_service: boolean;
  live_bus?: LiveBusCandidate | null;
}

export type Leg = WalkingLeg | TransitLeg;

export interface JourneyAccounting {
  access_walking_time_s: number;
  initial_waiting_time_s: number;
  in_vehicle_duration_s: number;
  transfer_walking_time_s: number;
  transfer_waiting_time_s: number;
  egress_walking_time_s: number;
  total_duration_s: number;
  discrepancy_s: number;
  is_valid_identity: boolean;
}

export interface JourneyAlternative {
  journey_id: string;
  num_transfers: number;
  departure_time_s: number;
  arrival_time_s: number;
  total_journey_duration_s: number;
  legs: Leg[];
  accounting: JourneyAccounting;
  heuristic_confidence_score: number;
  confidence_score_type: string;
  timetable_status: string;
  is_verified_current_service: boolean;
  actual_operations_verified: boolean; // strictly false
  long_transfer_advisory?: string | null;
  has_long_transfer_wait?: boolean;
  warnings: string[];
}

export interface JourneyPlanRequest {
  origin_stop_id?: string | null;
  dest_stop_id?: string | null;
  origin_lat?: number | null;
  origin_lon?: number | null;
  dest_lat?: number | null;
  dest_lon?: number | null;
  departure_date: string;
  departure_time: string;
  max_walking_distance_m: number;
  max_transfers: number;
  num_alternatives: number;
  ranking_strategy: 'earliest_arrival' | 'fewest_transfers' | 'least_walking' | 'most_reliable';
  use_experimental_ml: boolean;
  allow_assumed_recurring: boolean;
}

export interface JourneyPlanResponse {
  query_summary: Record<string, any>;
  journeys_count: number;
  journeys: JourneyAlternative[];
  timetable_status: string;
  stale_timetable_warning?: string | null;
}

export interface ApiError {
  error: string;
  detail: string;
  error_code?: string;
  action?: string;
  feed_end_date?: string;
  requested_date?: string;
}

export interface LiveVehicleItem {
  vehicle_id: string;
  route_id: string | null;
  trip_id: string | null;
  latitude: number;
  longitude: number;
  bearing: number | null;
  speed_kmh: number | null;
  timestamp_utc: number;
  age_seconds: number;
  is_fresh: boolean;
  is_current?: boolean;
  is_out_of_area?: boolean;
  area_classification?: string;
  is_matched_to_gtfs: boolean;
  agency: string;
  distance_m?: number;
}

export interface LiveVehiclesResponse {
  total_active_vehicles: number;
  returned_vehicles_count: number;
  current_vehicles_count?: number;
  last_known_vehicles_count?: number;
  out_of_area_count?: number;
  route_filter: string | null;
  vehicles: LiveVehicleItem[];
  latest_timestamp_utc: string | null;
  feed_availability_status: string;
  disclaimer: string;
  search_lat?: number | null;
  search_lon?: number | null;
  search_radius_m?: number | null;
  viewport_min_lat?: number | null;
  viewport_max_lat?: number | null;
  viewport_min_lon?: number | null;
  viewport_max_lon?: number | null;
  total_matching_count?: number | null;
  current_matching_count?: number | null;
  stale_matching_count?: number | null;
}

export interface SuitableVehicleItem {
  vehicle_id: string;
  route_id: string;
  trip_id?: string | null;
  trip_headsign?: string | null;
  destination_stop_name?: string | null;
  progress_status: 'NEAR_BOARDING_STOP' | 'APPROACHING' | 'UNVERIFIED_STALE';
  distance_to_board_m: number;
  stops_away?: number | null;
  speed_kmh?: number | null;
  latitude: number;
  longitude: number;
  bearing?: number | null;
  timestamp_utc: number;
  age_seconds: number;
  is_fresh: boolean;
  is_current: boolean;
  is_verified_suitable: boolean;
  is_verified_destination: boolean;
  guidance_message: string;
  position_source?: 'GPS' | 'DEAD_RECKONED';
  is_dead_reckoned?: boolean;
  last_gps_latitude?: number | null;
  last_gps_longitude?: number | null;
  last_gps_timestamp?: number | null;
  position_timestamp?: number | null;
  prediction_age_seconds?: number | null;
  uncertainty_meters?: number | null;
  route_progress_meters?: number | null;
  last_prediction_error_meters?: number | null;
  last_correction_distance_meters?: number | null;
  correction_status?: string;
  last_gps_observation_time?: string | null;
  latest_position_calculation_time?: string | null;
  next_expected_update_time?: string | null;
  anomaly_flags?: string[];
  has_anomalies?: boolean;
  gps_accuracy_status?: string;
}

export interface SuitableVehiclesResponse {
  route_id: string;
  board_stop_id: string;
  alight_stop_id: string;
  suitable_count: number;
  vehicles: SuitableVehicleItem[];
  fallback_message?: string | null;
  diagnostic_detail?: string | null;
  disclaimer: string;
  upstream_feed_timestamp_utc?: number | null;
  upstream_feed_age_seconds?: number | null;
  poll_interval_seconds?: number;
}


