// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  fetchApplicablePois,
  fetchGroundEntryPoint,
  fetchHistory,
  fetchStatus,
} from '../../services/monitoring';
import { metricOrder } from '../../services/monitoring';
import { useOverviewData } from './useOverviewData';

vi.mock('../../services/monitoring', async (loadOriginal) => {
  const original =
    await loadOriginal<typeof import('../../services/monitoring')>();
  return {
    ...original,
    fetchApplicablePois: vi.fn(),
    fetchGroundEntryPoint: vi.fn(),
    fetchHistory: vi.fn(),
    fetchStatus: vi.fn(),
  };
});

const now = new Date('2026-09-02T12:00:00Z');
const status = (latency = 20) => ({
  source: 'live' as const,
  timestamp: '2026-09-02T11:59:50Z',
  observed_at: '2026-09-02T11:59:50Z',
  received_at: '2026-09-02T11:59:51Z',
  position: { latitude: 41, longitude: -96, altitude: 1, speed: 0, heading: 0 },
  network: {
    latency_ms: latency,
    throughput_down_mbps: 100,
    throughput_up_mbps: 10,
    packet_loss_percent: 1,
  },
  obstruction: { obstruction_percent: 2 },
  environmental: {
    signal_quality_percent: 98,
    uptime_seconds: 10,
    temperature_celsius: null,
  },
});

const history = () => ({
  generated_at: now.toISOString(),
  window_start: '2026-09-02T11:30:00Z',
  window_end: now.toISOString(),
  range_seconds: 1800,
  step_seconds: 1,
  series: metricOrder.map((metric) => ({
    metric,
    samples:
      metric === 'latency_ms'
        ? [{ timestamp: '2026-09-02T11:59:59Z', value: 999 }]
        : metric === 'packet_loss_percent'
          ? [
              { timestamp: '2026-09-02T11:54:59Z', value: 88 },
              { timestamp: '2026-09-02T11:59:59Z', value: 9 },
            ]
          : [],
  })),
});

const poi = {
  poi_id: 'poi-1',
  name: 'Airport',
  category: null,
  eta_seconds: 60,
  distance_meters: 1000,
  active: true,
  latitude: 41,
  longitude: -96,
};
const gep = {
  available: true,
  observed_at: now.toISOString(),
  generated_at: now.toISOString(),
  display: 'Omaha',
  city: 'Omaha',
  region: 'Nebraska',
  country: 'US',
  latitude: 41,
  longitude: -96,
};

function setVisibility(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: state,
  });
  document.dispatchEvent(new Event('visibilitychange'));
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function defaults() {
  vi.mocked(fetchStatus).mockResolvedValue(status());
  vi.mocked(fetchHistory).mockResolvedValue(history());
  vi.mocked(fetchGroundEntryPoint).mockResolvedValue(gep);
  vi.mocked(fetchApplicablePois).mockResolvedValue([poi]);
}

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: 'visible',
  });
});

describe('useOverviewData lane ownership', () => {
  it('keeps live current values while newer backfill drives five-minute aggregates', async () => {
    vi.setSystemTime(now);
    defaults();
    const { result, unmount } = renderHook(() => useOverviewData());

    await waitFor(() => expect(result.current.status).not.toBeNull());
    await waitFor(() => expect(result.current.summaries.latency.max).toBe(999));

    expect(result.current.status?.network.latency_ms).toBe(20);
    expect(result.current.status?.network.packet_loss_percent).toBe(1);
    expect(result.current.summaries.packetLoss.max).toBe(9);
    unmount();
  });

  it('lets status and POIs advance while GEP is pending then localizes recovery', async () => {
    vi.setSystemTime(now);
    let rejectGep: ((reason?: unknown) => void) | undefined;
    vi.mocked(fetchGroundEntryPoint)
      .mockImplementationOnce(
        () => new Promise((_, reject) => (rejectGep = reject))
      )
      .mockResolvedValueOnce(gep);
    vi.mocked(fetchStatus).mockResolvedValue(status());
    vi.mocked(fetchHistory).mockResolvedValue(history());
    vi.mocked(fetchApplicablePois).mockResolvedValue([poi]);
    const { result, unmount } = renderHook(() => useOverviewData());

    await waitFor(() => expect(result.current.status).not.toBeNull());
    await waitFor(() => expect(result.current.pois).toHaveLength(1));
    expect(result.current.gepState.loading).toBe(true);
    expect(result.current.poiState.error).toBeNull();

    await act(async () => rejectGep?.(new Error('private 203.0.113.8')));
    await waitFor(() => expect(result.current.gepState.error).toBeTruthy());
    expect(result.current.poiState.error).toBeNull();

    await act(async () => result.current.refreshGep());
    expect(result.current.gep?.display).toBe('Omaha');
    expect(result.current.gepState.error).toBeNull();
    expect(result.current.gepState.recoveredAt).not.toBeNull();
    unmount();
  });

  it('retains last-good POIs on a localized refresh failure', async () => {
    vi.setSystemTime(now);
    defaults();
    vi.mocked(fetchApplicablePois)
      .mockResolvedValueOnce([poi])
      .mockRejectedValueOnce(new Error('failed'));
    const { result, unmount } = renderHook(() => useOverviewData());
    await waitFor(() => expect(result.current.pois).toHaveLength(1));

    await act(async () => result.current.refreshPois());
    expect(result.current.pois).toEqual([poi]);
    expect(result.current.poiState.error).toBe(
      'Points of interest unavailable'
    );
    expect(result.current.gepState.error).toBeNull();
    unmount();
  });

  it('aborts the active production-hook request on unmount without replay', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    let statusSignal: AbortSignal | undefined;
    vi.mocked(fetchStatus).mockImplementation(
      (signal) =>
        new Promise((_resolve, reject) => {
          statusSignal = signal;
          signal?.addEventListener('abort', () => reject(new Error('aborted')));
        })
    );
    vi.mocked(fetchHistory).mockResolvedValue(history());
    vi.mocked(fetchGroundEntryPoint).mockResolvedValue(gep);
    vi.mocked(fetchApplicablePois).mockResolvedValue([poi]);
    const { unmount } = renderHook(() => useOverviewData());
    await act(async () => Promise.resolve());

    expect(statusSignal?.aborted).toBe(false);
    unmount();
    expect(statusSignal?.aborted).toBe(true);
    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(fetchStatus).toHaveBeenCalledTimes(1);
  });

  it('repairs a long gap that begins before mounting hidden', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    defaults();
    setVisibility('hidden');
    const { unmount } = renderHook(() => useOverviewData());
    await act(async () => Promise.resolve());

    await act(async () => vi.advanceTimersByTimeAsync(6000));
    setVisibility('visible');
    await act(async () => Promise.resolve());

    expect(fetchHistory).toHaveBeenCalledTimes(2);
    unmount();
  });

  it.each(['online-first', 'visible-first'] as const)(
    'coalesces differing hidden/offline starts when %s recovers first',
    async (recoveryOrder) => {
      vi.useFakeTimers();
      vi.setSystemTime(now);
      defaults();
      const { unmount } = renderHook(() => useOverviewData());
      await act(async () => Promise.resolve());
      expect(fetchHistory).toHaveBeenCalledTimes(1);

      if (recoveryOrder === 'online-first') {
        setVisibility('hidden');
        await act(async () => vi.advanceTimersByTimeAsync(1000));
        window.dispatchEvent(new Event('offline'));
        await act(async () => vi.advanceTimersByTimeAsync(5001));
        window.dispatchEvent(new Event('online'));
        window.dispatchEvent(new Event('online'));
        await act(async () => Promise.resolve());
        setVisibility('visible');
        setVisibility('visible');
      } else {
        window.dispatchEvent(new Event('offline'));
        await act(async () => vi.advanceTimersByTimeAsync(1000));
        setVisibility('hidden');
        await act(async () => vi.advanceTimersByTimeAsync(5001));
        setVisibility('visible');
        setVisibility('visible');
        await act(async () => Promise.resolve());
        window.dispatchEvent(new Event('online'));
        window.dispatchEvent(new Event('online'));
      }
      await act(async () => Promise.resolve());

      expect(fetchHistory).toHaveBeenCalledTimes(2);
      unmount();
    }
  );

  it('queues one coalesced gap repair behind pending history', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const bootstrap = deferred<ReturnType<typeof history>>();
    defaults();
    vi.mocked(fetchHistory)
      .mockReturnValueOnce(bootstrap.promise)
      .mockResolvedValueOnce(history());
    const { unmount } = renderHook(() => useOverviewData());
    await act(async () => Promise.resolve());

    setVisibility('hidden');
    window.dispatchEvent(new Event('offline'));
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    window.dispatchEvent(new Event('online'));
    setVisibility('visible');
    expect(fetchHistory).toHaveBeenCalledTimes(1);

    await act(async () => {
      bootstrap.resolve(history());
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(fetchHistory).toHaveBeenCalledTimes(2);
    window.dispatchEvent(new Event('online'));
    setVisibility('visible');
    await act(async () => Promise.resolve());
    expect(fetchHistory).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('does not repair a short coalesced gap', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    defaults();
    const { unmount } = renderHook(() => useOverviewData());
    await act(async () => Promise.resolve());

    window.dispatchEvent(new Event('offline'));
    setVisibility('hidden');
    await act(async () => vi.advanceTimersByTimeAsync(4999));
    window.dispatchEvent(new Event('online'));
    setVisibility('visible');
    await act(async () => Promise.resolve());

    expect(fetchHistory).toHaveBeenCalledTimes(1);
    unmount();
  });
});
