type Timezone = 'UTC' | 'America/New_York' | 'Asia/Tokyo' | 'America/Chicago';
type PoiCategory = 'departure' | 'arrival' | 'waypoint' | 'alternate';
type HealthState = 'ok' | 'warning' | 'critical' | 'stale' | 'unavailable';

type Coordinate = Readonly<{
  latitude: number;
  longitude: number;
  altitudeMeters: number;
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

type Metrics = Readonly<{
  latencyMs: number | null;
  downloadMbps: number | null;
  uploadMbps: number | null;
  obstructionPercent: number | null;
  packetLossPercent: number | null;
  headingDegrees: number | null;
  speedKnots: number | null;
}>;
type Route = Readonly<{
  id: string;
  name: string;
  active: boolean;
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
type PoiTuple = readonly [
  id: string,
  name: string,
  category: PoiCategory,
  coordinate: Coordinate,
  etaIso: string,
  distanceMeters: number,
];

export type OverviewScenario = Readonly<{
  id: string;
  name: string;
  nowIso: string;
  telemetry: Readonly<{
    currentPosition: Coordinate | null;
    positionHistory: readonly Coordinate[];
    metrics: Metrics;
  }>;
  route: Route;
  pois: readonly Poi[];
  groundEntryPoint: Readonly<{
    id: string;
    display: string;
    coordinate: Coordinate | null;
  }>;
  satellites: readonly Readonly<{
    id: string;
    name: string;
    coordinate: Coordinate;
  }>[];
  expected: Readonly<{
    topFivePoiIds: readonly string[];
    panelStates: readonly Readonly<{
      panelId: string;
      state: HealthState;
      value: string;
    }>[];
    sourceFreshness: Readonly<Record<string, string | null>>;
    activeLayerIds: readonly string[];
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
      plannedRoute: { color: 'dark-orange', width: 2, opacity: 0.9 },
      activeXBandLinkNormal: { color: 'green', width: 4 },
      activeXBandLinkWarning: { color: 'yellow', width: 4 },
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
const baseRoute: Route = {
  id: 'route-transpacific-001',
  name: 'Seattle to Tokyo Operational Route',
  active: true,
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
const basePoiTuples = [
  [
    'poi-depart-ksea',
    'KSEA Departure',
    'departure',
    c(47.4502, -122.3088, 132),
    '2026-02-03T12:00:00Z',
    0,
  ],
  [
    'poi-waypoint-alaska',
    'Alaska Track Fix',
    'waypoint',
    c(55.2, -160.4, 11278),
    '2026-02-03T15:20:00Z',
    1820000,
  ],
  [
    'poi-alternate-panc',
    'PANC Alternate',
    'alternate',
    c(61.1744, -149.9964, 46),
    '2026-02-03T15:45:00Z',
    1960000,
  ],
  [
    'poi-waypoint-idl',
    'IDL Crossing',
    'waypoint',
    c(54.1, 179.7, 11278),
    '2026-02-03T17:05:00Z',
    3110000,
  ],
  [
    'poi-arrive-rjtt',
    'RJTT Arrival',
    'arrival',
    c(35.5494, 139.7798, 21),
    '2026-02-03T21:35:00Z',
    7710000,
  ],
] as const satisfies readonly PoiTuple[];
const basePois: readonly Poi[] = basePoiTuples.map(
  ([id, name, category, coordinate, etaIso, distanceMeters]) => ({
    id,
    name,
    category,
    coordinate,
    etaIso,
    distanceMeters,
  })
);
const baseMetrics: Metrics = {
  latencyMs: 74,
  downloadMbps: 192.4,
  uploadMbps: 24.6,
  obstructionPercent: 1.2,
  packetLossPercent: 0.3,
  headingDegrees: 287,
  speedKnots: 472,
};
const activeLayerIds = mapLayers.map((layer) => layer.id);
const poiIds = (pois: readonly Poi[]) => pois.map((poi) => poi.id);
const fresh = (iso: string | null, overrides = {}) => ({
  telemetry: iso,
  route: iso,
  pois: iso,
  radar: iso,
  satellites: iso,
  groundEntryPoint: iso,
  ...overrides,
});
const states = (state: HealthState, values: Record<string, string> = {}) =>
  panels.map(({ id }) => ({
    panelId: id,
    state,
    value: values[id] ?? 'ready',
  }));

const scenario = (
  name: OverviewScenario['name'],
  id: OverviewScenario['id'],
  nowIso: string,
  overrides: Partial<OverviewScenario> = {}
): OverviewScenario => {
  const pois = overrides.pois ?? basePois;
  return {
    id,
    name,
    nowIso,
    telemetry: {
      currentPosition: c(52.44, -151.12, 10973),
      positionHistory: [c(52.22, -150.1, 10973), c(52.44, -151.12, 10973)],
      metrics: baseMetrics,
    },
    route: baseRoute,
    pois,
    groundEntryPoint: {
      id: 'gep-seattle-001',
      display: 'Seattle, WA',
      coordinate: c(47.6062, -122.3321, 0),
    },
    satellites: [
      {
        id: 'sat-44713',
        name: 'STARLINK-1019',
        coordinate: c(53.2, -148.8, 550000),
      },
    ],
    expected: {
      topFivePoiIds: poiIds(pois),
      panelStates: states('ok', {
        'network-latency': '74 ms',
        throughput: '192.4 Mbps down / -24.6 Mbps up',
        obstruction: '1.2%',
        'packet-loss': '0.3%',
      }),
      sourceFreshness: fresh('2026-02-03T15:29:59Z'),
      activeLayerIds,
    },
    ...overrides,
  };
};

export const OVERVIEW_SCENARIOS = [
  scenario('nominal', 'overview-nominal', '2026-02-03T15:30:00Z'),
  scenario('no-route', 'overview-no-route', '2026-02-03T15:31:00Z', {
    telemetry: {
      currentPosition: c(39.8617, -104.6731, 1656),
      positionHistory: [],
      metrics: { ...baseMetrics, speedKnots: 0 },
    },
    route: {
      ...baseRoute,
      id: 'route-none',
      name: 'No Active Route',
      active: false,
    },
    pois: [],
    satellites: [],
    expected: {
      topFivePoiIds: [],
      panelStates: states('ok', { 'poi-quick-reference': 'No future POIs' }),
      sourceFreshness: fresh('2026-02-03T15:30:59Z', {
        route: null,
        pois: null,
      }),
      activeLayerIds: activeLayerIds.filter(
        (id) => !id.startsWith('planned-route')
      ),
    },
  }),
  scenario('sparse', 'overview-sparse', '2026-02-03T15:32:00Z', {
    telemetry: {
      currentPosition: c(50.1, -135.2, 10668),
      positionHistory: [c(50.1, -135.2, 10668)],
      metrics: { ...baseMetrics, downloadMbps: 0, uploadMbps: 0 },
    },
    pois: basePois.slice(0, 2),
    satellites: [],
    expected: {
      topFivePoiIds: poiIds(basePois.slice(0, 2)),
      panelStates: states('ok', { throughput: '0 Mbps down / 0 Mbps up' }),
      sourceFreshness: fresh('2026-02-03T15:31:59Z'),
      activeLayerIds: activeLayerIds.filter((id) => id !== 'satellites'),
    },
  }),
  scenario('stale', 'overview-stale', '2026-02-03T16:05:00Z', {
    telemetry: {
      currentPosition: c(53, -162, 11278),
      positionHistory: [c(52.9, -161.5, 11278), c(53, -162, 11278)],
      metrics: { ...baseMetrics, latencyMs: 88 },
    },
    expected: {
      topFivePoiIds: poiIds(basePois),
      panelStates: states('stale', { 'current-position-map': '35m old' }),
      sourceFreshness: fresh('2026-02-03T15:30:00Z'),
      activeLayerIds,
    },
  }),
  scenario(
    'backend failure',
    'overview-backend-failure',
    '2026-02-03T15:33:00Z',
    {
      telemetry: {
        currentPosition: null,
        positionHistory: [],
        metrics: {
          latencyMs: null,
          downloadMbps: null,
          uploadMbps: null,
          obstructionPercent: null,
          packetLossPercent: null,
          headingDegrees: null,
          speedKnots: null,
        },
      },
      route: { ...baseRoute, active: false },
      pois: [],
      groundEntryPoint: {
        id: 'gep-unavailable',
        display: 'Unavailable',
        coordinate: null,
      },
      satellites: [],
      expected: {
        topFivePoiIds: [],
        panelStates: states('unavailable', {
          'current-position-map': 'No data',
        }),
        sourceFreshness: fresh(null),
        activeLayerIds: [],
      },
    }
  ),
  scenario('radar failure', 'overview-radar-failure', '2026-02-03T15:34:00Z', {
    expected: {
      topFivePoiIds: poiIds(basePois),
      panelStates: states('warning', {
        'current-position-map': 'Radar unavailable',
      }),
      sourceFreshness: fresh('2026-02-03T15:33:59Z', { radar: null }),
      activeLayerIds: activeLayerIds.filter((id) => id !== 'weather-radar'),
    },
  }),
  scenario(
    'International Date Line (IDL)',
    'overview-idl',
    '2026-02-03T17:06:00Z',
    {
      telemetry: {
        currentPosition: c(54.05, -179.85, 11278),
        positionHistory: [c(54.2, 179.4, 11278), c(54.05, -179.85, 11278)],
        metrics: { ...baseMetrics, headingDegrees: 273 },
      },
      route: { ...baseRoute, crossesInternationalDateLine: true },
      pois: basePois.slice(3),
      expected: {
        topFivePoiIds: poiIds(basePois.slice(3)),
        panelStates: states('ok', {
          'current-position-map': 'IDL split route',
        }),
        sourceFreshness: fresh('2026-02-03T17:05:59Z'),
        activeLayerIds,
      },
    }
  ),
  scenario(
    'threshold crossing',
    'overview-threshold-crossing',
    '2026-02-03T15:35:00Z',
    {
      telemetry: {
        currentPosition: c(52.8, -154.4, 11278),
        positionHistory: [c(52.6, -153.6, 11278), c(52.8, -154.4, 11278)],
        metrics: {
          ...baseMetrics,
          latencyMs: 205,
          obstructionPercent: 10.5,
          packetLossPercent: 5.4,
        },
      },
      expected: {
        topFivePoiIds: poiIds(basePois),
        panelStates: states('critical', {
          'network-latency': '205 ms',
          obstruction: '10.5%',
          'packet-loss': '5.4%',
        }),
        sourceFreshness: fresh('2026-02-03T15:34:59Z'),
        activeLayerIds,
      },
    }
  ),
  scenario('recovery', 'overview-recovery', '2026-02-03T15:36:00Z', {
    telemetry: {
      currentPosition: c(53.1, -155.1, 11278),
      positionHistory: [
        c(52.8, -154.4, 11278),
        c(52.95, -154.75, 11278),
        c(53.1, -155.1, 11278),
      ],
      metrics: {
        ...baseMetrics,
        latencyMs: 99,
        obstructionPercent: 4.9,
        packetLossPercent: 1.9,
      },
    },
    satellites: [
      {
        id: 'sat-44714',
        name: 'STARLINK-1020',
        coordinate: c(52.7, -156, 550000),
      },
    ],
    expected: {
      topFivePoiIds: poiIds(basePois),
      panelStates: states('ok', {
        'network-latency': '99 ms',
        obstruction: '4.9%',
        'packet-loss': '1.9%',
      }),
      sourceFreshness: fresh('2026-02-03T15:35:59Z'),
      activeLayerIds,
    },
  }),
] as const satisfies readonly OverviewScenario[];

export const buildPoiQuery = (
  value: string
): Readonly<{ category?: string }> => (value === '' ? {} : { category: value });
