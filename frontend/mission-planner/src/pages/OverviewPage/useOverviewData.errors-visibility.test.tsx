import { act, renderHook } from '@testing-library/react';
import axios from 'axios';
import { StrictMode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { ActiveXLink, RouteCoordinates } from '../../types/monitoring';
import { useOverviewData } from './useOverviewData';
import {
  activeXLinkPayload,
  captureReactWarnings,
  cloneFixture,
  createCallCountingServices,
  createOverviewServices,
  flushOverviewEffects,
  historyPayload,
  routePayload,
  statusPayload,
  unavailableGep,
} from './overview-test-harness';

describe('useOverviewData errors', () => {
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
      const svc = createOverviewServices(overrides);
      const { result } = renderHook(() =>
        useOverviewData({
          cadence: 'paused',
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => 1_777_294_800_000,
        })
      );
      await act(flushOverviewEffects);
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
    vi.useFakeTimers();
    try {
      let now = 1_777_294_800_000;
      const { svc } = createCallCountingServices();
      const warnings = captureReactWarnings();
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
        await act(flushOverviewEffects);
        await act(async () => result.current.controller.manualRefresh());
        now += 1000;
        await act(async () => vi.advanceTimersByTime(1000));
        await act(flushOverviewEffects);
        unmount();
        expect(warnings.observed).toEqual([]);
      } finally {
        warnings.restore();
      }
    } finally {
      vi.useRealTimers();
    }
  });

  it('treats independent failures, semantic unavailable, and manual results separately', async () => {
    const svc = createOverviewServices({
      getPOIETAs: vi.fn(() => Promise.reject(new Error('poi failed'))),
      getGroundEntryPoint: vi.fn(() =>
        Promise.resolve(cloneFixture(unavailableGep))
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
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
    expect(result.current.snapshot.telemetry.error).toBeNull();
    unmount();
    await expect(result.current.controller.manualRefresh()).rejects.toThrow(
      /unmounted/i
    );
  });

  it('clears pending after neutral cancellation and does not report manual success', async () => {
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
    expect(result.current.snapshot.telemetry.pending).toBe(false);
    expect(result.current.snapshot.telemetry.error).toBeNull();
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.manualResult).toBe('partial');
    expect(result.current.snapshot.telemetry.error).toBeNull();
  });

  it('starts active link and route siblings for hostile thenables and sync throws', async () => {
    const activeStates: string[] = [];
    const routeDirections: string[] = [];
    const hostileThenable = Promise.resolve(activeXLinkPayload);
    Object.defineProperty(hostileThenable, 'then', {
      configurable: true,
      get() {
        throw new Error('hostile thenable');
      },
    });
    const svc = createOverviewServices({
      getActiveXLink: vi.fn((state: 'normal' | 'warning') => {
        activeStates.push(state);
        return state === 'normal'
          ? (hostileThenable as Promise<ActiveXLink>)
          : Promise.resolve({
              ...cloneFixture(activeXLinkPayload),
              state,
            } as ActiveXLink);
      }),
      getRouteCoordinates: vi.fn((direction: 'west' | 'east') => {
        routeDirections.push(direction);
        if (direction === 'west') throw new Error('west failed');
        return Promise.resolve(cloneFixture(routePayload) as RouteCoordinates);
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
    await act(flushOverviewEffects);
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
    const telemetry = cloneFixture(statusPayload);
    const history = cloneFixture(historyPayload);
    Object.freeze(telemetry);
    Object.freeze(telemetry.position);
    Object.freeze(telemetry.network);
    Object.freeze(history);
    Object.freeze(history.series);
    Object.freeze(history.series[0]);
    Object.freeze(history.series[0].samples);
    const svc = createOverviewServices({
      getStatus: vi.fn(() => Promise.resolve(telemetry)),
      getMonitoringHistory: vi.fn(() => Promise.resolve(history)),
    });
    const beforeTelemetry = cloneFixture(telemetry);
    const beforeHistory = cloneFixture(history);
    renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flushOverviewEffects);
    expect(telemetry).toEqual(beforeTelemetry);
    expect(history).toEqual(beforeHistory);
  });

  it('recomputes retained freshness on resume without transport mutation', async () => {
    let now = 1_777_294_800_000;
    const svc = createOverviewServices({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...cloneFixture(statusPayload),
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
    await act(flushOverviewEffects);
    expect(result.current.snapshot.telemetry.freshness).toBe('fresh');
    const successAt = result.current.snapshot.telemetry.transportLastSuccessAt;
    rerender({ cadence: 'paused' as const });
    now += 10_000;
    await act(flushOverviewEffects);
    expect(result.current.snapshot.telemetry.freshness).toBe('fresh');
    rerender({ cadence: 1 as const });
    await act(flushOverviewEffects);
    expect(result.current.snapshot.telemetry.freshness).toBe('stale');
    expect(result.current.snapshot.announcement).toBe(
      'Telemetry data is stale.'
    );
    expect(result.current.snapshot.telemetry.transportLastSuccessAt).toBe(
      successAt
    );
  });
});
