import { expect, test } from '@playwright/test';

import {
  attachScreenshots,
  attachResponsiveScreenshots,
  expectAxe,
  expectCoreOverview,
  expectNoGrafana,
  expectSameOriginApi,
  expectViewportLayout,
  openOverview,
  viewports,
} from './support/overview-assertions';
import { installOverviewRouter } from './support/overview-router';

const poiTuples = [
  ['Departure & Arrival', 'departure,arrival', 'category=departure%2Carrival'],
  ['All POIs', '', ''],
  ['Departure Only', 'departure', 'category=departure'],
  ['Arrival Only', 'arrival', 'category=arrival'],
  ['Waypoints Only', 'waypoint', 'category=waypoint'],
  ['Alternates Only', 'alternate', 'category=alternate'],
] as const;

test.describe('Operations overview deterministic browser acceptance', () => {
  test.beforeEach(async ({ context }) => {
    await context.clearCookies();
  });

  test('renders the production overview contract without external Grafana traffic', async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text());
    });
    page.on('pageerror', (error) => errors.push(error.message));
    const router = await installOverviewRouter(page);

    await openOverview(page);
    await expectCoreOverview(page, router);
    await expectSameOriginApi(page);
    await expectNoGrafana(router.records);
    expect(
      errors.filter((error) => !error.includes('message: canceled'))
    ).toEqual([]);
  });

  for (const viewport of viewports) {
    test(`meets responsive acceptance at ${viewport.name} @axe`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize(viewport);
      const router = await installOverviewRouter(page);
      await openOverview(page);

      await expectViewportLayout(page, viewport.mapHeight);
      await expectAxe(page, testInfo);
      await attachResponsiveScreenshots(
        page,
        testInfo,
        `overview-${viewport.name}`
      );
      await expectCoreOverview(page, router);

      const mobile = viewport.width < 768;
      await expect(
        page.getByRole('button', { name: 'Enable map interaction' })
      ).toHaveCount(mobile ? 1 : 0);
      await expect(page.getByText(/UTC/i).first()).toBeVisible();
    });
  }

  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 390, height: 844 },
  ]) {
    test(`preserves POI filter order, URL encoding, and state at ${viewport.width}`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const router = await installOverviewRouter(page);
      await openOverview(page);
      await openControls(page);
      const select = page.getByLabel('POI category');

      await expect
        .poll(() =>
          select
            .locator('option')
            .evaluateAll((options) =>
              options.map((option) =>
                option instanceof HTMLOptionElement
                  ? [option.label, option.value]
                  : ['', '']
              )
            )
        )
        .toEqual(poiTuples.map(([label, value]) => [label, value]));
      for (const [, value, encoded] of poiTuples) {
        const marker = router.records.length;
        await select.selectOption(value);
        await expect(select).toHaveValue(value);
        const beforeRefresh = await mapState(page);
        router.markNextManualCycle();
        await page.getByRole('button', { name: 'Refresh overview' }).click();
        await expect
          .poll(() =>
            router.records
              .slice(marker)
              .some(
                (record) =>
                  record.event === 'complete' &&
                  poiRecordMatches(record.url, encoded)
              )
          )
          .toBe(true);
        await expect
          .poll(() =>
            router.records
              .slice(marker)
              .some(
                (record) =>
                  record.kind === 'manual' && record.event === 'complete'
              )
          )
          .toBe(true);
        expect(await mapState(page)).toEqual(beforeRefresh);
        await page.reload();
        await openControls(page);
        await expect(select).toHaveValue(value);
        expect((await mapState(page)).filterValue).toBe(value);
      }
    });
  }

  test('supports required keyboard path and reduced motion contract', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installOverviewRouter(page);
    await openOverview(page);
    await page.keyboard.press('Tab');
    await expect(
      page.getByRole('link', { name: 'Skip to main content' })
    ).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
    await page.getByRole('button', { name: 'Toggle navigation' }).focus();
    await page.keyboard.press('Enter');
    await page.getByRole('link', { name: 'Overview' }).focus();
    await expect(page.getByRole('link', { name: 'Overview' })).toBeFocused();
    await page.getByRole('button', { name: 'Overview controls' }).focus();
    await expect(
      page.getByRole('button', { name: 'Overview controls' })
    ).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByLabel('POI category')).toBeVisible();
    await page.getByRole('button', { name: 'Additional clocks' }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByLabel(/^Tokyo:/)).toBeVisible();
    await page.locator('summary', { hasText: 'Operational layers' }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByLabel('Weather Radar')).toBeVisible();
    await page.getByLabel('Weather Radar').focus();
    await page.keyboard.press('Space');
    await expect(page.getByLabel('Weather Radar')).not.toBeChecked();
    const summary = page.getByLabel('Map status and layer summary');
    await summary.focus();
    await page.keyboard.press('Space');
    await expect(summary).toBeFocused();
    const reduced = await page.evaluate(() => {
      const style = getComputedStyle(document.body);
      return {
        media: matchMedia('(prefers-reduced-motion: reduce)').matches,
        scrollBehavior: style.scrollBehavior,
        transitionDuration: style.transitionDuration,
        animationDuration: style.animationDuration,
      };
    });
    expect(reduced.media).toBe(true);
    expect(reduced.scrollBehavior).toBe('auto');
  });

  test('preserves overview state through deterministic kiosk fullscreen', async ({
    page,
  }, testInfo) => {
    await page.addInitScript(() => {
      let calls = 0;
      Object.defineProperty(window, '__fullscreenCallCount', {
        value: () => calls,
      });
      HTMLElement.prototype.requestFullscreen = () =>
        new Promise((_resolve, reject) => {
          calls += 1;
          reject(new Error('fullscreen unavailable'));
        });
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await installOverviewRouter(page);
    await openOverview(page);
    await openControls(page);
    await page.getByLabel('POI category').selectOption('waypoint');
    await openLayerDisclosure(page);
    await page.getByLabel('Satellites').focus();
    await page.keyboard.press('Space');
    await expectFullscreenCalls(page, 0);

    await attachScreenshots(page, testInfo, 'fullscreen-inline');
    await page.getByRole('button', { name: 'Enter fullscreen' }).click();
    await expectFullscreenCalls(page, 1);
    await expect(page.getByText('Fullscreen unavailable')).toBeVisible();
    await expect(page.locator('.overview-page--kiosk')).toBeVisible();
    await attachScreenshots(page, testInfo, 'fullscreen-kiosk');
    await expect(page.getByLabel('POI category')).toHaveValue('waypoint');
    await expect(page.getByLabel('Satellites')).not.toBeChecked();

    await page.getByRole('button', { name: 'Exit kiosk view' }).click();
    await expect(page.locator('.overview-page--inline')).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Enter fullscreen' })
    ).toBeFocused();
    await attachScreenshots(page, testInfo, 'fullscreen-exit');
  });
});

async function openLayerDisclosure(page: import('@playwright/test').Page) {
  await page.locator('details.operational-map__panel').evaluate((details) => {
    if (details instanceof HTMLDetailsElement) details.open = true;
  });
}

async function openControls(page: import('@playwright/test').Page) {
  const button = page.getByRole('button', { name: 'Overview controls' });
  if ((await button.getAttribute('aria-expanded')) !== 'true') {
    await button.click();
  }
}

async function expectFullscreenCalls(
  page: import('@playwright/test').Page,
  calls: number
) {
  await expect
    .poll(() =>
      page.evaluate(() =>
        (
          window as unknown as { __fullscreenCallCount: () => number }
        ).__fullscreenCallCount()
      )
    )
    .toBe(calls);
}

function poiRecordMatches(url: string, encoded: string): boolean {
  const parsed = new URL(url);
  if (parsed.pathname !== '/api/pois/etas') return false;
  if (encoded === '') return parsed.search === '';
  return parsed.search.slice(1) === encoded;
}

async function mapState(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const map = document.querySelector('.leaflet-container') as
      | (HTMLElement & { _leaflet_id?: number })
      | null;
    return {
      mapIdentity: map?._leaflet_id ?? null,
      center: map?.getAttribute('style') ?? '',
      filterValue:
        document.querySelector<HTMLSelectElement>(
          'select[aria-label="POI category"]'
        )?.value ?? '',
    };
  });
}
