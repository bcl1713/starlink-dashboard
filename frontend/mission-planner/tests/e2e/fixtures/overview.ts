type Timezone = 'UTC' | 'America/New_York' | 'Asia/Tokyo' | 'America/Chicago';
type PoiCategory = 'departure' | 'arrival' | 'waypoint' | 'alternate';
type HealthState = 'ok' | 'warning' | 'critical' | 'stale' | 'unavailable';
type LayerAvailability =
  | 'available'
  | 'empty'
  | 'unavailable'
  | 'local-failure';

type Coordinate = Readonly<{
  latitude: number;
  longitude: number;
  altitudeMeters: number;
}>;

type TimestampedPosition = Readonly<{
  observedAt: string;
  coordinate: Coordinate | null;
  speedKnots: number | null;
  headingDegrees: number | null;
}>;

type NumericSample = Readonly<{ observedAt: string; value: number | null }>;

type SplitGeometry = Readonly<{
  westernSegment: readonly Coordinate[];
  easternSegment: readonly Coordinate[];
}>;

type PositionHistorySplit = Readonly<{
  westernSegment: readonly TimestampedPosition[];
  easternSegment: readonly TimestampedPosition[];
}>;

type Metrics = Readonly<{
  latency: Readonly<{
    currentMs: number | null;
    fiveMinute: Readonly<{
      minMs: number | null;
      averageMs: number | null;
      maxMs: number | null;
    }>;
    history: readonly NumericSample[];
  }>;
  packetLoss: Readonly<{
    currentPercent: number | null;
    averagePercent: number | null;
    maxPercent: number | null;
    history: readonly NumericSample[];
  }>;
  throughput: Readonly<{
    current: Readonly<{
      downloadMbps: number | null;
      uploadMbps: number | null;
    }>;
  }>;
  obstruction: Readonly<{ currentPercent: number | null }>;
}>;

type Route = Readonly<{
  id: string;
  name: string;
  active: boolean;
  revisionAt: string | null;
  crossesInternationalDateLine: boolean;
  westernSegment: readonly Coordinate[];
  easternSegment: readonly Coordinate[];
}>;

type Poi = Readonly<{
  id: string;
  name: string;
  category: PoiCategory;
  coordinate: Coordinate;
  etaIso: string;
  distanceMeters: number;
}>;

type PoiFilter = Readonly<{
  value: string;
  query: Readonly<{ category?: string }>;
}>;

type PoiResponse = Readonly<{
  generatedAt: string | null;
  items: readonly Poi[];
}>;

type SourceResponse<T> = Readonly<{
  generatedAt: string | null;
  items: readonly T[];
}>;

type RadarSource = Readonly<{
  available: boolean;
  frameAt: string | null;
  state: HealthState;
  error?: string;
}>;

type SourceFreshness = Readonly<{
  telemetry: string | null;
  history: string | null;
  activeLink: string | null;
  pois: string | null;
  route: string | null;
  groundEntryPoint: string | null;
  radar: string | null;
}>;

type LayerState = Readonly<{
  id: string;
  state: HealthState;
  availability: LayerAvailability;
  value: string;
}>;

type PanelState = Readonly<{
  id: string;
  state: HealthState;
  value: string;
}>;

type ActiveLink = Readonly<{
  id: string;
  mode: 'normal' | 'warning' | 'unavailable';
  observedAt: string | null;
  from: Coordinate | null;
  to: Coordinate | null;
  splitGeometry?: SplitGeometry;
}>;

type MissionEvent = Readonly<{
  id: string;
  observedAt: string;
  type: 'departure' | 'waypoint' | 'arrival' | 'system';
  label: string;
  coordinate: Coordinate | null;
}>;

export type OverviewPanel = Readonly<
  { concept: string; id: string } & { timezone?: Timezone }
>;

export type OverviewMapLayer = Readonly<{
  concept: string;
  id: string;
  source: string;
  enabledByDefault: boolean;
}>;

export type OverviewPoiOption = Readonly<{
  label: string;
  value: string;
  query: Readonly<{ category?: string }>;
  isDefault?: true;
}>;

export type OverviewScenario = Readonly<{
  id: string;
  name: string;
  nowIso: string;
  selectedPoiFilter: PoiFilter;
  telemetry: Readonly<{
    currentObservedAt: string | null;
    currentPosition: Coordinate | null;
    positionHistory: readonly TimestampedPosition[];
    positionHistorySplit?: PositionHistorySplit;
    metrics: Metrics;
  }>;
  route: Route;
  pois: PoiResponse;
  groundEntryPoint: Readonly<{
    id: string;
    display: string;
    observedAt: string | null;
    coordinate: Coordinate | null;
  }>;
  radar: RadarSource;
  satellites: SourceResponse<
    Readonly<{
      id: string;
      name: string;
      coordinate: Coordinate;
    }>
  >;
  activeLinks: readonly ActiveLink[];
  missionEvents: SourceResponse<MissionEvent>;
  expected: Readonly<{
    topFivePoiIds: readonly string[];
    panelStates: readonly PanelState[];
    sourceFreshness: SourceFreshness;
    layerStates: readonly LayerState[];
    route: Readonly<{
      state: HealthState;
      westernPointCount: number;
      easternPointCount: number;
      crossesInternationalDateLine: boolean;
    }>;
    radar: Readonly<{ state: HealthState; frameState: string }>;
  }>;
}>;

const panels = [
  { concept: 'UTC (Zulu) clock', id: 'clock-utc', timezone: 'UTC' },
  {
    concept: 'Washington DC clock',
    id: 'clock-washington-dc',
    timezone: 'America/New_York',
  },
  { concept: 'Tokyo clock', id: 'clock-tokyo', timezone: 'Asia/Tokyo' },
  {
    concept: 'Omaha clock',
    id: 'clock-omaha',
    timezone: 'America/Chicago',
  },
  { concept: 'Current Position map', id: 'current-position-map' },
  {
    concept: 'POI Quick Reference (top five applicable future POIs)',
    id: 'poi-quick-reference',
  },
  { concept: 'Network Latency', id: 'network-latency' },
  { concept: 'Throughput', id: 'throughput' },
  { concept: 'Ground Entry Point', id: 'ground-entry-point' },
  { concept: 'Obstruction', id: 'obstruction' },
  { concept: 'Packet Loss', id: 'packet-loss' },
] as const satisfies readonly OverviewPanel[];

const mapLayers = [
  ['Weather Radar', 'weather-radar', 'RainViewer'],
  ['Planned Route — western segment', 'planned-route-west', 'active-route'],
  ['Planned Route — eastern segment', 'planned-route-east', 'active-route'],
  ['Active X-band Link — normal', 'active-x-band-normal', 'satellite-link'],
  ['Active X-band Link — warning', 'active-x-band-warning', 'satellite-link'],
  [
    'Position History — western segments',
    'position-history-west',
    'telemetry-history',
  ],
  [
    'Position History — eastern segments',
    'position-history-east',
    'telemetry-history',
  ],
  ['Flight route/POI markers', 'flight-route-markers', 'route-pois'],
  ['Satellites', 'satellites', 'satellite-positions'],
  ['Mission events', 'mission-events', 'mission-events'],
  ['Ground entry point', 'ground-entry-point-layer', 'ground-entry-point'],
  ['Current position', 'current-position-layer', 'telemetry'],
].map(([concept, id, source]) => ({
  concept,
  id,
  source,
  enabledByDefault: true,
})) satisfies readonly OverviewMapLayer[];

export const OVERVIEW_CONTRACT = {
  panels,
  mapLayers,
  poiOptions: [
    {
      label: 'Departure & Arrival',
      value: 'departure,arrival',
      query: { category: 'departure,arrival' },
      isDefault: true,
    },
    { label: 'All POIs', value: '', query: {} },
    {
      label: 'Departure Only',
      value: 'departure',
      query: { category: 'departure' },
    },
    { label: 'Arrival Only', value: 'arrival', query: { category: 'arrival' } },
    {
      label: 'Waypoints Only',
      value: 'waypoint',
      query: { category: 'waypoint' },
    },
    {
      label: 'Alternates Only',
      value: 'alternate',
      query: { category: 'alternate' },
    },
  ],
  defaults: {
    historyRangeSeconds: 1800,
    historyStepSeconds: 1,
    dashboardRefreshSeconds: 1,
    radar: { enabledByDefault: true, opacity: 0.7, minZoom: 0, maxZoom: 7 },
    clocks: [
      { label: 'UTC (Zulu)', timezone: 'UTC', immutable: true },
      { label: 'Washington DC', timezone: 'America/New_York' },
      { label: 'Tokyo', timezone: 'Asia/Tokyo' },
      { label: 'Omaha', timezone: 'America/Chicago' },
    ],
    thresholds: {
      latencyMs: { warning: 100, critical: 200 },
      obstructionPercent: { warning: 5, critical: 10, min: 0, max: 20 },
      packetLossPercent: { warning: 2, critical: 5, min: 0, max: 100 },
    },
    throughput: {
      download: { sign: 'positive', color: 'blue' },
      upload: { sign: 'negative', color: 'green' },
    },
    styles: {
      plannedRouteWest: { color: 'dark-orange', width: 2, opacity: 0.9 },
      plannedRouteEast: { color: 'dark-orange', width: 2, opacity: 1 },
      activeXBandLinkNormal: { color: 'green', width: 4, opacity: 0.9 },
      activeXBandLinkWarning: { color: 'yellow', width: 4, opacity: 0.9 },
      positionHistory: { color: 'blue', width: 3, opacity: 0.7 },
    },
    basemap: { attribution: 'Tiles © Esri' },
  },
} as const;

const c = (
  latitude: number,
  longitude: number,
  altitudeMeters: number
): Coordinate => ({ latitude, longitude, altitudeMeters });

const point = (
  observedAt: string,
  coordinate: Coordinate | null,
  speedKnots: number | null,
  headingDegrees: number | null
): TimestampedPosition => ({
  observedAt,
  coordinate,
  speedKnots,
  headingDegrees,
});

const sample = (observedAt: string, value: number | null): NumericSample => ({
  observedAt,
  value,
});

const average = (values: readonly number[]): number | null => {
  if (values.length === 0) return null;

  return (
    Math.round(
      (values.reduce((total, value) => total + value, 0) / values.length) * 10
    ) / 10
  );
};

const validValues = (samples: readonly NumericSample[]): number[] =>
  samples
    .map((item) => item.value)
    .filter((value): value is number => value !== null);

const metrics = (
  latencyHistory: readonly NumericSample[],
  packetLossHistory: readonly NumericSample[],
  downloadMbps: number | null,
  uploadMbps: number | null,
  obstructionPercent: number | null
): Metrics => ({
  latency: {
    currentMs: latencyHistory.at(-1)?.value ?? null,
    fiveMinute: {
      minMs:
        validValues(latencyHistory).length === 0
          ? null
          : Math.min(...validValues(latencyHistory)),
      averageMs: average(validValues(latencyHistory)),
      maxMs:
        validValues(latencyHistory).length === 0
          ? null
          : Math.max(...validValues(latencyHistory)),
    },
    history: latencyHistory,
  },
  packetLoss: {
    currentPercent: packetLossHistory.at(-1)?.value ?? null,
    averagePercent: average(validValues(packetLossHistory)),
    maxPercent:
      validValues(packetLossHistory).length === 0
        ? null
        : Math.max(...validValues(packetLossHistory)),
    history: packetLossHistory,
  },
  throughput: { current: { downloadMbps, uploadMbps } },
  obstruction: { currentPercent: obstructionPercent },
});

const baseRoute: Route = {
  id: 'route-transpacific-001',
  name: 'Seattle to Tokyo Operational Route',
  active: true,
  revisionAt: '2026-02-03T15:30:00Z',
  crossesInternationalDateLine: false,
  westernSegment: [
    c(47.4502, -122.3088, 132),
    c(52, -150, 10668),
    c(54.6, -170, 11278),
  ],
  easternSegment: [
    c(53.8, 170, 11278),
    c(45, 150, 10973),
    c(35.5494, 139.7798, 21),
  ],
};

const idlRoute: Route = {
  id: 'route-idl-001',
  name: 'Tokyo to Seattle IDL Return',
  active: true,
  revisionAt: '2026-02-03T17:05:59Z',
  crossesInternationalDateLine: true,
  westernSegment: [
    c(35.5494, 170.2, 21),
    c(49.4, 179.6, 11278),
    c(49.8, 180, 11278),
  ],
  easternSegment: [
    c(49.8, -180, 11278),
    c(50.1, -179.7, 11278),
    c(54.2, -165, 11278),
    c(47.4502, -122.3088, 132),
  ],
};

const routeAt = (revisionAt: string): Route => ({ ...baseRoute, revisionAt });

const inactiveRoute = (
  id: string,
  name: string,
  revisionAt: string | null = null
): Route => ({
  id,
  name,
  active: false,
  revisionAt,
  crossesInternationalDateLine: false,
  westernSegment: [],
  easternSegment: [],
});

const basePois = [
  {
    id: 'poi-depart-ksea',
    name: 'KSEA Departure',
    category: 'departure',
    coordinate: c(47.4502, -122.3088, 132),
    etaIso: '2026-02-03T12:00:00Z',
    distanceMeters: 0,
  },
  {
    id: 'poi-waypoint-alaska',
    name: 'Alaska Track Fix',
    category: 'waypoint',
    coordinate: c(55.2, -160.4, 11278),
    etaIso: '2026-02-03T15:20:00Z',
    distanceMeters: 1820000,
  },
  {
    id: 'poi-alternate-panc',
    name: 'PANC Alternate',
    category: 'alternate',
    coordinate: c(61.1744, -149.9964, 46),
    etaIso: '2026-02-03T15:45:00Z',
    distanceMeters: 1960000,
  },
  {
    id: 'poi-waypoint-idl',
    name: 'IDL Crossing',
    category: 'waypoint',
    coordinate: c(54.1, 179.7, 11278),
    etaIso: '2026-02-03T17:05:00Z',
    distanceMeters: 3110000,
  },
  {
    id: 'poi-waypoint-kamchatka',
    name: 'Kamchatka Track Fix',
    category: 'waypoint',
    coordinate: c(53.1, 160.2, 11278),
    etaIso: '2026-02-03T18:10:00Z',
    distanceMeters: 4420000,
  },
  {
    id: 'poi-waypoint-hokkaido',
    name: 'Hokkaido Track Fix',
    category: 'waypoint',
    coordinate: c(43.1, 144.3, 10973),
    etaIso: '2026-02-03T20:05:00Z',
    distanceMeters: 6620000,
  },
  {
    id: 'poi-arrive-rjtt',
    name: 'RJTT Arrival',
    category: 'arrival',
    coordinate: c(35.5494, 139.7798, 21),
    etaIso: '2026-02-03T21:35:00Z',
    distanceMeters: 7710000,
  },
] as const satisfies readonly Poi[];

const baseMetrics = metrics(
  [
    sample('2026-02-03T15:25:00Z', 60),
    sample('2026-02-03T15:27:30Z', 88),
    sample('2026-02-03T15:29:59Z', 74),
  ],
  [
    sample('2026-02-03T15:25:00Z', 0),
    sample('2026-02-03T15:27:30Z', 0.3),
    sample('2026-02-03T15:29:59Z', 0.3),
  ],
  192.4,
  24.6,
  1.2
);
const defaultFilter: PoiFilter = {
  value: 'departure,arrival',
  query: { category: 'departure,arrival' },
};
const allPoisFilter: PoiFilter = { value: '', query: {} };

const poiResponse = (
  generatedAt: string | null,
  filter: PoiFilter
): PoiResponse => {
  const categories =
    filter.value === ''
      ? null
      : new Set<PoiCategory>(filter.value.split(',') as PoiCategory[]);

  return {
    generatedAt,
    items:
      categories === null
        ? basePois
        : basePois.filter((poi) => categories.has(poi.category)),
  };
};

const sourceResponse = <T>(
  generatedAt: string | null,
  items: readonly T[]
): SourceResponse<T> => ({ generatedAt, items });

const radar = (
  frameAt: string | null,
  state: HealthState = 'ok',
  error?: string
): RadarSource => ({
  available: frameAt !== null,
  frameAt,
  state,
  ...(error === undefined ? {} : { error }),
});

const nominalHistory = [
  point('2026-02-03T15:29:57Z', c(52.22, -150.1, 10973), 471, 287),
  point('2026-02-03T15:29:59Z', c(52.44, -151.12, 10973), 472, 287),
] as const satisfies readonly TimestampedPosition[];

const satellites = [
  {
    id: 'sat-44713',
    name: 'STARLINK-1019',
    coordinate: c(53.2, -148.8, 550000),
  },
] as const;

const normalLinks = [
  {
    id: 'xband-normal-001',
    mode: 'normal',
    observedAt: '2026-02-03T15:29:59Z',
    from: c(52.44, -151.12, 10973),
    to: c(53.2, -148.8, 550000),
  },
  {
    id: 'xband-warning-standby',
    mode: 'warning',
    observedAt: '2026-02-03T15:29:59Z',
    from: c(52.44, -151.12, 10973),
    to: c(47.6062, -122.3321, 0),
  },
] as const satisfies readonly ActiveLink[];

const baseEvents = [
  {
    id: 'event-depart-ksea',
    observedAt: '2026-02-03T12:00:00Z',
    type: 'departure',
    label: 'Departed KSEA',
    coordinate: c(47.4502, -122.3088, 132),
  },
  {
    id: 'event-waypoint-alaska',
    observedAt: '2026-02-03T15:20:00Z',
    type: 'waypoint',
    label: 'Passed Alaska Track Fix',
    coordinate: c(55.2, -160.4, 11278),
  },
] as const satisfies readonly MissionEvent[];

const freshness = (values: SourceFreshness): SourceFreshness => ({
  telemetry: values.telemetry,
  history: values.history,
  activeLink: values.activeLink,
  pois: values.pois,
  route: values.route,
  groundEntryPoint: values.groundEntryPoint,
  radar: values.radar,
});

const clocksFor = (nowIso: string): readonly PanelState[] => {
  const clockValues: Record<string, readonly string[]> = {
    '2026-02-03T15:10:00Z': [
      '15:10:00Z',
      '10:10:00 EST',
      '00:10:00 JST',
      '09:10:00 CST',
    ],
    '2026-02-03T15:30:00Z': [
      '15:30:00Z',
      '10:30:00 EST',
      '00:30:00 JST',
      '09:30:00 CST',
    ],
    '2026-02-03T15:31:00Z': [
      '15:31:00Z',
      '10:31:00 EST',
      '00:31:00 JST',
      '09:31:00 CST',
    ],
    '2026-02-03T15:33:00Z': [
      '15:33:00Z',
      '10:33:00 EST',
      '00:33:00 JST',
      '09:33:00 CST',
    ],
    '2026-02-03T15:34:00Z': [
      '15:34:00Z',
      '10:34:00 EST',
      '00:34:00 JST',
      '09:34:00 CST',
    ],
    '2026-02-03T15:35:00Z': [
      '15:35:00Z',
      '10:35:00 EST',
      '00:35:00 JST',
      '09:35:00 CST',
    ],
    '2026-02-03T15:36:00Z': [
      '15:36:00Z',
      '10:36:00 EST',
      '00:36:00 JST',
      '09:36:00 CST',
    ],
    '2026-02-03T16:05:00Z': [
      '16:05:00Z',
      '11:05:00 EST',
      '01:05:00 JST',
      '10:05:00 CST',
    ],
    '2026-02-03T17:06:00Z': [
      '17:06:00Z',
      '12:06:00 EST',
      '02:06:00 JST',
      '11:06:00 CST',
    ],
  };
  const values = clockValues[nowIso];

  return [
    { id: 'clock-utc', state: 'ok', value: values[0] },
    { id: 'clock-washington-dc', state: 'ok', value: values[1] },
    { id: 'clock-tokyo', state: 'ok', value: values[2] },
    { id: 'clock-omaha', state: 'ok', value: values[3] },
  ];
};

const panelsFor = (
  nowIso: string,
  values: Readonly<{
    map: PanelState;
    poi: PanelState;
    latency: PanelState;
    throughput: PanelState;
    gep: PanelState;
    obstruction: PanelState;
    packetLoss: PanelState;
  }>
): readonly PanelState[] =>
  [
    ...clocksFor(nowIso),
    values.map,
    values.poi,
    values.latency,
    values.throughput,
    values.gep,
    values.obstruction,
    values.packetLoss,
  ] as const;

const layersFor = (
  values: Readonly<{
    radar: LayerState;
    routeWest: LayerState;
    routeEast: LayerState;
    linkNormal: LayerState;
    linkWarning: LayerState;
    historyWest: LayerState;
    historyEast: LayerState;
    markers: LayerState;
    satellite: LayerState;
    events: LayerState;
    gep: LayerState;
    current: LayerState;
  }>
): readonly LayerState[] =>
  [
    values.radar,
    values.routeWest,
    values.routeEast,
    values.linkNormal,
    values.linkWarning,
    values.historyWest,
    values.historyEast,
    values.markers,
    values.satellite,
    values.events,
    values.gep,
    values.current,
  ] as const;

const expected = (
  topFivePoiIds: readonly string[],
  panelStates: readonly PanelState[],
  sourceFreshness: SourceFreshness,
  layerStates: readonly LayerState[],
  route: Route,
  radarState: HealthState = 'ok',
  radarFrameState = 'available',
  routeState: HealthState = route.active ? 'ok' : 'unavailable'
): OverviewScenario['expected'] => ({
  topFivePoiIds,
  panelStates,
  sourceFreshness,
  layerStates,
  route: {
    state: routeState,
    westernPointCount: route.westernSegment.length,
    easternPointCount: route.easternSegment.length,
    crossesInternationalDateLine: route.crossesInternationalDateLine,
  },
  radar: { state: radarState, frameState: radarFrameState },
});

export const OVERVIEW_SCENARIOS = [
  {
    id: 'overview-nominal',
    name: 'nominal',
    nowIso: '2026-02-03T15:30:00Z',
    selectedPoiFilter: defaultFilter,
    telemetry: {
      currentObservedAt: '2026-02-03T15:29:59Z',
      currentPosition: c(52.44, -151.12, 10973),
      positionHistory: nominalHistory,
      metrics: baseMetrics,
    },
    route: routeAt('2026-02-03T15:30:00Z'),
    pois: poiResponse('2026-02-03T15:30:00Z', defaultFilter),
    groundEntryPoint: {
      id: 'gep-seattle-001',
      display: 'Seattle, WA',
      observedAt: '2026-02-03T15:30:00Z',
      coordinate: c(47.6062, -122.3321, 0),
    },
    radar: radar('2026-02-03T15:29:59Z'),
    satellites: sourceResponse('2026-02-03T15:30:00Z', satellites),
    activeLinks: normalLinks,
    missionEvents: sourceResponse('2026-02-03T15:30:00Z', baseEvents),
    expected: expected(
      ['poi-arrive-rjtt'],
      panelsFor('2026-02-03T15:30:00Z', {
        map: {
          id: 'current-position-map',
          state: 'ok',
          value: '52.4400, -151.1200 at 10,973 m',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'ok',
          value: '1 future departure/arrival POI',
        },
        latency: {
          id: 'network-latency',
          state: 'ok',
          value: '74 ms current / 60-74-88 ms five-minute',
        },
        throughput: {
          id: 'throughput',
          state: 'ok',
          value: '192.4 Mbps down / -24.6 Mbps up',
        },
        gep: {
          id: 'ground-entry-point',
          state: 'ok',
          value: 'Seattle, WA',
        },
        obstruction: { id: 'obstruction', state: 'ok', value: '1.2%' },
        packetLoss: {
          id: 'packet-loss',
          state: 'ok',
          value: '0.3% current / 0.2% avg / 0.3% max',
        },
      }),
      freshness({
        telemetry: '2026-02-03T15:29:59Z',
        history: '2026-02-03T15:29:59Z',
        activeLink: '2026-02-03T15:29:59Z',
        pois: '2026-02-03T15:30:00Z',
        route: '2026-02-03T15:30:00Z',
        groundEntryPoint: '2026-02-03T15:30:00Z',
        radar: '2026-02-03T15:29:59Z',
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'ok',
          availability: 'available',
          value: 'frame 2026-02-03T15:29:59Z',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'ok',
          availability: 'available',
          value: '3 western route points',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'ok',
          availability: 'available',
          value: '3 eastern route points',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'ok',
          availability: 'available',
          value: 'normal link observed 2026-02-03T15:29:59Z',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'warning',
          availability: 'available',
          value: 'warning link standby 2026-02-03T15:29:59Z',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'ok',
          availability: 'available',
          value: '2 western samples',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'ok',
          availability: 'empty',
          value: '0 eastern samples',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'ok',
          availability: 'available',
          value: '2 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'ok',
          availability: 'available',
          value: '1 satellite',
        },
        events: {
          id: 'mission-events',
          state: 'ok',
          availability: 'available',
          value: '2 mission events',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'ok',
          availability: 'available',
          value: 'Seattle, WA',
        },
        current: {
          id: 'current-position-layer',
          state: 'ok',
          availability: 'available',
          value: 'current position observed 2026-02-03T15:29:59Z',
        },
      }),
      routeAt('2026-02-03T15:30:00Z')
    ),
  },
  {
    id: 'overview-no-route',
    name: 'no-route',
    nowIso: '2026-02-03T15:31:00Z',
    selectedPoiFilter: defaultFilter,
    telemetry: {
      currentObservedAt: '2026-02-03T15:30:59Z',
      currentPosition: c(39.8617, -104.6731, 1656),
      positionHistory: [
        point('2026-02-03T15:30:59Z', c(39.8617, -104.6731, 1656), 0, 0),
      ],
      metrics: metrics(
        [
          sample('2026-02-03T15:30:55Z', 65),
          sample('2026-02-03T15:30:57Z', 74),
          sample('2026-02-03T15:30:59Z', 71),
        ],
        [sample('2026-02-03T15:30:59Z', 0.2)],
        188.1,
        22.8,
        0.8
      ),
    },
    route: inactiveRoute('route-none', 'No Active Route'),
    pois: { generatedAt: null, items: [] },
    groundEntryPoint: {
      id: 'gep-denver-001',
      display: 'Denver, CO',
      observedAt: '2026-02-03T15:31:00Z',
      coordinate: c(39.7392, -104.9903, 0),
    },
    radar: radar('2026-02-03T15:30:59Z'),
    satellites: sourceResponse(null, []),
    activeLinks: [
      {
        id: 'xband-normal-no-route',
        mode: 'normal',
        observedAt: '2026-02-03T15:30:59Z',
        from: c(39.8617, -104.6731, 1656),
        to: c(40.1, -103.9, 550000),
      },
    ],
    missionEvents: sourceResponse(null, []),
    expected: expected(
      [],
      panelsFor('2026-02-03T15:31:00Z', {
        map: {
          id: 'current-position-map',
          state: 'ok',
          value: '39.8617, -104.6731 at 1,656 m; no active route overlay',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'unavailable',
          value: 'No active route',
        },
        latency: {
          id: 'network-latency',
          state: 'ok',
          value: '71 ms current / 65-70-74 ms five-minute',
        },
        throughput: {
          id: 'throughput',
          state: 'ok',
          value: '188.1 Mbps down / -22.8 Mbps up',
        },
        gep: {
          id: 'ground-entry-point',
          state: 'ok',
          value: 'Denver, CO',
        },
        obstruction: { id: 'obstruction', state: 'ok', value: '0.8%' },
        packetLoss: {
          id: 'packet-loss',
          state: 'ok',
          value: '0.2% current / 0.2% avg / 0.2% max',
        },
      }),
      freshness({
        telemetry: '2026-02-03T15:30:59Z',
        history: '2026-02-03T15:30:59Z',
        activeLink: '2026-02-03T15:30:59Z',
        pois: null,
        route: null,
        groundEntryPoint: '2026-02-03T15:31:00Z',
        radar: '2026-02-03T15:30:59Z',
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'ok',
          availability: 'available',
          value: 'frame 2026-02-03T15:30:59Z',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'unavailable',
          availability: 'empty',
          value: 'no active route',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'unavailable',
          availability: 'empty',
          value: 'no active route',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'ok',
          availability: 'empty',
          value: '0 eastern samples',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'ok',
          availability: 'available',
          value: 'normal link observed 2026-02-03T15:30:59Z',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'ok',
          availability: 'empty',
          value: 'no warning link',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'ok',
          availability: 'available',
          value: '1 western sample',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'unavailable',
          availability: 'empty',
          value: '0 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'unavailable',
          availability: 'empty',
          value: '0 satellites',
        },
        events: {
          id: 'mission-events',
          state: 'unavailable',
          availability: 'empty',
          value: '0 mission events',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'ok',
          availability: 'available',
          value: 'Denver, CO',
        },
        current: {
          id: 'current-position-layer',
          state: 'ok',
          availability: 'available',
          value: 'current position observed 2026-02-03T15:30:59Z',
        },
      }),
      inactiveRoute('route-none', 'No Active Route')
    ),
  },
  {
    id: 'overview-sparse',
    name: 'sparse',
    nowIso: '2026-02-03T15:10:00Z',
    selectedPoiFilter: allPoisFilter,
    telemetry: {
      currentObservedAt: '2026-02-03T15:09:59Z',
      currentPosition: c(50.1, -135.2, 10668),
      positionHistory: [
        point('2026-02-03T15:09:59Z', c(50.1, -135.2, 10668), 466, 286),
      ],
      metrics: metrics(
        [sample('2026-02-03T15:09:59Z', 83)],
        [sample('2026-02-03T15:09:59Z', 0.4)],
        0,
        0,
        1.4
      ),
    },
    route: routeAt('2026-02-03T15:10:00Z'),
    pois: poiResponse('2026-02-03T15:10:00Z', allPoisFilter),
    groundEntryPoint: {
      id: 'gep-seattle-001',
      display: 'Seattle, WA',
      observedAt: '2026-02-03T15:10:00Z',
      coordinate: c(47.6062, -122.3321, 0),
    },
    radar: radar('2026-02-03T15:09:59Z'),
    satellites: sourceResponse('2026-02-03T15:10:00Z', []),
    activeLinks: [
      {
        id: 'xband-normal-sparse',
        mode: 'normal',
        observedAt: '2026-02-03T15:09:59Z',
        from: c(50.1, -135.2, 10668),
        to: c(50.4, -134.6, 550000),
      },
    ],
    missionEvents: sourceResponse('2026-02-03T15:10:00Z', [baseEvents[0]]),
    expected: expected(
      [
        'poi-waypoint-alaska',
        'poi-alternate-panc',
        'poi-waypoint-idl',
        'poi-waypoint-kamchatka',
        'poi-waypoint-hokkaido',
      ],
      panelsFor('2026-02-03T15:10:00Z', {
        map: {
          id: 'current-position-map',
          state: 'ok',
          value: '50.1000, -135.2000 at 10,668 m',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'ok',
          value: '5 future POIs',
        },
        latency: {
          id: 'network-latency',
          state: 'ok',
          value: '83 ms current / 83-83-83 ms five-minute',
        },
        throughput: {
          id: 'throughput',
          state: 'warning',
          value: '0 Mbps down / 0 Mbps up',
        },
        gep: {
          id: 'ground-entry-point',
          state: 'ok',
          value: 'Seattle, WA',
        },
        obstruction: { id: 'obstruction', state: 'ok', value: '1.4%' },
        packetLoss: {
          id: 'packet-loss',
          state: 'ok',
          value: '0.4% current / 0.4% avg / 0.4% max',
        },
      }),
      freshness({
        telemetry: '2026-02-03T15:09:59Z',
        history: '2026-02-03T15:09:59Z',
        activeLink: '2026-02-03T15:09:59Z',
        pois: '2026-02-03T15:10:00Z',
        route: '2026-02-03T15:10:00Z',
        groundEntryPoint: '2026-02-03T15:10:00Z',
        radar: '2026-02-03T15:09:59Z',
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'ok',
          availability: 'available',
          value: 'frame 2026-02-03T15:09:59Z',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'ok',
          availability: 'available',
          value: '3 western route points',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'ok',
          availability: 'available',
          value: '3 eastern route points',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'ok',
          availability: 'available',
          value: 'normal link observed 2026-02-03T15:09:59Z',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'ok',
          availability: 'empty',
          value: 'no warning link',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'ok',
          availability: 'available',
          value: '1 western sample',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'ok',
          availability: 'empty',
          value: '0 eastern samples',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'ok',
          availability: 'available',
          value: '7 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'unavailable',
          availability: 'empty',
          value: '0 satellites',
        },
        events: {
          id: 'mission-events',
          state: 'ok',
          availability: 'available',
          value: '1 mission event',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'ok',
          availability: 'available',
          value: 'Seattle, WA',
        },
        current: {
          id: 'current-position-layer',
          state: 'ok',
          availability: 'available',
          value: 'current position observed 2026-02-03T15:09:59Z',
        },
      }),
      routeAt('2026-02-03T15:10:00Z')
    ),
  },
  {
    id: 'overview-stale',
    name: 'stale',
    nowIso: '2026-02-03T16:05:00Z',
    selectedPoiFilter: defaultFilter,
    telemetry: {
      currentObservedAt: '2026-02-03T15:30:00Z',
      currentPosition: c(53, -162, 11278),
      positionHistory: [
        point('2026-02-03T15:29:30Z', c(52.9, -161.5, 11278), 469, 287),
        point('2026-02-03T15:30:00Z', c(53, -162, 11278), 469, 287),
      ],
      metrics: metrics(
        [
          sample('2026-02-03T15:29:30Z', 70),
          sample('2026-02-03T15:29:45Z', 85),
          sample('2026-02-03T15:30:00Z', 88),
        ],
        [
          sample('2026-02-03T15:29:30Z', 0.1),
          sample('2026-02-03T15:29:45Z', 0.4),
          sample('2026-02-03T15:30:00Z', 0.4),
        ],
        180.8,
        21.4,
        1.8
      ),
    },
    route: routeAt('2026-02-03T15:30:00Z'),
    pois: poiResponse('2026-02-03T15:30:00Z', defaultFilter),
    groundEntryPoint: {
      id: 'gep-seattle-001',
      display: 'Seattle, WA',
      observedAt: '2026-02-03T15:30:00Z',
      coordinate: c(47.6062, -122.3321, 0),
    },
    radar: radar('2026-02-03T15:30:00Z', 'stale'),
    satellites: sourceResponse('2026-02-03T15:30:00Z', satellites),
    activeLinks: [
      {
        id: 'xband-normal-stale',
        mode: 'normal',
        observedAt: '2026-02-03T15:30:00Z',
        from: c(53, -162, 11278),
        to: c(53.2, -148.8, 550000),
      },
    ],
    missionEvents: sourceResponse('2026-02-03T15:30:00Z', baseEvents),
    expected: expected(
      ['poi-arrive-rjtt'],
      panelsFor('2026-02-03T16:05:00Z', {
        map: {
          id: 'current-position-map',
          state: 'stale',
          value: '53.0000, -162.0000 at 11,278 m; 35m old',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'stale',
          value: '1 future departure/arrival POI',
        },
        latency: {
          id: 'network-latency',
          state: 'stale',
          value: '88 ms current / 70-81-88 ms five-minute',
        },
        throughput: {
          id: 'throughput',
          state: 'stale',
          value: '180.8 Mbps down / -21.4 Mbps up',
        },
        gep: {
          id: 'ground-entry-point',
          state: 'stale',
          value: 'Seattle, WA',
        },
        obstruction: { id: 'obstruction', state: 'stale', value: '1.8%' },
        packetLoss: {
          id: 'packet-loss',
          state: 'stale',
          value: '0.4% current / 0.3% avg / 0.4% max',
        },
      }),
      freshness({
        telemetry: '2026-02-03T15:30:00Z',
        history: '2026-02-03T15:30:00Z',
        activeLink: '2026-02-03T15:30:00Z',
        pois: '2026-02-03T15:30:00Z',
        route: '2026-02-03T15:30:00Z',
        groundEntryPoint: '2026-02-03T15:30:00Z',
        radar: '2026-02-03T15:30:00Z',
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'stale',
          availability: 'available',
          value: 'frame 2026-02-03T15:30:00Z',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'stale',
          availability: 'available',
          value: '3 western route points',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'stale',
          availability: 'available',
          value: '3 eastern route points',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'stale',
          availability: 'available',
          value: 'normal link observed 2026-02-03T15:30:00Z',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'stale',
          availability: 'empty',
          value: 'no warning link',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'stale',
          availability: 'available',
          value: '2 stale western samples',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'stale',
          availability: 'empty',
          value: '0 eastern samples',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'stale',
          availability: 'available',
          value: '2 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'stale',
          availability: 'available',
          value: '1 satellite',
        },
        events: {
          id: 'mission-events',
          state: 'stale',
          availability: 'available',
          value: '2 mission events',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'stale',
          availability: 'available',
          value: 'Seattle, WA',
        },
        current: {
          id: 'current-position-layer',
          state: 'stale',
          availability: 'available',
          value: 'current position observed 2026-02-03T15:30:00Z',
        },
      }),
      routeAt('2026-02-03T15:30:00Z'),
      'stale',
      'available',
      'stale'
    ),
  },
  {
    id: 'overview-backend-failure',
    name: 'backend failure',
    nowIso: '2026-02-03T15:33:00Z',
    selectedPoiFilter: defaultFilter,
    telemetry: {
      currentObservedAt: null,
      currentPosition: null,
      positionHistory: [],
      metrics: metrics([], [], null, null, null),
    },
    route: inactiveRoute(
      'route-transpacific-001',
      'Seattle to Tokyo Operational Route'
    ),
    pois: { generatedAt: null, items: [] },
    groundEntryPoint: {
      id: 'gep-unavailable',
      display: 'Unavailable',
      observedAt: null,
      coordinate: null,
    },
    radar: radar('2026-02-03T15:32:59Z'),
    satellites: sourceResponse(null, []),
    activeLinks: [
      {
        id: 'xband-unavailable',
        mode: 'unavailable',
        observedAt: null,
        from: null,
        to: null,
      },
    ],
    missionEvents: sourceResponse(null, []),
    expected: expected(
      [],
      panelsFor('2026-02-03T15:33:00Z', {
        map: {
          id: 'current-position-map',
          state: 'unavailable',
          value: 'No telemetry',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'unavailable',
          value: 'POIs unavailable',
        },
        latency: {
          id: 'network-latency',
          state: 'unavailable',
          value: 'No latency data',
        },
        throughput: {
          id: 'throughput',
          state: 'unavailable',
          value: 'No throughput data',
        },
        gep: {
          id: 'ground-entry-point',
          state: 'unavailable',
          value: 'Ground entry point unavailable',
        },
        obstruction: {
          id: 'obstruction',
          state: 'unavailable',
          value: 'No obstruction data',
        },
        packetLoss: {
          id: 'packet-loss',
          state: 'unavailable',
          value: 'No packet loss data',
        },
      }),
      freshness({
        telemetry: null,
        history: null,
        activeLink: null,
        pois: null,
        route: null,
        groundEntryPoint: null,
        radar: '2026-02-03T15:32:59Z',
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'ok',
          availability: 'available',
          value: 'frame 2026-02-03T15:32:59Z',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'unavailable',
          availability: 'unavailable',
          value: 'route unavailable',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'unavailable',
          availability: 'unavailable',
          value: 'route unavailable',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'unavailable',
          availability: 'unavailable',
          value: 'active link unavailable',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'unavailable',
          availability: 'empty',
          value: 'no warning link',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'unavailable',
          availability: 'unavailable',
          value: 'history unavailable',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'unavailable',
          availability: 'empty',
          value: '0 eastern samples',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'unavailable',
          availability: 'unavailable',
          value: '0 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'unavailable',
          availability: 'empty',
          value: '0 satellites',
        },
        events: {
          id: 'mission-events',
          state: 'unavailable',
          availability: 'unavailable',
          value: '0 mission events unavailable',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'unavailable',
          availability: 'unavailable',
          value: 'ground entry point unavailable',
        },
        current: {
          id: 'current-position-layer',
          state: 'unavailable',
          availability: 'unavailable',
          value: 'current position unavailable',
        },
      }),
      inactiveRoute(
        'route-transpacific-001',
        'Seattle to Tokyo Operational Route'
      )
    ),
  },
  {
    id: 'overview-radar-failure',
    name: 'radar failure',
    nowIso: '2026-02-03T15:34:00Z',
    selectedPoiFilter: defaultFilter,
    telemetry: {
      currentObservedAt: '2026-02-03T15:33:59Z',
      currentPosition: c(52.55, -152.1, 10973),
      positionHistory: [
        point('2026-02-03T15:33:57Z', c(52.4, -151.7, 10973), 471, 287),
        point('2026-02-03T15:33:59Z', c(52.55, -152.1, 10973), 472, 287),
      ],
      metrics: metrics(
        [
          sample('2026-02-03T15:33:55Z', 60),
          sample('2026-02-03T15:33:57Z', 88),
          sample('2026-02-03T15:33:59Z', 74),
        ],
        [
          sample('2026-02-03T15:33:55Z', 0),
          sample('2026-02-03T15:33:57Z', 0.3),
          sample('2026-02-03T15:33:59Z', 0.3),
        ],
        192.4,
        24.6,
        1.2
      ),
    },
    route: routeAt('2026-02-03T15:34:00Z'),
    pois: poiResponse('2026-02-03T15:34:00Z', defaultFilter),
    groundEntryPoint: {
      id: 'gep-seattle-001',
      display: 'Seattle, WA',
      observedAt: '2026-02-03T15:34:00Z',
      coordinate: c(47.6062, -122.3321, 0),
    },
    radar: radar(null, 'unavailable', 'radar tile failure'),
    satellites: sourceResponse('2026-02-03T15:34:00Z', satellites),
    activeLinks: [
      {
        id: 'xband-normal-radar-failure',
        mode: 'normal',
        observedAt: '2026-02-03T15:33:59Z',
        from: c(52.55, -152.1, 10973),
        to: c(53.2, -148.8, 550000),
      },
      {
        id: 'xband-warning-radar-standby',
        mode: 'warning',
        observedAt: '2026-02-03T15:33:59Z',
        from: c(52.55, -152.1, 10973),
        to: c(47.6062, -122.3321, 0),
      },
    ],
    missionEvents: sourceResponse('2026-02-03T15:34:00Z', baseEvents),
    expected: expected(
      ['poi-arrive-rjtt'],
      panelsFor('2026-02-03T15:34:00Z', {
        map: {
          id: 'current-position-map',
          state: 'warning',
          value: '52.5500, -152.1000 at 10,973 m; radar unavailable',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'ok',
          value: '1 future departure/arrival POI',
        },
        latency: {
          id: 'network-latency',
          state: 'ok',
          value: '74 ms current / 60-74-88 ms five-minute',
        },
        throughput: {
          id: 'throughput',
          state: 'ok',
          value: '192.4 Mbps down / -24.6 Mbps up',
        },
        gep: {
          id: 'ground-entry-point',
          state: 'ok',
          value: 'Seattle, WA',
        },
        obstruction: { id: 'obstruction', state: 'ok', value: '1.2%' },
        packetLoss: {
          id: 'packet-loss',
          state: 'ok',
          value: '0.3% current / 0.2% avg / 0.3% max',
        },
      }),
      freshness({
        telemetry: '2026-02-03T15:33:59Z',
        history: '2026-02-03T15:33:59Z',
        activeLink: '2026-02-03T15:33:59Z',
        pois: '2026-02-03T15:34:00Z',
        route: '2026-02-03T15:34:00Z',
        groundEntryPoint: '2026-02-03T15:34:00Z',
        radar: null,
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'unavailable',
          availability: 'local-failure',
          value: 'radar tile failure',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'ok',
          availability: 'available',
          value: '3 western route points',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'ok',
          availability: 'available',
          value: '3 eastern route points',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'ok',
          availability: 'available',
          value: 'normal link observed 2026-02-03T15:33:59Z',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'warning',
          availability: 'available',
          value: 'warning link standby 2026-02-03T15:33:59Z',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'ok',
          availability: 'available',
          value: '2 western samples',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'ok',
          availability: 'empty',
          value: '0 eastern samples',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'ok',
          availability: 'available',
          value: '2 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'ok',
          availability: 'available',
          value: '1 satellite',
        },
        events: {
          id: 'mission-events',
          state: 'ok',
          availability: 'available',
          value: '2 mission events',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'ok',
          availability: 'available',
          value: 'Seattle, WA',
        },
        current: {
          id: 'current-position-layer',
          state: 'ok',
          availability: 'available',
          value: 'current position observed 2026-02-03T15:33:59Z',
        },
      }),
      baseRoute,
      'unavailable',
      'local-failure'
    ),
  },
  {
    id: 'overview-idl',
    name: 'International Date Line (IDL)',
    nowIso: '2026-02-03T17:06:00Z',
    selectedPoiFilter: defaultFilter,
    telemetry: {
      currentObservedAt: '2026-02-03T17:05:59Z',
      currentPosition: c(54.05, -179.85, 11278),
      positionHistory: [
        point('2026-02-03T17:05:57Z', c(54.2, 179.85, 11278), 474, 273),
        point('2026-02-03T17:05:59Z', c(54.05, -179.85, 11278), 476, 273),
      ],
      positionHistorySplit: {
        westernSegment: [
          point('2026-02-03T17:05:57Z', c(54.2, 179.85, 11278), 474, 273),
          point('2026-02-03T17:05:58Z', c(54.125, 180, 11278), 475, 273),
        ],
        easternSegment: [
          point('2026-02-03T17:05:58Z', c(54.125, -180, 11278), 475, 273),
          point('2026-02-03T17:05:59Z', c(54.05, -179.85, 11278), 476, 273),
        ],
      },
      metrics: metrics(
        [
          sample('2026-02-03T17:05:55Z', 61),
          sample('2026-02-03T17:05:57Z', 82),
          sample('2026-02-03T17:05:59Z', 76),
        ],
        [
          sample('2026-02-03T17:05:55Z', 0),
          sample('2026-02-03T17:05:57Z', 0.3),
          sample('2026-02-03T17:05:59Z', 0.3),
        ],
        185.2,
        23.3,
        1.1
      ),
    },
    route: idlRoute,
    pois: poiResponse('2026-02-03T17:06:00Z', defaultFilter),
    groundEntryPoint: {
      id: 'gep-tokyo-001',
      display: 'Tokyo, JP',
      observedAt: '2026-02-03T17:06:00Z',
      coordinate: c(35.6762, 139.6503, 0),
    },
    radar: radar('2026-02-03T17:05:59Z'),
    satellites: sourceResponse('2026-02-03T17:06:00Z', satellites),
    activeLinks: [
      {
        id: 'xband-normal-idl',
        mode: 'normal',
        observedAt: '2026-02-03T17:05:59Z',
        from: c(54.05, -179.85, 11278),
        to: c(53.9, 179.9, 550000),
        splitGeometry: {
          westernSegment: [c(54.05, -179.85, 11278), c(53.96, -180, 334511.2)],
          easternSegment: [c(53.96, 180, 334511.2), c(53.9, 179.9, 550000)],
        },
      },
      {
        id: 'xband-warning-idl',
        mode: 'warning',
        observedAt: '2026-02-03T17:05:59Z',
        from: c(54.2, 179.85, 11278),
        to: c(54.05, -179.85, 11278),
        splitGeometry: {
          westernSegment: [c(54.2, 179.85, 11278), c(54.125, 180, 11278)],
          easternSegment: [c(54.125, -180, 11278), c(54.05, -179.85, 11278)],
        },
      },
    ],
    missionEvents: sourceResponse('2026-02-03T17:06:00Z', [
      ...baseEvents,
      {
        id: 'event-idl-crossed',
        observedAt: '2026-02-03T17:05:58Z',
        type: 'waypoint',
        label: 'Crossed International Date Line',
        coordinate: c(54.125, 180, 11278),
      },
    ]),
    expected: expected(
      ['poi-arrive-rjtt'],
      panelsFor('2026-02-03T17:06:00Z', {
        map: {
          id: 'current-position-map',
          state: 'ok',
          value: '54.0500, -179.8500 at 11,278 m; IDL split route',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'ok',
          value: '1 future departure/arrival POI',
        },
        latency: {
          id: 'network-latency',
          state: 'ok',
          value: '76 ms current / 61-73-82 ms five-minute',
        },
        throughput: {
          id: 'throughput',
          state: 'ok',
          value: '185.2 Mbps down / -23.3 Mbps up',
        },
        gep: { id: 'ground-entry-point', state: 'ok', value: 'Tokyo, JP' },
        obstruction: { id: 'obstruction', state: 'ok', value: '1.1%' },
        packetLoss: {
          id: 'packet-loss',
          state: 'ok',
          value: '0.3% current / 0.2% avg / 0.3% max',
        },
      }),
      freshness({
        telemetry: '2026-02-03T17:05:59Z',
        history: '2026-02-03T17:05:59Z',
        activeLink: '2026-02-03T17:05:59Z',
        pois: '2026-02-03T17:06:00Z',
        route: '2026-02-03T17:05:59Z',
        groundEntryPoint: '2026-02-03T17:06:00Z',
        radar: '2026-02-03T17:05:59Z',
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'ok',
          availability: 'available',
          value: 'frame 2026-02-03T17:05:59Z',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'ok',
          availability: 'available',
          value: '3 western IDL points',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'ok',
          availability: 'available',
          value: '4 eastern IDL points',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'ok',
          availability: 'available',
          value: 'normal IDL link observed 2026-02-03T17:05:59Z',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'warning',
          availability: 'available',
          value: 'warning IDL link observed 2026-02-03T17:05:59Z',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'ok',
          availability: 'available',
          value: '2 western IDL points',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'ok',
          availability: 'available',
          value: '2 eastern IDL points',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'ok',
          availability: 'available',
          value: '2 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'ok',
          availability: 'available',
          value: '1 satellite',
        },
        events: {
          id: 'mission-events',
          state: 'ok',
          availability: 'available',
          value: '3 mission events',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'ok',
          availability: 'available',
          value: 'Tokyo, JP',
        },
        current: {
          id: 'current-position-layer',
          state: 'ok',
          availability: 'available',
          value: 'current position observed 2026-02-03T17:05:59Z',
        },
      }),
      idlRoute
    ),
  },
  {
    id: 'overview-threshold-crossing',
    name: 'threshold crossing',
    nowIso: '2026-02-03T15:35:00Z',
    selectedPoiFilter: defaultFilter,
    telemetry: {
      currentObservedAt: '2026-02-03T15:34:59Z',
      currentPosition: c(52.8, -154.4, 11278),
      positionHistory: [
        point('2026-02-03T15:34:58Z', c(52.6, -153.6, 11278), 468, 287),
        point('2026-02-03T15:34:59Z', c(52.8, -154.4, 11278), 468, 287),
      ],
      metrics: metrics(
        [
          sample('2026-02-03T15:34:55Z', 150),
          sample('2026-02-03T15:34:57Z', 188),
          sample('2026-02-03T15:34:59Z', 205),
        ],
        [
          sample('2026-02-03T15:34:55Z', 1),
          sample('2026-02-03T15:34:57Z', 3.2),
          sample('2026-02-03T15:34:59Z', 5.4),
        ],
        177.7,
        20.1,
        10.5
      ),
    },
    route: routeAt('2026-02-03T15:35:00Z'),
    pois: poiResponse('2026-02-03T15:35:00Z', defaultFilter),
    groundEntryPoint: {
      id: 'gep-seattle-001',
      display: 'Seattle, WA',
      observedAt: '2026-02-03T15:35:00Z',
      coordinate: c(47.6062, -122.3321, 0),
    },
    radar: radar('2026-02-03T15:34:59Z'),
    satellites: sourceResponse('2026-02-03T15:35:00Z', satellites),
    activeLinks: [
      {
        id: 'xband-normal-threshold',
        mode: 'normal',
        observedAt: '2026-02-03T15:34:59Z',
        from: c(52.8, -154.4, 11278),
        to: c(53.2, -148.8, 550000),
      },
      {
        id: 'xband-warning-threshold',
        mode: 'warning',
        observedAt: '2026-02-03T15:34:59Z',
        from: c(52.8, -154.4, 11278),
        to: c(47.6062, -122.3321, 0),
      },
    ],
    missionEvents: sourceResponse('2026-02-03T15:35:00Z', baseEvents),
    expected: expected(
      ['poi-arrive-rjtt'],
      panelsFor('2026-02-03T15:35:00Z', {
        map: {
          id: 'current-position-map',
          state: 'ok',
          value: '52.8000, -154.4000 at 11,278 m',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'ok',
          value: '1 future departure/arrival POI',
        },
        latency: {
          id: 'network-latency',
          state: 'critical',
          value: '205 ms current / 150-181-205 ms five-minute',
        },
        obstruction: { id: 'obstruction', state: 'critical', value: '10.5%' },
        throughput: {
          id: 'throughput',
          state: 'ok',
          value: '177.7 Mbps down / -20.1 Mbps up',
        },
        gep: {
          id: 'ground-entry-point',
          state: 'ok',
          value: 'Seattle, WA',
        },
        packetLoss: {
          id: 'packet-loss',
          state: 'critical',
          value: '5.4% current / 3.2% avg / 5.4% max',
        },
      }),
      freshness({
        telemetry: '2026-02-03T15:34:59Z',
        history: '2026-02-03T15:34:59Z',
        activeLink: '2026-02-03T15:34:59Z',
        pois: '2026-02-03T15:35:00Z',
        route: '2026-02-03T15:35:00Z',
        groundEntryPoint: '2026-02-03T15:35:00Z',
        radar: '2026-02-03T15:34:59Z',
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'ok',
          availability: 'available',
          value: 'frame 2026-02-03T15:34:59Z',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'ok',
          availability: 'available',
          value: '3 western route points',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'ok',
          availability: 'available',
          value: '3 eastern route points',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'ok',
          availability: 'available',
          value: 'normal link observed 2026-02-03T15:34:59Z',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'critical',
          availability: 'available',
          value: 'warning link active 2026-02-03T15:34:59Z',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'ok',
          availability: 'available',
          value: '2 western samples',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'ok',
          availability: 'empty',
          value: '0 eastern samples',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'ok',
          availability: 'available',
          value: '2 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'ok',
          availability: 'available',
          value: '1 satellite',
        },
        events: {
          id: 'mission-events',
          state: 'ok',
          availability: 'available',
          value: '2 mission events',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'ok',
          availability: 'available',
          value: 'Seattle, WA',
        },
        current: {
          id: 'current-position-layer',
          state: 'ok',
          availability: 'available',
          value: 'current position observed 2026-02-03T15:34:59Z',
        },
      }),
      baseRoute
    ),
  },
  {
    id: 'overview-recovery',
    name: 'recovery',
    nowIso: '2026-02-03T15:36:00Z',
    selectedPoiFilter: defaultFilter,
    telemetry: {
      currentObservedAt: '2026-02-03T15:35:59Z',
      currentPosition: c(53.1, -155.1, 11278),
      positionHistory: [
        point('2026-02-03T15:35:57Z', c(52.8, -154.4, 11278), 469, 287),
        point('2026-02-03T15:35:58Z', c(52.95, -154.75, 11278), 470, 287),
        point('2026-02-03T15:35:59Z', c(53.1, -155.1, 11278), 471, 287),
      ],
      metrics: metrics(
        [
          sample('2026-02-03T15:35:55Z', 82),
          sample('2026-02-03T15:35:57Z', 92),
          sample('2026-02-03T15:35:59Z', 99),
        ],
        [
          sample('2026-02-03T15:35:55Z', 0.1),
          sample('2026-02-03T15:35:57Z', 1.9),
          sample('2026-02-03T15:35:59Z', 1.9),
        ],
        201.5,
        25.4,
        4.9
      ),
    },
    route: routeAt('2026-02-03T15:36:00Z'),
    pois: poiResponse('2026-02-03T15:36:00Z', defaultFilter),
    groundEntryPoint: {
      id: 'gep-seattle-001',
      display: 'Seattle, WA',
      observedAt: '2026-02-03T15:36:00Z',
      coordinate: c(47.6062, -122.3321, 0),
    },
    radar: radar('2026-02-03T15:35:59Z'),
    satellites: sourceResponse('2026-02-03T15:36:00Z', [
      {
        id: 'sat-44714',
        name: 'STARLINK-1020',
        coordinate: c(52.7, -156, 550000),
      },
    ]),
    activeLinks: [
      {
        id: 'xband-normal-recovery',
        mode: 'normal',
        observedAt: '2026-02-03T15:35:59Z',
        from: c(53.1, -155.1, 11278),
        to: c(52.7, -156, 550000),
      },
    ],
    missionEvents: sourceResponse('2026-02-03T15:36:00Z', [
      ...baseEvents,
      {
        id: 'event-network-recovered',
        observedAt: '2026-02-03T15:35:59Z',
        type: 'system',
        label: 'Network metrics recovered',
        coordinate: c(53.1, -155.1, 11278),
      },
    ]),
    expected: expected(
      ['poi-arrive-rjtt'],
      panelsFor('2026-02-03T15:36:00Z', {
        map: {
          id: 'current-position-map',
          state: 'ok',
          value: '53.1000, -155.1000 at 11,278 m',
        },
        poi: {
          id: 'poi-quick-reference',
          state: 'ok',
          value: '1 future departure/arrival POI',
        },
        latency: {
          id: 'network-latency',
          state: 'ok',
          value: '99 ms current / 82-91-99 ms five-minute',
        },
        obstruction: { id: 'obstruction', state: 'ok', value: '4.9%' },
        throughput: {
          id: 'throughput',
          state: 'ok',
          value: '201.5 Mbps down / -25.4 Mbps up',
        },
        gep: {
          id: 'ground-entry-point',
          state: 'ok',
          value: 'Seattle, WA',
        },
        packetLoss: {
          id: 'packet-loss',
          state: 'ok',
          value: '1.9% current / 1.3% avg / 1.9% max',
        },
      }),
      freshness({
        telemetry: '2026-02-03T15:35:59Z',
        history: '2026-02-03T15:35:59Z',
        activeLink: '2026-02-03T15:35:59Z',
        pois: '2026-02-03T15:36:00Z',
        route: '2026-02-03T15:36:00Z',
        groundEntryPoint: '2026-02-03T15:36:00Z',
        radar: '2026-02-03T15:35:59Z',
      }),
      layersFor({
        radar: {
          id: 'weather-radar',
          state: 'ok',
          availability: 'available',
          value: 'frame 2026-02-03T15:35:59Z',
        },
        routeWest: {
          id: 'planned-route-west',
          state: 'ok',
          availability: 'available',
          value: '3 western route points',
        },
        routeEast: {
          id: 'planned-route-east',
          state: 'ok',
          availability: 'available',
          value: '3 eastern route points',
        },
        linkNormal: {
          id: 'active-x-band-normal',
          state: 'ok',
          availability: 'available',
          value: 'normal link observed 2026-02-03T15:35:59Z',
        },
        linkWarning: {
          id: 'active-x-band-warning',
          state: 'ok',
          availability: 'empty',
          value: 'no warning link',
        },
        historyWest: {
          id: 'position-history-west',
          state: 'ok',
          availability: 'available',
          value: '3 western samples',
        },
        historyEast: {
          id: 'position-history-east',
          state: 'ok',
          availability: 'empty',
          value: '0 eastern samples',
        },
        markers: {
          id: 'flight-route-markers',
          state: 'ok',
          availability: 'available',
          value: '2 POI markers',
        },
        satellite: {
          id: 'satellites',
          state: 'ok',
          availability: 'available',
          value: '1 satellite',
        },
        events: {
          id: 'mission-events',
          state: 'ok',
          availability: 'available',
          value: '3 mission events',
        },
        gep: {
          id: 'ground-entry-point-layer',
          state: 'ok',
          availability: 'available',
          value: 'Seattle, WA',
        },
        current: {
          id: 'current-position-layer',
          state: 'ok',
          availability: 'available',
          value: 'current position observed 2026-02-03T15:35:59Z',
        },
      }),
      baseRoute
    ),
  },
] as const satisfies readonly OverviewScenario[];

export const buildPoiQuery = (
  value: string
): Readonly<{ category?: string }> => (value === '' ? {} : { category: value });
