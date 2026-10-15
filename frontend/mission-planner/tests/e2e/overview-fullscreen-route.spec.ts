import { expect, test, type Page } from '@playwright/test';
import type { PerspectiveCamera } from 'three';
import { projectRouteArc } from '../../src/pages/globe-route-projection';
import { syntheticFullscreenCoordinates } from '../../src/pages/synthetic-fullscreen-route.test-fixture';
import { compositionFixture } from './support/overview-composition';
import { renderedRoutePoints } from './support/overview-route-probe';
import {
  overviewCamera,
  observeOverviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';

for (const viewport of [
  { width: 1920, height: 1280 },
  { width: 2560, height: 1440 },
]) {
  test(`synthetic dateline route remains visible through fullscreen and repeated resets at ${viewport.width}`, async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(120_000);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await observeOverviewCamera(page);
    if (process.env.OVERVIEW_ROUTE_PRODUCTION === '1') {
      expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
      // The acceptance configuration selects an isolated loopback Nginx origin.
      // No API interception: upload and activate exclusively fabricated geometry.
      const coordinates = syntheticFullscreenCoordinates.map(
        ({ latitude, longitude }) => `${longitude},${latitude}`
      );
      const kml = `<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
        <name>Synthetic fullscreen framing KCCC-KDDD</name>
        <Placemark><name>KCCC</name><Point><coordinates>${coordinates[0]}</coordinates></Point></Placemark>
        <Placemark><name>KDDD</name><Point><coordinates>${coordinates.at(-1)}</coordinates></Point></Placemark>
        <Placemark><name>Synthetic route</name><LineString><coordinates>${coordinates.join(' ')}</coordinates></LineString></Placemark>
      </Document></kml>`;
      const upload = await request.post('/api/routes/upload', {
        multipart: {
          file: {
            name: 'synthetic-fullscreen-framing.kml',
            mimeType: 'application/vnd.google-earth.kml+xml',
            buffer: Buffer.from(kml),
          },
        },
      });
      expect(upload.status(), await upload.text()).toBe(201);
      const activate = await request.post(
        `/api/routes/${(await upload.json()).id}/activate`
      );
      expect(activate.status(), await activate.text()).toBe(200);
      const active = await request.get('/api/routes?active=true');
      expect(active.status()).toBe(200);
      await testInfo.attach('real-active-route', {
        body: await active.body(),
        contentType: 'application/json',
      });
    } else {
      const state = await compositionFixture(page);
      state.position = {
        ...syntheticFullscreenCoordinates[0],
        altitude: 35000,
      };
      state.satellite = null;
      state.destination = 'KDDD';
      await page.route('**/api/routes/route', (route) =>
        route.fulfill({
          json: {
            id: 'route',
            name: 'Synthetic KCCC-KDDD',
            points: syntheticFullscreenCoordinates,
          },
        })
      );
    }
    await page.setViewportSize(viewport);
    await page.goto('/overview');
    await expect(page.locator('.overview-page')).toHaveAttribute(
      'data-layout',
      'desktop'
    );
    const canvas = page.locator('.overview-globe canvas');
    await expect(canvas).toBeVisible();
    await expect.poll(() => renderedRoutePoints(page)).toHaveLength(129);
    const route = projectRouteArc(syntheticFullscreenCoordinates, 2.015, 32);
    const checkRoute = async (stage: string, fullscreen: boolean) => {
      await settledOverviewCamera(page);
      const geometry = await routeGeometry(page, route);
      for (const {
        screen: [x, y],
        surfaceDot,
      } of geometry.route) {
        expect(surfaceDot).toBeGreaterThan(4);
        expect(x).toBeGreaterThan(
          fullscreen ? geometry.opening.left : geometry.stage.left
        );
        expect(x).toBeLessThan(
          fullscreen ? geometry.opening.right : geometry.stage.right
        );
        expect(y).toBeGreaterThan(
          fullscreen ? geometry.opening.top : geometry.stage.top
        );
        expect(y).toBeLessThan(
          fullscreen ? geometry.opening.bottom : geometry.stage.bottom
        );
      }
      await testInfo.attach(`${stage}-geometry`, {
        body: JSON.stringify(geometry),
        contentType: 'application/json',
      });
      await page.screenshot({ path: testInfo.outputPath(`${stage}.png`) });
    };
    await checkRoute('initial', false);
    await page
      .getByRole('button', { name: 'Enter fullscreen overview' })
      .click();
    await page.waitForFunction(() => !!document.fullscreenElement);
    await checkRoute('fullscreen-entry', true);
    for (let reset = 1; reset <= 2; reset++) {
      const before = await overviewCamera(page);
      const box = (await canvas.boundingBox())!;
      await page.mouse.move(
        box.x + box.width * 0.65,
        box.y + box.height * 0.55
      );
      await page.mouse.down();
      await page.mouse.move(
        box.x + box.width * 0.8,
        box.y + box.height * 0.65,
        { steps: 12 }
      );
      await page.mouse.up();
      const explored = await settledOverviewCamera(page);
      expect(
        explored.position.some(
          (value, i) => Math.abs(value - before.position[i]) > 0.1
        )
      ).toBe(true);
      await page.getByRole('button', { name: 'Reset map view' }).click();
      await checkRoute(`reset-${reset}`, true);
    }
    await page.evaluate(() => document.exitFullscreen());
    await page.waitForFunction(() => !document.fullscreenElement);
    await checkRoute('fullscreen-exit', false);
  });
}

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
  const geometry = await routeGeometry(
    page,
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
  for (const {
    screen: [x, y],
    surfaceDot,
  } of geometry.route) {
    expect(surfaceDot).toBeGreaterThan(4);
    expect(x).toBeGreaterThan(geometry.opening.left);
    expect(x).toBeLessThan(geometry.opening.right);
    expect(y).toBeGreaterThan(geometry.opening.top);
    expect(y).toBeLessThan(geometry.opening.bottom);
  }
  const xs = geometry.route.map((p) => p.screen[0]);
  expect(Math.max(...xs) - Math.min(...xs)).toBeGreaterThan(
    (geometry.opening.right - geometry.opening.left) * 0.8
  );
  await page.screenshot({
    path: testInfo.outputPath('fullscreen-route-feedback.png'),
  });
  await page.evaluate(() => document.exitFullscreen());
});

async function routeGeometry(page: Page, route: [number, number, number][]) {
  return page.evaluate((route) => {
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
      ...document.querySelectorAll('.overview-map-overlays, .overview-arrival'),
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
      route: route.map((p) => ({
        screen: project(p),
        surfaceDot: camera.position
          .clone()
          .set(...p)
          .dot(camera.position),
      })),
      stage: stage.toJSON(),
      opening: {
        left: metrics.right + 20,
        right: stage.right - 20,
        top: Math.max(...upper) + 20,
        bottom: Math.min(...lower) - 20,
      },
    };
  }, route);
}
