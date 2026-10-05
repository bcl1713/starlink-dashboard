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
  vi.unstubAllGlobals();
});

it('advances accelerated time on display frames between server responses and freezes on failure', () => {
  let monotonic = 0;
  let frame: FrameRequestCallback | undefined;
  vi.spyOn(performance, 'now').mockImplementation(() => monotonic);
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    frame = callback;
    return 1;
  });
  vi.stubGlobal('cancelAnimationFrame', () => {
    frame = undefined;
  });
  const status = parseSimulationRun(runningStatus());
  const { result, rerender, unmount } = renderHook(
    ({ failed }) => useSimulationClock(status, 0, failed, true),
    { initialProps: { failed: false } }
  );
  const start = result.current.missionNowMs;
  for (const elapsed of [16, 32, 48]) {
    act(() => {
      monotonic = elapsed;
      const callback = frame;
      frame = undefined;
      callback?.(elapsed);
    });
    expect(result.current.missionNowMs).toBe(start + elapsed * 10);
  }
  rerender({ failed: true });
  const frozen = result.current.missionNowMs;
  act(() => {
    monotonic = 500;
    frame?.(500);
  });
  expect(result.current.missionNowMs).toBe(frozen);
  expect(result.current.stale).toBe(true);
  unmount();
  expect(frame).toBeUndefined();
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
