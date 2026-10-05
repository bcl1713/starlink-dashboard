import { expect, type Browser, type TestInfo } from '@playwright/test';
import {
  observeOverviewCamera,
  settledOverviewCamera,
} from './overview-camera';

/** Each native fullscreen window starts at its actual laptop dimensions. */
export async function verifyRunLaptopFullscreen(
  browser: Browser,
  info: TestInfo
) {
  for (const size of [
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
  ]) {
    const laptop = await browser.browserType().launch({
      args: [`--window-size=${size.width},${size.height}`],
    });
    try {
      const context = await laptop.newContext({
        baseURL: process.env.SIMULATION_ACCEPTANCE_BASE_URL,
        viewport: size,
        screen: size,
      });
      const page = await context.newPage();
      await observeOverviewCamera(page);
      await page.goto('/overview');
      await expect(page.getByLabel('Simulation clock')).toBeVisible();
      await page
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
      await expect
        .poll(() => page.evaluate(() => Boolean(document.fullscreenElement)))
        .toBe(true);
      await expect(page.locator('.overview-page')).toHaveAttribute(
        'data-layout',
        'landscape'
      );
      await expect
        .poll(() =>
          page.evaluate(() => ({
            width: innerWidth,
            height: innerHeight,
          }))
        )
        .toEqual(size);
      await expect
        .poll(() =>
          page.evaluate(() => {
            const dashboard = document.querySelector('.overview-page')!;
            return dashboard.scrollHeight <= dashboard.clientHeight + 1;
          })
        )
        .toBe(true);
      await expect(page.getByLabel('Simulation run')).toHaveCount(0);
      await expect(page.getByLabel('Overview metric history')).toHaveCount(0);
      await settledOverviewCamera(page);
      await page.screenshot({
        path: info.outputPath(`running-fullscreen-${size.width}.png`),
      });
    } finally {
      await laptop.close();
    }
  }
}
