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
import type { OverviewDataServices } from './overview-data-types';
import { useOverviewData } from './useOverviewData';

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
    await act(async () => Promise.resolve());
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
    await act(async () => Promise.resolve());
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
    await act(async () => Promise.resolve());
    act(() =>
      result.current.controller.reportRadarResult({
        ok: true,
        frameTimestamp: '1788004800',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1788004800'
    );
    expect(result.current.snapshot.radar.sourceTimestamp).toBe(
      '2026-08-29T12:00:00Z'
    );
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
    await act(async () => Promise.resolve());
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
    await act(async () => Promise.resolve());
    expect(result.current.snapshot.announcement).toBe(
      'Telemetry refresh failed.'
    );
    await act(async () => result.current.controller.manualRefresh());
    expect(result.current.snapshot.announcement).toBe(
      'Manual refresh complete.'
    );
  });
});
