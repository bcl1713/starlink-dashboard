/** @vitest-environment jsdom */
import { StrictMode, type PropsWithChildren } from 'react';
import { cleanup, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { useOverviewWeatherLayer } from './useOverviewWeatherLayer';
vi.mock('@/services/api-client', () => ({ default: { get: vi.fn() } }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
it('mounts safely in StrictMode with default-off weather and zero image acquisition', async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { enabled: false, revision: 0 },
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: PropsWithChildren) => (
    <StrictMode>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </StrictMode>
  );
  const hook = renderHook(useOverviewWeatherLayer, { wrapper });
  expect(hook.result.current.state).toBe('off');
  expect(hook.result.current.atlas).toBeNull();
  hook.unmount();
  client.clear();
  expect(
    vi
      .mocked(apiClient.get)
      .mock.calls.every(([url]) => url === '/api/overview-weather/settings')
  ).toBe(true);
});
