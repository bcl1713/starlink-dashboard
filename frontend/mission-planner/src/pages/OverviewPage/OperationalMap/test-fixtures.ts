import type {
  ActiveXLink,
  MonitoringHistory,
  OverviewStatus,
  POIETA,
  POIETAResponse,
  RouteCoordinates,
} from '../../../types/monitoring';
import type {
  OverviewDataSnapshot,
  OverviewSourcePhase,
  OverviewSourceSlot,
} from '../overview-data-types';

type LatLon = Readonly<{ latitude: number; longitude: number }>;

interface SnapshotOptions {
  readonly routeWest?: readonly LatLon[];
  readonly routeEast?: readonly LatLon[];
  readonly activeNormal?: readonly LatLon[];
  readonly activeWarning?: readonly LatLon[];
  readonly history?: readonly (readonly [string, number, number])[];
  readonly routePhase?: OverviewSourcePhase;
  readonly routeError?: boolean;
  readonly radarPhase?: OverviewSourcePhase;
  readonly radarError?: boolean;
  readonly heading?: number;
}

const timestamp = '2026-08-29T12:00:00Z';

export function makeOverviewSnapshot(
  options: SnapshotOptions = {}
): OverviewDataSnapshot {
  const routeWest = route('route-west', options.routeWest ?? []);
  const routeEast = route('route-east', options.routeEast ?? []);
  const activeNormal = activeLink('normal', options.activeNormal ?? []);
  const activeWarning = activeLink('warning', options.activeWarning ?? []);
  const pois = poiResponse([
    poi('poi-a', 'Departure <script>', 39, -104, 'departure'),
  ]);
  return {
    telemetry: slot(status(options.heading), 'ready', timestamp),
    history: slot(history(options.history ?? []), 'ready', timestamp),
    activeLink: slot(
      { normal: activeNormal, warning: activeWarning },
      'ready',
      timestamp
    ),
    pois: slot(pois, 'ready', timestamp),
    satellites: slot(
      poiResponse([poi('sat-a', 'Satellite A', 1, 2, 'satellite')]),
      'ready',
      timestamp
    ),
    missionEvents: slot(poiResponse([]), 'ready', timestamp),
    route: slot(
      { west: routeWest, east: routeEast },
      options.routePhase ?? 'ready',
      timestamp,
      options.routeError
    ),
    groundEntryPoint: slot(
      {
        available: true,
        observed_at: timestamp,
        generated_at: timestamp,
        display: 'Denver',
        city: 'Denver',
        region: 'CO',
        country: 'US',
        latitude: 39.7392,
        longitude: -104.9903,
      },
      'ready',
      timestamp
    ),
    radar: slot(
      { frameTimestamp: '1777294800' },
      options.radarPhase ?? 'ready',
      '1777294800',
      options.radarError
    ),
    initialState: 'ready',
    manualResult: 'idle',
    globalTransportLastSuccessAt: 1,
    announcement: null,
  };
}

function slot<T>(
  data: T | undefined,
  phase: OverviewSourcePhase,
  sourceTimestamp: string | null,
  failed = false
): OverviewSourceSlot<T> {
  return {
    data,
    phase,
    availability: data === undefined ? 'unknown' : 'available',
    freshness: phase === 'stale' ? 'stale' : 'fresh',
    sourceTimestamp,
    transportLastAttemptAt: 1,
    transportLastSuccessAt: failed ? null : 1,
    pending: phase === 'refreshing',
    paused: phase === 'paused',
    error: failed
      ? { code: 'request-failed', message: 'Source refresh failed.' }
      : null,
  };
}

function route(id: string, coordinates: readonly LatLon[]): RouteCoordinates {
  return {
    route_id: id,
    route_name: id,
    revision_at: timestamp,
    generated_at: timestamp,
    total: coordinates.length,
    coordinates: coordinates.map((point, index) => ({
      ...point,
      altitude_meters: null,
      sequence: index,
    })),
  };
}

function activeLink(
  state: 'normal' | 'warning',
  coordinates: readonly LatLon[]
): ActiveXLink {
  const color = state === 'normal' ? 'green' : 'yellow';
  return {
    coordinates: [],
    links: coordinates.length
      ? [
          {
            satellite_id: 'sat-a',
            state,
            color,
            relative_azimuth_degrees: 12,
            in_forbidden_window: state === 'warning',
            coordinates: coordinates.map((point, index) => ({
              ...point,
              satellite_id: 'sat-a',
              state,
              color,
              relative_azimuth_degrees: 12,
              in_forbidden_window: state === 'warning',
              point: index === 0 ? 'aircraft' : 'satellite',
              sequence: index,
              observed_at: timestamp,
            })),
          },
        ]
      : [],
    total: coordinates.length,
    satellite_id: 'sat-a',
    pending_satellite_id: null,
    handoff: {
      phase: 'outside',
      transition_id: null,
      transition_satellite_id: null,
      radius_meters: 0,
      distance_to_transition_meters: null,
      in_handoff_zone: false,
      route_progress_percent: null,
      transition_progress_percent: null,
    },
    state,
    color,
    relative_azimuth_degrees: 12,
    in_forbidden_window: state === 'warning',
    observed_at: timestamp,
    generated_at: timestamp,
  };
}

function history(
  rows: readonly (readonly [string, number, number])[]
): MonitoringHistory {
  return {
    generated_at: timestamp,
    window_start: timestamp,
    window_end: timestamp,
    range_seconds: 1800,
    step_seconds: 1,
    series: [
      {
        metric: 'latitude_degrees',
        samples: rows.map(([sampleTimestamp, latitude]) => ({
          timestamp: sampleTimestamp,
          value: latitude,
        })),
      },
      {
        metric: 'longitude_degrees',
        samples: rows.map(([sampleTimestamp, , longitude]) => ({
          timestamp: sampleTimestamp,
          value: longitude,
        })),
      },
    ],
  };
}

function poiResponse(pois: readonly POIETA[]): POIETAResponse {
  return { pois: [...pois], total: pois.length, timestamp };
}

function poi(
  poi_id: string,
  name: string,
  latitude: number,
  longitude: number,
  category: string
): POIETA {
  return {
    poi_id,
    name,
    latitude,
    longitude,
    category,
    icon: '',
    active: true,
    eta_seconds: 120,
    eta_type: 'estimated',
    is_pre_departure: false,
    flight_phase: 'in_flight',
    distance_meters: 1000,
    bearing_degrees: 90,
    course_status: 'on_course',
    is_on_active_route: true,
    projected_latitude: null,
    projected_longitude: null,
    projected_waypoint_index: null,
    projected_route_progress: null,
    route_aware_status: null,
  };
}

function status(heading = 90): OverviewStatus {
  return {
    timestamp,
    position: {
      latitude: 39,
      longitude: -104,
      altitude: 1,
      speed: 2,
      heading,
    },
    network: {
      latency_ms: 1,
      throughput_down_mbps: 2,
      throughput_up_mbps: 3,
      packet_loss_percent: 0,
    },
    obstruction: { obstruction_percent: 0 },
    environmental: {
      signal_quality_percent: 99,
      uptime_seconds: 1,
      temperature_celsius: null,
    },
  };
}
