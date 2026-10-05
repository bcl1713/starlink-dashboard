import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import {
  seedSimulationRunMission,
  startSimulation,
} from './support/simulation-run-mission';
import {
  readRun,
  finishRun,
  renderedTrailCount,
} from './support/simulation-run-observations';
import { simulationRunSchema } from '../../src/services/simulation-run';
import {
  installOverviewRouteProbe,
  renderedRoutePoints,
} from './support/overview-route-probe';
import { projectRouteArc } from '../../src/pages/globe-route-projection';
import { ROUTE_OVERLAY_RADIUS } from '../../src/pages/globe-render-radii';
const evidence = process.env.SIMULATION_SPEED_EVIDENCE_DIR!;

test('120-second leg reaches all events and final arrival in two visible windows', async ({
  browser,
  page,
  request,
}, info) => {
  const seed = await seedSimulationRunMission(request);
  const second = await browser.newContext({
    baseURL: process.env.SIMULATION_ACCEPTANCE_BASE_URL,
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: info.outputPath('second-video') },
  });
  const overview = await second.newPage();
  await installOverviewRouteProbe(overview);
  await overview.goto('/overview');
  await expect(overview.locator('canvas').first()).toBeVisible();
  await overview.evaluate(() => {
    Object.assign(window, { __pacedCanvas: document.querySelector('canvas') });
  });
  const followBefore = await overview.evaluate(() =>
    localStorage.getItem('overview.follow-aircraft')
  );
  await page.goto(`/missions/${seed.missionId}`);
  await page.getByRole('button', { name: 'Simulate leg…' }).click();
  await page.getByLabel('Target runtime', { exact: true }).check();
  await page.getByLabel('Runtime seconds').fill('120');
  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  await expect(page.getByLabel('Simulation preview')).toContainText('10×');
  const activation = page.waitForResponse(
    (response) =>
      response.url().endsWith('/activate') &&
      response.request().method() === 'POST'
  );
  await page.getByRole('button', { name: 'Start simulation' }).click();
  const started = await activation;
  expect(started.ok()).toBeTruthy();
  const startStatus = simulationRunSchema.parse(
      (await started.json()).simulation_run
    ),
    startAt = performance.now();
  await expect(overview.getByLabel('Simulation run')).toContainText('Running', {
    timeout: 3000,
  });
  const propagationMs = performance.now() - startAt;
  await expect(overview.getByLabel('Overview metric history')).toHaveCount(0);
  await expect(overview.getByText('SIMULATED TIME')).toBeVisible();
  await overview.screenshot({ path: info.outputPath('running-desktop.png') });
  await page.goto('/overview');
  await expect(page.getByLabel('Simulation run')).toContainText('Running');
  expect(await page.evaluate(() => document.visibilityState)).toBe('visible');
  expect(await overview.evaluate(() => document.visibilityState)).toBe(
    'visible'
  );
  const geometry = await (
    await request.get(`/api/simulation/run/${startStatus.run!.run_id}/route`)
  ).json();
  await expect
    .poll(() => renderedRoutePoints(overview))
    .toEqual(projectRouteArc(geometry.route.points, ROUTE_OVERLAY_RADIUS, 8));
  await overview.setViewportSize({ width: 390, height: 844 });
  await overview.screenshot({
    path: info.outputPath('running-responsive.png'),
  });
  await overview.setViewportSize({ width: 1920, height: 1080 });
  await overview
    .getByRole('button', { name: 'Enter fullscreen overview' })
    .click();
  await expect
    .poll(() => overview.evaluate(() => Boolean(document.fullscreenElement)))
    .toBe(true);
  await overview.screenshot({
    path: info.outputPath('running-fullscreen.png'),
  });
  const final = await finishRun(request, seed),
    completedAt = performance.now();
  await expect(overview.getByLabel('Simulation run')).toContainText(
    'Completed',
    { timeout: 3000 }
  );
  await expect(page.getByLabel('Simulation run')).toContainText('Completed', {
    timeout: 3000,
  });
  const terminalPropagationMs = performance.now() - completedAt;
  await expect(overview.getByLabel('Overview metric history')).toBeVisible();
  await expect(overview.getByText('SIMULATED TIME')).toHaveCount(0);
  expect(
    await overview.evaluate(
      () =>
        document.querySelector('canvas') ===
        (window as unknown as { __pacedCanvas: Element }).__pacedCanvas
    )
  ).toBe(true);
  expect(
    await overview.evaluate(() =>
      localStorage.getItem('overview.follow-aircraft')
    )
  ).toBe(followBefore);
  await expect
    .poll(() => renderedTrailCount(overview), { timeout: 30_000 })
    .toBeGreaterThan(1);
  await overview.screenshot({
    path: info.outputPath('restored-fullscreen.png'),
  });
  await overview
    .getByRole('button', { name: 'Exit fullscreen overview' })
    .click();
  await overview.screenshot({ path: info.outputPath('restored-desktop.png') });
  await writeFile(
    info.outputPath('result.json'),
    JSON.stringify(
      {
        sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
        seed,
        startStatus,
        final,
        elapsedBrowserMs: performance.now() - startAt,
        propagationMs,
        terminalPropagationMs,
        browser: browser.version(),
        os: process.platform,
      },
      null,
      2
    )
  );
  expect(final.run!.elapsed_real_seconds).toBeGreaterThanOrEqual(120);
  expect(final.run!.elapsed_real_seconds).toBeLessThanOrEqual(121);
  await second.close();
});
test('fixed rate matches target runtime', async ({ request }, info) => {
  const seed = await seedSimulationRunMission(request);
  const start = await startSimulation(request, seed, {
    mode: 'multiplier',
    multiplier: 10,
  });
  expect(start.run.effective_multiplier).toBe(10);
  expect(start.run.expected_runtime_seconds).toBe(120);
  const final = await finishRun(request, seed);
  await writeFile(
    info.outputPath('fixed-rate.json'),
    JSON.stringify({ start, final }, null, 2)
  );
  expect(final.run!.elapsed_real_seconds).toBeGreaterThanOrEqual(120);
  expect(final.run!.elapsed_real_seconds).toBeLessThanOrEqual(121);
});
test('high-rate frames preserve transitions and slow pacing stays bounded', async ({
  request,
}, info) => {
  const long = await seedSimulationRunMission(request, true);
  await startSimulation(request, long, {
    mode: 'multiplier',
    multiplier: 1000,
  });
  const final = await finishRun(request, long);
  const slow = await seedSimulationRunMission(request);
  await startSimulation(request, slow, { mode: 'multiplier', multiplier: 0.1 });
  await expect
    .poll(async () => (await readRun(request)).run!.elapsed_real_seconds, {
      timeout: 5000,
    })
    .toBeGreaterThan(1);
  const bounded = await readRun(request);
  expect(
    Date.parse(bounded.run!.simulation_time) -
      Date.parse(bounded.run!.planned_departure)
  ).toBeLessThan(1000);
  expect(
    (
      await request.post(`/api/v2/missions/${slow.missionId}/legs/deactivate`)
    ).ok()
  ).toBeTruthy();
  await writeFile(
    info.outputPath('bounded.json'),
    JSON.stringify({ final, bounded }, null, 2)
  );
});
test('cancel and switch are truthful and restart fixture stays running', async ({
  page,
  request,
}, info) => {
  const seed = await seedSimulationRunMission(request);
  await page.goto('/overview');
  await startSimulation(request, seed, { mode: 'multiplier', multiplier: 2 });
  await expect(page.getByLabel('Overview metric history')).toHaveCount(0);
  expect(
    (
      await request.post(`/api/v2/missions/${seed.missionId}/legs/deactivate`)
    ).ok()
  ).toBeTruthy();
  await expect(page.getByLabel('Simulation run')).toContainText('Cancelled', {
    timeout: 3000,
  });
  await expect(page.getByLabel('Overview metric history')).toBeVisible();
  await page.screenshot({ path: info.outputPath('cancel-restored.png') });
  await startSimulation(request, seed, { mode: 'multiplier', multiplier: 1 });
  expect((await request.post('/api/routes/deactivate')).ok()).toBeTruthy();
  expect((await readRun(request)).state).toBe('cancelled');
  const status = await startSimulation(request, seed, {
    mode: 'multiplier',
    multiplier: 0.1,
  });
  await writeFile(
    join(evidence, 'restart-runtime.json'),
    JSON.stringify({ runtime_id: status.runtime_id, seed }, null, 2)
  );
});
test('restart-idle clears active flags and does not resume', async ({
  request,
}) => {
  const previous = JSON.parse(
    await readFile(join(evidence, 'restart-runtime.json'), 'utf8')
  );
  const status = await readRun(request);
  expect(status.runtime_id).not.toBe(previous.runtime_id);
  expect(status.state).toBe('idle');
  expect(status.run).toBeNull();
  const mission = await (
    await request.get(`/api/v2/missions/${previous.seed.missionId}`)
  ).json();
  expect(
    mission.legs.every((leg: { is_active: boolean }) => !leg.is_active)
  ).toBe(true);
  await writeFile(
    join(evidence, 'restart-result.json'),
    JSON.stringify(status, null, 2)
  );
});
test('live mode rejects paced requests through both entry points', async ({
  request,
}) => {
  const seed = await seedSimulationRunMission(request);
  const before = await readRun(request);
  expect(before.service_mode).toBe('live');
  const path = `/api/v2/missions/${seed.missionId}/legs/${seed.legId}`;
  expect(
    (
      await request.post(`${path}/simulation/preview`, {
        data: { mode: 'multiplier', multiplier: 10 },
      })
    ).status()
  ).toBe(409);
  expect(
    (
      await request.post(`${path}/activate`, {
        data: {
          simulation: {
            pacing: { mode: 'multiplier', multiplier: 10 },
            plan_token: 'a'.repeat(64),
          },
        },
      })
    ).status()
  ).toBe(409);
  const after = await readRun(request);
  expect(after.run).toBeNull();
  expect(after.revision).toBe(before.revision);
  await writeFile(
    join(evidence, 'live-result.json'),
    JSON.stringify(
      {
        before,
        after,
        hardware:
          'connect/test_connection forced disconnected; real app and HTTP paths',
      },
      null,
      2
    )
  );
});
