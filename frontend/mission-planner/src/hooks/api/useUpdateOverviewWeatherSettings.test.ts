/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { useUpdateOverviewWeatherSettings } from './useUpdateOverviewWeatherSettings';
import { useOverviewWeatherSettings } from './useOverviewWeatherSettings';
vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it('cancels an obsolete read and publishes only the confirmed saved response', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
  client.setQueryData(['overview-weather-settings'], {
    settings: { enabled: false, revision: 0 },
    receivedAtMono: 0,
  });
  let finishRead!: (value: {
    data: { enabled: boolean; revision: number };
  }) => void;
  vi.mocked(apiClient.get).mockImplementation(
    () =>
      new Promise((resolve) => {
        finishRead = resolve;
      })
  );
  vi.mocked(apiClient.put).mockResolvedValue({
    data: { enabled: true, revision: 1 },
  });
  const viewer = renderHook(useOverviewWeatherSettings, { wrapper });
  const editor = renderHook(useUpdateOverviewWeatherSettings, { wrapper });
  await waitFor(() => expect(viewer.result.current.isFetching).toBe(true));
  const signal = vi.mocked(apiClient.get).mock.calls[0][1]?.signal;
  await act(async () => {
    await editor.result.current.mutateAsync({ enabled: true });
  });
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    finishRead({ data: { enabled: false, revision: 0 } });
  });
  expect(viewer.result.current.data?.settings).toEqual({
    enabled: true,
    revision: 1,
  });
  viewer.unmount();
  editor.unmount();
  client.clear();
});
