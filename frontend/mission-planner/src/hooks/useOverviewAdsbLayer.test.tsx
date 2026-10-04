/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { ADSB_NOW, adsbSettings, adsbBundle } from '@/test/adsb-fixtures';
import { useOverviewAdsbLayer } from './useOverviewAdsbLayer';
vi.mock('@/services/api-client', () => ({ default: { get: vi.fn() } }));
let client: QueryClient;
let wrapper: (props: PropsWithChildren) => ReturnType<typeof createElement>;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(ADSB_NOW);
  vi.resetAllMocks();
  client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
  wrapper = ({ children }) =>
    createElement(QueryClientProvider, { client }, children);
  vi.mocked(apiClient.get).mockImplementation(async (path) => ({
    data: path.endsWith('settings') ? adsbSettings() : adsbBundle(),
  }));
});
afterEach(() => {
  cleanup();
  client.clear();
  vi.useRealTimers();
});
async function tick(ms = 10) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
it('initial settings failure stays off', async () => {
  vi.mocked(apiClient.get).mockRejectedValue(new Error('offline'));
  const { result } = renderHook(useOverviewAdsbLayer, { wrapper });
  await tick();
  expect(result.current.contacts).toEqual([]);
  expect(result.current.settingsError).toBe(true);
  expect(apiClient.get).toHaveBeenCalledTimes(1);
});
it('retains contacts through failures while freshness and expiry advance', async () => {
  const { result } = renderHook(useOverviewAdsbLayer, { wrapper });
  await tick();
  expect(result.current.contacts).toHaveLength(1);
  vi.mocked(apiClient.get).mockRejectedValue(new Error('offline'));
  await tick(30000);
  expect(result.current.contacts[0].freshness).toBe('stale');
  await tick(90000);
  expect(result.current.contacts).toEqual([]);
});
it('new settings reproject retained contacts, and older traffic cannot resurrect exclusion', async () => {
  const { result } = renderHook(useOverviewAdsbLayer, { wrapper });
  await tick();
  vi.mocked(apiClient.get).mockImplementation(() => new Promise(() => {}));
  act(() =>
    client.setQueryData(
      ['overview-adsb-settings'],
      adsbSettings({ revision: 2, include_hexes: ['00AB12'] })
    )
  );
  await tick();
  expect(result.current.contacts[0].included).toBe(true);
  act(() =>
    client.setQueryData(
      ['overview-adsb-settings'],
      adsbSettings({ revision: 3, exclude_hexes: ['00AB12'] })
    )
  );
  await tick();
  expect(result.current.contacts).toEqual([]);
  act(() => client.setQueryData(['overview-adsb-traffic'], adsbBundle()));
  await tick();
  expect(result.current.contacts).toEqual([]);
});
it('higher traffic revision waits for settings confirmation', async () => {
  vi.mocked(apiClient.get).mockImplementation(async (path) => ({
    data: path.endsWith('settings')
      ? adsbSettings()
      : adsbBundle({ settings_revision: 2 }),
  }));
  const { result } = renderHook(useOverviewAdsbLayer, { wrapper });
  await tick();
  expect(result.current.contacts).toEqual([]);
  act(() =>
    client.setQueryData(
      ['overview-adsb-settings'],
      adsbSettings({ revision: 2 })
    )
  );
  await tick();
  expect(result.current.contacts).toHaveLength(1);
});
it('foreground return immediately expires delayed or repeated positions', async () => {
  const { result } = renderHook(useOverviewAdsbLayer, { wrapper });
  await tick();
  vi.setSystemTime(ADSB_NOW + 130000);
  await act(async () => {
    document.dispatchEvent(new Event('visibilitychange'));
  });
  expect(result.current.contacts).toEqual([]);
});
it('disable clears retained contacts and enabled timer', async () => {
  const { result, unmount } = renderHook(useOverviewAdsbLayer, { wrapper });
  await tick();
  act(() =>
    client.setQueryData(
      ['overview-adsb-settings'],
      adsbSettings({ revision: 2, enabled: false })
    )
  );
  await tick();
  expect(result.current.contacts).toEqual([]);
  act(() =>
    client.setQueryData(
      ['overview-adsb-settings'],
      adsbSettings({ revision: 3 })
    )
  );
  await tick();
  expect(result.current.contacts).toEqual([]);
  unmount();
});
