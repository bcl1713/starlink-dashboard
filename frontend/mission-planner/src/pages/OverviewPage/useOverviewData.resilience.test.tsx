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
import type {
  ActiveXLink,
  OverviewPOIFilter,
  RouteCoordinates,
} from '../../types/monitoring';
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
  it('ignores abort-ignoring old lifecycle results after service replacement', async () => {
    const oldStatus = deferred<typeof statusPayload>();
    const oldServices = services({
      getStatus: vi.fn(() => oldStatus.promise),
    });
    const newServices = services({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(statusPayload),
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
    await act(flush);
    rerender({ svc: newServices });
    await act(flush);
    expect(result.current.snapshot.telemetry.data?.timestamp).toBe(
      '2026-08-29T18:00:10Z'
    );
    const before = result.current.snapshot;
    oldStatus.resolve({
      ...structuredClone(statusPayload),
      timestamp: '2026-08-29T18:00:01Z',
    });
    await act(flush);
    expect(result.current.snapshot).toBe(before);
    expect(result.current.snapshot.globalTransportLastSuccessAt).toBe(
      1_777_294_810_000
    );
  });

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

  it('makes retained radar callbacks no-ops after unmount', async () => {
    const svc = services();
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
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
    const controller = result.current.controller;
    const token = controller.radarRefreshToken;
    unmount();
    act(() => controller.retryRadar());
    act(() =>
      controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    expect(errorSpy).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });

  it('does not sample now or inspect hostile retained radar reports after unmount', async () => {
    let nowCalls = 0;
    let okAccessed = false;
    let frameAccessed = false;
    let errorAccessed = false;
    const svc = services();
    const { result, unmount } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => {
          nowCalls += 1;
          return 1_777_294_800_000;
        },
      })
    );
    await act(flush);
    const controller = result.current.controller;
    const token = controller.radarRefreshToken;
    const beforeUnmountNowCalls = nowCalls;
    const hostileOk = Object.defineProperty({}, 'ok', {
      get() {
        okAccessed = true;
        throw new Error('ok getter');
      },
    }) as { readonly ok: true; readonly frameTimestamp: string };
    const hostileFrame = Object.defineProperty({ ok: true }, 'frameTimestamp', {
      get() {
        frameAccessed = true;
        throw new Error('frame getter');
      },
    }) as { readonly ok: true; readonly frameTimestamp: string };
    const hostileError = Object.defineProperty({ ok: false }, 'error', {
      get() {
        errorAccessed = true;
        throw new Error('error getter');
      },
    }) as { readonly ok: false; readonly error: unknown };
    unmount();
    act(() => controller.reportRadarResult(token, hostileOk));
    act(() => controller.reportRadarResult(token, hostileFrame));
    act(() => controller.reportRadarResult(token, hostileError));
    expect(nowCalls).toBe(beforeUnmountNowCalls);
    expect(okAccessed).toBe(false);
    expect(frameAccessed).toBe(false);
    expect(errorAccessed).toBe(false);
  });

  it('starts active link and route siblings for hostile thenables and sync throws', async () => {
    const activeStates: string[] = [];
    const routeDirections: string[] = [];
    const hostileThenable = {
      get then() {
        throw new Error('hostile thenable');
      },
    };
    const svc = services({
      getActiveXLink: vi.fn((state: 'normal' | 'warning') => {
        activeStates.push(state);
        return state === 'normal'
          ? (hostileThenable as unknown as Promise<ActiveXLink>)
          : Promise.resolve({
              ...structuredClone(activeXLinkPayload),
              state,
            } as ActiveXLink);
      }),
      getRouteCoordinates: vi.fn((direction: 'west' | 'east') => {
        routeDirections.push(direction);
        if (direction === 'west') throw new Error('west failed');
        return Promise.resolve(
          structuredClone(routePayload) as RouteCoordinates
        );
      }),
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
    expect(activeStates).toEqual(['normal', 'warning']);
    expect(routeDirections).toEqual(['west', 'east']);
    expect(result.current.snapshot.activeLink.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    expect(result.current.snapshot.route.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    expect(result.current.snapshot.activeLink.data).toBeUndefined();
    expect(result.current.snapshot.route.data).toBeUndefined();
  });

  it('does not mutate frozen service payloads', async () => {
    const telemetry = structuredClone(statusPayload);
    const history = structuredClone(historyPayload);
    Object.freeze(telemetry);
    Object.freeze(telemetry.position);
    Object.freeze(telemetry.network);
    Object.freeze(history);
    Object.freeze(history.series);
    const svc = services({
      getStatus: vi.fn(() => Promise.resolve(telemetry)),
      getMonitoringHistory: vi.fn(() => Promise.resolve(history)),
    });
    const beforeTelemetry = structuredClone(telemetry);
    const beforeHistory = structuredClone(history);
    renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flush);
    expect(telemetry).toEqual(beforeTelemetry);
    expect(history).toEqual(beforeHistory);
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
    let throwNow = false;
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
          now: () => {
            if (throwNow) throw new Error('now inspected');
            return 1_777_294_800_000;
          },
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flush);
    const oldToken = result.current.controller.radarRefreshToken;
    expect(oldToken).toBe(0);
    const first = result.current.controller.manualRefresh();
    const second = result.current.controller.manualRefresh();
    expect(second).toBe(first);
    await act(flush);
    expect(result.current.controller.radarRefreshToken).toBe(1);
    let inspected = false;
    const hostile = Object.defineProperty({ ok: true }, 'frameTimestamp', {
      get() {
        inspected = true;
        throw new Error('frame inspected');
      },
    }) as { readonly ok: true; readonly frameTimestamp: string };
    const before = result.current.snapshot;
    throwNow = true;
    act(() => result.current.controller.reportRadarResult(oldToken, hostile));
    expect(result.current.snapshot).toBe(before);
    expect(inspected).toBe(false);
    throwNow = false;
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

  it('announces true stale-to-error as the entered error state', async () => {
    vi.useFakeTimers();
    try {
      let now = 1_777_294_800_000;
      const svc = services({
        getStatus: vi
          .fn()
          .mockResolvedValueOnce({
            ...structuredClone(statusPayload),
            timestamp: '2026-04-27T12:59:50Z',
          })
          .mockRejectedValueOnce(new Error('down')),
      });
      const { result } = renderHook(() =>
        useOverviewData({
          cadence: 1,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        })
      );
      await act(flush);
      expect(result.current.snapshot.telemetry.phase).toBe('stale');
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flush);
      expect(result.current.snapshot.telemetry.error).toEqual({
        code: 'request-failed',
        message: 'Source refresh failed.',
      });
      expect(result.current.snapshot.announcement).toBe(
        'Telemetry refresh failed.'
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it('announces true error-to-stale as the entered stale state', async () => {
    vi.useFakeTimers();
    try {
      let now = 1_777_294_800_000;
      const telemetry = {
        ...structuredClone(statusPayload),
        timestamp: '2026-04-27T13:00:00Z',
      };
      const svc = services({
        getStatus: vi
          .fn()
          .mockResolvedValueOnce(telemetry)
          .mockRejectedValueOnce(new Error('down'))
          .mockResolvedValueOnce(telemetry),
        getMissionEventETAs: vi.fn(() =>
          Promise.reject(new Error('events down'))
        ),
      });
      const { result } = renderHook(() =>
        useOverviewData({
          cadence: 1,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        })
      );
      await act(flush);
      expect(result.current.snapshot.telemetry.freshness).toBe('fresh');
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flush);
      expect(result.current.snapshot.telemetry.phase).toBe('error');
      expect(result.current.snapshot.announcement).toBe(
        'Telemetry refresh failed.'
      );
      now += 6000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flush);
      expect(result.current.snapshot.telemetry.error).toBeNull();
      expect(result.current.snapshot.telemetry.phase).toBe('stale');
      expect(result.current.snapshot.announcement).toBe(
        'Telemetry data is stale.'
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it('announces standalone error-to-ready recovery without manual masking', async () => {
    vi.useFakeTimers();
    try {
      let now = 1_777_294_800_000;
      const svc = services({
        getSatelliteETAs: vi
          .fn()
          .mockRejectedValueOnce(new Error('satellite down'))
          .mockResolvedValue(structuredClone(poiPayload)),
        getMissionEventETAs: vi.fn(() =>
          Promise.reject(new Error('events down'))
        ),
      });
      const { result } = renderHook(() =>
        useOverviewData({
          cadence: 1,
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => now,
        })
      );
      await act(flush);
      expect(result.current.snapshot.announcement).toBe(
        'Satellite ETAs refresh failed.'
      );
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flush);
      expect(result.current.snapshot.satellites.phase).toBe('ready');
      expect(result.current.snapshot.missionEvents.phase).toBe('error');
      expect(result.current.snapshot.announcement).toBe(
        'Satellite ETAs recovered.'
      );
      const repeated = result.current.snapshot.announcement;
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flush);
      expect(result.current.snapshot.announcement).toBe(repeated);
    } finally {
      vi.useRealTimers();
    }
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
