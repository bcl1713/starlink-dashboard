import { act, renderHook } from '@testing-library/react';
import axios from 'axios';
import { describe, expect, it, vi } from 'vitest';

import {
  activeXLinkPayload,
  availableGep,
  historyPayload,
  poiPayload,
  routePayload,
  statusPayload,
  unavailableGep,
} from '../../services/monitoring-test-fixtures';
import type { OverviewPOIFilter } from '../../types/monitoring';
import type { OverviewDataServices } from './overview-data-types';
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

function services(overrides: Partial<OverviewDataServices> = {}) {
  return {
    getStatus: vi.fn(() => Promise.resolve(structuredClone(statusPayload))),
    getMonitoringHistory: vi.fn(() =>
      Promise.resolve(structuredClone(historyPayload))
    ),
    getGroundEntryPoint: vi.fn(() =>
      Promise.resolve(structuredClone(availableGep))
    ),
    getPOIETAs: vi.fn(() => Promise.resolve(structuredClone(poiPayload))),
    getSatelliteETAs: vi.fn(() => Promise.resolve(structuredClone(poiPayload))),
    getMissionEventETAs: vi.fn(() =>
      Promise.resolve(structuredClone(poiPayload))
    ),
    getRouteCoordinates: vi.fn(() =>
      Promise.resolve(structuredClone(routePayload))
    ),
    getActiveXLink: vi.fn(() =>
      Promise.resolve(structuredClone(activeXLinkPayload))
    ),
    ...overrides,
  } as unknown as OverviewDataServices;
}

describe('useOverviewData resilience', () => {
  it('treats independent failures, semantic unavailable, and manual results separately', async () => {
    const svc = services({
      getPOIETAs: vi.fn(() => Promise.reject(new Error('poi failed'))),
      getGroundEntryPoint: vi.fn(() =>
        Promise.resolve(structuredClone(unavailableGep))
      ),
    });
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
    expect(result.current.snapshot.initialState).toBe('partial-error');
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.manualResult).toBe('partial');
    expect(result.current.snapshot.pois.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    expect(result.current.snapshot.groundEntryPoint.phase).toBe('unavailable');
    expect(result.current.snapshot.globalTransportLastSuccessAt).toBe(
      1_777_294_800_000
    );
  });

  it('keeps cancellation neutral and suppresses late commits after unmount', async () => {
    const cancel = new axios.CanceledError('stop');
    const svc = services({
      getStatus: vi.fn(() => Promise.reject(cancel)),
    });
    const { result, unmount } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flush);
    expect(result.current.snapshot.telemetry.error).toBeNull();
    unmount();
    await expect(result.current.controller.manualRefresh()).rejects.toThrow(
      /unmounted/i
    );
  });

  it('handles radar reports without HTTP, retains data while disabled, and ignores invalid now', async () => {
    let now = 1_777_294_800_000;
    const svc = services();
    const { result, rerender } = renderHook(
      ({ radarEnabled }) =>
        useOverviewData({
          cadence: 'paused',
          poiFilter: '',
          radarEnabled,
          services: svc,
          now: () => now,
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flush);
    act(() =>
      result.current.controller.reportRadarResult({
        ok: true,
        frameTimestamp: '1788004800',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1788004800'
    );
    expect(result.current.snapshot.radar.sourceTimestamp).toBe('1788004800');
    expect(result.current.snapshot.radar.transportLastSuccessAt).toBe(now);
    now = Number.NaN;
    act(() =>
      result.current.controller.reportRadarResult({
        ok: false,
        error: new Error('radar failed'),
      })
    );
    expect(result.current.snapshot.radar.error).toBeNull();
    rerender({ radarEnabled: false });
    await act(flush);
    act(() =>
      result.current.controller.reportRadarResult({
        ok: false,
        error: new Error('radar failed'),
      })
    );
    expect(result.current.snapshot.radar.phase).toBe('unavailable');
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1788004800'
    );
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
  });

  it('emits exact priority announcements with deduplication', async () => {
    const svc = services({
      getStatus: vi
        .fn()
        .mockRejectedValueOnce(new Error('down'))
        .mockResolvedValueOnce(structuredClone(statusPayload)),
    });
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
    expect(result.current.snapshot.announcement).toBe(
      'Telemetry refresh failed.'
    );
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.announcement).toBe(
      'Manual refresh complete.'
    );
  });

  it('replaces only the selected POI filter and commits the latest generation', async () => {
    const first = deferred<typeof poiPayload>();
    const latest = {
      ...structuredClone(poiPayload),
      timestamp: '2026-08-29T18:00:01Z',
    };
    const svc = services({
      getPOIETAs: vi
        .fn()
        .mockResolvedValueOnce(structuredClone(poiPayload))
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
    await act(flush);
    rerender({ poiFilter: 'waypoint' });
    rerender({ poiFilter: 'departure' });
    await act(flush);
    expect(result.current.snapshot.pois.data?.timestamp).toBe(
      '2026-08-29T18:00:01Z'
    );
    expect(svc.getSatelliteETAs).toHaveBeenCalledTimes(1);
    expect(svc.getMissionEventETAs).toHaveBeenCalledTimes(1);
  });

  it('keeps grouped pair data atomic when one member fails', async () => {
    const svc = services({
      getActiveXLink: vi
        .fn()
        .mockResolvedValueOnce({
          ...structuredClone(activeXLinkPayload),
          state: 'normal',
        })
        .mockResolvedValueOnce({
          ...structuredClone(activeXLinkPayload),
          state: 'warning',
        })
        .mockResolvedValueOnce({
          ...structuredClone(activeXLinkPayload),
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
    await act(flush);
    const previous = result.current.snapshot.activeLink.data;
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.activeLink.data).toEqual(previous);
    expect(result.current.snapshot.activeLink.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
  });

  it('fails open for hostile visibility and swallows cleanup failures', async () => {
    const svc = services();
    const visibility = {
      isHidden: vi.fn(() => {
        throw new Error('hidden trap');
      }),
      subscribe: vi.fn(() => () => {
        throw new Error('unsubscribe trap');
      }),
    };
    const { unmount } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        visibility,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flush);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
    expect(() => unmount()).not.toThrow();
  });
});
