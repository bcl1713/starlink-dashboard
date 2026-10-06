import { writeFile } from 'node:fs/promises';
import { adsbSettings } from '../../src/test/adsb-fixtures';
import { freshContact, installAdsbFixture } from './support/adsb-fixture';
import { makeCatalog } from '../../../../tools/acceptance/journeys/orbital-traffic-fixtures.mjs';
import { expect, test, type Page } from '@playwright/test';
import {
  observeOverviewCamera,
  settledOverviewCamera,
  expectSameCamera,
} from './support/overview-camera';

async function scene(page: Page) {
  return page.evaluate(() => {
    const roots = (
      window as unknown as {
        __overviewEvidenceRoots: Array<{
          containerInfo?: {
            getState?: () => {
              gl: {
                domElement: HTMLCanvasElement;
                info: {
                  memory: { geometries: number };
                  render: { calls: number; triangles: number };
                };
              };
              scene: {
                traverse: (
                  fn: (o: {
                    name: string;
                    geometry?: {
                      attributes: { position?: { count: number } };
                      type: string;
                      parameters?: { radius?: number };
                    };
                    material?: { depthTest: boolean; depthWrite: boolean };
                  }) => void
                ) => void;
              };
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
      ?.containerInfo?.getState?.();
    if (!state) return { borders: [], geometries: 0, calls: 0 };
    let earth = false;
    const borders: {
      name: string;
      count: number;
      depthTest?: boolean;
      depthWrite?: boolean;
    }[] = [];
    state.scene.traverse((o) => {
      if (
        o.geometry?.type === 'SphereGeometry' &&
        o.geometry.parameters?.radius === 2
      )
        earth = true;
      if (o.name.startsWith('overview-boundaries-'))
        borders.push({
          name: o.name,
          count: (o.geometry?.attributes.position?.count ?? 0) / 2,
          depthTest: o.material?.depthTest,
          depthWrite: o.material?.depthWrite,
        });
    });
    return {
      borders,
      earth,
      geometries: state.gl.info.memory.geometries,
      calls: state.gl.info.render.calls,
    };
  });
}
async function legend(page: Page) {
  const toggle = page.getByRole('button', { name: 'Legend', exact: true });
  if (
    (await toggle.isVisible()) &&
    (await toggle.getAttribute('aria-expanded')) === 'false'
  )
    await toggle.click();
  return page.getByLabel('Globe legend');
}
async function toggle(
  editing: Page,
  overview: Page,
  label: string,
  kind: string,
  enabled: boolean
) {
  const control = editing.getByRole('switch', { name: label, exact: true });
  await expect(control).toBeEnabled();
  const saved = editing.waitForResponse(
    (response) =>
      response.url().endsWith('/api/overview-links/settings') &&
      response.request().method() === 'PUT'
  );
  await control.click();
  const response = await saved;
  await expect(control).toHaveJSProperty('checked', enabled);
  expect(response.status()).toBe(200);
  expect(response.headers().server).toMatch(/nginx/);
  const started = Date.now();
  await expect
    .poll(
      async () =>
        (await scene(overview)).borders.some((line) =>
          line.name.startsWith(`overview-boundaries-${kind}`)
        ),
      { timeout: 6500 }
    )
    .toBe(enabled);
  return Date.now() - started;
}

async function frameSample(page: Page) {
  await page.bringToFront();
  await expect
    .poll(() => page.evaluate(() => document.visibilityState))
    .toBe('visible');
  return page.evaluate(
    () =>
      new Promise<number[]>((resolve) => {
        const values: number[] = [];
        let previous = performance.now();
        function frame(now: number) {
          values.push(now - previous);
          previous = now;
          if (values.length >= 30) resolve(values.slice(1));
          else requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      })
  );
}
function frameStats(times: number[]) {
  const sorted = [...times].sort((a, b) => a - b);
  return {
    median: sorted[Math.floor(sorted.length / 2)],
    p95: sorted[Math.floor(sorted.length * 0.95)],
  };
}

for (const mode of ['desktop', 'fullscreen', 'mobile'] as const) {
  test.describe(mode, () => {
    test.use({ deviceScaleFactor: mode === 'mobile' ? 2 : 1 });
    test(`real saved borders reach ${mode} Overview without mission, reload or camera reset`, async ({
      context,
      request,
    }, info) => {
      if (mode === 'mobile') await context.setDefaultTimeout(20_000);
      const reset = await request.put('/api/overview-links/settings', {
        data: { country_borders_enabled: false, state_borders_enabled: false },
      });
      expect(reset.status()).toBe(200);
      expect(await (await request.get('/api/routes')).json()).toMatchObject({
        routes: [],
      });
      const overview = await context.newPage();
      if (mode === 'mobile')
        await overview.setViewportSize({ width: 390, height: 844 });
      await observeOverviewCamera(overview);
      const errors: string[] = [];
      overview.on('pageerror', (error) => errors.push(error.message));
      const assets: string[] = [];
      overview.on('request', (request) => {
        if (request.url().includes('/boundaries/')) assets.push(request.url());
      });
      await overview.goto('/overview');
      await settledOverviewCamera(overview);
      await expect
        .poll(async () => (await scene(overview)).earth, { timeout: 30_000 })
        .toBe(true);
      expect((await scene(overview)).borders).toHaveLength(0);
      expect(assets).toHaveLength(0);
      await expect(overview.getByRole('switch')).toHaveCount(0);
      await expect(overview.getByLabel('Map status')).toContainText(
        'No active route'
      );
      if (mode === 'fullscreen') {
        await overview
          .getByRole('button', { name: 'Enter fullscreen overview' })
          .click();
        await expect
          .poll(() => overview.evaluate(() => !!document.fullscreenElement))
          .toBe(true);
      }
      // With no mission, automatic framing follows changing simulation positions.
      // Establish a user-explored view to prove that saves preserve that view.
      const explore = overview.getByRole('button', {
        name: 'Explore map',
        exact: true,
      });
      if (await explore.isVisible()) await explore.click();
      const box = (await overview
        .locator('.overview-globe canvas')
        .boundingBox())!;
      await overview.mouse.move(
        box.x + box.width * 0.55,
        box.y + box.height * 0.55
      );
      await overview.mouse.down();
      await overview.mouse.move(
        box.x + box.width * 0.65,
        box.y + box.height * 0.5,
        { steps: 10 }
      );
      await overview.mouse.up();
      await overview.mouse.wheel(0, -900);
      const camera = await settledOverviewCamera(overview);
      const baselineFrames = frameStats(await frameSample(overview));
      const originalScene = await scene(overview);
      const editing = await context.newPage();
      await editing.goto('/configuration');
      await expect(
        editing.getByRole('heading', { name: 'Geographic boundaries' })
      ).toBeVisible();
      const before = await overview.evaluate(() => performance.timeOrigin);
      const countryMs = await toggle(
        editing,
        overview,
        'Country borders',
        'countries',
        true
      );
      const countryScene = await scene(overview);
      expect(countryScene.borders).toHaveLength(2);
      await expect(
        (await legend(overview)).getByText('Country borders', { exact: true })
      ).toBeVisible();
      const stateMs = await toggle(
        editing,
        overview,
        'State/province borders',
        'subdivisions',
        true
      );
      const bothScene = await scene(overview);
      expect(bothScene.borders).toHaveLength(4);
      expect(bothScene.calls - originalScene.calls).toBeLessThanOrEqual(4);
      for (const line of bothScene.borders) {
        expect(line.count).toBeGreaterThan(0);
        expect(line.depthTest).toBe(true);
        expect(line.depthWrite).toBe(false);
      }
      await expect(
        (await legend(overview)).getByText('Aircraft', { exact: true })
      ).toBeVisible();
      expectSameCamera(await settledOverviewCamera(overview), camera);
      expect(await overview.evaluate(() => performance.timeOrigin)).toBe(
        before
      );
      if (mode === 'fullscreen')
        expect(
          await overview.evaluate(() => !!document.fullscreenElement)
        ).toBe(true);
      await overview.screenshot({
        path: info.outputPath(`${mode}-borders.png`),
      });
      await editing.screenshot({
        path: info.outputPath(`${mode}-settings.png`),
        fullPage: true,
      });
      const borderFrames = frameStats(await frameSample(overview));
      expect(borderFrames.median).toBeLessThan(
        Math.max(100, baselineFrames.median * 2)
      );
      expect(borderFrames.p95).toBeLessThan(
        Math.max(200, baselineFrames.p95 * 3)
      );
      const countryOffMs = await toggle(
        editing,
        overview,
        'Country borders',
        'countries',
        false
      );
      expect((await scene(overview)).borders).toHaveLength(2);
      const stateOffMs = await toggle(
        editing,
        overview,
        'State/province borders',
        'subdivisions',
        false
      );
      expect((await scene(overview)).borders).toHaveLength(0);
      await expect(
        (await legend(overview)).getByText('State/province borders', {
          exact: true,
        })
      ).toHaveCount(0);
      for (let i = 0; i < 2; i++) {
        await toggle(
          editing,
          overview,
          'State/province borders',
          'subdivisions',
          true
        );
        await toggle(
          editing,
          overview,
          'State/province borders',
          'subdivisions',
          false
        );
      }
      // Successful immutable assets are reused; no polling or per-feature requests.
      expect(assets).toHaveLength(2);
      await expect
        .poll(async () => (await scene(overview)).geometries)
        .toBe(originalScene.geometries);
      await editing.reload();
      await expect(
        editing.getByRole('switch', { name: 'State/province borders' })
      ).not.toBeChecked();
      expect(errors).toEqual([]);
      await writeFile(
        info.outputPath('observations.json'),
        JSON.stringify(
          {
            candidate: process.env.ACCEPTANCE_CANDIDATE_SHA,
            mode,
            countryMs,
            stateMs,
            countryOffMs,
            stateOffMs,
            assets,
            originalScene,
            bothScene,
            baselineFrames,
            borderFrames,
            errors,
          },
          null,
          2
        )
      );
    });
  });
}

test('missing or malformed optional data leaves real telemetry and globe controls usable', async ({
  context,
  request,
}, info) => {
  await request.put('/api/overview-links/settings', {
    data: { country_borders_enabled: true, state_borders_enabled: true },
  });
  // Only these optional assets are intercepted. Telemetry/settings use real Nginx/backend.
  await context.route('**/boundaries/countries.json', (route) =>
    route.fulfill({ status: 404, body: 'missing' })
  );
  await context.route('**/boundaries/subdivisions.json', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"version":1,"lines":[{"points":[[0,100],[1,0]],"disputed":false}]}',
    })
  );
  const overview = await context.newPage();
  await observeOverviewCamera(overview);
  const errors: string[] = [];
  overview.on('pageerror', (error) => errors.push(error.message));
  await overview.goto('/overview');
  await settledOverviewCamera(overview);
  await expect(
    overview.getByText('Country borders unavailable.', { exact: false })
  ).toBeVisible();
  await expect(
    overview.getByText('State/province borders unavailable.', { exact: false })
  ).toBeVisible();
  expect((await scene(overview)).borders).toHaveLength(0);
  await expect(
    (await legend(overview)).getByText('Aircraft', { exact: true })
  ).toBeVisible();
  await overview
    .getByRole('button', { name: 'Enter fullscreen overview' })
    .click();
  await expect
    .poll(() => overview.evaluate(() => !!document.fullscreenElement))
    .toBe(true);
  await overview
    .getByRole('button', { name: 'Reset map view', exact: true })
    .click();
  await settledOverviewCamera(overview);
  expect((await request.get('/api/status')).status()).toBe(200);
  expect(errors).toEqual([]);
  await overview.screenshot({ path: info.outputPath('unavailable.png') });
});

test('fixture operational overlays remain readable with real bundled borders', async ({
  context,
  request,
}, info) => {
  await request.put('/api/overview-links/settings', {
    data: {
      country_borders_enabled: true,
      state_borders_enabled: true,
      aircraft_history_enabled: true,
      orbital_traffic_enabled: true,
    },
  });
  // Operational telemetry/catalogs are deterministic browser fixtures; boundary
  // assets, renderer and saved layer settings are the production Nginx path.
  const fixture = await installAdsbFixture(context, true);
  fixture.setContacts([
    freshContact({ latitude: 38, longitude: -90, callsign: 'BORDER-TEST' }),
  ]);
  fixture.setSettings(adsbSettings({ enabled: true }));
  await context.route('**/api/overview-links/settings', (route) =>
    route.continue()
  );
  const catalog = await makeCatalog(256);
  await context.route('**/api/orbital/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.startsWith('/api/orbital/viewers/'))
      return route.fulfill(
        route.request().method() === 'DELETE'
          ? { status: 204 }
          : {
              json: { expires_at: new Date(Date.now() + 75_000).toISOString() },
            }
      );
    if (path === '/api/orbital/catalog')
      return route.fulfill({ json: catalog });
    const { objects, ...diagnostics } = catalog;
    void objects;
    return route.fulfill({ json: { ...diagnostics, active_viewers: 1 } });
  });
  const overview = await context.newPage();
  await observeOverviewCamera(overview);
  const errors: string[] = [];
  overview.on('pageerror', (error) => errors.push(error.message));
  await overview.goto('/overview');
  await settledOverviewCamera(overview);
  await expect
    .poll(async () => (await scene(overview)).borders.length, {
      timeout: 20_000,
    })
    .toBe(4);
  const entries = await legend(overview);
  for (const label of [
    'Country borders',
    'State/province borders',
    'Aircraft',
    'Planned route',
    'Track history',
    'Ground entry point',
    'Traffic path',
    'Planned satellite link',
    'ADS-B aircraft',
    'Satellites',
  ]) {
    await expect(entries.getByText(label, { exact: true })).toBeVisible({
      timeout: 30_000,
    });
  }
  await expect(overview.locator('[data-adsb-label="00AB12"]')).toBeVisible();
  await overview.screenshot({
    path: info.outputPath('operational-layers.png'),
  });
  // Camera probes exercise globe-attached geometry at the date line and pole;
  // they are identified as controlled views rather than public recenter behavior.
  for (const [name, latitude, longitude] of [
    ['dateline', 10, 180],
    ['polar', 82, 20],
  ] as const) {
    await overview.evaluate(
      ({ latitude, longitude }) => {
        type Root = {
          containerInfo?: {
            getState?: () => {
              gl: { domElement: HTMLCanvasElement };
              controls: {
                setLookAt: (
                  x: number,
                  y: number,
                  z: number,
                  tx: number,
                  ty: number,
                  tz: number,
                  transition: boolean
                ) => void;
              };
            };
          };
        };
        const roots = (window as unknown as { __overviewEvidenceRoots: Root[] })
          .__overviewEvidenceRoots;
        const state = roots
          .find(
            (root) =>
              typeof root.containerInfo?.getState === 'function' &&
              document.contains(root.containerInfo.getState().gl.domElement)
          )
          ?.containerInfo?.getState?.();
        if (!state) throw new Error('Renderer not observed');
        const lat = (latitude * Math.PI) / 180,
          lon = (longitude * Math.PI) / 180;
        state.controls.setLookAt(
          7 * Math.cos(lat) * Math.cos(lon),
          7 * Math.sin(lat),
          -7 * Math.cos(lat) * Math.sin(lon),
          0,
          0,
          0,
          false
        );
      },
      { latitude, longitude }
    );
    await settledOverviewCamera(overview);
    expect((await scene(overview)).borders).toHaveLength(4);
    await overview.screenshot({ path: info.outputPath(`${name}-borders.png`) });
  }
  expect(errors).toEqual([]);
  await writeFile(
    info.outputPath('fixture-observations.json'),
    JSON.stringify(
      {
        candidate: process.env.ACCEPTANCE_CANDIDATE_SHA,
        operationalData: 'browser fixtures',
        boundaryData: 'real bundled Nginx assets',
        scene: await scene(overview),
        errors,
      },
      null,
      2
    )
  );
});
