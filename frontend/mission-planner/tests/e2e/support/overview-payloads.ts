import type { OverviewScenario } from '../fixtures/overview';
import { specialPoiPayload } from './overview-special-poi-payloads';

const metricNames = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;

type Scenario = OverviewScenario;
type Coordinate = NonNullable<Scenario['telemetry']['currentPosition']>;
type Poi = Scenario['pois']['items'][number];

export interface LatencyPayloadOverride {
  readonly currentMs: number;
  readonly history: readonly {
    readonly observedAt: string;
    readonly value: number;
  }[];
}

export function statusPayload(
  scenario: Scenario,
  latencyOverride?: LatencyPayloadOverride
) {
  const position = scenario.telemetry.currentPosition;
  const metrics = scenario.telemetry.metrics;
  return {
    timestamp: scenario.telemetry.currentObservedAt ?? scenario.nowIso,
    position: position
      ? {
          latitude: position.latitude,
          longitude: position.longitude,
          altitude: position.altitudeMeters,
          speed: scenario.telemetry.positionHistory.at(-1)?.speedKnots ?? 0,
          heading:
            scenario.telemetry.positionHistory.at(-1)?.headingDegrees ?? 0,
        }
      : null,
    network: {
      latency_ms: latencyOverride?.currentMs ?? metrics.latency.currentMs ?? 0,
      throughput_down_mbps: metrics.throughput.current.downloadMbps ?? 0,
      throughput_up_mbps: metrics.throughput.current.uploadMbps ?? 0,
      packet_loss_percent: metrics.packetLoss.currentPercent ?? 0,
    },
    obstruction: {
      obstruction_percent: metrics.obstruction.currentPercent ?? 0,
    },
    environmental: {
      signal_quality_percent: 96,
      uptime_seconds: 86400,
      temperature_celsius: null,
    },
  };
}

export function historyPayload(
  scenario: Scenario,
  latencyOverride?: LatencyPayloadOverride
) {
  const points = scenario.telemetry.positionHistory;
  const latency =
    latencyOverride?.history ?? scenario.telemetry.metrics.latency.history;
  const down = scenario.telemetry.metrics.throughput.current.downloadMbps;
  const up = scenario.telemetry.metrics.throughput.current.uploadMbps;
  const packetLoss = scenario.telemetry.metrics.packetLoss.history;
  return {
    generated_at: scenario.nowIso,
    window_start: points.at(0)?.observedAt ?? scenario.nowIso,
    window_end: points.at(-1)?.observedAt ?? scenario.nowIso,
    range_seconds: 1800,
    step_seconds: 1,
    series: metricNames.map((metric) => ({
      metric,
      samples: samplesFor(metric, points, latency, packetLoss, down, up),
    })),
  };
}

function samplesFor(
  metric: (typeof metricNames)[number],
  points: Scenario['telemetry']['positionHistory'],
  latency: Scenario['telemetry']['metrics']['latency']['history'],
  packetLoss: Scenario['telemetry']['metrics']['packetLoss']['history'],
  down: number | null,
  up: number | null
) {
  if (metric === 'latitude_degrees') {
    return points.map((point) => ({
      timestamp: point.observedAt,
      value: point.coordinate?.latitude ?? null,
    }));
  }
  if (metric === 'longitude_degrees') {
    return points.map((point) => ({
      timestamp: point.observedAt,
      value: point.coordinate?.longitude ?? null,
    }));
  }
  if (metric === 'latency_ms') {
    return latency.map((sample) => ({
      timestamp: sample.observedAt,
      value: sample.value,
    }));
  }
  if (metric === 'packet_loss_percent') {
    return packetLoss.map((sample) => ({
      timestamp: sample.observedAt,
      value: sample.value,
    }));
  }
  return points.map((point) => ({
    timestamp: point.observedAt,
    value: metric === 'throughput_down_mbps' ? down : up,
  }));
}

export function gepPayload(scenario: Scenario) {
  const coordinate = scenario.groundEntryPoint.coordinate;
  const available =
    coordinate !== null && scenario.groundEntryPoint.display !== '';
  return {
    available,
    observed_at: available ? scenario.groundEntryPoint.observedAt : null,
    generated_at: scenario.nowIso,
    display: available ? scenario.groundEntryPoint.display : null,
    city: available ? scenario.groundEntryPoint.display.split(',')[0] : null,
    region: available
      ? scenario.groundEntryPoint.display.split(',')[1]?.trim()
      : null,
    country: available ? 'US' : null,
    latitude: coordinate?.latitude ?? null,
    longitude: coordinate?.longitude ?? null,
  };
}

export function poiPayload(scenario: Scenario, category: string | null) {
  const special = specialPoiPayload(scenario, category);
  if (special) return special;
  const items =
    category === null
      ? scenario.pois.items
      : scenario.pois.items.filter((poi) =>
          category.split(',').includes(poi.category)
        );
  return {
    pois: items.map(toPoiDto),
    total: items.length,
    timestamp: scenario.pois.generatedAt ?? scenario.nowIso,
  };
}

function toPoiDto(poi: Poi) {
  return {
    poi_id: poi.id,
    name: poi.name,
    latitude: poi.coordinate.latitude,
    longitude: poi.coordinate.longitude,
    category: poi.category,
    icon: iconFor(poi.category),
    active: true,
    eta_seconds: etaSeconds(poi.etaIso),
    eta_type: 'estimated',
    is_pre_departure: false,
    flight_phase: 'in_flight',
    distance_meters: poi.distanceMeters,
    bearing_degrees: 82,
    course_status: 'on_course',
    is_on_active_route: true,
    projected_latitude: poi.coordinate.latitude,
    projected_longitude: poi.coordinate.longitude,
    projected_waypoint_index: 1,
    projected_route_progress: 55,
    route_aware_status: 'ahead_on_route',
  };
}

function etaSeconds(etaIso: string): number {
  return Math.max(
    60,
    Math.round((Date.parse(etaIso) - Date.parse('2026-02-03T15:30:00Z')) / 1000)
  );
}

function iconFor(category: Poi['category']): string {
  if (category === 'departure') return 'plane-takeoff';
  if (category === 'arrival') return 'plane-landing';
  if (category === 'alternate') return 'map-pin';
  return 'navigation';
}

export function routePayload(scenario: Scenario, direction: 'west' | 'east') {
  const coordinates =
    direction === 'west'
      ? scenario.route.westernSegment
      : scenario.route.easternSegment;
  return {
    route_id: scenario.route.active ? scenario.route.id : null,
    route_name: scenario.route.active ? scenario.route.name : null,
    revision_at: scenario.route.revisionAt,
    generated_at: scenario.nowIso,
    total: coordinates.length,
    coordinates: coordinates.map(toRouteCoordinate),
  };
}

function toRouteCoordinate(coordinate: Coordinate, sequence: number) {
  return {
    latitude: coordinate.latitude,
    longitude: coordinate.longitude,
    altitude_meters: coordinate.altitudeMeters,
    sequence,
  };
}

export function activeLinkPayload(
  scenario: Scenario,
  state: 'normal' | 'warning'
) {
  const links = scenario.activeLinks.filter((link) => link.mode === state);
  const coordinates = links.flatMap((link) =>
    link.from && link.to
      ? [
          toXLinkCoordinate(link.from, state, 0),
          toXLinkCoordinate(link.to, state, 1),
        ]
      : []
  );
  return {
    coordinates,
    links: links.map((link) => ({
      satellite_id: link.id,
      state,
      color: state === 'normal' ? 'green' : 'yellow',
      relative_azimuth_degrees: 24,
      in_forbidden_window: false,
      coordinates:
        link.from && link.to
          ? [
              toXLinkCoordinate(link.from, state, 0),
              toXLinkCoordinate(link.to, state, 1),
            ]
          : [],
    })),
    total: coordinates.length,
    satellite_id: links.at(0)?.id ?? null,
    pending_satellite_id: null,
    handoff: {
      phase: 'outside',
      transition_id: null,
      transition_satellite_id: null,
      radius_meters: 1000,
      distance_to_transition_meters: null,
      in_handoff_zone: false,
      route_progress_percent: null,
      transition_progress_percent: null,
    },
    state: links.length > 0 ? state : null,
    color: links.length > 0 ? (state === 'normal' ? 'green' : 'yellow') : null,
    relative_azimuth_degrees: links.length > 0 ? 24 : null,
    in_forbidden_window: links.length > 0 ? false : null,
    observed_at: links.at(0)?.observedAt ?? null,
    generated_at: scenario.nowIso,
  };
}

function toXLinkCoordinate(
  coordinate: Coordinate,
  state: 'normal' | 'warning',
  sequence: number
) {
  return {
    satellite_id: `${state}-satellite`,
    state,
    color: state === 'normal' ? 'green' : 'yellow',
    relative_azimuth_degrees: 24,
    in_forbidden_window: false,
    point: sequence === 0 ? 'aircraft' : 'satellite',
    sequence,
    latitude: coordinate.latitude,
    longitude: coordinate.longitude,
    observed_at: '2026-02-03T15:30:00Z',
  };
}
