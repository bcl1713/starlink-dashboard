import { expect, test } from '@playwright/test';

import { OVERVIEW_CONTRACT } from './fixtures/overview';
import {
  attachScreenshots,
  expectAxe,
  expectCoreOverview,
  expectNoGrafana,
  expectSameOriginApi,
  expectViewportLayout,
  openOverview,
  viewports,
} from './support/overview-assertions';
import { installOverviewRouter } from './support/overview-router';

test.describe('Operations overview deterministic browser acceptance', () => {
  test.beforeEach(async ({ context }) => {
    await context.clearCookies();
  });

  test.afterEach(async ({ page }) => {
    await page.close();
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
      await expectCoreOverview(page, router);
      await expectAxe(page, testInfo);
      await attachScreenshots(page, testInfo, `overview-${viewport.name}`);

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
                option instanceof HTMLOptionElement ? option.value : ''
              )
            )
        )
        .toEqual(OVERVIEW_CONTRACT.poiOptions.map((option) => option.value));
      for (const option of OVERVIEW_CONTRACT.poiOptions) {
        const marker = router.records.length;
        await select.selectOption(option.value);
        await expect(select).toHaveValue(option.value);
        await expect
          .poll(() =>
            router.records
              .slice(marker)
              .some((record) =>
                poiRecordMatches(record.url, option.query.category)
              )
          )
          .toBe(true);
        await page.reload();
        await openControls(page);
        await expect(select).toHaveValue(option.value);
      }
    });
  }

  test('preserves overview state through deterministic kiosk fullscreen', async ({
    page,
  }, testInfo) => {
    await page.addInitScript(() => {
      HTMLElement.prototype.requestFullscreen = () =>
        Promise.reject(new Error('fullscreen unavailable'));
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await installOverviewRouter(page);
    await openOverview(page);
    await openControls(page);
    await page.getByLabel('POI category').selectOption('waypoint');
    await openLayerDisclosure(page);
    await page.getByLabel('Satellites').focus();
    await page.keyboard.press('Space');

    await attachScreenshots(page, testInfo, 'fullscreen-inline');
    await page.getByRole('button', { name: 'Enter fullscreen' }).click();
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

function poiRecordMatches(url: string, category: string | undefined): boolean {
  const parsed = new URL(url);
  if (parsed.pathname !== '/api/pois/etas') return false;
  if (category === undefined) return !parsed.searchParams.has('category');
  return parsed.searchParams.get('category') === category;
}
