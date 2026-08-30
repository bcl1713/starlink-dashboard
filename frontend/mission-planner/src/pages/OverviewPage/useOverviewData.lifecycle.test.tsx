import './overview-refresh-observer.mock';

import { act, render, renderHook } from '@testing-library/react';
import { StrictMode, useEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { OverviewStatus } from '../../types/monitoring';
import type { OverviewRefreshCadence } from './preferences';
import { useOverviewData } from './useOverviewData';
import { getOverviewRefreshObserver } from './overview-refresh-observer.mock';
import {
  captureReactWarnings,
  cloneFixture,
  createCallCountingServices,
  createDeferredSlotServices,
  createOverviewServices,
  deferred,
  flushOverviewEffects,
  statusPayload,
} from './overview-test-harness';

const overviewRefreshObserver = getOverviewRefreshObserver();

describe('useOverviewData lifecycle and service replacement', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    overviewRefreshObserver.reset();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('one shared refresh timer and one bootstrap under StrictMode', async () => {
    const { calls, svc } = createCallCountingServices();
    const announcements: string[] = [];
    function Probe() {
      const { snapshot } = useOverviewData({
        cadence: 1,
        poiFilter: 'arrival',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      });
      useEffect(() => {
        if (snapshot.announcement) {
          announcements.push(
            `${snapshot.initialState}:${snapshot.announcement}`
          );
        }
      }, [snapshot]);
      return null;
    }

    const { unmount } = render(
      <StrictMode>
        <Probe />
      </StrictMode>
    );
    await act(flushOverviewEffects);

    expect(calls).toHaveLength(10);
    expect(announcements).toEqual(['ready:Overview ready.']);
    expect(vi.getTimerCount()).toBeLessThanOrEqual(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('does not bootstrap or commit after an ordinary mount unmounts before the bootstrap microtask', async () => {
    const { calls, svc } = createCallCountingServices();
    const observedSnapshots: string[] = [];
    const observedAnnouncements: string[] = [];

    function Probe() {
      const { snapshot } = useOverviewData({
        cadence: 1,
        poiFilter: 'arrival',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      });
      useEffect(() => {
        if (
          snapshot.initialState !== 'initial-loading' ||
          snapshot.announcement !== null ||
          snapshot.globalTransportLastSuccessAt !== null ||
          snapshot.telemetry.pending ||
          snapshot.history.pending ||
          snapshot.pois.pending
        ) {
          observedSnapshots.push(snapshot.initialState);
        }
        if (snapshot.announcement) {
          observedAnnouncements.push(snapshot.announcement);
        }
      }, [snapshot]);
      return null;
    }

    const { unmount } = render(<Probe />);
    unmount();
    await act(flushOverviewEffects);

    expect(calls).toEqual([]);
    expect(svc.getStatus).not.toHaveBeenCalled();
    expect(svc.getMonitoringHistory).not.toHaveBeenCalled();
    expect(svc.getGroundEntryPoint).not.toHaveBeenCalled();
    expect(svc.getPOIETAs).not.toHaveBeenCalled();
    expect(svc.getSatelliteETAs).not.toHaveBeenCalled();
    expect(svc.getMissionEventETAs).not.toHaveBeenCalled();
    expect(svc.getRouteCoordinates).not.toHaveBeenCalled();
    expect(svc.getActiveXLink).not.toHaveBeenCalled();
    expect(observedSnapshots).toEqual([]);
    expect(observedAnnouncements).toEqual([]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('bootstraps the latest ordinary mount with exactly ten calls', async () => {
    const { calls, svc } = createCallCountingServices();
    const { unmount } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: 'arrival',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );

    await act(flushOverviewEffects);
    expect(calls).toHaveLength(10);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('keeps cadence reset pending while another cycle is active', async () => {
    let now = 1_777_294_800_000;
    const gate = deferred<typeof statusPayload>();
    const { svc } = createCallCountingServices();
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
    await act(flushOverviewEffects);
    rerender({ cadence: 10 as const });
    now += 10_000;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
    gate.resolve(cloneFixture(statusPayload));
    await act(flushOverviewEffects);
    vi.clearAllMocks();
    now += 9_000;
    await act(async () => vi.advanceTimersByTime(9_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).not.toHaveBeenCalled();
  });

  it('keeps reset pending across overlapping manual and visibility cycles', async () => {
    let now = 1_777_294_800_000;
    let listener = () => {};
    const gate = deferred<typeof statusPayload>();
    const { svc } = createCallCountingServices();
    svc.getStatus = vi
      .fn()
      .mockResolvedValueOnce(cloneFixture(statusPayload))
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
    await act(flushOverviewEffects);
    const manual = result.current.controller.manualRefresh();
    await act(flushOverviewEffects);
    rerender({ cadence: 10 as const });
    act(listener);
    now += 10_000;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).toHaveBeenCalledTimes(2);
    gate.resolve(cloneFixture(statusPayload));
    await act(async () => manual);
    vi.clearAllMocks();
    now += 9_000;
    await act(async () => vi.advanceTimersByTime(9_000));
    await act(flushOverviewEffects);
    expect(svc.getStatus).not.toHaveBeenCalled();
  });

  it('aborts all eight owned slot controllers on unmount', async () => {
    const { gates, signals, svc } = createDeferredSlotServices();
    const { unmount } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );

    await act(flushOverviewEffects);
    unmount();
    for (const gate of gates) {
      gate.reject(new Error('unmounted'));
    }
    await act(flushOverviewEffects);
    expect(signals).toHaveLength(10);
    expect(new Set(signals).size).toBe(8);
    expect(signals.every((signal) => signal.aborted)).toBe(true);
  });

  it('rejects a manual queued behind active scheduled work on unmount without warnings', async () => {
    overviewRefreshObserver.enabled = true;
    let now = 1_777_294_800_000;
    const gate = deferred<typeof statusPayload>();
    const { svc } = createCallCountingServices();
    svc.getStatus = vi
      .fn()
      .mockResolvedValueOnce(cloneFixture(statusPayload))
      .mockImplementationOnce(() => gate.promise);
    const warnings = captureReactWarnings();
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
      await act(flushOverviewEffects);
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flushOverviewEffects);
      expect(svc.getStatus).toHaveBeenCalledTimes(2);
      expect(overviewRefreshObserver.scheduled).toHaveLength(1);
      expect(result.current.controller.isManualRefreshPending).toBe(false);
      const queued = result.current.controller.manualRefresh();
      await act(flushOverviewEffects);
      expect(result.current.controller.isManualRefreshPending).toBe(true);
      expect(svc.getStatus).toHaveBeenCalledTimes(2);
      const scheduledRunCycle = overviewRefreshObserver.scheduled[0];
      const activeScheduled = scheduledRunCycle.then(
        () => 'resolved',
        (error: unknown) => String((error as Error).message)
      );
      expect(overviewRefreshObserver.scheduled[0]).toBe(scheduledRunCycle);
      unmount();
      gate.reject(new Error('Overview refresh unmounted'));
      await expect(scheduledRunCycle).resolves.toBeUndefined();
      await expect(activeScheduled).resolves.toBe('resolved');
      await expect(queued).rejects.toMatchObject({
        message: 'Overview refresh unmounted',
      });
      await expect(
        result.current.controller.manualRefresh()
      ).rejects.toMatchObject({ message: 'Overview refresh unmounted' });
      expect(warnings.observed).toEqual([]);
    } finally {
      warnings.restore();
    }
  });

  it('ignores abort-ignoring old lifecycle results after service replacement', async () => {
    const oldStatus = deferred<typeof statusPayload>();
    const oldServices = createOverviewServices({
      getStatus: vi.fn(() => oldStatus.promise),
    });
    const newServices = createOverviewServices({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...cloneFixture(statusPayload),
          timestamp: '2026-08-29T18:00:10Z',
        })
      ),
    });
    const { result, rerender } = renderHook(
      ({ svc }) =>
        useOverviewData({
          cadence: 'paused',
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => 1_777_294_810_000,
        }),
      { initialProps: { svc: oldServices } }
    );
    await act(flushOverviewEffects);
    rerender({ svc: newServices });
    await act(flushOverviewEffects);
    expect(result.current.snapshot.telemetry.data?.timestamp).toBe(
      '2026-08-29T18:00:10Z'
    );
    const before = result.current.snapshot;
    oldStatus.resolve({
      ...cloneFixture(statusPayload),
      timestamp: '2026-08-29T18:00:01Z',
    });
    await act(flushOverviewEffects);
    expect(result.current.snapshot).toBe(before);
    expect(result.current.snapshot.globalTransportLastSuccessAt).toBe(
      1_777_294_810_000
    );
  });

  it('settles obsolete scheduled cycles and lets the new lifecycle reset cadence', async () => {
    overviewRefreshObserver.enabled = true;
    let now = 1_777_294_800_000;
    const oldStatus = deferred<typeof statusPayload>();
    const old = createOverviewServices();
    old.getStatus = vi
      .fn()
      .mockResolvedValueOnce(cloneFixture(statusPayload))
      .mockImplementationOnce(() => oldStatus.promise);
    const fresh = createOverviewServices();
    fresh.getStatus = vi.fn(() =>
      Promise.resolve({
        ...cloneFixture(statusPayload),
        timestamp: '2026-08-29T18:00:10Z',
      } as OverviewStatus)
    );
    const { result, rerender } = renderHook(
      ({ svc, cadence }) =>
        useOverviewData({
          cadence,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        }),
      {
        initialProps: {
          svc: old,
          cadence: 1 as OverviewRefreshCadence,
        },
      }
    );
    await act(flushOverviewEffects);
    now += 1000;
    await act(async () => vi.advanceTimersByTime(1000));
    await act(flushOverviewEffects);
    const obsoleteScheduled = overviewRefreshObserver.scheduled.at(-1);
    expect(obsoleteScheduled).toBeDefined();

    rerender({ svc: fresh, cadence: 1 });
    await act(flushOverviewEffects);
    await expect(obsoleteScheduled).resolves.toBeUndefined();
    expect(result.current.snapshot.telemetry.data?.timestamp).toBe(
      '2026-08-29T18:00:10Z'
    );

    rerender({ svc: fresh, cadence: 10 });
    await act(flushOverviewEffects);
    vi.clearAllMocks();
    now += 9_000;
    await act(async () => vi.advanceTimersByTime(9_000));
    await act(flushOverviewEffects);
    expect(fresh.getStatus).not.toHaveBeenCalled();
    now += 1_000;
    await act(async () => vi.advanceTimersByTime(1_000));
    await act(flushOverviewEffects);
    expect(fresh.getStatus).not.toHaveBeenCalled();
    now += 10_000;
    await act(async () => vi.advanceTimersByTime(10_000));
    await act(flushOverviewEffects);
    expect(fresh.getStatus).toHaveBeenCalledTimes(1);
    oldStatus.reject(new Error('late old failure'));
    await act(flushOverviewEffects);
    expect(result.current.snapshot.telemetry.data?.timestamp).toBe(
      '2026-08-29T18:00:10Z'
    );
  });

  it('settles obsolete manual cycles while the replacement lifecycle proceeds', async () => {
    const oldStatus = deferred<typeof statusPayload>();
    const old = createOverviewServices();
    old.getStatus = vi
      .fn()
      .mockResolvedValueOnce(cloneFixture(statusPayload))
      .mockImplementationOnce(() => oldStatus.promise);
    const fresh = createOverviewServices();
    fresh.getStatus = vi.fn(() =>
      Promise.resolve({
        ...cloneFixture(statusPayload),
        timestamp: '2026-08-29T18:00:11Z',
      } as OverviewStatus)
    );
    const { result, rerender } = renderHook(
      ({ svc }) =>
        useOverviewData({
          cadence: 'paused',
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => 1_777_294_811_000,
        }),
      { initialProps: { svc: old } }
    );
    await act(flushOverviewEffects);
    const manual = result.current.controller.manualRefresh();
    await act(flushOverviewEffects);
    expect(result.current.controller.isManualRefreshPending).toBe(true);
    rerender({ svc: fresh });
    await act(flushOverviewEffects);
    await expect(manual).resolves.toBeUndefined();
    expect(result.current.snapshot.manualResult).toBe('idle');
    expect(result.current.snapshot.telemetry.data?.timestamp).toBe(
      '2026-08-29T18:00:11Z'
    );
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.manualResult).toBe('success');
    oldStatus.resolve({
      ...cloneFixture(statusPayload),
      timestamp: '2026-08-29T18:00:01Z',
    });
    await act(flushOverviewEffects);
    expect(result.current.snapshot.telemetry.data?.timestamp).toBe(
      '2026-08-29T18:00:11Z'
    );
  });
});
