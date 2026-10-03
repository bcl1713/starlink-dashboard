import { expect, test, type Page } from '@playwright/test';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';
import {
  installOverviewSceneProbe,
  sceneSnapshot,
} from './support/overview-scene-probe';
import { trafficPathFixture } from './support/traffic-path-fixture';
import {
  assertOppositeTrafficMotion,
  exerciseTrafficResources,
  sampleTrafficRendering,
} from './support/traffic-path-rendering';

// API interception is deterministic development coverage, never persistence evidence.
test.use({ viewport: { width: 1920, height: 1080 } });
async function openGlobe(page: Page) {
  const texture = page.waitForResponse(
    (response) => response.url().endsWith('/earth-day-hi.jpg') && response.ok()
  );
  await page.goto('/overview');
  await waitForGlobeVisualReady(
    page,
    texture,
    page.viewportSize()!.width < 1000 &&
      page.viewportSize()!.width > page.viewportSize()!.height
      ? { x: 0.4, y: 0.65 }
      : { x: 0.5, y: 0.5 }
  );
  await expect.poll(() => sceneSnapshot(page)).not.toBeNull();
}
async function links(page: Page, traffic: boolean, xBand: boolean) {
  const legend = page.getByLabel('Globe legend');
  await expect(legend.getByText('Traffic path', { exact: true })).toHaveCount(
    traffic ? 1 : 0,
    { timeout: 10000 }
  );
  await expect(
    legend.getByText('Planned satellite link', { exact: true })
  ).toHaveCount(xBand ? 1 : 0);
  await expect(legend.getByText('Aircraft', { exact: true })).toHaveCount(1);
  await expect(legend.getByText('Planned route', { exact: true })).toHaveCount(
    1
  );
  await expect(legend.getByText('Track history', { exact: true })).toHaveCount(
    1
  );
}
async function particleSizes(page: Page) {
  return (
    (await sceneSnapshot(page))?.particles.flatMap((branch) => branch.sizes) ??
    []
  );
}

test('keeps both particle streams alive across moving-aircraft status polls', async ({
  page,
}) => {
  await installOverviewSceneProbe(page);
  const fixture = await trafficPathFixture(page);
  await openGlobe(page);
  await expect
    .poll(
      async () =>
        (await sceneSnapshot(page))!.particles.filter((branch) =>
          branch.sizes.some((size) => size < 10)
        ).length
    )
    .toBe(2);
  const initial = (await sceneSnapshot(page))!.particles.filter((branch) =>
    branch.sizes.some((size) => size < 10)
  );

  for (let tick = 0; tick < 3; tick += 1) {
    const response = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/status'
    );
    fixture.status.position!.latitude! += 0.01;
    fixture.status.position!.longitude! += 0.01;
    await response;
    // Observe through the following poll so the first response has rendered.
    await page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/status'
    );
    await expect
      .poll(
        async () => {
          const current = (await sceneSnapshot(page))!.particles;
          return initial.every((previous) => {
            const branch = current.find(
              (branch) => branch.geometry === previous.geometry
            );
            return (
              branch &&
              branch.count > 0 &&
              JSON.stringify(branch.positions) !==
                JSON.stringify(previous.positions)
            );
          });
        },
        { timeout: 15000 }
      )
      .toBe(true);
  }
});

for (const [traffic, xBand] of [
  [false, false],
  [true, false],
  [false, true],
  [true, true],
]) {
  test(`saves independent switches ${traffic}/${xBand}, navigates immediately and reloads`, async ({
    page,
  }, info) => {
    await installOverviewSceneProbe(page);
    const fixture = await trafficPathFixture(page);
    await page.goto('/configuration');
    for (const [label, enabled] of [
      ['Starshield data link', traffic],
      ['X-band data link', xBand],
    ] as const) {
      const control = page.getByRole('switch', { name: label });
      await expect(control).toBeEnabled();
      if ((await control.isChecked()) !== enabled) await control.click();
      await expect(control).toBeEnabled();
      await expect(control).toBeChecked({ checked: enabled });
    }
    await page.getByRole('link', { name: 'Overview', exact: true }).click();
    await links(page, traffic, xBand);
    await openGlobe(page);
    await links(page, traffic, xBand);
    await expect
      .poll(async () =>
        (await particleSizes(page)).some((size) => Math.abs(size - 9.5) < 0.01)
      )
      .toBe(traffic);
    await expect
      .poll(async () =>
        (await particleSizes(page)).some((size) => Math.abs(size - 4.8) < 0.01)
      )
      .toBe(xBand);
    const snapshot = await sceneSnapshot(page);
    expect(snapshot!.particles.every((branch) => branch.count <= 200)).toBe(
      true
    );
    if (traffic) {
      const measured = snapshot!.particles.find((branch) =>
        branch.sizes.some((size) => Math.abs(size - 9.5) < 0.01)
      );
      // Amber upload and cyan download reach the actual GPU geometry.
      await expect
        .poll(async () => {
          const current = (await sceneSnapshot(page))!.particles.find(
            (branch) => branch.geometry === measured!.geometry
          );
          return [
            current?.colors.some(([r, g, b]) => r > g && g > b),
            current?.colors.some(([r, g, b]) => b > g && g > r),
          ];
        })
        .toEqual([true, true]);
    }
    if (traffic) await assertOppositeTrafficMotion(page, 9.5);
    if (xBand) await assertOppositeTrafficMotion(page, 4.8);
    await page.screenshot({
      path: info.outputPath(`links-${traffic}-${xBand}.png`),
    });
    const failedRead = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/api/overview-links/settings' &&
        response.request().method() === 'GET' &&
        response.status() === 503
    );
    fixture.getError = true;
    await page.evaluate(() =>
      window.dispatchEvent(new Event('visibilitychange'))
    );
    await failedRead;
    await links(page, traffic, xBand);
    await page
      .getByRole('link', { name: 'Configuration', exact: true })
      .click();
    for (const [name, checked] of [
      ['Starshield data link', traffic],
      ['X-band data link', xBand],
    ] as const)
      await expect(page.getByRole('switch', { name })).toBeChecked({ checked });
  });
}

test('hides unconfirmed settings during delayed/failed GET and recovers without reload', async ({
  page,
}) => {
  const fixture = await trafficPathFixture(page);
  fixture.delayGet = true;
  await page.goto('/overview');
  await links(page, false, false);
  await expect.poll(() => fixture.getStarted).toBe(true);
  fixture.delayGet = false;
  fixture.releaseGet();
  await links(page, true, true);
  fixture.getError = true;
  await page.reload();
  await links(page, false, false);
  fixture.getError = false;
  await links(page, true, true);
});

test('keeps last confirmed switches on failed save and refresh error', async ({
  page,
}) => {
  const fixture = await trafficPathFixture(page);
  await page.goto('/configuration');
  const control = page.getByRole('switch', { name: 'Starshield data link' });
  await expect(control).toBeChecked();
  fixture.saveError = true;
  await control.click();
  await expect(
    page.getByText('Unable to save data link settings. Please try again.')
  ).toBeVisible();
  await expect(control).toBeChecked();
  fixture.getError = true;
  await expect(
    page.getByText('Data link settings unavailable', { exact: true })
  ).toBeVisible({ timeout: 10000 });
  await expect(control).toBeChecked();
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await links(page, true, true);
});

test('separates missing directions/modulation, warning, expiration, PoP and selection failure', async ({
  page,
}, info) => {
  await installOverviewSceneProbe(page);
  const fixture = await trafficPathFixture(page);
  await openGlobe(page);
  await links(page, true, true);
  fixture.status.metric_availability!.throughput_up_mbps = false;
  fixture.status.metric_availability!.latency_ms = false;
  fixture.status.metric_availability!.packet_loss_percent = false;
  await expect
    .poll(
      async () => {
        const measured = (await sceneSnapshot(page))!.particles.find((branch) =>
          branch.sizes.some((size) => Math.abs(size - 9.5) < 0.01)
        );
        return measured && measured.colors.every(([r, g, b]) => b > g && g > r);
      },
      { timeout: 10000 }
    )
    .toBe(true);
  fixture.selection = 'warning';
  await expect(page.getByLabel('Map status')).toContainText(
    'Planned link warning'
  );
  await expect
    .poll(async () => (await particleSizes(page)).some((size) => size < 5))
    .toBe(false);
  await links(page, true, true);
  await page.screenshot({
    path: info.outputPath('warning-measured-download.png'),
  });
  fixture.selection = 'normal';
  await expect
    .poll(async () => (await particleSizes(page)).some((size) => size < 5), {
      timeout: 10000,
    })
    .toBe(true);
  fixture.expired = true;
  await links(page, false, true);
  await expect
    .poll(async () =>
      (await sceneSnapshot(page))!.particles.filter((branch) =>
        branch.sizes.some((size) => size < 10)
      )
    )
    .toHaveLength(0);
  fixture.expired = false;
  fixture.status.ground_entry_point = null;
  await links(page, false, true);
  await expect
    .poll(async () => (await particleSizes(page)).some((size) => size < 5))
    .toBe(true);
  fixture.selectionError = true;
  await expect(
    page.getByRole('region', { name: 'Planned satellite' })
  ).toContainText('UNAVAILABLE', { timeout: 15000 });
  await expect
    .poll(async () => (await particleSizes(page)).some((size) => size < 5))
    .toBe(false);
  await links(page, false, true);
});

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
  { width: 844, height: 390 },
]) {
  test(`paints both links with fullscreen/reduced-motion recovery at ${viewport.width}x${viewport.height}`, async ({
    page,
  }, info) => {
    await page.setViewportSize(viewport);
    await installOverviewSceneProbe(page);
    await trafficPathFixture(page);
    await openGlobe(page);
    await links(page, true, true);
    await expect
      .poll(async () => (await particleSizes(page)).some((size) => size < 5), {
        timeout: 15000,
      })
      .toBe(true);
    if (viewport.width === 1920)
      await page
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
    await page.screenshot({ path: info.outputPath('both-on.png') });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect
      .poll(async () => (await sceneSnapshot(page))!.particles)
      .toHaveLength(0);
    await links(page, true, true);
    await page.screenshot({
      path: info.outputPath('reduced-motion-lines.png'),
    });
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await expect
      .poll(async () => (await particleSizes(page)).some((size) => size < 5), {
        timeout: 15000,
      })
      .toBe(true);
  });
}

test('stops activity on the first failed status attempt and recovers during retries', async ({
  page,
}) => {
  await installOverviewSceneProbe(page);
  const fixture = await trafficPathFixture(page);
  await openGlobe(page);
  await expect
    .poll(async () => (await particleSizes(page)).some((size) => size < 5), {
      timeout: 15000,
    })
    .toBe(true);
  const firstFailure = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/api/status' &&
      response.status() === 503
  );
  fixture.statusError = true;
  await firstFailure;
  // The first retry is delayed by a second; this must clear before retries finish.
  await expect(
    page.getByLabel('Globe legend').getByText('Traffic path', { exact: true })
  ).toHaveCount(0, { timeout: 750 });
  await expect
    .poll(
      async () =>
        (await sceneSnapshot(page))!.particles.filter((branch) =>
          branch.sizes.some((size) => size < 10)
        ),
      { timeout: 750 }
    )
    .toHaveLength(0);
  fixture.statusError = false;
  await links(page, true, true);
  await expect
    .poll(async () => (await particleSizes(page)).some((size) => size < 5), {
      timeout: 15000,
    })
    .toBe(true);
});

test('bounds resources through 20 toggle cycles and 10 mounts', async ({
  page,
}, info) => {
  test.setTimeout(180000);
  await installOverviewSceneProbe(page);
  const fixture = await trafficPathFixture(page);
  await openGlobe(page);
  await exerciseTrafficResources(page, fixture, info);
});

test('records 60-second rendering distributions for both-off, Starshield-only and both-on', async ({
  page,
}, info) => {
  test.setTimeout(240000);
  await installOverviewSceneProbe(page);
  const fixture = await trafficPathFixture(page);
  await openGlobe(page);
  await sampleTrafficRendering(page, fixture, info);
});
