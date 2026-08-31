import { expect, test, type Page } from '@playwright/test';

import { openOverview } from './support/overview-assertions';
import { installElementIdentity } from './support/overview-cdp-capture';
import { installOverviewRouter } from './support/overview-router';

test('preserves full overview state in kiosk fullscreen fallback', async ({
  page,
}) => {
  await page.addInitScript(() => {
    HTMLElement.prototype.requestFullscreen = () =>
      Promise.reject(new Error('fullscreen unavailable'));
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await installOverviewRouter(page);
  await installElementIdentity(page);
  await openOverview(page);
  await openControls(page);
  await page.getByLabel('POI category').selectOption('waypoint');
  await openLayerDisclosure(page);
  await page.getByLabel('Weather Radar').uncheck();
  await page.evaluate(() => window.scrollTo(0, 32));
  const before = await fullscreenState(page);
  expect(before.refreshCadence).toBeTruthy();
  expect(before.chartContent.every((chart) => chart.nonzeroPixels > 0)).toBe(
    true
  );
  expect(before.chartContent.map((chart) => chart.seriesCount)).toEqual([
    1, 1, 2,
  ]);
  expectOverflowContained(before);

  await page.getByRole('button', { name: 'Enter fullscreen' }).click();
  await expect(page.locator('.overview-page--kiosk')).toBeVisible();
  await expect(page.locator('.overview-page')).toBeFocused();
  await expect
    .poll(() => fullscreenState(page))
    .toMatchObject({
      mode: 'kiosk',
      poiFilter: 'waypoint',
      layerChecks: before.layerChecks,
      detailsOpen: before.detailsOpen,
      chartCount: before.chartCount,
      chartOwnership: before.chartOwnership,
      chartContent: before.chartContent,
      refreshCadence: before.refreshCadence,
      mapOwnerIdentity: before.mapOwnerIdentity,
      mapViewport: before.mapViewport,
      scrollOffset: before.scrollOffset,
    });
  const entered = await fullscreenState(page);
  expectOverflowContained(entered);
  expect(entered.scrollOffset).toBe(before.scrollOffset);

  await page.getByRole('button', { name: 'Exit kiosk view' }).click();
  await expect(page.locator('.overview-page--inline')).toBeVisible();
  await expect
    .poll(() => fullscreenState(page))
    .toMatchObject({
      mode: 'inline',
      poiFilter: before.poiFilter,
      layerChecks: before.layerChecks,
      detailsOpen: before.detailsOpen,
      chartOwnership: before.chartOwnership,
      chartContent: before.chartContent,
      refreshCadence: before.refreshCadence,
      mapOwnerIdentity: before.mapOwnerIdentity,
      mapViewport: before.mapViewport,
      scrollOffset: before.scrollOffset,
    });
  await expect(
    page.getByRole('button', { name: 'Enter fullscreen' })
  ).toBeFocused();
  expectOverflowContained(await fullscreenState(page));
});

async function openControls(page: Page) {
  const button = page.getByRole('button', { name: 'Overview controls' });
  if ((await button.getAttribute('aria-expanded')) !== 'true') {
    await button.click();
  }
}

async function openLayerDisclosure(page: Page) {
  await page.locator('details.operational-map__panel').evaluate((details) => {
    if (details instanceof HTMLDetailsElement) details.open = true;
  });
}

async function fullscreenState(page: Page) {
  return page.evaluate(() => {
    const root = document.querySelector('.overview-page');
    const map = document.querySelector<HTMLElement>('.leaflet-container');
    const objectId = (
      window as typeof window & {
        __overviewObjectId?: (
          value: object | null | undefined
        ) => string | null;
      }
    ).__overviewObjectId;

    return {
      mode: root?.classList.contains('overview-page--kiosk')
        ? 'kiosk'
        : 'inline',
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
