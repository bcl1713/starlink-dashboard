import { expect, type Page } from '@playwright/test';

import type { OverviewRouter } from './overview-router';

export async function expectScenarioOracle(page: Page, router: OverviewRouter) {
  const expected = router.scenario().expected;
  const main = page.locator('main');
  if (router.scenario().id === 'overview-backend-failure') {
    await expect(main).toContainText(/Source refresh failed/i);
    return;
  }
  for (const id of expected.topFivePoiIds) {
    const poi = router.scenario().pois.items.find((item) => item.id === id);
    if (poi) await expect(main).toContainText(poi.name);
  }
  for (const layer of expected.layerStates) {
    const summary = page.getByText(
      new RegExp(`${escapeRegExp(layerLabel(layer.id))}:`)
    );
    await expect(summary).toHaveCount(1);
    await expect(summary).toContainText(/\d+ features/);
    await expect(summary).toContainText(
      layer.availability === 'empty'
        ? /ready|unavailable/i
        : layerStatePattern(layer.state)
    );
  }
  for (const panel of expected.panelStates) {
    const token = panel.value.match(/[A-Za-z]{3,}|\d+(?:[.,]\d+)?/)?.[0];
    expect(token, `panel ${panel.id} expected value`).toBeTruthy();
    if (token) await expect(main).toContainText(token);
    expect(['ok', 'warning', 'critical', 'stale', 'unavailable']).toContain(
      panel.state
    );
  }
  const scenario = router.scenario();
  const sourceFreshness =
    scenario.id === 'overview-backend-failure'
      ? Object.fromEntries(
          Object.keys(expected.sourceFreshness).map((key) => [key, null])
        )
      : {
          telemetry: scenario.telemetry.currentObservedAt,
          history:
            scenario.telemetry.positionHistory.at(-1)?.observedAt ??
            scenario.telemetry.currentObservedAt,
          activeLink: scenario.activeLinks[0]?.observedAt ?? null,
          pois: scenario.pois.generatedAt,
          route: scenario.route.revisionAt,
          groundEntryPoint: scenario.groundEntryPoint.observedAt,
          radar: scenario.radar.frameAt,
        };
  expect(expected.sourceFreshness).toEqual(sourceFreshness);
  expect(expected.route).toEqual({
    state: scenario.route.active ? 'ok' : 'unavailable',
    westernPointCount: scenario.route.westernSegment.length,
    easternPointCount: scenario.route.easternSegment.length,
    crossesInternationalDateLine: scenario.route.crossesInternationalDateLine,
  });
  expect(expected.radar.state).toMatch(/ok|warning|critical|stale|unavailable/);
  expect(expected.radar.frameState).toMatch(
    /available|unavailable|local-failure/
  );
}

function layerStatePattern(state: string) {
  if (state === 'ok') return /ready/i;
  if (state === 'unavailable') return /error|unavailable/i;
  return new RegExp(state, 'i');
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function layerLabel(id: string): string {
  return (
    {
      'weather-radar': 'Weather Radar',
      'planned-route-west': 'Planned Route — western segment',
      'planned-route-east': 'Planned Route — eastern segment',
      'active-x-band-normal': 'Active X-band Link — normal',
      'active-x-band-warning': 'Active X-band Link — warning',
      'position-history-west': 'Position History — western segments',
      'position-history-east': 'Position History — eastern segments',
      'flight-route-markers': 'Flight route/POI markers',
      satellites: 'Satellites',
      'mission-events': 'Mission events',
      'ground-entry-point-layer': 'Ground entry point',
      'current-position-layer': 'Current position',
    }[id] ?? id
  );
}
