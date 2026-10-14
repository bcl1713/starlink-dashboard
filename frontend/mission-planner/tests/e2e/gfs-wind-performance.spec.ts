import { test, expect } from '@playwright/test';
import { writeFile, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import {
  installWeatherProbe,
  weatherSnapshot,
} from './support/overview-weather-probe';
import { windSnapshot } from './support/gfs-wind-probe';
import type { RootState } from '@react-three/fiber';

test('H1 paired real hardware runs; every pair satisfies both gates', async ({
  browser,
}, info) => {
  const source = await readFile(process.env.GFS_HARDWARE_SOURCE_MANIFEST!);
  const manifest = JSON.parse(source.toString());
  const pinned = JSON.parse(
    await readFile(
      new URL(
        '../../../../tools/acceptance/gfs-weather/presentation-source.json',
        import.meta.url
      ),
      'utf8'
    )
  );
  const hash = (body: Uint8Array) =>
    createHash('sha256').update(body).digest('hex');
  for (const [name, digest] of Object.entries(pinned)) {
    const body = await readFile(`${manifest.source_root}/presentation/${name}`);
    expect(hash(body), name).toBe(digest);
  }
  expect(manifest.clock_utc_ms).toBe(Date.parse('2026-10-06T06:00:00Z'));
  for (const n of ['u', 'v', 't', 'mask'])
    expect(manifest.normalized_buffers[n]).toMatch(/^[a-f0-9]{64}$/);
  for (const kind of ['BASELINE', 'CANDIDATE']) {
    const target = manifest.targets[kind];
    expect(target.sha).toBe(process.env[`GFS_HARDWARE_${kind}_SHA`]);
    expect(target.origin).toBe(
      new URL(process.env[`GFS_HARDWARE_${kind}_URL`]!).origin
    );
    expect(Object.keys(target.assets)).toContain('/index.html');
    expect(
      Object.keys(target.assets).some((path) =>
        /^\/assets\/[^/]+\.js$/.test(path)
      )
    ).toBe(true);
  }
  const runs: unknown[] = [];
  const p95 = (values: number[]) => {
    expect(values.length).toBeGreaterThan(0);
    expect(values.every(Number.isFinite)).toBe(true);
    return [...values].sort((a, b) => a - b)[
      Math.ceil(values.length * 0.95) - 1
    ];
  };
  for (const overlays of [false, true])
    for (let pair = 0; pair < 3; pair++) {
      const metrics: Record<string, { frame: number; update: number }> = {};
      for (const kind of pair % 2
        ? ['CANDIDATE', 'BASELINE']
        : ['BASELINE', 'CANDIDATE']) {
        const context = await browser.newContext({
          viewport: { width: 1920, height: 1080 },
          deviceScaleFactor: 1,
        });
        const page = await context.newPage();
        try {
          const origin = new URL(process.env[`GFS_HARDWARE_${kind}_URL`]!)
            .origin;
          const target = manifest.targets[kind];
          for (const [path, digest] of Object.entries(target.assets)) {
            expect(path).toMatch(/^\/(?:index\.html|assets\/[A-Za-z0-9._-]+)$/);
            const response = await page.request.get(origin + path);
            expect(response.ok()).toBe(true);
            expect(hash(await response.body()), path).toBe(digest);
          }
          const index = await (
            await page.request.get(origin + '/index.html')
          ).text();
          for (const [, path] of index.matchAll(
            /(?:src|href)="(\/assets\/[^"]+)"/g
          ))
            expect(target.assets).toHaveProperty(path);
          await page.goto(origin + '/configuration');
          await page.getByRole('tab', { name: 'Weather', exact: true }).click();
          // Legacy baseline can combine modes; explicitly disable temperature.
          for (const [name, on] of [
            ['GFS air temperature', false],
            ['GFS winds', true],
            ['Precipitation radar', overlays],
            ['METAR / SPECI observations', overlays],
            ['TAF terminal forecasts', overlays],
            ['International SIGMET advisories', overlays],
          ] as const) {
            const toggle = page.getByRole('switch', { name, exact: true });
            if ((await toggle.isChecked()) !== on) await toggle.click();
          }
          await page
            .getByRole('combobox', { name: 'Atmosphere level' })
            .selectOption('pressure:50000');
          await page
            .getByRole('combobox', { name: 'Forecast horizon' })
            .selectOption('0');
          await installWeatherProbe(page);
          await page.goto(origin + '/overview');
          await expect
            .poll(async () => (await windSnapshot(page))?.present, {
              timeout: 180000,
            })
            .toBe(true);
          if (kind === 'CANDIDATE')
            expect((await windSnapshot(page))?.particleCount).toBe(2000);
          const admitted = await windSnapshot(page);
          expect(admitted?.lead).toBe(21600);
          expect(admitted?.vertical).toEqual({
            kind: 'pressure',
            pressure_pa: 50000,
          });
          expect(admitted?.valid).toBe(manifest.clock_utc_ms);
          expect(admitted?.bulletins).toEqual([overlays, overlays, overlays]);
          expect(!!(await weatherSnapshot(page)).radar).toBe(overlays);
          const catalog = await (
            await page.request.get(origin + '/api/aviation-weather/v1/catalog')
          ).json();
          expect(
            Math.abs(catalog.generated_at_ms - manifest.clock_utc_ms)
          ).toBeLessThanOrEqual(10000);
          if (overlays) {
            const signatures = catalog.products
              .filter(
                (p: { layer_id: string }) => !p.layer_id.startsWith('gfs-')
              )
              .map(
                (p: {
                  layer_id: string;
                  instance_id: string | null;
                  payload: { sha256: string } | null;
                  radar: { product_id: string } | null;
                }) => ({
                  layer: p.layer_id,
                  instance: p.instance_id,
                  payload: p.payload?.sha256 ?? p.radar?.product_id ?? null,
                })
              );
            expect(signatures).toEqual(manifest.overlay_products);
          }
          const product = catalog.products.find(
            (p: { layer_id: string }) => p.layer_id === 'gfs-winds'
          );
          const descriptor = await (
            await page.request.get(origin + product.payload.path)
          ).json();
          for (const n of ['u', 'v', 't', 'mask']) {
            expect(descriptor.buffers[n].sha256).toBe(
              manifest.normalized_buffers[n]
            );
            const response = await page.request.get(
              origin + descriptor.buffers[n].path
            );
            expect(response.ok()).toBe(true);
            expect(hash(await response.body())).toBe(
              manifest.normalized_buffers[n]
            );
          }
          if (kind === 'BASELINE')
            expect(
              await page.evaluate(() => {
                const roots = (
                  window as unknown as {
                    __overviewEvidenceRoots: {
                      containerInfo?: { getState?: () => RootState };
                    }[];
                  }
                ).__overviewEvidenceRoots;
                return !!roots
                  .find(
                    (r) =>
                      r.containerInfo?.getState?.().gl.domElement.isConnected
                  )
                  ?.containerInfo?.getState?.()
                  .scene.getObjectByName('GFS wind FROM barbs');
              })
            ).toBe(true);
          const measured = await page.evaluate(async (candidate) => {
            type Fiber = {
              memoizedProps?: {
                view?: { drawing?: { update?: (delta: number) => void } };
              };
              child?: Fiber;
              sibling?: Fiber;
            };
            const roots = (
              window as unknown as {
                __overviewEvidenceRoots: {
                  containerInfo?: { getState?: () => RootState };
                  current?: Fiber;
                }[];
              }
            ).__overviewEvidenceRoots;
            const state = roots
              .find(
                (r) => r.containerInfo?.getState?.().gl.domElement.isConnected
              )
              ?.containerInfo?.getState?.();
            if (!state) throw Error('Missing native renderer');
            const gl = state.gl.getContext(),
              extension = gl.getExtension('WEBGL_debug_renderer_info');
            if (!extension)
              throw Error('Hardware renderer identity unavailable');
            const renderer = String(
              gl.getParameter(extension.UNMASKED_RENDERER_WEBGL)
            );
            if (/swiftshader|llvmpipe|software/i.test(renderer))
              throw Error('H1 requires hardware acceleration');
            const find = (f?: Fiber): Fiber | undefined =>
              !f
                ? undefined
                : f.memoizedProps?.view?.drawing?.update
                  ? f
                  : (find(f.child) ?? find(f.sibling));
            const drawing = roots.map((r) => find(r.current)).find(Boolean)
              ?.memoizedProps?.view?.drawing;
            if (candidate && !drawing?.update)
              throw Error('Native update not observed');
            const controls = state.controls as unknown as {
              setLookAt: (...v: (number | boolean)[]) => void;
              update: (d: number) => void;
            };
            controls.setLookAt(6, 0, 0, 0, 0, 0, false);
            controls.update(0);
            const owner = state.scene.getObjectByName('Native GFS atmosphere');
            const particles = state.scene.getObjectByName('GFS wind particles');
            const assertOwner = () => {
              if (
                state.scene.getObjectByName('Native GFS atmosphere') !==
                  owner ||
                !owner?.userData.gfs
              )
                throw Error('H1 owner changed during capture');
              if (
                candidate &&
                (state.scene.getObjectByName('GFS wind particles') !==
                  particles ||
                  particles?.userData.windParticles?.count !== 2000)
              )
                throw Error('H1 full-cap particle owner lost during capture');
            };
            const updates: number[] = [],
              frames: number[] = [],
              original = drawing?.update;
            let capture = false;
            if (drawing && original)
              drawing.update = (delta) => {
                const t = performance.now();
                original.call(drawing, delta);
                if (capture) updates.push(performance.now() - t);
              };
            try {
              await new Promise((resolve) => setTimeout(resolve, 15000));
              assertOwner();
              capture = true;
              await new Promise<void>((resolve, reject) => {
                const start = performance.now();
                let last = start;
                const frame = (now: number) => {
                  try {
                    assertOwner();
                  } catch (error) {
                    reject(error);
                    return;
                  }
                  frames.push(now - last);
                  last = now;
                  if (now - start >= 60000) resolve();
                  else requestAnimationFrame(frame);
                };
                requestAnimationFrame(frame);
              });
              if (candidate && updates.length < frames.length - 2)
                throw Error('H1 update/frame evidence incomplete');
              return {
                renderer,
                userAgent: navigator.userAgent,
                dpr: devicePixelRatio,
                frames,
                updates,
                calls: state.gl.info.render.calls,
              };
            } finally {
              if (drawing && original) drawing.update = original;
            }
          }, kind === 'CANDIDATE');
          const snapshot = await windSnapshot(page);
          const health = [];
          for (const path of ['/api/health', '/api/status']) {
            const start = performance.now();
            const response = await page.request.get(origin + path);
            expect(response.ok()).toBe(true);
            health.push({ path, ms: performance.now() - start });
          }
          metrics[kind] = {
            frame: p95(measured.frames),
            update: kind === 'CANDIDATE' ? p95(measured.updates) : 0,
          };
          runs.push({
            kind,
            pair,
            overlays,
            sha: process.env[`GFS_HARDWARE_${kind}_SHA`],
            origin,
            measured,
            snapshot,
            health,
          });
        } finally {
          await context.close();
        }
      }
      expect(metrics.CANDIDATE.update).toBeLessThanOrEqual(4);
      expect(metrics.CANDIDATE.frame).toBeLessThanOrEqual(
        metrics.BASELINE.frame * 1.2
      );
    }
  await writeFile(
    info.outputPath('hardware.json'),
    JSON.stringify(
      {
        target: process.env.GFS_HARDWARE_TARGET,
        sourceManifestSha256: createHash('sha256').update(source).digest('hex'),
        runs,
      },
      null,
      2
    )
  );
});
