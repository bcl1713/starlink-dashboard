/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { adsbSettings } from '@/test/adsb-fixtures';
import { useOverviewAdsbSettings } from './useOverviewAdsbSettings';
import { useUpdateOverviewAdsbSettings } from './useUpdateOverviewAdsbSettings';
vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
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
it('save failure retains confirmed settings', async () => {
  client.setQueryData(['overview-adsb-settings'], adsbSettings());
  vi.mocked(apiClient.put).mockRejectedValue(new Error('disk failure'));
  const { result } = renderHook(useUpdateOverviewAdsbSettings, { wrapper });
  act(() => result.current.mutate({ enabled: false }));
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(client.getQueryData(['overview-adsb-settings'])).toEqual(
    adsbSettings()
  );
});
it('late settings GET cannot restore older revision after PUT', async () => {
  client.setQueryData(['overview-adsb-settings'], adsbSettings());
  let resolve!: (value: { data: ReturnType<typeof adsbSettings> }) => void;
  vi.mocked(apiClient.get).mockReturnValue(
    new Promise((done) => {
      resolve = done;
    })
  );
  vi.mocked(apiClient.put).mockResolvedValue({
    data: adsbSettings({ revision: 2, enabled: false }),
  });
  const { result } = renderHook(
    () => ({
      settings: useOverviewAdsbSettings(),
      update: useUpdateOverviewAdsbSettings(),
    }),
    { wrapper }
  );
  await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
  await act(async () => {
    await result.current.update.mutateAsync({ enabled: false });
  });
  await act(async () => {
    resolve({ data: adsbSettings() });
  });
  expect(result.current.settings.data?.revision).toBe(2);
  expect(result.current.settings.data?.enabled).toBe(false);
});

it('serializes two editor saves and cancels reads started during PUT', async () => {
  client.setQueryData(['overview-adsb-settings'], adsbSettings());
  let release!: (value: { data: ReturnType<typeof adsbSettings> }) => void;
  vi.mocked(apiClient.put)
    .mockReturnValueOnce(
      new Promise((done) => {
        release = done;
      })
    )
    .mockResolvedValueOnce({
      data: adsbSettings({
        revision: 3,
        enabled: false,
        exclude_hexes: ['00AB12'],
      }),
    });
  vi.mocked(apiClient.get).mockImplementation(() => new Promise(() => {}));
  const first = renderHook(useUpdateOverviewAdsbSettings, { wrapper });
  const second = renderHook(useUpdateOverviewAdsbSettings, { wrapper });
  act(() => first.result.current.mutate({ enabled: false }));
  await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));
  renderHook(
    () => {
      const query = useOverviewAdsbSettings();
      return query.data;
    },
    { wrapper }
  );
  await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));
  const signal = vi.mocked(apiClient.get).mock.calls[0][1]?.signal;
  act(() => second.result.current.mutate({ exclude_hexes: ['00AB12'] }));
  expect(apiClient.put).toHaveBeenCalledTimes(1);
  await act(async () => {
    release({ data: adsbSettings({ revision: 2, enabled: false }) });
  });
  await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(2));
  await waitFor(() =>
    expect(
      client.getQueryData<{ revision: number }>(['overview-adsb-settings'])
        ?.revision
    ).toBe(3)
  );
  expect(signal?.aborted).toBe(true);
});
