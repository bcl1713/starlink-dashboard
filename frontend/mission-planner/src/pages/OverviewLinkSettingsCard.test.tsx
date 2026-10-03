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
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { OverviewLinkSettingsCard } from './OverviewLinkSettingsCard';

vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
let client: QueryClient;
const pair = { starshield_link_enabled: false, x_band_link_enabled: true };
const switches = () => [
  screen.getByRole('switch', { name: 'Starshield data link' }),
  screen.getByRole('switch', { name: 'X-band data link' }),
];
function renderCard() {
  return render(
    <QueryClientProvider client={client}>
      <OverviewLinkSettingsCard />
    </QueryClientProvider>
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
});
afterEach(() => {
  cleanup();
  client.clear();
});

describe('OverviewLinkSettingsCard', () => {
  it.each([
    [true, true],
    [false, true],
    [true, false],
    [false, false],
  ])(
    'shows the confirmed accessible switch pair %s/%s and exact descriptions',
    async (starshield, xBand) => {
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          starshield_link_enabled: starshield,
          x_band_link_enabled: xBand,
        },
      });
      renderCard();
      await waitFor(() => expect(switches()[0]).toBeEnabled());
      expect(switches()[0]).toHaveProperty('checked', starshield);
      expect(switches()[1]).toHaveProperty('checked', xBand);
      expect(switches()[0]).toHaveAccessibleDescription(
        'Show aircraft-to-PoP traffic.'
      );
      expect(switches()[1]).toHaveAccessibleDescription(
        'Show the configured satellite link and its activity.'
      );
    }
  );

  it('disables unconfirmed controls during loading and initial failure', async () => {
    let reject!: (error: Error) => void;
    vi.mocked(apiClient.get).mockReturnValue(
      new Promise((_resolve, fail) => {
        reject = fail;
      })
    );
    renderCard();
    expect(screen.getByRole('status')).toHaveTextContent(
      'Loading data link settings'
    );
    switches().forEach((control) => {
      expect(control).toBeDisabled();
      expect(control).not.toBeChecked();
    });
    await act(async () => {
      reject(new Error('unavailable'));
    });
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Data link settings unavailable'
      )
    );
    switches().forEach((control) => expect(control).toBeDisabled());
  });

  it.each([
    [
      'Starshield data link',
      { starshield_link_enabled: true },
      { starshield_link_enabled: true, x_band_link_enabled: true },
    ],
    [
      'X-band data link',
      { x_band_link_enabled: false },
      { starshield_link_enabled: false, x_band_link_enabled: false },
    ],
  ])(
    'saves only %s and keeps both switches confirmed/disabled until PUT finishes',
    async (label, changes, saved) => {
      let resolve!: (value: { data: typeof pair }) => void;
      vi.mocked(apiClient.get).mockResolvedValue({ data: pair });
      vi.mocked(apiClient.put).mockReturnValue(
        new Promise((done) => {
          resolve = done;
        })
      );
      renderCard();
      await waitFor(() => expect(switches()[0]).toBeEnabled());
      fireEvent.click(screen.getByRole('switch', { name: label }));
      await waitFor(() =>
        expect(screen.getByRole('status')).toHaveTextContent(
          'Saving data link settings'
        )
      );
      switches().forEach((control) => expect(control).toBeDisabled());
      expect(switches()[0]).not.toBeChecked();
      expect(switches()[1]).toBeChecked();
      expect(apiClient.put).toHaveBeenCalledWith(
        '/api/overview-links/settings',
        changes
      );
      vi.mocked(apiClient.get).mockResolvedValue({ data: saved });
      await act(async () => {
        resolve({ data: saved });
      });
      await waitFor(() =>
        expect(screen.getByRole('status')).toHaveTextContent(
          'Data link settings saved'
        )
      );
      expect(switches()[0]).toHaveProperty(
        'checked',
        saved.starshield_link_enabled
      );
      expect(switches()[1]).toHaveProperty(
        'checked',
        saved.x_band_link_enabled
      );
      switches().forEach((control) => expect(control).toBeEnabled());
    }
  );

  it('keeps the confirmed pair on failed saves and offers a working retry', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: pair });
    vi.mocked(apiClient.put).mockRejectedValueOnce(new Error('save failed'));
    renderCard();
    await waitFor(() => expect(switches()[0]).toBeEnabled());
    fireEvent.click(switches()[1]);
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Unable to save data link settings'
      )
    );
    expect(switches()[0]).not.toBeChecked();
    expect(switches()[1]).toBeChecked();
    switches().forEach((control) => expect(control).toBeEnabled());
    const saved = {
      starshield_link_enabled: false,
      x_band_link_enabled: false,
    };
    vi.mocked(apiClient.put).mockResolvedValueOnce({ data: saved });
    vi.mocked(apiClient.get).mockResolvedValue({ data: saved });
    fireEvent.click(switches()[1]);
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        'Data link settings saved'
      )
    );
    expect(screen.queryByRole('alert')).toBeNull();
    switches().forEach((control) => expect(control).not.toBeChecked());
  });

  it('retains confirmed switch states and permits saves after a refresh error', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: pair });
    renderCard();
    await waitFor(() => expect(switches()[0]).toBeEnabled());
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('refresh failed'));
    await act(async () => {
      await client.refetchQueries({ queryKey: ['overview-link-settings'] });
    });
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Data link settings unavailable'
      )
    );
    expect(switches()[0]).not.toBeChecked();
    expect(switches()[1]).toBeChecked();
    switches().forEach((control) => expect(control).toBeEnabled());
  });
});
