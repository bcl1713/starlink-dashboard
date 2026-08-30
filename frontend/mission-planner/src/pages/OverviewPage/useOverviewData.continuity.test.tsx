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
import type { OverviewStatus } from '../../types/monitoring';
import type { OverviewDataServices } from './overview-data-types';
import { HISTORY_MAX_SAMPLES } from './history';
import { buildSlotCommits } from './overview-history-continuity';
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
  it('bounds and deduplicates telemetry pending before any server history success', () => {
    let pending: OverviewStatus[] = Array.from(
      { length: HISTORY_MAX_SAMPLES + 20 },
      (_, index) => ({
        ...structuredClone(statusPayload),
        timestamp: `2026-08-29T12:${String(Math.floor(index / 60)).padStart(
          2,
          '0'
        )}:${String(index % 60).padStart(2, '0')}Z`,
      })
    );
    const duplicate = {
      ...structuredClone(statusPayload),
      timestamp: pending.at(-1)?.timestamp ?? '2026-08-29T12:30:20Z',
      network: {
        ...statusPayload.network,
        latency_ms: 999,
      },
    };

    const result = buildSlotCommits(
      [
        {
          slot: 'telemetry',
          outcome: { ok: true, data: duplicate },
        },
        {
          slot: 'history',
          outcome: {
            ok: false,
            error: {
              code: 'request-failed',
              message: 'Source refresh failed.',
            },
          },
        },
      ],
      undefined,
      pending,
      1_788_008_220_000
    );

    pending = result.pending;
    expect(result.commits.some(([slot]) => slot === 'history')).toBe(true);
    expect(pending).toHaveLength(HISTORY_MAX_SAMPLES);
    expect(pending.at(0)?.timestamp).toBe('2026-08-29T12:00:20Z');
    expect(pending.at(-1)?.network.latency_ms).toBe(999);
  });

  it('discards malformed and hostile pending telemetry during prolonged history failures', () => {
    const valid = Array.from(
      { length: HISTORY_MAX_SAMPLES + 30 },
      (_, index) => ({
        ...structuredClone(statusPayload),
        timestamp: `2026-08-29T12:${String(Math.floor(index / 60)).padStart(
          2,
          '0'
        )}:${String(index % 60).padStart(2, '0')}Z`,
      })
    );
    const duplicate = {
      ...structuredClone(statusPayload),
      timestamp: valid.at(-1)?.timestamp ?? '2026-08-29T12:30:30Z',
      network: { ...statusPayload.network, latency_ms: 1234 },
    };
    const throwingTimestamp = Object.defineProperty(
      { ...structuredClone(statusPayload) },
      'timestamp',
      {
        get() {
          throw new Error('timestamp revoked');
        },
      }
    ) as OverviewStatus;
    const { proxy, revoke } = Proxy.revocable(
      { ...structuredClone(statusPayload) },
      {}
    );
    revoke();
    const malformed = {
      ...structuredClone(statusPayload),
      timestamp: 'not-a-date',
    };
    let pending: OverviewStatus[] = [
      malformed,
      throwingTimestamp,
      proxy as OverviewStatus,
      ...valid,
      duplicate,
    ];

    for (let attempt = 0; attempt < 3; attempt += 1) {
      const result = buildSlotCommits(
        [
          {
            slot: 'history',
            outcome: {
              ok: false,
              error: {
                code: 'request-failed',
                message: 'Source refresh failed.',
              },
            },
          },
        ],
        undefined,
        pending,
        1_788_008_230_000
      );
      pending = result.pending;
    }

    expect(pending).toHaveLength(HISTORY_MAX_SAMPLES);
    expect(pending.at(0)?.timestamp).toBe('2026-08-29T12:00:30Z');
    expect(pending.at(-1)?.timestamp).toBe('2026-08-29T12:30:30Z');
    expect(pending.at(-1)?.network.latency_ms).toBe(1234);
  });

  it('holds telemetry samples before server history and reconciles both completion orders identically', async () => {
    const telemetryTime = '2026-08-29T18:00:05Z';
    const nextTelemetryTime = '2026-08-29T18:30:05Z';
    const firstServerHistory = {
      ...structuredClone(historyPayload),
      window_start: '2026-08-29T18:00:00Z',
      window_end: telemetryTime,
      series: historyPayload.series.map((series) => ({
        ...series,
        samples: [],
      })),
    };
    const nextServerHistory = {
      ...structuredClone(historyPayload),
      generated_at: '2026-08-29T18:30:05Z',
      window_start: telemetryTime,
      window_end: nextTelemetryTime,
      series: historyPayload.series.map((series) => ({
        ...series,
        samples: [{ timestamp: telemetryTime, value: null }],
      })),
    };
    const finalServerHistory = {
      ...structuredClone(historyPayload),
      generated_at: '2026-08-29T18:30:06Z',
      window_start: telemetryTime,
      window_end: nextTelemetryTime,
      series: historyPayload.series.map((series, index) => ({
        ...series,
        samples: [{ timestamp: nextTelemetryTime, value: index + 20 }],
      })),
    };

    async function renderOrder(order: 'telemetry-first' | 'history-first') {
      let nowMs = 1_788_026_405_000;
      const statusGate = deferred<typeof statusPayload>();
      const historyGate = deferred<typeof historyPayload>();
      const svc = baseServices({
        getStatus: vi
          .fn()
          .mockImplementationOnce(() => statusGate.promise)
          .mockResolvedValueOnce({
            ...structuredClone(statusPayload),
            timestamp: nextTelemetryTime,
          })
          .mockResolvedValueOnce({
            ...structuredClone(statusPayload),
            timestamp: nextTelemetryTime,
          }),
        getMonitoringHistory: vi
          .fn()
          .mockImplementationOnce(() => historyGate.promise)
          .mockResolvedValueOnce(nextServerHistory)
          .mockResolvedValueOnce(finalServerHistory),
      });
      const rendered = renderHook(() =>
        useOverviewData({
          cadence: 'paused',
          poiFilter: '',
          radarEnabled: true,
          services: svc,
          now: () => nowMs,
        })
      );
      await act(flush);
      if (order === 'telemetry-first') {
        statusGate.resolve({
          ...structuredClone(statusPayload),
          timestamp: telemetryTime,
        });
        await act(flush);
        expect(rendered.result.current.snapshot.history.data).toBeUndefined();
        historyGate.resolve(firstServerHistory);
      } else {
        historyGate.resolve(firstServerHistory);
        await act(flush);
        expect(rendered.result.current.snapshot.history.data).toBeUndefined();
        statusGate.resolve({
          ...structuredClone(statusPayload),
          timestamp: telemetryTime,
        });
      }
      await act(flush);
      return {
        ...rendered,
        advanceToNextCycle() {
          nowMs = 1_788_028_205_000;
        },
      };
    }

    const telemetryFirst = await renderOrder('telemetry-first');
    const historyFirst = await renderOrder('history-first');
    expect(telemetryFirst.result.current.snapshot.history.data).toEqual(
      historyFirst.result.current.snapshot.history.data
    );
    for (const rendered of [telemetryFirst, historyFirst]) {
      const initial = rendered.result.current.snapshot.history.data;
      expect(initial).toMatchObject({
        generated_at: firstServerHistory.generated_at,
        window_start: firstServerHistory.window_start,
        window_end: firstServerHistory.window_end,
        range_seconds: historyPayload.range_seconds,
        step_seconds: historyPayload.step_seconds,
      });
      for (const series of initial?.series ?? []) {
        expect(
          series.samples.find((sample) => sample.timestamp === telemetryTime)
            ?.value
        ).toEqual(expect.any(Number));
      }
    }

    for (const rendered of [telemetryFirst, historyFirst]) {
      rendered.advanceToNextCycle();
      await act(async () => rendered.result.current.controller.manualRefresh());
      const reconciled = rendered.result.current.snapshot.history.data;
      expect(reconciled).toMatchObject({
        generated_at: nextServerHistory.generated_at,
        window_start: nextServerHistory.window_start,
        window_end: nextServerHistory.window_end,
        range_seconds: historyPayload.range_seconds,
        step_seconds: historyPayload.step_seconds,
      });
      for (const series of reconciled?.series ?? []) {
        expect(
          series.samples.find((sample) => sample.timestamp === telemetryTime)
            ?.value
        ).toBeNull();
        expect(
          series.samples.some(
            (sample) => sample.timestamp === nextTelemetryTime
          )
        ).toBe(true);
      }
      await act(async () => rendered.result.current.controller.manualRefresh());
      const final = rendered.result.current.snapshot.history.data;
      expect(final).toMatchObject({
        generated_at: finalServerHistory.generated_at,
        window_start: finalServerHistory.window_start,
        window_end: finalServerHistory.window_end,
        range_seconds: historyPayload.range_seconds,
        step_seconds: historyPayload.step_seconds,
      });
      for (const series of final?.series ?? []) {
        expect(
          series.samples.find((sample) => sample.timestamp === telemetryTime)
            ?.value
        ).toBeNull();
        expect(
          series.samples.find(
            (sample) => sample.timestamp === nextTelemetryTime
          )?.value
        ).toEqual(expect.any(Number));
      }
    }
  });

  it('keeps telemetry-only history pending without fabricated metadata', async () => {
    const historyGate = deferred<typeof historyPayload>();
    const svc = baseServices({
      getMonitoringHistory: vi.fn(() => historyGate.promise),
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(statusPayload),
          timestamp: '2026-08-29T18:00:04Z',
        })
      ),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_804_000,
      })
    );
    await act(flush);
    expect(result.current.snapshot.history.data).toBeUndefined();
    expect(result.current.snapshot.history.transportLastSuccessAt).toBeNull();
    expect(result.current.snapshot.history.transportLastAttemptAt).toBeNull();
    expect(result.current.snapshot.history.availability).toBe('unknown');
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

  it('maps six telemetry metrics through the hook without fabricated series', async () => {
    const telemetryTime = '2026-08-29T12:30:01Z';
    const telemetry = {
      ...structuredClone(statusPayload),
      timestamp: telemetryTime,
      position: {
        ...statusPayload.position,
        latitude: 12,
        longitude: -34,
        altitude: 1234,
      },
      network: {
        ...statusPayload.network,
        latency_ms: 45,
        throughput_down_mbps: 67,
        throughput_up_mbps: 8,
        packet_loss_percent: 9,
      },
      obstruction: { obstruction_percent: 99 },
    };
    const serverHistory = {
      ...structuredClone(historyPayload),
      window_start: '2026-08-29T12:00:01Z',
      window_end: telemetryTime,
      series: historyPayload.series.map((series) => ({
        ...series,
        samples: [],
      })),
    };
    const svc = baseServices({
      getStatus: vi.fn(() => Promise.resolve(telemetry)),
      getMonitoringHistory: vi.fn(() => Promise.resolve(serverHistory)),
    });
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_788_006_601_000,
      })
    );
    await act(flush);
    const byMetric = Object.fromEntries(
      result.current.snapshot.history.data?.series.map((series) => [
        series.metric,
        series.samples,
      ]) ?? []
    );
    expect(byMetric.latitude_degrees).toEqual([
      { timestamp: telemetryTime, value: 12 },
    ]);
    expect(byMetric.longitude_degrees).toEqual([
      { timestamp: telemetryTime, value: -34 },
    ]);
    expect(byMetric.latency_ms).toEqual([
      { timestamp: telemetryTime, value: 45 },
    ]);
    expect(byMetric.throughput_down_mbps).toEqual([
      { timestamp: telemetryTime, value: 67 },
    ]);
    expect(byMetric.throughput_up_mbps).toEqual([
      { timestamp: telemetryTime, value: 8 },
    ]);
    expect(byMetric.packet_loss_percent).toEqual([
      { timestamp: telemetryTime, value: 9 },
    ]);
    expect(byMetric.altitude).toBeUndefined();
    expect(byMetric.obstruction_percent).toBeUndefined();
  });

  it('includes the exact history horizon and prunes older samples through the hook', async () => {
    const lower = '2026-08-29T12:00:01Z';
    const upper = '2026-08-29T12:30:01Z';
    const tooOld = '2026-08-29T12:00:00.999999Z';
    const serverHistory = {
      ...structuredClone(historyPayload),
      window_start: lower,
      window_end: upper,
      series: historyPayload.series.map((series, index) => ({
        ...series,
        samples: [
          { timestamp: tooOld, value: -1 },
          { timestamp: lower, value: index },
          { timestamp: upper, value: index + 10 },
        ],
      })),
    };
    const svc = baseServices({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(statusPayload),
          timestamp: '2026-08-29T12:31:00Z',
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
        now: () => 1_788_006_601_000,
      })
    );
    await act(flush);
    for (const series of result.current.snapshot.history.data?.series ?? []) {
      expect(series.samples.map((sample) => sample.timestamp)).toEqual([
        lower,
        upper,
      ]);
    }
  });

  it('caps hook-level history while preserving server metadata and metric order', async () => {
    const serverHistory = {
      ...structuredClone(historyPayload),
      window_start: '2026-08-29T12:00:00Z',
      window_end: '2026-08-29T12:30:01Z',
      series: historyPayload.series.map((series) => ({
        ...series,
        samples: Array.from({ length: 1802 }, (_, index) => ({
          timestamp: `2026-08-29T12:00:01.${String(index).padStart(6, '0')}Z`,
          value: index,
        })),
      })),
    };
    const svc = baseServices({
      getStatus: vi.fn(() =>
        Promise.resolve({
          ...structuredClone(statusPayload),
          timestamp: '2026-08-29T12:31:00Z',
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
        now: () => 1_788_006_601_000,
      })
    );
    await act(flush);
    const history = result.current.snapshot.history.data;
    expect(history).toMatchObject({
      generated_at: historyPayload.generated_at,
      window_start: '2026-08-29T12:00:00Z',
      window_end: '2026-08-29T12:30:01Z',
      range_seconds: historyPayload.range_seconds,
      step_seconds: historyPayload.step_seconds,
    });
    expect(history?.series.map((series) => series.metric)).toEqual([
      'latitude_degrees',
      'longitude_degrees',
      'latency_ms',
      'throughput_down_mbps',
      'throughput_up_mbps',
      'packet_loss_percent',
    ]);
    for (const series of history?.series ?? []) {
      expect(series.samples).toHaveLength(1801);
      expect(series.samples.at(0)?.timestamp).toBe(
        '2026-08-29T12:00:01.000001Z'
      );
      expect(series.samples.at(-1)?.timestamp).toBe(
        '2026-08-29T12:00:01.001801Z'
      );
    }
    expect(
      history?.series.some((series) =>
        ['altitude', 'obstruction_percent'].includes(series.metric)
      )
    ).toBe(false);
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
