import { expect, test, type Page } from '@playwright/test';

import {
  attachScreenshots,
  expectNoGrafana,
  openOverview,
} from './support/overview-assertions';
import {
  captureCdpContinuity,
  installElementIdentity,
} from './support/overview-cdp-capture';
import { assertContinuityEvidence } from './support/overview-cdp-assertions';
import {
  installOverviewRouter,
  type OverviewRouter,
} from './support/overview-router';

const continuityViewports = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'mobile', width: 390, height: 844 },
] as const;

test.describe('Operations overview temporal continuity', () => {
  test.describe.configure({ mode: 'serial' });

  for (const viewport of continuityViewports) {
    test(`keeps stable regions alive across scheduled and manual refreshes at ${viewport.name}`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize(viewport);
      const errors: string[] = [];
      page.on('console', (message) => {
        if (message.type() === 'error') errors.push(message.text());
      });
      page.on('pageerror', (error) => errors.push(error.message));
      const router = await installOverviewRouter(page);
      await installElementIdentity(page);
      await openOverview(page, router.scenario().nowIso);
      await settleInitialRequests(router);
      await page.getByRole('button', { name: 'Overview controls' }).click();
      await openLayerDisclosure(page);
      await page.getByRole('button', { name: 'Refresh overview' }).focus();

      const before = await sampleState(page);
      const evidence = await captureCdpContinuity(
        page,
        router,
        testInfo,
        viewport.name
      );
      await expect.poll(() => router.cycles.length).toBeGreaterThan(12);
      const after = await sampleState(page);

      assertContinuityEvidence(evidence);
      expectDistinctCycleCompletions(router, 'scheduled', 5);
      expectDistinctCycleCompletions(router, 'manual', 1);
      expect(after.boxes.every((box) => box.width > 0 && box.height > 0)).toBe(
        true
      );
      expect(after.mapNode).toBe(before.mapNode);
      expect(after.chartCount).toBeGreaterThanOrEqual(before.chartCount);
      expect(after.panelCount).toBeGreaterThanOrEqual(before.panelCount);
      expect(
        errors.filter((error) => !error.includes('message: canceled'))
      ).toEqual([]);
      await expectNoGrafana(router.records);
      await attachScreenshots(page, testInfo, `continuity-${viewport.name}`);
    });
  }

  for (const scenario of [
    'overview-no-route',
    'overview-sparse',
    'overview-backend-failure',
    'overview-stale',
    'overview-idl',
    'overview-threshold-crossing',
    'overview-radar-failure',
    'overview-recovery',
  ] as const) {
    test(`renders truthful localized state for ${scenario}`, async ({
      page,
    }) => {
      const router = await installOverviewRouter(page, scenario);
      await openOverview(page, router.scenario().nowIso);
      await settleInitialRequests(router, true);

      const visibleText = await page.locator('main').innerText();
      expect(visibleText).not.toMatch(/stack|traceback|exception|axios/i);
      await openLayerDisclosure(page);
      await expectScenarioState(page, router);
      expect(
        router.records.filter((record) => record.event === 'failed')
      ).toEqual([]);
    });
  }

  test('preserves controls across mobile rotation', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installOverviewRouter(page);
    await installElementIdentity(page);
    await openOverview(page);
    await page.getByRole('button', { name: 'Overview controls' }).click();
    await page.getByLabel('POI category').selectOption('alternate');
    await openLayerDisclosure(page);
    await page.getByLabel('Weather Radar').focus();
    await page.keyboard.press('Space');
    await page.evaluate(() => window.scrollTo(0, 40));
    const before = await rotationState(page);

    await page.setViewportSize({ width: 844, height: 390 });
    await expectRotationPreserved(page, before);
    await page.setViewportSize({ width: 390, height: 844 });
    await expectRotationPreserved(page, before);
  });
});

async function settleInitialRequests(
  router: OverviewRouter,
  includeErrors = false
) {
  await expect
    .poll(() =>
      includeErrors
        ? firstPartyTerminalCount(router)
        : firstPartyCompleteCount(router)
    )
    .toBeGreaterThan(3);
}

function firstPartyCompleteCount(router: OverviewRouter): number {
  return router.records.filter(
    (record) => record.firstParty && record.event === 'complete'
  ).length;
}

function firstPartyTerminalCount(router: OverviewRouter): number {
  return router.records.filter(
    (record) =>
      record.firstParty &&
      ['complete', 'error', 'failed', 'blocked'].includes(record.event)
  ).length;
}

async function openLayerDisclosure(page: Page) {
  await page.locator('details.operational-map__panel').evaluate((details) => {
    if (details instanceof HTMLDetailsElement) details.open = true;
  });
}

async function expectScenarioState(page: Page, router: OverviewRouter) {
  const id = router.scenario().id;
  if (id === 'overview-backend-failure') {
    await expect(page.getByText('Unavailable').first()).toBeVisible();
    expect(
      router.records.some(
        (record) =>
          record.firstParty &&
          record.event === 'error' &&
          record.status !== null &&
          record.status >= 500
      )
    ).toBe(true);
    return;
  }
  if (id === 'overview-radar-failure') {
    await expect(
      page.getByRole('button', { name: 'Retry weather radar' })
    ).toBeVisible();
    expect(
      router.records.some(
        (record) => record.source === 'radar' && record.event === 'error'
      )
    ).toBe(true);
    return;
  }
  if (id === 'overview-idl') {
    for (const layer of [
      'Planned Route — western segment',
      'Planned Route — eastern segment',
      'Active X-band Link — normal',
      'Active X-band Link — warning',
      'Position History — western segments',
      'Position History — eastern segments',
    ]) {
      await expect(
        page.getByText(new RegExp(`${layer}: visible.*1 features`, 'i'))
      ).toBeVisible();
    }
    return;
  }
  if (id === 'overview-threshold-crossing') {
    await expect(page.getByText(/Critical/i).first()).toBeVisible();
    return;
  }
  await expect(
    page.getByText(/Ready|Stale|Unavailable/i).first()
  ).toBeVisible();
}

function expectDistinctCycleCompletions(
  router: OverviewRouter,
  kind: 'scheduled' | 'manual',
  minimum: number
) {
  const cycles = new Set(
    router.records
      .filter(
        (record) =>
          record.firstParty &&
          record.kind === kind &&
          record.event === 'complete' &&
          record.source === 'telemetry'
      )
      .map((record) => record.cycle)
  );
  expect(cycles.size).toBeGreaterThanOrEqual(minimum);
}

async function sampleState(page: Page) {
  return page.evaluate(() => {
    const boxes = [
      '.overview-map-region',
      '.overview-summary-region',
      '.overview-right-rail',
    ].map((selector) => {
      const box = document.querySelector(selector)?.getBoundingClientRect();
      return { width: box?.width ?? 0, height: box?.height ?? 0 };
    });
    return {
      boxes,
      chartCount: document.querySelectorAll('canvas, svg').length,
      mapNode: document
        .querySelector('.leaflet-container')
        ?.getAttribute('class'),
      panelCount: document.querySelectorAll('section').length,
    };
  });
}

async function expectRotationPreserved(
  page: Page,
  before: Awaited<ReturnType<typeof rotationState>>
) {
  await expect
    .poll(async () => ({
      ...(await rotationState(page)),
      viewport: before.viewport,
    }))
    .toEqual(before);
  expect(before.viewport).not.toBeNull();
}

async function rotationState(page: Page) {
  return page.evaluate(() => {
    const container = document.querySelector('.leaflet-container');
    const objectId = (
      window as typeof window & {
        __overviewObjectId?: (
          value: object | null | undefined
        ) => string | null;
      }
    ).__overviewObjectId;
    return {
      mapIdentity: objectId?.(container),
      viewport: container
        ? {
            paneTransform:
              container.querySelector<HTMLElement>('.leaflet-map-pane')?.style
                .transform ?? '',
            zoomClass: [...container.classList]
              .filter((name) => name.includes('zoom'))
              .sort(),
          }
        : null,
      layers: [
        ...document.querySelectorAll<HTMLInputElement>(
          '.operational-map__layer-row input'
        ),
      ].map((input) => [input.getAttribute('aria-label'), input.checked]),
      disclosures: [...document.querySelectorAll('details')].map(
        (details) => details.open
      ),
      filter:
        document.querySelector<HTMLSelectElement>('[aria-label="POI category"]')
          ?.value ?? '',
      scroll: window.scrollY,
    };
  });
}
