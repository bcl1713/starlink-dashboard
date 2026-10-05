import { expect, type APIRequestContext, type Page } from '@playwright/test';
import { simulationRunSchema } from '../../../src/services/simulation-run';
import type { seedSimulationRunMission } from './simulation-run-mission';
export async function readRun(request: APIRequestContext) {
  const response = await request.get('/api/simulation/run');
  expect(response.ok()).toBeTruthy();
  return simulationRunSchema.parse(await response.json());
}
export async function finishRun(
  request: APIRequestContext,
  seed: Awaited<ReturnType<typeof seedSimulationRunMission>>
) {
  await expect
    .poll(async () => (await readRun(request)).state, {
      timeout: 125_000,
      intervals: [250],
    })
    .toBe('completed');
  const status = await readRun(request),
    run = status.run!;
  expect(run.progress_percent).toBe(100);
  expect(run.phase).toBe('post_arrival');
  expect(run.processed_event_count).toBe(seed.expectedEventCount);
  expect(run.transport_states).toEqual(seed.expectedFinalStates);
  expect(
    Date.parse(run.simulation_time) - Date.parse(run.planned_departure)
  ).toBe(seed.duration * 1000);
  const position = (await (await request.get('/api/status')).json()).position;
  expect(position.latitude).toBe(seed.arrival.latitude);
  expect(position.longitude).toBe(seed.arrival.longitude);
  expect((await (await request.get('/api/flight-status')).json()).phase).toBe(
    'post_arrival'
  );
  expect(
    (await (await request.get('/api/active-x-link')).json()).satellite_id
  ).toBe('Paced-X-3');
  return status;
}
export async function renderedTrailCount(page: Page) {
  return page.evaluate(() => {
    type Fiber = {
      child?: Fiber;
      sibling?: Fiber;
      memoizedProps?: { core?: { color?: string }; points?: number[][] };
    };
    const roots =
      (
        window as unknown as {
          __overviewEvidenceRoots?: Array<{ current?: Fiber }>;
        }
      ).__overviewEvidenceRoots ?? [];
    const pending = roots.flatMap((root) =>
      root.current ? [root.current] : []
    );
    while (pending.length) {
      const fiber = pending.pop()!;
      if (
        fiber.memoizedProps?.core?.color === '#d9ffff' &&
        fiber.memoizedProps.points
      )
        return fiber.memoizedProps.points.length;
      if (fiber.child) pending.push(fiber.child);
      if (fiber.sibling) pending.push(fiber.sibling);
    }
    return 0;
  });
}
