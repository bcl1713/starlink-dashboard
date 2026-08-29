import { describe, expect, it } from 'vitest';

import {
  OVERVIEW_CONTRACT,
  OVERVIEW_SCENARIOS,
  buildPoiQuery,
} from '../../../tests/e2e/fixtures/overview';

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

describe('operations overview parity contract', () => {
  it('freezes the approved scenario inventory', () => {
    expect(OVERVIEW_SCENARIOS.map((scenario) => scenario.name)).toEqual(
      EXPECTED_SCENARIOS
    );
    expect(OVERVIEW_SCENARIOS.map((scenario) => scenario.id)).toEqual(
      EXPECTED_SCENARIO_IDS
    );

    for (const scenario of OVERVIEW_SCENARIOS) {
      expect(scenario.nowIso).toMatch(/Z$/);
      expect(scenario.expected.panelStates).toHaveLength(
        OVERVIEW_CONTRACT.panels.length
      );
      expect(Object.keys(scenario.expected.sourceFreshness)).toEqual([
        'telemetry',
        'route',
        'pois',
        'radar',
        'satellites',
        'groundEntryPoint',
      ]);
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
      'Planned Route — western segment',
      'Planned Route — eastern segment',
      'Active X-band Link — normal',
      'Active X-band Link — warning',
      'Position History — western segments',
      'Position History — eastern segments',
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

  it('freezes timing, threshold, style, and basemap defaults', () => {
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
        plannedRoute: { color: 'dark-orange', width: 2, opacity: 0.9 },
        activeXBandLinkNormal: { color: 'green', width: 4 },
        activeXBandLinkWarning: { color: 'yellow', width: 4 },
        positionHistory: { color: 'blue', width: 3, opacity: 0.7 },
      },
      basemap: { attribution: 'Tiles © Esri' },
    });
  });

  it('documents that All POIs omits the category query parameter', () => {
    expect(buildPoiQuery('')).toEqual({});
    expect(buildPoiQuery('departure,arrival')).toEqual({
      category: 'departure,arrival',
    });
  });

  it('keeps fixture data deterministic and explicit', () => {
    const serialized = JSON.stringify({
      OVERVIEW_CONTRACT,
      OVERVIEW_SCENARIOS,
    });

    expect(serialized).not.toMatch(
      /Date\\.now|Math\\.random|localhost|process\\.env/
    );
    expect(OVERVIEW_SCENARIOS.every((scenario) => scenario.route.id)).toBe(
      true
    );
    expect(
      OVERVIEW_SCENARIOS.every((scenario) =>
        scenario.expected.panelStates.every((state) =>
          OVERVIEW_CONTRACT.panels.some((panel) => panel.id === state.panelId)
        )
      )
    ).toBe(true);
  });
});
