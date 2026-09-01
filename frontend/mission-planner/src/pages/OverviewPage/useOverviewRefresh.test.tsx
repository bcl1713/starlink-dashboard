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

function throwingThenable(error: Error) {
  return {
    get then() {
      throw error;
    },
  };
}

function hostileThenCall(error: Error) {
  return {
    then() {
      throw error;
    },
  };
}

describe('useOverviewRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
  });

  afterEach(() => {
    vi.restoreAllMocks();
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

  it('schedules an earlier slot-relative deadline without adding a second timer', async () => {
    let now = 5_019;
    let historyDue = 10_019;
    const calls: OverviewRefreshReason[] = [];
    const onRefresh = vi.fn(async (reason: OverviewRefreshReason) => {
      calls.push(reason);
      historyDue += 5_000;
    });
    renderHook(() =>
      useOverviewRefresh({
        cadence: 5,
        now: () => now,
        nextScheduledAt: () => historyDue,
        onRefresh,
      })
    );

    expect(vi.getTimerCount()).toBe(1);
    now = 10_018;
    await act(async () => vi.advanceTimersByTime(4_999));
    expect(calls).toEqual([]);
    now = 10_019;
    await act(async () => vi.advanceTimersByTime(1));
    expect(calls).toEqual(['scheduled']);
    expect(vi.getTimerCount()).toBe(1);
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

  it('keeps the latest callback without replacing the active timer', async () => {
    let now = 0;
    const first = vi.fn(async () => {});
    const second = vi.fn(async () => {});
    const { rerender } = renderHook(
      ({ onRefresh }) =>
        useOverviewRefresh({ cadence: 1, now: () => now, onRefresh }),
      { initialProps: { onRefresh: first } }
    );

    expect(vi.getTimerCount()).toBe(1);
    rerender({ onRefresh: second });
    expect(vi.getTimerCount()).toBe(1);
    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledWith('scheduled');
  });

  it('uses Date.now when no clock provider is supplied', async () => {
    const dateNow = vi.spyOn(Date, 'now').mockReturnValue(250);
    const onRefresh = vi.fn(async () => {});
    renderHook(() => useOverviewRefresh({ cadence: 1, onRefresh }));

    expect(dateNow).toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(1);
    await act(async () => vi.advanceTimersByTime(749));
    expect(onRefresh).not.toHaveBeenCalled();
    dateNow.mockReturnValue(1000);
    await act(async () => vi.advanceTimersByTime(1));
    expect(onRefresh).toHaveBeenCalledWith('scheduled');
    dateNow.mockRestore();
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

  it('drops scheduled ticks while active and queues one manual after scheduled rejection', async () => {
    let now = 0;
    const gate = deferred();
    const calls: OverviewRefreshReason[] = [];
    const onRefresh = vi.fn((reason: OverviewRefreshReason) => {
      calls.push(reason);
      if (reason === 'scheduled') {
        return gate.promise;
      }
      return Promise.resolve();
    });
    const { result } = renderHook(() =>
      useOverviewRefresh({ cadence: 1, now: () => now, onRefresh })
    );

    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    expect(vi.getTimerCount()).toBe(1);
    now = 5000;
    await act(async () => vi.advanceTimersByTime(4000));
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(1);
    const queued = result.current.manualRefresh();
    gate.reject(new Error('scheduled failed'));
    await act(async () => expect(queued).resolves.toBeUndefined());
    expect(calls).toEqual(['scheduled', 'manual']);
  });

  it('keeps one timer through slow scheduled ticks and resumes next boundary after settlement', async () => {
    let now = 0;
    const gate = deferred();
    const calls: OverviewRefreshReason[] = [];
    const onRefresh = vi.fn((reason: OverviewRefreshReason) => {
      calls.push(reason);
      return reason === 'scheduled' && calls.length === 1
        ? gate.promise
        : Promise.resolve();
    });
    renderHook(() =>
      useOverviewRefresh({ cadence: 1, now: () => now, onRefresh })
    );

    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    expect(calls).toEqual(['scheduled']);
    expect(vi.getTimerCount()).toBe(1);
    for (let boundary = 2; boundary <= 5; boundary += 1) {
      now = boundary * 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      expect(calls).toEqual(['scheduled']);
      expect(vi.getTimerCount()).toBe(1);
    }

    gate.resolve();
    await act(async () => gate.promise);
    now = 6000;
    await act(async () => vi.advanceTimersByTime(1000));
    expect(calls).toEqual(['scheduled', 'scheduled']);
    expect(vi.getTimerCount()).toBe(1);
  });

  it('releases pending state after manual rejection and allows the next manual', async () => {
    const onRefresh = vi
      .fn()
      .mockRejectedValueOnce(new Error('manual failed'))
      .mockResolvedValueOnce(undefined);
    const { result } = renderHook(() =>
      useOverviewRefresh({ cadence: 'paused', onRefresh })
    );

    const first = result.current.manualRefresh();
    await act(async () =>
      expect(first).rejects.toEqual(Error('manual failed'))
    );
    expect(result.current.isManualRefreshPending).toBe(false);
    await act(async () => result.current.manualRefresh());
    expect(onRefresh).toHaveBeenCalledTimes(2);
  });

  it.each([
    [
      'sync throw',
      () => {
        throw new Error('sync manual');
      },
    ],
    ['then getter throw', () => throwingThenable(new Error('then getter'))],
    ['then call throw', () => hostileThenCall(new Error('then call'))],
  ])(
    'settles manual refresh after %s and preserves promise identity',
    async (_label, firstRefresh) => {
      const onRefresh = vi
        .fn()
        .mockImplementationOnce(firstRefresh as never)
        .mockResolvedValueOnce(undefined);
      const { result } = renderHook(() =>
        useOverviewRefresh({ cadence: 'paused', onRefresh })
      );

      let first!: Promise<void>;
      let same!: Promise<void>;
      let observed!: Promise<unknown>;
      await act(async () => {
        first = result.current.manualRefresh();
        observed = first.catch((error: Error) => error);
        same = result.current.manualRefresh();
      });

      expect(first).toBe(same);
      await act(async () => expect(observed).resolves.toBeInstanceOf(Error));
      expect(result.current.isManualRefreshPending).toBe(false);
      await act(async () =>
        expect(result.current.manualRefresh()).resolves.toBeUndefined()
      );
      expect(onRefresh).toHaveBeenCalledTimes(2);
    }
  );

  it.each([
    [
      'sync throw',
      () => {
        throw new Error('sync scheduled');
      },
    ],
    ['then getter throw', () => throwingThenable(new Error('then getter'))],
    ['then call throw', () => hostileThenCall(new Error('then call'))],
  ])('recovers scheduled refresh after %s', async (_label, firstRefresh) => {
    let now = 0;
    const onRefresh = vi
      .fn()
      .mockImplementationOnce(firstRefresh as never)
      .mockResolvedValueOnce(undefined);
    renderHook(() =>
      useOverviewRefresh({ cadence: 1, now: () => now, onRefresh })
    );

    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    await act(async () => Promise.resolve());
    expect(vi.getTimerCount()).toBe(1);

    now = 2000;
    await act(async () => vi.advanceTimersByTime(1000));
    expect(onRefresh).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(1);
  });

  it.each([
    [
      'throwing',
      () => {
        throw new Error('now failed');
      },
    ],
    ['NaN', () => Number.NaN],
    ['positive infinity', () => Number.POSITIVE_INFINITY],
    ['negative infinity', () => Number.NEGATIVE_INFINITY],
  ])(
    'does not schedule timers for %s refresh providers',
    async (_label, now) => {
      const onRefresh = vi.fn(async () => {});
      const { rerender } = renderHook(
        ({ now: provider }) =>
          useOverviewRefresh({ cadence: 1, now: provider, onRefresh }),
        { initialProps: { now } }
      );

      expect(vi.getTimerCount()).toBe(0);
      await act(async () => vi.advanceTimersByTime(5000));
      expect(onRefresh).not.toHaveBeenCalled();

      rerender({ now: () => 250 });
      expect(vi.getTimerCount()).toBe(1);
      await act(async () => vi.advanceTimersByTime(750));
      expect(onRefresh).toHaveBeenCalledWith('scheduled');
    }
  );

  it('normalizes negative epoch boundaries for refresh scheduling', async () => {
    const now = -1000;
    const onRefresh = vi.fn(async () => {});
    renderHook(() =>
      useOverviewRefresh({ cadence: 1, now: () => now, onRefresh })
    );

    await act(async () => vi.advanceTimersByTime(999));
    expect(onRefresh).not.toHaveBeenCalled();
    await act(async () => vi.advanceTimersByTime(1));
    expect(onRefresh).toHaveBeenCalledTimes(1);
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

  it('replaces cadence timers while scheduled work is unresolved', async () => {
    let now = 0;
    const gate = deferred();
    const calls: OverviewRefreshReason[] = [];
    const onRefresh = vi.fn((reason: OverviewRefreshReason) => {
      calls.push(reason);
      return reason === 'scheduled' && calls.length === 1
        ? gate.promise
        : Promise.resolve();
    });
    const { rerender } = renderHook(
      ({ cadence }) =>
        useOverviewRefresh({ cadence, now: () => now, onRefresh }),
      { initialProps: { cadence: 1 as OverviewRefreshCadence } }
    );

    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    expect(calls).toEqual(['scheduled']);
    expect(vi.getTimerCount()).toBe(1);
    rerender({ cadence: 5 });
    expect(vi.getTimerCount()).toBe(1);
    now = 5000;
    await act(async () => vi.advanceTimersByTime(4000));
    expect(calls).toEqual(['scheduled']);
    expect(vi.getTimerCount()).toBe(1);
    gate.resolve();
    await act(async () => gate.promise);
    now = 10000;
    await act(async () => vi.advanceTimersByTime(5000));
    expect(calls).toEqual(['scheduled', 'scheduled']);
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
      () => {
        useOverviewClock(() => new Date(nowMs));
        return useOverviewRefresh({
          cadence: 1,
          now: () => nowMs,
          onRefresh: async () => {},
        });
      },
      { wrapper: StrictMode }
    );
    expect(vi.getTimerCount()).toBe(2);
    strict.unmount();
    expect(vi.getTimerCount()).toBe(0);

    const refreshOnly = renderHook(
      () =>
        useOverviewRefresh({
          cadence: 1,
          now: () => nowMs,
          onRefresh: async () => {},
        }),
      { wrapper: StrictMode }
    );
    expect(vi.getTimerCount()).toBeLessThanOrEqual(1);
    refreshOnly.unmount();
  });
});
