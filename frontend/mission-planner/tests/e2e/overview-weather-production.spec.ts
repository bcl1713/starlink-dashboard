import { settledOverviewCamera } from './support/overview-camera';
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
            stream_id?: string;
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
  expect(loaded.textures - initial.textures).toBeGreaterThanOrEqual(2);
  expect(loaded.textures - initial.textures).toBeLessThanOrEqual(4);
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
  const westSeam = await weatherPixel(overview, 0, -179, true);
  const centerDelta = westSeam.withWeather
    .slice(0, 3)
    .map((value, index) => value - westSeam.withoutWeather[index]);
  expect(Math.max(...centerDelta) - Math.min(...centerDelta)).toBeLessThan(12);
  pixels.push({ lat: 0, lon: -179, ...westSeam });
  for (const [lat, lon] of [
    [0, -170],
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
  const cameraBefore = await settledOverviewCamera(overview);
  const box = (await overview.locator('.overview-globe canvas').boundingBox())!;
  await overview.mouse.move(box.x + box.width * 0.35, box.y + box.height * 0.6);
  await overview.mouse.down();
  await overview.mouse.move(
    box.x + box.width * 0.48,
    box.y + box.height * 0.48,
    { steps: 10 }
  );
  await overview.mouse.up();
  const rotated = await settledOverviewCamera(overview);
  expect(rotated.position).not.toEqual(cameraBefore.position);
  await overview.mouse.wheel(0, -150);
  const zoomed = await settledOverviewCamera(overview);
  expect(Math.hypot(...zoomed.position)).toBeLessThan(
    Math.hypot(...rotated.position)
  );
  await overview
    .getByRole('button', { name: 'Reset map view', exact: true })
    .click();
  await settledOverviewCamera(overview);
  const follow = config.getByRole('switch', {
    name: 'Follow aircraft on Overview',
  });
  await follow.click();
  await expect(follow).toBeChecked();
  await expect(
    overview.getByText('Following aircraft', { exact: true })
  ).toBeVisible();
  expect((await weatherSnapshot(overview)).radar).toBe(loaded.radar);
  expect((await weatherSnapshot(overview)).canvas).toBe(initial.canvas);
  await overview.screenshot({ path: info.outputPath('weather-globe.png') });
  await overview
    .getByRole('button', { name: 'Enter fullscreen overview' })
    .click();
  await expect
    .poll(() => overview.evaluate(() => !!document.fullscreenElement))
    .toBe(true);
  await expect(overview.getByLabel('Weather status')).toBeVisible();
  expect((await weatherSnapshot(overview)).canvas).toBe(initial.canvas);
  await overview.screenshot({
    path: info.outputPath('weather-fullscreen.png'),
  });
  await overview.evaluate(() => document.exitFullscreen());
  await expect
    .poll(() => overview.evaluate(() => !!document.fullscreenElement))
    .toBe(false);
  await overview.setViewportSize({ width: 390, height: 844 });
  await expect(overview.getByLabel('Weather status')).toBeVisible();
  await overview.screenshot({ path: info.outputPath('weather-mobile.png') });
  await overview.setViewportSize({ width: 1920, height: 1080 });
  // No synthetic clock, reload, query invalidation, or mission operation here.
  // Production metadata TTL and browser 300s timer must both elapse naturally.
  await control({
    frame: baselineFrame + 60,
    radar_path: '/v2/radar/a487536b232a',
  });
  await expect
    .poll(
      async () =>
        (await events()).filter(
          (e) =>
            e.event === 'request' &&
            e.path?.includes('/radar/a487536b232a/512/2/')
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
  expect(refreshed.textures - initial.textures).toBeLessThanOrEqual(4);
  const observed = await events();
  expect(
    observed.filter(
      (e) => e.event === 'request' && e.path === '/public/weather-maps.json'
    )
  ).toHaveLength(2);
  expect(
    observed.filter(
      (e) => e.event === 'request' && e.path?.includes('/coverage/0/512/2/')
    )
  ).toHaveLength(
    16 *
      (Math.floor(Date.now() / 86400000) - Math.floor(enabledAt / 86400000) + 1)
  );
  expect(
    observed.filter(
      (e) =>
        e.event === 'request' &&
        e.path?.includes('/radar/') &&
        e.path?.includes('/512/2/')
    )
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

// A probe observes native owners and shader uniforms. It neither replaces their
// loaders nor injects textures. Alternate opacity values are inspection only.
async function opacity(page: import('@playwright/test').Page, value: number) {
  await page.evaluate((alpha) => {
    const roots = (
      window as unknown as {
        __overviewEvidenceRoots: Array<{
          containerInfo?: {
            getState?: () => import('@react-three/fiber').RootState;
          };
        }>;
      }
    ).__overviewEvidenceRoots;
    const s = roots
      .find(
        (root) => root.containerInfo?.getState?.().gl.domElement.isConnected
      )
      ?.containerInfo?.getState?.();
    if (!s) throw new Error('No native renderer');
    const material = (
      s.scene.getObjectByName(
        'Overview precipitation radar'
      ) as import('three').Mesh
    ).material as import('three').ShaderMaterial;
    material.uniforms.radarOpacity.value = alpha;
    s.gl.render(s.scene, s.camera);
  }, value);
}

async function aim(
  page: import('@playwright/test').Page,
  lat: number,
  lon: number,
  radius = 3
) {
  await weatherPixel(page, lat, lon, false, radius);
  await settledOverviewCamera(page);
}

// Seed operational overlays through their production API; simulated aircraft,
// native GEP, telemetry and borders stay present throughout these inspections.
async function seedOverlays(
  request: import('@playwright/test').APIRequestContext
) {
  const waypointTime = (offset: number) =>
    new Date(Date.now() + offset).toISOString().replace('T', ' ').slice(0, 19) +
    'Z';
  const mission = 'weather-opacity';
  const leg = 'weather-leg';
  const created = await request.post('/api/v2/missions', {
    data: {
      id: mission,
      name: 'Weather opacity acceptance',
      legs: [
        {
          id: leg,
          name: 'Storm route',
          route_id: 'weather-route',
          transports: { initial_x_satellite_id: 'X-1' },
        },
      ],
    },
  });
  expect(created.ok(), await created.text()).toBe(true);
  const kml = `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Weather acceptance</name><Placemark><name>Storm departure</name><description>Time Over Waypoint: ${waypointTime(-600000)}</description><Point><coordinates>-78,32,10000</coordinates></Point></Placemark><Placemark><name>Storm arrival</name><description>Time Over Waypoint: ${waypointTime(1800000)}</description><Point><coordinates>-74,34,10000</coordinates></Point></Placemark><Placemark><name>Weather route</name><LineString><coordinates>-78,32,10000 -76,33,10000 -74,34,10000</coordinates></LineString></Placemark></Document></kml>`;
  const uploaded = await request.put(
    `/api/v2/missions/${mission}/legs/${leg}/route`,
    {
      multipart: {
        file: {
          name: 'weather-acceptance.kml',
          mimeType: 'application/vnd.google-earth.kml+xml',
          buffer: Buffer.from(kml),
        },
      },
    }
  );
  expect(uploaded.ok(), await uploaded.text()).toBe(true);
  const route = await uploaded.json();
  const activated = await request.post(
    `/api/v2/missions/${mission}/legs/${leg}/activate`
  );
  expect(activated.ok(), await activated.text()).toBe(true);
  const upcoming = await request.get('/api/overview/upcoming-pois');
  expect((await upcoming.json()).pois.length).toBeGreaterThan(0);
  await writeFile(
    `${process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR}/seeded-route.json`,
    JSON.stringify(route)
  );
}

test('native detail acquisition, geographic pixels, resource limits, failure fallback and opacity views', async ({
  page,
  request,
}, info) => {
  test.setTimeout(240_000);
  const frame = Math.floor(Date.now() / 1000) - 120;
  await control({ frame, detail_fixture: true });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: true },
  });
  await seedOverlays(request);
  const responses: { url: string; status: number }[] = [];
  page.on('response', (response) => {
    if (response.url().includes('/api/overview-weather/'))
      responses.push({ url: response.url(), status: response.status() });
  });
  await installWeatherProbe(page);
  await page.goto('/overview');
  await expect(
    page.getByText('Current precipitation', { exact: true })
  ).toBeVisible({ timeout: 30000 });
  const explore = page.getByRole('button', {
    name: 'Explore map',
    exact: true,
  });
  if (await explore.isVisible()) await explore.click();
  await aim(page, 33, -76);
  await expect(page.locator('[data-poi-label]').first()).toBeVisible();
  await expect
    .poll(
      async () =>
        (await weatherSnapshot(page)).detailSlots.filter(Boolean).length,
      { timeout: 30000 }
    )
    .toBeGreaterThan(0);
  await expect
    .poll(async () => Math.max(...(await weatherSnapshot(page)).detailFades), {
      timeout: 10000,
    })
    .toBe(1);
  const native = await weatherSnapshot(page);
  expect(native.weatherGPUBytes).toBeLessThanOrEqual(48 * 1024 * 1024);
  expect(native.detailSlots.filter(Boolean).length).toBeLessThanOrEqual(8);
  expect(
    responses.some(
      (response) =>
        /\/radar\/\d+\/[3-7]\//.test(response.url) && response.status === 200
    )
  ).toBe(true);
  await expect
    .poll(
      async () => {
        const sample = await weatherPixel(page, 32, -75, true, 3);
        return sample.withWeather[1] - sample.withWeather[2];
      },
      { timeout: 30000 }
    )
    .toBeGreaterThan(15);
  // Sample off the populated route: route/aircraft color must not satisfy the
  // precipitation assertion. Overlay visibility is retained for comparison.
  const storm = await weatherPixel(page, 32, -75, true, 3);
  expect(storm.withWeather[1]).toBeGreaterThan(storm.withWeather[2] + 15);
  expect(storm.withWeather[1] - storm.withoutWeather[1]).toBeGreaterThan(15);
  await aim(page, 36, -76);
  await page.waitForTimeout(1000);
  const absent = await weatherPixel(page, 36, -76, true, 3);
  const hatch = [];
  for (let offset = 0; offset < absent.patchWithWeather.length; offset += 4) {
    const delta = [0, 1, 2].map(
      (channel) =>
        absent.patchWithWeather[offset + channel] -
        absent.patchWithoutWeather[offset + channel]
    );
    if (Math.max(...delta) > 8) hatch.push(delta);
  }
  expect(hatch.length).toBeGreaterThan(0);
  expect(
    hatch.every((delta) => Math.max(...delta) - Math.min(...delta) < 12)
  ).toBe(true);
  await expect
    .poll(
      async () =>
        (await weatherSnapshot(page)).detailSlots.filter(Boolean).length
    )
    .toBeGreaterThan(0);
  const views = [];
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
    await aim(page, 33, -76);
    for (const night of [false, true]) {
      await lights(page, night);
      for (const alpha of [0.35, 0.4, 0.45, 0.72]) {
        await opacity(page, alpha);
        const pixel = await weatherPixel(page, 33, -76, night, 3);
        const snapshot = await weatherSnapshot(page);
        expect(snapshot.weatherGPUBytes).toBeLessThanOrEqual(48 * 1024 * 1024);
        expect(snapshot.work?.peakDecodedBytes).toBeLessThanOrEqual(
          96 * 1024 * 1024
        );
        const filename = `detail-${view}-${night ? 'night' : 'day'}-${alpha}.png`;
        await page.screenshot({ path: info.outputPath(filename) });
        views.push({ view, night, alpha, pixel, snapshot, filename });
      }
    }
    await lights(page, false);
    if (view === 'fullscreen')
      await page.evaluate(() => document.exitFullscreen());
  }
  await opacity(page, 0.4);
  if (await explore.isVisible()) await explore.click();
  await aim(page, 33, -76, 5);
  const touchBefore = await settledOverviewCamera(page);
  const touch = await page.context().newCDPSession(page);
  try {
    await touch.send('Emulation.setTouchEmulationEnabled', { enabled: true });
    const box = (await page.locator('.overview-globe canvas').boundingBox())!;
    const x = box.x + box.width * 0.5,
      y = box.y + box.height * 0.4;
    await touch.send('Input.dispatchTouchEvent', {
      type: 'touchStart',
      touchPoints: [
        { x: x - 20, y, id: 1 },
        { x: x + 20, y, id: 2 },
      ],
    });
    for (const spread of [25, 30, 40, 55])
      await touch.send('Input.dispatchTouchEvent', {
        type: 'touchMove',
        touchPoints: [
          { x: x - spread, y, id: 1 },
          { x: x + spread, y, id: 2 },
        ],
      });
    await touch.send('Input.dispatchTouchEvent', {
      type: 'touchEnd',
      touchPoints: [],
    });
  } finally {
    await touch.detach();
  }
  const touchAfter = await settledOverviewCamera(page);
  expect(Math.hypot(...touchAfter.position)).toBeLessThan(
    Math.hypot(...touchBefore.position)
  );
  const beforeFailure = await weatherSnapshot(page);
  await control({ frame, detail_fixture: true, detail_fail: true });
  await aim(page, 33, 40);
  await page.waitForTimeout(2000);
  await expect(
    page.getByText('Current precipitation', { exact: true })
  ).toBeVisible();
  expect((await weatherSnapshot(page)).radar).toBe(beforeFailure.radar);
  await page.goto('/configuration');
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  const observed = await events();
  const attempts = observed.filter((event) => event.event === 'request');
  const paths = new Map(attempts.map((event) => [event.stream_id, event.path]));
  const active = new Set<string>();
  let peakActive = 0,
    peakDetail = 0;
  for (const event of observed) {
    if (event.stream_id && event.event === 'dial') active.add(event.stream_id);
    if (event.stream_id && event.event === 'close')
      active.delete(event.stream_id);
    peakActive = Math.max(peakActive, active.size);
    peakDetail = Math.max(
      peakDetail,
      [...active].filter((id) => /\/512\/[3-7]\//.test(paths.get(id) ?? ''))
        .length
    );
  }
  expect(peakActive).toBeLessThanOrEqual(4);
  expect(peakDetail).toBeLessThanOrEqual(2);
  for (const event of attempts) {
    const window = attempts.filter(
      (other) => other.at > event.at - 60 && other.at <= event.at
    );
    expect(window.length).toBeLessThanOrEqual(90);
    expect(
      window.filter((other) => /\/512\/[3-7]\//.test(other.path ?? '')).length
    ).toBeLessThanOrEqual(30);
  }
  await writeFile(
    info.outputPath('detail-evidence.json'),
    JSON.stringify(
      {
        sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
        native,
        peakActive,
        peakDetail,
        touchBefore,
        touchAfter,
        storm,
        absent,
        views,
        responses,
        observed,
      },
      null,
      2
    )
  );
});

test('normalized alternate source fixture drives native max zoom and displayed attribution', async ({
  page,
  request,
}, info) => {
  await page.waitForTimeout(61_000);
  const frame = Math.floor(Date.now() / 1000) - 120;
  await control({
    frame,
    source: 'fixture-radar',
    provenance: 'Fixture observed precipitation',
    max_zoom: 5,
    detail_fixture: true,
  });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: true },
  });
  await installWeatherProbe(page);
  await page.goto('/overview');
  await expect(
    page.getByText('Current precipitation', { exact: true })
  ).toBeVisible({ timeout: 30000 });
  await expect(
    page.getByRole('link', { name: 'Fixture radar' })
  ).toHaveAttribute('href', 'https://example.com/radar');
  const manifest = await (
    await request.get('/api/overview-weather/frame')
  ).json();
  expect(manifest.source).toBe('fixture-radar');
  expect(manifest.max_zoom).toBe(5);
  await aim(page, 33, -76);
  await expect
    .poll(
      async () =>
        (await weatherSnapshot(page)).detailSlots.filter(Boolean).length,
      { timeout: 30000 }
    )
    .toBeGreaterThan(0);
  const snapshot = await weatherSnapshot(page);
  expect(snapshot.weatherGPUBytes).toBeLessThanOrEqual(48 * 1024 * 1024);
  expect(snapshot.work?.peakDecodedBytes).toBeLessThanOrEqual(96 * 1024 * 1024);
  await page.screenshot({ path: info.outputPath('normalized-source.png') });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  await writeFile(
    info.outputPath('normalized-source.json'),
    JSON.stringify({ manifest, snapshot }, null, 2)
  );
});

async function demandReplay(
  page: import('@playwright/test').Page,
  keys: { z: number; x: number; y: number }[]
) {
  await page.evaluate((tiles) => {
    type Fiber = {
      memoizedProps?: {
        capabilities?: unknown;
        onDemand?: (demand: {
          keys: typeof tiles;
          level: number;
          texelPixels: number;
        }) => void;
      };
      child?: Fiber;
      sibling?: Fiber;
    };
    const roots = (
      window as unknown as { __overviewEvidenceRoots: { current?: Fiber }[] }
    ).__overviewEvidenceRoots;
    function find(node: Fiber | undefined): Fiber | undefined {
      if (!node) return;
      if (node.memoizedProps?.onDemand && node.memoizedProps.capabilities)
        return node;
      return find(node.child) ?? find(node.sibling);
    }
    const observer = roots.map((root) => find(root.current)).find(Boolean);
    if (!observer?.memoizedProps?.onDemand)
      throw new Error('No production demand observer');
    observer.memoizedProps.onDemand({
      keys: tiles,
      level: tiles[0]?.z ?? 2,
      texelPixels: 1,
    });
  }, keys);
}

test('dated actual RainViewer captures use production pairing, scheduling and shader with intact replay freshness fences', async ({
  page,
  request,
}, info) => {
  test.setTimeout(240_000);
  // Keep shared rolling admission history intact; this is an actual wait, not
  // a provider-budget reset or production-timer override.
  await page.waitForTimeout(61_000);
  const captures = JSON.parse(
    await readFile(
      `${process.env.WEATHER_ACCEPTANCE_CAPTURE_DIR}/capture.json`,
      'utf8'
    )
  );
  const match = captures.metadata.comparisons.find(
    (comparison: { source: string }) => comparison.source === 'mrms'
  );
  const source = captures.snapshots.find(
    (snapshot: { source: string; observed_utc: number }) =>
      snapshot.source === 'rainviewer' && snapshot.observed_utc === 1791253800
  );
  const keys = captures.tiles[match.rainviewer_identity]
    .filter((entry: { key: { z: number } }) => entry.key.z === 5)
    .map((entry: { key: { z: number; x: number; y: number } }) => entry.key);
  expect(keys).toHaveLength(8);
  await control({
    frame: source.observed_utc,
    radar_path: match.radar_path,
    capture_identity: match.rainviewer_identity,
    replay_utc_ms: source.captured_utc * 1000,
    provenance: 'RainViewer observed radar (dated capture replay)',
  });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: true },
  });
  await installWeatherProbe(page);
  await page.goto('/overview');
  await expect(
    page.getByText('Current precipitation', { exact: true })
  ).toBeVisible({ timeout: 30000 });
  const explore = page.getByRole('button', {
    name: 'Explore map',
    exact: true,
  });
  if (await explore.isVisible()) await explore.click();
  await aim(page, match.region.latitude, match.region.longitude);
  // Captured regional z5 demand is a bounded replay input. Native camera-driven
  // selection is verified separately above; no textures or shader are replaced.
  await page.waitForTimeout(1250);
  await demandReplay(page, []);
  const baseline = await weatherPixel(
    page,
    match.region.latitude,
    match.region.longitude,
    true,
    3
  );
  await demandReplay(page, keys);
  await expect
    .poll(
      async () =>
        (await weatherSnapshot(page)).detailSlots.filter(Boolean).length,
      { timeout: 30000 }
    )
    .toBe(8);
  await page.waitForTimeout(250);
  const refined = await weatherPixel(
    page,
    match.region.latitude,
    match.region.longitude,
    true,
    3
  );
  expect(refined.patchWithWeather).not.toEqual(baseline.patchWithWeather);
  const manifest = await (
    await request.get('/api/overview-weather/frame')
  ).json();
  expect(manifest.frame_time_ms).toBe(source.observed_utc * 1000);
  expect(manifest.generated_at_ms - manifest.frame_time_ms).toBeLessThan(
    1200000
  );
  const records = [];
  for (const night of [false, true]) {
    await lights(page, night);
    await weatherPixel(
      page,
      match.region.latitude,
      match.region.longitude,
      night,
      3
    );
    const filename = `rainviewer-production-replay-${night ? 'night' : 'day'}.png`;
    await page.screenshot({ path: info.outputPath(filename) });
    records.push({ night, filename, snapshot: await weatherSnapshot(page) });
  }
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  await writeFile(
    info.outputPath('actual-replay.json'),
    JSON.stringify(
      {
        sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
        kind: 'historical capture replay through production owners',
        cameraSelection:
          'bounded recorded z5 replay demand; native selector separately verified',
        source,
        match,
        keys,
        manifest,
        baseline,
        refined,
        records,
      },
      null,
      2
    )
  );
});

test('native coverage stays conservative at shared boundaries, fades and antimeridian fallback', async ({
  page,
  request,
}, info) => {
  test.setTimeout(240000);
  // Source-switch fixtures share the real rolling allowance with replay.
  await page.waitForTimeout(61000);
  const frame = Math.floor(Date.now() / 1000) - 120;
  await control({ frame, detail_fixture: true, boundary_fixture: true });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  await request.put('/api/overview-weather/settings', {
    data: { enabled: true },
  });
  await installWeatherProbe(page);
  await page.goto('/overview');
  await expect(
    page.getByText('Current precipitation', { exact: true })
  ).toBeVisible({ timeout: 30000 });
  const explore = page.getByRole('button', {
    name: 'Explore map',
    exact: true,
  });
  if (await explore.isVisible()) await explore.click();
  const evidence = [];
  for (const edge of [0, 180]) {
    await aim(page, 10, edge === 180 ? 179 : -1);
    await expect
      .poll(
        async () => {
          const s = await weatherSnapshot(page);
          const u = edge === 180 ? 1 : 0.5;
          return s.detailBounds.filter(
            (b, i) =>
              s.detailSlots[i] &&
              b[1] < 0.4721 &&
              b[3] > 0.4721 &&
              (Math.abs(b[0] - (u % 1)) < 1e-6 || Math.abs(b[2] - u) < 1e-6)
          ).length;
        },
        { timeout: 30000 }
      )
      .toBeGreaterThanOrEqual(2);
    const s = await weatherSnapshot(page);
    const b = s.detailBounds.find(
      (b, i) => s.detailSlots[i] && b[1] < 0.4721 && b[3] > 0.4721
    )!;
    const epsilon = (360 * (b[2] - b[0])) / 510 / 4;
    for (const fade of [0.25, 0.5, 1]) {
      const sample = await boundaryPixel(page, edge - epsilon, fade, false);
      const actualDistance = (edge - sample.sampleLongitude + 360) % 360;
      expect(actualDistance).toBeGreaterThan(0);
      expect(actualDistance).toBeLessThan(epsilon * 4);
      expect(
        hatchColumn(sample).length,
        `covered side next to missing neighbor: edge=${edge}, fade=${fade}`
      ).toBeGreaterThan(0);
      evidence.push({ edge, fade, sample });
    }
    const fallback = await boundaryPixel(page, edge - epsilon, 1, true);
    expect(hatchColumn(fallback)).toHaveLength(0);
    if (edge === 0) {
      const absentFallback = await boundaryPixel(page, epsilon, 0.5, true);
      await writeFile(
        info.outputPath('boundary-diagnostic.json'),
        JSON.stringify(
          { edge, epsilon, evidence, fallback, absentFallback },
          null,
          2
        )
      );
      expect(absentFallback.sampleLongitude).toBeGreaterThan(0);
      expect(absentFallback.sampleLongitude).toBeLessThan(epsilon * 4);
      expect(hatchColumn(absentFallback).length).toBeGreaterThan(0);
      evidence.push({ edge, absentFallback });
    }
    evidence.push({ edge, fallback, snapshot: s });
  }
  await page.goto('/configuration');
  await request.put('/api/overview-weather/settings', {
    data: { enabled: false },
  });
  await writeFile(
    info.outputPath('coverage-boundary-evidence.json'),
    JSON.stringify(evidence, null, 2)
  );
});

type BoundarySample = {
  patchWithWeather: number[];
  patchWithoutWeather: number[];
  sampleLongitude: number;
};
function hatchColumn(sample: BoundarySample) {
  const marked = [];
  for (let row = 0; row < 12; row++) {
    const offset = (row * 12 + 6) * 4;
    const delta = [0, 1, 2].map(
      (c) =>
        sample.patchWithWeather[offset + c] -
        sample.patchWithoutWeather[offset + c]
    );
    if (Math.max(...delta) > 8) {
      expect(Math.max(...delta) - Math.min(...delta)).toBeLessThan(12);
      marked.push(delta);
    }
  }
  return marked;
}
async function boundaryPixel(
  page: import('@playwright/test').Page,
  longitude: number,
  fade: number,
  onlyContaining: boolean
) {
  return page.evaluate(
    ({ longitude, fade, onlyContaining }) => {
      const target = window as unknown as {
        __overviewEvidenceRoots: {
          containerInfo?: {
            getState?: () => import('@react-three/fiber').RootState;
          };
        }[];
        __weatherPixel: (
          lat: number,
          lon: number,
          dark: boolean,
          radius: number
        ) => BoundarySample;
      };
      const state = target.__overviewEvidenceRoots
        .find(
          (root) => root.containerInfo?.getState?.().gl.domElement.isConnected
        )
        ?.containerInfo?.getState?.();
      if (!state) throw new Error('No native renderer');
      const material = (
        state.scene.getObjectByName(
          'Overview precipitation radar'
        ) as import('three').Mesh
      ).material as import('three').ShaderMaterial;
      const uniforms = material.uniforms;
      const originalValid = [...uniforms.detailValid.value];
      const originalFades = [...uniforms.detailFades.value];
      const originalOpacity = uniforms.radarOpacity.value;
      const u = (((longitude / 360 + 0.5) % 1) + 1) % 1;
      let aimLongitude = longitude;
      for (let i = 0; i < 2; i++) {
        const first = target.__weatherPixel(10, aimLongitude, true, 3);
        aimLongitude -= ((first.sampleLongitude - longitude + 540) % 360) - 180;
      }
      try {
        // Observe mask output alone, without replacing textures or the shader.
        uniforms.radarOpacity.value = 0;
        uniforms.detailFades.value.fill(fade);
        if (onlyContaining)
          uniforms.detailValid.value.forEach((_value: number, i: number) => {
            const b = uniforms.detailBounds.value[i] as import('three').Vector4;
            if (!(u >= b.x && u < b.z && 0.4721 >= b.y && 0.4721 < b.w))
              uniforms.detailValid.value[i] = 0;
          });
        return target.__weatherPixel(10, aimLongitude, true, 3);
      } finally {
        uniforms.detailValid.value.set(originalValid);
        uniforms.detailFades.value.set(originalFades);
        uniforms.radarOpacity.value = originalOpacity;
      }
    },
    { longitude, fade, onlyContaining }
  );
}

async function lights(page: import('@playwright/test').Page, night: boolean) {
  await page.evaluate((dark) => {
    const target = window as unknown as {
      __overviewEvidenceRoots: {
        containerInfo?: {
          getState?: () => import('@react-three/fiber').RootState;
        };
      }[];
      __weatherLights?: { light: import('three').Light; intensity: number }[];
    };
    const state = target.__overviewEvidenceRoots
      .find(
        (root) => root.containerInfo?.getState?.().gl.domElement.isConnected
      )
      ?.containerInfo?.getState?.();
    if (!state) throw new Error('No native renderer');
    if (!target.__weatherLights) {
      target.__weatherLights = [];
      state.scene.traverse((node) => {
        if ((node as import('three').Light).isLight) {
          const light = node as import('three').Light;
          target.__weatherLights!.push({ light, intensity: light.intensity });
        }
      });
    }
    for (const entry of target.__weatherLights)
      entry.light.intensity = dark ? 0 : entry.intensity;
    state.gl.render(state.scene, state.camera);
  }, night);
}
