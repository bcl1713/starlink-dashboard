import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useOverviewData } from './useOverviewData';
import {
  cloneFixture,
  createOverviewServices,
  flushOverviewEffects,
  poiPayload,
  statusPayload,
} from './overview-test-harness';

describe('useOverviewData announcements', () => {
  it('announces true stale-to-error as the entered error state', async () => {
    vi.useFakeTimers();
    try {
      let now = 1_777_294_800_000;
      const svc = createOverviewServices({
        getStatus: vi
          .fn()
          .mockResolvedValueOnce({
            ...cloneFixture(statusPayload),
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
      await act(flushOverviewEffects);
      expect(result.current.snapshot.telemetry.phase).toBe('stale');
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flushOverviewEffects);
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
        ...cloneFixture(statusPayload),
        timestamp: '2026-04-27T13:00:00Z',
      };
      const svc = createOverviewServices({
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
      await act(flushOverviewEffects);
      expect(result.current.snapshot.telemetry.freshness).toBe('fresh');
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flushOverviewEffects);
      expect(result.current.snapshot.telemetry.phase).toBe('error');
      expect(result.current.snapshot.announcement).toBe(
        'Telemetry refresh failed.'
      );
      now += 6000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flushOverviewEffects);
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
      const svc = createOverviewServices({
        getSatelliteETAs: vi
          .fn()
          .mockRejectedValueOnce(new Error('satellite down'))
          .mockResolvedValue(cloneFixture(poiPayload)),
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
      await act(flushOverviewEffects);
      expect(result.current.snapshot.announcement).toBe(
        'Satellite ETAs refresh failed.'
      );
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flushOverviewEffects);
      expect(result.current.snapshot.satellites.phase).toBe('ready');
      expect(result.current.snapshot.missionEvents.phase).toBe('error');
      expect(result.current.snapshot.announcement).toBe(
        'Satellite ETAs recovered.'
      );
      const repeated = result.current.snapshot.announcement;
      now += 1000;
      await act(async () => vi.advanceTimersByTime(1000));
      await act(flushOverviewEffects);
      expect(result.current.snapshot.announcement).toBe(repeated);
    } finally {
      vi.useRealTimers();
    }
  });

  it('emits exact priority announcements with deduplication', async () => {
    const svc = createOverviewServices({
      getStatus: vi
        .fn()
        .mockRejectedValueOnce(new Error('down'))
        .mockResolvedValueOnce(cloneFixture(statusPayload)),
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
    expect(result.current.snapshot.announcement).toBe(
      'Telemetry refresh failed.'
    );
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.announcement).toBe(
      'Manual refresh complete.'
    );
  });
});
