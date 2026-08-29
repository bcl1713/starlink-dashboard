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
type Poi = Scenario['pois'][number];
type PositionSample = Scenario['telemetry']['positionHistory'][number];
type ActiveLink = Scenario['activeLinks'][number];
type Coordinate = Scenario['route']['westernSegment'][number];
type NumericSample =
  Scenario['telemetry']['metrics']['latency']['history'][number];

const scenarioById = (id: string): Scenario => byId(OVERVIEW_SCENARIOS, id);

const panelState = (scenario: Scenario, panelId: string): PanelState =>
  byId(scenario.expected.panelStates, panelId);

const layerState = (scenario: Scenario, layerId: string): LayerState =>
  byId(scenario.expected.layerStates, layerId);

const applicablePoiIds = (scenario: Scenario) => {
  const categories =
    scenario.selectedPoiFilter.value === ''
      ? null
      : new Set(scenario.selectedPoiFilter.value.split(','));

  return scenario.pois
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
    scenario.telemetry.positionHistory.map((sample) =>
      sample.coordinate === null ? null : sample.observedAt
    )
  );

const latestActiveLinkIso = (scenario: Scenario): string | null =>
  latestIso(
    scenario.activeLinks.map((link) =>
      link.from === null || link.to === null ? null : link.observedAt
    )
  );

const latestEventIso = (scenario: Scenario): string | null =>
  latestIso(scenario.missionEvents.map((event) => event.observedAt));

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

const freshnessIsCurrent = (scenario: Scenario, iso: string | null) =>
  iso !== null && Date.parse(scenario.nowIso) - Date.parse(iso) <= 5_000;

const expectChronologicalNoFuture = (
  scenario: Scenario,
  samples: readonly { observedAt: string }[]
) => {
  const timestamps = samples.map((sample) => sample.observedAt);

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
      expect(scenario.expected.topFivePoiIds).toEqual(
        applicablePoiIds(scenario)
      );
      expect(scenario.expected.topFivePoiIds.length).toBeLessThanOrEqual(5);
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
      expect(scenario.telemetry.metrics.latency.history.length).toBeGreaterThan(
        0
      );
      expect(
        scenario.telemetry.metrics.packetLoss.history.length
      ).toBeGreaterThan(0);
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
      expect(scenario.activeLinks.length).toBeGreaterThanOrEqual(1);
      expectChronologicalNoFuture(scenario, scenario.activeLinks);
      expectChronologicalNoFuture(scenario, scenario.missionEvents);
      expect(Array.isArray(scenario.missionEvents)).toBe(true);
      expect(scenario.expected.route).toBeDefined();
      expect(scenario.expected.radar).toBeDefined();
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

      expect(scenario.expected.sourceFreshness.telemetry).toBe(
        latestPositionIso(scenario)
      );
      expect(scenario.expected.sourceFreshness.history).toBe(
        latestPositionIso(scenario)
      );
      expect(scenario.expected.sourceFreshness.activeLink).toBe(
        latestActiveLinkIso(scenario)
      );
      expect(scenario.expected.sourceFreshness.pois).toBe(
        scenario.pois.length === 0 ? null : scenario.nowIso
      );
      expect(scenario.expected.sourceFreshness.route).toBe(
        scenario.route.active ? scenario.nowIso : null
      );
      expect(scenario.expected.sourceFreshness.groundEntryPoint).toBe(
        scenario.groundEntryPoint.coordinate === null ? null : scenario.nowIso
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
        scenario.pois.length
      );
      expectLayerValueContainsCount(
        scenario,
        'satellites',
        scenario.satellites.length
      );
      expectLayerValueContainsCount(
        scenario,
        'mission-events',
        scenario.missionEvents.length
      );
      if (scenario.expected.sourceFreshness.radar === null) {
        expect(layerState(scenario, 'weather-radar')).toMatchObject({
          state: 'unavailable',
          availability: 'local-failure',
        });
      } else {
        expect(layerState(scenario, 'weather-radar').value).toContain(
          scenario.expected.sourceFreshness.radar
        );
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
    expect(idl.route.westernSegment.some((point) => point.longitude > 0)).toBe(
      true
    );
    expect(idl.route.easternSegment.some((point) => point.longitude < 0)).toBe(
      true
    );
    expect(countByLongitudeSign(idl.telemetry.positionHistory, 'west')).toBe(1);
    expect(countByLongitudeSign(idl.telemetry.positionHistory, 'east')).toBe(1);
    expect(layerState(idl, 'position-history-west').value).toBe(
      '1 western sample'
    );
    expect(layerState(idl, 'position-history-east').value).toBe(
      '1 eastern sample'
    );
    expect(countLinks(idl, 'normal')).toBe(1);
    expect(countLinks(idl, 'warning')).toBe(1);
    expect(
      idl.activeLinks.some(
        (link) =>
          link.from !== null &&
          link.to !== null &&
          link.from.longitude > 0 &&
          link.to.longitude < 0
      )
    ).toBe(true);
    expect(idl.expected.sourceFreshness.activeLink).toBe(
      latestActiveLinkIso(idl)
    );
    expect(layerState(idl, 'active-x-band-normal').value).toContain(
      idl.expected.sourceFreshness.activeLink
    );
    expect(layerState(idl, 'active-x-band-warning').value).toContain(
      idl.expected.sourceFreshness.activeLink
    );
    expect(latestEventIso(idl)).toBe('2026-02-03T17:05:59Z');
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
    expect(panelState(stale, 'current-position-map').state).toBe('stale');
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
    ).toEqual([170.2, 179.6]);
    expect(
      idl.route.easternSegment.map((point: Coordinate) => point.longitude)
    ).toEqual([-179.7, -165, -122.3088]);

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
      '8d814d18504d73afc3cc0d8c140740da0d9da09494a1c9a00695e4eaf33acfcb'
    );
    expect(canonical).toMatch(/2026-02-03T15:30:00Z/);
    expect(canonical).not.toMatch(/localhost|127\.0\.0\.1/);
  });
});
