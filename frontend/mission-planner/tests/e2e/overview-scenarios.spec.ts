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
    await manualRefresh(page, router);
    await expect(
      page.getByText(/Showing retained last-good data/i).first()
    ).toBeVisible();
    await expect(page.getByText('Seattle, WA').first()).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Network Latency' })
    ).toBeVisible();

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

    router.failNextBasemap();
    await page.reload();
    await openLayerDisclosure(page);
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

    router.setScenario('overview-recovery');
    await manualRefresh(page, router);
    await expect(
      page.getByText(/Network metrics recovered|Ready/i).first()
    ).toBeVisible();
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
