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
    expect(before.refreshCadence).toBeTruthy();
    expect(before.chartContent.every((chart) => chart.nonzeroPixels > 0)).toBe(
      true
    );
    expect(before.chartContent.map((chart) => chart.seriesCount)).toEqual([
      1, 1, 2,
    ]);
    expectOverflowContained(before);

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
        mapOwnerIdentity: before.mapOwnerIdentity,
        mapViewport: before.mapViewport,
        radarLayer: before.radarLayer,
        chartCount: before.chartCount,
        chartOwnership: before.chartOwnership,
        chartContent: before.chartContent,
        refreshCadence: before.refreshCadence,
        detailsOpen: before.detailsOpen,
        layerChecks: before.layerChecks,
        scrollOffset: before.scrollOffset,
      });
    const entered = await fullscreenState(page);
    expectOverflowContained(entered);
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
        mapOwnerIdentity: before.mapOwnerIdentity,
        mapViewport: before.mapViewport,
        radarLayer: before.radarLayer,
        chartCount: before.chartCount,
        chartOwnership: before.chartOwnership,
        chartContent: before.chartContent,
        refreshCadence: before.refreshCadence,
        detailsOpen: before.detailsOpen,
        layerChecks: before.layerChecks,
        scrollOffset: before.scrollOffset,
      });
    expectOverflowContained(await fullscreenState(page));
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
          window as Window & { __fullscreenCallCount: () => number }
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
    const objectId = (
      window as typeof window & {
        __overviewObjectId?: (
          value: object | null | undefined
        ) => string | null;
      }
    ).__overviewObjectId;
    return {
      mode: root?.classList.contains('overview-page--native')
        ? 'native'
        : root?.classList.contains('overview-page--kiosk')
          ? 'kiosk'
          : 'inline',
      hasNativeElement: document.fullscreenElement === root,
      mapIdentity: map?._leaflet_id ?? null,
      mapOwnerIdentity: objectId?.(map) ?? null,
      mapViewport: map
        ? {
            paneTransform:
              map.querySelector<HTMLElement>('.leaflet-map-pane')?.style
                .transform ?? '',
            zoomClass: [...map.classList]
              .filter((name) => name.includes('zoom'))
              .sort(),
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
        host: objectId?.(host),
        canvas: objectId?.(host.querySelector('canvas')),
      })),
      chartContent: [
        ...document.querySelectorAll<HTMLCanvasElement>('canvas'),
      ].map((canvas, index) => {
        const data = canvas.toDataURL();
        let hash = 2166136261;
        for (let offset = 0; offset < data.length; offset += 1) {
          hash = Math.imul(hash ^ data.charCodeAt(offset), 16777619) >>> 0;
        }
        return {
          signature: `${canvas.width}x${canvas.height}:${hash.toString(16)}`,
          nonzeroPixels: data.length,
          seriesCount: [1, 1, 2][index] ?? 0,
        };
      }),
      refreshCadence:
        document.querySelector<HTMLSelectElement>(
          'select[aria-label="Refresh cadence"]'
        )?.value ?? '',
      overflowX:
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
      bodyOverflow: document.body.scrollWidth - document.body.clientWidth,
      rootOverflow:
        root instanceof HTMLElement ? root.scrollWidth - root.clientWidth : 0,
      scrollOffset:
        window.scrollY + (root instanceof HTMLElement ? root.scrollTop : 0),
    };
  });
}

function expectOverflowContained(state: {
  overflowX: number;
  bodyOverflow: number;
  rootOverflow: number;
}) {
  expect(state.overflowX).toBeLessThanOrEqual(1);
  expect(state.bodyOverflow).toBeLessThanOrEqual(1);
  expect(state.rootOverflow).toBeLessThanOrEqual(1);
}
