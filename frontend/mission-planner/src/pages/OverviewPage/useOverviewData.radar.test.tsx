import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SOURCE_ORDER } from './overview-sources';
import { useOverviewData } from './useOverviewData';
import {
  cloneFixture,
  createCallCountingServices,
  createOverviewServices,
  deferred,
  flushOverviewEffects,
  statusPayload,
} from './overview-test-harness';

describe('useOverviewData radar orchestration', () => {
  it('projects initially disabled radar as unavailable without request or error', () => {
    const { calls, svc } = createCallCountingServices();
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: false,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );

    expect(calls).toEqual([]);
    expect(result.current.snapshot.radar).toMatchObject({
      availability: 'unavailable',
      phase: 'unavailable',
      freshness: 'unknown',
      sourceTimestamp: null,
      transportLastAttemptAt: null,
      transportLastSuccessAt: null,
      pending: false,
      paused: false,
      error: null,
    });
    expect(result.current.snapshot.radar.data).toBeUndefined();
  });

  it('leaves initial enabled radar and empty sources loading before bootstrap', () => {
    const { calls, svc } = createCallCountingServices();
    const { result } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => 1_777_294_800_000,
      })
    );

    expect(calls).toEqual([]);
    expect(result.current.snapshot.initialState).toBe('initial-loading');
    expect(result.current.snapshot.manualResult).toBe('idle');
    expect(result.current.snapshot.globalTransportLastSuccessAt).toBeNull();
    expect(result.current.snapshot.announcement).toBeNull();
    for (const source of SOURCE_ORDER) {
      expect(result.current.snapshot[source]).toMatchObject({
        availability: 'unknown',
        phase: 'initial-loading',
        freshness: 'unknown',
        sourceTimestamp: null,
        transportLastAttemptAt: null,
        transportLastSuccessAt: null,
        pending: false,
        paused: false,
        error: null,
      });
      expect(result.current.snapshot[source].data).toBeUndefined();
    }
  });

  it('handles radar reports without HTTP, retains data while disabled, and ignores invalid now', async () => {
    let now = 1_777_294_800_000;
    const svc = createOverviewServices();
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
    await act(flushOverviewEffects);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1788004800',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1788004800'
    );
    expect(result.current.snapshot.radar.sourceTimestamp).toBe('1788004800');
    expect(result.current.snapshot.radar.transportLastSuccessAt).toBe(now);
    now = Number.NaN;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: false,
        error: new Error('radar failed'),
      })
    );
    expect(result.current.snapshot.radar.error).toBeNull();
    rerender({ radarEnabled: false });
    await act(flushOverviewEffects);
    act(() =>
      result.current.controller.reportRadarResult(token, {
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

  it('makes retained radar callbacks no-ops after unmount', async () => {
    const svc = createOverviewServices();
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
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
    const controller = result.current.controller;
    const token = controller.radarRefreshToken;
    unmount();
    act(() => controller.retryRadar());
    act(() =>
      controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    expect(errorSpy).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });

  it('does not sample now or inspect hostile retained radar reports after unmount', async () => {
    let nowCalls = 0;
    let okAccessed = false;
    let frameAccessed = false;
    let errorAccessed = false;
    const svc = createOverviewServices();
    const { result, unmount } = renderHook(() =>
      useOverviewData({
        cadence: 'paused',
        poiFilter: '',
        radarEnabled: true,
        services: svc,
        now: () => {
          nowCalls += 1;
          return 1_777_294_800_000;
        },
      })
    );
    await act(flushOverviewEffects);
    const controller = result.current.controller;
    const token = controller.radarRefreshToken;
    const beforeUnmountNowCalls = nowCalls;
    const hostileOk = Object.defineProperty({}, 'ok', {
      get() {
        okAccessed = true;
        throw new Error('ok getter');
      },
    }) as { readonly ok: true; readonly frameTimestamp: string };
    const hostileFrame = Object.defineProperty({ ok: true }, 'frameTimestamp', {
      get() {
        frameAccessed = true;
        throw new Error('frame getter');
      },
    }) as { readonly ok: true; readonly frameTimestamp: string };
    const hostileError = Object.defineProperty({ ok: false }, 'error', {
      get() {
        errorAccessed = true;
        throw new Error('error getter');
      },
    }) as { readonly ok: false; readonly error: unknown };
    unmount();
    act(() => controller.reportRadarResult(token, hostileOk));
    act(() => controller.reportRadarResult(token, hostileFrame));
    act(() => controller.reportRadarResult(token, hostileError));
    expect(nowCalls).toBe(beforeUnmountNowCalls);
    expect(okAccessed).toBe(false);
    expect(frameAccessed).toBe(false);
    expect(errorAccessed).toBe(false);
  });

  it('restores radar availability after re-enable and ignores stale toggle reports', async () => {
    let now = 1_777_294_800_000;
    const svc = createOverviewServices();
    const { result, rerender } = renderHook(
      ({ radarEnabled }) =>
        useOverviewData({
          cadence: 1,
          poiFilter: '',
          radarEnabled,
          services: svc,
          now: () => now,
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flushOverviewEffects);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    expect(result.current.snapshot.radar.availability).toBe('available');
    rerender({ radarEnabled: false });
    await act(flushOverviewEffects);
    expect(result.current.snapshot.radar.availability).toBe('unavailable');
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294801',
      })
    );
    expect(result.current.snapshot.radar.data?.frameTimestamp).toBe(
      '1777294800'
    );
    now += 10_000;
    rerender({ radarEnabled: true });
    await act(flushOverviewEffects);
    expect(result.current.snapshot.radar.availability).toBe('available');
    expect(result.current.snapshot.radar.freshness).toBe('stale');
  });

  it('restores retained radar availability on re-enable even when now is invalid', async () => {
    let now = 1_777_294_800_000;
    const svc = createOverviewServices();
    const { result, rerender } = renderHook(
      ({ radarEnabled }) =>
        useOverviewData({
          cadence: 1,
          poiFilter: '',
          radarEnabled,
          services: svc,
          now: () => now,
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flushOverviewEffects);
    const token = result.current.controller.radarRefreshToken;
    act(() =>
      result.current.controller.reportRadarResult(token, {
        ok: true,
        frameTimestamp: '1777294800',
      })
    );
    expect(result.current.snapshot.radar.availability).toBe('available');
    rerender({ radarEnabled: false });
    now = Number.NaN;
    await act(flushOverviewEffects);
    rerender({ radarEnabled: true });
    await act(flushOverviewEffects);
    expect(result.current.snapshot.radar.availability).toBe('available');
    expect(result.current.snapshot.radar.freshness).toBe('fresh');
  });

  it('increments radar token only for actual manual starts and enabled retry', async () => {
    let throwNow = false;
    const gate = deferred<typeof statusPayload>();
    const svc = createOverviewServices({
      getStatus: vi
        .fn()
        .mockResolvedValueOnce(cloneFixture(statusPayload))
        .mockImplementationOnce(() => gate.promise),
    });
    const { result, rerender } = renderHook(
      ({ radarEnabled }) =>
        useOverviewData({
          cadence: 'paused',
          poiFilter: '',
          radarEnabled,
          services: svc,
          now: () => {
            if (throwNow) throw new Error('now inspected');
            return 1_777_294_800_000;
          },
        }),
      { initialProps: { radarEnabled: true } }
    );
    await act(flushOverviewEffects);
    const oldToken = result.current.controller.radarRefreshToken;
    expect(oldToken).toBe(0);
    const first = result.current.controller.manualRefresh();
    const second = result.current.controller.manualRefresh();
    expect(second).toBe(first);
    await act(flushOverviewEffects);
    expect(result.current.controller.radarRefreshToken).toBe(1);
    let inspected = false;
    const hostile = Object.defineProperty({ ok: true }, 'frameTimestamp', {
      get() {
        inspected = true;
        throw new Error('frame inspected');
      },
    }) as { readonly ok: true; readonly frameTimestamp: string };
    const before = result.current.snapshot;
    throwNow = true;
    act(() => result.current.controller.reportRadarResult(oldToken, hostile));
    expect(result.current.snapshot).toBe(before);
    expect(inspected).toBe(false);
    throwNow = false;
    gate.resolve(cloneFixture(statusPayload));
    await act(async () => first);
    act(() => result.current.controller.retryRadar());
    expect(result.current.controller.radarRefreshToken).toBe(2);
    rerender({ radarEnabled: false });
    await act(flushOverviewEffects);
    act(() => result.current.controller.retryRadar());
    expect(result.current.controller.radarRefreshToken).toBe(2);
  });
});
