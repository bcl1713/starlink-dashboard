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
    await act(flush);
    const manual = result.current.controller.manualRefresh();
    await act(flush);
    expect(result.current.snapshot.history.data).toBeUndefined();
    historyGate.resolve(structuredClone(historyPayload));
    await act(async () => manual);
    await act(flush);
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
    await act(flush);
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
    await act(flush);
    expect(result.current.snapshot.route.data).toBeUndefined();
    routeGate.resolve({ ...structuredClone(routePayload), route_id: 'new' });
    await act(async () => routeGate.promise);
    expect(result.current.snapshot.route.data?.west.route_id).toBe('old');
    expect(result.current.snapshot.route.data?.east.route_id).toBe('new');
  });

  it('keeps same-cycle telemetry when server history also completes', async () => {
    const telemetryTime = '2026-08-29T18:00:04Z';
    const svc = baseServices({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(statusPayload),
          timestamp: telemetryTime,
        })
      ),
      getMonitoringHistory: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(historyPayload),
          series: historyPayload.series.map((series) => ({
            ...series,
            samples: series.samples.slice(0, 1),
          })),
        })
      ),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_788_026_404_000,
      })
    );
    await act(flush);
    await act(async () => result.current.controller.manualRefresh());
    const history = result.current.snapshot.history.data;
    expect(
      history?.series.every((series) =>
        series.samples.some((sample) => sample.timestamp === telemetryTime)
      )
    ).toBe(true);
  });

  it('lets duplicate server samples including null win over telemetry samples', async () => {
    const telemetryTime = '2026-08-29T18:00:04Z';
    const serverHistory = {
      ...structuredClone(historyPayload),
      window_end: telemetryTime,
      series: historyPayload.series.map((series) => ({
        ...series,
        samples: [{ timestamp: telemetryTime, value: null }],
      })),
    };
    const svc = baseServices({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(statusPayload),
          timestamp: telemetryTime,
        })
      ),
      getMonitoringHistory: vi.fn(() => Promise.resolve(serverHistory)),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_788_026_404_000,
      })
    );
    await act(flush);
    const history = result.current.snapshot.history.data;
    expect(
      history?.series.every(
        (series) =>
          series.samples.find((sample) => sample.timestamp === telemetryTime)
            ?.value === null
      )
    ).toBe(true);
    expect(history?.generated_at).toBe(historyPayload.generated_at);
  });

  it('preserves a real history failure while appending local telemetry', async () => {
    const telemetryTime = '2026-08-29T18:00:05Z';
    const svc = baseServices({
      getStatus: vi
        .fn()
        .mockResolvedValueOnce(structuredClone(statusPayload))
        .mockResolvedValueOnce({
          ...structuredClone(statusPayload),
          timestamp: telemetryTime,
        }),
      getMonitoringHistory: vi
        .fn()
        .mockResolvedValueOnce(structuredClone(historyPayload))
        .mockRejectedValueOnce(new Error('history down')),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_788_026_405_000,
      })
    );
    await act(flush);
    const successAt = result.current.snapshot.history.transportLastSuccessAt;
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.history.error).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    expect(result.current.snapshot.history.transportLastSuccessAt).toBe(
      successAt
    );
    expect(
      result.current.snapshot.history.data?.series.every((series) =>
        series.samples.some((sample) => sample.timestamp === telemetryTime)
      )
    ).toBe(true);
  });
});
