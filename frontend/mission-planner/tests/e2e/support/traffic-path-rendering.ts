import { writeFile } from 'node:fs/promises';
import { expect, type Page, type TestInfo } from '@playwright/test';
import { sceneSnapshot } from './overview-scene-probe';
import type { trafficPathFixture } from './traffic-path-fixture';

type Fixture = Awaited<ReturnType<typeof trafficPathFixture>>;
async function updateLinks(
  page: Page,
  fixture: Fixture,
  traffic: boolean,
  xBand: boolean
) {
  fixture.settings = {
    ...fixture.settings,
    starshield_link_enabled: traffic,
    x_band_link_enabled: xBand,
  };
  // A visibility/focus event exercises the shared settings read, just as another
  // viewer's update does; this is an intercepted case, not a persisted save.
  await page.evaluate(() =>
    window.dispatchEvent(new Event('visibilitychange'))
  );
  await expect(
    page.getByLabel('Globe legend').getByText('Traffic path', { exact: true })
  ).toHaveCount(traffic ? 1 : 0, { timeout: 10000 });
  await expect(
    page
      .getByLabel('Globe legend')
      .getByText('Planned satellite link', { exact: true })
  ).toHaveCount(xBand ? 1 : 0, { timeout: 10000 });
  await expect
    .poll(
      async () =>
        (await sceneSnapshot(page))!.particles.filter((branch) =>
          branch.sizes.some((size) => size < 10)
        ).length,
      { timeout: 15000 }
    )
    .toBe(Number(traffic) + Number(xBand));
}
export async function exerciseTrafficResources(
  page: Page,
  fixture: Fixture,
  info: TestInfo
) {
  const off: number[] = [],
    on: number[] = [],
    mounts: number[] = [];
  for (let cycle = 0; cycle < 20; cycle++) {
    await updateLinks(page, fixture, false, false);
    off.push((await sceneSnapshot(page))!.geometries);
    await updateLinks(page, fixture, true, true);
    on.push((await sceneSnapshot(page))!.geometries);
  }
  // Same mounted scene: every disabled state returns to the same GPU baseline.
  expect(new Set(off).size).toBe(1);
  expect(new Set(on).size).toBe(1);
  expect(on[0]).toBeGreaterThan(off[0]);
  for (let mount = 0; mount < 10; mount++) {
    await page
      .getByRole('link', { name: 'Configuration', exact: true })
      .click();
    await page.getByRole('link', { name: 'Overview', exact: true }).click();
    await expect.poll(() => sceneSnapshot(page)).not.toBeNull();
    await expect
      .poll(
        async () =>
          (await sceneSnapshot(page))!.particles.filter((branch) =>
            branch.sizes.some((size) => size < 10)
          ).length,
        { timeout: 15000 }
      )
      .toBe(2);
    mounts.push((await sceneSnapshot(page))!.geometries);
  }
  expect(new Set(mounts).size).toBe(1);
  await expect
    .poll(
      async () =>
        (await sceneSnapshot(page))!.retiredGeometries.every(
          (count) => count === 0
        ),
      { timeout: 10000 }
    )
    .toBe(true);
  const retiredGeometries = (await sceneSnapshot(page))!.retiredGeometries;
  expect(retiredGeometries).toHaveLength(10);
  // Desktop camera controls are already enabled.
  const canvas = page.locator('.overview-globe canvas');
  await canvas.dragTo(canvas, {
    sourcePosition: { x: 500, y: 300 },
    targetPosition: { x: 600, y: 350 },
  });
  await page
    .getByRole('button', { name: 'Reset map view', exact: true })
    .click();
  await expect(
    page.getByLabel('Globe legend').getByText('Track history', { exact: true })
  ).toHaveCount(1);
  await expect(
    page.getByLabel('Globe legend').getByText('Planned route', { exact: true })
  ).toHaveCount(1);
  // Deterministic browser event coverage; native OS/tab suspension is a separate
  // hardware check, not inferred from this injected visibility transition.
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      value: true,
    });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect
    .poll(async () => (await sceneSnapshot(page))!.particles)
    .toHaveLength(0);
  await page.evaluate(() => {
    Reflect.deleteProperty(document, 'hidden');
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect
    .poll(
      async () =>
        (await sceneSnapshot(page))!.particles.filter((branch) =>
          branch.sizes.some((size) => size < 10)
        ).length,
      { timeout: 15000 }
    )
    .toBe(2);
  const resourcePath = info.outputPath('resource-plateau.json');
  await writeFile(
    resourcePath,
    JSON.stringify({
      evidenceKind: 'intercepted-development',
      cycles: 20,
      mounts: 10,
      off,
      on,
      mountedGeometries: mounts,
      retiredGeometries,
      hiddenRecovery: 'injected-visibility-event',
    })
  );
  await info.attach('resource-plateau.json', {
    contentType: 'application/json',
    path: resourcePath,
  });
}
export async function sampleTrafficRendering(
  page: Page,
  fixture: Fixture,
  info: TestInfo
) {
  const samples = [];
  for (const [name, traffic, xBand] of [
    ['both-off', false, false],
    ['Starshield-only', true, false],
    ['both-on', true, true],
  ] as const) {
    await updateLinks(page, fixture, traffic, xBand);
    const result = await page.evaluate(async () => {
      const probe = (
        window as unknown as {
          __overviewScene: (statsOnly: boolean) => {
            calls: number;
            geometries: number;
            pixelRatio: number;
          };
        }
      ).__overviewScene;
      const frames: number[] = [],
        calls: number[] = [],
        geometries: number[] = [];
      const start = performance.now();
      let previous = start;
      await new Promise<void>((resolve) => {
        const tick = (now: number) => {
          frames.push(now - previous);
          previous = now;
          const snapshot = probe(true);
          calls.push(snapshot.calls);
          geometries.push(snapshot.geometries);
          if (now - start >= 60000) resolve();
          else requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      const distribution = (values: number[]) => {
        const sorted = [...values].sort((a, b) => a - b);
        const percentile = (p: number) =>
          sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))];
        return {
          count: sorted.length,
          min: sorted[0],
          p50: percentile(0.5),
          p95: percentile(0.95),
          p99: percentile(0.99),
          max: sorted.at(-1),
        };
      };
      const gl = document
        .querySelector<HTMLCanvasElement>('.overview-globe canvas')!
        .getContext('webgl2')!;
      const debug = gl.getExtension('WEBGL_debug_renderer_info');
      return {
        durationMs: performance.now() - start,
        framesMs: distribution(frames),
        drawCalls: distribution(calls),
        gpuGeometries: distribution(geometries),
        pixelRatio: probe(true).pixelRatio,
        renderer: gl.getParameter(
          debug?.UNMASKED_RENDERER_WEBGL ?? gl.RENDERER
        ),
        vendor: gl.getParameter(debug?.UNMASKED_VENDOR_WEBGL ?? gl.VENDOR),
        version: gl.getParameter(gl.VERSION),
      };
    });
    expect(result.durationMs).toBeGreaterThanOrEqual(60000);
    expect(result.framesMs.count).toBeGreaterThan(1);
    expect(result.pixelRatio).toBeLessThanOrEqual(2);
    samples.push({ name, ...result });
  }
  const renderingPath = info.outputPath('rendering-60s.json');
  await writeFile(
    renderingPath,
    JSON.stringify({
      evidenceKind: 'intercepted-development',
      viewport: { width: 1920, height: 1080 },
      samples,
      deltasFromBothOff: samples.slice(1).map((sample) => ({
        name: sample.name,
        p50Ms: sample.framesMs.p50 - samples[0].framesMs.p50,
        p95Ms: sample.framesMs.p95 - samples[0].framesMs.p95,
        drawCalls: sample.drawCalls.p50 - samples[0].drawCalls.p50,
        gpuGeometries: sample.gpuGeometries.p50 - samples[0].gpuGeometries.p50,
      })),
      hardwareGap:
        'Unknown deployment laptop; software renderer cannot establish its performance.',
    })
  );
  await info.attach('rendering-60s.json', {
    contentType: 'application/json',
    path: renderingPath,
  });
}

export async function assertOppositeTrafficMotion(page: Page, size: number) {
  await expect
    .poll(
      async () => {
        const first = (await sceneSnapshot(page))!.particles.find((branch) =>
          branch.sizes.some((value) => Math.abs(value - size) < 0.01)
        );
        if (!first) return false;
        await page.evaluate(
          () =>
            new Promise<void>((resolve) =>
              requestAnimationFrame(() =>
                requestAnimationFrame(() => resolve())
              )
            )
        );
        const second = (await sceneSnapshot(page))!.particles.find(
          (branch) => branch.geometry === first.geometry
        );
        if (!second || second.count < first.count) return false;
        const position = (branch: typeof first, upload: boolean) => {
          const index = branch.colors.findIndex(([r, g, b]) =>
            upload ? r > g && g > b : b > g && g > r
          );
          return branch.positions[index];
        };
        const a = position(first, true),
          b = position(first, false);
        const c = position(second, true),
          d = position(second, false);
        if (!a || !b || !c || !d) return false;
        // Independent visual oracle: opposite color-coded particles in a small arc
        // have opposing displacement vectors over adjacent painted frames.
        return (
          c.reduce(
            (dot, value, index) =>
              dot + (value - a[index]) * (d[index] - b[index]),
            0
          ) < 0
        );
      },
      { timeout: 10000 }
    )
    .toBe(true);
}
