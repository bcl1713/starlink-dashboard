import './overview-refresh-observer.mock';

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { OverviewPOIFilter } from '../../types/monitoring';
import type { OverviewRefreshCadence } from './preferences';
import { useOverviewData } from './useOverviewData';
import { useOverviewRefresh } from './useOverviewRefresh';
import { getOverviewRefreshObserver } from './overview-refresh-observer.mock';
import {
  cloneFixture,
  createCallCountingServices,
  deferred,
  flushOverviewEffects,
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
    [1, { selected: 30, active: 60, route: 12, gep: 1, history: 3 }],
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
    expect(svc.getMonitoringHistory).not.toHaveBeenCalled();

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

  it('uses Task8 manual identity for duplicate manual and queued-behind-scheduled refreshes', async () => {
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

  it('keeps the Task8 timer chain when callbacks change between ticks', async () => {
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
