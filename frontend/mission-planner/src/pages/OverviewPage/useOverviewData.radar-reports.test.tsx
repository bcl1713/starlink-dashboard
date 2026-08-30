import { act, renderHook } from '@testing-library/react';
import axios from 'axios';
import { describe, expect, it } from 'vitest';

import { useOverviewData } from './useOverviewData';
import {
  createOverviewServices,
  flushOverviewEffects,
} from './overview-test-harness';

describe('useOverviewData radar report validation', () => {
  it('clears radar error on enabled retry and invalidates prior reports', async () => {
    const svc = createOverviewServices();
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices();
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices();
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 1,
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices();
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
    await act(flushOverviewEffects);
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
    const svc = createOverviewServices();
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
    await act(flushOverviewEffects);
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
    await act(flushOverviewEffects);
    act(() =>
      result.current.controller.reportRadarResult(initial, {
        ok: true,
        frameTimestamp: '1777294801',
      })
    );
    rerender({ radarEnabled: true });
    await act(flushOverviewEffects);
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
});
