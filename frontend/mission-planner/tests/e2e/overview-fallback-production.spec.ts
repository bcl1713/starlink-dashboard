import { writeFile } from 'node:fs/promises';
import { expect, test, type Page } from '@playwright/test';
import {
  observeOverviewCamera,
  overviewCamera,
} from './support/overview-camera';
import { sampleRunMotion } from './support/simulation-run-motion-probe';
import {
  seedSimulationRunMission,
  startSimulation,
} from './support/simulation-run-mission';

async function renderedAircraft(page: Page) {
  const [sample] = await sampleRunMotion(page, 1);
  const visibleChevron = await page.evaluate(() => {
    type Node = {
      visible: boolean;
      userData: { starMarkerShape?: string };
      traverse: (visit: (node: Node) => void) => void;
    };
    const roots = (
      window as unknown as {
        __overviewEvidenceRoots?: Array<{
          containerInfo?: { getState?: () => { scene: Node } };
        }>;
      }
    ).__overviewEvidenceRoots;
    let visible = false;
    for (const root of roots ?? []) {
      root.containerInfo?.getState?.().scene.traverse((node) => {
        if (node.userData.starMarkerShape === 'chevron' && node.visible)
          visible = true;
      });
    }
    return visible;
  });
  return { coordinate: sample?.aircraft, visibleChevron };
}

for (const longitude of [179.95, -179.95]) {
  test(`real fallback crosses the dateline and resumes after mission with reset framing (${longitude})`, async ({
    page,
    request,
  }, info) => {
    expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
    expect(await (await request.get('/api/v2/missions')).json()).toEqual([]);
    const original = await (await request.get('/api/config')).json();
    const observations: unknown[] = [];
    try {
      // Supported simulator settings accelerate a fabricated 100 km circle so
      // both dateline crossings fit in a bounded browser observation.
      const configured = await request.post('/api/config', {
        data: {
          ...original,
          route: {
            ...original.route,
            latitude_start: 70,
            longitude_start: longitude,
          },
          position: {
            ...original.position,
            speed_min_knots: 60000,
            speed_max_knots: 60000,
          },
        },
      });
      expect(configured.ok(), await configured.text()).toBeTruthy();
      await observeOverviewCamera(page);
      await page.goto('/overview');
      await expect(
        page.getByText('No active route.', { exact: true })
      ).toBeVisible();
      const longitudes: number[] = [];
      const renderedLongitudes: number[] = [];
      for (let index = 0; index < 26; index++) {
        const response = await request.get('/api/status');
        expect(response.ok()).toBeTruthy();
        expect(response.headers().server).toMatch(/nginx/);
        const status = await response.json();
        expect(status.position.latitude).toBeGreaterThan(69);
        expect(status.position.latitude).toBeLessThan(71);
        expect(Math.abs(status.position.longitude)).toBeGreaterThan(177);
        expect(Math.abs(status.position.longitude)).toBeLessThanOrEqual(180);
        longitudes.push(status.position.longitude);
        await expect
          .poll(async () => (await renderedAircraft(page)).visibleChevron)
          .toBe(true);
        const rendered = await renderedAircraft(page);
        expect(rendered.coordinate).toBeDefined();
        expect(Math.abs(rendered.coordinate!.longitude)).toBeGreaterThan(177);
        expect(Math.abs(rendered.coordinate!.longitude)).toBeLessThanOrEqual(
          180
        );
        renderedLongitudes.push(rendered.coordinate!.longitude);
        observations.push({ status, rendered });
        await page.waitForTimeout(1000);
      }
      expect(longitudes.some((lon) => lon < -177)).toBe(true);
      expect(longitudes.some((lon) => lon > 177)).toBe(true);
      expect(new Set(longitudes).size).toBeGreaterThan(20);
      expect(new Set(renderedLongitudes).size).toBeGreaterThan(5);
      await page.screenshot({ path: info.outputPath('fallback-dateline.png') });

      const seed = await seedSimulationRunMission(request);
      await startSimulation(request, seed, {
        mode: 'target_runtime',
        runtime_seconds: 20,
      });
      await expect
        .poll(async () => (await renderedAircraft(page)).coordinate?.latitude)
        .toBeCloseTo(35, 1);
      await expect
        .poll(async () => (await renderedAircraft(page)).visibleChevron)
        .toBe(true);
      observations.push({ mission: await renderedAircraft(page) });
      await page.screenshot({ path: info.outputPath('mission-aircraft.png') });
      const deactivated = await request.post(
        `/api/v2/missions/${seed.missionId}/legs/deactivate`
      );
      expect(deactivated.ok(), await deactivated.text()).toBeTruthy();
      await expect(
        page.getByText('No active route.', { exact: true })
      ).toBeVisible();
      await expect
        .poll(async () => (await renderedAircraft(page)).coordinate?.latitude)
        .toBeGreaterThan(69);
      const resumedBeforeReset = await renderedAircraft(page);
      await expect
        .poll(async () => (await renderedAircraft(page)).coordinate?.longitude)
        .not.toBe(resumedBeforeReset.coordinate!.longitude);
      observations.push({
        resumedBeforeReset,
        resumedBeforeResetMoved: await renderedAircraft(page),
        retainedCamera: await overviewCamera(page),
      });
      await page.screenshot({
        path: info.outputPath('fallback-retained-camera.png'),
      });
      // Automatic view retains the mission framing after route removal. First
      // prove telemetry/scene recovery, then use the normal reset control to
      // establish visibility without changing camera policy in this position fix.
      await page
        .getByRole('button', { name: 'Reset map view', exact: true })
        .click();
      await expect
        .poll(async () => (await renderedAircraft(page)).visibleChevron, {
          timeout: 15000,
        })
        .toBe(true);
      const before = await (await request.get('/api/status')).json();
      await expect
        .poll(
          async () =>
            (await (await request.get('/api/status')).json()).position.longitude
        )
        .not.toBe(before.position.longitude);
      observations.push({ resumed: await renderedAircraft(page) });
      await page.screenshot({ path: info.outputPath('fallback-resumed.png') });
    } finally {
      // This project starts with empty task-owned storage, so also remove any
      // partially seeded mission after an early assertion or upload failure.
      const missions = await (await request.get('/api/v2/missions')).json();
      for (const mission of missions) {
        await request.post(`/api/v2/missions/${mission.id}/legs/deactivate`);
        expect(
          (await request.delete(`/api/v2/missions/${mission.id}`)).status()
        ).toBe(204);
      }
      expect(
        (await request.post('/api/config', { data: original })).ok()
      ).toBeTruthy();
      await writeFile(
        info.outputPath('observations.json'),
        JSON.stringify(
          {
            candidate: process.env.ACCEPTANCE_CANDIDATE_SHA,
            longitude,
            observations,
          },
          null,
          2
        )
      );
    }
  });
}
