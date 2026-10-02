import { expect, test } from '@playwright/test';
import type { PerspectiveCamera } from 'three';
import { projectRouteArc } from '../../src/pages/globe-route-projection';
import { compositionFixture } from './support/overview-composition';
import {
  observeOverviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';

test('fullscreen keeps Earth centered and fits a coast-to-coast route in the right opening', async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await observeOverviewCamera(page);
  await compositionFixture(page);
  const points = [
    { latitude: 32.87, longitude: -117.14 },
    { latitude: 38.81, longitude: -76.87 },
  ];
  await page.route('**/api/routes/route', (route) =>
    route.fulfill({ json: { id: 'route', name: 'KNKX to KADW', points } })
  );
  await page.setViewportSize({ width: 1920, height: 1280 });
  await page.goto('/overview');
  await settledOverviewCamera(page);
  await page.getByRole('button', { name: 'Enter fullscreen overview' }).click();
  await page.waitForFunction(() => !!document.fullscreenElement);
  await settledOverviewCamera(page);
  const geometry = await page.evaluate(
    (route) => {
      const roots = (
        window as unknown as {
          __overviewEvidenceRoots: Array<{
            containerInfo?: {
              getState?: () => {
                camera: PerspectiveCamera;
                gl: { domElement: HTMLCanvasElement };
              };
            };
          }>;
        }
      ).__overviewEvidenceRoots;
      const container = roots.find(
        (root) =>
          typeof root.containerInfo?.getState === 'function' &&
          document.contains(root.containerInfo.getState().gl.domElement)
      )?.containerInfo;
      if (!container?.getState) throw new Error('Renderer store unavailable');
      const camera = container.getState().camera;
      const stage = document
        .querySelector('.overview-map-stage')!
        .getBoundingClientRect();
      const metrics = document
        .querySelector('.overview-metrics-overlays')!
        .getBoundingClientRect();
      const upper = [
        ...document.querySelectorAll(
          '.overview-satellite-overlays, .overview-map-controls, .overview-top-overlays'
        ),
      ].map((el) => el.getBoundingClientRect().bottom);
      const lower = [
        ...document.querySelectorAll(
          '.overview-map-overlays, .overview-arrival'
        ),
      ].map((el) => el.getBoundingClientRect().top);
      camera.updateMatrixWorld();
      const project = (p: number[]) => {
        const vector = camera.position
          .clone()
          .set(...p)
          .project(camera);
        return [
          stage.x + ((vector.x + 1) * stage.width) / 2,
          stage.y + ((1 - vector.y) * stage.height) / 2,
        ];
      };
      return {
        earth: project([0, 0, 0]),
        route: route.map(project),
        stage: stage.toJSON(),
        opening: {
          left: metrics.right + 20,
          right: stage.right - 20,
          top: Math.max(...upper) + 20,
          bottom: Math.min(...lower) - 20,
        },
      };
    },
    projectRouteArc(points, 2.015, 32)
  );
  expect(geometry.earth[0]).toBeCloseTo(
    geometry.stage.x + geometry.stage.width / 2,
    1
  );
  expect(geometry.earth[1]).toBeCloseTo(
    geometry.stage.y + geometry.stage.height / 2,
    1
  );
  for (const [x, y] of geometry.route) {
    expect(x).toBeGreaterThan(geometry.opening.left);
    expect(x).toBeLessThan(geometry.opening.right);
    expect(y).toBeGreaterThan(geometry.opening.top);
    expect(y).toBeLessThan(geometry.opening.bottom);
  }
  const xs = geometry.route.map((p) => p[0]);
  expect(Math.max(...xs) - Math.min(...xs)).toBeGreaterThan(
    (geometry.opening.right - geometry.opening.left) * 0.8
  );
  await page.screenshot({
    path: testInfo.outputPath('fullscreen-route-feedback.png'),
  });
  await page.evaluate(() => document.exitFullscreen());
});
