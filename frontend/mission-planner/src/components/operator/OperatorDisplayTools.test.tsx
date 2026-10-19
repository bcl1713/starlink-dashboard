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
import { OVERVIEW_VISIBILITY_DEFAULTS } from '@/services/overview-link-settings';
import { OperatorDisplayTools } from './OperatorDisplayTools';
vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
let client: QueryClient;
let saved: Record<string, boolean>;
let presets: Record<string, unknown>;
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
  presets = { normal: null, communications: null, weather: null };
  client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  vi.mocked(apiClient.get).mockImplementation(async (url) => ({
    data:
      url === '/api/overview-links/presets'
        ? presets
        : url === '/api/overview-history/settings'
          ? { window_seconds: 1800 }
          : url === '/api/overview-weather/settings'
            ? { enabled: true, revision: 2 }
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
    if (url === '/api/overview-links/settings') {
      const changes = Object.fromEntries(
        Object.entries(body).filter(([key]) => key !== 'expected_values')
      );
      saved = { ...saved, ...changes } as Record<string, boolean>;
      return { data: saved };
    }
    if (url === '/api/overview-weather/settings')
      return { data: { enabled: body.enabled, revision: 3 } };
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
  fireEvent.click(
    screen.getByRole('button', { name: 'Show display controls' })
  );
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Save current as Normal' })
    ).toBeEnabled()
  );
}
it('defers display queries until expanded and separates shared settings from browser commands', async () => {
  mount();
  expect(apiClient.get).not.toHaveBeenCalled();
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
  expect(await screen.findByRole('alert')).toHaveTextContent(/not confirmed/);
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
  expect(await screen.findByRole('alert')).toHaveTextContent(/Preset changed/);
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
  expect(await screen.findByRole('alert')).toHaveTextContent(
    /Invalid Overview preset acknowledgment/
  );
  expect(screen.queryByText('Normal preset saved')).toBeNull();
  expect(screen.getByRole('button', { name: 'Apply Normal' })).toBeDisabled();
});

it('keeps existing Configuration and selected mission planning destinations reachable before lazy controls mount', () => {
  mount();
  expect(
    screen.getByRole('link', { name: 'Display settings' }).getAttribute('href')
  ).toBe('/configuration');
  expect(
    screen.getByRole('link', { name: 'Mission planning' }).getAttribute('href')
  ).toBe('/missions/synthetic-demo');
  expect(apiClient.get).not.toHaveBeenCalled();
});
