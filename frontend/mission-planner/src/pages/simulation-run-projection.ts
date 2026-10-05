import type { SimulationRunStatus } from '@/services/simulation-run';
function observationAge(
  status: SimulationRunStatus,
  received: number,
  now: number
) {
  return (
    Math.max(
      0,
      Date.parse(status.served_at) - Date.parse(status.run!.observed_at)
    ) + Math.max(0, now - received)
  );
}
export function isRunStale(
  status: SimulationRunStatus | undefined,
  received: number,
  now: number,
  failed: boolean
) {
  return (
    status?.state === 'running' &&
    (failed || observationAge(status, received, now) >= 10_000)
  );
}
export function projectMissionTime(
  status: SimulationRunStatus | undefined,
  receivedMonotonicMs: number,
  monotonicNowMs: number,
  realNowMs: number,
  refreshFailed: boolean,
  previousDisplayTimeMs?: number
): number {
  if (status?.state !== 'running' || !status.run) return realNowMs;
  const run = status.run,
    observed = Date.parse(run.simulation_time);
  const serverAge = Math.max(
    0,
    Date.parse(status.served_at) - Date.parse(run.observed_at)
  );
  const interval = refreshFailed
    ? 0
    : Math.min(
        Math.max(0, monotonicNowMs - receivedMonotonicMs),
        Math.max(0, 10_000 - serverAge)
      );
  const projected = observed + interval * run.effective_multiplier;
  return Math.min(
    Date.parse(run.planned_arrival),
    Math.max(projected, previousDisplayTimeMs ?? observed)
  );
}
