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
import { useOverviewWeatherSettings } from './useOverviewWeatherSettings';
vi.mock('@/services/api-client', () => ({ default: { get: vi.fn() } }));
afterEach(() => {
  cleanup();
  focusManager.setFocused(undefined);
  vi.useRealTimers();
  vi.restoreAllMocks();
});

it('polls visible settings, pauses hidden documents and recovers on visibility', async () => {
  vi.useFakeTimers();
  focusManager.setFocused(true);
  let hidden = false;
  vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden);
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity, retry: false } },
  });
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { enabled: false, revision: 0 },
  });
  const hook = renderHook(
    () => {
      const query = useOverviewWeatherSettings();
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
  expect(hook.result.current.data?.settings.enabled).toBe(false);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(apiClient.get).toHaveBeenCalledTimes(2);
  await act(async () => {
    hidden = true;
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(20000);
  });
  expect(apiClient.get).toHaveBeenCalledTimes(2);
  await act(async () => {
    hidden = false;
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(apiClient.get).toHaveBeenCalledTimes(3);
  hook.unmount();
  client.clear();
});

it('discards older revisions without renewing their trust timestamp', async () => {
  vi.useFakeTimers();
  focusManager.setFocused(true);
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
  const old = { settings: { enabled: false, revision: 2 }, receivedAtMono: 10 };
  client.setQueryData(['overview-weather-settings'], old);
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { enabled: true, revision: 1 },
  });
  const hook = renderHook(
    () => {
      const query = useOverviewWeatherSettings();
      return { data: query.data };
    },
    { wrapper }
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(hook.result.current.data).toEqual(old);
  hook.unmount();
  client.clear();
});
