// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  fetchApplicablePois,
  fetchGroundEntryPoint,
  fetchHistory,
  fetchStatus,
} from '../../services/monitoring';
import { useOverviewData } from './useOverviewData';
import {
  defaults,
  gep,
  history,
  now,
  poi,
  resetOverviewMocks,
  status,
} from './useOverviewData.testSupport';

const { fetchRadarMetadata } = vi.hoisted(() => ({
  fetchRadarMetadata: vi.fn(),
}));

vi.mock('../../services/monitoring', async (loadOriginal) => {
  const original =
    await loadOriginal<typeof import('../../services/monitoring')>();
  return {
    ...original,
    fetchApplicablePois: vi.fn(),
    fetchGroundEntryPoint: vi.fn(),
    fetchHistory: vi.fn(),
    fetchMapOverlays: vi.fn(),
    fetchRadarMetadata,
    fetchStatus: vi.fn(),
  };
});

afterEach(resetOverviewMocks);

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

  it('starts core overview refreshes without requesting deferred radar metadata', async () => {
    vi.setSystemTime(now);
    defaults();
    const { result, unmount } = renderHook(() => useOverviewData());

    await waitFor(() => expect(result.current.status).not.toBeNull());
    await waitFor(() => expect(result.current.pois).toHaveLength(1));
    expect(result.current.statusMessage).toContain('Updated');
    expect(fetchRadarMetadata).not.toHaveBeenCalled();
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
});
