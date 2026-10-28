/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import {
  onlineManager,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { adsbSettings } from '@/test/adsb-fixtures';
import { OVERVIEW_VISIBILITY_DEFAULTS } from '@/services/overview-link-settings';
import { OperatorDisplayTools } from './OperatorDisplayTools';
vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
let client: QueryClient;
let saved: Record<string, boolean>;
let presets: Record<string, unknown>;
let radar = { enabled: true, revision: 2 };
let aircraft = adsbSettings({ enabled: false });
beforeEach(() => {
  saved = {
    ...OVERVIEW_VISIBILITY_DEFAULTS,
    starshield_link_enabled: true,
    x_band_link_enabled: true,
    orbital_traffic_enabled: false,
    aircraft_history_enabled: true,
    country_borders_enabled: false,
    state_borders_enabled: false,
  };
  radar = { enabled: true, revision: 2 };
  aircraft = adsbSettings({ enabled: false });
  presets = { normal: null, communications: null, weather: null };
  client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  vi.mocked(apiClient.get).mockImplementation(async (url) => ({
    data:
      url === '/api/overview-adsb/settings'
        ? aircraft
        : url === '/api/overview-links/presets'
          ? presets
          : url === '/api/overview-history/settings'
            ? { window_seconds: 1800 }
            : url === '/api/overview-weather/settings'
              ? radar
              : url === '/api/aviation-weather/v1/settings'
                ? {
                    metar: false,
                    taf: false,
                    sigmet: true,
                    sigmet_intersecting_only: true,
                    winds: true,
                    temperature: false,
                    revision: 3,
                  }
                : saved,
  }));
  vi.mocked(apiClient.put).mockImplementation(async (url, value) => {
    const body = value as Record<string, unknown>;
    if (url === '/api/overview-adsb/settings') {
      aircraft = { ...aircraft, ...body, revision: aircraft.revision + 1 };
      return { data: aircraft };
    }
    if (url === '/api/overview-links/settings') {
      const changes = Object.fromEntries(
        Object.entries(body).filter(([key]) => key !== 'expected_values')
      );
      saved = { ...saved, ...changes } as Record<string, boolean>;
      return { data: saved };
    }
    if (url === '/api/overview-weather/settings') {
      radar = {
        enabled: body.enabled as boolean,
        revision: radar.revision + 1,
      };
      return { data: radar };
    }
    if (url === '/api/aviation-weather/v1/settings') {
      const flags = Object.fromEntries(
        Object.entries(body).filter(([key]) => key !== 'expected_revision')
      );
      return { data: { ...flags, revision: 4 } };
    }
    const name = String(url).split('/').pop()!;
    presets = {
      ...presets,
      [name]: {
        version: 1,
        settings: body.settings,
        ...(body.weather_visibility
          ? { weather_visibility: body.weather_visibility }
          : {}),
      },
    };
    return { data: presets[name] };
  });
});
afterEach(() => {
  cleanup();
  client.clear();
  onlineManager.setOnline(true);
  vi.resetAllMocks();
});
function mount() {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <OperatorDisplayTools missionId="synthetic-demo" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}
async function open() {
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Save current as Normal' })
    ).toBeEnabled()
  );
}
it('immediately shows shared settings and browser controls without a Configuration detour', async () => {
  mount();
  expect(
    screen.queryByRole('button', { name: 'Show display controls' })
  ).toBeNull();
  expect(screen.queryByRole('link', { name: 'Display settings' })).toBeNull();
  expect(screen.queryByLabelText('Atmosphere level')).toBeNull();
  expect(screen.queryByLabelText('ADS-B mode')).toBeNull();
  expect(
    screen.getByRole('switch', { name: 'Precipitation radar' })
  ).toBeVisible();
  expect(
    screen.getByRole('switch', { name: 'ADS-B aircraft layer' })
  ).toBeVisible();
  await open();
  expect(screen.getByText(/Shared across all Overview displays/)).toBeVisible();
  expect(
    screen.getByText(/Control an Overview window in this browser/)
  ).toBeVisible();
  expect(screen.getByLabelText('Overview history window')).toHaveValue('1800');
  expect(
    screen.getByRole('switch', { name: 'Starshield data link' })
  ).toBeChecked();
});
it('saves a bundle without applying it, then restores its confirmed switches', async () => {
  mount();
  await open();
  fireEvent.click(
    screen.getByRole('button', { name: 'Save current as Normal' })
  );
  await screen.findByText('Normal preset saved');
  fireEvent.click(screen.getByRole('switch', { name: 'Starshield data link' }));
  await waitFor(() =>
    expect(
      screen.getByRole('switch', { name: 'Starshield data link' })
    ).not.toBeChecked()
  );
  fireEvent.click(screen.getByRole('button', { name: 'Apply Normal' }));
  await screen.findByText('Normal preset applied');
  expect(
    screen.getByRole('switch', { name: 'Starshield data link' })
  ).toBeChecked();
  expect(saved.starshield_link_enabled).toBe(true);
});
it('waits for the server and never claims an offline preset save succeeded', async () => {
  let reject!: (e: Error) => void;
  vi.mocked(apiClient.put).mockImplementation(
    () =>
      new Promise((_resolve, fail) => {
        reject = fail;
      })
  );
  mount();
  await open();
  onlineManager.setOnline(false);
  fireEvent.click(
    screen.getByRole('button', { name: 'Save current as Weather' })
  );
  await screen.findByText(/Waiting for server acknowledgment/);
  expect(screen.queryByText('Weather preset saved')).toBeNull();
  await act(async () => reject(new Error('Network unavailable')));
  expect(await screen.findByText(/not confirmed/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Apply Weather' })).toBeDisabled();
});
it('refreshes a conflicting preset without overwriting the counterpart bundle', async () => {
  presets.normal = { version: 2, settings: { legend_enabled: false } };
  mount();
  await open();
  vi.mocked(apiClient.put).mockRejectedValue(
    new Error('Preset changed; refresh before retrying')
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Save current as Normal' })
  );
  expect(await screen.findByText(/Preset changed/)).toBeVisible();
  expect(presets.normal).toEqual({
    version: 2,
    settings: { legend_enabled: false },
  });
});

it('does not confirm a save when the server returns a malformed acknowledgment', async () => {
  mount();
  await open();
  vi.mocked(apiClient.put).mockResolvedValue({
    data: { version: 1, settings: { fictional_layer: true } },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Save current as Normal' })
  );
  expect(
    await screen.findByText(/Invalid Overview preset acknowledgment/)
  ).toBeVisible();
  expect(screen.queryByText('Normal preset saved')).toBeNull();
  expect(screen.getByRole('button', { name: 'Apply Normal' })).toBeDisabled();
});

it('keeps mission planning reachable without an ambiguous Configuration link', () => {
  mount();
  expect(
    screen.getByRole('link', { name: 'Mission planning' }).getAttribute('href')
  ).toBe('/missions/synthetic-demo');
  expect(
    screen.queryByRole('button', { name: 'Show display controls' })
  ).toBeNull();
  expect(screen.queryByRole('link', { name: 'Display settings' })).toBeNull();
  expect(screen.queryByLabelText('Atmosphere level')).toBeNull();
  expect(screen.queryByLabelText('ADS-B mode')).toBeNull();
  expect(
    screen.getByRole('switch', { name: 'Precipitation radar' })
  ).toBeVisible();
  expect(
    screen.getByRole('switch', { name: 'ADS-B aircraft layer' })
  ).toBeVisible();
});

it('writes radar and ADS-B on/off to their existing shared settings APIs without querying provider traffic', async () => {
  mount();
  await open();
  for (const [name, endpoint] of [
    ['Precipitation radar', '/api/overview-weather/settings'],
    ['ADS-B aircraft layer', '/api/overview-adsb/settings'],
  ] as const) {
    const control = screen.getByRole('switch', { name });
    await waitFor(() => expect(control).toBeEnabled());
    const before = (control as HTMLInputElement).checked;
    fireEvent.click(control);
    await waitFor(() => expect(control).toHaveProperty('checked', !before));
    expect(apiClient.put).toHaveBeenCalledWith(endpoint, { enabled: !before });
    await waitFor(() => expect(control).toBeEnabled());
    fireEvent.click(control);
    await waitFor(() => expect(control).toHaveProperty('checked', before));
    expect(apiClient.put).toHaveBeenCalledWith(endpoint, { enabled: before });
  }
  expect(
    vi
      .mocked(apiClient.get)
      .mock.calls.some(([url]) =>
        String(url).includes('/overview-adsb/catalog')
      )
  ).toBe(false);
});

it('saves a fully customizable Customer preset with flight-only selection', async () => {
  mount();
  await open();
  const flightOnly = screen.getByRole('switch', { name: 'Flight Events Only' });
  expect(flightOnly).not.toBeChecked();
  fireEvent.click(flightOnly);
  await waitFor(() => expect(flightOnly).toBeChecked());
  fireEvent.click(
    screen.getByRole('button', { name: 'Save current as Customer' })
  );
  await screen.findByText('Customer preset saved');
  expect(presets.customer).toMatchObject({
    settings: { next_flight_events_only: true },
  });
  fireEvent.click(flightOnly);
  await waitFor(() => expect(flightOnly).not.toBeChecked());
  fireEvent.click(screen.getByRole('button', { name: 'Apply Customer' }));
  await screen.findByText('Customer preset applied');
  expect(flightOnly).toBeChecked();
});
