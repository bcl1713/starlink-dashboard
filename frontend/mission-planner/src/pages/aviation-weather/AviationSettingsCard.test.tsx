// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AviationSettingsCard } from './AviationSettingsCard';
import { aviationWeatherApi } from '@/services/aviation-weather';
vi.mock('@/services/aviation-weather', () => ({
  aviationWeatherApi: { getSettings: vi.fn(), updateSettings: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it('offers independent default-off switches and confirms server changes in shared cache', async () => {
  const initial = {
    metar: false,
    taf: false,
    sigmet: false,
    winds: false,
    temperature: false,
    gfs_selection: {
      vertical: { kind: 'pressure' as const, pressure_pa: 50000 as const },
      horizon_hours: 0 as const,
    },
    revision: 1,
  };
  vi.mocked(aviationWeatherApi.getSettings).mockResolvedValue(initial);
  let resolve: (v: typeof initial) => void = () => {};
  vi.mocked(aviationWeatherApi.updateSettings).mockImplementation(
    () =>
      new Promise((r) => {
        resolve = r;
      })
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AviationSettingsCard />
    </QueryClientProvider>
  );
  await waitFor(() =>
    expect(
      screen
        .getByRole('switch', { name: 'METAR / SPECI observations' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  expect(screen.getAllByRole('switch')).toHaveLength(3);
  fireEvent.click(
    screen.getByRole('switch', { name: 'METAR / SPECI observations' })
  );
  expect(
    await screen.findByText('Saving aviation weather settings…')
  ).toBeTruthy();
  expect(client.getQueryData(['aviation-weather', 'settings'])).toEqual(
    initial
  );
  resolve({ ...initial, metar: true, revision: 2 });
  await waitFor(() =>
    expect(client.getQueryData(['aviation-weather', 'settings'])).toEqual({
      ...initial,
      metar: true,
      revision: 2,
    })
  );
  expect(aviationWeatherApi.updateSettings).toHaveBeenCalledWith({
    metar: true,
  });
  client.clear();
});
it('keeps unavailable optional settings visibly off without throwing', async () => {
  vi.mocked(aviationWeatherApi.getSettings).mockRejectedValue(new Error('404'));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AviationSettingsCard />
    </QueryClientProvider>
  );
  await screen.findByText('Aviation weather settings unavailable');
  expect(
    screen.getAllByRole('switch').every((s) => s.hasAttribute('disabled'))
  ).toBe(true);
  client.clear();
});
