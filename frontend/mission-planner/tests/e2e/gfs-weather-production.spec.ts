import { overviewCamera } from './support/overview-camera';
import { captureGfsViews } from './support/gfs-presentation-views';
import { readFile, rename, writeFile } from 'node:fs/promises';
import { expect, test, type Page } from '@playwright/test';
import {
  windSnapshot as snapshot,
  windReadbacks as samples,
  windTrailPixels,
  windDirection,
} from './support/gfs-wind-probe';
import {
  installWeatherProbe,
  weatherSnapshot,
} from './support/overview-weather-probe';

async function patchControl(changes: Record<string, unknown>) {
  const path = process.env.WEATHER_ACCEPTANCE_CONTROL_PATH!;
  const before = JSON.parse(await readFile(path, 'utf8'));
  await writeFile(path + '.new', JSON.stringify({ ...before, ...changes }));
  await rename(path + '.new', path);
}
test('production GFS selection, source/CPU/GPU, native winds, combined views and cancellation', async ({
  browser,
  context,
  request,
}, info) => {
  test.setTimeout(1200000);
  const output = process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR!;
  const oracles = JSON.parse(
    await readFile(output + '/capture/gfs-presentation/oracles.json', 'utf8')
  ) as {
    lead: number;
    vertical: string;
    latitude: number;
    longitude: number;
    mask: number;
    source_values: Record<string, number>;
  }[];
  const secondary = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const config = await context.newPage(),
    overview = await context.newPage(),
    other = await secondary.newPage();
  const errors: string[] = [],
    providerRequests: string[] = [];
  for (const page of [overview, other, config]) {
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('request', (r) => {
      if (
        /noaa-gfs|aviationweather\.gov|rainviewer\.com/.test(
          new URL(r.url()).hostname
        )
      )
        providerRequests.push(r.url());
    });
  }
  await overview.clock.setFixedTime(new Date('2026-10-06T06:00:00Z'));
  await installWeatherProbe(overview);
  await installWeatherProbe(other);
  const evidence: { [key: string]: unknown } = {},
    readbacks: unknown[] = [],
    snapshots: NonNullable<Awaited<ReturnType<typeof snapshot>>>[] = [];
  const remember = async () => {
    const v = await snapshot(overview);
    if (!v?.present) throw Error('Grid not admitted');
    snapshots.push(v);
    return v;
  };
  const ready = async (page: Page, kind: string, lead: number) => {
    await expect
      .poll(
        async () => {
          const v = await snapshot(page);
          return v?.present && v.wind && v.particleCount > 0
            ? `${v.vertical.kind}:${v.lead}`
            : '';
        },
        { timeout: 180000 }
      )
      .toBe(`${kind}:${lead * 3600}`);
  };
  try {
    await config.goto('/configuration');
    await config.getByRole('tab', { name: 'Weather', exact: true }).click();
    const route = await request.post('/api/routes/upload', {
      multipart: {
        file: {
          name: 'fabricated-wind-route.kml',
          mimeType: 'application/vnd.google-earth.kml+xml',
          buffer: Buffer.from(
            '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Fabricated wind check</name><Placemark><name>KXXA</name><Point><coordinates>-80,35</coordinates></Point></Placemark><Placemark><name>KXXB</name><Point><coordinates>-70,40</coordinates></Point></Placemark><Placemark><LineString><coordinates>-80,35 -70,40</coordinates></LineString></Placemark></Document>'
          ),
        },
      },
    });
    expect(route.status()).toBe(201);
    expect(
      (
        await request.post(`/api/routes/${(await route.json()).id}/activate`)
      ).ok()
    ).toBe(true);
    await overview.goto('/overview');
    await other.goto('/overview');
    for (const name of [
      'METAR / SPECI observations',
      'TAF terminal forecasts',
      'International SIGMET advisories',
      'Precipitation radar',
      'GFS winds',
    ]) {
      const toggle = config.getByRole('switch', { name, exact: true });
      await expect(toggle).toBeEnabled();
      if (!(await toggle.isChecked())) await toggle.click();
      await expect(toggle).toBeChecked();
    }
    await ready(overview, 'pressure', 6);
    await ready(other, 'pressure', 6);
    const first = await remember();
    await expect(overview.getByLabel('Atmosphere legend')).toContainText(
      '500 hPa · Now'
    );
    await expect(
      overview.getByLabel('Globe legend').getByLabel('Atmosphere legend')
    ).toBeVisible();
    await expect(
      overview.getByLabel('Atmosphere legend').locator('time, details')
    ).toHaveCount(0);
    expect(first.bulletins).toEqual([true, true, true]);
    expect(first.particleCount).toBeGreaterThan(0);
    expect(first.particleCount).toBeLessThanOrEqual(2000);
    expect((await weatherSnapshot(overview)).radar).not.toBeNull();
    for (const [kind, lead] of [
      ['pressure', 6],
      ['flight-level', 6],
      ['flight-level', 9],
      ['pressure-850', 9],
    ] as const) {
      if (kind === 'pressure-850')
        await config
          .getByRole('combobox', { name: 'Atmosphere level' })
          .selectOption('pressure:85000');
      if (kind === 'flight-level') {
        if (lead === 6)
          await config
            .getByRole('combobox', { name: 'Atmosphere level' })
            .selectOption('fl:390');
        else
          await config
            .getByRole('combobox', { name: 'Forecast horizon' })
            .selectOption('3');
        await expect(
          config.getByText('Aviation weather settings saved', { exact: true })
        ).toBeVisible();
      }
      await ready(overview, kind === 'pressure-850' ? 'pressure' : kind, lead);
      await ready(other, kind === 'pressure-850' ? 'pressure' : kind, lead);
      const previous = snapshots[snapshots.length - 1];
      const current = await remember();
      if (kind !== 'pressure')
        expect(current.instance).not.toBe(previous.instance);
      expect(current.valid).toBe(
        Date.parse('2026-10-06T00:00:00Z') + lead * 3600000
      );
      if (kind === 'pressure-850')
        expect(current.vertical.pressure_pa).toBe(85000);
      if (kind === 'flight-level') {
        expect(current.vertical.source_pressures_pa).toEqual([15000, 20000]);
        expect(current.vertical.derivation).toBe('isa-log-pressure-v1');
      }
      const reference = oracles.filter(
          (o) => o.lead === lead && o.vertical === kind
        ),
        native = await samples(overview, reference);
      readbacks.push({ kind, lead, native, reference });
      await writeFile(
        output + '/presentation-readbacks.json',
        JSON.stringify(readbacks, null, 2)
      );
      native.forEach((actual, i) => {
        const node = actual.node;
        expect(node.mask).toBe(reference[i].mask);
        if (actual.mask) expect(actual.maskedTransparent).toBe(true);
        if (!node.mask)
          for (const n of ['u', 'v', 't'] as const)
            expect(
              Math.abs(node[n] - reference[i].source_values[n])
            ).toBeLessThanOrEqual(0.01);
        if ('u' in actual) {
          for (const component of [actual.u, actual.v]) {
            expect(component.gpuMask).toBe(component.mask);
            if (!component.mask)
              expect(component.error).toBeLessThanOrEqual(0.02);
          }
          expect(actual.speedMask).toBe(actual.mask);
          if (!node.mask) {
            expect(
              Math.abs(actual.knots - actual.cpuKnots)
            ).toBeLessThanOrEqual(0.06);
            actual.expectedColor.forEach((c, j) =>
              expect(Math.abs(actual.rgba[j] - c)).toBeLessThanOrEqual(2)
            );
            actual.expectedColor.forEach((c, j) =>
              expect(
                Math.abs(
                  actual.productionRGBA[j] -
                    (c * 0.45 + actual.hiddenRGBA[j] * 0.55)
                )
              ).toBeLessThanOrEqual(2)
            );
          }
        }
      });
      await config
        .getByRole('switch', { name: 'GFS air temperature', exact: true })
        .click();
      for (const page of [overview, other]) {
        await expect
          .poll(async () => (await snapshot(page))?.mode, { timeout: 180000 })
          .toBe('temperature');
        expect((await snapshot(page))?.particleCount).toBe(0);
        await expect(page.getByLabel('Atmosphere legend')).not.toContainText(
          'Wind speed'
        );
      }
      const thermal = await samples(overview, reference);
      thermal.forEach((actual) => {
        if ('t' in actual) {
          expect(actual.t.gpuMask).toBe(actual.t.mask);
          if (!actual.t.mask) expect(actual.t.error).toBeLessThanOrEqual(0.02);
          else expect(actual.maskedTransparent).toBe(true);
        }
      });
      readbacks.push({ kind, lead, thermal });
      await config
        .getByRole('switch', { name: 'GFS winds', exact: true })
        .click();
      await expect(
        config.getByRole('switch', { name: 'GFS air temperature', exact: true })
      ).not.toBeChecked();
      await ready(overview, kind === 'pressure-850' ? 'pressure' : kind, lead);
      await ready(other, kind === 'pressure-850' ? 'pressure' : kind, lead);
      const moving = await remember();
      expect(moving.finite).toBe(true);
      expect(moving.particleCount).toBe(2000);
      expect(moving.depthTest).toBe(true);
      expect(moving.depthWrite).toBe(false);
      await expect
        .poll(async () => (await snapshot(overview))?.vertices)
        .toBeGreaterThan(0);
    }
    expect(
      oracles.some((o) => o.vertical === 'pressure-850' && o.mask === 1)
    ).toBe(true);
    await config
      .getByRole('combobox', { name: 'Atmosphere level' })
      .selectOption('fl:390');
    await ready(overview, 'flight-level', 9);
    await ready(other, 'flight-level', 9);
    await remember();
    await expect(overview.getByLabel('Atmosphere legend')).toContainText(
      'FL390 · +3 h'
    );
    await overview
      .getByRole('link', { name: 'Configuration', exact: true })
      .click();
    await expect(overview.locator('.overview-globe canvas')).toHaveCount(0);
    await expect
      .poll(() =>
        overview.evaluate(() =>
          (
            window as unknown as { __gfsOwnedBytes?: () => unknown }
          ).__gfsOwnedBytes?.()
        )
      )
      .toEqual({ decoded: 0, gpu: 0 });
    await overview.getByRole('link', { name: 'Overview', exact: true }).click();
    await ready(overview, 'flight-level', 9);
    await expect
      .poll(() =>
        overview.evaluate(() => {
          const roots = (
            window as unknown as {
              __overviewEvidenceRoots: {
                containerInfo?: {
                  getState?: () => import('@react-three/fiber').RootState;
                };
              }[];
            }
          ).__overviewEvidenceRoots;
          const scene = roots
            .find(
              (r) => r.containerInfo?.getState?.().gl.domElement.isConnected
            )
            ?.containerInfo?.getState?.().scene;
          let count = 0;
          scene?.traverse((node) => {
            const mesh = node as import('three').Mesh<
              import('three').BufferGeometry,
              import('three').ShaderMaterial
            >;
            if (mesh.material?.uniforms?.uHalfWidthWorld) {
              const a = mesh.geometry.getAttribute('position');
              if (!Array.from(a.array).every(Number.isFinite))
                throw Error('Nonfinite native route');
              count++;
            }
          });
          return count;
        })
      )
      .toBeGreaterThan(0);
    evidence.wind_raster = true;
    const trailPixels = await windTrailPixels(overview);
    expect(trailPixels.frontChanged).toBeGreaterThan(0);
    expect(trailPixels.farControls).toBeGreaterThan(0);
    expect(trailPixels.farChanged).toBe(0);
    expect((await windDirection(overview)).alignment).toBeGreaterThan(0.98);
    evidence.wind_particles = true;
    evidence.exclusive_modes = true;
    await captureGfsViews(overview, 'wind', info.outputPath.bind(info));
    await config
      .getByRole('switch', { name: 'GFS air temperature', exact: true })
      .click();
    for (const page of [overview, other]) {
      await expect
        .poll(async () => (await snapshot(page))?.mode, { timeout: 180000 })
        .toBe('temperature');
      expect((await snapshot(page))?.particleCount).toBe(0);
    }
    await captureGfsViews(overview, 'temperature', info.outputPath.bind(info));
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    await ready(overview, 'flight-level', 9);
    await ready(other, 'flight-level', 9);
    await overview.emulateMedia({ reducedMotion: 'reduce' });
    await expect
      .poll(async () => (await snapshot(overview))?.particleCount)
      .toBe(0);
    expect((await snapshot(overview))?.wind).toBe(true);
    await captureGfsViews(
      overview,
      'wind-reduced-motion',
      info.outputPath.bind(info)
    );
    await overview.emulateMedia({ reducedMotion: 'no-preference' });
    await expect
      .poll(async () => (await snapshot(overview))?.particleCount)
      .toBe(2000);
    await overview.setViewportSize({ width: 1920, height: 1080 });
    evidence.reduced_motion = true;
    await overview.setViewportSize({ width: 390, height: 844 });
    const explore = overview.getByRole('button', {
      name: 'Explore map',
      exact: true,
    });
    await explore.click();
    const box = await overview.locator('.overview-globe canvas').boundingBox();
    if (!box) throw Error('Missing globe gesture surface');
    const cameraBefore = await overviewCamera(overview);
    await overview.mouse.move(
      box.x + box.width * 0.4,
      box.y + box.height * 0.6
    );
    await overview.mouse.down();
    await overview.mouse.move(
      box.x + box.width * 0.6,
      box.y + box.height * 0.5,
      { steps: 10 }
    );
    await overview.mouse.up();
    await expect
      .poll(async () =>
        JSON.stringify((await overviewCamera(overview)).position)
      )
      .not.toBe(JSON.stringify(cameraBefore.position));
    await overview.keyboard.press('Escape');
    await overview.setViewportSize({ width: 1920, height: 1080 });
    evidence.native_samples = true;
    evidence.configuration = true;
    await overview.screenshot({ path: info.outputPath('gfs-desktop.png') });
    await overview
      .getByRole('button', { name: 'Inspect weather reports' })
      .click();
    await expect(overview.getByRole('dialog')).toBeVisible();
    await expect(overview.getByRole('dialog')).toBeInViewport({ ratio: 1 });
    await overview.screenshot({
      path: info.outputPath('gfs-report-chooser.png'),
    });
    const report = overview.getByLabel('Weather report', { exact: true });
    if (await report.count()) {
      await report.first().click();
      await expect(overview.getByRole('dialog')).toContainText(
        /METAR|TAF|SIGMET/
      );
    }
    await overview
      .getByRole('button', { name: 'Close weather report' })
      .click();
    await overview
      .getByRole('button', { name: 'Enter fullscreen overview' })
      .click();
    await expect
      .poll(() => overview.evaluate(() => !!document.fullscreenElement))
      .toBe(true);
    await expect(overview.getByLabel('Atmosphere legend')).toBeVisible();
    await overview
      .getByRole('button', { name: 'Inspect weather reports' })
      .click();
    await expect(overview.getByRole('dialog')).toBeVisible();
    await expect(overview.getByRole('dialog')).toBeInViewport({ ratio: 1 });
    expect(
      await overview
        .getByRole('dialog')
        .evaluate((node) => !!document.fullscreenElement?.contains(node))
    ).toBe(true);
    await overview
      .getByRole('button', { name: 'Close weather report' })
      .click();
    await overview.screenshot({ path: info.outputPath('gfs-fullscreen.png') });
    await overview.evaluate(() => document.exitFullscreen());
    await overview.setViewportSize({ width: 390, height: 844 });
    await ready(overview, 'flight-level', 9);
    await overview.getByRole('button', { name: 'Legend', exact: true }).click();
    await expect(
      overview.getByLabel('Globe legend').getByLabel('Atmosphere legend')
    ).toBeVisible();
    await overview.screenshot({ path: info.outputPath('gfs-mobile.png') });
    await expect(overview.getByLabel('Globe legend')).toBeVisible();
    await overview
      .getByRole('button', { name: 'Inspect weather reports' })
      .click();
    await expect(overview.getByRole('dialog')).toBeVisible();
    await expect(overview.getByRole('dialog')).toBeInViewport({ ratio: 1 });
    await overview.screenshot({
      path: info.outputPath('gfs-mobile-reports.png'),
    });
    await overview
      .getByRole('button', { name: 'Close weather report' })
      .click();
    evidence.combined_viewports = true;
    await overview.setViewportSize({ width: 1920, height: 1080 });
    // Visibility/offline remove native owners immediately and recover from settings.
    await overview.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        value: true,
        configurable: true,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await expect
      .poll(async () => (await snapshot(overview))?.present)
      .toBe(false);
    await overview.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        value: false,
        configurable: true,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await ready(overview, 'flight-level', 9);
    await context.setOffline(true);
    await expect
      .poll(async () => (await snapshot(overview))?.present)
      .toBe(false);
    await context.setOffline(false);
    await ready(overview, 'flight-level', 9);
    await remember();
    // Cancel a genuinely in-flight replacement descriptor and ignore its late body.
    const releases: (() => void)[] = [];
    let entered = false;
    await overview.route(
      '**/api/aviation-weather/v1/products/*/grid.json',
      async (route) => {
        entered = true;
        const response = await route.fetch();
        await new Promise<void>((resolve) => {
          releases.push(resolve);
        });
        await route.fulfill({ response }).catch(() => {});
      }
    );
    await config
      .getByRole('combobox', { name: 'Atmosphere level' })
      .selectOption('pressure:50000');
    await expect.poll(() => entered, { timeout: 180000 }).toBe(true);
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    releases.forEach((resolve) => resolve());
    await overview.unroute('**/api/aviation-weather/v1/products/*/grid.json');
    await expect
      .poll(async () => (await snapshot(overview))?.present)
      .toBe(false);
    expect((await snapshot(overview))?.ownedBytes).toEqual({
      decoded: 0,
      gpu: 0,
    });
    expect((await request.get('/api/status')).ok()).toBe(true);
    await patchControl({ gfs_mismatch: true });
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    await expect(overview.getByLabel('Map status')).toContainText(
      'GFS unavailable',
      { timeout: 180000 }
    );
    await expect(overview.getByLabel('Atmosphere legend')).toHaveCount(0);
    expect((await request.get('/api/status')).ok()).toBe(true);
    await expect(overview.getByLabel('Globe legend')).toBeVisible();
    await patchControl({ gfs_mismatch: false });
    await ready(overview, 'pressure', 9);
    await remember();
    // Independent monotonic expiry progresses even after catalog failures. Shorten
    // timing only through the explicit replay clock; original contract deadlines stay intact.
    const catalog = await (
      await request.get('/api/aviation-weather/v1/catalog')
    ).json();
    const product = catalog.products.find(
      (p: { layer_id: string }) => p.layer_id === 'gfs-winds'
    );
    await patchControl({
      replay_utc_ms: product.fresh_until_ms + 1000,
      replay_monotonic: undefined,
    });
    // Host/container monotonic authority is supplied by the runner control file;
    // advancing UTC must not be offset by a browser's unrelated monotonic epoch.
    await overview.clock.install({
      time: new Date(product.fresh_until_ms + 1000),
    });
    await overview.reload();
    await expect(overview.getByLabel('Map status')).toContainText('GFS stale', {
      timeout: 180000,
    });
    await overview.route('**/api/aviation-weather/v1/catalog', (route) =>
      route.abort()
    );
    // Let the admitted deadline run on its original UTC anchor; use Playwright's
    // elapsed performance clock, without changing the product or payload.
    await overview.clock.fastForward(
      product.expires_at_ms - product.fresh_until_ms + 60000
    );
    await expect
      .poll(async () => (await snapshot(overview))?.present)
      .toBe(false);
    await overview.unroute('**/api/aviation-weather/v1/catalog');
    evidence.lifecycle = true;
    const peak = (key: string) =>
      Math.max(...snapshots.map((s) => s.budget!.peaks[key as 'encoded']));
    evidence.browser_metrics = {
      encoded_peak: peak('encoded'),
      decoded_peak: peak('decoded'),
      gpu_peak: peak('gpu'),
      slot_peak: peak('slots'),
      native_sample_count: oracles.length,
      particle_count: Math.max(...snapshots.map((s) => s.particleCount ?? 0)),
    };
    expect(errors).toEqual([]);
    expect(providerRequests).toEqual([]);
    await writeFile(
      output + '/presentation-readbacks.json',
      JSON.stringify(readbacks, null, 2)
    );
    await writeFile(
      output + '/presentation-snapshots.json',
      JSON.stringify(snapshots, null, 2)
    );
    await writeFile(
      output + '/presentation.json',
      JSON.stringify(evidence, null, 2)
    );
  } finally {
    await config.close();
    await overview.close();
    await other.close();
    await secondary.close();
  }
});
