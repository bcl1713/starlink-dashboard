/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { useOverviewLinkSettings } from './useOverviewLinkSettings';
import { useUpdateOverviewLinkSettings } from './useUpdateOverviewLinkSettings';

vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
const key = ['overview-link-settings'];
const original = {
  starshield_link_enabled: true,
  x_band_link_enabled: true,
  orbital_traffic_enabled: true,
  aircraft_history_enabled: true,
};
const saved = {
  starshield_link_enabled: false,
  x_band_link_enabled: true,
  orbital_traffic_enabled: false,
  aircraft_history_enabled: true,
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
let client: QueryClient;
let wrapper: (props: PropsWithChildren) => ReturnType<typeof createElement>;
beforeEach(() => {
  vi.resetAllMocks();
  client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
  wrapper = ({ children }) =>
    createElement(QueryClientProvider, { client }, children);
});
afterEach(() => {
  cleanup();
  client.clear();
});

describe('useUpdateOverviewLinkSettings', () => {
  it.each([false, true])(
    'late_get_cannot_restore_orbital_after_save with unmount=%s',
    async (unmountBeforeSave) => {
      const stale = deferred<{ data: typeof original }>();
      const put = deferred<{ data: typeof saved }>();
      const fresh = deferred<{ data: typeof saved }>();
      client.setQueryData(key, original);
      vi.mocked(apiClient.get)
        .mockReturnValueOnce(stale.promise)
        .mockReturnValue(fresh.promise);
      vi.mocked(apiClient.put).mockReturnValue(put.promise);
      const editor = renderHook(
        () => ({
          query: useOverviewLinkSettings(),
          update: useUpdateOverviewLinkSettings(),
        }),
        { wrapper }
      );
      const viewer = renderHook(useOverviewLinkSettings, { wrapper });
      await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));
      const signal = vi.mocked(apiClient.get).mock.calls[0][1]?.signal;
      act(() =>
        editor.result.current.update.mutate({ orbital_traffic_enabled: false })
      );
      await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));
      expect(signal?.aborted).toBe(true);
      expect(client.getQueryData(key)).toEqual(original);
      if (unmountBeforeSave) {
        editor.unmount();
        viewer.unmount();
      }
      await act(async () => {
        put.resolve({ data: saved });
      });
      // The PUT pair must be visible before the invalidation GET completes.
      expect(client.getQueryData(key)).toEqual(saved);
      if (!unmountBeforeSave) {
        await waitFor(() => expect(viewer.result.current.data).toEqual(saved));
        expect(editor.result.current.query.data).toEqual(saved);
      }
      // Simulate a transport that ignores abort and completes anyway.
      await act(async () => {
        stale.resolve({ data: original });
      });
      expect(client.getQueryData(key)).toEqual(saved);
      await act(async () => {
        fresh.resolve({ data: saved });
      });
      expect(client.getQueryData(key)).toEqual(saved);
    }
  );

  it('cancels a read started during PUT before publishing the confirmed save', async () => {
    client.setQueryData(key, original);
    const stale = deferred<{ data: typeof original }>();
    const fresh = deferred<{ data: typeof saved }>();
    const put = deferred<{ data: typeof saved }>();
    vi.mocked(apiClient.put).mockReturnValue(put.promise);
    vi.mocked(apiClient.get)
      .mockReturnValueOnce(stale.promise)
      .mockReturnValue(fresh.promise);
    const editor = renderHook(useUpdateOverviewLinkSettings, { wrapper });
    act(() => editor.result.current.mutate({ starshield_link_enabled: false }));
    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));
    const viewer = renderHook(useOverviewLinkSettings, { wrapper });
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));
    const signal = vi.mocked(apiClient.get).mock.calls[0][1]?.signal;
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

  it.each([
    new Error('save failed'),
    { data: { starshield_link_enabled: false } },
  ])(
    'retains the pair on rejected/malformed saves and recovers %j',
    async (response) => {
      client.setQueryData(key, saved);
      if (response instanceof Error)
        vi.mocked(apiClient.put).mockRejectedValueOnce(response);
      else vi.mocked(apiClient.put).mockResolvedValueOnce(response);
      const { result } = renderHook(useUpdateOverviewLinkSettings, { wrapper });
      act(() => result.current.mutate({ x_band_link_enabled: false }));
      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(client.getQueryData(key)).toEqual(saved);
      expect(apiClient.get).not.toHaveBeenCalled();
      const bothOff = {
        starshield_link_enabled: false,
        x_band_link_enabled: false,
        orbital_traffic_enabled: false,
        aircraft_history_enabled: true,
      };
      vi.mocked(apiClient.put).mockResolvedValueOnce({ data: bothOff });
      await act(async () => {
        await result.current.mutateAsync({ x_band_link_enabled: false });
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(client.getQueryData(key)).toEqual(bothOff);
    }
  );

  it('serializes saves from separate hook instances and cancels the first save’s refetch before the queued PUT', async () => {
    client.setQueryData(key, original);
    const firstPut = deferred<{ data: typeof saved }>();
    const firstRefetch = deferred<{ data: typeof saved }>();
    vi.mocked(apiClient.put)
      .mockReturnValueOnce(firstPut.promise)
      .mockResolvedValueOnce({
        data: {
          starshield_link_enabled: false,
          x_band_link_enabled: false,
          orbital_traffic_enabled: false,
          aircraft_history_enabled: true,
        },
      });
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: original })
      .mockReturnValueOnce(firstRefetch.promise)
      .mockResolvedValue({
        data: {
          starshield_link_enabled: false,
          x_band_link_enabled: false,
          orbital_traffic_enabled: false,
          aircraft_history_enabled: true,
        },
      });
    const viewer = renderHook(useOverviewLinkSettings, { wrapper });
    await waitFor(() => expect(viewer.result.current.isFetching).toBe(false));
    const first = renderHook(useUpdateOverviewLinkSettings, { wrapper });
    const second = renderHook(useUpdateOverviewLinkSettings, { wrapper });
    act(() => {
      first.result.current.mutate({ starshield_link_enabled: false });
      second.result.current.mutate({
        x_band_link_enabled: false,
        orbital_traffic_enabled: false,
      });
    });
    await waitFor(() => expect(second.result.current.isPaused).toBe(true));
    expect(apiClient.put).toHaveBeenCalledTimes(1);
    await act(async () => {
      firstPut.resolve({ data: saved });
    });
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true));
    expect(apiClient.get).toHaveBeenCalledTimes(3);
    expect(vi.mocked(apiClient.get).mock.calls[1][1]?.signal?.aborted).toBe(
      true
    );
    expect(apiClient.put).toHaveBeenNthCalledWith(
      2,
      '/api/overview-links/settings',
      { x_band_link_enabled: false, orbital_traffic_enabled: false }
    );
    await act(async () => {
      firstRefetch.resolve({ data: saved });
    });
    expect(viewer.result.current.data).toEqual({
      starshield_link_enabled: false,
      x_band_link_enabled: false,
      orbital_traffic_enabled: false,
      aircraft_history_enabled: true,
    });
  });
});
