import { expect, test } from '@playwright/test';

import {
  attachScreenshots,
  expectNoGrafana,
  openOverview,
} from './support/overview-assertions';
import { installElementIdentity } from './support/overview-cdp-capture';
import { installOverviewRouter } from './support/overview-router';

test.describe('Operations overview native fullscreen browser contract', () => {
  test('enters and exits native fullscreen from a real user click', async ({
    page,
  }, testInfo) => {
    await page.addInitScript(() => {
      let calls = 0;
      const nativeRequest = HTMLElement.prototype.requestFullscreen;
      HTMLElement.prototype.requestFullscreen = function requestFullscreen(
        options?: FullscreenOptions
      ) {
        calls += 1;
        return nativeRequest.call(this, options);
      };
      Object.defineProperty(window, '__fullscreenCallCount', {
        value: () => calls,
      });
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    const router = await installOverviewRouter(page);
    await installElementIdentity(page);
    await openOverview(page);
    await page.getByRole('button', { name: 'Overview controls' }).click();
    await page.getByLabel('POI category').selectOption('alternate');
    await openLayerDisclosure(page);
    await page.getByLabel('Satellites').uncheck();
    const before = await fullscreenState(page);

    await expectFullscreenCalls(page, 0);
    await page.getByRole('button', { name: 'Enter fullscreen' }).click();
    await expectFullscreenCalls(page, 1);
    await expect
      .poll(() => fullscreenState(page))
      .toMatchObject({
        mode: 'native',
        hasNativeElement: true,
        poiFilter: 'alternate',
        satelliteLayer: false,
        mapIdentity: before.mapIdentity,
      });
    await attachScreenshots(page, testInfo, 'native-fullscreen');

    await page.getByRole('button', { name: 'Exit fullscreen' }).click();
    await expect
      .poll(() => fullscreenState(page))
      .toMatchObject({
        mode: 'inline',
        hasNativeElement: false,
        poiFilter: 'alternate',
        satelliteLayer: false,
        mapIdentity: before.mapIdentity,
      });
    await expect(
      page.getByRole('button', { name: 'Enter fullscreen' })
    ).toBeFocused();
    await expectNoGrafana(router.records);
  });
});

async function openLayerDisclosure(page: import('@playwright/test').Page) {
  await page.locator('details.operational-map__panel').evaluate((details) => {
    if (details instanceof HTMLDetailsElement) details.open = true;
  });
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

async function fullscreenState(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const map = document.querySelector('.leaflet-container') as
      | (HTMLElement & { _leaflet_id?: number })
      | null;
    const root = document.querySelector('.overview-page');
    return {
      mode: root?.classList.contains('overview-page--native')
        ? 'native'
        : root?.classList.contains('overview-page--kiosk')
          ? 'kiosk'
          : 'inline',
      hasNativeElement: document.fullscreenElement === root,
      mapIdentity: map?._leaflet_id ?? null,
      poiFilter:
        document.querySelector<HTMLSelectElement>(
          'select[aria-label="POI category"]'
        )?.value ?? '',
      satelliteLayer:
        document.querySelector<HTMLInputElement>(
          'input[aria-label="Satellites"]'
        )?.checked ?? null,
      chartCount: document.querySelectorAll('canvas').length,
      overflowX:
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    };
  });
}
