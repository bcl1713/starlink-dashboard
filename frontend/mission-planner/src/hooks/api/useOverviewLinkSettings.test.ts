/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import {
  focusManager,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { useOverviewLinkSettings } from './useOverviewLinkSettings';

vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
const confirmed = {
  starshield_link_enabled: false,
  x_band_link_enabled: true,
  orbital_traffic_enabled: false,
};
let client: QueryClient;
let wrapper: (props: PropsWithChildren) => ReturnType<typeof createElement>;
beforeEach(() => {
  vi.resetAllMocks();
  focusManager.setFocused(true);
  client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
  wrapper = ({ children }) =>
    createElement(QueryClientProvider, { client }, children);
});
afterEach(() => {
  cleanup();
  client.clear();
  focusManager.setFocused(undefined);
  vi.useRealTimers();
});

describe('useOverviewLinkSettings', () => {
  it('has no confirmed data while the first read is pending', async () => {
    vi.mocked(apiClient.get).mockReturnValue(new Promise(() => {}));
    const { result, unmount } = renderHook(useOverviewLinkSettings, {
      wrapper,
    });
    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));
    const signal = vi.mocked(apiClient.get).mock.calls[0][1]?.signal;
    unmount();
    expect(signal?.aborted).toBe(true);
  });

  it.each([
    new Error('unavailable'),
    { data: { starshield_link_enabled: false, x_band_link_enabled: 'true' } },
  ])(
    'does not fabricate settings or retry an initial failed read %j',
    async (response) => {
      if (response instanceof Error)
        vi.mocked(apiClient.get).mockRejectedValue(response);
      else vi.mocked(apiClient.get).mockResolvedValue(response);
      const { result } = renderHook(useOverviewLinkSettings, { wrapper });
      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.data).toBeUndefined();
      expect(apiClient.get).toHaveBeenCalledTimes(1);
    }
  );

  it('retains confirmed false on refresh failure and recovers to another viewer’s pair', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: confirmed });
    const { result } = renderHook(useOverviewLinkSettings, { wrapper });
    await waitFor(() => expect(result.current.data).toEqual(confirmed));
    // Subscribe to errors before a same-data refresh changes only query status.
    expect(result.current.isError).toBe(false);
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('refresh failed'));
    await act(async () => {
      await result.current.refetch();
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toEqual(confirmed);
    const changed = {
      starshield_link_enabled: false,
      x_band_link_enabled: false,
      orbital_traffic_enabled: false,
    };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: changed });
    await act(async () => {
      await result.current.refetch();
    });
    await waitFor(() => expect(result.current.data).toEqual(changed));
    expect(result.current.isError).toBe(false);
  });

  it('polls every five seconds while visible and synchronizes on focus', async () => {
    vi.useFakeTimers();
    vi.mocked(apiClient.get).mockResolvedValue({ data: confirmed });
    const { result } = renderHook(useOverviewLinkSettings, { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(result.current.data).toEqual(confirmed);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4999);
    });
    expect(apiClient.get).toHaveBeenCalledTimes(2);
    focusManager.setFocused(false);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(apiClient.get).toHaveBeenCalledTimes(2);
    const changed = {
      starshield_link_enabled: true,
      x_band_link_enabled: false,
      orbital_traffic_enabled: false,
    };
    vi.mocked(apiClient.get).mockResolvedValue({ data: changed });
    await act(async () => {
      focusManager.setFocused(true);
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(apiClient.get).toHaveBeenCalledTimes(3);
    expect(result.current.data).toEqual(changed);
  });
  it('live Overview keeps reading link settings while unfocused', async () => {
    vi.useFakeTimers();
    focusManager.setFocused(false);
    vi.mocked(apiClient.get).mockResolvedValue({ data: confirmed });
    const { result, unmount } = renderHook(
      () => useOverviewLinkSettings(true),
      { wrapper }
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    const changed = {
      starshield_link_enabled: true,
      x_band_link_enabled: false,
    };
    vi.mocked(apiClient.get).mockResolvedValue({ data: changed });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5001);
    });
    expect(result.current.data).toEqual(changed);
    expect(apiClient.get).toHaveBeenCalledTimes(2);
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(apiClient.get).toHaveBeenCalledTimes(2);
  });
});
