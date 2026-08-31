// @ts-expect-error -- test source reads require Node APIs outside app types.
import { createHash } from 'node:crypto';
// @ts-expect-error -- test source reads require Node APIs outside app types.
import { readFileSync } from 'node:fs';
// @ts-expect-error -- test source reads require Node APIs outside app types.
import { resolve } from 'node:path';
// @ts-expect-error -- test source reads require Node APIs outside app types.
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  OVERVIEW_CONTRACT,
  OVERVIEW_SCENARIOS,
  type OverviewScenario,
  buildPoiQuery,
} from '../../../tests/e2e/fixtures/overview';

const fixtureSourceUrl = new URL(
  '../../../tests/e2e/fixtures/overview.ts',
  import.meta.url
);
const FIXTURE_SOURCE_PATH =
  fixtureSourceUrl.protocol === 'file:'
    ? fileURLToPath(fixtureSourceUrl)
    : resolve('tests/e2e/fixtures/overview.ts');

const EXPECTED_SCENARIOS = [
  'nominal',
  'no-route',
  'sparse',
  'stale',
  'backend failure',
  'radar failure',
  'International Date Line (IDL)',
  'threshold crossing',
  'recovery',
];

const EXPECTED_SCENARIO_IDS = [
  'overview-nominal',
  'overview-no-route',
  'overview-sparse',
  'overview-stale',
  'overview-backend-failure',
  'overview-radar-failure',
  'overview-idl',
  'overview-threshold-crossing',
  'overview-recovery',
];

const PANEL_IDS = OVERVIEW_CONTRACT.panels.map((panel) => panel.id);
const LAYER_IDS = OVERVIEW_CONTRACT.mapLayers.map((layer) => layer.id);
const EXPECTED_LAYER_INVENTORY = [
  {
    concept: 'Weather Radar',
    id: 'weather-radar',
    source: 'RainViewer',
    enabledByDefault: true,
  },
  {
    concept: 'Planned Route — western segment',
    id: 'planned-route-west',
    source: 'active-route',
    enabledByDefault: true,
  },
  {
    concept: 'Planned Route — eastern segment',
    id: 'planned-route-east',
    source: 'active-route',
    enabledByDefault: true,
  },
  {
    concept: 'Active X-band Link — normal',
    id: 'active-x-band-normal',
    source: 'satellite-link',
    enabledByDefault: true,
  },
  {
    concept: 'Active X-band Link — warning',
    id: 'active-x-band-warning',
    source: 'satellite-link',
    enabledByDefault: true,
  },
  {
    concept: 'Position History — western segments',
    id: 'position-history-west',
    source: 'telemetry-history',
    enabledByDefault: true,
  },
  {
    concept: 'Position History — eastern segments',
    id: 'position-history-east',
    source: 'telemetry-history',
    enabledByDefault: true,
  },
  {
    concept: 'Flight route/POI markers',
    id: 'flight-route-markers',
    source: 'route-pois',
    enabledByDefault: true,
  },
  {
    concept: 'Satellites',
    id: 'satellites',
    source: 'satellite-positions',
    enabledByDefault: true,
  },
  {
    concept: 'Mission events',
    id: 'mission-events',
    source: 'mission-events',
    enabledByDefault: true,
  },
  {
    concept: 'Ground entry point',
    id: 'ground-entry-point-layer',
    source: 'ground-entry-point',
    enabledByDefault: true,
  },
  {
    concept: 'Current position',
    id: 'current-position-layer',
    source: 'telemetry',
    enabledByDefault: true,
  },
];
const FRESHNESS_KEYS = [
  'telemetry',
  'history',
  'activeLink',
  'pois',
  'route',
  'groundEntryPoint',
  'radar',
];
const ISO_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

const byId = <T extends { id: string }>(items: readonly T[], id: string): T => {
  const item = items.find((candidate) => candidate.id === id);

  expect(item).toBeDefined();
  return item as T;
};

type Scenario = OverviewScenario;
type PanelState = Scenario['expected']['panelStates'][number];
type LayerState = Scenario['expected']['layerStates'][number];
type Poi = Scenario['pois']['items'][number];
type Satellite = Scenario['satellites']['items'][number];
type MissionEvent = Scenario['missionEvents']['items'][number];
type PositionSample = Scenario['telemetry']['positionHistory'][number];
type ActiveLink = Scenario['activeLinks'][number];
type Coordinate = Scenario['route']['westernSegment'][number];
type NumericSample =
  Scenario['telemetry']['metrics']['latency']['history'][number];
const EXPECTED_PANEL_STATE_MAPS = {
  'overview-nominal': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'ok',
    'poi-quick-reference': 'ok',
    'network-latency': 'ok',
    throughput: 'ok',
    'ground-entry-point': 'ok',
    obstruction: 'ok',
    'packet-loss': 'ok',
  },
  'overview-no-route': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'ok',
    'poi-quick-reference': 'unavailable',
    'network-latency': 'ok',
    throughput: 'ok',
    'ground-entry-point': 'ok',
    obstruction: 'ok',
    'packet-loss': 'ok',
  },
  'overview-sparse': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'ok',
    'poi-quick-reference': 'ok',
    'network-latency': 'ok',
    throughput: 'warning',
    'ground-entry-point': 'ok',
    obstruction: 'ok',
    'packet-loss': 'ok',
  },
  'overview-stale': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'stale',
    'poi-quick-reference': 'stale',
    'network-latency': 'stale',
    throughput: 'stale',
    'ground-entry-point': 'stale',
    obstruction: 'stale',
    'packet-loss': 'stale',
  },
  'overview-backend-failure': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'unavailable',
    'poi-quick-reference': 'unavailable',
    'network-latency': 'unavailable',
    throughput: 'unavailable',
    'ground-entry-point': 'unavailable',
    obstruction: 'unavailable',
    'packet-loss': 'unavailable',
  },
  'overview-radar-failure': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'warning',
    'poi-quick-reference': 'ok',
    'network-latency': 'ok',
    throughput: 'ok',
    'ground-entry-point': 'ok',
    obstruction: 'ok',
    'packet-loss': 'ok',
  },
  'overview-idl': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'ok',
    'poi-quick-reference': 'ok',
    'network-latency': 'ok',
    throughput: 'ok',
    'ground-entry-point': 'ok',
    obstruction: 'ok',
    'packet-loss': 'ok',
  },
  'overview-threshold-crossing': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'ok',
    'poi-quick-reference': 'ok',
    'network-latency': 'critical',
    throughput: 'ok',
    'ground-entry-point': 'ok',
    obstruction: 'critical',
    'packet-loss': 'critical',
  },
  'overview-recovery': {
    'clock-utc': 'ok',
    'clock-washington-dc': 'ok',
    'clock-tokyo': 'ok',
    'clock-omaha': 'ok',
    'current-position-map': 'ok',
    'poi-quick-reference': 'ok',
    'network-latency': 'ok',
    throughput: 'ok',
    'ground-entry-point': 'ok',
    obstruction: 'ok',
    'packet-loss': 'ok',
  },
} as const satisfies Record<string, Record<string, PanelState['state']>>;
const EXPECTED_LAYER_STATE_MAPS = {
  'overview-nominal': {
    'weather-radar': 'ok',
    'planned-route-west': 'ok',
    'planned-route-east': 'ok',
    'active-x-band-normal': 'ok',
    'active-x-band-warning': 'warning',
    'position-history-west': 'ok',
    'position-history-east': 'ok',
    'flight-route-markers': 'ok',
    satellites: 'stale',
    'mission-events': 'stale',
    'ground-entry-point-layer': 'ok',
    'current-position-layer': 'ok',
  },
  'overview-no-route': {
    'weather-radar': 'ok',
    'planned-route-west': 'unavailable',
    'planned-route-east': 'unavailable',
    'active-x-band-normal': 'ok',
    'active-x-band-warning': 'ok',
    'position-history-west': 'ok',
    'position-history-east': 'ok',
    'flight-route-markers': 'unavailable',
    satellites: 'unavailable',
    'mission-events': 'unavailable',
    'ground-entry-point-layer': 'ok',
    'current-position-layer': 'ok',
  },
  'overview-sparse': {
    'weather-radar': 'ok',
    'planned-route-west': 'ok',
    'planned-route-east': 'ok',
    'active-x-band-normal': 'ok',
    'active-x-band-warning': 'ok',
    'position-history-west': 'ok',
    'position-history-east': 'ok',
    'flight-route-markers': 'ok',
    satellites: 'unavailable',
    'mission-events': 'ok',
    'ground-entry-point-layer': 'ok',
    'current-position-layer': 'ok',
  },
  'overview-stale': {
    'weather-radar': 'stale',
    'planned-route-west': 'stale',
    'planned-route-east': 'stale',
    'active-x-band-normal': 'stale',
    'active-x-band-warning': 'stale',
    'position-history-west': 'stale',
    'position-history-east': 'stale',
    'flight-route-markers': 'stale',
    satellites: 'stale',
    'mission-events': 'stale',
    'ground-entry-point-layer': 'stale',
    'current-position-layer': 'stale',
  },
  'overview-backend-failure': {
    'weather-radar': 'unavailable',
    'planned-route-west': 'unavailable',
    'planned-route-east': 'unavailable',
    'active-x-band-normal': 'unavailable',
    'active-x-band-warning': 'unavailable',
    'position-history-west': 'unavailable',
    'position-history-east': 'unavailable',
    'flight-route-markers': 'unavailable',
    satellites: 'unavailable',
    'mission-events': 'unavailable',
    'ground-entry-point-layer': 'unavailable',
    'current-position-layer': 'unavailable',
  },
  'overview-radar-failure': {
    'weather-radar': 'unavailable',
    'planned-route-west': 'ok',
    'planned-route-east': 'ok',
    'active-x-band-normal': 'ok',
    'active-x-band-warning': 'warning',
    'position-history-west': 'ok',
    'position-history-east': 'ok',
    'flight-route-markers': 'ok',
    satellites: 'ok',
    'mission-events': 'ok',
    'ground-entry-point-layer': 'ok',
    'current-position-layer': 'ok',
  },
  'overview-idl': {
    'weather-radar': 'ok',
    'planned-route-west': 'ok',
    'planned-route-east': 'ok',
    'active-x-band-normal': 'ok',
    'active-x-band-warning': 'warning',
    'position-history-west': 'ok',
    'position-history-east': 'ok',
    'flight-route-markers': 'ok',
    satellites: 'ok',
    'mission-events': 'ok',
    'ground-entry-point-layer': 'ok',
    'current-position-layer': 'ok',
  },
  'overview-threshold-crossing': {
    'weather-radar': 'ok',
    'planned-route-west': 'ok',
    'planned-route-east': 'ok',
    'active-x-band-normal': 'ok',
    'active-x-band-warning': 'critical',
    'position-history-west': 'ok',
    'position-history-east': 'ok',
    'flight-route-markers': 'ok',
    satellites: 'ok',
    'mission-events': 'ok',
    'ground-entry-point-layer': 'ok',
    'current-position-layer': 'ok',
  },
  'overview-recovery': {
    'weather-radar': 'ok',
    'planned-route-west': 'ok',
    'planned-route-east': 'ok',
    'active-x-band-normal': 'ok',
    'active-x-band-warning': 'ok',
    'position-history-west': 'ok',
    'position-history-east': 'ok',
    'flight-route-markers': 'ok',
    satellites: 'ok',
    'mission-events': 'ok',
    'ground-entry-point-layer': 'ok',
    'current-position-layer': 'ok',
  },
} as const satisfies Record<string, Record<string, LayerState['state']>>;
type SplitGeometry = Readonly<{
  westernSegment: readonly Coordinate[];
  easternSegment: readonly Coordinate[];
}>;
type TimestampedSplitGeometry = NonNullable<
  Scenario['telemetry']['positionHistorySplit']
>;

const scenarioById = (id: string): Scenario => byId(OVERVIEW_SCENARIOS, id);

const panelState = (scenario: Scenario, panelId: string): PanelState =>
  byId(scenario.expected.panelStates, panelId);

const layerState = (scenario: Scenario, layerId: string): LayerState =>
  byId(scenario.expected.layerStates, layerId);

const poiItems = (scenario: Scenario): readonly Poi[] => scenario.pois.items;

const applicablePoiIds = (scenario: Scenario) => {
  const categories =
    scenario.selectedPoiFilter.value === ''
      ? null
      : new Set(scenario.selectedPoiFilter.value.split(','));

  return poiItems(scenario)
    .filter((poi: Poi) => poi.etaIso > scenario.nowIso)
    .filter((poi: Poi) => categories === null || categories.has(poi.category))
    .sort((left: Poi, right: Poi) => left.etaIso.localeCompare(right.etaIso))
    .slice(0, 5)
    .map((poi: Poi) => poi.id);
};

const expectExactIds = (
  actualIds: readonly string[],
  expectedIds: string[]
) => {
  expect(actualIds).toEqual(expectedIds);
  expect(new Set(actualIds).size).toBe(actualIds.length);
};

const latestIso = (values: readonly (string | null)[]): string | null =>
  values
    .filter((value): value is string => value !== null)
    .sort()
    .at(-1) ?? null;

const latestPositionIso = (scenario: Scenario): string | null =>
  latestIso(
    scenario.telemetry.positionHistory.map((sample) => sample.observedAt)
  );

const latestHistoryIso = (scenario: Scenario): string | null =>
  latestIso([
    ...scenario.telemetry.positionHistory.map((sample) => sample.observedAt),
    ...scenario.telemetry.metrics.latency.history.map(
      (sample) => sample.observedAt
    ),
    ...scenario.telemetry.metrics.packetLoss.history.map(
      (sample) => sample.observedAt
    ),
  ]);

const latestActiveLinkIso = (scenario: Scenario): string | null =>
  latestIso(scenario.activeLinks.map((link) => link.observedAt));

const latestEventIso = (scenario: Scenario): string | null =>
  latestIso(scenario.missionEvents.items.map((event) => event.observedAt));

const satelliteItems = (scenario: Scenario): readonly Satellite[] =>
  scenario.satellites.items;

const missionEventItems = (scenario: Scenario): readonly MissionEvent[] =>
  scenario.missionEvents.items;

const validValues = (samples: readonly NumericSample[]): number[] =>
  samples
    .map((sample) => sample.value)
    .filter((value): value is number => value !== null);

const mean = (values: readonly number[]): number | null =>
  values.length === 0
    ? null
    : Math.round(
        (values.reduce((total, value) => total + value, 0) / values.length) * 10
      ) / 10;

const currentValue = (samples: readonly NumericSample[]): number | null =>
  samples.at(-1)?.value ?? null;

const metricSummary = (samples: readonly NumericSample[]) => {
  const values = validValues(samples);

  return {
    current: currentValue(samples),
    min: values.length === 0 ? null : Math.min(...values),
    average: mean(values),
    max: values.length === 0 ? null : Math.max(...values),
  };
};

const formatNumber = (value: number | null, digits = 0): string =>
  value === null
    ? 'No data'
    : new Intl.NumberFormat('en-US', {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      }).format(value);

const formatCoordinate = (coordinate: Coordinate): string =>
  `${coordinate.latitude.toFixed(4)}, ${coordinate.longitude.toFixed(
    4
  )} at ${formatNumber(coordinate.altitudeMeters)} m`;

const classifyHighBad = (
  value: number | null,
  threshold: Readonly<{ warning: number; critical: number }>
) => {
  if (value === null) return 'unavailable';
  if (value >= threshold.critical) return 'critical';
  if (value >= threshold.warning) return 'warning';
  return 'ok';
};

const countByLongitudeSign = (
  samples: readonly PositionSample[],
  side: 'west' | 'east'
) =>
  samples.filter((sample) => {
    if (sample.coordinate === null) return false;
    return side === 'west'
      ? sample.coordinate.longitude < 0
      : sample.coordinate.longitude >= 0;
  }).length;

const countLinks = (scenario: Scenario, mode: ActiveLink['mode']) =>
  scenario.activeLinks.filter((link) => link.mode === mode).length;

const staleThresholdMs =
  Math.max(5, 3 * OVERVIEW_CONTRACT.defaults.dashboardRefreshSeconds) * 1_000;

const sourceAgeMs = (scenario: Scenario, iso: string | null): number | null =>
  iso === null ? null : Date.parse(scenario.nowIso) - Date.parse(iso);

const sourceState = (
  scenario: Scenario,
  iso: string | null
): PanelState['state'] =>
  iso === null
    ? 'unavailable'
    : (sourceAgeMs(scenario, iso) ?? 0) > staleThresholdMs
      ? 'stale'
      : 'ok';

const freshnessIsCurrent = (scenario: Scenario, iso: string | null) =>
  sourceState(scenario, iso) === 'ok';

const sourceFreshnessFromPayload = (scenario: Scenario) => ({
  telemetry: scenario.telemetry.currentObservedAt,
  history: latestHistoryIso(scenario),
  activeLink: latestActiveLinkIso(scenario),
  pois: scenario.pois.generatedAt,
  route: scenario.route.revisionAt,
  groundEntryPoint: scenario.groundEntryPoint.observedAt,
  radar: scenario.radar.frameAt,
});

const expectChronologicalNoFuture = (
  scenario: Scenario,
  samples: readonly { observedAt: string | null }[]
) => {
  const timestamps = samples
    .map((sample) => sample.observedAt)
    .filter((timestamp): timestamp is string => timestamp !== null);

  expect(timestamps).toEqual([...timestamps].sort());
  for (const timestamp of timestamps) {
    expect(timestamp).toMatch(ISO_UTC);
    expect(timestamp <= scenario.nowIso).toBe(true);
  }
};

const expectLayerValueContainsCount = (
  scenario: Scenario,
  layerId: string,
  count: number
) => {
  expect(layerState(scenario, layerId).value).toContain(String(count));
};

const expectedPanelStateMap = (
  scenario: Scenario
): Record<string, PanelState['state']> =>
  Object.fromEntries(
    scenario.expected.panelStates.map((state) => [state.id, state.state])
  );

const expectedLayerStateMap = (
  scenario: Scenario
): Record<string, LayerState['state']> =>
  Object.fromEntries(
    scenario.expected.layerStates.map((state) => [state.id, state.state])
  );

const expectNoLargeLongitudeJump = (segment: readonly Coordinate[]) => {
  for (let index = 1; index < segment.length; index += 1) {
    expect(
      Math.abs(segment[index].longitude - segment[index - 1].longitude)
    ).toBeLessThanOrEqual(180);
  }
};

const expectPairedBoundary = (
  western: readonly Coordinate[],
  eastern: readonly Coordinate[]
) => {
  const westernEnd = western.at(-1);
  const easternStart = eastern.at(0);

  expect(westernEnd).toBeDefined();
  expect(easternStart).toBeDefined();
  expect(Math.abs(westernEnd?.longitude ?? 0)).toBe(180);
  expect(Math.abs(easternStart?.longitude ?? 0)).toBe(180);
  expect(westernEnd?.longitude).toBe(-(easternStart?.longitude ?? 0));
  expect(easternStart?.latitude).toBe(westernEnd?.latitude);
  expect(easternStart?.altitudeMeters).toBe(westernEnd?.altitudeMeters);
};

const expectSplitGeometry = (geometry: SplitGeometry) => {
  expect(geometry.westernSegment.length).toBeGreaterThan(1);
  expect(geometry.easternSegment.length).toBeGreaterThan(1);
  expectPairedBoundary(geometry.westernSegment, geometry.easternSegment);
  expectNoLargeLongitudeJump(geometry.westernSegment);
  expectNoLargeLongitudeJump(geometry.easternSegment);
};

const unwrapDestinationLongitude = (
  startLongitude: number,
  endLongitude: number
) => {
  if (endLongitude - startLongitude > 180) return endLongitude - 360;
  if (startLongitude - endLongitude > 180) return endLongitude + 360;
  return endLongitude;
};

const idlBoundaryLongitude = (
  startLongitude: number,
  unwrappedEndLongitude: number
) => (unwrappedEndLongitude > startLongitude ? 180 : -180);

const interpolate = (start: number, end: number, fraction: number) =>
  start + (end - start) * fraction;

const expectInterpolatedBoundary = (
  start: Coordinate,
  end: Coordinate,
  boundary: Coordinate
) => {
  const unwrappedEndLongitude = unwrapDestinationLongitude(
    start.longitude,
    end.longitude
  );
  const crossingLongitude = idlBoundaryLongitude(
    start.longitude,
    unwrappedEndLongitude
  );
  const fraction =
    (crossingLongitude - start.longitude) /
    (unwrappedEndLongitude - start.longitude);

  expect(boundary.longitude).toBe(crossingLongitude);
  expect(boundary.latitude).toBeCloseTo(
    interpolate(start.latitude, end.latitude, fraction),
    10
  );
  expect(boundary.altitudeMeters).toBeCloseTo(
    interpolate(start.altitudeMeters, end.altitudeMeters, fraction),
    7
  );

  return { crossingLongitude, fraction };
};

const expectSplitFromRawEndpoints = (
  rawFrom: Coordinate,
  rawTo: Coordinate,
  split: SplitGeometry
) => {
  const start = split.westernSegment.at(0);
  const boundary = split.westernSegment.at(-1);
  const pairedBoundary = split.easternSegment.at(0);
  const finish = split.easternSegment.at(-1);

  expect(start).toEqual(rawFrom);
  expect(finish).toEqual(rawTo);
  expect(boundary).toBeDefined();
  expect(pairedBoundary).toBeDefined();

  const { crossingLongitude } = expectInterpolatedBoundary(
    rawFrom,
    rawTo,
    boundary as Coordinate
  );

  expect(pairedBoundary?.longitude).toBe(-crossingLongitude);
  expect(pairedBoundary?.latitude).toBe(boundary?.latitude);
  expect(pairedBoundary?.altitudeMeters).toBe(boundary?.altitudeMeters);
};

const expectTimestampedBoundaryPair = (
  rawFrom: PositionSample,
  rawTo: PositionSample,
  split: TimestampedSplitGeometry
) => {
  expect(rawFrom.coordinate).not.toBeNull();
  expect(rawTo.coordinate).not.toBeNull();

  const westernStart = split.westernSegment.at(0);
  const westernBoundary = split.westernSegment.at(-1);
  const easternBoundary = split.easternSegment.at(0);
  const easternEnd = split.easternSegment.at(-1);

  expect(westernStart).toEqual(rawFrom);
  expect(easternEnd).toEqual(rawTo);
  expect(westernBoundary).toBeDefined();
  expect(easternBoundary).toBeDefined();

  const rawFromCoordinate = rawFrom.coordinate as Coordinate;
  const rawToCoordinate = rawTo.coordinate as Coordinate;
  const boundaryCoordinate = westernBoundary?.coordinate as Coordinate;
  const { crossingLongitude, fraction } = expectInterpolatedBoundary(
    rawFromCoordinate,
    rawToCoordinate,
    boundaryCoordinate
  );
  const expectedObservedAt = new Date(
    interpolate(
      Date.parse(rawFrom.observedAt),
      Date.parse(rawTo.observedAt),
      fraction
    )
  )
    .toISOString()
    .replace('.000Z', 'Z');

  expect(easternBoundary?.coordinate?.longitude).toBe(-crossingLongitude);
  expect(easternBoundary?.coordinate?.latitude).toBe(
    westernBoundary?.coordinate?.latitude
  );
  expect(easternBoundary?.coordinate?.altitudeMeters).toBe(
    westernBoundary?.coordinate?.altitudeMeters
  );
  expect(westernBoundary?.observedAt).toBe(expectedObservedAt);
  expect(easternBoundary?.observedAt).toBe(expectedObservedAt);
  expect(easternBoundary?.speedKnots).toBe(westernBoundary?.speedKnots);
  expect(easternBoundary?.headingDegrees).toBe(westernBoundary?.headingDegrees);
};

describe('operations overview parity contract', () => {
  it('freezes the approved scenario inventory and exact per-scenario coverage', () => {
    expect(OVERVIEW_SCENARIOS.map((scenario) => scenario.name)).toEqual(
      EXPECTED_SCENARIOS
    );
    expect(OVERVIEW_SCENARIOS.map((scenario) => scenario.id)).toEqual(
      EXPECTED_SCENARIO_IDS
    );

    for (const scenario of OVERVIEW_SCENARIOS) {
      expect(scenario.nowIso).toMatch(ISO_UTC);
      expect(scenario.selectedPoiFilter).toEqual(
        scenario.selectedPoiFilter.value === ''
          ? { value: '', query: {} }
          : {
              value: scenario.selectedPoiFilter.value,
              query: { category: scenario.selectedPoiFilter.value },
            }
      );

      expectExactIds(
        scenario.expected.panelStates.map((state: PanelState) => state.id),
        PANEL_IDS
      );
      expectExactIds(
        scenario.expected.layerStates.map((state: LayerState) => state.id),
        LAYER_IDS
      );
      expect(Object.keys(scenario.expected.sourceFreshness)).toEqual(
        FRESHNESS_KEYS
      );
      expect(panelState(scenario, 'clock-utc').value).toBe(
        `${scenario.nowIso.slice(11, 19)}Z`
      );

      for (const value of Object.values(
        scenario.expected.sourceFreshness
      ) as Array<string | null>) {
        if (value !== null) expect(value).toMatch(ISO_UTC);
      }
    }
  });

  it('freezes exact ordered panel, map layer, and POI option inventories', () => {
    expect(OVERVIEW_CONTRACT.panels).toEqual([
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
    ]);

    expect(OVERVIEW_CONTRACT.mapLayers).toEqual(EXPECTED_LAYER_INVENTORY);

    expect(OVERVIEW_CONTRACT.poiOptions).toEqual([
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
      {
        label: 'Arrival Only',
        value: 'arrival',
        query: { category: 'arrival' },
      },
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
    ]);
  });

  it('freezes timing, threshold, exact style, and basemap defaults', () => {
    expect(OVERVIEW_CONTRACT.defaults).toEqual({
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
    });
  });

  it('documents default filter and All POIs omitted-category semantics', () => {
    const defaultOption = OVERVIEW_CONTRACT.poiOptions.find(
      (option) => 'isDefault' in option && option.isDefault
    );

    expect(defaultOption).toEqual({
      label: 'Departure & Arrival',
      value: 'departure,arrival',
      query: { category: 'departure,arrival' },
      isDefault: true,
    });
    expect(buildPoiQuery('')).toEqual({});
    expect(buildPoiQuery('departure,arrival')).toEqual({
      category: 'departure,arrival',
    });
  });

  it('proves POI applicability is future-only, filtered, chronological, and capped', () => {
    for (const scenario of OVERVIEW_SCENARIOS) {
      const filterCategories =
        scenario.selectedPoiFilter.value === ''
          ? null
          : new Set(scenario.selectedPoiFilter.value.split(','));

      if (filterCategories === null) {
        expect(scenario.selectedPoiFilter.query).toEqual({});
      }
      for (const poi of poiItems(scenario)) {
        expect(
          filterCategories === null || filterCategories.has(poi.category)
        ).toBe(true);
      }
      expect(scenario.expected.topFivePoiIds).toEqual(
        applicablePoiIds(scenario)
      );
      expect(scenario.expected.topFivePoiIds.length).toBeLessThanOrEqual(5);
      expectLayerValueContainsCount(
        scenario,
        'flight-route-markers',
        poiItems(scenario).length
      );
    }

    expect(scenarioById('overview-nominal').expected.topFivePoiIds).toEqual([
      'poi-arrive-rjtt',
    ]);
    expect(scenarioById('overview-idl').expected.topFivePoiIds).toEqual([
      'poi-arrive-rjtt',
    ]);
    expect(scenarioById('overview-sparse').selectedPoiFilter).toEqual({
      value: '',
      query: {},
    });
    expect(scenarioById('overview-sparse').expected.topFivePoiIds).toEqual([
      'poi-waypoint-alaska',
      'poi-alternate-panc',
      'poi-waypoint-idl',
      'poi-waypoint-kamchatka',
      'poi-waypoint-hokkaido',
    ]);
  });

  it('represents complete timestamped metric, position, link, event, and map payloads', () => {
    for (const scenario of OVERVIEW_SCENARIOS) {
      expect(
        Object.keys(scenario.telemetry.metrics.throughput.current)
      ).toEqual(['downloadMbps', 'uploadMbps']);
      expect(scenario.telemetry.metrics.obstruction).toHaveProperty(
        'currentPercent'
      );
      expectChronologicalNoFuture(scenario, scenario.telemetry.positionHistory);
      expectChronologicalNoFuture(
        scenario,
        scenario.telemetry.metrics.latency.history
      );
      expectChronologicalNoFuture(
        scenario,
        scenario.telemetry.metrics.packetLoss.history
      );
      if (scenario.id === 'overview-backend-failure') {
        expect(scenario.telemetry.positionHistory).toEqual([]);
        expect(scenario.telemetry.metrics.latency.history).toEqual([]);
        expect(scenario.telemetry.metrics.packetLoss.history).toEqual([]);
        expect(scenario.expected.sourceFreshness.history).toBeNull();
      } else {
        expect(
          scenario.telemetry.metrics.latency.history.length
        ).toBeGreaterThan(0);
        expect(
          scenario.telemetry.metrics.packetLoss.history.length
        ).toBeGreaterThan(0);
      }
      expect(scenario.activeLinks.length).toBeGreaterThanOrEqual(1);
      expectChronologicalNoFuture(scenario, scenario.activeLinks);
      expectChronologicalNoFuture(scenario, missionEventItems(scenario));
      expect(Array.isArray(scenario.pois.items)).toBe(true);
      expect(Array.isArray(scenario.satellites.items)).toBe(true);
      expect(Array.isArray(scenario.missionEvents.items)).toBe(true);
      expect(scenario.expected.route).toBeDefined();
      expect(scenario.expected.radar).toBeDefined();
      expect(scenario.radar).toMatchObject({
        available: expect.any(Boolean),
      });
      if (scenario.route.active) {
        expect(scenario.route.revisionAt).toMatch(ISO_UTC);
        expect(scenario.route.westernSegment.length).toBeGreaterThan(0);
        expect(scenario.route.easternSegment.length).toBeGreaterThan(0);
      } else {
        expect(scenario.route.revisionAt).toBeNull();
        expect(scenario.route.westernSegment).toEqual([]);
        expect(scenario.route.easternSegment).toEqual([]);
        expect(scenario.expected.route.westernPointCount).toBe(0);
        expect(scenario.expected.route.easternPointCount).toBe(0);
      }
    }
  });

  it('derives metric summaries, source freshness, and panel values from payloads', () => {
    for (const scenario of OVERVIEW_SCENARIOS) {
      const latency = metricSummary(scenario.telemetry.metrics.latency.history);
      const packetLoss = metricSummary(
        scenario.telemetry.metrics.packetLoss.history
      );
      const metrics = scenario.telemetry.metrics;

      expect(metrics.latency.currentMs).toBe(latency.current);
      expect(metrics.latency.fiveMinute.minMs).toBe(latency.min);
      expect(metrics.latency.fiveMinute.averageMs).toBe(latency.average);
      expect(metrics.latency.fiveMinute.maxMs).toBe(latency.max);
      expect(metrics.packetLoss.currentPercent).toBe(packetLoss.current);
      expect(metrics.packetLoss.averagePercent).toBe(packetLoss.average);
      expect(metrics.packetLoss.maxPercent).toBe(packetLoss.max);

      expect(scenario.expected.sourceFreshness).toEqual(
        sourceFreshnessFromPayload(scenario)
      );
      expect(scenario.expected.sourceFreshness.telemetry).toBe(
        latestPositionIso(scenario)
      );
      expect(scenario.expected.sourceFreshness.history).toBe(
        latestHistoryIso(scenario)
      );
      expect(scenario.expected.sourceFreshness.pois).toBe(
        scenario.pois.generatedAt
      );

      if (metrics.latency.currentMs === null) {
        expect(panelState(scenario, 'network-latency')).toMatchObject({
          state: 'unavailable',
          value: 'No latency data',
        });
      } else {
        expect(panelState(scenario, 'network-latency').value).toBe(
          `${metrics.latency.currentMs} ms current / ${metrics.latency.fiveMinute.minMs}-${metrics.latency.fiveMinute.averageMs}-${metrics.latency.fiveMinute.maxMs} ms five-minute`
        );
      }

      if (metrics.packetLoss.currentPercent === null) {
        expect(panelState(scenario, 'packet-loss')).toMatchObject({
          state: 'unavailable',
          value: 'No packet loss data',
        });
      } else {
        expect(panelState(scenario, 'packet-loss').value).toBe(
          `${metrics.packetLoss.currentPercent}% current / ${metrics.packetLoss.averagePercent}% avg / ${metrics.packetLoss.maxPercent}% max`
        );
      }

      if (scenario.telemetry.currentPosition !== null) {
        expect(panelState(scenario, 'current-position-map').value).toContain(
          formatCoordinate(scenario.telemetry.currentPosition)
        );
      }
      expect(layerState(scenario, 'ground-entry-point-layer').value).toBe(
        scenario.groundEntryPoint.display === 'Unavailable'
          ? 'ground entry point unavailable'
          : scenario.groundEntryPoint.display
      );
      expectLayerValueContainsCount(
        scenario,
        'flight-route-markers',
        poiItems(scenario).length
      );
      expectLayerValueContainsCount(
        scenario,
        'satellites',
        satelliteItems(scenario).length
      );
      expectLayerValueContainsCount(
        scenario,
        'mission-events',
        missionEventItems(scenario).length
      );
      if (scenario.radar.available) {
        expect(scenario.expected.radar.state).toBe(scenario.radar.state);
        expect(scenario.radar.error).toBeUndefined();
        expect(scenario.radar.frameAt).toBe(
          scenario.expected.sourceFreshness.radar
        );
        expect(layerState(scenario, 'weather-radar').state).toBe(
          sourceState(scenario, scenario.radar.frameAt)
        );
        if (layerState(scenario, 'weather-radar').state === 'ok') {
          expect(
            sourceAgeMs(scenario, scenario.radar.frameAt)
          ).toBeLessThanOrEqual(staleThresholdMs);
        }
        expect(layerState(scenario, 'weather-radar').value).toContain(
          scenario.expected.sourceFreshness.radar
        );
      } else {
        expect(scenario.expected.radar.state).toBe(scenario.radar.state);
        expect(scenario.radar.error).toBeDefined();
        expect(scenario.radar.frameAt).toBeNull();
        expect(layerState(scenario, 'weather-radar')).toMatchObject({
          state: 'unavailable',
          availability: 'local-failure',
        });
      }
      if (scenario.expected.sourceFreshness.activeLink !== null) {
        const linkLayer =
          countLinks(scenario, 'normal') > 0
            ? layerState(scenario, 'active-x-band-normal')
            : layerState(scenario, 'active-x-band-warning');

        expect(linkLayer.value).toContain(
          scenario.expected.sourceFreshness.activeLink
        );
      }
    }
  });

  it('derives source-age panel and layer states from the five-second refresh threshold', () => {
    for (const scenario of OVERVIEW_SCENARIOS) {
      const freshness = sourceFreshnessFromPayload(scenario);
      const poiAgeMs = sourceAgeMs(scenario, scenario.pois.generatedAt);
      const satelliteAgeMs = sourceAgeMs(
        scenario,
        scenario.satellites.generatedAt
      );
      const missionEventAgeMs = sourceAgeMs(
        scenario,
        scenario.missionEvents.generatedAt
      );
      const states = {
        telemetry: sourceState(scenario, freshness.telemetry),
        history: sourceState(scenario, freshness.history),
        activeLink: sourceState(scenario, freshness.activeLink),
        pois:
          poiAgeMs === null
            ? 'unavailable'
            : poiAgeMs > staleThresholdMs
              ? 'stale'
              : 'ok',
        satellites:
          satelliteAgeMs === null
            ? 'unavailable'
            : satelliteAgeMs > staleThresholdMs
              ? 'stale'
              : 'ok',
        missionEvents:
          missionEventAgeMs === null
            ? 'unavailable'
            : missionEventAgeMs > staleThresholdMs
              ? 'stale'
              : 'ok',
        route: scenario.route.active
          ? sourceState(scenario, freshness.route)
          : 'unavailable',
        groundEntryPoint:
          scenario.groundEntryPoint.coordinate === null
            ? 'unavailable'
            : sourceState(scenario, freshness.groundEntryPoint),
        radar: scenario.radar.available
          ? sourceState(scenario, freshness.radar)
          : 'unavailable',
      } as const;

      if (
        sourceState(scenario, freshness.telemetry) !== 'ok' ||
        scenario.telemetry.currentPosition === null
      ) {
        expect(panelState(scenario, 'current-position-map').state).toBe(
          sourceState(scenario, freshness.telemetry)
        );
      }
      if (sourceState(scenario, freshness.history) !== 'ok') {
        expect(panelState(scenario, 'network-latency').state).toBe(
          scenario.telemetry.metrics.latency.currentMs === null
            ? 'unavailable'
            : sourceState(scenario, freshness.history)
        );
        expect(panelState(scenario, 'packet-loss').state).toBe(
          scenario.telemetry.metrics.packetLoss.currentPercent === null
            ? 'unavailable'
            : sourceState(scenario, freshness.history)
        );
      }
      if (sourceState(scenario, freshness.telemetry) !== 'ok') {
        expect(panelState(scenario, 'throughput').state).toBe(
          scenario.telemetry.metrics.throughput.current.downloadMbps === null
            ? 'unavailable'
            : sourceState(scenario, freshness.telemetry)
        );
        expect(panelState(scenario, 'obstruction').state).toBe(
          scenario.telemetry.metrics.obstruction.currentPercent === null
            ? 'unavailable'
            : sourceState(scenario, freshness.telemetry)
        );
      }
      expect(panelState(scenario, 'ground-entry-point').state).toBe(
        scenario.groundEntryPoint.coordinate === null
          ? 'unavailable'
          : sourceState(scenario, freshness.groundEntryPoint)
      );

      for (const panelId of [
        'clock-utc',
        'clock-washington-dc',
        'clock-tokyo',
        'clock-omaha',
      ]) {
        expect(panelState(scenario, panelId).state).toBe('ok');
      }

      expect(scenario.expected.route.state).toBe(states.route);
      expect(layerState(scenario, 'weather-radar').state).toBe(states.radar);
      expect(layerState(scenario, 'planned-route-west').state).toBe(
        states.route
      );
      expect(layerState(scenario, 'planned-route-east').state).toBe(
        states.route
      );
      if (states.activeLink === 'unavailable') {
        expect(layerState(scenario, 'active-x-band-normal').state).toBe(
          'unavailable'
        );
        expect(layerState(scenario, 'active-x-band-warning').state).toBe(
          'unavailable'
        );
      } else {
        expect(layerState(scenario, 'active-x-band-normal').value).toContain(
          freshness.activeLink
        );
        if (countLinks(scenario, 'warning') === 0) {
          expect(
            layerState(scenario, 'active-x-band-warning').availability
          ).toBe('empty');
        } else {
          expect(layerState(scenario, 'active-x-band-warning').value).toContain(
            freshness.activeLink
          );
        }
      }
      expect(layerState(scenario, 'position-history-west').state).toBe(
        states.history
      );
      expect(layerState(scenario, 'position-history-east').state).toBe(
        states.history
      );
      expect(layerState(scenario, 'flight-route-markers').state).toBe(
        scenario.route.active && poiItems(scenario).length > 0
          ? states.pois
          : 'unavailable'
      );
      expect(layerState(scenario, 'satellites').state).toBe(
        scenario.satellites.generatedAt !== null &&
          satelliteItems(scenario).length > 0
          ? states.satellites
          : 'unavailable'
      );
      expect(layerState(scenario, 'mission-events').state).toBe(
        scenario.missionEvents.generatedAt !== null &&
          missionEventItems(scenario).length > 0
          ? states.missionEvents
          : 'unavailable'
      );
      expect(layerState(scenario, 'ground-entry-point-layer').state).toBe(
        states.groundEntryPoint
      );
      expect(layerState(scenario, 'current-position-layer').state).toBe(
        states.telemetry
      );
      expect(expectedPanelStateMap(scenario)).toEqual(
        EXPECTED_PANEL_STATE_MAPS[scenario.id]
      );
      expect(expectedLayerStateMap(scenario)).toEqual(
        EXPECTED_LAYER_STATE_MAPS[scenario.id]
      );
    }
  });

  it('classifies thresholds from source payloads and keeps unrelated panels ok', () => {
    const checked = ['overview-threshold-crossing', 'overview-recovery'];

    for (const scenario of checked.map(scenarioById)) {
      expect(panelState(scenario, 'network-latency').state).toBe(
        classifyHighBad(
          scenario.telemetry.metrics.latency.currentMs,
          OVERVIEW_CONTRACT.defaults.thresholds.latencyMs
        )
      );
      expect(panelState(scenario, 'obstruction').state).toBe(
        classifyHighBad(
          scenario.telemetry.metrics.obstruction.currentPercent,
          OVERVIEW_CONTRACT.defaults.thresholds.obstructionPercent
        )
      );
      expect(panelState(scenario, 'packet-loss').state).toBe(
        classifyHighBad(
          scenario.telemetry.metrics.packetLoss.currentPercent,
          OVERVIEW_CONTRACT.defaults.thresholds.packetLossPercent
        )
      );

      for (const panelId of [
        'clock-utc',
        'clock-washington-dc',
        'clock-tokyo',
        'clock-omaha',
        'current-position-map',
        'poi-quick-reference',
        'throughput',
        'ground-entry-point',
      ]) {
        expect(panelState(scenario, panelId).state).toBe('ok');
      }
      expect(freshnessIsCurrent(scenario, latestPositionIso(scenario))).toBe(
        true
      );
    }
  });

  it('keeps IDL route, history, links, events, and freshness internally consistent', () => {
    const idl = scenarioById('overview-idl');

    expect(idl.route.crossesInternationalDateLine).toBe(true);
    expectSplitGeometry(idl.route);
    expect(idl.route.westernSegment.at(-2)).toEqual({
      latitude: 49.4,
      longitude: 179.6,
      altitudeMeters: 11278,
    });
    expect(idl.route.easternSegment.at(1)).toEqual({
      latitude: 50.1,
      longitude: -179.7,
      altitudeMeters: 11278,
    });
    expectInterpolatedBoundary(
      idl.route.westernSegment.at(-2) as Coordinate,
      idl.route.easternSegment.at(1) as Coordinate,
      idl.route.westernSegment.at(-1) as Coordinate
    );
    expect(idl.telemetry.positionHistorySplit).toBeDefined();
    const historySplit = idl.telemetry
      .positionHistorySplit as TimestampedSplitGeometry;

    expectSplitGeometry({
      westernSegment: historySplit.westernSegment.map(
        (sample) => sample.coordinate as Coordinate
      ),
      easternSegment: historySplit.easternSegment.map(
        (sample) => sample.coordinate as Coordinate
      ),
    });
    expectTimestampedBoundaryPair(
      idl.telemetry.positionHistory[0],
      idl.telemetry.positionHistory[1],
      historySplit
    );
    expect(countByLongitudeSign(idl.telemetry.positionHistory, 'west')).toBe(1);
    expect(countByLongitudeSign(idl.telemetry.positionHistory, 'east')).toBe(1);
    expect(layerState(idl, 'position-history-west').value).toBe(
      `${historySplit.westernSegment.length} western IDL points`
    );
    expect(layerState(idl, 'position-history-east').value).toBe(
      `${historySplit.easternSegment.length} eastern IDL points`
    );
    expect(countLinks(idl, 'normal')).toBe(1);
    expect(countLinks(idl, 'warning')).toBe(1);
    for (const mode of ['normal', 'warning'] as const) {
      const link = idl.activeLinks.find((candidate) => candidate.mode === mode);

      expect(link).toBeDefined();
      expect(link?.splitGeometry).toBeDefined();
      expectSplitGeometry(link?.splitGeometry as SplitGeometry);
      expectSplitFromRawEndpoints(
        link?.from as Coordinate,
        link?.to as Coordinate,
        link?.splitGeometry as SplitGeometry
      );
    }
    expect(idl.expected.sourceFreshness.activeLink).toBe(
      latestActiveLinkIso(idl)
    );
    expect(layerState(idl, 'active-x-band-normal').value).toContain(
      idl.expected.sourceFreshness.activeLink
    );
    expect(layerState(idl, 'active-x-band-warning').value).toContain(
      idl.expected.sourceFreshness.activeLink
    );
    const idlEvent = byId(missionEventItems(idl), 'event-idl-crossed');
    const boundary = historySplit.westernSegment.at(-1);

    expect(latestEventIso(idl)).toBe('2026-02-03T17:05:58Z');
    expect(idlEvent.observedAt).toBe(boundary?.observedAt);
    expect(idlEvent.coordinate).toEqual(boundary?.coordinate);
    expect(idlEvent.label).toContain('International Date Line');
    expect(idl.expected.sourceFreshness.route).toBe(idl.route.revisionAt);
  });

  it('freezes localized scenario semantics', () => {
    const nominal = scenarioById('overview-nominal');
    expect(nominal.selectedPoiFilter.value).toBe('departure,arrival');
    expect(panelState(nominal, 'network-latency')).toMatchObject({
      state: 'ok',
      value: '74 ms current / 60-74-88 ms five-minute',
    });
    expect(layerState(nominal, 'active-x-band-normal')).toMatchObject({
      state: 'ok',
      availability: 'available',
    });

    const noRoute = scenarioById('overview-no-route');
    expect(panelState(noRoute, 'poi-quick-reference')).toMatchObject({
      state: 'unavailable',
      value: 'No active route',
    });
    expect(layerState(noRoute, 'planned-route-west')).toMatchObject({
      state: 'unavailable',
      availability: 'empty',
    });

    const stale = scenarioById('overview-stale');
    expect(stale.expected.sourceFreshness.telemetry).toBe(
      '2026-02-03T15:30:00Z'
    );
    for (const panelId of [
      'current-position-map',
      'poi-quick-reference',
      'network-latency',
      'throughput',
      'ground-entry-point',
      'obstruction',
      'packet-loss',
    ]) {
      expect(panelState(stale, panelId).state).toBe('stale');
    }
    for (const layerId of [
      'weather-radar',
      'planned-route-west',
      'planned-route-east',
      'active-x-band-normal',
      'position-history-west',
      'position-history-east',
      'flight-route-markers',
      'ground-entry-point-layer',
      'current-position-layer',
    ]) {
      expect(layerState(stale, layerId).state).toBe('stale');
    }
    expect(stale.expected.route.state).toBe('stale');
    expect(panelState(stale, 'clock-utc').state).toBe('ok');

    const backendFailure = scenarioById('overview-backend-failure');
    expect(
      ['clock-utc', 'clock-washington-dc', 'clock-tokyo', 'clock-omaha'].map(
        (panelId) => panelState(backendFailure, panelId).state
      )
    ).toEqual(['ok', 'ok', 'ok', 'ok']);
    expect(panelState(backendFailure, 'network-latency').state).toBe(
      'unavailable'
    );
    expect(byId(backendFailure.activeLinks, 'xband-unavailable')).toMatchObject(
      {
        mode: 'unavailable',
        observedAt: null,
        from: null,
        to: null,
      }
    );
    expect(backendFailure.expected.sourceFreshness.activeLink).toBeNull();

    const radarFailure = scenarioById('overview-radar-failure');
    expect(layerState(radarFailure, 'weather-radar')).toMatchObject({
      state: 'unavailable',
      availability: 'local-failure',
    });
    expect(panelState(radarFailure, 'network-latency').state).toBe('ok');
    expect(panelState(radarFailure, 'ground-entry-point').state).toBe('ok');

    const idl = scenarioById('overview-idl');
    expect(idl.route.crossesInternationalDateLine).toBe(true);
    expect(
      idl.route.westernSegment.map((point: Coordinate) => point.longitude)
    ).toEqual([170.2, 179.6, 180]);
    expect(
      idl.route.easternSegment.map((point: Coordinate) => point.longitude)
    ).toEqual([-180, -179.7, -165, -122.3088]);

    const threshold = scenarioById('overview-threshold-crossing');
    expect(panelState(threshold, 'network-latency')).toMatchObject({
      state: 'critical',
      value: '205 ms current / 150-181-205 ms five-minute',
    });
    expect(panelState(threshold, 'obstruction')).toMatchObject({
      state: 'critical',
      value: '10.5%',
    });
    expect(panelState(threshold, 'packet-loss')).toMatchObject({
      state: 'critical',
      value: '5.4% current / 3.2% avg / 5.4% max',
    });
    expect(panelState(threshold, 'throughput').state).toBe('ok');

    const recovery = scenarioById('overview-recovery');
    expect(panelState(recovery, 'network-latency')).toMatchObject({
      state: 'ok',
      value: '99 ms current / 82-91-99 ms five-minute',
    });
    expect(panelState(recovery, 'obstruction')).toMatchObject({
      state: 'ok',
      value: '4.9%',
    });
    expect(panelState(recovery, 'packet-loss')).toMatchObject({
      state: 'ok',
      value: '1.9% current / 1.3% avg / 1.9% max',
    });
    expect(layerState(recovery, 'weather-radar').state).toBe('ok');
  });

  it('keeps fixture data literal, deterministic, and serializable', () => {
    const source = readFileSync(FIXTURE_SOURCE_PATH, 'utf8');
    const forbiddenTokens = [
      'Date.now',
      'new Date',
      'Math.random',
      'fetch',
      'axios',
      'process.env',
      'setTimeout',
      'setInterval',
    ];

    for (const token of forbiddenTokens) {
      expect(source).not.toContain(token);
    }

    const canonical = JSON.stringify({ OVERVIEW_CONTRACT, OVERVIEW_SCENARIOS });
    const digest = createHash('sha256').update(canonical).digest('hex');

    expect(digest).toBe(
      '58a10237f8fc614597ab9c6bdaaacaa8d96fdd0d72da26a9188fa54c1f8ff4b2'
    );
    expect(canonical).toMatch(/2026-02-03T15:30:00Z/);
    expect(canonical).not.toMatch(/localhost|127\.0\.0\.1/);
  });
});
