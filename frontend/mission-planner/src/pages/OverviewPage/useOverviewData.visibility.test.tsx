import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { OverviewPOIFilter } from '../../types/monitoring';
import { useOverviewData } from './useOverviewData';
import {
  createCallCountingServices,
  createOverviewServices,
  flushOverviewEffects,
} from './overview-test-harness';

describe('useOverviewData visibility', () => {
  it('keeps the default visibility listener stable across snapshot renders', async () => {
    const { svc } = createCallCountingServices();
    const add = vi.spyOn(document, 'addEventListener');
    const remove = vi.spyOn(document, 'removeEventListener');
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
    act(() =>
      result.current.controller.reportRadarResult(0, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    await act(async () => result.current.controller.manualRefresh());
    expect(
      add.mock.calls.filter(([event]) => event === 'visibilitychange')
    ).toHaveLength(1);
    expect(
      remove.mock.calls.filter(([event]) => event === 'visibilitychange')
    ).toHaveLength(0);
    unmount();
    expect(
      remove.mock.calls.filter(([event]) => event === 'visibilitychange')
    ).toHaveLength(1);
    add.mockRestore();
    remove.mockRestore();
  });

  it('runs an explicit manual refresh hidden or paused and preserves controller identity', async () => {
    const { svc } = createCallCountingServices();
    const visibility = {
      isHidden: () => true,
      subscribe: vi.fn(() => vi.fn()),
    };
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: 'waypoint' as OverviewPOIFilter,
        radarEnabled: false,
        services: svc,
        visibility,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flushOverviewEffects);
    const manual = result.current.controller.manualRefresh;
    await act(async () => manual());
    expect(result.current.controller.manualRefresh).toBe(manual);
    expect(result.current.snapshot.manualResult).toBe('success');
    expect(svc.getStatus).toHaveBeenCalledTimes(2);
  });

  it('fails open for hostile visibility and swallows cleanup failures', async () => {
    const svc = createOverviewServices();
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
    await act(flushOverviewEffects);
    expect(svc.getStatus).toHaveBeenCalledTimes(1);
    expect(() => unmount()).not.toThrow();
  });
});
