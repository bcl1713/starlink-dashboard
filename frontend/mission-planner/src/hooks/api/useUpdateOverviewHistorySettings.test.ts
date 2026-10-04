/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { useOverviewHistorySettings } from './useOverviewHistorySettings';
import { useUpdateOverviewHistorySettings } from './useUpdateOverviewHistorySettings';
import { useOverviewHistory } from './useOverviewHistory';

vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
const key = ['overview-history-settings'];
const original = { window_seconds: 300 };
const draft = 600;
const saved = { window_seconds: 600 };
const later = { window_seconds: 900 };
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}
let client: QueryClient;
let wrapper: (props: PropsWithChildren) => ReturnType<typeof createElement>;
beforeEach(() => {
  vi.resetAllMocks();
  client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity, retry: false } },
  });
  wrapper = ({ children }) =>
    createElement(QueryClientProvider, { client }, children);
  client.setQueryData(key, original);
});
afterEach(() => {
  cleanup();
  client.clear();
});

describe('useUpdateOverviewHistorySettings confirmed state', () => {
  it.each(['resolve', 'reject'] as const)(
    'cancels reads before and during PUT and ignores their late %s',
    async (completion) => {
      const readA = deferred<{ data: typeof original }>();
      const readB = deferred<{ data: typeof original }>();
      const put = deferred<{ data: typeof saved }>();
      const fresh = deferred<{ data: typeof saved }>();
      vi.mocked(apiClient.get)
        .mockReturnValueOnce(readA.promise)
        .mockReturnValueOnce(readB.promise)
        .mockReturnValue(fresh.promise);
      vi.mocked(apiClient.put).mockReturnValueOnce(put.promise);
      const viewer = renderHook(() => useOverviewHistorySettings(true), {
        wrapper,
      });
      const editor = renderHook(useUpdateOverviewHistorySettings, { wrapper });
      await waitFor(() => expect(viewer.result.current.isFetching).toBe(true));
      const signalA = vi.mocked(apiClient.get).mock.calls[0][1]?.signal;
      act(() => editor.result.current.mutate(draft));
      await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));
      expect(signalA?.aborted).toBe(true);
      expect(client.getQueryData(key)).toEqual(original);
      act(() => {
        void viewer.result.current.refetch();
      });
      await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(2));
      const signalB = vi.mocked(apiClient.get).mock.calls[1][1]?.signal;
      await act(async () => {
        put.resolve({ data: saved });
      });
      expect(signalB?.aborted).toBe(true);
      // Full server response wins, before the invalidation read completes.
      expect(client.getQueryData(key)).toEqual(saved);
      await act(async () => {
        if (completion === 'resolve') {
          readA.resolve({ data: original });
          readB.resolve({ data: original });
        } else {
          readA.reject(new Error('late aborted read A'));
          readB.reject(new Error('late aborted read B'));
        }
      });
      await waitFor(() => expect(viewer.result.current.data).toEqual(saved));
      expect(viewer.result.current.isError).toBe(false);
      await act(async () => {
        fresh.resolve({ data: saved });
      });
      expect(client.getQueryData(key)).toEqual(saved);
    }
  );

  it('cancels a read begun during PUT and publishes even if the editor unmounts', async () => {
    const stale = deferred<{ data: typeof original }>();
    const fresh = deferred<{ data: typeof saved }>();
    const put = deferred<{ data: typeof saved }>();
    vi.mocked(apiClient.get)
      .mockReturnValueOnce(stale.promise)
      .mockReturnValue(fresh.promise);
    vi.mocked(apiClient.put).mockReturnValueOnce(put.promise);
    const editor = renderHook(useUpdateOverviewHistorySettings, { wrapper });
    act(() => editor.result.current.mutate(draft));
    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));
    const viewer = renderHook(() => useOverviewHistorySettings(true), {
      wrapper,
    });
    await waitFor(() => expect(viewer.result.current.isFetching).toBe(true));
    const signal = vi.mocked(apiClient.get).mock.calls[0][1]?.signal;
    editor.unmount();
    await act(async () => {
      put.resolve({ data: saved });
    });
    expect(signal?.aborted).toBe(true);
    expect(client.getQueryData(key)).toEqual(saved);
    await act(async () => {
      stale.resolve({ data: original });
    });
    await waitFor(() => expect(viewer.result.current.data).toEqual(saved));
    await act(async () => {
      fresh.resolve({ data: saved });
    });
  });

  it('serializes separate editors and cancels the preceding save’s refetch before the queued PUT', async () => {
    const firstPut = deferred<{ data: typeof saved }>();
    const refetch = deferred<{ data: typeof saved }>();
    const secondPut = deferred<{ data: typeof later }>();
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: original })
      .mockReturnValueOnce(refetch.promise)
      .mockResolvedValue({ data: later });
    vi.mocked(apiClient.put)
      .mockReturnValueOnce(firstPut.promise)
      .mockReturnValueOnce(secondPut.promise);
    const viewer = renderHook(() => useOverviewHistorySettings(true), {
      wrapper,
    });
    await waitFor(() => expect(viewer.result.current.isFetching).toBe(false));
    const first = renderHook(useUpdateOverviewHistorySettings, { wrapper });
    const second = renderHook(useUpdateOverviewHistorySettings, { wrapper });
    act(() => {
      first.result.current.mutate(draft);
      second.result.current.mutate(900);
    });
    await waitFor(() => expect(second.result.current.isPaused).toBe(true));
    expect(apiClient.put).toHaveBeenCalledTimes(1);
    await act(async () => {
      firstPut.resolve({ data: saved });
    });
    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(2));
    expect(client.getQueryData(key)).toEqual(saved);
    expect(vi.mocked(apiClient.get).mock.calls[1][1]?.signal?.aborted).toBe(
      true
    );
    await act(async () => {
      secondPut.resolve({ data: later });
    });
    await waitFor(() => expect(viewer.result.current.data).toEqual(later));
    await act(async () => {
      refetch.resolve({ data: saved });
    });
    expect(client.getQueryData(key)).toEqual(later);
  });

  it('never confirms a rejected draft and allows the next save to recover', async () => {
    client.setQueryData(key, saved);
    vi.mocked(apiClient.put).mockRejectedValueOnce(new Error('save failed'));
    const editor = renderHook(useUpdateOverviewHistorySettings, { wrapper });
    act(() => editor.result.current.mutate(3600));
    await waitFor(() => expect(editor.result.current.isError).toBe(true));
    expect(client.getQueryData(key)).toEqual(saved);
    expect(apiClient.get).not.toHaveBeenCalled();
    vi.mocked(apiClient.put).mockResolvedValueOnce({ data: later });
    await act(async () => {
      await editor.result.current.mutateAsync(900);
    });
    expect(client.getQueryData(key)).toEqual(later);
  });

  it('invalidates the history observer after a confirmed window save without relabeling its old bundle', async () => {
    const oldBundle = {
      window_seconds: 300,
      start_timestamp_seconds: 0,
      end_timestamp_seconds: 300,
      step_seconds: 5,
      series: {},
    };
    const newBundle = { ...oldBundle, window_seconds: 600 };
    const fresh = deferred<{ data: typeof newBundle }>();
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: oldBundle })
      .mockReturnValue(fresh.promise);
    vi.mocked(apiClient.put).mockResolvedValueOnce({ data: saved });
    const history = renderHook(useOverviewHistory, { wrapper });
    await waitFor(() => {
      expect(history.result.current.data).toEqual(oldBundle);
      expect(history.result.current.isFetching).toBe(false);
    });
    const editor = renderHook(useUpdateOverviewHistorySettings, { wrapper });
    await act(async () => {
      await editor.result.current.mutateAsync(600);
    });
    expect(client.getQueryData(key)).toEqual({ window_seconds: 600 });
    expect(history.result.current.data).toEqual(oldBundle);
    expect(history.result.current.data?.window_seconds).not.toBe(600);
    await waitFor(() => expect(history.result.current.isFetching).toBe(true));
    await act(async () => {
      fresh.resolve({ data: newBundle });
    });
    await waitFor(() =>
      expect(history.result.current.data?.window_seconds).toBe(600)
    );
  });
});
