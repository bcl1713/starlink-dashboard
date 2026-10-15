/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import {
  QueryClient,
  QueryClientProvider,
  focusManager,
} from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { adsbSettings } from '@/test/adsb-fixtures';
import { useOverviewAdsbSettings } from './useOverviewAdsbSettings';
vi.mock('@/services/api-client', () => ({ default: { get: vi.fn() } }));
afterEach(() => {
  cleanup();
  focusManager.setFocused(undefined);
  vi.useRealTimers();
  vi.resetAllMocks();
});
it('polls every five seconds while visible and refreshes on foreground', async () => {
  vi.useFakeTimers();
  focusManager.setFocused(true);
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
  vi.mocked(apiClient.get).mockResolvedValue({ data: adsbSettings() });
  const { result, unmount } = renderHook(
    () => {
      const query = useOverviewAdsbSettings();
      return { data: query.data };
    },
    { wrapper }
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10);
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(result.current.data?.revision).toBe(1);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(apiClient.get).toHaveBeenCalledTimes(2);
  focusManager.setFocused(false);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(apiClient.get).toHaveBeenCalledTimes(2);
  await act(async () => {
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(apiClient.get).toHaveBeenCalledTimes(3);
  unmount();
  client.clear();
});
