import { readFile, rename, writeFile } from 'node:fs/promises';
import { expect, test, type Page } from '@playwright/test';
import type { RootState } from '@react-three/fiber';
import type {
  Mesh,
  ShaderMaterial,
  DataTexture,
  Object3D,
  Intersection,
} from 'three';
import {
  installWeatherProbe,
  weatherSnapshot,
} from './support/overview-weather-probe';

type NativeWindow = Window & {
  __overviewEvidenceRoots?: {
    containerInfo?: { getState?: () => RootState };
  }[];
};
async function patchControl(changes: Record<string, unknown>) {
  const path = process.env.WEATHER_ACCEPTANCE_CONTROL_PATH!;
  const before = JSON.parse(await readFile(path, 'utf8'));
  await writeFile(path + '.new', JSON.stringify({ ...before, ...changes }));
  await rename(path + '.new', path);
}
async function snapshot(page: Page) {
  return page.evaluate(() => {
    const state = (window as NativeWindow).__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    const object = state?.scene.getObjectByName('Native GFS atmosphere');
    if (!state) return null;
    if (!object) return { present: false, calls: state.gl.info.render.calls };
    const g = object.userData.gfs;
    const lines = state.scene.getObjectByName('GFS wind FROM barbs') as Mesh;
    return {
      present: true,
      calls: state.gl.info.render.calls,
      vertical: g.grid.descriptor.vertical,
      lead: g.grid.descriptor.lead_seconds,
      valid: g.grid.descriptor.valid_at_ms,
      budget: g.budget(),
      bytes: g.bytes,
      barbs: g.barbSamples.length / 9,
      firstSample: Array.from(g.barbSamples.slice(0, 9)),
      firstShaft: Array.from(
        lines.geometry.getAttribute('position').array.slice(0, 6)
      ),
    };
  });
}
// Read the admitted packed raster's real shader and real WebGL framebuffer.
// Diagnostic U/V reuses the same packed texture allocation in place; restore T
// before returning. No test renderer/texture/geometry replaces the production one.
async function samples(
  page: Page,
  coordinates: { latitude: number; longitude: number }[]
) {
  return page.evaluate((coordinates) => {
    const state = (window as NativeWindow).__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    if (!state) throw Error('Native renderer missing');
    const object = state.scene.getObjectByName('Native GFS atmosphere');
    if (!object) throw Error('Native grid missing');
    const grid = object.userData.gfs.grid;
    const mesh = state.scene.getObjectByName('GFS temperature') as Mesh<
        import('three').BufferGeometry,
        ShaderMaterial
      >,
      material = mesh.material;
    const texture = material.uniforms.packedGrid.value as DataTexture,
      packed = texture.image.data as Uint8Array;
    const controls = state.controls as unknown as {
      setLookAt: (...v: (number | boolean)[]) => void;
      update: (n: number) => void;
    };
    const visibility: { node: Object3D; visible: boolean }[] = [];
    state.scene.traverse((node) => {
      if (['Mesh', 'LineSegments', 'Points'].includes(node.type)) {
        visibility.push({ node, visible: node.visible });
        node.visible = node === mesh;
      }
    });
    const gl = state.gl.getContext(),
      out = [];
    try {
      material.uniforms.diagnostic.value = 1;
      for (const geo of coordinates) {
        const lat = (geo.latitude * Math.PI) / 180,
          lon = (geo.longitude * Math.PI) / 180;
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
        const x = Math.floor(gl.drawingBufferWidth / 2),
          y = Math.floor(gl.drawingBufferHeight / 2);
        state.raycaster.setFromCamera(
          {
            x: ((x + 0.5) / gl.drawingBufferWidth) * 2 - 1,
            y: ((y + 0.5) / gl.drawingBufferHeight) * 2 - 1,
          },
          state.camera
        );
        const hits: Intersection[] = [];
        Object.getPrototypeOf(mesh).raycast.call(mesh, state.raycaster, hits);
        hits.sort((a, b) => a.distance - b.distance);
        if (!hits.length) throw Error('No native triangle intersection');
        const point = hits[0].point.clone().normalize(),
          latitude = (Math.asin(point.y) * 180) / Math.PI,
          longitude = (Math.atan2(-point.z, point.x) * 180) / Math.PI;
        const qx = ((((longitude + 180) % 360) + 360) % 360) * 2,
          qy = Math.max(0, Math.min(360, (90 - latitude) * 2)),
          col = Math.floor(qx),
          row = Math.floor(qy),
          fx = qx - col,
          fy = qy - row;
        const contributors = [
          [row * 720 + col, (1 - fx) * (1 - fy)],
          [row * 720 + ((col + 1) % 720), fx * (1 - fy)],
          [Math.min(360, row + 1) * 720 + col, (1 - fx) * fy],
          [Math.min(360, row + 1) * 720 + ((col + 1) % 720), fx * fy],
        ];
        const result: { [key: string]: unknown } = {
          ...geo,
          sampledLatitude: latitude,
          sampledLongitude: longitude,
        };
        for (const name of ['u', 'v', 't']) {
          const values = grid[name] as Int16Array;
          for (let i = 0; i < values.length; i++) {
            packed[i * 4] = values[i] & 255;
            packed[i * 4 + 1] = (values[i] >> 8) & 255;
          }
          texture.needsUpdate = true;
          state.gl.render(state.scene, state.camera);
          const bytes = new Uint8Array(4);
          gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, bytes);
          let expected = 0,
            mask = 0;
          for (const [i, w] of contributors)
            if (w > 0) {
              expected += values[i] * w;
              mask = Math.max(mask, grid.mask[i]);
            }
          const gpu = bytes[0] * 256 + bytes[1] - 32768;
          result[name] = {
            gpu: gpu * 0.01 + (name === 't' ? 273.15 : 0),
            cpu: expected * 0.01 + (name === 't' ? 273.15 : 0),
            gpuMask: bytes[2],
            mask,
            error: Math.abs(gpu - expected) * 0.01,
          };
        }
        const node =
          Math.round((90 - geo.latitude) * 2) * 720 +
          (Math.round((geo.longitude + 180) * 2) % 720);
        result.node = {
          u: grid.u[node] * 0.01,
          v: grid.v[node] * 0.01,
          t: grid.t[node] * 0.01 + 273.15,
          mask: grid.mask[node],
        };
        out.push(result);
      }
    } finally {
      for (let i = 0; i < grid.t.length; i++) {
        packed[i * 4] = grid.t[i] & 255;
        packed[i * 4 + 1] = (grid.t[i] >> 8) & 255;
      }
      texture.needsUpdate = true;
      material.uniforms.diagnostic.value = 0;
      visibility.forEach(({ node, visible }) => {
        node.visible = visible;
      });
      state.gl.render(state.scene, state.camera);
    }
    return out;
  }, coordinates);
}

test('production GFS selection, source/CPU/GPU, native winds, combined views and cancellation', async ({
  browser,
  context,
  request,
}, info) => {
  test.setTimeout(900000);
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
  overview.on('pageerror', (e) => errors.push(e.message));
  overview.on('request', (r) => {
    if (
      /noaa-gfs|aviationweather\.gov|rainviewer\.com/.test(
        new URL(r.url()).hostname
      )
    )
      providerRequests.push(r.url());
  });
  await overview.clock.install();
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
          return v?.present ? `${v.vertical.kind}:${v.lead}` : '';
        },
        { timeout: 90000 }
      )
      .toBe(`${kind}:${lead * 3600}`);
  };
  try {
    await config.goto('/configuration');
    await overview.goto('/overview');
    await other.goto('/overview');
    for (const name of [
      'GFS winds',
      'GFS air temperature',
      'METAR / SPECI observations',
      'TAF terminal forecasts',
      'International SIGMET advisories',
      'Precipitation radar',
    ]) {
      const toggle = config.getByRole('switch', { name, exact: true });
      await expect(toggle).toBeEnabled();
      if (!(await toggle.isChecked())) await toggle.click();
      await expect(toggle).toBeChecked();
    }
    await ready(overview, 'pressure', 6);
    await ready(other, 'pressure', 6);
    expect((await remember()).barbs).toBeLessThanOrEqual(2000);
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
      const current = await remember();
      expect(current.valid).toBe(
        Date.parse('2026-10-06T00:00:00Z') + lead * 3600000
      );
      if (kind === 'pressure-850')
        await config
          .getByRole('combobox', { name: 'Atmosphere level' })
          .selectOption('pressure:85000');
      if (kind === 'flight-level') {
        expect(current.vertical.source_pressures_pa).toEqual([15000, 20000]);
        expect(current.vertical.derivation).toBe('isa-log-pressure-v1');
      }
      const reference = oracles.filter(
          (o) => o.lead === lead && o.vertical === kind
        ),
        native = await samples(overview, reference);
      native.forEach((actual, i) => {
        const node = actual.node as Record<string, number>;
        expect(node.mask).toBe(reference[i].mask);
        if (!node.mask)
          for (const n of ['u', 'v', 't'])
            expect(
              Math.abs(node[n] - reference[i].source_values[n])
            ).toBeLessThanOrEqual(0.01);
        for (const n of ['u', 'v', 't']) {
          const component = actual[n] as {
            error: number;
            gpuMask: number;
            mask: number;
          };
          expect(component.gpuMask).toBe(component.mask);
          if (!component.mask)
            expect(component.error).toBeLessThanOrEqual(0.01);
        }
      });
      readbacks.push({ kind, lead, native, reference });
      // Independent tangent check against the first real glyph's actual shaft.
      const s = current.firstSample as number[],
        line = current.firstShaft as number[],
        lat = (s[2] * Math.PI) / 180,
        lon = (s[3] * Math.PI) / 180;
      const shaft = [line[3] - line[0], line[4] - line[1], line[5] - line[2]],
        length = Math.hypot(...shaft),
        speed = Math.hypot(s[4], s[5]);
      const east = [-Math.sin(lon), 0, -Math.cos(lon)],
        north = [
          -Math.sin(lat) * Math.cos(lon),
          Math.cos(lat),
          Math.sin(lat) * Math.sin(lon),
        ];
      if (speed > 2.5 / 1.9438444924406) {
        expect(
          shaft.reduce((v, x, i) => v + x * east[i], 0) / length
        ).toBeCloseTo(-s[4] / speed, 4);
        expect(
          shaft.reduce((v, x, i) => v + x * north[i], 0) / length
        ).toBeCloseTo(-s[5] / speed, 4);
      }
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
    evidence.native_samples = true;
    evidence.configuration = true;
    await overview.screenshot({ path: info.outputPath('gfs-desktop.png') });
    await overview
      .getByRole('button', { name: 'Inspect weather reports' })
      .click();
    await expect(overview.getByRole('dialog')).toBeVisible();
    await overview.screenshot({
      path: info.outputPath('gfs-report-chooser.png'),
    });
    const report = overview.getByLabel('Weather report', { exact: true });
    if (await report.count()) {
      await report.first().click();
      await expect(overview.getByRole('dialog')).toContainText('TEST');
    }
    await overview
      .getByRole('button', { name: 'Close weather report' })
      .click();
    await overview
      .locator('.overview-globe')
      .evaluate((element) => element.requestFullscreen());
    await overview.screenshot({ path: info.outputPath('gfs-fullscreen.png') });
    await overview.evaluate(() => document.exitFullscreen());
    await overview.setViewportSize({ width: 390, height: 844 });
    await ready(overview, 'flight-level', 9);
    await overview.screenshot({ path: info.outputPath('gfs-mobile.png') });
    await expect(overview.getByLabel('Globe legend')).toBeVisible();
    await overview
      .getByRole('button', { name: 'Inspect weather reports' })
      .click();
    await expect(overview.getByRole('dialog')).toBeVisible();
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
    let release!: () => void,
      entered = false;
    await overview.route(
      '**/api/aviation-weather/v1/products/*/grid.json',
      async (route) => {
        entered = true;
        const response = await route.fetch();
        await new Promise<void>((resolve) => {
          release = resolve;
        });
        await route.fulfill({ response }).catch(() => {});
      }
    );
    await config
      .getByRole('combobox', { name: 'Atmosphere level' })
      .selectOption('pressure:50000');
    await expect.poll(() => entered, { timeout: 90000 }).toBe(true);
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    await config
      .getByRole('switch', { name: 'GFS air temperature', exact: true })
      .click();
    release();
    await overview.unroute('**/api/aviation-weather/v1/products/*/grid.json');
    await expect
      .poll(async () => (await snapshot(overview))?.present)
      .toBe(false);
    expect((await request.get('/api/status')).ok()).toBe(true);
    await patchControl({ gfs_mismatch: true });
    await config
      .getByRole('switch', { name: 'GFS winds', exact: true })
      .click();
    await config
      .getByRole('switch', { name: 'GFS air temperature', exact: true })
      .click();
    await expect(
      overview.getByLabel('Flight-level atmosphere status')
    ).toContainText('Unavailable', { timeout: 90000 });
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
    await overview.reload();
    await expect(
      overview.getByLabel('Flight-level atmosphere status')
    ).toContainText('Stale', { timeout: 90000 });
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
