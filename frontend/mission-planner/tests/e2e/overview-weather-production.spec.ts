import { readFile, writeFile, rename } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import {
  installWeatherProbe,
  weatherSnapshot,
  weatherPixel,
} from './support/overview-weather-probe';

async function control(values: Record<string, unknown>) {
  const path = process.env.WEATHER_ACCEPTANCE_CONTROL_PATH!;
  await writeFile(`${path}.new`, JSON.stringify(values));
  await rename(`${path}.new`, path);
}
async function events() {
  try {
    return (
      await readFile(
        process.env.WEATHER_ACCEPTANCE_CONTROL_PATH!.replace(
          'control.json',
          'events.jsonl'
        ),
        'utf8'
      )
    )
      .trim()
      .split('\n')
      .map(
        (line) =>
          JSON.parse(line) as {
            event: string;
            path?: string;
            count?: number;
            at: number;
          }
      );
  } catch {
    return [];
  }
}

test('exact production SHA: passive shared weather, pixels, real five-minute refresh and cleanup', async ({
  context,
  request,
}, info) => {
  test.setTimeout(780_000);
  expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
  const baselineFrame = Math.floor(Date.now() / 1000) - 120;
  await control({ frame: baselineFrame });
  const overview = await context.newPage();
  await installWeatherProbe(overview);
  await overview.goto('/overview');
  await expect(overview.locator('.overview-globe canvas')).toBeVisible();
  await expect
    .poll(async () => (await weatherSnapshot(overview)).calls)
    .toBeGreaterThan(0);
  const initial = await weatherSnapshot(overview);
  const initialStatus = await (await request.get('/api/status')).json();
  expect((await events()).length).toBe(0);
  await expect(overview.getByLabel('Weather status')).toHaveCount(0);
  const config = await context.newPage();
  await config.goto('/configuration');
  await config.getByRole('tab', { name: 'Overview', exact: true }).click();
  const toggle = config.getByRole('switch', { name: 'Precipitation radar' });
  await expect(toggle).not.toBeChecked();
  expect((await events()).length).toBe(0);
  const enabledAt = Date.now();
  await toggle.click();
  await expect(toggle).toBeChecked();
  await expect(toggle).toBeEnabled();
  await expect(
    overview.getByText('Current precipitation', { exact: true })
  ).toBeVisible({ timeout: 30_000 });
  const loaded = await weatherSnapshot(overview);
  expect(loaded.canvas).toBe(initial.canvas);
  expect(loaded.width).toBe(2048);
  expect(loaded.depthTest).toBe(true);
  expect(loaded.depthWrite).toBe(false);
  expect(loaded.renderOrder).toBeLessThan(0);
  expect(loaded.textures - initial.textures).toBe(2);
  await expect(overview.getByRole('switch')).toHaveCount(0);
  await expect(
    overview.getByRole('link', { name: 'RainViewer' })
  ).toHaveAttribute('href', 'https://www.rainviewer.com/');
  // Full map exploration is a product control; aim through the existing renderer
  // boundary to read actual GPU center pixels against independent XYZ landmarks.
  const explore = overview.getByRole('button', {
    name: 'Explore map',
    exact: true,
  });
  if (await explore.isVisible()) await explore.click();
  const pixels = [];
  for (const [lat, lon, channels] of [
    [1, 45, [0]],
    [-1, 45, [1]],
    [60, 45, [0]],
    [65, 45, [0]],
    [68, 45, [0, 2]],
    [45, -1, [2]],
    [45, 1, [0]],
    [1, 179, [0, 1]],
  ] as const) {
    for (const night of [false, true]) {
      const sample = await weatherPixel(overview, lat, lon, night);
      expect(sample.withWeather).not.toEqual(sample.withoutWeather);
      const other = sample.withWeather.filter(
        (_, index) => index < 3 && !channels.some((c) => c === index)
      );
      for (const channel of channels)
        expect(sample.withWeather[channel]).toBeGreaterThan(
          Math.max(...other) + 10
        );
      pixels.push({ lat, lon, channels, night, ...sample });
    }
  }
  // Both antimeridian sides and poles must distinguish absence of coverage
  // from precipitation. Night pixels remove terrain lighting from the test.
  for (const [lat, lon] of [
    [0, -179],
    [88, 45],
    [-88, 45],
  ]) {
    const sample = await weatherPixel(overview, lat, lon, true);
    let hatchPixels = 0;
    for (let offset = 0; offset < sample.patchWithWeather.length; offset += 4) {
      const delta = [0, 1, 2].map(
        (c) =>
          sample.patchWithWeather[offset + c] -
          sample.patchWithoutWeather[offset + c]
      );
      if (Math.max(...delta) > 8) {
        hatchPixels++;
        expect(Math.max(...delta) - Math.min(...delta)).toBeLessThan(12);
      }
    }
    expect(hatchPixels).toBeGreaterThan(0);
    expect(hatchPixels).toBeLessThan(144);
    pixels.push({ lat, lon, hatchPixels, ...sample });
  }
  await overview.screenshot({ path: info.outputPath('weather-globe.png') });
  await overview
    .getByRole('button', { name: 'Enter fullscreen overview' })
    .click();
  await expect(
    overview.getByRole('button', { name: 'Exit fullscreen overview' })
  ).toBeVisible();
  await overview
    .getByRole('button', { name: 'Exit fullscreen overview' })
    .click();
  await overview.setViewportSize({ width: 390, height: 844 });
  await expect(overview.getByLabel('Weather status')).toBeVisible();
  await overview.screenshot({ path: info.outputPath('weather-mobile.png') });
  await overview.setViewportSize({ width: 1920, height: 1080 });
  // No synthetic clock, reload, query invalidation, or mission operation here.
  // Production metadata TTL and browser 300s timer must both elapse naturally.
  await control({ frame: baselineFrame + 60 });
  await expect
    .poll(
      async () =>
        (await events()).filter(
          (e) =>
            e.event === 'request' &&
            e.path?.includes(`/radar/${baselineFrame + 60}/`)
        ).length,
      {
        timeout: 650_000,
        intervals: [1000],
      }
    )
    .toBe(16);
  await expect
    .poll(async () => (await weatherSnapshot(overview)).radar)
    .not.toBe(loaded.radar);
  expect(Date.now() - enabledAt).toBeGreaterThanOrEqual(300_000);
  const refreshed = await weatherSnapshot(overview);
  expect(refreshed.canvas).toBe(initial.canvas);
  expect(refreshed.textures).toBe(loaded.textures);
  const observed = await events();
  expect(
    observed.filter(
      (e) => e.event === 'request' && e.path === '/public/weather-maps.json'
    )
  ).toHaveLength(2);
  expect(
    observed.filter(
      (e) => e.event === 'request' && e.path?.includes('/coverage/')
    )
  ).toHaveLength(
    16 *
      (Math.floor(Date.now() / 86400000) - Math.floor(enabledAt / 86400000) + 1)
  );
  expect(
    observed.filter((e) => e.event === 'request' && e.path?.includes('/radar/'))
  ).toHaveLength(32);
  const finalStatus = await (await request.get('/api/status')).json();
  expect(finalStatus.timestamp).not.toBe(initialStatus.timestamp);
  // Re-enable with a failing provider verifies graceful degradation via the
  // same Configuration control while preserving the original canvas.
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  await expect(overview.getByLabel('Weather status')).toHaveCount(0, {
    timeout: 15_000,
  });
  await expect
    .poll(async () => (await weatherSnapshot(overview)).textures)
    .toBe(initial.textures);
  await control({ fail: true });
  await toggle.click();
  await expect(toggle).toBeChecked();
  await expect(
    overview.getByText('Weather unavailable', { exact: true })
  ).toBeVisible({ timeout: 20_000 });
  expect((await weatherSnapshot(overview)).canvas).toBe(initial.canvas);
  expect((await request.get('/health')).status()).toBe(200);
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  await expect(overview.getByLabel('Weather status')).toHaveCount(0, {
    timeout: 15_000,
  });
  const all = await events();
  const closes = all.filter((e) => e.event === 'close');
  const waits = all.filter((e) => e.event === 'wait_closed');
  expect(closes.length).toBe(all.filter((e) => e.event === 'dial').length);
  expect(waits.length).toBe(closes.length);
  expect(
    closes.every((e) => e.count === 1) && waits.every((e) => e.count === 1)
  ).toBe(true);
  await writeFile(
    info.outputPath('evidence.json'),
    JSON.stringify(
      {
        sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
        initial,
        loaded,
        refreshed,
        pixels,
        enabledAt,
        finishedAt: Date.now(),
        all,
        initialStatus,
        finalStatus,
      },
      null,
      2
    )
  );
});

test('real Nginx disconnect leases preserve siblings and global disable closes every stream once', async ({
  request,
}, info) => {
  const origin = process.env.WEATHER_ACCEPTANCE_BASE_URL!;
  const frame = Math.floor(Date.now() / 1000) - 120;
  await control({ frame, delay: 1 });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: true },
  });
  const before = (await events()).length;
  const abort = new AbortController();
  const first = fetch(`${origin}/api/overview-weather/frame`, {
    signal: abort.signal,
  })
    .then((r) => r.json())
    .catch((error) => error.name);
  const second = fetch(`${origin}/api/overview-weather/frame`).then(
    async (r) => ({ status: r.status, body: await r.json() })
  );
  await expect
    .poll(
      async () =>
        (await events()).slice(before).filter((e) => e.event === 'request')
          .length
    )
    .toBe(1);
  await new Promise((resolve) => setTimeout(resolve, 200));
  abort.abort();
  expect(await first).toBe('AbortError');
  const sibling = await second;
  expect(sibling.status).toBe(200);
  expect(sibling.body.state).toBe('ready');
  const tile = sibling.body.radar_tile_template
    .replace('{z}', '2')
    .replace('{x}', '2')
    .replace('{y}', '1');
  const abortTile = new AbortController();
  const tileBefore = (await events()).length;
  const tileFirst = fetch(`${origin}${tile}`, { signal: abortTile.signal })
    .then((r) => r.arrayBuffer())
    .catch((error) => error.name);
  const tileSecond = fetch(`${origin}${tile}`).then(async (r) => ({
    status: r.status,
    bytes: (await r.arrayBuffer()).byteLength,
  }));
  await expect
    .poll(
      async () =>
        (await events()).slice(tileBefore).filter((e) => e.event === 'request')
          .length
    )
    .toBe(1);
  await new Promise((resolve) => setTimeout(resolve, 200));
  abortTile.abort();
  expect(await tileFirst).toBe('AbortError');
  const pngSibling = await tileSecond;
  expect(pngSibling.status).toBe(200);
  expect(pngSibling.bytes).toBeGreaterThan(100);
  await control({ frame, delay: 4 });
  const disableBefore = (await events()).length;
  const pending = [0, 1].map((x) =>
    fetch(`${origin}${tile.replace('/2/1.png', `/${x}/1.png`)}`).then(
      (r) => r.status
    )
  );
  await expect
    .poll(
      async () =>
        (await events())
          .slice(disableBefore)
          .filter((e) => e.event === 'request').length
    )
    .toBe(2);
  expect(
    (
      await request.put('/api/overview-weather/settings', {
        data: { enabled: false },
      })
    ).status()
  ).toBe(200);
  await Promise.all(pending);
  const owned = (await events()).slice(before);
  expect(owned.filter((e) => e.event === 'dial').length).toBe(
    owned.filter((e) => e.event === 'close').length
  );
  expect(
    owned.filter((e) => e.event === 'close').every((e) => e.count === 1)
  ).toBe(true);
  expect(
    owned.filter((e) => e.event === 'wait_closed').every((e) => e.count === 1)
  ).toBe(true);
  expect((await request.get('/health')).status()).toBe(200);
  await writeFile(
    info.outputPath('disconnect-evidence.json'),
    JSON.stringify(owned, null, 2)
  );
});
