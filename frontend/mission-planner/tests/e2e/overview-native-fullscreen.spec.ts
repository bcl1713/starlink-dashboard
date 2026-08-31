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
    await page.evaluate(() => window.scrollTo(0, 24));
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
        mapObjectIdentity: before.mapObjectIdentity,
        mapViewport: before.mapViewport,
        radarLayer: before.radarLayer,
        chartCount: before.chartCount,
        chartOwnership: before.chartOwnership,
        detailsOpen: before.detailsOpen,
        layerChecks: before.layerChecks,
        scrollOffset: before.scrollOffset,
      });
    const entered = await fullscreenState(page);
    expect(entered.overflowX).toBeLessThanOrEqual(1);
    expect(entered.bodyOverflow).toBeLessThanOrEqual(1);
    expect(entered.scrollOffset).toBeGreaterThanOrEqual(0);
    await expect(page.locator('.overview-page')).toBeFocused();
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
        mapObjectIdentity: before.mapObjectIdentity,
        mapViewport: before.mapViewport,
        radarLayer: before.radarLayer,
        chartCount: before.chartCount,
        chartOwnership: before.chartOwnership,
        detailsOpen: before.detailsOpen,
        layerChecks: before.layerChecks,
        scrollOffset: before.scrollOffset,
      });
    expect((await fullscreenState(page)).overflowX).toBeLessThanOrEqual(1);
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
    type MapProbe = {
      getCenter(): { lat: number; lng: number };
      getZoom(): number;
    };
    const map = document.querySelector('.leaflet-container') as
      | (HTMLElement & {
          _leaflet_id?: number;
          __overviewLeafletMap?: MapProbe;
        })
      | null;
    const root = document.querySelector('.overview-page');
    const objectId = (
      window as typeof window & {
        __overviewObjectId?: (
          value: object | null | undefined
        ) => string | null;
      }
    ).__overviewObjectId;
    const mapObject = map?.__overviewLeafletMap;
    const center = mapObject?.getCenter();
    return {
      mode: root?.classList.contains('overview-page--native')
        ? 'native'
        : root?.classList.contains('overview-page--kiosk')
          ? 'kiosk'
          : 'inline',
      hasNativeElement: document.fullscreenElement === root,
      mapIdentity: map?._leaflet_id ?? null,
      mapObjectIdentity: objectId?.(mapObject) ?? null,
      mapViewport:
        center && mapObject
          ? {
              latitude: center.lat,
              longitude: center.lng,
              zoom: mapObject.getZoom(),
            }
          : null,
      poiFilter:
        document.querySelector<HTMLSelectElement>(
          'select[aria-label="POI category"]'
        )?.value ?? '',
      satelliteLayer:
        document.querySelector<HTMLInputElement>(
          'input[aria-label="Satellites"]'
        )?.checked ?? null,
      radarLayer:
        document.querySelector<HTMLInputElement>(
          'input[aria-label="Weather Radar"]'
        )?.checked ?? null,
      detailsOpen: [...document.querySelectorAll('details')].map(
        (details) => details.open
      ),
      layerChecks: [
        ...document.querySelectorAll<HTMLInputElement>(
          '.operational-map__layer-row input'
        ),
      ].map((input) => [input.getAttribute('aria-label'), input.checked]),
      chartCount: document.querySelectorAll('canvas').length,
      chartOwnership: [
        ...document.querySelectorAll<HTMLElement>(
          '[data-testid="time-series-chart-host"]'
        ),
      ].map((host) => ({
        plot: objectId?.(
          (host as HTMLElement & { __overviewUPlot?: object }).__overviewUPlot
        ),
        canvas: objectId?.(host.querySelector('canvas')),
      })),
      overflowX:
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
      bodyOverflow: document.body.scrollWidth - document.body.clientWidth,
      scrollOffset:
        window.scrollY + (root instanceof HTMLElement ? root.scrollTop : 0),
    };
  });
}
