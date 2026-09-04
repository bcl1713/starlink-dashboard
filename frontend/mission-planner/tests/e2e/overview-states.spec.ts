import { expect, test } from '@playwright/test';
import { installOverviewRoutes } from './overview-fixtures';
import {
  enterOverviewFullscreen,
  measureOverviewFrame,
} from './overview-geometry';

test.describe('Operations overview resilient states', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
  });

  test('partial failure keeps last-good data and production tree identity', async ({
    page,
  }) => {
    const routes = await installOverviewRoutes(page);
    await page.goto('/overview');
    await expect(page.getByText('27.0 ms', { exact: true })).toBeVisible();
    await expect(
      page.getByText('Waypoint 5 with safe operational label')
    ).toBeVisible();
    const root = page.getByTestId('overview-root');
    const rootHandle = await root.elementHandle();
    const mapHandle = await page
      .locator('.current-position-map')
      .elementHandle();
    await page.getByLabel('Refresh cadence').selectOption('5');

    routes.setFailed('status', true);
    routes.setFailed('pois', true);
    routes.setFailed('gep', true);
    await page.getByRole('button', { name: 'Refresh live status' }).click();
    await page.getByRole('button', { name: 'Refresh POIs' }).click();
    await page
      .getByRole('button', { name: 'Refresh ground entry point' })
      .click();
    await expect(page.getByText(/Live status unavailable/)).toBeVisible();
    await expect(
      page.getByText(/Points of interest unavailable/)
    ).toBeVisible();
    await expect(
      page.getByText(/Ground entry point unavailable/)
    ).toBeVisible();
    await expect(page.getByText('27.0 ms', { exact: true })).toBeVisible();
    await expect(
      page.getByText('Waypoint 5 with safe operational label')
    ).toBeVisible();

    await enterOverviewFullscreen(page);
    const dimensions = await measureOverviewFrame(page);
    await page.getByRole('button', { name: 'Exit fullscreen' }).click();
    await expect
      .poll(() => page.evaluate(() => document.fullscreenElement))
      .toBeNull();

    await root.evaluate((element) => {
      element.requestFullscreen = () => Promise.reject(new Error('denied'));
    });
    await page.getByRole('button', { name: 'Enter fullscreen' }).click();
    await expect(page.getByRole('status')).toContainText(
      'Fullscreen was unavailable'
    );
    await expect(
      page.getByRole('button', { name: 'Enter fullscreen' })
    ).toBeFocused();
    await expect(page.getByLabel('Refresh cadence')).toHaveValue('5');
    await expect(page.getByText('27.0 ms', { exact: true })).toBeVisible();
    expect(
      await page.evaluate(
        ({ root, map }) =>
          document.querySelector('[data-testid="overview-root"]') === root &&
          document.querySelector('.current-position-map') === map,
        { root: rootHandle, map: mapHandle }
      )
    ).toBe(true);
    process.stdout.write(
      `OVERVIEW_PARTIAL_FAILURE_GEOMETRY ${JSON.stringify(dimensions)}\n`
    );
  });

  test('total source failure remains complete in fullscreen', async ({
    page,
  }) => {
    await installOverviewRoutes(page, {
      failedSources: ['status', 'pois', 'gep'],
    });
    await page.goto('/overview');
    await expect(page.getByText(/Live status unavailable/)).toBeVisible();
    await expect(page.getByText('No applicable POIs')).toBeVisible();
    await expect(
      page.getByText('Unavailable', { exact: true }).first()
    ).toBeVisible();

    await enterOverviewFullscreen(page);
    const dimensions = await measureOverviewFrame(page);
    process.stdout.write(
      `OVERVIEW_TOTAL_FAILURE_GEOMETRY ${JSON.stringify(dimensions)}\n`
    );
  });

  test('stale content and browser zoom keep controls reachable', async ({
    page,
  }) => {
    await installOverviewRoutes(page, { staleStatus: true });
    await page.goto('/overview');
    await expect(page.getByText('Live status is stale')).toBeVisible();
    await enterOverviewFullscreen(page);
    await measureOverviewFrame(page);

    const session = await page.context().newCDPSession(page);
    try {
      await session.send('Emulation.setDeviceMetricsOverride', {
        width: 1536,
        height: 864,
        screenWidth: 1920,
        screenHeight: 1080,
        deviceScaleFactor: 1.25,
        mobile: false,
      });
      expect(
        await page.evaluate(() => ({
          width: innerWidth,
          height: innerHeight,
          ratio: devicePixelRatio,
        }))
      ).toEqual({ width: 1536, height: 864, ratio: 1.25 });
      await expect(
        page.getByRole('button', { name: 'Refresh live status' })
      ).toBeVisible();
      await expect(page.getByLabel('Refresh cadence')).toBeVisible();
    } finally {
      await session.detach();
    }
  });
});
