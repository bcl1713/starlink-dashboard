/** @vitest-environment jsdom */
import { cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { type ReactNode } from 'react';
import { adsbContact, adsbSettings } from '@/test/adsb-fixtures';
import { overviewAdsbApi } from '@/services/overview-adsb';
import { useConfigurationAdsbLayer } from './useConfigurationAdsbLayer';
const settings = adsbSettings({
  mode: 'included_only',
  exclude_hexes: ['00AB12'],
});
vi.mock('./api/useOverviewAdsbSettings', () => ({
  useOverviewAdsbSettings: () => ({ data: settings }),
}));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('reads the independent catalog only while its tab is active, including excluded military', async () => {
  const now = Date.now();
  const fetch = vi
    .spyOn(overviewAdsbApi, 'getCatalog')
    .mockResolvedValue({
      settings_revision: settings.revision,
      generated_at_ms: now,
      sources: [],
      contacts: [
        adsbContact({ position_observed_at_ms: now, acquired_at_ms: now }),
      ],
    });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const view = renderHook(({ active }) => useConfigurationAdsbLayer(active), {
    wrapper,
    initialProps: { active: false },
  });
  expect(fetch).not.toHaveBeenCalled();
  view.rerender({ active: true });
  await waitFor(() =>
    expect(view.result.current.contacts[0]?.selection).toBe('excluded')
  );
  expect(view.result.current.contacts[0].hex).toBe('00AB12');
  view.rerender({ active: false });
  const calls = fetch.mock.calls.length;
  await client.invalidateQueries({ queryKey: ['overview-adsb-catalog'] });
  expect(fetch).toHaveBeenCalledTimes(calls);
  view.unmount();
  client.clear();
});
