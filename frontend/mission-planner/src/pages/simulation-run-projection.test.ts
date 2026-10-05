import { expect, it } from 'vitest';
import { projectMissionTime, isRunStale } from './simulation-run-projection';
import { runningStatus, completedStatus } from '@/test/simulation-run-fixtures';
const real = Date.parse('2026-10-05T00:00:00Z');
const simulated = Date.parse('2025-01-01T01:02:00Z');
it('advances the old planned clock by monotonic time despite UTC jumps', () => {
  expect(
    projectMissionTime(runningStatus(), 100, 1100, real + 99_000, false)
  ).toBe(simulated + 10_000);
});
it('freezes on failed refresh and caps ten-second silence and arrival', () => {
  expect(
    projectMissionTime(runningStatus(), 0, 5000, real, true, simulated + 2000)
  ).toBe(simulated + 2000);
  expect(projectMissionTime(runningStatus(), 0, 11_000, real, false)).toBe(
    simulated + 100_000
  );
  expect(isRunStale(runningStatus(), 0, 11_000, false)).toBe(true);
  const status = runningStatus();
  status.run!.simulation_time = '2025-01-01T01:19:59Z';
  expect(projectMissionTime(status, 0, 1000, real, false)).toBe(
    Date.parse(status.run!.planned_arrival)
  );
});
it('uses server observation age rather than browser clock skew', () => {
  const status = runningStatus();
  status.served_at = '2026-10-05T00:00:11Z';
  expect(isRunStale(status, 0, 0, false)).toBe(true);
  expect(projectMissionTime(status, 0, 1000, real - 999999, false)).toBe(
    simulated
  );
});
it('does not rewind same-run corrections and returns to real terminal clocks', () => {
  expect(
    projectMissionTime(runningStatus(), 0, 0, real, false, simulated + 5000)
  ).toBe(simulated + 5000);
  expect(projectMissionTime(completedStatus(), 0, 1000, real, false)).toBe(
    real
  );
});
