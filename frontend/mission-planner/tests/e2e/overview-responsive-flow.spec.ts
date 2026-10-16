import { expect, test } from '@playwright/test';
import { compositionFixture } from './support/overview-composition';
import {
  observeOverviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';

for (const [width, height, mode] of [
  [1920, 1080, 'desktop'],
  [1920, 900, 'landscape'],
  [1366, 768, 'landscape'],
  [1100, 600, 'landscape'],
  [1024, 768, 'stacked'],
  [844, 390, 'stacked'],
  [390, 844, 'stacked'],
  [390, 568, 'stacked'],
  [360, 800, 'stacked'],
] as const) {
  test(`${width}x${height} keeps the map stable through legend disclosure`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await compositionFixture(page);
    await observeOverviewCamera(page);
    await page.goto('/overview');
    const main = page.locator('.overview-page');
    await expect(main).toHaveAttribute('data-layout', mode);
    await expect(page.locator('[data-metric-panel] .uplot')).toHaveCount(5);
    await settledOverviewCamera(page);
    const globe = page.locator('.overview-globe');
    const geometry = () =>
      globe.evaluate((el) => {
        const box = el.getBoundingClientRect();
        return {
          x: box.x,
          y: box.y + document.querySelector('.app-route-content')!.scrollTop,
          width: box.width,
          height: box.height,
        };
      });
    const before = await geometry();
    const canvas = await globe.locator('canvas').elementHandle();
    const dashboard = await main.boundingBox();
    expect(before.width).toBeCloseTo(dashboard!.width, 0);
    expect(before.height).toBeCloseTo(dashboard!.height, 0);
    const actions = await page
      .locator('.overview-map-toolbar button')
      .evaluateAll((nodes) =>
        nodes
          .filter((node) => node.getBoundingClientRect().width > 0)
          .map((node) => node.getBoundingClientRect().toJSON())
      );
    expect(actions).toHaveLength(mode === 'desktop' ? 2 : 3);
    for (const action of actions) {
      expect(action.height).toBeCloseTo(actions[0].height, 0);
      expect(action.width).toBeCloseTo(actions[0].width, 0);
      expect(action.y).toBeCloseTo(actions[0].y, 0);
    }

    expect(before!.width).toBeGreaterThan(250);
    expect(before!.height).toBeGreaterThan(200);
    if (width === 844 && height === 390) {
      const controls = await page
        .locator('.overview-right-overlays')
        .boundingBox();
      const map = await globe.boundingBox();
      const opening = await page.locator('.overview-map-opening').boundingBox();
      expect(controls!.x).toBeGreaterThanOrEqual(opening!.x + opening!.width);
      expect(map!.width).toBe(width);
      await expect(
        page.locator('.overview-sidebar [data-metric-panel]')
      ).toHaveCount(5);
      const arrival = await page
        .locator('.overview-arrival-overlays')
        .boundingBox();
      const clocks = await page.locator('.overview-top-overlays').boundingBox();
      expect(arrival!.y + arrival!.height).toBeLessThanOrEqual(height);
      expect(clocks!.y).toBeGreaterThanOrEqual(0);
      expect(map!.height).toBeGreaterThan(height * 0.75);
    }
    if (mode !== 'stacked') {
      expect(before!.height).toBeGreaterThan(height * 0.45);
      expect(
        await main.evaluate((el) => el.scrollHeight <= el.clientHeight + 1)
      ).toBe(true);
    }
    if (mode === 'desktop') {
      const reset = await page.locator('.overview-map-controls').boundingBox();
      const fullscreen = await page
        .locator('.overview-fullscreen-control')
        .boundingBox();
      const legend = await page.locator('.overview-map-overlays').boundingBox();
      expect(fullscreen!.y).toBeCloseTo(reset!.y, 0);
      expect(reset!.y + reset!.height).toBeLessThanOrEqual(legend!.y);
      const stage = await page.locator('.overview-map-stage').boundingBox();
      expect(legend!.y + legend!.height).toBeCloseTo(
        stage!.y + stage!.height - 20,
        0
      );
      expect(
        await page.locator('.overview-arrival').evaluate((el) => {
          const box = el.getBoundingClientRect();
          const hit = document.elementFromPoint(
            box.x + box.width / 2,
            box.y + Math.min(box.height / 2, 40)
          );
          return hit !== null && el.contains(hit);
        })
      ).toBe(true);
    }
    if (mode !== 'desktop') {
      const legend = page.getByRole('button', { name: 'Legend', exact: true });
      for (const expanded of ['true', 'false', 'true', 'false']) {
        await legend.click();
        await expect(legend).toHaveAttribute('aria-expanded', expanded);
        await expect(main).toHaveAttribute('data-layout', mode);
        expect(await geometry()).toEqual(before);
        expect(await canvas!.evaluate((el) => el.isConnected)).toBe(true);
        if (width === 844 && expanded === 'true') {
          const rail = page.locator('.overview-sidebar');
          await rail.hover();
          await page.mouse.wheel(0, 600);
          await expect
            .poll(() => rail.evaluate((el) => el.scrollTop))
            .toBeGreaterThan(0);
          await page
            .locator('.globe-legend li')
            .last()
            .scrollIntoViewIfNeeded();
          await expect(
            page.locator('.globe-legend li').last()
          ).toBeInViewport();
          expect(await geometry()).toEqual(before);
        }
      }
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth
      )
    ).toBe(true);
    const boxes = await page
      .locator(
        '.overview-planned-satellite, .overview-arrival, .overview-map-controls, .overview-display-controls, .globe-legend'
      )
      .evaluateAll((nodes) =>
        nodes.flatMap((el) => {
          const rect = el.getBoundingClientRect();
          let { left, right, top, bottom } = rect;
          for (let parent = el.parentElement; parent; parent = parent.parentElement) {
            const style = getComputedStyle(parent);
            if (style.display === 'contents') continue;
            const clip = parent.getBoundingClientRect();
            if (/auto|scroll|hidden|clip/.test(style.overflowX)) {
              left = Math.max(left, clip.left);
              right = Math.min(right, clip.right);
            }
            if (/auto|scroll|hidden|clip/.test(style.overflowY)) {
              top = Math.max(top, clip.top);
              bottom = Math.min(bottom, clip.bottom);
            }
          }
          return right > left && bottom > top
            ? [{ left, right, top, bottom }]
            : [];
        })
      );
    for (let i = 0; i < boxes.length; i++) {
      const a = boxes[i];
      for (const b of boxes.slice(i + 1)) {
        expect(
          a.left < b.right - 1 &&
            a.right > b.left + 1 &&
            a.top < b.bottom - 1 &&
            a.bottom > b.top + 1
        ).toBe(false);
      }
    }
    await globe.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: info.outputPath('layout.png'),
      fullPage: true,
    });
  });
}

test('automatic and reset views retain route framing through rotation and resizing', async ({
  page,
}) => {
  await compositionFixture(page);
  await observeOverviewCamera(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/overview');
  const canvas = await page.locator('.overview-globe canvas').elementHandle();
  for (const reset of [false, true]) {
    if (reset)
      await page
        .getByRole('button', { name: 'Reset map view', exact: true })
        .click();
    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 390, height: 844 },
      { width: 390, height: 568 },
      { width: 844, height: 390 },
      { width: 1920, height: 1080 },
    ]) {
      await page.setViewportSize(viewport);
      await settledOverviewCamera(page);
      expect(await canvas!.evaluate((el) => el.isConnected)).toBe(true);
      const projected = await page.evaluate(() => {
        const roots = (
          window as unknown as {
            __overviewEvidenceRoots: Array<{
              containerInfo?: {
                getState?: () => {
                  camera: import('three').PerspectiveCamera;
                  size: { width: number; height: number };
                  gl: { domElement: HTMLCanvasElement };
                };
              };
            }>;
          }
        ).__overviewEvidenceRoots;
        const state = roots
          .find(
            (root) =>
              typeof root.containerInfo?.getState === 'function' &&
              document.contains(root.containerInfo.getState().gl.domElement)
          )
          .containerInfo.getState();
        const { camera, size } = state;
        camera.updateMatrixWorld();
        return [
          [35, -100],
          [38, -90],
          [45, -80],
        ].map(([latitude, longitude]) => {
          const phi = (latitude * Math.PI) / 180;
          const theta = (longitude * Math.PI) / 180;
          const point = camera.position
            .clone()
            .set(
              2.015 * Math.cos(phi) * Math.cos(theta),
              2.015 * Math.sin(phi),
              -2.015 * Math.cos(phi) * Math.sin(theta)
            )
            .project(camera);
          const x = ((point.x + 1) * size.width) / 2;
          const y = ((1 - point.y) * size.height) / 2;
          const globe = state.gl.domElement.getBoundingClientRect();
          const panels = [
            ...document.querySelectorAll(
              '.overview-top-overlays, .overview-metrics-overlays, .overview-right-overlays, .overview-arrival-overlays'
            ),
          ].map((el) => el.getBoundingClientRect());
          return {
            x,
            y,
            width: size.width,
            height: size.height,
            covered: panels.some(
              (box) =>
                x + globe.left > box.left - 12 &&
                x + globe.left < box.right + 12 &&
                y + globe.top > box.top - 12 &&
                y + globe.top < box.bottom + 12
            ),
          };
        });
      });
      for (const point of projected) {
        expect(point.covered).toBe(false);
        expect(point.x).toBeGreaterThanOrEqual(12);
        expect(point.x).toBeLessThanOrEqual(point.width - 12);
        expect(point.y).toBeGreaterThanOrEqual(12);
        expect(point.y).toBeLessThanOrEqual(point.height - 12);
      }
    }
  }
});

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
  { width: 844, height: 390 },
  { width: 1920, height: 1080 },
]) {
  test(`hidden groups release their space at ${viewport.width}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await compositionFixture(page);
    let hidden = false;
    await page.route('**/api/overview-links/settings', (route) =>
      route.fulfill({
        json: {
          starshield_link_enabled: false,
          x_band_link_enabled: false,
          orbital_traffic_enabled: false,
          operational_clocks_enabled: !hidden,
          arrival_panel_enabled: !hidden,
          planned_satellite_panel_enabled: !hidden,
          legend_enabled: !hidden,
          latency_panel_enabled: !hidden,
          downlink_panel_enabled: !hidden,
          uplink_panel_enabled: !hidden,
          packet_loss_panel_enabled: !hidden,
          obstruction_panel_enabled: !hidden,
        },
      })
    );
    await page.goto('/overview');
    await expect(page.locator('.overview-top-overlays')).toHaveCount(1);
    const initialWidth = (await page.locator('.overview-globe').boundingBox())!
      .width;
    hidden = true;
    await page.reload();
    await expect(page.locator('.overview-top-overlays')).toHaveCount(0);
    await expect(page.locator('.overview-metrics-overlays')).toHaveCount(0);
    await expect(page.locator('.overview-arrival-overlays')).toHaveCount(0);
    await expect(page.locator('.overview-satellite-overlays')).toHaveCount(0);
    await expect(page.locator('.globe-legend')).toHaveCount(0);
    await expect(
      page.getByRole('button', { name: 'Reset map view', exact: true })
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Enter fullscreen overview' })
    ).toBeVisible();
    if (viewport.width === 844) {
      const stage = await page.locator('.overview-map-stage').boundingBox();
      const globe = await page.locator('.overview-globe').boundingBox();
      expect(stage!.height).toBeCloseTo(globe!.height, 0);
    }
    if (viewport.width === 1440) {
      await expect
        .poll(
          async () =>
            (await page.locator('.overview-globe').boundingBox())!.width
        )
        .toBeGreaterThanOrEqual(initialWidth);
      expect(
        (await page.locator('.overview-map-stage').boundingBox())!.y
      ).toBeLessThan(90);
    }
  });
}
