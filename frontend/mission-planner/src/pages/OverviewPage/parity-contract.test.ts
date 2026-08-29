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

    expect(OVERVIEW_CONTRACT.mapLayers.map((layer) => layer.concept)).toEqual([
      'Weather Radar',
      'Planned Route - western segment',
      'Planned Route - eastern segment',
      'Active X-band Link - normal',
      'Active X-band Link - warning',
      'Position History - western segments',
      'Position History - eastern segments',
      'Flight route/POI markers',
      'Satellites',
      'Mission events',
      'Ground entry point',
      'Current position',
    ]);

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
    expect(OVERVIEW_CONTRACT.defaults.styles).toEqual({
      plannedRouteWest: { color: 'dark-orange', width: 2, opacity: 0.9 },
      plannedRouteEast: { color: 'dark-orange', width: 2, opacity: 1 },
      activeXBandLinkNormal: { color: 'green', width: 4, opacity: 0.9 },
      activeXBandLinkWarning: { color: 'yellow', width: 4, opacity: 0.9 },
      positionHistory: { color: 'blue', width: 3, opacity: 0.7 },
    });
    expect(OVERVIEW_CONTRACT.defaults.radar).toEqual({
      enabledByDefault: true,
      opacity: 0.7,
      minZoom: 0,
      maxZoom: 7,
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
      expect(
        scenario.telemetry.positionHistory.every((sample: PositionSample) =>
          ISO_UTC.test(sample.observedAt)
        )
      ).toBe(true);
      expect(scenario.activeLinks.length).toBeGreaterThanOrEqual(1);
      expect(
        scenario.activeLinks.every((link: ActiveLink) =>
          ISO_UTC.test(link.observedAt)
        )
      ).toBe(true);
      expect(Array.isArray(scenario.missionEvents)).toBe(true);
      expect(scenario.expected.route).toBeDefined();
      expect(scenario.expected.radar).toBeDefined();
    }
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

    const first = JSON.stringify({ OVERVIEW_CONTRACT, OVERVIEW_SCENARIOS });
    const second = JSON.stringify({ OVERVIEW_CONTRACT, OVERVIEW_SCENARIOS });

    expect(first).toBe(second);
    expect(first).toMatch(/2026-02-03T15:30:00Z/);
    expect(first).not.toMatch(/localhost|127\.0\.0\.1/);
  });
});
