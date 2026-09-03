import { expect, test } from '@playwright/test';
import { installOverviewRoutes } from './overview-fixtures';
import {
  enterOverviewFullscreen,
  measureOverviewGeometry,
  overviewInventoryNames,
} from './overview-geometry';

test.describe('Operations overview display', () => {
  test('1920x1080 fullscreen keeps the complete readable inventory in one screen', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    const statusCount = await installOverviewRoutes(page);
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    await page.goto('/overview');
    await expect(
      page.getByText('Waypoint 5 with safe operational label')
    ).toBeVisible();
    await expect(page.getByText('27.0 ms', { exact: true })).toBeVisible();
    await expect(
      page.getByText('21.0 / 27.0 / 33.0 ms', { exact: true })
    ).toBeVisible();
    await expect(
      page.getByText('Average 0.5% · Max 0.8%', { exact: true })
    ).toBeVisible();
    const mapBeforeEntry = await page
      .locator('.current-position-map')
      .elementHandle();
    await page.getByLabel('Refresh cadence').selectOption('paused');
    const root = await enterOverviewFullscreen(page);
    await expect(root).toBeFocused();
    expect(
      await page.evaluate(
        (map) => document.querySelector('.current-position-map') === map,
        mapBeforeEntry
      )
    ).toBe(true);
    expect(
      await page
        .getByLabel('Refresh cadence')
        .locator('option')
        .allTextContents()
    ).toEqual([
      '1 second',
      '2 second',
      '5 second',
      '10 second',
      '30 second',
      'Paused',
    ]);

    const geometry = await measureOverviewGeometry(page, {
      selectedInterval: 'Selected interval: Paused',
      freshness: /Updated|stale/,
    });
    process.stdout.write(
      `OVERVIEW_GEOMETRY ${JSON.stringify({
        dimensions: geometry.dimensions,
        inventory: geometry.inventory.map((box, index) => ({
          name: overviewInventoryNames[index],
          ...box,
        })),
      })}\n`
    );
    if (process.env.OVERVIEW_SCREENSHOT) {
      await page.screenshot({
        path: process.env.OVERVIEW_SCREENSHOT,
        fullPage: false,
      });
    }
    const beforeManual = statusCount();
    await page.getByRole('button', { name: 'Refresh live status' }).click();
    await expect.poll(statusCount).toBe(beforeManual + 1);
    await page.waitForTimeout(500);
    expect(statusCount()).toBe(beforeManual + 1);
    expect(consoleErrors).toEqual([]);

    await page.getByRole('button', { name: 'Exit fullscreen' }).click();
    await expect
      .poll(() => page.evaluate(() => document.fullscreenElement))
      .toBeNull();
    await expect(
      page.getByRole('button', { name: 'Enter fullscreen' })
    ).toBeFocused();
    await expect(page.getByLabel('Refresh cadence')).toHaveValue('paused');
  });

  test('fullscreen rejection leaves the overview usable with a visible fallback', async ({
    page,
  }) => {
    await installOverviewRoutes(page);
    await page.addInitScript(() => {
      Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
        configurable: true,
        value: () => Promise.reject(new Error('denied by browser policy')),
      });
    });
    await page.goto('/overview');
    await page.getByRole('button', { name: 'Enter fullscreen' }).click();

    await expect(page.getByRole('status')).toContainText(
      'Fullscreen was unavailable'
    );
    await expect(page.getByLabel('Refresh cadence')).toHaveValue('1');
    await expect(
      page.getByRole('button', { name: 'Refresh live status' })
    ).toBeVisible();
    expect(await page.evaluate(() => document.fullscreenElement)).toBeNull();
  });

  test('normal desktop and narrow layouts keep controls reachable without horizontal overflow', async ({
    page,
  }) => {
    await installOverviewRoutes(page);
    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto('/overview');
      await expect(
        page.getByRole('button', { name: 'Enter fullscreen' })
      ).toBeVisible();
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth
      );
      expect(overflow).toBeLessThanOrEqual(0);
    }
  });
});
