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
      mapObjectIdentity: before.mapObjectIdentity,
      mapViewport: before.mapViewport,
      scrollOffset: before.scrollOffset,
    });
  const entered = await fullscreenState(page);
  expect(entered.overflowX).toBeLessThanOrEqual(1);
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
      mapObjectIdentity: before.mapObjectIdentity,
      mapViewport: before.mapViewport,
      scrollOffset: before.scrollOffset,
    });
  await expect(
    page.getByRole('button', { name: 'Enter fullscreen' })
  ).toBeFocused();
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
    const map = document.querySelector('.leaflet-container') as
      | (HTMLElement & {
          __overviewLeafletMap?: {
            getCenter(): { lat: number; lng: number };
            getZoom(): number;
          };
        })
      | null;
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
      mode: root?.classList.contains('overview-page--kiosk')
        ? 'kiosk'
        : 'inline',
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
      scrollOffset:
        window.scrollY + (root instanceof HTMLElement ? root.scrollTop : 0),
    };
  });
}
