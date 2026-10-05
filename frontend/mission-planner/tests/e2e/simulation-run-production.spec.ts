import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import {
  seedSimulationRunMission,
  startSimulation,
} from './support/simulation-run-mission';
import { readRun, finishRun } from './support/simulation-run-observations';
import { runTargetJourney } from './support/simulation-run-target';
const evidence = process.env.SIMULATION_SPEED_EVIDENCE_DIR!;
test(
  '120-second leg reaches all events and final arrival in two visible windows',
  runTargetJourney
);
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
test('short target wakes the producer during an ordinary 30-second wait', async ({
  request,
}, info) => {
  const seed = await seedSimulationRunMission(request);
  await startSimulation(request, seed, {
    mode: 'target_runtime',
    runtime_seconds: 2,
  });
  const final = await finishRun(request, seed);
  expect(final.run!.elapsed_real_seconds).toBeGreaterThanOrEqual(2);
  expect(final.run!.elapsed_real_seconds).toBeLessThanOrEqual(3);
  await writeFile(
    info.outputPath('short-target.json'),
    JSON.stringify(final, null, 2)
  );
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
