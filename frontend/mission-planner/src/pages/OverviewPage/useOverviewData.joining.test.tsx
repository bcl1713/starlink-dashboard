import { act, renderHook } from '@testing-library/react';
import axios from 'axios';
import { describe, expect, it, vi } from 'vitest';

import type { OverviewPOIFilter } from '../../types/monitoring';
import { useOverviewData } from './useOverviewData';
import {
  activeXLinkPayload,
  cloneFixture,
  createOverviewServices,
  deferred,
  flushOverviewEffects,
  poiPayload,
  routePayload,
} from './overview-test-harness';

describe('useOverviewData request joining and replacement', () => {
  it('manual and scheduled cycles follow selected POI replacements', async () => {
    vi.useFakeTimers();
    try {
      let now = 1_777_294_800_000;
      const manualGate = deferred<typeof poiPayload>();
      const scheduledGate = deferred<typeof poiPayload>();
      const manualLatest = {
        ...cloneFixture(poiPayload),
        timestamp: '2026-08-29T18:00:01Z',
      };
      const scheduledLatest = {
        ...cloneFixture(poiPayload),
        timestamp: '2026-08-29T18:00:02Z',
      };
      const svc = createOverviewServices();
      svc.getPOIETAs = vi
        .fn()
        .mockResolvedValueOnce(cloneFixture(poiPayload))
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
      await act(flushOverviewEffects);

      const manual = result.current.controller.manualRefresh();
      await act(flushOverviewEffects);
      rerender({ poiFilter: 'departure' });
      await act(async () => manual);
      expect(result.current.snapshot.manualResult).toBe('success');
      expect(result.current.snapshot.pois.data?.timestamp).toBe(
        '2026-08-29T18:00:01Z'
      );

      now += 1000;
      act(() => vi.advanceTimersByTime(1000));
      await act(flushOverviewEffects);
      rerender({ poiFilter: 'waypoint' });
      await act(flushOverviewEffects);
      expect(result.current.snapshot.pois.data?.timestamp).toBe(
        '2026-08-29T18:00:02Z'
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it('bootstrap follows a selected POI replacement before terminal commit', async () => {
    const first = deferred<typeof poiPayload>();
    const latest = {
      ...cloneFixture(poiPayload),
      timestamp: '2026-08-29T18:00:03Z',
    };
    const svc = createOverviewServices();
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
    await act(flushOverviewEffects);
    expect(result.current.snapshot.initialState).toBe('initial-loading');
    rerender({ poiFilter: 'departure' });
    await act(flushOverviewEffects);
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

  it('replaces only the selected POI filter and commits the latest generation', async () => {
    const first = deferred<typeof poiPayload>();
    const latest = {
      ...cloneFixture(poiPayload),
      timestamp: '2026-08-29T18:00:01Z',
    };
    const svc = createOverviewServices({
      getPOIETAs: vi
        .fn()
        .mockResolvedValueOnce(cloneFixture(poiPayload))
        .mockImplementationOnce((_filter, signal: AbortSignal) => {
          signal.addEventListener('abort', () =>
            first.reject(new axios.CanceledError('stale'))
          );
          return first.promise;
        })
        .mockResolvedValueOnce(latest),
    });
    const { result, rerender } = renderHook(
      ({ poiFilter }) =>
        useOverviewData({
          cadence: 'paused',
          poiFilter,
          radarEnabled: true,
          services: svc,
          now: () => 1_777_294_801_000,
        }),
      { initialProps: { poiFilter: 'arrival' as OverviewPOIFilter } }
    );
    await act(flushOverviewEffects);
    rerender({ poiFilter: 'waypoint' });
    rerender({ poiFilter: 'departure' });
    await act(flushOverviewEffects);
    expect(result.current.snapshot.pois.data?.timestamp).toBe(
      '2026-08-29T18:00:01Z'
    );
    expect(svc.getSatelliteETAs).toHaveBeenCalledTimes(1);
    expect(svc.getMissionEventETAs).toHaveBeenCalledTimes(1);
  });

  it('keeps grouped pair data atomic when one member fails', async () => {
    const svc = createOverviewServices({
      getActiveXLink: vi
        .fn()
        .mockResolvedValueOnce({
          ...cloneFixture(activeXLinkPayload),
          state: 'normal',
        })
        .mockResolvedValueOnce({
          ...cloneFixture(activeXLinkPayload),
          state: 'warning',
        })
        .mockResolvedValueOnce({
          ...cloneFixture(activeXLinkPayload),
          state: 'normal',
          observed_at: '2026-08-29T18:00:01Z',
        })
        .mockRejectedValueOnce(new Error('warning failed')),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_801_000,
      })
    );
    await act(flushOverviewEffects);
    const previous = result.current.snapshot.activeLink.data;
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.activeLink.data).toEqual(previous);
    expect(result.current.snapshot.activeLink.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
  });

  it('commits grouped active link and route pairs atomically without mixed generations', async () => {
    const routeGate = deferred<typeof routePayload>();
    const services = createOverviewServices({
      getRouteCoordinates: vi.fn((direction) =>
        direction === 'west'
          ? Promise.resolve({
              ...cloneFixture(routePayload),
              route_id: 'old',
            })
          : routeGate.promise
      ),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flushOverviewEffects);
    expect(result.current.snapshot.route.data).toBeUndefined();
    routeGate.resolve({ ...cloneFixture(routePayload), route_id: 'new' });
    await act(async () => routeGate.promise);
    expect(result.current.snapshot.route.data?.west.route_id).toBe('old');
    expect(result.current.snapshot.route.data?.east.route_id).toBe('new');
  });
});
