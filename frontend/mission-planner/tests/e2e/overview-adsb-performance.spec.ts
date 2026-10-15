import { writeFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { adsbSettings } from '../../src/test/adsb-fixtures';
import {
  adsbScene,
  globalWorkload,
  installAdsbFixture,
  observeAdsbScene,
} from './support/adsb-fixture';
import { settledOverviewCamera } from './support/overview-camera';

test('2,000 contacts and 50 included identities retain all instances and release resources after camera workload', async ({
  context,
  browser,
}, info) => {
  test.setTimeout(180000);
  const fixture = await installAdsbFixture(context, true),
    page = await context.newPage();
  await page.setViewportSize({ width: 1920, height: 1080 });
  await observeAdsbScene(page);
  await page.goto('/overview');
  await expect(page.getByLabel('Globe legend')).toContainText('Aircraft');
  await settledOverviewCamera(page);
  await expect
    .poll(async () => (await adsbScene(page)).flightLayers.route)
    .toBeGreaterThan(0);
  await expect
    .poll(async () => (await adsbScene(page)).flightLayers.history)
    .toBeGreaterThan(0);
  const measure = () =>
    page.evaluate(async () => {
      const state = window.__overviewEvidenceRoots
        ?.find(
          (root) =>
            root.containerInfo?.getState &&
            document.contains(root.containerInfo.getState().gl.domElement)
        )
        ?.containerInfo?.getState?.();
      if (!state) throw new Error('Missing scene');
      const frames: number[] = [];
      const start = performance.now();
      let last = start,
        angle = 0;
      await new Promise<void>((resolve) => {
        const frame = (time: number) => {
          frames.push(time - last);
          last = time;
          const next = 0.15 * Math.sin((time - start) / 2000);
          state.controls?.rotate(next - angle, 0, false);
          angle = next;
          if (time - start < 30000) requestAnimationFrame(frame);
          else resolve();
        };
        requestAnimationFrame(frame);
      });
      state.controls?.rotate(-angle, 0, false);
      const sorted = frames.slice(1).sort((a, b) => a - b);
      return {
        frames: sorted.length,
        p50: sorted[Math.floor(sorted.length * 0.5)],
        p95: sorted[Math.floor(sorted.length * 0.95)],
        p99: sorted[Math.floor(sorted.length * 0.99)],
      };
    });
  const profiler = await context.newCDPSession(page);
  await profiler.send('Profiler.enable');
  await profiler.send('Profiler.start');
  const off = await measure(),
    baseline = await adsbScene(page);
  const offProfile = await profiler.send('Profiler.stop');
  await writeFile(
    info.outputPath('cpu-profile-off.json'),
    JSON.stringify(offProfile.profile)
  );
  const contacts = globalWorkload();
  fixture.setContacts([...contacts, contacts[0]]);
  fixture.setSettings(
    adsbSettings({
      include_hexes: contacts.slice(0, 50).map((c) => c.hex),
      revision: 1,
    })
  );
  await expect
    .poll(
      async () =>
        (await adsbScene(page)).batches.reduce((n, b) => n + b.count, 0),
      { timeout: 10000 }
    )
    .toBe(2000);
  await expect(page.locator('[data-adsb-label]')).toHaveCount(50);
  await profiler.send('Profiler.start');
  const on = await measure(),
    enabled = await adsbScene(page);
  const profile = await profiler.send('Profiler.stop');
  await writeFile(
    info.outputPath('cpu-profile.json'),
    JSON.stringify(profile.profile)
  );
  await profiler.detach();
  expect(enabled.batches.reduce((n, b) => n + b.count, 0)).toBe(2000);
  expect(enabled.labels).toBe(50);
  expect(enabled.flightLayers.route).toBeGreaterThan(0);
  expect(enabled.flightLayers.history).toBeGreaterThan(0);
  await page.screenshot({ path: info.outputPath('workload-50-labels.png') });
  const released = [];
  for (let cycle = 0; cycle < 3; cycle++) {
    fixture.setSettings(
      adsbSettings({ enabled: false, revision: 2 + cycle * 2 })
    );
    await expect
      .poll(async () => (await adsbScene(page)).batches.length, {
        timeout: 10000,
      })
      .toBe(0);
    await expect(page.locator('[data-adsb-label]')).toHaveCount(0);
    let state = await adsbScene(page);
    await expect
      .poll(async () => {
        state = await adsbScene(page);
        return state.geometries;
      })
      .toBe(baseline.geometries);
    expect(state.flightLayers.route).toBeGreaterThan(0);
    expect(state.flightLayers.history).toBeGreaterThan(0);
    released.push(state);
    if (cycle < 2) {
      fixture.setContacts(globalWorkload());
      fixture.setSettings(
        adsbSettings({
          revision: 3 + cycle * 2,
          include_hexes: contacts.slice(0, 50).map((c) => c.hex),
        })
      );
      await expect
        .poll(
          async () =>
            (await adsbScene(page)).batches.reduce((n, b) => n + b.count, 0),
          { timeout: 10000 }
        )
        .toBe(2000);
    }
  }
  await page.goto('/configuration');
  await page.getByRole('tab', { name: 'Aircraft Traffic', exact: true }).click();
  fixture.setSettings(
    adsbSettings({
      revision: 9,
      include_hexes: contacts.slice(0, 50).map((c) => c.hex),
    })
  );
  fixture.setContacts(globalWorkload());
  await expect(
    page
      .getByRole('region', { name: 'ADS-B aircraft settings' })
      .getByRole('row')
  ).toHaveCount(2001, { timeout: 10000 });
  await writeFile(
    info.outputPath('performance.json'),
    JSON.stringify(
      {
        browser: browser.version(),
        hardware: await page.evaluate(() => ({
          cores: navigator.hardwareConcurrency,
          userAgent: navigator.userAgent,
        })),
        off,
        on,
        baseline,
        enabled,
        released,
      },
      null,
      2
    )
  );
});
