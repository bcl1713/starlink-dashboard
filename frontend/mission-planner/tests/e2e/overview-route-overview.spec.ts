import { expect, test, type Page } from '@playwright/test';
import { compositionFixture } from './support/overview-composition';
import {
  observeOverviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';
import { globePosition } from '../../src/pages/globe-coordinates';

// Fully invented geometry. No imported mission coordinates or operator artifacts.
const crossing = [
  { latitude: 58, longitude: -135 },
  { latitude: 50, longitude: 170 },
  { latitude: 25, longitude: 140 },
  { latitude: 5, longitude: 115 },
];
async function aircraftGeometry(
  page: Page,
  coordinate: (typeof crossing)[number]
) {
  return page.evaluate(
    (point) => {
      const roots = (
        window as unknown as {
          __overviewEvidenceRoots: Array<{
            containerInfo?: {
              getState?: () => {
                camera: import('three').PerspectiveCamera;
                gl: { domElement: HTMLCanvasElement };
              };
            };
          }>;
        }
      ).__overviewEvidenceRoots;
      const state = roots.find(
        (root) =>
          typeof root.containerInfo?.getState === 'function' &&
          document.contains(root.containerInfo.getState().gl.domElement)
      )!.containerInfo!.getState!();
      const { camera, gl } = state;
      camera.updateMatrixWorld();
      const v = camera.position.clone().set(...point);
      const surfaceDot = v.dot(camera.position);
      v.project(camera);
      const stage = gl.domElement.getBoundingClientRect();
      const x = stage.x + ((v.x + 1) * stage.width) / 2;
      const y = stage.y + ((1 - v.y) * stage.height) / 2;
      const panels = [
        ...document.querySelectorAll(
          '.overview-metrics-overlays, .overview-top-overlays, .overview-satellite-overlays, .overview-map-controls, .overview-map-overlays, .overview-arrival'
        ),
      ]
        .map((el) => el.getBoundingClientRect())
        .filter((b) => b.width > 0 && b.height > 0);
      return {
        x,
        y,
        surfaceDot,
        inStage:
          x > stage.left + 12 &&
          x < stage.right - 12 &&
          y > stage.top + 12 &&
          y < stage.bottom - 12,
        covered: panels.some(
          (b) =>
            x > b.left - 12 &&
            x < b.right + 12 &&
            y > b.top - 12 &&
            y < b.bottom + 12
        ),
      };
    },
    globePosition(coordinate.latitude, coordinate.longitude, 2.04)
  );
}

for (const viewport of [
  { width: 1920, height: 1280 },
  { width: 1024, height: 600 },
  { width: 390, height: 844 },
]) {
  test(`route overview keeps a fabricated crossing and aircraft clear through repeated resets at ${viewport.width}`, async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(120_000);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await observeOverviewCamera(page);
    if (process.env.OVERVIEW_ROUTE_PRODUCTION === '1') {
      expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
      const coordinates = crossing.map((p) => `${p.longitude},${p.latitude}`);
      const kml = `<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Fabricated KXXA-KXXB</name>
        <Placemark><name>KXXA</name><Point><coordinates>${coordinates[0]}</coordinates></Point></Placemark>
        <Placemark><name>KXXB</name><Point><coordinates>${coordinates.at(-1)}</coordinates></Point></Placemark>
        <Placemark><LineString><coordinates>${coordinates.join(' ')}</coordinates></LineString></Placemark></Document></kml>`;
      const upload = await request.post('/api/routes/upload', {
        multipart: {
          file: {
            name: 'fabricated-route-overview.kml',
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
    } else {
      const state = await compositionFixture(page);
      state.position = { ...crossing[0], altitude: 35000 };
      state.satellite = null;
      await page.route('**/api/routes/route', (route) =>
        route.fulfill({
          json: { id: 'route', name: 'Fabricated crossing', points: crossing },
        })
      );
    }
    await page.setViewportSize(viewport);
    await page.goto('/overview');
    for (const fullscreen of [false, true]) {
      if (fullscreen) {
        await page
          .getByRole('button', { name: 'Enter fullscreen overview' })
          .click();
        await page.waitForFunction(() => !!document.fullscreenElement);
      }
      for (let reset = 0; reset < 2; reset++) {
        await page.getByRole('button', { name: 'Reset map view' }).click();
        await expect(
          page.getByText('Route overview', { exact: true })
        ).toBeVisible();
        await settledOverviewCamera(page);
        const coordinate =
          process.env.OVERVIEW_ROUTE_PRODUCTION === '1'
            ? (await (await request.get('/api/status')).json()).position
            : crossing[0];
        const geometry = await aircraftGeometry(page, coordinate);
        expect(geometry.inStage).toBe(true);
        expect(geometry.covered).toBe(false);
        expect(geometry.surfaceDot).toBeGreaterThan(4.5);
        await testInfo.attach(`aircraft-${fullscreen}-${reset}`, {
          body: JSON.stringify(geometry),
          contentType: 'application/json',
        });
        const canvas = page.locator('.overview-globe canvas');
        if (viewport.width !== 1920)
          await page
            .getByRole('button', { name: 'Explore map', exact: true })
            .click();
        const box = (await canvas.boundingBox())!;
        const x =
          viewport.width === 1920
            ? box.x + box.width * 0.65
            : box.x + box.width * 0.35;
        await page.mouse.move(x, box.y + box.height * 0.6);
        await page.mouse.down();
        await page.mouse.move(x + 35, box.y + box.height * 0.65, { steps: 5 });
        await page.mouse.up();
        await expect(
          page.getByText('Route overview', { exact: true })
        ).toHaveCount(0);
      }
      await page.screenshot({
        path: testInfo.outputPath(`fabricated-crossing-${fullscreen}.png`),
      });
    }
    await page.evaluate(() => document.exitFullscreen());
  });
}

test('route overview adjusts to aircraft movement while manual exploration stays still', async ({
  page,
}) => {
  test.skip(
    process.env.OVERVIEW_ROUTE_PRODUCTION === '1',
    'Moving status is a controlled API fixture; production checks use real status.'
  );
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1920, height: 1280 });
  await observeOverviewCamera(page);
  const state = await compositionFixture(page);
  const points = Array.from({ length: 65 }, (_, i) => ({
    latitude: 0,
    longitude: ((i * 5 + 180) % 360) - 180,
  }));
  state.position = { latitude: 0, longitude: 90, altitude: 35000 };
  state.satellite = null;
  await page.route('**/api/routes/route', (route) =>
    route.fulfill({
      json: { id: 'route', name: 'Fabricated extended arc', points },
    })
  );
  await page.goto('/overview');
  await page.getByRole('button', { name: 'Reset map view' }).click();
  await settledOverviewCamera(page);
  state.position = { latitude: 0, longitude: -125, altitude: 35000 };
  await expect
    .poll(
      async () => {
        const geometry = await aircraftGeometry(page, state.position!);
        return (
          geometry.inStage && !geometry.covered && geometry.surfaceDot > 4.5
        );
      },
      { timeout: 20_000 }
    )
    .toBe(true);
  const canvas = (await page.locator('.overview-globe canvas').boundingBox())!;
  await page.mouse.move(
    canvas.x + canvas.width * 0.65,
    canvas.y + canvas.height * 0.6
  );
  await page.mouse.wheel(0, 100);
  await expect(page.getByText('Route overview', { exact: true })).toHaveCount(
    0
  );
  const manual = await settledOverviewCamera(page);
  state.position = { latitude: 0, longitude: 0, altitude: 35000 };
  await page.waitForTimeout(2200);
  const after = await settledOverviewCamera(page);
  for (let i = 0; i < 3; i++)
    expect(after.position[i]).toBeCloseTo(manual.position[i], 3);
  await page.getByRole('button', { name: 'Reset map view' }).click();
  await settledOverviewCamera(page);
  expect((await aircraftGeometry(page, state.position)).covered).toBe(false);
  const reset = await aircraftGeometry(page, state.position);
  expect(reset.inStage).toBe(true);
  expect(reset.surfaceDot).toBeGreaterThan(4.5);
});
