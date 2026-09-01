import './overview-refresh-observer.mock';

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { OverviewPOIFilter } from '../../types/monitoring';
import type { OverviewRefreshCadence } from './preferences';
import { dueSlots, nextHistoryDueAt } from './overview-cycle-policy';
import type { OverviewHttpSlot } from './overview-sources';
import { useOverviewData } from './useOverviewData';
import { useOverviewRefresh } from './useOverviewRefresh';
import { getOverviewRefreshObserver } from './overview-refresh-observer.mock';
import {
  cloneFixture,
  createCallCountingServices,
  deferred,
  flushOverviewEffects,
  historyPayload,
  statusPayload,
} from './overview-test-harness';

const overviewRefreshObserver = getOverviewRefreshObserver();

describe('useOverviewData scheduling and anchors', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    overviewRefreshObserver.reset();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('uses an exact history slot relative to its last start, not an early allowance', () => {
    const anchors = new Map<OverviewHttpSlot, number>([['history', 0]]);

    expect(dueSlots('scheduled', 5, anchors, 4_949)).not.toContain('history');
    expect(dueSlots('scheduled', 5, anchors, 4_950)).not.toContain('history');
    expect(dueSlots('scheduled', 5, anchors, 4_951)).not.toContain('history');
    expect(dueSlots('scheduled', 5, anchors, 5_000)).toContain('history');
    expect(nextHistoryDueAt(5, anchors)).toBe(5_000);

    anchors.set('history', 5_019);
    expect(dueSlots('scheduled', 5, anchors, 10_001)).not.toContain('history');
    expect(nextHistoryDueAt(5, anchors)).toBe(10_019);
    anchors.set('history', 10_019);
    expect(nextHistoryDueAt(5, anchors)).toBe(15_019);
    expect(dueSlots('scheduled', 5, anchors, 15_038)).toContain('history');
  });

  it('schedules from a rounded post-dispatch monotonic history anchor without an early browser start', async () => {
    vi.setSystemTime(0);
    let synchronousSetupMs = 0;
    const historyStarts: number[] = [];
    const { svc } = createCallCountingServices({
      getMonitoringHistory: vi.fn(() => {
        historyStarts.push(Date.now());
        // Model synchronous fast/setup work between transport dispatch and the
        // scheduler's anchor capture, as observed in the browser trace.
        synchronousSetupMs = 2.809;
        queueMicrotask(() => {
          synchronousSetupMs = 0;
        });
        return Promise.resolve(cloneFixture(historyPayload));
      }),
    });
    const { unmount } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: Date.now,
        historyScheduleNow: () => Date.now() + synchronousSetupMs,
      })
    );
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([0]);
    expect(vi.getTimerCount()).toBe(1);

    // The transport started at 0, but its scheduling anchor must be captured
    // immediately afterwards and rounded upward from 2.809ms to 3ms. The next
    // real start therefore cannot be earlier than 5003ms after dispatch.
    await act(async () => vi.advanceTimersByTime(5_000));
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([0]);
    await act(async () => vi.advanceTimersByTime(3));
    await act(flushOverviewEffects);

    expect(historyStarts).toEqual([0, 5_003]);
    expect(historyStarts[1]! - historyStarts[0]!).toBeGreaterThanOrEqual(5_003);
    expect(vi.getTimerCount()).toBe(1);
    unmount();
  });

  it.each([
    [
      'throws',
      () => {
        throw new Error('monotonic clock unavailable');
      },
    ],
    ['returns NaN', () => Number.NaN],
    ['returns Infinity', () => Number.POSITIVE_INFINITY],
  ] as const)(
    'fails closed for an anchored history slot when its scheduler clock %s',
    async (_failure, invalidScheduleNow) => {
      for (const cadence of [1, 5] as const) {
        let scheduleNow = 0;
        let scheduleClock = () => scheduleNow;
        let listener = () => {};
        const { svc } = createCallCountingServices();
        const visibility = {
          isHidden: () => false,
          subscribe: vi.fn((callback: () => void) => {
            listener = callback;
            return vi.fn();
          }),
        };
        const { result, unmount } = renderHook(() =>
          useOverviewData({
            cadence,
            poiFilter: '',
            radarEnabled: true,
            services: svc,
            visibility,
            now: Date.now,
            historyScheduleNow: () => scheduleClock(),
          })
        );
        await act(flushOverviewEffects);
        expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(1);
        vi.clearAllMocks();

        // These requests happen after bootstrap has dispatched and captured its
        // history anchor. An unusable scheduler clock must omit only history;
        // visibility, manual, and ordinary fast-slot work still run.
        scheduleClock = invalidScheduleNow;
        await act(async () => listener());
        await act(flushOverviewEffects);
        await act(async () => result.current.controller.manualRefresh());
        await act(async () => vi.advanceTimersByTime(cadence * 1_000));
        await act(flushOverviewEffects);
        expect(svc.getStatus).toHaveBeenCalledTimes(2);
        expect(svc.getMonitoringHistory).not.toHaveBeenCalled();

        // Recovery remains fail-closed until the original monotonic deadline.
        scheduleClock = () => scheduleNow;
        scheduleNow = 4_999;
        await act(async () => listener());
        await act(flushOverviewEffects);
        expect(svc.getMonitoringHistory).not.toHaveBeenCalled();

        scheduleNow = 5_000;
        await act(async () => listener());
        await act(flushOverviewEffects);
        expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(1);
        unmount();
      }
    }
  );

  it('starts history without a scheduler clock when bootstrap has no anchor', () => {
    const anchors = new Map<OverviewHttpSlot, number>();

    expect(dueSlots('bootstrap', 1, anchors, 0, null)).toContain('history');
    expect(dueSlots('bootstrap', 5, anchors, 0, null)).toContain('history');
  });

  it('starts selected five-second history on its exact slot with one timer and shifts late work forward', async () => {
    let now = 5_019;
    const historyStarts: number[] = [];
    const { svc } = createCallCountingServices({
      getMonitoringHistory: vi.fn(() => {
        historyStarts.push(now);
        return Promise.resolve(cloneFixture(historyPayload));
      }),
    });
    const { unmount } = renderHook(() =>
      useOverviewData({
        cadence: 5,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => now,
      })
    );
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([5_019]);
    expect(vi.getTimerCount()).toBe(1);

    now = 10_001;
    await act(async () => vi.advanceTimersByTime(4_982));
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([5_019]);
    expect(vi.getTimerCount()).toBe(1);

    now = 10_019;
    await act(async () => vi.advanceTimersByTime(18));
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([5_019, 10_019]);
    expect(vi.getTimerCount()).toBe(1);

    // The timer is late by 19ms.  The contract is no early/overlapping catch-up:
    // start once at the observed time and make that start the next slot anchor.
    now = 15_038;
    await act(async () => vi.advanceTimersByTime(5_019));
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([5_019, 10_019, 15_038]);
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('uses the supplemental history deadline at cadence one without an early or extra start', async () => {
    let now = 5_019;
    const historyStarts: number[] = [];
    const { svc } = createCallCountingServices({
      getMonitoringHistory: vi.fn(() => {
        historyStarts.push(now);
        return Promise.resolve(cloneFixture(historyPayload));
      }),
    });
    const { unmount } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => now,
      })
    );
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([5_019]);
    expect(vi.getTimerCount()).toBe(1);

    // The ordinary global tick is late in this simulated clock, but it is
    // still before the history slot and cannot start history early.
    now = 10_001;
    await act(async () => vi.advanceTimersByTime(4_982));
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([5_019]);
    expect(vi.getTimerCount()).toBe(1);

    // The one timer must use the slot-relative supplemental deadline instead
    // of waiting for a subsequent global cadence tick.
    now = 10_019;
    await act(async () => vi.advanceTimersByTime(18));
    await act(flushOverviewEffects);
    expect(historyStarts).toEqual([5_019, 10_019]);
    expect(vi.getTimerCount()).toBe(1);
    unmount();
  });

  it('rejects an older same-millisecond history commit after its fast slots settle late', async () => {
    const now = 5_019;
    let historyScheduleNow = 0;
    const firstFastSlots = deferred<typeof statusPayload>();
    const older = {
      ...cloneFixture(historyPayload),
      generated_at: '2026-08-29T18:00:01Z',
    };
    const newer = {
      ...cloneFixture(historyPayload),
      generated_at: '2026-08-29T18:00:02Z',
    };
    const { svc } = createCallCountingServices({
      getStatus: vi
        .fn()
        .mockImplementationOnce(() => firstFastSlots.promise)
        .mockResolvedValue(cloneFixture(statusPayload)),
      getMonitoringHistory: vi
        .fn()
        .mockResolvedValueOnce(older)
        .mockResolvedValueOnce(newer),
    });
    const { result, unmount } = renderHook(() =>
      useOverviewData({
        cadence: 5,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => now,
        historyScheduleNow: () => historyScheduleNow,
      })
    );
    await act(flushOverviewEffects);
    expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(1);

    // The first transport has settled, but its delayed fast slots still hold
    // its commit. A due manual cycle starts attempt 2 at the same UI time.
    historyScheduleNow = 5_000;
    let manual!: Promise<void>;
    await act(() => {
      manual = result.current.controller.manualRefresh();
    });
    expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(2);

    // The shared fast request releases both cycles together.  Attempt 1 must
    // still be barred solely by its older token, despite sharing `now`.
    firstFastSlots.resolve(cloneFixture(statusPayload));
    await act(async () => manual);
    expect(result.current.snapshot.history.data?.generated_at).toBe(
      newer.generated_at
    );
    unmount();
  });

  it('bootstraps exactly ten HTTP calls with shared grouped signals and no radar HTTP', async () => {
    const { calls, svc } = createCallCountingServices();
    const { result, unmount } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: 'departure,arrival',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );

    expect(calls).toEqual([]);
    await act(flushOverviewEffects);

    expect(calls).toEqual([
      'status',
      'pois',
      'satellites',
      'missionEvents',
      'normal',
      'warning',
      'west',
      'east',
      'gep',
      'history',
    ]);
    const activeCalls = (svc.getActiveXLink as ReturnType<typeof vi.fn>).mock
      .calls;
    const routeCalls = (svc.getRouteCoordinates as ReturnType<typeof vi.fn>)
      .mock.calls;
    const historyArgs = (svc.getMonitoringHistory as ReturnType<typeof vi.fn>)
      .mock.calls[0][0];
    expect(svc.getStatus).toHaveBeenCalledWith(expect.any(AbortSignal));
    expect(svc.getPOIETAs).toHaveBeenCalledWith(
      'departure,arrival',
      expect.any(AbortSignal)
    );
    expect(svc.getSatelliteETAs).toHaveBeenCalledWith(expect.any(AbortSignal));
    expect(svc.getMissionEventETAs).toHaveBeenCalledWith(
      expect.any(AbortSignal)
    );
    expect(svc.getGroundEntryPoint).toHaveBeenCalledWith(
      expect.any(AbortSignal)
    );
    expect(historyArgs).toMatchObject({ rangeSeconds: 1800, stepSeconds: 1 });
    expect(historyArgs.signal).toBeInstanceOf(AbortSignal);
    expect(activeCalls[0]).toEqual(['normal', activeCalls[1][1]]);
    expect(activeCalls[1]).toEqual(['warning', activeCalls[0][1]]);
    expect(routeCalls[0]).toEqual(['west', routeCalls[1][1]]);
    expect(routeCalls[1]).toEqual(['east', routeCalls[0][1]]);
    expect(result.current.snapshot.initialState).toBe('ready');
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each([
    [1, { selected: 30, active: 60, route: 12, gep: 1, history: 6 }],
    [10, { selected: 3, active: 6, route: 6, gep: 1, history: 3 }],
    [30, { selected: 1, active: 2, route: 2, gep: 1, history: 1 }],
  ] as const)(
    'matches the 30s cadence table for %s seconds',
    async (cadence, expected) => {
      let now = 1_777_294_800_000;
      const { svc } = createCallCountingServices();
      renderHook(() =>
        useOverviewData({
          cadence,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        })
      );
      await act(flushOverviewEffects);
      vi.clearAllMocks();

      for (let second = 1; second <= 30; second += 1) {
        now += 1000;
        await act(async () => vi.advanceTimersByTime(1000));
        await act(flushOverviewEffects);
      }

      expect(svc.getStatus).toHaveBeenCalledTimes(expected.selected);
      expect(svc.getPOIETAs).toHaveBeenCalledTimes(expected.selected);
      expect(svc.getSatelliteETAs).toHaveBeenCalledTimes(expected.selected);
      expect(svc.getMissionEventETAs).toHaveBeenCalledTimes(expected.selected);
      expect(svc.getActiveXLink).toHaveBeenCalledTimes(expected.active);
      expect(svc.getRouteCoordinates).toHaveBeenCalledTimes(expected.route);
      expect(svc.getGroundEntryPoint).toHaveBeenCalledTimes(expected.gep);
      expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(expected.history);
    }
  );

  it('keeps fast slots on the 5s cadence while one history flight is deferred', async () => {
    let now = 1_777_294_800_000;
    const history = deferred<typeof historyPayload>();
    const { svc } = createCallCountingServices({
      getMonitoringHistory: vi.fn(() => history.promise),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 5,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => now,
      })
    );
    await act(flushOverviewEffects);
    expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(1);
    expect(result.current.snapshot.history.pending).toBe(true);
    vi.clearAllMocks();

    for (let second = 1; second <= 10; second += 1) {
      now += 1_000;
      await act(async () => vi.advanceTimersByTime(1_000));
      await act(flushOverviewEffects);
    }

    expect(svc.getStatus).toHaveBeenCalledTimes(2);
    expect(svc.getMonitoringHistory).not.toHaveBeenCalled();
    expect(result.current.snapshot.history.pending).toBe(true);
    history.resolve(cloneFixture(historyPayload));
    await act(flushOverviewEffects);
    expect(result.current.snapshot.history.pending).toBe(false);
  });

  it('honors first-five due counts and coalesces cadence reset to a full new period', async () => {
    let now = 1_777_294_800_000;
    const { svc } = createCallCountingServices();
    const { rerender } = renderHook(
      ({ cadence }) =>
        useOverviewData({
          cadence,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        }),
      { initialProps: { cadence: 1 as OverviewRefreshCadence } }
    );
    await act(flushOverviewEffects);
    vi.clearAllMocks();

    for (let second = 1; second <= 5; second += 1) {
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flushOverviewEffects);
    }

    expect(svc.getStatus).toHaveBeenCalledTimes(5);
    expect(svc.getPOIETAs).toHaveBeenCalledTimes(5);
    expect(svc.getActiveXLink).toHaveBeenCalledTimes(10);
    expect(svc.getRouteCoordinates).toHaveBeenCalledTimes(2);
    expect(svc.getGroundEntryPoint).not.toHaveBeenCalled();
    expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(1);

    rerender({ cadence: 10 as const });
    await act(flushOverviewEffects);
    vi.clearAllMocks();
    now += 9_000;
    await act(async () => vi.advanceTimersByTime(9_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).not.toHaveBeenCalled();
    now += 6_000;
    await act(async () => vi.advanceTimersByTime(6_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
    expect(svc.getRouteCoordinates).toHaveBeenCalledTimes(2);
  });

  it('keeps history on its monotonic cadence deadline after a divergent-clock cadence change', async () => {
    vi.setSystemTime(1_700_000_000_000);
    let historyScheduleNow = 2_000;
    const { svc } = createCallCountingServices();
    const { rerender, result, unmount } = renderHook(
      ({ cadence }) =>
        useOverviewData({
          cadence,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: Date.now,
          historyScheduleNow: () => historyScheduleNow,
        }),
      { initialProps: { cadence: 1 as OverviewRefreshCadence } }
    );
    await act(flushOverviewEffects);
    expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(1);
    vi.clearAllMocks();

    // A real control change resets ordinary HTTP anchors from wall time, but
    // history must retain a monotonic anchor and wait for its new deadline.
    rerender({ cadence: 5 as const });
    await act(flushOverviewEffects);
    historyScheduleNow = 6_999;
    await act(async () => vi.advanceTimersByTime(4_999));
    await act(flushOverviewEffects);
    expect(svc.getStatus).not.toHaveBeenCalled();
    expect(svc.getMonitoringHistory).not.toHaveBeenCalled();

    historyScheduleNow = 7_000;
    await act(async () => vi.advanceTimersByTime(1));
    await act(flushOverviewEffects);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
    expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(1);

    // An unavailable monotonic clock during a later cadence change cannot
    // replace the history anchor with Date.now() or make history immediately due.
    vi.clearAllMocks();
    historyScheduleNow = Number.NaN;
    rerender({ cadence: 10 as const });
    await act(flushOverviewEffects);
    await act(async () => result.current.controller.manualRefresh());
    expect(svc.getMonitoringHistory).not.toHaveBeenCalled();

    historyScheduleNow = 16_999;
    await act(async () => result.current.controller.manualRefresh());
    expect(svc.getMonitoringHistory).not.toHaveBeenCalled();
    historyScheduleNow = 17_000;
    await act(async () => result.current.controller.manualRefresh());
    expect(svc.getMonitoringHistory).toHaveBeenCalledTimes(1);
    unmount();
  });

  it('does not advance anchors while hidden or while reset time is invalid', async () => {
    let now = Number.NaN;
    let hidden = false;
    const { svc } = createCallCountingServices();
    const visibility = {
      isHidden: () => hidden,
      subscribe: vi.fn(() => vi.fn()),
    };
    const { rerender } = renderHook(
      ({ cadence }) =>
        useOverviewData({
          cadence,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          visibility,
          now: () => now,
        }),
      { initialProps: { cadence: 1 as OverviewRefreshCadence } }
    );
    await act(flushOverviewEffects);
    expect(svc.getStatus).not.toHaveBeenCalled();

    now = 1_777_294_800_000;
    rerender({ cadence: 10 as const });
    hidden = true;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).not.toHaveBeenCalled();
    hidden = false;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).not.toHaveBeenCalled();
    now += 10_000;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
  });

  it('anchors filter-immediate attempts before the next scheduled cadence', async () => {
    let now = 0;
    const { svc } = createCallCountingServices();
    const { rerender } = renderHook(
      ({ poiFilter }) =>
        useOverviewData({
          cadence: 1,
          poiFilter,
          radarEnabled: true,
          services: svc,
          now: () => now,
        }),
      { initialProps: { poiFilter: 'arrival' as OverviewPOIFilter } }
    );
    await act(flushOverviewEffects);
    now = 500;
    rerender({ poiFilter: 'departure' });
    await act(flushOverviewEffects);
    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    await act(flushOverviewEffects);
    expect(svc.getPOIETAs).toHaveBeenCalledTimes(2);
  });

  it('does not increment the radar token for bootstrap, scheduled, visibility, filter, cadence, or reports', async () => {
    let now = 1_777_294_800_000;
    let listener = () => {};
    const { svc } = createCallCountingServices();
    const visibility = {
      isHidden: () => false,
      subscribe: vi.fn((callback: () => void) => {
        listener = callback;
        return vi.fn();
      }),
    };
    const { result, rerender } = renderHook(
      ({ cadence, poiFilter }) =>
        useOverviewData({
          cadence,
          poiFilter,
          radarEnabled: true,
          services: svc,
          visibility,
          now: () => now,
        }),
      {
        initialProps: {
          cadence: 1 as OverviewRefreshCadence,
          poiFilter: 'arrival' as OverviewPOIFilter,
        },
      }
    );
    await act(flushOverviewEffects);
    expect(result.current.controller.radarRefreshToken).toBe(0);
    act(() =>
      result.current.controller.reportRadarResult(0, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    expect(result.current.controller.radarRefreshToken).toBe(0);
    now += 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    await act(flushOverviewEffects);
    act(listener);
    rerender({ cadence: 10, poiFilter: 'arrival' });
    await act(flushOverviewEffects);
    rerender({ cadence: 10, poiFilter: 'departure' });
    await act(flushOverviewEffects);
    expect(result.current.controller.radarRefreshToken).toBe(0);
  });

  it('manual refresh Promise identity', async () => {
    overviewRefreshObserver.enabled = true;
    let now = 1_777_294_800_000;
    const manualGate = deferred<typeof statusPayload>();
    const scheduledGate = deferred<typeof statusPayload>();
    const { svc } = createCallCountingServices();
    svc.getStatus = vi
      .fn()
      .mockResolvedValueOnce(cloneFixture(statusPayload))
      .mockImplementationOnce(() => manualGate.promise)
      .mockImplementationOnce(() => scheduledGate.promise)
      .mockResolvedValue(cloneFixture(statusPayload));
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => now,
      })
    );
    await act(flushOverviewEffects);
    const controllerManual = result.current.controller.manualRefresh;
    const activeManual = controllerManual();
    const duplicateActiveManual = controllerManual();
    expect(duplicateActiveManual).toBe(activeManual);
    manualGate.resolve(cloneFixture(statusPayload));
    await act(async () => activeManual);
    expect(result.current.controller.manualRefresh).toBe(controllerManual);

    now += 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    await act(flushOverviewEffects);
    const scheduled = overviewRefreshObserver.scheduled[0];
    expect(scheduled).toBeDefined();
    const queuedManual = result.current.controller.manualRefresh();
    const duplicateQueuedManual = result.current.controller.manualRefresh();
    expect(duplicateQueuedManual).toBe(queuedManual);
    expect(svc.getStatus).toHaveBeenCalledTimes(3);
    scheduledGate.resolve(cloneFixture(statusPayload));
    await act(async () => scheduled);
    await act(async () => queuedManual);
    expect(svc.getStatus).toHaveBeenCalledTimes(4);
    expect(overviewRefreshObserver.manual).toHaveLength(2);
  });

  it('scheduler timer-chain stability', async () => {
    let now = 0;
    const firstRefresh = vi.fn(() => Promise.resolve());
    const secondRefresh = vi.fn(() => Promise.resolve());
    const stableNow = () => now;
    const { rerender } = renderHook(
      ({ onRefresh }) =>
        useOverviewRefresh({
          cadence: 1,
          onRefresh,
          now: stableNow,
        }),
      { initialProps: { onRefresh: firstRefresh } }
    );

    now = 500;
    rerender({ onRefresh: secondRefresh });
    await act(async () => vi.advanceTimersByTime(499));
    await act(flushOverviewEffects);
    expect(firstRefresh).not.toHaveBeenCalled();
    expect(secondRefresh).not.toHaveBeenCalled();

    now = 1000;
    await act(async () => vi.advanceTimersByTime(501));
    await act(flushOverviewEffects);
    expect(firstRefresh).not.toHaveBeenCalled();
    expect(secondRefresh).toHaveBeenCalledTimes(1);
    expect(secondRefresh).toHaveBeenCalledWith('scheduled');
  });
});
