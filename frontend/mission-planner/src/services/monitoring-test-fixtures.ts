export const aware = '2026-08-29T12:34:56.789123Z';

export const missing = Symbol('missing');

export function clone<T>(value: T): T {
  return structuredClone(value);
}

export function setAt<T>(
  value: T,
  path: readonly (string | number)[],
  next: unknown
): T {
  const output = clone(value) as Record<string, unknown>;
  let cursor: Record<string, unknown> = output;
  for (const key of path.slice(0, -1)) {
    cursor = cursor[key] as Record<string, unknown>;
  }
  const key = path.at(-1);
  if (key === undefined) return output as T;
  if (next === missing) delete cursor[key];
  else cursor[key] = next;
  return output as T;
}

export function withResponse<T>(payload: T): { data: T } {
  return { data: payload };
}

export const historyMetrics = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;

export const statusPayload = {
  timestamp: aware,
  position: {
    latitude: -90,
    longitude: 180,
    altitude: -12.5,
    speed: 0,
    heading: 360,
  },
  network: {
    latency_ms: 23.5,
    throughput_down_mbps: 125,
    throughput_up_mbps: 18,
    packet_loss_percent: 100,
  },
  obstruction: { obstruction_percent: 0 },
  environmental: {
    signal_quality_percent: 99.1,
    uptime_seconds: 120,
    temperature_celsius: -40,
  },
};

export const historyPayload = {
  generated_at: aware,
  window_start: '2026-08-29T12:00:00-06:00',
  window_end: '2026-08-29T12:30:00-06:00',
  range_seconds: 1800,
  step_seconds: 1,
  series: historyMetrics.map((metric, index) => ({
    metric,
    samples: [
      { timestamp: `2026-08-29T12:00:0${index}.000001Z`, value: index },
      { timestamp: `2026-08-29T12:00:0${index}.000002Z`, value: null },
    ],
  })),
};

export const availableGep = {
  available: true,
  observed_at: '2026-08-29T12:30:00+00:00',
  generated_at: aware,
  display: 'Denver, CO, US',
  city: '',
  region: 'CO',
  country: 'US',
  latitude: 39.7392,
  longitude: -104.9903,
};

export const unavailableGep = {
  available: false,
  observed_at: null,
  generated_at: aware,
  display: null,
  city: null,
  region: null,
  country: null,
  latitude: null,
  longitude: null,
};

export const routeCoordinate = {
  latitude: 39,
  longitude: -104,
  altitude_meters: null,
  sequence: 1.5,
};

export const routePayload = {
  route_id: 'route-1',
  route_name: null,
  revision_at: '2026-08-29T12:00:00+00:00',
  generated_at: aware,
  total: 1,
  coordinates: [routeCoordinate],
};

export const poi = {
  poi_id: 'poi-1',
  name: 'Departure',
  latitude: 39,
  longitude: -104,
  category: 'departure',
  icon: 'plane-takeoff',
  active: true,
  eta_seconds: -1,
  eta_type: 'anticipated',
  is_pre_departure: true,
  flight_phase: 'pre_departure',
  distance_meters: 0,
  bearing_degrees: 360,
  course_status: 'on_course',
  is_on_active_route: true,
  projected_latitude: 39,
  projected_longitude: -104,
  projected_waypoint_index: 0,
  projected_route_progress: 100,
  route_aware_status: 'pre_departure',
};

export const poiPayload = { pois: [poi], total: 1, timestamp: aware };

export const xLinkCoordinate = {
  satellite_id: 'sat-1',
  state: 'normal',
  color: 'green',
  relative_azimuth_degrees: 12.5,
  in_forbidden_window: false,
  point: 'aircraft',
  sequence: 0,
  latitude: 39,
  longitude: -104,
  observed_at: null,
};

export const xLinkHandoff = {
  phase: 'outside',
  transition_id: null,
  transition_satellite_id: null,
  radius_meters: 1000,
  distance_to_transition_meters: null,
  in_handoff_zone: false,
  route_progress_percent: null,
  transition_progress_percent: null,
};

export const activeXLinkPayload = {
  coordinates: [xLinkCoordinate],
  links: [
    {
      satellite_id: 'sat-1',
      state: 'normal',
      color: 'green',
      relative_azimuth_degrees: 12.5,
      in_forbidden_window: false,
      coordinates: [
        xLinkCoordinate,
        { ...xLinkCoordinate, point: 'satellite', sequence: 1 },
      ],
    },
  ],
  total: 1,
  satellite_id: 'sat-1',
  pending_satellite_id: null,
  handoff: xLinkHandoff,
  state: 'normal',
  color: 'green',
  relative_azimuth_degrees: 12.5,
  in_forbidden_window: false,
  observed_at: null,
  generated_at: aware,
};
