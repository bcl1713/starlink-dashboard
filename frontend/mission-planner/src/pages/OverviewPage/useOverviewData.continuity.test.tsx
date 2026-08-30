import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  activeXLinkPayload,
  availableGep,
  historyPayload,
  poiPayload,
  routePayload,
  statusPayload,
} from '../../services/monitoring-test-fixtures';
import type { OverviewDataServices } from './overview-data-types';
import { useOverviewData } from './useOverviewData';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function baseServices(overrides: Partial<OverviewDataServices> = {}) {
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

describe('useOverviewData continuity', () => {
  it('holds telemetry samples before server history and reconciles both completion orders identically', async () => {
    const historyGate = deferred<typeof historyPayload>();
    const first = baseServices({
      getMonitoringHistory: vi.fn(() => historyGate.promise),
      getStatus: vi
        .fn()
        .mockResolvedValueOnce({
          ...structuredClone(statusPayload),
          timestamp: '2026-08-29T18:00:04Z',
        })
        .mockResolvedValueOnce({
          ...structuredClone(statusPayload),
          timestamp: '2026-08-29T18:00:04Z',
        }),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: first,
        now: () => 1_777_294_804_000,
      })
    );
    await act(async () => Promise.resolve());
    const manual = result.current.controller.manualRefresh();
    await act(async () => Promise.resolve());
    expect(result.current.snapshot.history.data).toBeUndefined();
    historyGate.resolve(structuredClone(historyPayload));
    await act(async () => manual);
    await act(async () => Promise.resolve());
    expect(result.current.snapshot.history.data).toMatchObject({
      generated_at: historyPayload.generated_at,
      window_start: historyPayload.window_start,
      window_end: historyPayload.window_end,
      range_seconds: historyPayload.range_seconds,
      step_seconds: historyPayload.step_seconds,
    });

    const second = baseServices({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(statusPayload),
          timestamp: '2026-08-29T18:00:04Z',
        })
      ),
    });
    const other = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: second,
        now: () => 1_777_294_804_000,
      })
    );
    await act(async () => Promise.resolve());
    await act(async () => other.result.current.controller.manualRefresh());
    expect(other.result.current.snapshot.history.data).toEqual(
      result.current.snapshot.history.data
    );
  });

  it('commits grouped active link and route pairs atomically without mixed generations', async () => {
    const routeGate = deferred<typeof routePayload>();
    const services = baseServices({
      getRouteCoordinates: vi.fn((direction) =>
        direction === 'west'
          ? Promise.resolve({
              ...structuredClone(routePayload),
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
    await act(async () => Promise.resolve());
    expect(result.current.snapshot.route.data).toBeUndefined();
    routeGate.resolve({ ...structuredClone(routePayload), route_id: 'new' });
    await act(async () => routeGate.promise);
    expect(result.current.snapshot.route.data?.west.route_id).toBe('old');
    expect(result.current.snapshot.route.data?.east.route_id).toBe('new');
  });
});
