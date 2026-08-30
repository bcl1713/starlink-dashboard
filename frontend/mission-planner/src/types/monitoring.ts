export type OverviewDataSource =
  | 'status'
  | 'monitoring-history'
  | 'ground-entry-point'
  | 'poi-etas'
  | 'route-coordinates'
  | 'active-x-link'
  | 'rainviewer-radar-tile';

export class OverviewDataValidationError extends Error {
  declare readonly name: 'OverviewDataValidationError';
  declare readonly code: 'invalid_overview_data';
  declare readonly source: OverviewDataSource;

  constructor(source: OverviewDataSource) {
    super(`Invalid overview data: ${source}`);
    Object.defineProperty(this, 'name', {
      value: 'OverviewDataValidationError',
      enumerable: true,
      configurable: true,
    });
    Object.defineProperty(this, 'code', {
      value: 'invalid_overview_data',
      enumerable: true,
      configurable: true,
    });
    Object.defineProperty(this, 'source', {
      value: source,
      enumerable: true,
      configurable: true,
    });
  }
}

export type OverviewPOIFilter =
  | 'departure,arrival'
  | ''
  | 'departure'
  | 'arrival'
  | 'waypoint'
  | 'alternate';

export type POIETAFilter = OverviewPOIFilter | 'satellite' | 'mission-event';

export const OVERVIEW_POI_FILTER_OPTIONS = [
  { label: 'Departure & Arrival', value: 'departure,arrival' },
  { label: 'All POIs', value: '' },
  { label: 'Departure Only', value: 'departure' },
  { label: 'Arrival Only', value: 'arrival' },
  { label: 'Waypoints Only', value: 'waypoint' },
  { label: 'Alternates Only', value: 'alternate' },
] as const satisfies readonly {
  label: string;
  value: OverviewPOIFilter;
}[];

export interface GetMonitoringHistoryArgs {
  rangeSeconds?: number;
  stepSeconds?: number;
  signal?: AbortSignal;
}

export interface GetRainViewerRadarTileArgs {
  z: number;
  x: number;
  y: number;
  signal?: AbortSignal;
}

export interface OverviewStatus {
  timestamp: string;
  position: {
    latitude: number;
    longitude: number;
    altitude: number;
    speed: number;
    heading: number;
  };
  network: {
    latency_ms: number;
    throughput_down_mbps: number;
    throughput_up_mbps: number;
    packet_loss_percent: number;
  };
  obstruction: { obstruction_percent: number };
  environmental: {
    signal_quality_percent: number;
    uptime_seconds: number;
    temperature_celsius: number | null;
  };
}

export interface MonitoringHistory {
  generated_at: string;
  window_start: string;
  window_end: string;
  range_seconds: number;
  step_seconds: number;
  series: {
    name:
      | 'latitude_degrees'
      | 'longitude_degrees'
      | 'latency_ms'
      | 'throughput_down_mbps'
      | 'throughput_up_mbps'
      | 'packet_loss_percent';
    samples: { timestamp: string; value: number | null }[];
  }[];
}

export interface GroundEntryPoint {
  available: boolean;
  observed_at: string | null;
  generated_at: string;
  display: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface RouteCoordinates {
  route_id: string | null;
  route_name: string | null;
  revision_at: string | null;
  generated_at: string;
  total: number;
  coordinates: {
    latitude: number;
    longitude: number;
    altitude_meters: number | null;
    sequence: number;
  }[];
}

export interface POIETAResponse {
  pois: POIETA[];
  total: number;
  timestamp: string;
}

export interface POIETA {
  poi_id: string;
  name: string;
  latitude: number;
  longitude: number;
  category: string | null;
  icon: string;
  active: boolean;
  eta_seconds: number;
  eta_type: 'anticipated' | 'estimated';
  is_pre_departure: boolean;
  flight_phase: 'pre_departure' | 'in_flight' | 'post_arrival' | null;
  distance_meters: number;
  bearing_degrees: number | null;
  course_status: 'on_course' | 'slightly_off' | 'off_track' | 'behind' | null;
  is_on_active_route: boolean;
  projected_latitude: number | null;
  projected_longitude: number | null;
  projected_waypoint_index: number | null;
  projected_route_progress: number | null;
  route_aware_status:
    | 'ahead_on_route'
    | 'already_passed'
    | 'not_on_route'
    | 'pre_departure'
    | null;
}

export interface ActiveXLink {
  coordinates: ActiveXLinkCoordinate[];
  links: ActiveXLinkSegment[];
  total: number;
  satellite_id: string | null;
  pending_satellite_id: string | null;
  handoff: ActiveXLinkHandoff;
  state: 'normal' | 'warning' | null;
  color: 'green' | 'yellow' | null;
  relative_azimuth_degrees: number | null;
  in_forbidden_window: boolean | null;
  observed_at: string | null;
  generated_at: string;
}

export interface ActiveXLinkCoordinate {
  satellite_id: string;
  state: 'normal' | 'warning';
  color: 'green' | 'yellow';
  relative_azimuth_degrees: number;
  in_forbidden_window: boolean;
  point: 'aircraft' | 'satellite';
  sequence: number;
  latitude: number;
  longitude: number;
  observed_at: string | null;
}

export interface ActiveXLinkSegment {
  satellite_id: string;
  state: 'normal' | 'warning';
  color: 'green' | 'yellow';
  relative_azimuth_degrees: number;
  in_forbidden_window: boolean;
  coordinates: ActiveXLinkCoordinate[];
}

export interface ActiveXLinkHandoff {
  phase: 'outside' | 'in_handoff_zone' | 'committed';
  transition_id: string | null;
  transition_satellite_id: string | null;
  radius_meters: number;
  distance_to_transition_meters: number | null;
  in_handoff_zone: boolean;
  route_progress_percent: number | null;
  transition_progress_percent: number | null;
}

export interface RainViewerRadarTile {
  bytes: ArrayBuffer;
  frameTimestamp: string;
}
