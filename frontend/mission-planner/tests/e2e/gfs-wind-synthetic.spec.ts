import { captureGfsViews } from './support/gfs-presentation-views';
// Labeled synthetic controls only; never substitutes for pinned NOAA acceptance.
import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { gridFixture, GRID_RUN, digest } from '../../src/test/gfs-grid';
import { installWeatherProbe } from './support/overview-weather-probe';
import {
  windSnapshot,
  windReadbacks,
  windTrailPixels,
  windDirection,
} from './support/gfs-wind-probe';

test('synthetic production shader, particles, exclusive controls and cleanup', async ({
  context,
}, info) => {
  let settings = {
    metar: false,
    taf: false,
    sigmet: false,
    winds: true,
    temperature: false,
    revision: 1,
    gfs_selection: {
      vertical: { kind: 'pressure', pressure_pa: 50000 },
      horizon_hours: 0,
    },
  };
  const f = gridFixture();
  const view = new DataView(f.buffers.u.buffer);
  for (let row = 0; row < 361; row++)
    for (let col = 0; col < 720; col++) {
      const i = row * 720 + col;
      view.setInt16(i * 2, col === 360 ? -2000 : 2000, true);
      new DataView(f.buffers.v.buffer).setInt16(i * 2, 0, true);
      if (col >= 440 && col <= 460) view.setInt16(i * 2, 0, true);
      if (col >= 480 && col <= 500) f.buffers.mask[i] = 1;
      if (col >= 520 && col <= 540) f.buffers.mask[i] = 2;
      if (col >= 560 && col <= 580) f.buffers.mask[i] = 3;
    }
  for (const n of ['u', 'v', 't', 'mask'] as const)
    f.descriptor.buffers[n].sha256 = digest(f.buffers[n]);
  f.descriptor.generated_at_ms = GRID_RUN + 21600000;
  Object.assign(f.product, {
    generated_at_ms: GRID_RUN + 21600000,
    source_id: 'noaa-gfs',
    provenance: 'Labeled synthetic renderer control; not NOAA source evidence',
    attribution: [{ label: 'Synthetic test', url: 'https://example.com' }],
    time_kind: 'forecast',
    method_kind: 'numerical-model',
    observed_at_ms: null,
    issued_at_ms: null,
    scan_start_ms: null,
    scan_end_ms: null,
    validity_kind: 'instant',
    valid_from_ms: null,
    valid_to_ms: null,
    radar: null,
    coverage: {
      generation: f.descriptor.instance_id,
      expires_at_ms: GRID_RUN + 18 * 3600000,
      mask_encoding: 'uint8-validity-v1',
      missing_meaning: 'unknown-not-clear',
      feed_completeness: 'complete',
    },
  });
  const json = Buffer.from(JSON.stringify(f.descriptor));
  f.product.payload!.sha256 = digest(json);
  f.product.payload!.encoded_bytes = json.length + 1819440;
  f.product.payload!.decoded_bytes = 12 * 1024 ** 2;
  f.product.payload!.gpu_bytes = 4 * 1024 ** 2;
  await context.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/aviation-weather/v1/settings') {
      if (route.request().method() === 'PUT')
        settings = {
          ...settings,
          ...route.request().postDataJSON(),
          revision: settings.revision + 1,
        };
      return route.fulfill({ json: settings });
    }
    if (path === '/api/aviation-weather/v1/catalog')
      return route.fulfill({
        json: {
          schema: 'aviation-weather-v1',
          generated_at_ms: GRID_RUN + 21600000,
          settings_revision: settings.revision,
          products:
            settings.winds || settings.temperature
              ? [
                  {
                    ...f.product,
                    layer_id: settings.winds ? 'gfs-winds' : 'gfs-temperature',
                    product_type: settings.winds ? 'winds' : 'air-temperature',
                  },
                ]
              : [],
        },
      });
    if (path.endsWith('/grid.json'))
      return route.fulfill({ body: json, contentType: 'application/json' });
    if (path.endsWith('.bin'))
      return route.fulfill({
        body: Buffer.from(
          f.buffers[
            path.split('/').pop()!.replace('.bin', '') as keyof typeof f.buffers
          ]
        ),
        contentType: 'application/octet-stream',
      });
    const values: Record<string, unknown> = {
      '/api/status': {
        timestamp: '2026-10-06T06:00:00Z',
        position: { latitude: 0, longitude: 0, altitude: 35000 },
        network: {
          latency_ms: 40,
          throughput_down_mbps: 100,
          throughput_up_mbps: 20,
          packet_loss_percent: 0,
        },
        environmental: { signal_quality_percent: 85 },
      },
      '/api/satellites': [],
      '/api/active-x-link': { satellite_id: null },
      '/api/routes': { routes: [], total: 0 },
      '/api/overview/upcoming-pois': { pois: [] },
      '/api/overview-history/settings': { window_seconds: 1800 },
      '/api/overview-clocks/settings': { clocks: [] },
      '/api/overview-weather/settings': { enabled: false, revision: 0 },
    };
    return route.fulfill({ json: values[path] ?? {} });
  });
  const page = await context.newPage(),
    config = await context.newPage(),
    errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  config.on('pageerror', (e) => errors.push(e.message));
  await page.clock.setFixedTime(new Date(GRID_RUN + 21600000));
  await installWeatherProbe(page);
  page.setDefaultTimeout(15000);
  config.setDefaultTimeout(15000);
  const snapshots = [];
  try {
    await page.goto('/overview');
    await config.goto('/configuration');
    await config.getByRole('tab', { name: 'Weather', exact: true }).click();
    await expect
      .poll(async () => (await windSnapshot(page))?.particleCount, {
        timeout: 60000,
      })
      .toBe(2000);
    await expect
      .poll(async () => (await windSnapshot(page))?.vertices)
      .toBeGreaterThan(0);
    const trails = await windTrailPixels(page);
    expect(trails.frontChanged).toBeGreaterThan(0);
    expect(trails.farControls).toBeGreaterThan(0);
    expect(trails.farChanged).toBe(0);
    const direction = await windDirection(page);
    expect(direction.alignment).toBeGreaterThan(0.98);
    snapshots.push(await windSnapshot(page));
    await expect(page.getByLabel('Atmosphere legend')).toContainText(
      'Wind speed · kt'
    );
    const samples = await windReadbacks(page, [
      { latitude: 0, longitude: 20 },
      { latitude: 0, longitude: -0.25 },
      { latitude: 0, longitude: 45 },
      { latitude: 0, longitude: 65 },
      { latitude: 0, longitude: 85 },
      { latitude: 0, longitude: 105 },
      { latitude: 88, longitude: 179.9 },
      { latitude: -88, longitude: -179.9 },
    ]);
    for (const a of samples) {
      if (!('u' in a)) throw Error('Expected wind readback');
      expect(a.u.gpuMask).toBe(a.mask);
      expect(a.v.gpuMask).toBe(a.mask);
      if (a.mask) expect(a.maskedTransparent).toBe(true);
      else {
        expect(a.u.error).toBeLessThanOrEqual(0.02);
        expect(a.v.error).toBeLessThanOrEqual(0.02);
        expect(Math.abs(a.knots - a.cpuKnots)).toBeLessThanOrEqual(0.06);
        a.expectedColor.forEach((c, i) =>
          expect(Math.abs(a.rgba[i] - c)).toBeLessThanOrEqual(2)
        );
        a.expectedColor.forEach((c, i) =>
          expect(
            Math.abs(a.productionRGBA[i] - (c * 0.45 + a.hiddenRGBA[i] * 0.55))
          ).toBeLessThanOrEqual(2)
        );
      }
    }
    const opposite = samples[1];
    if (!('u' in opposite)) throw Error('Missing control');
    expect(opposite.cpuKnots).toBeLessThan(2);
    const initial = await windSnapshot(page);
    await expect
      .poll(async () => JSON.stringify((await windSnapshot(page))?.positions))
      .not.toBe(JSON.stringify(initial?.positions));
    for (const mode of ['winds', 'temperature'] as const) {
      const toggle = config.getByRole('switch', {
        name: mode === 'winds' ? 'GFS winds' : 'GFS air temperature',
        exact: true,
      });
      if (!(await toggle.isChecked())) await toggle.click();
      await expect
        .poll(async () => (await windSnapshot(page))?.mode, { timeout: 60000 })
        .toBe(mode);
      const s = await windSnapshot(page);
      snapshots.push(s);
      expect(s?.finite).toBe(true);
      expect(s?.particleCount).toBe(mode === 'winds' ? 2000 : 0);
      await captureGfsViews(page, mode, info.outputPath.bind(info));
    }
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    await expect
      .poll(async () => (await windSnapshot(page))?.particleCount, {
        timeout: 60000,
      })
      .toBe(2000);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect
      .poll(async () => (await windSnapshot(page))?.particleCount)
      .toBe(0);
    expect((await windSnapshot(page))?.wind).toBe(true);
    await captureGfsViews(
      page,
      'wind-reduced-motion',
      info.outputPath.bind(info)
    );
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await expect
      .poll(async () => (await windSnapshot(page))?.particleCount)
      .toBe(2000);
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    await expect
      .poll(async () => (await windSnapshot(page))?.present, { timeout: 60000 })
      .toBe(false);
    expect((await windSnapshot(page))?.ownedBytes).toEqual({
      decoded: 0,
      gpu: 0,
    });
    await page.setViewportSize({ width: 1920, height: 1080 });
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    await expect
      .poll(async () => (await windSnapshot(page))?.particleCount, {
        timeout: 60000,
      })
      .toBe(2000);
    await page
      .getByRole('link', { name: 'Configuration', exact: true })
      .click();
    await expect(page.locator('.overview-globe canvas')).toHaveCount(0);
    await expect
      .poll(() =>
        page.evaluate(() =>
          (
            window as unknown as { __gfsOwnedBytes?: () => unknown }
          ).__gfsOwnedBytes?.()
        )
      )
      .toEqual({ decoded: 0, gpu: 0 });
    await page.getByRole('link', { name: 'Overview', exact: true }).click();
    await expect
      .poll(async () => (await windSnapshot(page))?.particleCount, {
        timeout: 60000,
      })
      .toBe(2000);
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    await expect
      .poll(async () => (await windSnapshot(page))?.present, { timeout: 60000 })
      .toBe(false);
    expect(errors).toEqual([]);
    await writeFile(
      info.outputPath('synthetic-evidence.json'),
      JSON.stringify(
        {
          source:
            'labeled synthetic; SwiftShader; not NOAA or hardware acceptance',
          trails,
          direction,
          samples,
          snapshots,
          errors,
        },
        null,
        2
      )
    );
  } finally {
    await config.close();
    await page.close();
  }
});
