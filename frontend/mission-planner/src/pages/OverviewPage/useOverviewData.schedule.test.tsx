import { act, renderHook } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  ActiveXLink,
  GroundEntryPoint,
  MonitoringHistory,
  OverviewPOIFilter,
  OverviewStatus,
  POIETAResponse,
  RouteCoordinates,
} from '../../types/monitoring';
import {
  activeXLinkPayload,
  availableGep,
  historyPayload,
  poiPayload,
  routePayload,
  statusPayload,
} from '../../services/monitoring-test-fixtures';
import type { OverviewDataServices } from './overview-data-types';
import type { OverviewRefreshCadence } from './preferences';
import { useOverviewData } from './useOverviewData';

const flush = async () => {
  for (let count = 0; count < 8; count += 1) await Promise.resolve();
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function services() {
  const calls: string[] = [];
  const record = <T,>(name: string, value: T) =>
    vi.fn(() => {
      calls.push(name);
      return Promise.resolve(structuredClone(value));
    });
  const svc = {
    getStatus: record('status', statusPayload),
    getMonitoringHistory: record('history', historyPayload),
    getGroundEntryPoint: record('gep', availableGep),
    getPOIETAs: record('pois', poiPayload),
    getSatelliteETAs: record('satellites', poiPayload),
    getMissionEventETAs: record('missionEvents', poiPayload),
    getRouteCoordinates: vi.fn((direction) => {
      calls.push(direction);
      return Promise.resolve(structuredClone(routePayload));
    }),
    getActiveXLink: vi.fn((state) => {
      calls.push(state);
      return Promise.resolve({ ...structuredClone(activeXLinkPayload), state });
    }),
  } as unknown as OverviewDataServices;
  return { calls, svc };
}

describe('useOverviewData scheduling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('bootstraps exactly ten HTTP calls with shared grouped signals and no radar HTTP', async () => {
    const { calls, svc } = services();
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
    await act(flush);
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
    [1, { selected: 30, active: 60, route: 12, gep: 1, history: 3 }],
    [10, { selected: 3, active: 6, route: 6, gep: 1, history: 3 }],
    [30, { selected: 1, active: 2, route: 2, gep: 1, history: 1 }],
  ] as const)(
    'matches the 30s cadence table for %s seconds',
    async (cadence, expected) => {
      let now = 1_777_294_800_000;
      const { svc } = services();
      renderHook(() =>
        useOverviewData({
          cadence,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        })
      );
      await act(flush);
      vi.clearAllMocks();
      for (let second = 1; second <= 30; second += 1) {
        now += 1000;
        await act(async () => vi.advanceTimersByTime(1000));
        await act(flush);
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

  it('keeps one Task8 timer and one bootstrap under StrictMode', async () => {
    const { calls, svc } = services();
    const { unmount } = renderHook(
      () =>
        useOverviewData({
          cadence: 1,
          poiFilter: 'arrival',
          radarEnabled: true,
          services: svc,
          now: () => 1_777_294_800_000,
        }),
      { wrapper: StrictMode }
    );
    await act(flush);
    expect(calls).toHaveLength(10);
    expect(vi.getTimerCount()).toBeLessThanOrEqual(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('runs an explicit manual refresh hidden or paused and preserves controller identity', async () => {
    const { svc } = services();
    const visibility = {
      isHidden: () => true,
      subscribe: vi.fn(() => vi.fn()),
    };
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: 'waypoint' as OverviewPOIFilter,
        radarEnabled: false,
        services: svc,
        visibility,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flush);
    const manual = result.current.controller.manualRefresh;
    await act(async () => manual());
    expect(result.current.controller.manualRefresh).toBe(manual);
    expect(result.current.snapshot.manualResult).toBe('success');
    expect(svc.getStatus).toHaveBeenCalledTimes(2);
  });

  it.each([
    ['success', {}, 'success'],
    [
      'partial',
      {
        getStatus: vi.fn(() => Promise.reject(new Error('status failed'))),
      },
      'partial',
    ],
    [
      'failure',
      {
        getStatus: vi.fn(() => Promise.reject(new Error('status failed'))),
        getMonitoringHistory: vi.fn(() =>
          Promise.reject(new Error('history failed'))
        ),
        getGroundEntryPoint: vi.fn(() =>
          Promise.reject(new Error('gep failed'))
        ),
        getPOIETAs: vi.fn(() => Promise.reject(new Error('pois failed'))),
        getSatelliteETAs: vi.fn(() =>
          Promise.reject(new Error('satellites failed'))
        ),
        getMissionEventETAs: vi.fn(() =>
          Promise.reject(new Error('events failed'))
        ),
        getRouteCoordinates: vi.fn(() =>
          Promise.reject(new Error('route failed'))
        ),
        getActiveXLink: vi.fn(() => Promise.reject(new Error('link failed'))),
      },
      'failure',
    ],
  ] as const)(
    'resolves the manual promise only after the %s result is committed',
    async (_label, overrides, expected) => {
      const { svc } = services();
      Object.assign(svc, overrides);
      const { result } = renderHook(() =>
        useOverviewData({
          cadence: 'paused',
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => 1_777_294_800_000,
        })
      );
      await act(flush);
      let observed = 'unresolved';
      const manual = result.current.controller.manualRefresh().then(() => {
        observed = result.current.snapshot.manualResult;
      });
      await act(async () => manual);
      expect(observed).toBe(expected);
      expect(result.current.snapshot.manualResult).toBe(expected);
    }
  );

  it('does not emit flushSync warnings from effect, timer, or StrictMode paths', async () => {
    let now = 1_777_294_800_000;
    const { svc } = services();
    const testConsole = globalThis.console;
    const originalError = testConsole.error;
    const originalWarn = testConsole.warn;
    const observed: string[] = [];
    const capture = (...args: unknown[]) => {
      const text = args.map(String).join('\n');
      if (/flushSync|act\(|unmounted component/i.test(text))
        observed.push(text);
    };
    testConsole.error = capture;
    testConsole.warn = capture;
    try {
      const { result, unmount } = renderHook(
        () =>
          useOverviewData({
            cadence: 1,
            poiFilter: '',
            radarEnabled: true,
            services: svc,
            now: () => now,
          }),
        { wrapper: StrictMode }
      );
      await act(flush);
      await act(async () => result.current.controller.manualRefresh());
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flush);
      unmount();
      expect(observed).toEqual([]);
    } finally {
      testConsole.error = originalError;
      testConsole.warn = originalWarn;
    }
  });

  it('does not increment the radar token for bootstrap, scheduled, visibility, filter, cadence, or reports', async () => {
    let now = 1_777_294_800_000;
    let listener = () => {};
    const { svc } = services();
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
    await act(flush);
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
    await act(flush);
    act(listener);
    rerender({ cadence: 10, poiFilter: 'arrival' });
    await act(flush);
    rerender({ cadence: 10, poiFilter: 'departure' });
    await act(flush);
    expect(result.current.controller.radarRefreshToken).toBe(0);
  });

  it('honors first-five due counts and coalesces cadence reset to a full new period', async () => {
    let now = 1_777_294_800_000;
    const { svc } = services();
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
    await act(flush);
    vi.clearAllMocks();
    for (let second = 1; second <= 5; second += 1) {
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flush);
    }
    expect(svc.getStatus).toHaveBeenCalledTimes(5);
    expect(svc.getPOIETAs).toHaveBeenCalledTimes(5);
    expect(svc.getActiveXLink).toHaveBeenCalledTimes(10);
    expect(svc.getRouteCoordinates).toHaveBeenCalledTimes(2);
    expect(svc.getGroundEntryPoint).not.toHaveBeenCalled();
    expect(svc.getMonitoringHistory).not.toHaveBeenCalled();

    rerender({ cadence: 10 as const });
    await act(flush);
    vi.clearAllMocks();
    now += 9_000;
    await act(async () => vi.advanceTimersByTime(9_000));
    await act(flush);
    expect(svc.getStatus).not.toHaveBeenCalled();
    now += 6_000;
    await act(async () => vi.advanceTimersByTime(6_000));
    await act(flush);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
    expect(svc.getRouteCoordinates).toHaveBeenCalledTimes(2);
  });

  it('does not advance anchors while hidden or while reset time is invalid', async () => {
    let now = Number.NaN;
    let hidden = false;
    const { svc } = services();
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
    await act(flush);
    expect(svc.getStatus).not.toHaveBeenCalled();
    now = 1_777_294_800_000;
    rerender({ cadence: 10 as const });
    hidden = true;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flush);
    expect(svc.getStatus).not.toHaveBeenCalled();
    hidden = false;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flush);
    expect(svc.getStatus).not.toHaveBeenCalled();
    now += 10_000;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flush);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
  });

  it('keeps cadence reset pending while another cycle is active', async () => {
    let now = 1_777_294_800_000;
    const gate = deferred<typeof statusPayload>();
    const { svc } = services();
    svc.getStatus = vi.fn(() => gate.promise);
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
    await act(flush);
    rerender({ cadence: 10 as const });
    now += 10_000;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flush);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
    gate.resolve(structuredClone(statusPayload));
    await act(flush);
    vi.clearAllMocks();
    now += 9_000;
    await act(async () => vi.advanceTimersByTime(9_000));
    await act(flush);
    expect(svc.getStatus).not.toHaveBeenCalled();
  });

  it('keeps reset pending across overlapping manual and visibility cycles', async () => {
    let now = 1_777_294_800_000;
    let listener = () => {};
    const gate = deferred<typeof statusPayload>();
    const { svc } = services();
    svc.getStatus = vi
      .fn()
      .mockResolvedValueOnce(structuredClone(statusPayload))
      .mockImplementationOnce(() => gate.promise);
    const visibility = {
      isHidden: () => false,
      subscribe: vi.fn((callback: () => void) => {
        listener = callback;
        return vi.fn();
      }),
    };
    const { result, rerender } = renderHook(
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
    await act(flush);
    const manual = result.current.controller.manualRefresh();
    await act(flush);
    rerender({ cadence: 10 as const });
    act(listener);
    now += 10_000;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flush);
    expect(svc.getStatus).toHaveBeenCalledTimes(2);
    gate.resolve(structuredClone(statusPayload));
    await act(async () => manual);
    vi.clearAllMocks();
    now += 9_000;
    await act(async () => vi.advanceTimersByTime(9_000));
    await act(flush);
    expect(svc.getStatus).not.toHaveBeenCalled();
  });

  it('aborts all eight owned slot controllers on unmount', async () => {
    const signals: AbortSignal[] = [];
    const gates: ReturnType<typeof deferred<unknown>>[] = [];
    const never = <T,>(signal: AbortSignal): Promise<T> => {
      const gate = deferred<unknown>();
      signals.push(signal);
      gates.push(gate);
      return gate.promise as Promise<T>;
    };
    const svc = services().svc;
    svc.getStatus = vi.fn((signal) => never<OverviewStatus>(signal));
    svc.getPOIETAs = vi.fn((_filter, signal) => never<POIETAResponse>(signal));
    svc.getSatelliteETAs = vi.fn((signal) => never<POIETAResponse>(signal));
    svc.getMissionEventETAs = vi.fn((signal) => never<POIETAResponse>(signal));
    svc.getActiveXLink = vi.fn((_state, signal) => never<ActiveXLink>(signal));
    svc.getRouteCoordinates = vi.fn((_direction, signal) =>
      never<RouteCoordinates>(signal)
    );
    svc.getGroundEntryPoint = vi.fn((signal) =>
      never<GroundEntryPoint>(signal)
    );
    svc.getMonitoringHistory = vi.fn((args) =>
      never<MonitoringHistory>(args.signal)
    );
    const { unmount } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flush);
    unmount();
    for (const gate of gates) gate.reject(new Error('unmounted'));
    await act(flush);
    expect(signals).toHaveLength(10);
    expect(new Set(signals).size).toBe(8);
    expect(signals.every((signal) => signal.aborted)).toBe(true);
  });

  it('rejects a manual queued behind active scheduled work on unmount without warnings', async () => {
    let now = 1_777_294_800_000;
    const gate = deferred<typeof statusPayload>();
    const { svc } = services();
    svc.getStatus = vi
      .fn()
      .mockResolvedValueOnce(structuredClone(statusPayload))
      .mockImplementationOnce(() => gate.promise);
    const observed: string[] = [];
    const originalError = console.error;
    const originalWarn = console.warn;
    const capture = (...args: unknown[]) => {
      const text = args.map(String).join('\n');
      if (/act\(|unmounted component|flushSync/i.test(text))
        observed.push(text);
    };
    console.error = capture;
    console.warn = capture;
    const { result, unmount } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => now,
      })
    );
    try {
      await act(flush);
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flush);
      expect(svc.getStatus).toHaveBeenCalledTimes(2);
      expect(result.current.controller.isManualRefreshPending).toBe(false);
      const queued = result.current.controller.manualRefresh();
      await act(flush);
      expect(result.current.controller.isManualRefreshPending).toBe(true);
      expect(svc.getStatus).toHaveBeenCalledTimes(2);
      const activeScheduled = gate.promise.then(
        () => 'resolved',
        (error: unknown) => String((error as Error).message)
      );
      unmount();
      gate.reject(new Error('scheduled unmounted'));
      await expect(activeScheduled).resolves.toBe('scheduled unmounted');
      await expect(queued).rejects.toThrow(/unmounted/i);
      await expect(result.current.controller.manualRefresh()).rejects.toThrow(
        /unmounted/i
      );
      expect(observed).toEqual([]);
    } finally {
      console.error = originalError;
      console.warn = originalWarn;
    }
  });

  it('anchors filter-immediate attempts before the next scheduled cadence', async () => {
    let now = 0;
    const { svc } = services();
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
    await act(flush);
    now = 500;
    rerender({ poiFilter: 'departure' });
    await act(flush);
    now = 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    await act(flush);
    expect(svc.getPOIETAs).toHaveBeenCalledTimes(2);
  });

  it('manual and scheduled cycles follow selected POI replacements', async () => {
    let now = 1_777_294_800_000;
    const manualGate = deferred<typeof poiPayload>();
    const scheduledGate = deferred<typeof poiPayload>();
    const manualLatest = {
      ...structuredClone(poiPayload),
      timestamp: '2026-08-29T18:00:01Z',
    };
    const scheduledLatest = {
      ...structuredClone(poiPayload),
      timestamp: '2026-08-29T18:00:02Z',
    };
    const { svc } = services();
    svc.getPOIETAs = vi
      .fn()
      .mockResolvedValueOnce(structuredClone(poiPayload))
      .mockImplementationOnce((_filter, signal: AbortSignal) => {
        signal.addEventListener('abort', () =>
          manualGate.reject(new Error('manual stale'))
        );
        return manualGate.promise;
      })
      .mockResolvedValueOnce(manualLatest)
      .mockImplementationOnce((_filter, signal: AbortSignal) => {
        signal.addEventListener('abort', () =>
          scheduledGate.reject(new Error('scheduled stale'))
        );
        return scheduledGate.promise;
      })
      .mockResolvedValueOnce(scheduledLatest);
    const { result, rerender } = renderHook(
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
    await act(flush);

    const manual = result.current.controller.manualRefresh();
    await act(flush);
    rerender({ poiFilter: 'departure' });
    await act(async () => manual);
    expect(result.current.snapshot.manualResult).toBe('success');
    expect(result.current.snapshot.pois.data?.timestamp).toBe(
      '2026-08-29T18:00:01Z'
    );

    now += 1000;
    act(() => vi.advanceTimersByTime(1000));
    await act(flush);
    rerender({ poiFilter: 'waypoint' });
    await act(flush);
    expect(result.current.snapshot.pois.data?.timestamp).toBe(
      '2026-08-29T18:00:02Z'
    );
  });

  it('bootstrap follows a selected POI replacement before terminal commit', async () => {
    const first = deferred<typeof poiPayload>();
    const latest = {
      ...structuredClone(poiPayload),
      timestamp: '2026-08-29T18:00:03Z',
    };
    const { svc } = services();
    svc.getPOIETAs = vi
      .fn()
      .mockImplementationOnce((_filter, signal: AbortSignal) => {
        signal.addEventListener('abort', () =>
          first.reject(new Error('bootstrap stale'))
        );
        return first.promise;
      })
      .mockResolvedValueOnce(latest);
    const { result, rerender } = renderHook(
      ({ poiFilter }) =>
        useOverviewData({
          cadence: 'paused',
          poiFilter,
          radarEnabled: true,
          services: svc,
          now: () => 1_777_294_803_000,
        }),
      { initialProps: { poiFilter: 'arrival' as OverviewPOIFilter } }
    );
    await act(flush);
    expect(result.current.snapshot.initialState).toBe('initial-loading');
    rerender({ poiFilter: 'departure' });
    await act(flush);
    expect(result.current.snapshot.pois.data?.timestamp).toBe(
      '2026-08-29T18:00:03Z'
    );
    expect(result.current.snapshot.initialState).toBe('ready');
    expect(result.current.snapshot.manualResult).toBe('idle');
    expect(svc.getPOIETAs).toHaveBeenNthCalledWith(
      1,
      'arrival',
      expect.any(AbortSignal)
    );
    expect(svc.getPOIETAs).toHaveBeenNthCalledWith(
      2,
      'departure',
      expect.any(AbortSignal)
    );
  });
});
