import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useOverviewData } from './useOverviewData';
import {
  createOverviewServices,
  flushOverviewEffects,
  historyPayload,
  statusPayload,
} from './overview-test-harness';

describe('useOverviewData history reconciliation', () => {
  it('keeps same-cycle telemetry when server history also completes', async () => {
    const telemetryTime = '2026-08-29T18:00:04Z';
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
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
