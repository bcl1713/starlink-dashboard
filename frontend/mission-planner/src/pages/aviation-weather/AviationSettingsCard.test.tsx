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

const modelSettings = {
  metar: false,
  taf: false,
  sigmet: false,
  winds: false,
  temperature: false,
  revision: 1,
  gfs_selection: {
    vertical: { kind: 'pressure' as const, pressure_pa: 50000 as const },
    horizon_hours: 0 as const,
  },
};
async function modelCard(initial = modelSettings) {
  vi.mocked(aviationWeatherApi.getSettings).mockResolvedValue(initial);
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
      screen.getByRole('switch', { name: 'GFS winds' }).hasAttribute('disabled')
    ).toBe(false)
  );
  return client;
}
it.each([
  ['winds', 'GFS winds', 'temperature', 'GFS air temperature'],
  ['temperature', 'GFS air temperature', 'winds', 'GFS winds'],
] as const)(
  'enabling %s atomically replaces its counterpart and allows both off',
  async (layer, name, other, otherName) => {
    const initial = { ...modelSettings, [other]: true };
    const client = await modelCard(initial);
    vi.mocked(aviationWeatherApi.updateSettings).mockImplementation(
      async (changes) => ({ ...initial, ...changes, revision: 2 })
    );
    fireEvent.click(screen.getByRole('switch', { name }));
    await waitFor(() =>
      expect(aviationWeatherApi.updateSettings).toHaveBeenCalledWith({
        [layer]: true,
        [other]: false,
      })
    );
    await waitFor(() =>
      expect(
        (screen.getByRole('switch', { name }) as HTMLInputElement).checked
      ).toBe(true)
    );
    expect(
      (screen.getByRole('switch', { name: otherName }) as HTMLInputElement)
        .checked
    ).toBe(false);
    expect(client.getQueryData(['aviation-weather', 'settings'])).toMatchObject(
      { [layer]: true, [other]: false, gfs_selection: initial.gfs_selection }
    );
    vi.mocked(aviationWeatherApi.updateSettings).mockResolvedValue({
      ...modelSettings,
      revision: 3,
    });
    fireEvent.click(screen.getByRole('switch', { name }));
    await waitFor(() =>
      expect(aviationWeatherApi.updateSettings).toHaveBeenLastCalledWith({
        [layer]: false,
      })
    );
    await waitFor(() =>
      expect(
        (screen.getByRole('switch', { name }) as HTMLInputElement).checked
      ).toBe(false)
    );
    expect(
      (screen.getByRole('switch', { name: otherName }) as HTMLInputElement)
        .checked
    ).toBe(false);
    expect(
      screen.getByText('Only one GFS layer can be displayed at a time.')
    ).toBeTruthy();
    client.clear();
  }
);
it('keeps confirmed mode after failed acknowledgement and reconciles the persisted revision on polling', async () => {
  const initial = { ...modelSettings, temperature: true };
  const client = await modelCard(initial);
  vi.mocked(aviationWeatherApi.updateSettings).mockRejectedValue(
    new Error('worker acknowledgement failed')
  );
  fireEvent.click(screen.getByRole('switch', { name: 'GFS winds' }));
  await screen.findByText('Aviation weather settings could not be saved');
  expect(
    (screen.getByRole('switch', { name: 'GFS winds' }) as HTMLInputElement)
      .checked
  ).toBe(false);
  expect(
    (
      screen.getByRole('switch', {
        name: 'GFS air temperature',
      }) as HTMLInputElement
    ).checked
  ).toBe(true);
  vi.mocked(aviationWeatherApi.getSettings).mockResolvedValue({
    ...initial,
    winds: true,
    temperature: false,
    revision: 2,
  });
  await client.invalidateQueries({
    queryKey: ['aviation-weather', 'settings'],
  });
  await waitFor(() =>
    expect(
      (screen.getByRole('switch', { name: 'GFS winds' }) as HTMLInputElement)
        .checked
    ).toBe(true)
  );
  expect(
    (
      screen.getByRole('switch', {
        name: 'GFS air temperature',
      }) as HTMLInputElement
    ).checked
  ).toBe(false);
  client.clear();
});
it('displays only wind for a legacy simultaneous cache snapshot', async () => {
  const client = await modelCard({
    ...modelSettings,
    winds: true,
    temperature: true,
  });
  expect(
    (screen.getByRole('switch', { name: 'GFS winds' }) as HTMLInputElement)
      .checked
  ).toBe(true);
  expect(
    (
      screen.getByRole('switch', {
        name: 'GFS air temperature',
      }) as HTMLInputElement
    ).checked
  ).toBe(false);
  client.clear();
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
  expect(screen.getAllByRole('switch')).toHaveLength(5);
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
  expect(
    screen.getByRole('combobox', { name: 'Atmosphere level' })
  ).toBeTruthy();
  expect(
    screen
      .getByRole('option', { name: 'Surface · unsupported' })
      .hasAttribute('disabled')
  ).toBe(true);
  await screen.findByText('Aviation weather settings saved');
  fireEvent.change(screen.getByRole('combobox', { name: 'Atmosphere level' }), {
    target: { value: 'fl:390' },
  });
  await waitFor(() =>
    expect(aviationWeatherApi.updateSettings).toHaveBeenCalledWith({
      gfs_selection: {
        vertical: { kind: 'flight-level', flight_level: 390 },
        horizon_hours: 0,
      },
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

it('keeps the confirmed selection after a failed model save', async () => {
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
    revision: 4,
  };
  vi.mocked(aviationWeatherApi.getSettings).mockResolvedValue(initial);
  vi.mocked(aviationWeatherApi.updateSettings).mockRejectedValue(
    new Error('worker unavailable')
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
        .getByRole('combobox', { name: 'Atmosphere level' })
        .closest('fieldset')!.disabled
    ).toBe(false)
  );
  fireEvent.change(screen.getByRole('combobox', { name: 'Atmosphere level' }), {
    target: { value: 'fl:450' },
  });
  await screen.findByText('Aviation weather settings could not be saved');
  expect(client.getQueryData(['aviation-weather', 'settings'])).toEqual(
    initial
  );
  expect(
    (
      screen.getByRole('combobox', {
        name: 'Atmosphere level',
      }) as HTMLSelectElement
    ).value
  ).toBe('pressure:50000');
  client.clear();
});
