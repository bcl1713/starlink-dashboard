// @vitest-environment jsdom

import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchHistory } from '../../services/monitoring';
import { useOverviewData } from './useOverviewData';
import {
  defaults,
  deferred,
  history,
  now,
  resetOverviewMocks,
  setVisibility,
} from './useOverviewData.testSupport';

vi.mock('../../services/monitoring', async (loadOriginal) => {
  const original =
    await loadOriginal<typeof import('../../services/monitoring')>();
  return {
    ...original,
    fetchApplicablePois: vi.fn(),
    fetchGroundEntryPoint: vi.fn(),
    fetchHistory: vi.fn(),
    fetchMapOverlays: vi.fn(),
    fetchRadarMetadata: vi.fn(),
    fetchStatus: vi.fn(),
  };
});

afterEach(resetOverviewMocks);

describe('useOverviewData gap recovery', () => {
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
        expect(fetchHistory).toHaveBeenCalledTimes(1);
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
        expect(fetchHistory).toHaveBeenCalledTimes(1);
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

  it('repairs a later gap generation once and removes recovery listeners', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    defaults();
    const { unmount } = renderHook(() => useOverviewData());
    await act(async () => Promise.resolve());

    window.dispatchEvent(new Event('offline'));
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    window.dispatchEvent(new Event('online'));
    await act(async () => Promise.resolve());
    expect(fetchHistory).toHaveBeenCalledTimes(2);

    setVisibility('hidden');
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    setVisibility('visible');
    setVisibility('visible');
    await act(async () => Promise.resolve());
    expect(fetchHistory).toHaveBeenCalledTimes(3);

    unmount();
    window.dispatchEvent(new Event('offline'));
    window.dispatchEvent(new Event('online'));
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    expect(fetchHistory).toHaveBeenCalledTimes(3);
  });
});
