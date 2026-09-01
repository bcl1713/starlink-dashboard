import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  createOverviewServices,
  deferred,
  flushOverviewEffects,
  historyPayload,
  statusPayload,
} from './overview-test-harness';
import { useOverviewData } from './useOverviewData';

describe('useOverviewData continuity', () => {
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
      let historyScheduleNow = 0;
      const statusGate = deferred<typeof statusPayload>();
      const historyGate = deferred<typeof historyPayload>();
      const svc = createOverviewServices({
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
          historyScheduleNow: () => historyScheduleNow,
        })
      );
      await act(flushOverviewEffects);
      if (order === 'telemetry-first') {
        statusGate.resolve({
          ...structuredClone(statusPayload),
          timestamp: telemetryTime,
        });
        await act(flushOverviewEffects);
        expect(rendered.result.current.snapshot.history.data).toBeUndefined();
        historyGate.resolve(firstServerHistory);
      } else {
        historyGate.resolve(firstServerHistory);
        await act(flushOverviewEffects);
        expect(rendered.result.current.snapshot.history.data).toBeUndefined();
        statusGate.resolve({
          ...structuredClone(statusPayload),
          timestamp: telemetryTime,
        });
      }
      await act(flushOverviewEffects);
      return {
        ...rendered,
        advanceToNextCycle() {
          nowMs = 1_788_028_205_000;
          historyScheduleNow = 5_000;
        },
        advanceHistorySchedule() {
          historyScheduleNow = 10_000;
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
      rendered.advanceHistorySchedule();
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
    const svc = createOverviewServices({
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
    await act(flushOverviewEffects);
    expect(result.current.snapshot.history.data).toBeUndefined();
    expect(result.current.snapshot.history.transportLastSuccessAt).toBeNull();
    expect(result.current.snapshot.history.transportLastAttemptAt).toBeNull();
    expect(result.current.snapshot.history.availability).toBe('unknown');
  });
});
