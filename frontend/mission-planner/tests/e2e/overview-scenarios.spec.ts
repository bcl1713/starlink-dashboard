import { expect, test, type Page } from '@playwright/test';

import { openOverview } from './support/overview-assertions';
import {
  installOverviewRouter,
  type OverviewRouter,
} from './support/overview-router';

test.describe('Operations overview production state transitions', () => {
  test('executes localized failure, stale recovery, radar retry, and basemap recovery', async ({
    page,
  }) => {
    const router = await installOverviewRouter(page);
    await openOverview(page, router.scenario().nowIso);
    await settleInitialRequests(router);
    await openLayerDisclosure(page);
    await expect(page.getByText('Seattle, WA').first()).toBeVisible();

    router.failSourceOnce('groundEntryPoint', 503, 'localized_gep_error');
    const gepMarker = router.records.length;
    await manualRefresh(page, router);
    await expect(
      page.getByText(/Showing retained last-good data/i).first()
    ).toBeVisible();
    await expect(page.getByText('Seattle, WA').first()).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Network Latency' })
    ).toBeVisible();
    expect(
      router.records
        .slice(gepMarker)
        .some(
          (record) =>
            record.source === 'groundEntryPoint' &&
            record.kind === 'manual' &&
            record.event === 'error' &&
            record.status === 503
        )
    ).toBe(true);

    router.setScenario('overview-radar-failure');
    await manualRefresh(page, router);
    await expect(
      page.getByRole('button', { name: 'Retry weather radar' })
    ).toBeVisible();
    router.setScenario('overview-nominal');
    await page.getByRole('button', { name: 'Retry weather radar' }).focus();
    await page.keyboard.press('Enter');
    await expect(
      page.getByRole('button', { name: 'Retry weather radar' })
    ).toHaveCount(0);

    for (let index = 0; index < 16; index += 1) router.failNextBasemap();
    await page.reload();
    await openLayerDisclosure(page);
    await expect(page.getByText(/Unable to load basemap tiles/i)).toBeVisible();
    expect(hasRecord(router, 'basemap', 'error')).toBe(true);
    await page.reload();
    await openLayerDisclosure(page);
    expect(hasRecord(router, 'basemap', 'complete')).toBe(true);
  });

  test('renders per-source stale state and fresh recovery', async ({
    page,
  }) => {
    const router = await installOverviewRouter(page, 'overview-stale');
    await openOverview(page, router.scenario().nowIso);
    await settleInitialRequests(router);
    await openLayerDisclosure(page);
    await expect(page.locator('main')).toContainText(/stale/i);
    await expectScenarioOracle(page, router);

    router.setScenario('overview-recovery');
    await manualRefresh(page, router);
    await expect(
      page.getByText(/Network metrics recovered|Ready/i).first()
    ).toBeVisible();
    await expectScenarioOracle(page, router);
  });

  test('renders a genuinely empty production response without stale features', async ({
    page,
  }) => {
    const router = await installOverviewRouter(page, 'overview-empty');
    await openOverview(page, router.scenario().nowIso);
    await settleInitialRequests(router);
    await openLayerDisclosure(page);

    await expect(
      page
        .getByLabel('POI quick reference table scroll area')
        .locator('tbody tr')
    ).toHaveCount(0);
    await expect
      .poll(() =>
        router.records.some(
          (record) => record.source === 'radar' && record.event === 'error'
        )
      )
      .toBe(true);
    await page.getByLabel('Weather Radar').uncheck();
    await expect(
      page.getByText(/Weather Radar: hidden,.*0 features/i)
    ).toBeVisible();
    const layerCounts = await page
      .locator('.operational-map__summary li')
      .evaluateAll((items) =>
        items.map(
          (item) => item.textContent?.match(/(\d+) features/)?.[1] ?? ''
        )
      );
    expect(layerCounts).toHaveLength(12);
    expect(layerCounts.every((count) => count === '0')).toBe(true);
    await expect(page.locator('main')).toContainText('Unavailable');
  });

  test('retains last-good content through a total 503 cycle and recovery', async ({
    page,
  }) => {
    const router = await installOverviewRouter(page);
    await openOverview(page, router.scenario().nowIso);
    await settleInitialRequests(router);
    await expect(page.getByText('Seattle, WA').first()).toBeVisible();

    router.setScenario('overview-backend-failure');
    const failureMarker = router.records.length;
    await manualRefresh(page, router, true);
    await expect(page.getByText('Seattle, WA').first()).toBeVisible();
    await expect(page.locator('main')).toContainText(/last-good|Unavailable/i);
    expect(
      router.records
        .slice(failureMarker)
        .some(
          (record) =>
            record.kind === 'manual' &&
            record.firstParty &&
            record.event === 'error' &&
            record.status === 503
        )
    ).toBe(true);

    router.setScenario('overview-nominal');
    await manualRefresh(page, router);
    await expect(page.getByText('Seattle, WA').first()).toBeVisible();
    await expect(page.getByText(/Ready/i).first()).toBeVisible();
  });

  test('renders exact latency warning and critical threshold transitions', async ({
    page,
  }) => {
    const router = await installOverviewRouter(page);
    await openOverview(page, router.scenario().nowIso);
    await settleInitialRequests(router);

    router.setLatency({
      currentMs: 100,
      history: [
        { observedAt: '2026-02-03T15:29:55Z', value: 98 },
        { observedAt: '2026-02-03T15:29:57Z', value: 100 },
      ],
    });
    await manualRefresh(page, router);
    await expect(page.getByText(/Current 100 ms/i).first()).toBeVisible();
    await expect(page.getByText('Warning').first()).toBeVisible();

    router.setLatency({
      currentMs: 200,
      history: [
        { observedAt: '2026-02-03T15:29:55Z', value: 100 },
        { observedAt: '2026-02-03T15:29:57Z', value: 200 },
      ],
    });
    await manualRefresh(page, router);
    await expect(page.getByText(/Current 200 ms/i).first()).toBeVisible();
    await expect(page.getByText('Critical').first()).toBeVisible();
  });
});

test.describe('Operations overview fixture oracles', () => {
  for (const scenario of [
    'overview-no-route',
    'overview-backend-failure',
    'overview-idl',
    'overview-radar-failure',
  ] as const) {
    test(`renders exact production values for ${scenario}`, async ({
      page,
    }) => {
      const router = await installOverviewRouter(page, scenario);
      await openOverview(page, router.scenario().nowIso);
      await settleInitialRequests(router);
      await openLayerDisclosure(page);
      await expectScenarioOracle(page, router);
    });
  }
});

async function settleInitialRequests(router: OverviewRouter) {
  await expect
    .poll(
      () =>
        router.records.filter((record) => record.event === 'complete').length
    )
    .toBeGreaterThan(3);
}

async function openLayerDisclosure(page: Page) {
  await page.locator('details.operational-map__panel').evaluate((details) => {
    if (details instanceof HTMLDetailsElement) details.open = true;
  });
}

async function openControls(page: Page) {
  const controls = page.getByRole('button', { name: 'Overview controls' });
  if ((await controls.getAttribute('aria-expanded')) !== 'true') {
    await controls.click();
  }
}

async function manualRefresh(
  page: Page,
  router: OverviewRouter,
  allowFailure = false
) {
  const marker = router.records.length;
  await openControls(page);
  router.markNextManualCycle();
  await page.getByRole('button', { name: 'Refresh overview' }).click();
  await expect
    .poll(() =>
      router.records
        .slice(marker)
        .some((record) => record.kind === 'manual' && record.event !== 'start')
    )
    .toBe(true);
  await expect
    .poll(() =>
      router.records
        .slice(marker)
        .some(
          (record) =>
            record.kind === 'manual' &&
            record.source === 'history' &&
            (record.event === 'complete' ||
              (allowFailure && record.event === 'error'))
        )
    )
    .toBe(true);
}

function hasRecord(
  router: OverviewRouter,
  source: string,
  event: 'complete' | 'error'
): boolean {
  return router.records.some(
    (record) => record.source === source && record.event === event
  );
}

async function expectScenarioOracle(page: Page, router: OverviewRouter) {
  const expected = router.scenario().expected;
  const main = page.locator('main');
  for (const id of expected.topFivePoiIds) {
    const poi = router.scenario().pois.items.find((item) => item.id === id);
    if (poi) await expect(main).toContainText(poi.name);
  }
  for (const layer of expected.layerStates) {
    await expect(
      page.getByText(new RegExp(`${escapeRegExp(layerLabel(layer.id))}:`))
    ).toHaveCount(1);
  }
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
