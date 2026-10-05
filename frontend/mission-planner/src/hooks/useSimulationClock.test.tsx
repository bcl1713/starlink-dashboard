/** @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { parseSimulationRun } from '@/services/simulation-run';
import { runningStatus } from '@/test/simulation-run-fixtures';
import { useSimulationClock } from './useSimulationClock';
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});
it('does not renew a producer observation with repeated reads after backward server UTC', () => {
  vi.useFakeTimers();
  let monotonic = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => monotonic);
  function read(revision = 2) {
    const status = runningStatus();
    status.revision = revision;
    status.served_at = '2026-10-04T23:00:00Z';
    return parseSimulationRun(status);
  }
  const { result, rerender } = renderHook(
    ({ status }) => useSimulationClock(status, 0, false),
    { initialProps: { status: read() } }
  );
  for (let i = 1; i <= 12; i++) {
    act(() => {
      monotonic = i * 1000;
      vi.advanceTimersByTime(1000);
    });
    rerender({ status: read() });
  }
  expect(result.current.stale).toBe(true);
  const frozen = result.current.missionNowMs;
  act(() => {
    monotonic += 1000;
    vi.advanceTimersByTime(1000);
  });
  rerender({ status: read() });
  expect(result.current.missionNowMs).toBe(frozen);
  rerender({ status: read(3) });
  expect(result.current.stale).toBe(false);
});
