import { readFile, rename, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { expect, test, type APIRequestContext } from '@playwright/test';
import { installWeatherProbe } from './support/overview-weather-probe';
import {
  overviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';
import {
  routeSigmetSnapshot,
  setVisibility,
} from './support/route-sigmets-probe';
import {
  seedSimulationRunMission,
  startSimulation,
} from './support/simulation-run-mission';

const endpoint = '/api/aviation-weather/v1/route-sigmets';
const output = process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR!;
let generation = 100;
async function control(changes: Record<string, unknown>) {
  const path = process.env.WEATHER_ACCEPTANCE_CONTROL_PATH!;
  const previous = JSON.parse(await readFile(path, 'utf8'));
  await writeFile(path + '.next', JSON.stringify({ ...previous, ...changes }));
  await rename(path + '.next', path);
}
async function feed(name: string, changes: Record<string, unknown> = {}) {
  await control({
    sigmet_fixture: `${name}-sigmets.json`,
    aviation_generation: ++generation,
    aviation_failure: false,
    aviation_delay_ms: 0,
    ...changes,
  });
}
async function snapshot(request: APIRequestContext) {
  const response = await request.get(endpoint);
  expect(response.status(), await response.text()).toBe(200);
  expect(response.headers()['cache-control']).toBe('no-store');
  return response.json();
}
async function route(
  request: APIRequestContext,
  coordinates: string,
  name = 'Synthetic route SIGMET control'
) {
  const uploaded = await request.post('/api/routes/upload', {
    multipart: {
      file: {
        name: `route-sigmets-${randomUUID()}.kml`,
        mimeType: 'application/vnd.google-earth.kml+xml',
        buffer: Buffer.from(
          `<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${name}</name><Placemark><LineString><coordinates>${coordinates}</coordinates></LineString></Placemark></Document></kml>`
        ),
      },
    },
  });
  expect(uploaded.status(), await uploaded.text()).toBe(201);
  const id = (await uploaded.json()).id;
  expect((await request.post(`/api/routes/${id}/activate`)).ok()).toBe(true);
  return id as string;
}
async function events() {
  return (
    await readFile(
      process.env.WEATHER_ACCEPTANCE_CONTROL_PATH!.replace(
        'control.json',
        'aviation-events.jsonl'
      ),
      'utf8'
    )
  )
    .trim()
    .split('\n')
    .map((line) => JSON.parse(line));
}

test('independent Configuration and passive Overview: propagation, native spans, lineage, routes and disposal', async ({
  browser,
  request,
}, info) => {
  test.setTimeout(300000);
  const configContext = await browser.newContext({
    baseURL: process.env.WEATHER_ACCEPTANCE_BASE_URL,
  });
  const overviewContext = await browser.newContext({
    baseURL: process.env.WEATHER_ACCEPTANCE_BASE_URL,
    viewport: { width: 1920, height: 1080 },
  });
  const config = await configContext.newPage(),
    overview = await overviewContext.newPage();
  const errors: string[] = [],
    elapsed: number[] = [],
    snapshots = [],
    scenarios: Record<string, unknown> = {};
  overview.on('pageerror', (error) => errors.push(error.message));
  await installWeatherProbe(overview);
  try {
    await feed('route', { replay_utc_ms: null });
    const initialGeneration = generation;
    const routeId = await route(request, '-82,35 -65,35');
    await overview.goto('/overview');
    await config.goto('/configuration');
    await config.getByRole('tab', { name: 'Weather', exact: true }).click();
    const sigmet = config.getByRole('switch', {
      name: 'International SIGMET advisories',
      exact: true,
    });
    await expect(sigmet).not.toBeChecked();
    const save = config.waitForResponse(
      (r) =>
        r.url().endsWith('/aviation-weather/v1/settings') &&
        r.request().method() === 'PUT'
    );
    await sigmet.focus();
    await config.keyboard.press('Space');
    expect((await save).ok()).toBe(true);
    let started = Date.now();
    const notices = overview.getByRole('region', {
      name: 'Route SIGMET advisories',
    });
    await expect(notices.getByRole('article')).toHaveCount(3, {
      timeout: 8000,
    });
    elapsed.push(Date.now() - started);
    await expect(notices).toContainText('4 pending route advisories');
    await expect(notices).toContainText('1 additional in Configuration');
    await expect(notices).toContainText(
      'Altitude and passage-time match not evaluated'
    );
    await expect(notices.getByRole('button')).toHaveCount(0);
    await expect(overview.getByRole('switch')).toHaveCount(0);
    await expect(
      config.getByRole('region', { name: 'Route intersection unknown' })
    ).toContainText('C1');
    const initial = await snapshot(request);
    expect(initial.entries).toHaveLength(4);
    expect(initial.unresolved.length).toBeGreaterThan(0);
    scenarios.initial = initial;
    for (const name of [
      'METAR / SPECI observations',
      'TAF terminal forecasts',
      'Precipitation radar',
    ]) {
      const toggle = config.getByRole('switch', { name, exact: true });
      if (!(await toggle.isChecked())) await toggle.click();
      await expect(toggle).toBeChecked();
    }
    await expect
      .poll(
        async () => (await routeSigmetSnapshot(overview)).layers.every(Boolean),
        { timeout: 30000 }
      )
      .toBe(true);
    const loaded = await routeSigmetSnapshot(overview, true);
    snapshots.push(loaded);
    expect(
      loaded.objects.filter((o) => o.name === 'Route advisory outline').length
    ).toBe(3);
    expect(
      loaded.objects.filter((o) => o.name === 'Confirmed route span').length
    ).toBeGreaterThanOrEqual(3);
    expect(
      loaded.objects
        .filter((o) => o.vertices > 0)
        .every((o) => o.depthTest.every(Boolean))
    ).toBe(true);
    expect(loaded.calls).toBeGreaterThan(0);
    const baseBytes = loaded.objects.find(
      (object) => object.name === 'Native international SIGMET advisories'
    )!.bytes;
    const filter = config.getByRole('switch', {
      name: 'Intersecting route only',
      exact: true,
    });
    const filteredSave = config.waitForResponse(
      (response) =>
        response.url().endsWith('/aviation-weather/v1/settings') &&
        response.request().method() === 'PUT'
    );
    await filter.click();
    expect((await filteredSave).ok()).toBe(true);
    started = Date.now();
    await expect
      .poll(
        async () =>
          (await routeSigmetSnapshot(overview)).objects.find(
            (object) => object.name === 'Native international SIGMET advisories'
          )?.bytes ?? baseBytes,
        { timeout: 8000 }
      )
      .toBeLessThan(baseBytes);
    elapsed.push(Date.now() - started);
    await expect(notices.getByRole('article')).toHaveCount(3);
    scenarios.filtered = await snapshot(request);
    const explore = overview.getByRole('button', {
      name: 'Explore map',
      exact: true,
    });
    if (await explore.isVisible()) await explore.click();
    // A real manual gesture freezes automatic aircraft/route reframing.
    const canvas = (await overview
      .locator('.overview-globe canvas')
      .boundingBox())!;
    await overview.mouse.move(
      canvas.x + canvas.width * 0.65,
      canvas.y + canvas.height * 0.6
    );
    await overview.mouse.down();
    await overview.mouse.move(
      canvas.x + canvas.width * 0.65 + 35,
      canvas.y + canvas.height * 0.65,
      { steps: 5 }
    );
    await overview.mouse.up();
    await expect(
      overview.getByText('Route overview', { exact: true })
    ).toHaveCount(0);
    let camera = await settledOverviewCamera(overview),
      stableFrames = 0;
    await expect
      .poll(
        async () => {
          const current = await overviewCamera(overview);
          const delta = Math.max(
            ...(['position', 'quaternion', 'target'] as const).flatMap((key) =>
              current[key].map((value, index) =>
                Math.abs(value - camera[key][index])
              )
            )
          );
          stableFrames = delta < 1e-11 ? stableFrames + 1 : 0;
          camera = current;
          return stableFrames;
        },
        { timeout: 15000, intervals: [100] }
      )
      .toBeGreaterThanOrEqual(3);
    const focus = await overview.evaluate(
      () => document.activeElement?.outerHTML
    );
    const clear = config.getByRole('button', {
      name: /Clear advisory · KZNY R1 /,
    });
    const changed = config.waitForResponse(
      (r) =>
        r.url().endsWith('/acknowledgement') && r.request().method() === 'PUT'
    );
    await clear.focus();
    await config.keyboard.press('Enter');
    expect((await changed).ok()).toBe(true);
    started = Date.now();
    await expect(notices).toContainText('3 pending route advisories', {
      timeout: 8000,
    });
    elapsed.push(Date.now() - started);
    const cleared = await snapshot(request);
    expect(
      cleared.entries.filter((e: { acknowledged: boolean }) => e.acknowledged)
    ).toHaveLength(1);
    const reopen = config.getByRole('button', {
      name: /Show again · KZNY R1 /,
    });
    await expect(reopen).toBeEnabled();
    const again = config.waitForResponse(
      (r) =>
        r.url().endsWith('/acknowledgement') && r.request().method() === 'PUT'
    );
    await reopen.click();
    expect((await again).ok()).toBe(true);
    started = Date.now();
    await expect(notices.getByRole('article').first()).toContainText('R1', {
      timeout: 8000,
    });
    elapsed.push(Date.now() - started);
    const afterCamera = await overviewCamera(overview);
    for (const key of ['position', 'quaternion', 'target'] as const)
      for (const [index, value] of afterCamera[key].entries())
        expect(value).toBeCloseTo(camera[key][index], 10);
    expect(afterCamera.zoom).toBe(camera.zoom);
    scenarios.camera = { before: camera, after: afterCamera };
    expect(
      await overview.evaluate(() => document.activeElement?.outerHTML)
    ).toBe(focus);
    for (const [name, size] of [
      ['desktop', { width: 1920, height: 1080 }],
      ['mobile', { width: 390, height: 844 }],
    ] as const) {
      await overview.setViewportSize(size);
      await expect(notices.getByRole('article')).toHaveCount(3);
      await expect(overview.getByLabel('Map status')).toBeVisible();
      if (name === 'mobile')
        expect(
          await notices.evaluate((n) => !n.closest('.overview-globe'))
        ).toBe(true);
      await overview.screenshot({
        path: info.outputPath(`route-sigmets-${name}.png`),
        fullPage: true,
      });
    }
    await overview.setViewportSize({ width: 1920, height: 1080 });
    await overview
      .getByRole('button', { name: 'Enter fullscreen overview' })
      .click();
    await expect
      .poll(() => overview.evaluate(() => !!document.fullscreenElement))
      .toBe(true);
    expect(
      await notices.evaluate((n) => !!document.fullscreenElement?.contains(n))
    ).toBe(true);
    await overview.screenshot({
      path: info.outputPath('route-sigmets-fullscreen.png'),
    });
    await overview.evaluate(() => document.exitFullscreen());
    // Keep actual API mutations and reads; only upstream transport changes.
    await feed('new');
    await expect
      .poll(async () => (await snapshot(request)).entries.length)
      .toBe(5);
    await expect(notices).toContainText('5 pending route advisories', {
      timeout: 8000,
    });
    await feed('amended');
    await expect
      .poll(async () =>
        (await snapshot(request)).entries.some(
          (e: { semantic_digest: string }) =>
            !initial.entries.some(
              (old: { semantic_digest: string }) =>
                old.semantic_digest === e.semantic_digest
            )
        )
      )
      .toBe(true);
    scenarios.amended = await snapshot(request);
    await feed('cancelled');
    await expect
      .poll(async () => (await snapshot(request)).entries.length)
      .toBe(3);
    scenarios.cancelled = await snapshot(request);
    await feed('reused');
    await expect
      .poll(async () => (await snapshot(request)).entries.length)
      .toBe(4);
    scenarios.reused = await snapshot(request);
    expect(scenarios.reused).not.toEqual(scenarios.cancelled);
    // Delayed old-source completion concurrent with a new active route.
    await feed('route', { aviation_delay_ms: 1500 });
    const delayed = request.get(endpoint);
    await expect
      .poll(async () =>
        (await events()).some(
          (event) =>
            event.layer === 'sigmet' && event.source_generation === generation
        )
      )
      .toBe(true);
    const noMatch = await route(request, '10,0 20,0', 'Nonintersecting route');
    const late = await (await delayed).json();
    expect(late.context.route_id).toBe(noMatch);
    expect(late.entries).toHaveLength(0);
    await control({ aviation_delay_ms: 0 });
    await expect
      .poll(async () => (await snapshot(request)).context?.route_id)
      .toBe(noMatch);
    await expect(notices).toContainText('Nonintersecting route', {
      timeout: 8000,
    });
    await expect(notices.getByRole('article')).toHaveCount(0);
    scenarios.reversed = { late, current: await snapshot(request) };
    await route(request, '0,0 180,0', 'Ambiguous antipodal route');
    await expect
      .poll(async () => (await snapshot(request)).complete)
      .toBe(false);
    await expect(notices).toContainText(/incomplete|unavailable/, {
      timeout: 8000,
    });
    scenarios.incomplete = await snapshot(request);
    expect((await request.post(`/api/routes/${routeId}/activate`)).ok()).toBe(
      true
    );
    await feed('empty');
    await expect
      .poll(async () => (await snapshot(request)).entries.length)
      .toBe(0);
    await expect(notices).toContainText('Coverage unknown or partial');
    scenarios.empty = await snapshot(request);
    await feed('route');
    await expect(notices.getByRole('article')).toHaveCount(3, {
      timeout: 8000,
    });
    const current = await snapshot(request);
    await feed('route', {
      aviation_failure: true,
      replay_utc_ms: current.sigmet_product.fresh_until_ms + 1000,
    });
    await expect
      .poll(async () => (await snapshot(request)).sigmet_product.state)
      .toBe('stale');
    await expect(notices).toContainText('stale', { timeout: 8000 });
    scenarios.stale = await snapshot(request);
    await control({
      replay_utc_ms:
        Math.max(
          ...current.entries.map(
            (e: { expires_at_ms: number }) => e.expires_at_ms
          )
        ) + 1000,
    });
    await expect
      .poll(async () => (await snapshot(request)).entries.length)
      .toBe(0);
    await expect(notices.getByRole('article')).toHaveCount(0, {
      timeout: 8000,
    });
    scenarios.expired = await snapshot(request);
    await feed('route', { replay_utc_ms: null });
    // A fresh context resets its UTC anchor after this explicit time-control rewind.
    await overview.reload();
    await expect(notices.getByRole('article')).toHaveCount(3, {
      timeout: 15000,
    });
    for (let cycle = 0; cycle < 2; cycle++) {
      const owned = await routeSigmetSnapshot(overview, true);
      await setVisibility(overview, true);
      await expect
        .poll(async () => (await routeSigmetSnapshot(overview)).present)
        .toBe(false);
      const hidden = await routeSigmetSnapshot(overview);
      for (const id of owned.resources) expect(hidden.disposed).toContain(id);
      await setVisibility(overview, false);
      await expect
        .poll(async () => (await routeSigmetSnapshot(overview)).present)
        .toBe(true);
      const offlineOwned = await routeSigmetSnapshot(overview, true);
      await overviewContext.setOffline(true);
      await expect
        .poll(async () => (await routeSigmetSnapshot(overview)).present)
        .toBe(false);
      const offline = await routeSigmetSnapshot(overview);
      for (const id of offlineOwned.resources)
        expect(offline.disposed).toContain(id);
      await overviewContext.setOffline(false);
      await expect
        .poll(async () => (await routeSigmetSnapshot(overview)).present)
        .toBe(true);
      snapshots.push(await routeSigmetSnapshot(overview));
    }
    const unmountOwned = await routeSigmetSnapshot(overview, true);
    await config.goto('/overview');
    await overview
      .getByRole('link', { name: 'Configuration', exact: true })
      .click();
    await expect
      .poll(async () => (await routeSigmetSnapshot(overview)).present)
      .toBe(false);
    const unmounted = await routeSigmetSnapshot(overview);
    for (const id of unmountOwned.resources)
      expect(unmounted.disposed).toContain(id);
    expect(unmounted.budget!.gpu).toBe(0);
    snapshots.push(unmounted);
    // Running/completed simulation contexts use 2025 replay geometry and actual weather UTC.
    await feed('route');
    await control({ sigmet_fixture: 'sigmets.json' });
    const seed = await seedSimulationRunMission(request);
    const run = await startSimulation(request, seed, {
      mode: 'target_runtime',
      runtime_seconds: 2,
    });
    await expect
      .poll(async () => (await snapshot(request)).context?.source)
      .toBe('simulation');
    const simulation = await snapshot(request);
    expect(simulation.generated_at_ms).toBeGreaterThan(
      Date.parse('2026-01-01T00:00:00Z')
    );
    expect(simulation.context.run_id).toBeTruthy();
    await expect
      .poll(
        async () =>
          (await (await request.get('/api/simulation/run')).json()).state,
        { timeout: 30000 }
      )
      .toBe('completed');
    expect((await snapshot(request)).context.context_key).toBe(
      simulation.context.context_key
    );
    scenarios.simulation = {
      run,
      snapshot: simulation,
      completed: await snapshot(request),
    };
    await request.post(`/api/v2/missions/${seed.missionId}/legs/deactivate`);
    await request.delete(`/api/v2/missions/${seed.missionId}`);
    for (const value of snapshots) {
      expect(value.budget).toBeDefined();
      expect(value.budget!.peaks.encoded).toBeLessThanOrEqual(16 * 1024 ** 2);
      expect(value.budget!.peaks.decoded).toBeLessThanOrEqual(32 * 1024 ** 2);
      expect(value.budget!.peaks.gpu).toBeLessThanOrEqual(16 * 1024 ** 2);
      expect(value.budget!.peaks.slots).toBeLessThanOrEqual(4);
    }
    const sourceRequests = await events();
    expect(
      sourceRequests.filter(
        (event) =>
          event.layer === 'sigmet' &&
          event.source_generation === initialGeneration
      )
    ).toHaveLength(1);
    expect(errors).toEqual([]);
    await writeFile(
      output + '/route-sigmet-evidence.json',
      JSON.stringify(
        {
          sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
          label:
            'Synthetic source transport; actual production API, Nginx, independent browser contexts and native WebGL',
          elapsed_save_to_display_ms: elapsed,
          assertions_complete: true,
          scenarios,
          snapshots,
          source_requests: sourceRequests,
          errors,
        },
        null,
        2
      )
    );
  } finally {
    try {
      await overviewContext.setOffline(false);
      await request.put('/api/aviation-weather/v1/settings', {
        data: { metar: false, taf: false, sigmet: false },
      });
      await request.put('/api/overview-weather/settings', {
        data: { enabled: false },
      });
      await request.post('/api/routes/deactivate');
      await control({
        aviation_failure: false,
        aviation_delay_ms: 0,
        replay_utc_ms: null,
      });
    } finally {
      await Promise.allSettled([
        configContext.close(),
        overviewContext.close(),
      ]);
    }
  }
});

test('pinned dated real AWC source passes normalization and the native route renderer', async ({
  browser,
  request,
}, info) => {
  const context = await browser.newContext({
    baseURL: process.env.WEATHER_ACCEPTANCE_BASE_URL,
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();
  await installWeatherProbe(page);
  try {
    const manifest = JSON.parse(
      await readFile(output + '/real-source/capture.json', 'utf8')
    );
    const normalized = JSON.parse(
      await readFile(output + '/real-source/normalized.json', 'utf8')
    );
    const feature = normalized.features.find(
      (f: {
        geometry: { type: string } | null;
        properties: {
          valid_from_ms: number;
          expires_at_ms: number;
          cancelled: boolean;
        };
      }) =>
        f.geometry?.type === 'Polygon' &&
        !f.properties.cancelled &&
        f.properties.valid_from_ms <= manifest.captured_at_ms &&
        f.properties.expires_at_ms > manifest.captured_at_ms
    );
    expect(feature).toBeTruthy();
    const ring = feature.geometry.coordinates[0];
    await route(
      request,
      ring
        .slice(0, 3)
        .map((p: number[]) => p.join(','))
        .join(' '),
      'Dated AWC source replay'
    );
    await feed('real', { replay_utc_ms: manifest.captured_at_ms });
    await request.put('/api/aviation-weather/v1/settings', {
      data: { sigmet: true },
    });
    await page.goto('/overview');
    await expect
      .poll(async () => (await snapshot(request)).entries.length, {
        timeout: 30000,
      })
      .toBeGreaterThan(0);
    await expect
      .poll(async () => (await routeSigmetSnapshot(page)).present, {
        timeout: 30000,
      })
      .toBe(true);
    const native = await routeSigmetSnapshot(page);
    expect(native.objects.some((o) => o.name === 'Confirmed route span')).toBe(
      true
    );
    const admitted = await snapshot(request);
    const payload = await request.get(admitted.sigmet_product.payload.path);
    expect(payload.ok()).toBe(true);
    const collection = await payload.json();
    expect(collection.features).toHaveLength(151);
    await writeFile(
      output + '/real-source/production-normalized.json',
      JSON.stringify(collection, null, 2)
    );
    await page.screenshot({
      path: info.outputPath('dated-real-source.png'),
      fullPage: true,
    });
    await writeFile(
      output + '/real-source-evidence.json',
      JSON.stringify(
        {
          sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
          replayed: true,
          label: 'Dated AWC capture replay; not current live weather',
          manifest,
          native,
          snapshot: admitted,
        },
        null,
        2
      )
    );
  } finally {
    try {
      await request.put('/api/aviation-weather/v1/settings', {
        data: { sigmet: false },
      });
      await request.post('/api/routes/deactivate');
      await control({ replay_utc_ms: null });
    } finally {
      await context.close();
    }
  }
});
