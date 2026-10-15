/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { onlineManager, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { OverviewLinkSettingsCard } from '@/pages/OverviewLinkSettingsCard';
import { createQueryClient } from './query-client';

vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));

let client: ReturnType<typeof createQueryClient>;
let settings: Record<string, boolean>;
beforeEach(() => {
  onlineManager.setOnline(true);
  vi.resetAllMocks();
  client = createQueryClient();
  settings = {
    starshield_link_enabled: true,
    x_band_link_enabled: true,
    orbital_traffic_enabled: false,
    ground_entry_point_enabled: true,
    latency_panel_enabled: true,
  };
  vi.mocked(apiClient.get).mockImplementation(async () => ({ data: settings }));
  vi.mocked(apiClient.put).mockImplementation(async (_url, changes) => {
    settings = Object.assign({}, settings, changes);
    return { data: settings };
  });
});
afterEach(() => {
  cleanup();
  client.clear();
  onlineManager.setOnline(true);
  vi.restoreAllMocks();
});

it.each([
  ['network', 'Ground entry point', 'ground_entry_point_enabled', 'online'],
  ['metrics', 'Network latency panel', 'latency_panel_enabled', 'online'],
  [
    'network',
    'Ground entry point',
    'ground_entry_point_enabled',
    'offline before load',
  ],
  [
    'metrics',
    'Network latency panel',
    'latency_panel_enabled',
    'offline before load',
  ],
  [
    'network',
    'Ground entry point',
    'ground_entry_point_enabled',
    'offline before save',
  ],
  [
    'metrics',
    'Network latency panel',
    'latency_panel_enabled',
    'offline before save',
  ],
] as const)(
  'loads and saves %s configuration: %s, %s, %s',
  async (group, label, field, mode) => {
    if (mode === 'offline before load') onlineManager.setOnline(false);
    render(
      <QueryClientProvider client={client}>
        <OverviewLinkSettingsCard group={group} />
      </QueryClientProvider>
    );
    const control = screen.getByRole('switch', { name: label });
    await waitFor(() => expect(control).toHaveProperty('disabled', false));
    if (mode === 'offline before save') onlineManager.setOnline(false);
    fireEvent.click(control);
    await waitFor(() =>
      expect(apiClient.put).toHaveBeenCalledWith(
        '/api/overview-links/settings',
        { [field]: false }
      )
    );
    await waitFor(() => expect(control).toHaveProperty('disabled', false));
    expect(control).toHaveProperty('checked', false);
  }
);

it('reports a failed offline save and retains the confirmed switch value', async () => {
  onlineManager.setOnline(false);
  vi.mocked(apiClient.put).mockRejectedValue(
    new Error('Local API unavailable')
  );
  render(
    <QueryClientProvider client={client}>
      <OverviewLinkSettingsCard group="network" />
    </QueryClientProvider>
  );
  const control = screen.getByRole('switch', { name: 'Ground entry point' });
  await waitFor(() => expect(control).toHaveProperty('disabled', false));
  fireEvent.click(control);
  await screen.findByRole('alert');
  expect(control).toHaveProperty('checked', true);
  expect(control).toHaveProperty('disabled', false);
  expect(apiClient.put).toHaveBeenCalledTimes(1);
});

it('reports an unavailable local API on an offline initial read', async () => {
  onlineManager.setOnline(false);
  vi.mocked(apiClient.get).mockRejectedValue(
    new Error('Local API unavailable')
  );
  render(
    <QueryClientProvider client={client}>
      <OverviewLinkSettingsCard group="network" />
    </QueryClientProvider>
  );
  await screen.findByRole('alert');
  expect(
    screen.getByRole('switch', { name: 'Ground entry point' })
  ).toHaveProperty('disabled', true);
  expect(apiClient.get).toHaveBeenCalledTimes(1);
});
