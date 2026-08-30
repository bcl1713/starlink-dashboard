import { act, renderHook } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useOverviewClock } from './useOverviewClock';
import {
  useOverviewRefresh,
  type OverviewRefreshReason,
} from './useOverviewRefresh';
import type { OverviewRefreshCadence } from './preferences';

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('useOverviewRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('schedules recursively on epoch boundaries and supports manual refresh', async () => {
    let now = 0;
    const calls: OverviewRefreshReason[] = [];
    const onRefresh = vi.fn(async (reason: OverviewRefreshReason) => {
      calls.push(reason);
    });
    const { result, unmount } = renderHook(() =>
      useOverviewRefresh({ cadence: 1, now: () => now, onRefresh })
    );

    for (let index = 0; index < 5; index += 1) {
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
    }
    await act(async () => result.current.manualRefresh());

    expect(calls).toEqual([
      'scheduled',
      'scheduled',
      'scheduled',
      'scheduled',
      'scheduled',
      'manual',
    ]);
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('does not zero-loop on exact boundary or replay large jumps', async () => {
    let now = 1000;
    const onRefresh = vi.fn(async () => {});
    renderHook(() =>
      useOverviewRefresh({ cadence: 1, now: () => now, onRefresh })
    );

    expect(vi.getTimerCount()).toBe(1);
    await act(async () => vi.advanceTimersByTime(1));
    expect(onRefresh).not.toHaveBeenCalled();
    now = 20_000;
    await act(async () => vi.advanceTimersByTime(999));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('coalesces manual requests during a slow scheduled refresh', async () => {
    let now = 0;
    const gate = deferred();
    const calls: OverviewRefreshReason[] = [];
    const onRefresh = vi.fn((reason: OverviewRefreshReason) => {
      calls.push(reason);
      return reason === 'scheduled' ? gate.promise : Promise.resolve();
    });
    const { result } = renderHook(() =>
      useOverviewRefresh({ cadence: 1, now: () => now, onRefresh })
    );

    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    let first!: Promise<void>;
    let second!: Promise<void>;
    await act(async () => {
      first = result.current.manualRefresh();
      second = result.current.manualRefresh();
    });
    expect(first).toBe(second);
    expect(result.current.isManualRefreshPending).toBe(true);
    gate.resolve();
    await act(async () => first);
    expect(calls).toEqual(['scheduled', 'manual']);
    expect(result.current.isManualRefreshPending).toBe(false);
  });

  it('recovers from rejection and settles unmount cases exactly', async () => {
    const active = deferred();
    const onRefresh = vi
      .fn()
      .mockRejectedValueOnce(new Error('scheduled'))
      .mockResolvedValueOnce(undefined)
      .mockImplementationOnce(() => active.promise);
    let now = 0;
    const { result, rerender, unmount } = renderHook(
      ({ cadence }) =>
        useOverviewRefresh({ cadence, now: () => now, onRefresh }),
      { initialProps: { cadence: 1 as OverviewRefreshCadence } }
    );

    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    await act(async () => Promise.resolve());
    await expect(result.current.manualRefresh()).resolves.toBeUndefined();
    let manual!: Promise<void>;
    let same!: Promise<void>;
    await act(async () => {
      manual = result.current.manualRefresh();
      same = result.current.manualRefresh();
    });
    expect(manual).toBe(same);
    rerender({ cadence: 'paused' });
    const expectation = expect(manual).resolves.toBeUndefined();
    unmount();
    active.resolve();
    await expectation;
    await expect(result.current.manualRefresh()).rejects.toEqual(
      Error('Overview refresh unmounted')
    );
  });

  it('rejects queued manual work on unmount and keeps combined timers bounded', async () => {
    let nowMs = 0;
    const gate = deferred();
    const onRefresh = vi.fn(() => gate.promise);
    const { result, unmount } = renderHook(() => {
      useOverviewClock(() => new Date(nowMs));
      return useOverviewRefresh({ cadence: 1, now: () => nowMs, onRefresh });
    });

    expect(vi.getTimerCount()).toBe(2);
    nowMs = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    const queued = result.current.manualRefresh();
    const queuedExpectation = expect(queued).rejects.toEqual(
      Error('Overview refresh unmounted')
    );
    unmount();
    expect(vi.getTimerCount()).toBe(0);
    gate.resolve();
    await queuedExpectation;

    const strict = renderHook(
      () =>
        useOverviewRefresh({
          cadence: 1,
          now: () => nowMs,
          onRefresh: async () => {},
        }),
      { wrapper: StrictMode }
    );
    expect(vi.getTimerCount()).toBeLessThanOrEqual(1);
    strict.unmount();
  });
});
