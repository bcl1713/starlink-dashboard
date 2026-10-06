import { readFile, writeFile, rename } from 'node:fs/promises';
import { expect, test, type Page } from '@playwright/test';
import type { RootState } from '@react-three/fiber';
import type { Light } from 'three';
import {
  installWeatherProbe,
  weatherPixel,
  weatherSnapshot,
} from './support/overview-weather-probe';
import {
  installComparison,
  restoreComparison,
  type ComparisonCapture,
  type ComparisonPair,
} from './support/overview-weather-comparison';

type CaptureFile = {
  snapshots: Array<{
    source: string;
    product: string;
    observed_utc: number;
    sha256: string;
  }>;
  tiles: Record<
    string,
    Array<{
      key: ComparisonPair['key'];
      pair: {
        snapshot_identity: string;
        radar_path: string;
        absence_path: string;
      };
    }>
  >;
  metadata: {
    comparisons: Array<{
      source: string;
      raw_identity: string;
      rainviewer_identity: string;
      delta_seconds: number;
      region: { latitude: number; longitude: number; rain_fraction: number };
    }>;
  };
};
type ProbeWindow = Window & {
  __overviewEvidenceRoots?: Array<{
    containerInfo?: { getState?: () => RootState };
  }>;
  __comparisonLights?: Array<{ light: Light; intensity: number }>;
  __weatherComparisonMetrics?: Record<string, number>;
};

async function lights(page: Page, night: boolean) {
  await page.evaluate((dark) => {
    const target = window as ProbeWindow;
    const s = target.__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    if (!s) throw new Error('No native renderer');
    if (!target.__comparisonLights) {
      target.__comparisonLights = [];
      s.scene.traverse((node) => {
        if ((node as Light).isLight)
          target.__comparisonLights!.push({
            light: node as Light,
            intensity: (node as Light).intensity,
          });
      });
    }
    target.__comparisonLights.forEach(
      ({ light, intensity }) => (light.intensity = dark ? 0 : intensity)
    );
    s.gl.render(s.scene, s.camera);
  }, night);
}

async function nativeEvidence(page: Page) {
  return page.evaluate(() => {
    const target = window as ProbeWindow;
    const s = target.__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    if (!s) throw new Error('No native renderer');
    const gl = s.gl.getContext();
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    const frameMilliseconds = [];
    for (let i = 0; i < 8; i++) {
      const start = performance.now();
      s.gl.render(s.scene, s.camera);
      gl.finish();
      frameMilliseconds.push(performance.now() - start);
    }
    return {
      renderer: extension
        ? (gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) as string)
        : (gl.getParameter(gl.RENDERER) as string),
      camera: s.camera.matrixWorld.toArray(),
      projection: s.camera.projectionMatrix.toArray(),
      drawingBuffer: [gl.drawingBufferWidth, gl.drawingBufferHeight],
      viewport: [innerWidth, innerHeight],
      frameMilliseconds,
      cacheState: 'saved capture; cold bitmap decode; warm native rendering',
      weatherGPUBytes: target.__weatherComparisonMetrics?.weatherGPUBytes,
      ownedDecodedPeakBytes:
        target.__weatherComparisonMetrics?.ownedDecodedPeakBytes,
      ...target.__weatherComparisonMetrics,
    };
  });
}

test.beforeEach(async ({ page, request }) => {
  const path = process.env.WEATHER_ACCEPTANCE_CONTROL_PATH!;
  await writeFile(
    `${path}.new`,
    JSON.stringify({ frame: Math.floor(Date.now() / 1000) - 120 })
  );
  await rename(`${path}.new`, path);
  expect(
    (
      await request.put('/api/overview-weather/settings', {
        data: { enabled: true },
      })
    ).ok()
  ).toBe(true);
  await installWeatherProbe(page);
  await page.goto('/overview');
  await expect(
    page.getByText('Current precipitation', { exact: true })
  ).toBeVisible({ timeout: 30_000 });
  const explore = page.getByRole('button', {
    name: 'Explore map',
    exact: true,
  });
  if (await explore.isVisible()) await explore.click();
});

test('synthetic geographic detail, truthful masks, mixed frames and failed-install cleanup', async ({
  page,
  request,
}) => {
  const manifest = await (
    await request.get('/api/overview-weather/frame')
  ).json();
  const tile = (template: string, x: number, y: number) =>
    template
      .replace('{z}', '2')
      .replace('{x}', String(x))
      .replace('{y}', String(y));
  const pair: ComparisonPair = {
    key: { z: 7, x: 64, y: 46 },
    radarIdentity: 'synthetic',
    absenceIdentity: 'synthetic',
    radarURL: tile(manifest.radar_tile_template, 2, 2),
    absenceURL: tile(manifest.coverage_tile_template, 2, 2),
  };
  const capture: ComparisonCapture = {
    snapshotIdentity: 'synthetic',
    opacity: 0.4,
    basePairs: [],
    detailPairs: [pair],
  };
  const initial = await weatherSnapshot(page);
  await expect(
    installComparison(page, {
      ...capture,
      detailPairs: [{ ...pair, absenceIdentity: 'other frame' }],
    })
  ).rejects.toThrow('Mixed frame');
  await installComparison(page, capture);
  const rain = await weatherPixel(page, 45, 1, true, 3.2);
  expect(rain.withWeather[1]).toBeGreaterThan(rain.withWeather[0] + 15);
  expect((await weatherSnapshot(page)).textures).toBe(initial.textures + 2);
  const metrics = await nativeEvidence(page);
  expect(metrics.weatherGPUBytes).toBeLessThanOrEqual(48 * 1024 ** 2);
  expect(metrics.ownedDecodedPeakBytes).toBeLessThanOrEqual(96 * 1024 ** 2);
  await restoreComparison(page);
  await weatherPixel(page, 45, 1, true, 3.2);
  expect((await weatherSnapshot(page)).textures).toBe(initial.textures);
  await installComparison(page, {
    ...capture,
    detailPairs: [
      { ...pair, absenceURL: tile(manifest.coverage_tile_template, 0, 2) },
    ],
  });
  const absent = await weatherPixel(page, 45, 1, true, 3.2);
  expect(absent.withWeather[1] - absent.withWeather[0]).toBeLessThan(15);
  await restoreComparison(page);
  await expect(
    installComparison(page, {
      ...capture,
      detailPairs: [
        { ...pair, radarURL: '/api/weather-comparison-assets/missing.png' },
      ],
    })
  ).rejects.toThrow('404');
  await weatherPixel(page, 45, 1, true, 3.2);
  expect((await weatherSnapshot(page)).textures).toBe(initial.textures);
});

test('actual saved radar sources on identical native desktop, fullscreen and mobile views', async ({
  page,
}, info) => {
  test.setTimeout(240_000);
  const captures: CaptureFile = JSON.parse(
    await readFile(
      `${process.env.WEATHER_ACCEPTANCE_CAPTURE_DIR}/capture.json`,
      'utf8'
    )
  );
  expect(captures.metadata.comparisons.length).toBe(2);
  const pairs = (identity: string, zoom: number): ComparisonPair[] =>
    captures.tiles[identity]
      .filter(({ key }) => key.z === zoom)
      .map(({ key, pair }) => ({
        key,
        radarIdentity: pair.snapshot_identity,
        absenceIdentity: pair.snapshot_identity,
        radarURL: `/api/weather-comparison-assets/${pair.radar_path}`,
        absenceURL: `/api/weather-comparison-assets/${pair.absence_path}`,
      }));
  const records = [];
  const requests: Array<{ url: string; status: number }> = [];
  page.on('response', (response) => {
    if (response.url().includes('/weather-comparison-assets/'))
      requests.push({ url: response.url(), status: response.status() });
  });
  try {
    for (const comparison of captures.metadata.comparisons) {
      expect(Math.abs(comparison.delta_seconds)).toBeLessThanOrEqual(300);
      for (const view of ['desktop', 'fullscreen', 'mobile'] as const) {
        await page.setViewportSize(
          view === 'mobile'
            ? { width: 390, height: 844 }
            : { width: 1920, height: 1080 }
        );
        if (view === 'fullscreen') {
          await page
            .getByRole('button', { name: 'Enter fullscreen overview' })
            .click();
          await expect
            .poll(() => page.evaluate(() => !!document.fullscreenElement))
            .toBe(true);
        }
        const variants =
          view === 'desktop'
            ? [
                { level: 2, opacity: 0.72 },
                { level: 5, opacity: 0.4 },
                { level: 6, opacity: 0.4 },
                { level: 7, opacity: 0.4 },
                { level: 6, opacity: 0.35 },
                { level: 6, opacity: 0.45 },
              ]
            : [
                { level: 2, opacity: 0.72 },
                { level: 6, opacity: 0.4 },
              ];
        for (const night of [false, true]) {
          await lights(page, night);
          for (const variant of variants) {
            for (const source of ['rainviewer', comparison.source]) {
              const identity =
                source === 'rainviewer'
                  ? comparison.rainviewer_identity
                  : comparison.raw_identity;
              const basePairs = pairs(identity, 2),
                detailPairs =
                  variant.level > 2 ? pairs(identity, variant.level) : [];
              expect(basePairs.length).toBe(16);
              expect(detailPairs.length).toBeLessThanOrEqual(8);
              await installComparison(page, {
                snapshotIdentity: identity,
                opacity: variant.opacity,
                basePairs,
                detailPairs,
              });
              const pixels = await weatherPixel(
                page,
                comparison.region.latitude,
                comparison.region.longitude,
                false,
                3.2
              );
              const measured = await nativeEvidence(page);
              const name = `${comparison.source}-${source}-${view}-${night ? 'night' : 'day'}-z${variant.level}-${variant.opacity}`;
              await page.evaluate((label) => {
                let banner = document.getElementById('weather-research-label');
                if (!banner) {
                  banner = document.createElement('div');
                  banner.id = 'weather-research-label';
                  banner.style.cssText =
                    'position:fixed;bottom:8px;right:8px;z-index:9999;background:#111c;color:white;padding:8px;font:12px sans-serif;pointer-events:none';
                  document.body.append(banner);
                }
                banner.textContent = label;
              }, `Offline radar research replay: ${source}; ${identity}`);
              await page.screenshot({ path: info.outputPath(`${name}.png`) });
              records.push({
                name,
                source,
                region: comparison.source,
                identity,
                level: variant.level,
                opacity: variant.opacity,
                night,
                view,
                precipitationPresent: comparison.region.rain_fraction > 0,
                pixels,
                ...measured,
              });
              await restoreComparison(page);
            }
          }
        }
        if (view === 'fullscreen')
          await page.evaluate(() => document.exitFullscreen());
      }
    }
  } finally {
    await restoreComparison(page);
    await lights(page, false);
    await writeFile(
      `${process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR}/comparison.json`,
      JSON.stringify(
        {
          mode: 'offline actual-source replay with test-only detail shader',
          sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
          records,
          requests,
          hashValidation: 'passed',
          synthesis: false,
        },
        null,
        2
      )
    );
  }
  expect(requests.every((request) => request.status === 200)).toBe(true);
});
