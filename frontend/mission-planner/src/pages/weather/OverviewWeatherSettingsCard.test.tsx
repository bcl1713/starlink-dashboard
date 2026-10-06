/** @vitest-environment jsdom */
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
import { OverviewWeatherSettingsCard } from './OverviewWeatherSettingsCard';
vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it('starts off, confirms a save, and never acquires imagery on Configuration', async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { enabled: false, revision: 0 },
  });
  vi.mocked(apiClient.put).mockResolvedValue({
    data: { enabled: true, revision: 1 },
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <OverviewWeatherSettingsCard />
    </QueryClientProvider>
  );
  const control = (await screen.findByRole('switch', {
    name: 'Precipitation radar',
  })) as HTMLInputElement;
  await waitFor(() => expect(control.disabled).toBe(false));
  expect(control.checked).toBe(false);
  fireEvent.click(control);
  await screen.findByText('Weather settings saved');
  expect(control.checked).toBe(true);
  expect(apiClient.get).toHaveBeenCalledWith(
    '/api/overview-weather/settings',
    expect.anything()
  );
  expect(
    vi
      .mocked(apiClient.get)
      .mock.calls.some(([url]) => url !== '/api/overview-weather/settings')
  ).toBe(false);
  client.clear();
});

it('shows save failure and preserves the confirmed off switch', async () => {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { enabled: false, revision: 0 },
  });
  vi.mocked(apiClient.put).mockRejectedValue(new Error('write failed'));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <OverviewWeatherSettingsCard />
    </QueryClientProvider>
  );
  const control = (await screen.findByRole('switch')) as HTMLInputElement;
  await waitFor(() => expect(control.disabled).toBe(false));
  fireEvent.click(control);
  await screen.findByText('Weather settings could not be saved');
  expect(control.checked).toBe(false);
  client.clear();
});
