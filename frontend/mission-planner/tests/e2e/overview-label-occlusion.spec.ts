import { expect, test, type Page } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { adsbSettings } from '../../src/test/adsb-fixtures';
import {
  adsbScene,
  freshContact,
  installAdsbFixture,
} from './support/adsb-fixture';
import {
  observeOverviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';

// Screenshot starting point, now deterministic: own aircraft, GEP, KADW and
// long/stale traffic identities share one position. Browser API interception
// is explicit; the production frontend and real Nginx/API controls are separate.
const origin = { latitude: 38.810795, longitude: -76.867386 };

async function monitorFrames(page: Page) {
  await page.evaluate(() => {
    const evidence = {
      frames: 0,
      visibleLabels: 0,
      violations: [] as unknown[],
      poses: new Set<string>(),
      aircraftPositions: new Set<string>(),
    };
    Object.assign(window, { __labelOcclusionEvidence: evidence });
    const sample = () => {
      const state = window.__overviewEvidenceRoots
        ?.find(
          (root) =>
            root.containerInfo?.getState &&
            document.contains(root.containerInfo.getState().gl.domElement)
        )
        ?.containerInfo?.getState?.();
      const own = state?.scene.getObjectByName('overview-own-aircraft');
      if (state && own?.visible) {
        const viewport = state.gl.domElement.getBoundingClientRect();
        const halo = own.children[0] as import('three').Mesh;
        const extent = (halo.material as import('three').ShaderMaterial)
          .uniforms.uExtent.value;
        // Independently inspect all four rendered shader-quad corners.
        const corners = [-1, 1].flatMap((x) =>
          [-1, 1].map((y) => {
            const p = own.position
              .clone()
              .set(x * extent, y * extent, 0)
              .applyMatrix4(own.matrixWorld)
              .project(state.camera);
            return {
              x: viewport.x + ((p.x + 1) * viewport.width) / 2,
              y: viewport.y + ((1 - p.y) * viewport.height) / 2,
            };
          })
        );
        const protectedBox = {
          left: Math.min(...corners.map((p) => p.x)) - 8,
          right: Math.max(...corners.map((p) => p.x)) + 8,
          top: Math.min(...corners.map((p) => p.y)) - 8,
          bottom: Math.max(...corners.map((p) => p.y)) + 8,
        };
        if (
          protectedBox.right > viewport.x &&
          protectedBox.left < viewport.right &&
          protectedBox.bottom > viewport.y &&
          protectedBox.top < viewport.bottom
        ) {
          evidence.frames++;
          evidence.poses.add(
            state.camera.position
              .toArray()
              .map((n) => n.toFixed(4))
              .join(',')
          );
          evidence.aircraftPositions.add(
            own.matrixWorld.elements
              .slice(12, 15)
              .map((n) => n.toFixed(5))
              .join(',')
          );
          for (const node of document.querySelectorAll<HTMLElement>(
            '[data-label-source],.overview-label-group summary,.overview-label-group[open] ul'
          )) {
            if (
              !node.getClientRects().length ||
              getComputedStyle(node).visibility !== 'visible'
            )
              continue;
            const b = node.getBoundingClientRect();
            evidence.visibleLabels++;
            if (
              b.left < protectedBox.right &&
              b.right > protectedBox.left &&
              b.top < protectedBox.bottom &&
              b.bottom > protectedBox.top &&
              evidence.violations.length < 20
            )
              evidence.violations.push({
                label: node.textContent,
                box: b.toJSON(),
                aircraft: protectedBox,
              });
          }
        }
      }
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
}

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
  { width: 844, height: 390 },
]) {
  test(`own aircraft stays clear during camera and telemetry motion at ${viewport.width}x${viewport.height}`, async ({
    page,
    context,
  }, info) => {
    await page.setViewportSize(viewport);
    const fixture = await installAdsbFixture(context, true);
    let tick = 0;
    let moving = false;
    await context.route('**/api/status', (route) => {
      if (moving) tick++;
      return route.fulfill({
        json: {
          timestamp: new Date().toISOString(),
          position: {
            ...origin,
            longitude: origin.longitude + Math.sin(tick / 2) * 0.08,
            heading: tick * 35,
            altitude: 35000,
          },
          ground_entry_point: origin,
          metric_availability: {
            latency_ms: true,
            throughput_down_mbps: true,
            throughput_up_mbps: true,
            packet_loss_percent: true,
            obstruction_percent: true,
          },
          network: {
            latency_ms: 54,
            throughput_down_mbps: 58.3,
            throughput_up_mbps: 32,
            packet_loss_percent: 0.004,
          },
          obstruction: { obstruction_percent: 31.24 },
        },
      });
    });
    const routePoints = [origin, { latitude: 40, longitude: -80 }];
    await context.route('**/api/routes/route-a', (route) =>
      route.fulfill({ json: { id: 'route-a', points: routePoints } })
    );
    await context.route('**/api/overview/upcoming-pois', (route) =>
      route.fulfill({
        json: {
          state: 'available',
          calculated_at: new Date().toISOString(),
          flight_phase: 'in_flight',
          position_state: 'fresh',
          position_observed_at: new Date().toISOString(),
          current_route_progress: 0,
          pois: Array.from({ length: 40 }, (_, i) => ({
            poi_id: `cluster-${i}`,
            name: i
              ? `KADW coincident operational POI with a long name ${i}`
              : 'KADW',
            kind: 'ka_coverage_entry',
            ...origin,
            projected_route_progress: 0,
            flight_phase: 'in_flight',
            eta_seconds: null,
            estimated_arrival_time: null,
            expected_arrival_time: null,
            eta_type: null,
            upcoming: true,
            map_retained: true,
          })),
        },
      })
    );
    fixture.setSettings(adsbSettings({ include_hexes: ['00AB12', '000001'] }));
    fixture.setContacts([
      freshContact({
        ...origin,
        callsign: 'MYSTC13',
        position_observed_at_ms: Date.now() - 40000,
      }),
      freshContact({
        ...origin,
        hex: '000001',
        callsign: 'VERY LONG COINCIDENT AIRCRAFT IDENTITY WITH A STALE BADGE',
        position_observed_at_ms: Date.now() - 40000,
      }),
    ]);
    await observeOverviewCamera(page);
    await page.goto('/overview');
    await settledOverviewCamera(page);
    await expect(page.locator('[data-adsb-label="00AB12"]')).toContainText(
      'Stale'
    );
    await monitorFrames(page);
    moving = true;
    const disclosure = page
      .locator('.overview-label-group:visible summary')
      .first();
    await expect(disclosure).toBeVisible();
    await disclosure.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.overview-label-group[open]')).toHaveCount(1);
    const popup = page.locator('.overview-label-group[open] ul');
    // A compact canvas may have no room for the full list beside the aircraft.
    // Its identities remain in the disclosure; suppression is aircraft-safe.
    expect(await popup.locator('li').count()).toBeGreaterThan(1);
    await expect(popup).toContainText('KADW');
    if (viewport.width === 1920) await expect(popup).toBeVisible();
    if (await popup.isVisible())
      expect((await popup.boundingBox())!.height).toBeLessThanOrEqual(180);
    if (viewport.width !== 1920)
      await page
        .getByRole('button', { name: 'Explore map', exact: true })
        .click();
    const canvas = await page
      .locator('.overview-map-stage canvas')
      .boundingBox();
    await page.mouse.move(
      canvas!.x + canvas!.width * 0.5,
      canvas!.y + canvas!.height * 0.65
    );
    await page.mouse.down();
    await page.mouse.move(
      canvas!.x + canvas!.width * 0.58,
      canvas!.y + canvas!.height * 0.6,
      { steps: 18 }
    );
    await page.mouse.up();
    await page.mouse.wheel(0, -120);
    // Exercise a deterministic damped camera transition as well as gestures;
    // compact overlay rails can intercept the pointer path.
    await page.evaluate(() => {
      const state = window.__overviewEvidenceRoots
        ?.find(
          (root) =>
            root.containerInfo?.getState &&
            document.contains(root.containerInfo.getState().gl.domElement)
        )
        ?.containerInfo?.getState?.();
      if (!state?.controls) throw new Error('No camera controls');
      void state.controls.rotate(0.08, 0.03, true);
    });
    await page.waitForTimeout(1500);
    if (viewport.width !== 1920)
      await page
        .getByRole('button', { name: 'Exit map exploration', exact: true })
        .click();
    // Freshness/content changes arrive through the actual polling hooks.
    fixture.setContacts([
      freshContact({
        ...origin,
        callsign: 'MYSTC13 FRESH WITH A MUCH LONGER IDENTITY',
      }),
      freshContact({
        ...origin,
        hex: '000001',
        callsign: 'SECOND COINCIDENT CONTACT',
      }),
    ]);
    await expect(page.locator('[data-adsb-label="00AB12"]')).toContainText(
      'FRESH',
      { timeout: 20000 }
    );
    if (viewport.width === 1920) {
      await page
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
      await expect
        .poll(() => page.evaluate(() => !!document.fullscreenElement))
        .toBe(true);
      await page.waitForTimeout(1000);
      await page.screenshot({
        path: info.outputPath('own-aircraft-fullscreen.png'),
      });
      await page
        .getByRole('button', { name: 'Exit fullscreen overview' })
        .click();
      await expect
        .poll(() => page.evaluate(() => !!document.fullscreenElement))
        .toBe(false);
    }
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '32px';
    });
    await page.waitForTimeout(1500);
    await page.screenshot({
      path: info.outputPath('own-aircraft-enlarged-text.png'),
    });
    const evidence = await page.evaluate(() => {
      const e = (
        window as unknown as {
          __labelOcclusionEvidence: {
            frames: number;
            visibleLabels: number;
            violations: unknown[];
            poses: Set<string>;
            aircraftPositions: Set<string>;
          };
        }
      ).__labelOcclusionEvidence;
      return {
        frames: e.frames,
        visibleLabels: e.visibleLabels,
        violations: e.violations,
        cameraPoses: e.poses.size,
        aircraftPositions: e.aircraftPositions.size,
      };
    });
    const evidencePath = info.outputPath('moving-scene.json');
    await writeFile(evidencePath, JSON.stringify(evidence, null, 2));
    await info.attach('moving-scene.json', {
      path: evidencePath,
      contentType: 'application/json',
    });
    expect(evidence.frames).toBeGreaterThan(50);
    expect(evidence.visibleLabels).toBeGreaterThan(50);
    expect(evidence.cameraPoses).toBeGreaterThan(5);
    expect(evidence.aircraftPositions).toBeGreaterThan(1);
    expect(evidence.violations).toEqual([]);
    moving = false;
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '';
      for (const details of document.querySelectorAll<HTMLDetailsElement>(
        '.overview-label-group'
      ))
        details.open = false;
    });
    await page.locator('.overview-map-stage').scrollIntoViewIfNeeded();
    await page.getByRole('button', { name: 'Reset map view' }).click();
    await settledOverviewCamera(page);
    // Marker selection and its accessible identity survive label movement.
    const point = (await adsbScene(page)).batches
      .flatMap((b) => b.points)
      .find((p) => p.hex === '00AB12')!;
    await page.mouse.click(point.x, point.y);
    await expect(page.getByRole('dialog')).toBeVisible();
    // Coincident contacts share a hit target; either identity can be picked.
    await expect(page.getByRole('dialog')).toContainText(/00AB12|000001/);
    await page.keyboard.press('Escape');
    await page
      .getByRole('button', { name: 'Details for 00AB12' })
      .press('Enter');
    await expect(page.getByRole('dialog')).toContainText('00AB12');
    await page.keyboard.press('Escape');
  });
}
