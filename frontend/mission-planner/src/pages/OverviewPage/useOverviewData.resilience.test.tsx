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

  it('clears pending after neutral cancellation and does not report manual success', async () => {
    const svc = services({
      getStatus: vi.fn(() => Promise.reject(new axios.CanceledError('stop'))),
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
    expect(result.current.snapshot.telemetry.pending).toBe(false);
    expect(result.current.snapshot.telemetry.error).toBeNull();
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.manualResult).toBe('partial');
    expect(result.current.snapshot.telemetry.error).toBeNull();
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
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
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
      result.current.controller.reportRadarResult(token, {
        ok: false,
        error: new Error('radar failed'),
      })
    );
    expect(result.current.snapshot.radar.error).toBeNull();
    rerender({ radarEnabled: false });
    await act(flush);
    act(() =>
      result.current.controller.reportRadarResult(token, {
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

  it('restores radar availability after re-enable and ignores stale toggle reports', async () => {
    let now = 1_777_294_800_000;
    const svc = services();
    const { result, rerender } = renderHook(
      ({ radarEnabled }) =>
        useOverviewData({
          cadence: 1,
          poiFilter: '',
          radarEnabled,
          services: svc,
          now: () => now,
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flush);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    expect(result.current.snapshot.radar.availability).toBe('available');
    rerender({ radarEnabled: false });
    await act(flush);
    expect(result.current.snapshot.radar.availability).toBe('unavailable');
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294801',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
    now += 10_000;
    rerender({ radarEnabled: true });
    await act(flush);
    expect(result.current.snapshot.radar.availability).toBe('available');
    expect(result.current.snapshot.radar.freshness).toBe('stale');
  });

  it('restores retained radar availability on re-enable even when now is invalid', async () => {
    let now = 1_777_294_800_000;
    const svc = services();
    const { result, rerender } = renderHook(
      ({ radarEnabled }) =>
        useOverviewData({
          cadence: 1,
          poiFilter: '',
          radarEnabled,
          services: svc,
          now: () => now,
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flush);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    expect(result.current.snapshot.radar.availability).toBe('available');
    rerender({ radarEnabled: false });
    now = Number.NaN;
    await act(flush);
    rerender({ radarEnabled: true });
    await act(flush);
    expect(result.current.snapshot.radar.availability).toBe('available');
    expect(result.current.snapshot.radar.freshness).toBe('fresh');
  });

  it('increments radar token only for actual manual starts and enabled retry', async () => {
    const gate = deferred<typeof statusPayload>();
    const svc = services({
      getStatus: vi
        .fn()
        .mockResolvedValueOnce(structuredClone(statusPayload))
        .mockImplementationOnce(() => gate.promise),
    });
    const { result, rerender } = renderHook(
      ({ radarEnabled }) =>
        useOverviewData({
          cadence: 'paused',
          poiFilter: '',
          radarEnabled,
          services: svc,
          now: () => 1_777_294_800_000,
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flush);
    expect(result.current.controller.radarRefreshToken).toBe(0);
    const first = result.current.controller.manualRefresh();
    const second = result.current.controller.manualRefresh();
    expect(second).toBe(first);
    await act(flush);
    expect(result.current.controller.radarRefreshToken).toBe(1);
    gate.resolve(structuredClone(statusPayload));
    await act(async () => first);
    act(() => result.current.controller.retryRadar());
    expect(result.current.controller.radarRefreshToken).toBe(2);
    rerender({ radarEnabled: false });
    await act(flush);
    act(() => result.current.controller.retryRadar());
    expect(result.current.controller.radarRefreshToken).toBe(2);
  });

  it('clears radar error on enabled retry and invalidates prior reports', async () => {
    const svc = services();
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flush);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: false,
        error: new Error('radar failed'),
      })
    );
    expect(result.current.snapshot.radar.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    act(() => result.current.controller.retryRadar());
    expect(result.current.snapshot.radar.error).toBeNull();
    expect(result.current.snapshot.radar.pending).toBe(true);
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294801',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
    act(() =>
      result.current.controller.reportRadarResult(
        result.current.controller.radarRefreshToken,
        {
          ok: true,
          frameTimestamp: '1777294801',
        }
      )
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294801'
    );
  });

  it('reports invalid radar frame syntax without dropping the last good frame', async () => {
    const svc = services();
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flush);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '01777294800',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
    expect(result.current.snapshot.radar.error).toEqual({
      code: 'invalid-data',
      message: 'Source data was invalid.',
    });
  });

  it('records accepted canceled radar failures as fixed request failures', async () => {
    const svc = services();
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flush);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: false,
        error: new axios.CanceledError('radar canceled'),
      })
    );
    expect(result.current.snapshot.radar.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    expect(result.current.snapshot.radar.transportLastAttemptAt).toBe(
      1_777_294_800_000
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
  });

  it('does not inspect validation-shaped or hostile radar failure values', async () => {
    const svc = services();
    let accessed = false;
    const hostile = Object.defineProperty({ ok: false }, 'error', {
      get() {
        accessed = true;
        throw new Error('error getter was inspected');
      },
    }) as { readonly ok: false; readonly error: unknown };
    const validation = {
      name: 'OverviewDataValidationError',
      code: 'invalid_overview_data',
      source: 'radar',
    };
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_801_000,
      })
    );
    await act(flush);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: false,
        error: validation,
      })
    );
    expect(result.current.snapshot.radar.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    act(() => result.current.controller.reportRadarResult(token, hostile));
    expect(accessed).toBe(false);
    expect(result.current.snapshot.radar.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
  });

  it('ignores malformed, future, stale, disabled, and superseded radar tokens', async () => {
    const svc = services();
    const { result, rerender } = renderHook(
      ({ radarEnabled }) =>
        useOverviewData({
          cadence: 1,
          poiFilter: '',
          radarEnabled,
          services: svc,
          now: () => 1_777_294_800_000,
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flush);
    const initial = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(initial, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    for (const token of [Number.NaN, initial + 1, -1]) {
      act(() =>
        result.current.controller.reportRadarResult(token, {
          ok: true,
          frameTimestamp: '1777294801',
        })
      );
    }
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
    rerender({ radarEnabled: false });
    await act(flush);
    act(() =>
      result.current.controller.reportRadarResult(initial, {
        ok: true,
        frameTimestamp: '1777294801',
      })
    );
    rerender({ radarEnabled: true });
    await act(flush);
    act(() =>
      result.current.controller.reportRadarResult(initial, {
        ok: true,
        frameTimestamp: '1777294802',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
    act(() => result.current.controller.retryRadar());
    const current = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(initial, {
        ok: true,
        frameTimestamp: '1777294803',
      })
    );
    act(() =>
      result.current.controller.reportRadarResult(current, {
        ok: true,
        frameTimestamp: '1777294804',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294804'
    );
  });

  it('recomputes retained freshness on resume without transport mutation', async () => {
    let now = 1_777_294_800_000;
    const svc = services({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(statusPayload),
          timestamp: '2026-04-27T13:00:00Z',
        })
      ),
    });
    const { result, rerender } = renderHook(
      ({ cadence }) =>
        useOverviewData({
          cadence,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        }),
      { initialProps: { cadence: 1 as 1 | 'paused' } }
    );
    await act(flush);
    expect(result.current.snapshot.telemetry.freshness).toBe('fresh');
    const successAt = result.current.snapshot.telemetry.transportLastSuccessAt;
    rerender({ cadence: 'paused' as const });
    now += 10_000;
    await act(flush);
    expect(result.current.snapshot.telemetry.freshness).toBe('fresh');
    rerender({ cadence: 1 as const });
    await act(flush);
    expect(result.current.snapshot.telemetry.freshness).toBe('stale');
    expect(result.current.snapshot.announcement).toBe(
      'Telemetry data is stale.'
    );
    expect(result.current.snapshot.telemetry.transportLastSuccessAt).toBe(
      successAt
    );
  });

  it('announces direct error-to-stale and stale-to-error transitions as entered states', async () => {
    let now = 1_777_294_800_000;
    const svc = services({
      getStatus: vi
        .fn()
        .mockResolvedValueOnce({
          ...structuredClone(statusPayload),
          timestamp: '2026-04-27T13:00:00Z',
        })
        .mockRejectedValueOnce(new Error('down')),
    });
    const { result, rerender } = renderHook(
      ({ cadence }) =>
        useOverviewData({
          cadence,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        }),
      { initialProps: { cadence: 1 as 1 | 'paused' } }
    );
    await act(flush);
    rerender({ cadence: 'paused' as const });
    now += 10_000;
    rerender({ cadence: 1 as const });
    await act(flush);
    expect(result.current.snapshot.announcement).toBe(
      'Telemetry data is stale.'
    );
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.announcement).toBe(
      'Manual refresh completed with partial failures.'
    );
    expect(result.current.snapshot.telemetry.error).toBeTruthy();
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
