/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { OverviewBoundarySettingsCard } from './OverviewBoundarySettingsCard';
vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
it('saves only the selected geographic layer and preserves confirmed state on failure', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const saved = {
    starshield_link_enabled: true,
    x_band_link_enabled: true,
    orbital_traffic_enabled: false,
    aircraft_history_enabled: true,
    country_borders_enabled: false,
    state_borders_enabled: false,
  };
  vi.mocked(apiClient.get).mockResolvedValue({ data: saved });
  vi.mocked(apiClient.put).mockRejectedValueOnce(new Error('save failed'));
  render(
    <QueryClientProvider client={client}>
      <OverviewBoundarySettingsCard />
    </QueryClientProvider>
  );
  const country = screen.getByRole('switch', { name: 'Country borders' });
  const state = screen.getByRole('switch', { name: 'State/province borders' });
  await waitFor(() => expect(country).toBeEnabled());
  expect(country).not.toBeChecked();
  expect(state).not.toBeChecked();
  fireEvent.click(country);
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('Unable to save')
  );
  expect(country).not.toBeChecked();
  vi.mocked(apiClient.put).mockResolvedValue({
    data: { ...saved, state_borders_enabled: true },
  });
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { ...saved, state_borders_enabled: true },
  });
  fireEvent.click(state);
  await waitFor(() => expect(state).toBeChecked());
  expect(country).not.toBeChecked();
  expect(apiClient.put).toHaveBeenLastCalledWith(
    '/api/overview-links/settings',
    { state_borders_enabled: true }
  );
  client.clear();
});
