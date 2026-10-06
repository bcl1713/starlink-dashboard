import { readFile, rename, writeFile } from 'node:fs/promises';
import { expect, test, type Page } from '@playwright/test';
import type { RootState } from '@react-three/fiber';
import type { BufferGeometry, Material, Mesh, Object3D } from 'three';
import {
  installWeatherProbe,
  weatherSnapshot,
} from './support/overview-weather-probe';

const names = [
  'Native METAR / SPECI observations',
  'Native TAF terminal forecasts',
  'Native international SIGMET advisories',
];
const switches = [
  'METAR / SPECI observations',
  'TAF terminal forecasts',
  'International SIGMET advisories',
];
async function control(values: Record<string, unknown>) {
  const path = process.env.WEATHER_ACCEPTANCE_CONTROL_PATH!;
  await writeFile(`${path}.new`, JSON.stringify(values));
  await rename(`${path}.new`, path);
}
async function sourceEvents() {
  try {
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
      .filter(Boolean)
      .map(
        (line) =>
          JSON.parse(line) as { layer: string; source_generation: number }
      );
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}
type ProbeWindow = Window & {
  __overviewEvidenceRoots?: {
    containerInfo?: { getState?: () => RootState };
  }[];
  __aviationDisposals?: string[];
};
async function nativeSnapshot(page: Page, recordDisposals = false) {
  return page.evaluate(
    ({ names, recordDisposals }) => {
      const target = window as ProbeWindow;
      const state = target.__overviewEvidenceRoots
        ?.find(
          (root) => root.containerInfo?.getState?.().gl.domElement.isConnected
        )
        ?.containerInfo?.getState?.();
      if (!state) throw Error('No mounted native renderer');
      target.__aviationDisposals ??= [];
      const objects = names.map((name) => {
        const object = state.scene.getObjectByName(name);
        if (!object) return null;
        let bytes = 0,
          vertices = 0;
        const geometries: string[] = [],
          materials: string[] = [];
        object.traverse((node) => {
          const rendered = node as Object3D & {
            geometry?: BufferGeometry;
            material?: Material | Material[];
          };
          if (rendered.geometry) {
            const geometry = rendered.geometry;
            geometries.push(geometry.uuid);
            vertices += geometry.getAttribute('position').count;
            bytes +=
              Object.values(geometry.attributes).reduce(
                (n, a) => n + a.array.byteLength,
                0
              ) + (geometry.index?.array.byteLength ?? 0);
            if (recordDisposals)
              geometry.addEventListener('dispose', () =>
                target.__aviationDisposals!.push(geometry.uuid)
              );
          }
          for (const material of rendered.material
            ? Array.isArray(rendered.material)
              ? rendered.material
              : [rendered.material]
            : []) {
            materials.push(material.uuid);
            if (recordDisposals)
              material.addEventListener('dispose', () =>
                target.__aviationDisposals!.push(material.uuid)
              );
          }
        });
        return {
          name,
          type: object.type,
          uuid: object.uuid,
          bytes,
          vertices,
          geometries,
          materials,
          renderOrder: object.renderOrder,
        };
      });
      return {
        objects,
        calls: state.gl.info.render.calls,
        geometries: state.gl.info.memory.geometries,
        disposed: [...target.__aviationDisposals],
      };
    },
    { names, recordDisposals }
  );
}
// Observe real WebGL output by toggling only the admitted SIGMET object's
// visibility. No textures, shaders, payloads, or application owners are replaced.
async function advisoryPixel(page: Page, latitude: number, longitude: number) {
  return page.evaluate(
    ({ latitude, longitude }) => {
      const target = window as ProbeWindow;
      const state = target.__overviewEvidenceRoots
        ?.find(
          (root) => root.containerInfo?.getState?.().gl.domElement.isConnected
        )
        ?.containerInfo?.getState?.();
      if (!state) throw Error('No mounted native renderer');
      const mesh = state.scene.getObjectByName(
        'Native international SIGMET advisories'
      ) as Mesh | undefined;
      if (!mesh) throw Error('No native SIGMET mesh');
      const lat = (latitude * Math.PI) / 180,
        lon = (longitude * Math.PI) / 180;
      const controls = state.controls as unknown as {
        setLookAt: (...v: (number | boolean)[]) => void;
        update: (delta: number) => void;
      };
      controls.setLookAt(
        3 * Math.cos(lat) * Math.cos(lon),
        3 * Math.sin(lat),
        -3 * Math.cos(lat) * Math.sin(lon),
        0,
        0,
        0,
        false
      );
      controls.update(0);
      state.camera.updateMatrixWorld();
      const point = state.camera.position
        .clone()
        .set(
          2.026 * Math.cos(lat) * Math.cos(lon),
          2.026 * Math.sin(lat),
          -2.026 * Math.cos(lat) * Math.sin(lon)
        )
        .project(state.camera);
      const gl = state.gl.getContext(),
        x = Math.floor((point.x / 2 + 0.5) * gl.drawingBufferWidth),
        y = Math.floor((point.y / 2 + 0.5) * gl.drawingBufferHeight);
      if (
        x < 2 ||
        y < 2 ||
        x >= gl.drawingBufferWidth - 2 ||
        y >= gl.drawingBufferHeight - 2
      )
        throw Error('Geographic sample falls outside native Canvas');
      const read = () => {
        state.gl.render(state.scene, state.camera);
        const p = new Uint8Array(5 * 5 * 4);
        gl.readPixels(x - 2, y - 2, 5, 5, gl.RGBA, gl.UNSIGNED_BYTE, p);
        return [...p];
      };
      const original = mesh.visible;
      let withAdvisory: number[], withoutAdvisory: number[];
      try {
        mesh.visible = true;
        withAdvisory = read();
        mesh.visible = false;
        withoutAdvisory = read();
      } finally {
        mesh.visible = original;
        state.gl.render(state.scene, state.camera);
      }
      const offset = (2 * 5 + 2) * 4;
      return {
        latitude,
        longitude,
        x,
        y,
        withAdvisory: withAdvisory!.slice(offset, offset + 4),
        withoutAdvisory: withoutAdvisory!.slice(offset, offset + 4),
        patchWithAdvisory: withAdvisory!,
        patchWithoutAdvisory: withoutAdvisory!,
      };
    },
    { latitude, longitude }
  );
}

test('exact production SHA: native station forecasts and advisory topology coexist with radar and dispose on disable', async ({
  context,
  request,
}, info) => {
  test.setTimeout(180000);
  expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
  const frame = Math.floor(Date.now() / 1000) - 120;
  await control({ frame });
  const config = await context.newPage(),
    overview = await context.newPage();
  const errors: string[] = [],
    providerRequests: string[] = [];
  overview.on('pageerror', (error) => errors.push(error.message));
  overview.on('request', (r) => {
    if (/aviationweather\.gov|rainviewer\.com/.test(new URL(r.url()).hostname))
      providerRequests.push(r.url());
  });
  await installWeatherProbe(overview);
  await overview.addInitScript(() =>
    Object.defineProperty(window.crypto, 'subtle', {
      value: undefined,
      configurable: true,
    })
  );
  try {
    await overview.goto('/overview');
    expect(await overview.evaluate(() => window.crypto.subtle)).toBeUndefined();
    await expect(overview.locator('.overview-globe canvas')).toBeVisible();
    await expect
      .poll(async () => (await weatherSnapshot(overview)).calls)
      .toBeGreaterThan(0);
    const baseline = await weatherSnapshot(overview),
      initialStatus = await (await request.get('/api/status')).json();
    expect(await sourceEvents()).toHaveLength(0);
    await expect(overview.getByLabel('Aviation weather status')).toHaveCount(0);
    await config.goto('/configuration');
    for (const name of switches) {
      const toggle = config.getByRole('switch', { name, exact: true });
      await expect(toggle).toBeEnabled();
      await expect(toggle).not.toBeChecked();
    }
    const beforeSettings = await (
      await request.get('/api/aviation-weather/v1/settings')
    ).json();
    expect(beforeSettings).toMatchObject({
      metar: false,
      taf: false,
      sigmet: false,
    });
    for (const name of switches) {
      const toggle = config.getByRole('switch', { name, exact: true });
      await toggle.click();
      await expect(toggle).toBeChecked();
      await expect(toggle).toBeEnabled();
    }
    const status = overview.getByLabel('Aviation weather status');
    for (const text of [
      'METAR / SPECI observations · current',
      'TAF terminal forecasts · current',
      'International SIGMET advisories · current',
    ])
      await expect(status).toContainText(text, { timeout: 30000 });
    await expect(status).toContainText('Coverage unknown');
    await expect(status).toContainText('1 unlocated');
    await expect(status).toContainText('future');
    await expect(status).toContainText('m/s');
    await expect(status).toContainText('m AGL');
    await expect(status).toContainText('UTC');
    await expect(overview.getByRole('switch')).toHaveCount(0);
    const afterSettings = await (
      await request.get('/api/aviation-weather/v1/settings')
    ).json();
    expect(afterSettings).toMatchObject({
      metar: true,
      taf: true,
      sigmet: true,
    });
    expect(afterSettings.revision).toBeGreaterThan(beforeSettings.revision);
    const catalog = await (
      await request.get('/api/aviation-weather/v1/catalog')
    ).json();
    expect(catalog.settings_revision).toBe(afterSettings.revision);
    const products = catalog.products.filter((p: { layer_id: string }) =>
      ['metar', 'taf', 'sigmet'].includes(p.layer_id)
    );
    expect(products).toHaveLength(3);
    const payloadEvidence = [];
    for (const product of products) {
      expect(product.state).toBe('ready');
      const response = await request.get(product.payload.path);
      expect(response.ok()).toBe(true);
      expect(response.headers()['content-type']).toContain(
        'application/geo+json'
      );
      const bytes = await response.body();
      expect(bytes.byteLength).toBe(product.payload.encoded_bytes);
      const collection = JSON.parse(bytes.toString());
      expect(collection.source_id).toBe('awc');
      expect(collection.features.length).toBeGreaterThan(0);
      payloadEvidence.push({
        layer: product.layer_id,
        bytes: bytes.length,
        sha256: product.payload.sha256,
        features: collection.features,
      });
    }
    const loaded = await nativeSnapshot(overview, true);
    expect(loaded.objects.every(Boolean)).toBe(true);
    expect(loaded.objects.map((o) => o!.type)).toEqual([
      'Points',
      'LineSegments',
      'Mesh',
    ]);
    expect(loaded.objects[0]!.vertices).toBe(4);
    expect(loaded.objects[1]!.vertices).toBe(32);
    expect(loaded.objects[2]!.vertices).toBeGreaterThan(100);
    expect(loaded.objects[2]!.vertices).toBeLessThanOrEqual(100000);
    expect(
      loaded.objects.reduce((sum, o) => sum + o!.bytes, 0)
    ).toBeLessThanOrEqual(16 * 1024 ** 2);
    expect((await weatherSnapshot(overview)).canvas).toBe(baseline.canvas);
    const events = await sourceEvents();
    for (const layer of ['metar', 'taf', 'sigmet'])
      expect(events.some((e) => e.layer === layer)).toBe(true);
    const radar = config.getByRole('switch', {
      name: 'Precipitation radar',
      exact: true,
    });
    await radar.click();
    await expect(radar).toBeChecked();
    await expect(
      overview.getByText('Current precipitation', { exact: true })
    ).toBeVisible({ timeout: 30000 });
    const withRadar = await weatherSnapshot(overview);
    expect(withRadar.canvas).toBe(baseline.canvas);
    expect(withRadar.radar).not.toBeNull();
    expect(
      (await nativeSnapshot(overview)).objects.map((o) => o!.uuid)
    ).toEqual(loaded.objects.map((o) => o!.uuid));
    const explore = overview.getByRole('button', {
      name: 'Explore map',
      exact: true,
    });
    if (await explore.isVisible()) await explore.click();
    const pixels = [];
    for (const [lat, lon, inside] of [
      [36, -78, true],
      [40, -74, false],
      [40, 179, true],
      [40, -179, true],
      [40, 0, false],
    ] as const) {
      const sample = await advisoryPixel(overview, lat, lon);
      const difference = Math.max(
        ...sample.withAdvisory
          .slice(0, 3)
          .map((v, i) => Math.abs(v - sample.withoutAdvisory[i]))
      );
      if (inside)
        expect(
          difference,
          `native advisory fill ${lat},${lon}`
        ).toBeGreaterThan(4);
      else
        expect(
          difference,
          `native hole/absence ${lat},${lon}`
        ).toBeLessThanOrEqual(1);
      pixels.push({ ...sample, inside, difference });
    }
    await advisoryPixel(overview, 40, -74);
    await overview.screenshot({
      path: info.outputPath('aviation-desktop.png'),
    });
    await overview
      .getByRole('button', { name: 'Enter fullscreen overview' })
      .click();
    await expect
      .poll(() => overview.evaluate(() => !!document.fullscreenElement))
      .toBe(true);
    await expect(status).toBeVisible();
    expect((await weatherSnapshot(overview)).canvas).toBe(baseline.canvas);
    await overview.screenshot({
      path: info.outputPath('aviation-fullscreen.png'),
    });
    await overview.evaluate(() => document.exitFullscreen());
    await overview.setViewportSize({ width: 390, height: 844 });
    await expect(status).toBeVisible();
    await expect(overview.getByLabel('Map status')).toBeVisible();
    await overview.screenshot({ path: info.outputPath('aviation-mobile.png') });
    await overview.setViewportSize({ width: 1920, height: 1080 });
    for (const name of switches) {
      const toggle = config.getByRole('switch', { name, exact: true });
      await toggle.click();
      await expect(toggle).not.toBeChecked();
      await expect(toggle).toBeEnabled();
    }
    await expect(status).toHaveCount(0, { timeout: 15000 });
    await expect
      .poll(
        async () =>
          (await nativeSnapshot(overview)).objects.filter(Boolean).length
      )
      .toBe(0);
    const disabled = await nativeSnapshot(overview);
    for (const object of loaded.objects)
      for (const uuid of [...object!.geometries, ...object!.materials])
        expect(disabled.disposed).toContain(uuid);
    expect((await weatherSnapshot(overview)).radar).toBe(withRadar.radar);
    expect((await weatherSnapshot(overview)).canvas).toBe(baseline.canvas);
    const failureEventsStart = (await sourceEvents()).length;
    await control({ frame, aviation_failure: true, aviation_generation: 1 });
    for (const name of switches) {
      const toggle = config.getByRole('switch', { name, exact: true });
      await toggle.click();
      await expect(toggle).toBeChecked();
      await expect(toggle).toBeEnabled();
    }
    for (const text of [
      'METAR / SPECI observations · unavailable',
      'TAF terminal forecasts · unavailable',
      'International SIGMET advisories · unavailable',
    ])
      await expect(status).toContainText(text, { timeout: 30000 });
    const failureEvents = (await sourceEvents()).slice(failureEventsStart);
    for (const layer of ['metar', 'taf', 'sigmet'])
      expect(
        failureEvents.some(
          (e) => e.layer === layer && e.source_generation === 1
        )
      ).toBe(true);
    expect((await request.get('/health')).status()).toBe(200);
    const finalStatusResponse = await request.get('/api/status');
    expect(finalStatusResponse.status()).toBe(200);
    const finalStatus = await finalStatusResponse.json();
    expect(finalStatus.timestamp).not.toBe(initialStatus.timestamp);
    expect((await weatherSnapshot(overview)).canvas).toBe(baseline.canvas);
    await expect(overview.getByLabel('Map status')).toBeVisible();
    expect(errors).toEqual([]);
    expect(providerRequests).toEqual([]);
    await writeFile(
      info.outputPath('aviation-evidence.json'),
      JSON.stringify(
        {
          sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
          fixture:
            'Deterministic source-shaped transport fixtures, not live weather evidence',
          baseline,
          loaded,
          withRadar,
          disabled,
          pixels,
          payloadEvidence,
          events,
          failureEvents,
          initialStatus,
          finalStatus,
          errors,
          providerRequests,
        },
        null,
        2
      )
    );
  } finally {
    try {
      await request.put('/api/aviation-weather/v1/settings', {
        data: { metar: false, taf: false, sigmet: false },
      });
      await request.put('/api/overview-weather/settings', {
        data: { enabled: false },
      });
      await control({ frame });
    } finally {
      await Promise.allSettled([config.close(), overview.close()]);
    }
  }
});
