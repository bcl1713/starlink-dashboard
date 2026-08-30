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
});
