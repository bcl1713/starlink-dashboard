import { expect, test } from '@playwright/test';
import { compositionFixture } from './support/overview-composition';
import {
  observeOverviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';

for (const [width, height] of [
  [1280, 853],
  [1920, 1080],
  [844, 390],
] as const) {
  test(`globe and arrival share the available center at ${width}x${height}`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const fixture = await compositionFixture(page);
    fixture.route = false;
    await observeOverviewCamera(page);
    let metrics = false,
      right = false,
      clocks = true,
      arrival = true;
    await page.route('**/api/overview-links/settings', (route) =>
      route.fulfill({
        json: {
          starshield_link_enabled: false,
          x_band_link_enabled: false,
          orbital_traffic_enabled: false,
          operational_clocks_enabled: clocks,
          arrival_panel_enabled: arrival,
          planned_satellite_panel_enabled: right,
          legend_enabled: right,
          map_status_enabled: false,
          latency_panel_enabled: metrics,
          downlink_panel_enabled: metrics,
          uplink_panel_enabled: metrics,
          packet_loss_panel_enabled: metrics,
          obstruction_panel_enabled: metrics,
        },
      })
    );
    for (const [showMetrics, showRight] of [
      [false, false],
      [true, false],
      [false, true],
      [true, true],
    ]) {
      metrics = showMetrics;
      right = showRight;
      await page.goto('/overview');
      await expect(page.locator('.overview-satellite-overlays')).toHaveCount(
        right ? 1 : 0
      );
      await expect(page.locator('.overview-metrics-overlays')).toHaveCount(
        metrics ? 1 : 0
      );
      await settledOverviewCamera(page);
      const geometry = await page.evaluate(() => {
        const box = (selector: string) =>
          document.querySelector(selector)!.getBoundingClientRect();
        const main = box('.overview-page'),
          arrival = box('.overview-arrival');
        const desktop =
          document
            .querySelector('.overview-page')!
            .getAttribute('data-layout') === 'desktop';
        const left =
          desktop && document.querySelector('.overview-metrics-overlays')
            ? box('.overview-metrics-overlays').right + 20
            : main.left + (desktop ? 20 : 12);
        const hasRight =
          !!document.querySelector('.overview-satellite-overlays') ||
          (!desktop && !!document.querySelector('.overview-metrics-overlays'));
        const right = hasRight
          ? box(desktop ? '.overview-right-overlays' : '.overview-sidebar')
              .left - (desktop ? 20 : 12)
          : main.right - (desktop ? 20 : 12);
        const roots = (
          window as unknown as {
            __overviewEvidenceRoots: Array<{
              containerInfo?: {
                getState?: () => { camera: import('three').PerspectiveCamera };
              };
            }>;
          }
        ).__overviewEvidenceRoots;
        const camera = roots.find(
          (root) => typeof root.containerInfo?.getState === 'function'
        )!.containerInfo!.getState!().camera;
        camera.updateMatrixWorld();
        const origin = camera.position.clone().set(0, 0, 0).project(camera);
        return {
          center: (left + right) / 2,
          arrivalCenter: arrival.x + arrival.width / 2,
          globeCenter: main.left + ((origin.x + 1) * main.width) / 2,
          screenCenter: main.left + main.width / 2,
        };
      });
      expect(geometry.arrivalCenter).toBeCloseTo(geometry.center, 0);
      expect(geometry.globeCenter).toBeCloseTo(geometry.center, 0);
      if (!metrics && !right)
        expect(geometry.center).toBeCloseTo(geometry.screenCenter, 0);
      await expect(
        page.getByRole('button', { name: 'Reset map view', exact: true })
      ).toBeVisible();
      await page.screenshot({
        path: info.outputPath(`metrics-${metrics}-right-${right}.png`),
      });
    }
    clocks = false;
    for (arrival of [true, false]) {
      metrics = right = false;
      await page.goto('/overview');
      await expect(page.locator('.overview-top-overlays')).toHaveCount(0);
      await expect(page.locator('.overview-arrival-overlays')).toHaveCount(
        arrival ? 1 : 0
      );
      const reset = await page.locator('.overview-map-controls').boundingBox();
      const opening = await page.locator('.overview-map-opening').boundingBox();
      if (width === 844) expect(reset!.y).toBeCloseTo(opening!.y, 0);
    }
  });
}
