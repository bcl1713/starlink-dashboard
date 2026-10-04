/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { adsbBundle } from '@/test/adsb-fixtures';
import { useOverviewAdsbTraffic } from './useOverviewAdsbTraffic';
vi.mock('@/services/api-client', () => ({ default: { get: vi.fn() } }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
it('acquires traffic only with confirmed enable and aborts on unmount', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
  vi.mocked(apiClient.get).mockResolvedValue({ data: adsbBundle() });
  const { result, rerender, unmount } = renderHook(
    ({ enabled }) => useOverviewAdsbTraffic(enabled),
    { wrapper, initialProps: { enabled: false } }
  );
  expect(apiClient.get).not.toHaveBeenCalled();
  rerender({ enabled: true });
  await waitFor(() =>
    expect(result.current.data?.contacts[0].hex).toBe('00AB12')
  );
  unmount();
  client.clear();
});
