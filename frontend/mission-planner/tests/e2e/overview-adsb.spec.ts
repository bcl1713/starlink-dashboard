import { expect, test } from '@playwright/test';
import { adsbSettings } from '../../src/test/adsb-fixtures';
import {
  adsbScene,
  freshContact,
  installAdsbFixture,
  observeAdsbScene,
} from './support/adsb-fixture';
import {
  expectSameCamera,
  settledOverviewCamera,
} from './support/overview-camera';

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
  { width: 844, height: 390 },
])
  test(`included identities, selection, focus and dialog fit ${viewport.width}x${viewport.height}`, async ({
    context,
  }, info) => {
    const fixture = await installAdsbFixture(context);
    const contacts = [
      freshContact({
        callsign:
          'VERY LONG COINCIDENT AIRCRAFT IDENTITY THAT MUST REMAIN VISIBLE',
      }),
      freshContact({
        hex: '000001',
        callsign: null,
        registration: 'REG-FALLBACK',
      }),
      freshContact({
        hex: '000002',
        callsign: null,
        registration: null,
        position_observed_at_ms: Date.now() - 40000,
      }),
      freshContact({ hex: '000003', latitude: -38, longitude: 90 }),
    ];
    fixture.setContacts(contacts);
    fixture.setSettings(
      adsbSettings({ include_hexes: contacts.slice(0, 3).map((c) => c.hex) })
    );
    const page = await context.newPage();
    await page.setViewportSize(viewport);
    await observeAdsbScene(page);
    await page.goto('/overview');
    await expect(page.locator('[data-adsb-label]')).toHaveCount(3);
    await expect(page.locator('[data-adsb-label="000002"]')).toContainText(
      '000002 · ◷ Stale'
    );
    await expect(page.locator('[data-adsb-label="000001"]')).toContainText(
      'REG-FALLBACK'
    );
    const identityBounds = await page
      .locator('[data-adsb-label="000001"]')
      .boundingBox();
    expect(identityBounds!.width).toBeGreaterThan(50);
    expect(identityBounds!.height).toBeLessThan(40);
    await expect(
      page.getByRole('button', { name: 'Details for 000003' })
    ).toHaveCount(0);
    const before = await settledOverviewCamera(page);
    const trigger = page.getByRole('button', { name: 'Details for 00AB12' });
    await trigger.focus();
    await trigger.press('Enter');
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    expect(
      await dialog.getByRole('heading').evaluate((heading) => {
        const bounds = heading.getBoundingClientRect();
        const hit = document.elementFromPoint(
          bounds.x + bounds.width / 2,
          bounds.y + bounds.height / 2
        );
        return heading.contains(hit);
      })
    ).toBe(true);
    await expect(dialog).toContainText('Track');
    await expect(dialog).toContainText('30000 ft (barometric)');
    await expect(dialog.getByRole('button', { name: 'Include' })).toHaveCount(
      0
    );
    expect(
      await dialog.evaluate((node) => node.contains(document.activeElement))
    ).toBe(true);
    await page.screenshot({ path: info.outputPath('before-containment.png') });
    const bounds = await dialog.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.y).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport.height);
    await page.screenshot({ path: info.outputPath('details.png') });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
    expectSameCamera(before, await settledOverviewCamera(page));
    if (viewport.width === 1920) {
      await page
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
      await expect
        .poll(() => page.evaluate(() => !!document.fullscreenElement))
        .toBe(true);
      await trigger.focus();
      await trigger.press('Enter');
      await expect(dialog).toBeVisible();
      expect(
        await dialog.evaluate(
          (node) => !!document.fullscreenElement?.contains(node)
        )
      ).toBe(true);
      await page.screenshot({
        path: info.outputPath('fullscreen-details.png'),
      });
      await dialog.getByRole('button', { name: 'Close', exact: true }).click();
      await expect(trigger).toBeFocused();
      await settledOverviewCamera(page);
      const point = (await adsbScene(page)).batches
        .flatMap((b) => b.points)
        .find((p) => p.hex === '000001')!;
      await page.mouse.click(point.x, point.y);
      await expect(dialog).toBeVisible();
      await dialog.getByRole('button', { name: 'Close', exact: true }).click();
      await page.mouse.move(point.x, point.y);
      await page.mouse.down();
      await page.mouse.move(point.x + 25, point.y + 25);
      await page.mouse.move(point.x, point.y);
      await page.mouse.up();
      await expect(dialog).toHaveCount(0);
    }
    await page.screenshot({ path: info.outputPath('labels.png') });
  });

test('original observation age survives failures, repeated replies and foreground resume; selected expiry closes details', async ({
  context,
}) => {
  const fixture = await installAdsbFixture(context),
    now = Date.now();
  fixture.setContacts([freshContact({ position_observed_at_ms: now })]);
  fixture.setSettings(adsbSettings({ include_hexes: ['00AB12'] }));
  const page = await context.newPage();
  await observeAdsbScene(page);
  await page.clock.setFixedTime(now + 29999);
  await page.goto('/overview');
  const label = page.locator('[data-adsb-label="00AB12"]');
  await expect(label).toBeVisible();
  await expect(label).not.toContainText('Stale');
  fixture.failTraffic(true);
  await page.clock.setFixedTime(now + 30000);
  await expect(label).toContainText('◷ Stale');
  const trigger = page.getByRole('button', { name: 'Details for 00AB12' });
  await trigger.focus();
  await trigger.press('Enter');
  await expect(page.getByRole('dialog')).toContainText('Stale');
  await page.clock.setFixedTime(now + 119999);
  await expect(label).toHaveCount(1);
  await page.clock.setFixedTime(now + 120000);
  await expect(label).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  fixture.failTraffic(false);
  await page.clock.setFixedTime(now + 130000);
  await page.evaluate(() =>
    document.dispatchEvent(new Event('visibilitychange'))
  );
  await expect(label).toHaveCount(0);
  await page.waitForResponse('**/api/overview-adsb/traffic');
  await expect(label).toHaveCount(0);
  const returning = page.waitForResponse(
    async (response) =>
      response.url().endsWith('/api/overview-adsb/traffic') &&
      response.status() === 200 &&
      (await response.json()).contacts.some(
        (contact: { position_observed_at_ms: number }) =>
          contact.position_observed_at_ms === now + 130000
      )
  );
  fixture.setContacts([
    freshContact({
      position_observed_at_ms: now + 130000,
      acquired_at_ms: now + 130000,
    }),
  ]);
  await returning;
  await expect(label).toBeVisible();
  await expect(label).not.toContainText('Stale');
  await page.goto('/configuration');
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue('00AB12');
});

test('shared chevrons stay compact at globe and flight zoom with white-blue own aircraft and amber traffic', async ({
  context,
}, info) => {
  const fixture = await installAdsbFixture(context, true);
  fixture.setContacts([
    freshContact({ latitude: 38, longitude: -95, track_degrees: 0 }),
    freshContact({
      hex: '000001',
      latitude: 37,
      longitude: -87,
      track_degrees: 90,
    }),
    freshContact({
      hex: '000002',
      latitude: 34,
      longitude: -90,
      track_degrees: 180,
      position_observed_at_ms: Date.now() - 40000,
    }),
  ]);
  fixture.setSettings(
    adsbSettings({ include_hexes: ['00AB12', '000001', '000002'] })
  );
  const page = await context.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  await observeAdsbScene(page);
  await page.goto('/overview');
  await expect(page.locator('[data-adsb-label]')).toHaveCount(3);
  await settledOverviewCamera(page);
  const measure = () =>
    page.evaluate(() => {
      const state = window.__overviewEvidenceRoots
        ?.find(
          (root) =>
            root.containerInfo?.getState &&
            document.contains(root.containerInfo.getState().gl.domElement)
        )
        ?.containerInfo?.getState?.();
      if (!state) throw new Error('No scene');
      const rect = state.gl.domElement.getBoundingClientRect();
      const heights: { own: boolean; pixels: number }[] = [];
      state.scene.traverse((node) => {
        const mesh = node as import('three').Mesh;
        const batch = node.userData.adsbBatch;
        if (!batch && node.userData.starMarkerShape !== 'chevron') return;
        // Derive the visible height from the rendered instance matrices; no production sizing helper.
        const a = state.camera.position.clone(),
          b = a.clone();
        const matrix = node.matrixWorld.clone();
        for (let i = 0; i < (batch ? batch.hexes.length : 1); i++) {
          if (batch) {
            (mesh as import('three').InstancedMesh).getMatrixAt(i, matrix);
            matrix.premultiply(node.matrixWorld);
          }
          a.set(0, 1, 0).applyMatrix4(matrix).project(state.camera);
          b.set(0, -1, 0).applyMatrix4(matrix).project(state.camera);
          heights.push({
            own: !batch,
            pixels: Math.hypot(
              ((a.x - b.x) * rect.width) / 2,
              ((a.y - b.y) * rect.height) / 2
            ),
          });
        }
      });
      return heights;
    });
  const check = async () => {
    const heights = await measure();
    expect(heights.filter((h) => h.own)).toHaveLength(1);
    expect(heights.filter((h) => !h.own)).toHaveLength(3);
    for (const h of heights) expect(h.pixels).toBeCloseTo(h.own ? 16 : 14, 2);
  };
  await check();
  await page.screenshot({ path: info.outputPath('chevrons-flight-view.png') });
  // Zoom out through the real camera controls; camera tracking remains part of the normal scene.
  const canvas = page.locator('.overview-globe canvas');
  const box = await canvas.boundingBox();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.wheel(0, 1000);
  await settledOverviewCamera(page);
  await check();
  await page.screenshot({ path: info.outputPath('chevrons-globe-view.png') });
});

test('telemetry heading, matching globe labels and visible chevron glow', async ({
  context,
}, info) => {
  const fixture = await installAdsbFixture(context, true);
  fixture.setAircraftHeading(270);
  fixture.setContacts([
    freshContact({ latitude: 38, longitude: -95, track_degrees: 90 }),
  ]);
  fixture.setSettings(adsbSettings({ include_hexes: ['00AB12'] }));
  const page = await context.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  await observeAdsbScene(page);
  await page.goto('/overview');
  await expect(page.locator('[data-adsb-label]')).toHaveCount(1);
  await settledOverviewCamera(page);
  const appearance = (selector: string) =>
    page
      .locator(selector)
      .first()
      .evaluate((node) => {
        const style = getComputedStyle(node);
        return {
          fontSize: style.fontSize,
          fontWeight: style.fontWeight,
          color: style.color,
          letterSpacing: style.letterSpacing,
          background: style.backgroundColor,
          border: style.borderWidth,
        };
      });
  expect
    .soft(await appearance('[data-adsb-label]'))
    .toEqual(await appearance('[data-poi-label]'));
  const evidence = await page.evaluate(() => {
    const state = window.__overviewEvidenceRoots
      ?.find(
        (root) =>
          root.containerInfo?.getState &&
          document.contains(root.containerInfo.getState().gl.domElement)
      )
      ?.containerInfo?.getState?.();
    if (!state) throw new Error('No scene');
    let own: import('three').Mesh | undefined,
      traffic: import('three').InstancedMesh | undefined;
    state.scene.traverse((node) => {
      if (node.userData.starMarkerShape === 'chevron')
        own = node as import('three').Mesh;
      if (node.userData.adsbBatch?.hexes.length)
        traffic = node as import('three').InstancedMesh;
    });
    if (!own || !traffic) throw new Error('Missing aircraft');
    const rect = state.gl.domElement.getBoundingClientRect();
    const center = state.camera.position
      .clone()
      .setFromMatrixPosition(own.matrixWorld);
    const west = center
      .clone()
      .set(
        Math.cos((35 * Math.PI) / 180) * Math.cos((-100.01 * Math.PI) / 180),
        Math.sin((35 * Math.PI) / 180),
        -Math.cos((35 * Math.PI) / 180) * Math.sin((-100.01 * Math.PI) / 180)
      )
      .multiplyScalar(center.length())
      .project(state.camera);
    const tip = center
      .clone()
      .set(0, 1, 0)
      .applyMatrix4(own.matrixWorld)
      .project(state.camera);
    center.project(state.camera);
    const tx = (tip.x - center.x) * rect.width,
      ty = (tip.y - center.y) * rect.height;
    const wx = (west.x - center.x) * rect.width,
      wy = (west.y - center.y) * rect.height;
    const alignment =
      (tx * wx + ty * wy) / (Math.hypot(tx, ty) * Math.hypot(wx, wy));
    const glowPixels = (
      marker: import('three').Mesh | import('three').InstancedMesh,
      blue: boolean
    ) => {
      // Isolate the real rendered marker from map textures, then inspect actual GPU pixels outside its solid body.
      const scene = state.scene.clone(false);
      const clone = marker.clone();
      scene.add(clone);
      const anchor = state.camera.position.clone();
      if ((marker as import('three').InstancedMesh).isInstancedMesh) {
        (clone as import('three').InstancedMesh).count = 1;
        const matrix = clone.matrixWorld.clone();
        (marker as import('three').InstancedMesh).getMatrixAt(0, matrix);
        anchor.setFromMatrixPosition(matrix);
      } else anchor.setFromMatrixPosition(marker.matrixWorld);
      anchor.project(state.camera);
      state.gl.render(scene, state.camera);
      const gl = state.gl.getContext(),
        ratio = state.gl.getPixelRatio();
      const cx = Math.round(((anchor.x + 1) * gl.drawingBufferWidth) / 2),
        cy = Math.round(((anchor.y + 1) * gl.drawingBufferHeight) / 2);
      const radius = Math.ceil(24 * ratio),
        side = radius * 2;
      const pixels = new Uint8Array(side * side * 4);
      gl.readPixels(
        cx - radius,
        cy - radius,
        side,
        side,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        pixels
      );
      let count = 0;
      for (let y = 0; y < side; y++)
        for (let x = 0; x < side; x++) {
          const distance = Math.hypot(x - radius, y - radius) / ratio;
          if (distance < 13 || distance > 22) continue;
          const i = (y * side + x) * 4,
            r = pixels[i],
            b = pixels[i + 2];
          if (blue ? b > r + 8 && b > 20 : r > b + 8 && r > 20) count++;
        }
      if ((clone as import('three').InstancedMesh).isInstancedMesh)
        (clone as import('three').InstancedMesh).dispose();
      return count;
    };
    const ownGlowPixels = glowPixels(own, true),
      trafficGlowPixels = glowPixels(traffic, false);
    state.gl.render(state.scene, state.camera);
    return { alignment, ownGlowPixels, trafficGlowPixels };
  });
  expect.soft(evidence.alignment).toBeGreaterThan(0.999);
  expect.soft(evidence.ownGlowPixels).toBeGreaterThan(8);
  expect.soft(evidence.trafficGlowPixels).toBeGreaterThan(8);
  await page.screenshot({ path: info.outputPath('heading-labels-glow.png') });
});
