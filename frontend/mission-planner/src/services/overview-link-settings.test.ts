import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import { overviewLinkSettingsApi } from './overview-link-settings';

vi.mock('./api-client', () => ({ default: { get: vi.fn(), put: vi.fn() } }));
beforeEach(() => vi.resetAllMocks());

const pairs = [
  {
    starshield_link_enabled: true,
    x_band_link_enabled: true,
    orbital_traffic_enabled: false,
    aircraft_history_enabled: true,
  },
  {
    starshield_link_enabled: false,
    x_band_link_enabled: true,
    orbital_traffic_enabled: false,
    aircraft_history_enabled: true,
  },
  {
    starshield_link_enabled: true,
    x_band_link_enabled: false,
    orbital_traffic_enabled: false,
    aircraft_history_enabled: true,
  },
  {
    starshield_link_enabled: false,
    x_band_link_enabled: false,
    orbital_traffic_enabled: false,
    aircraft_history_enabled: true,
  },
];

describe('overviewLinkSettingsApi', () => {
  it.each(pairs)(
    'reads a confirmed pair %j without replacing false',
    async (pair) => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: pair });
      await expect(overviewLinkSettingsApi.get()).resolves.toEqual(pair);
      expect(apiClient.get).toHaveBeenCalledWith(
        '/api/overview-links/settings',
        {
          signal: undefined,
        }
      );
    }
  );

  it('forwards read cancellation to HTTP', async () => {
    const controller = new AbortController();
    vi.mocked(apiClient.get).mockResolvedValue({ data: pairs[0] });
    await overviewLinkSettingsApi.get(controller.signal);
    expect(apiClient.get).toHaveBeenCalledWith('/api/overview-links/settings', {
      signal: controller.signal,
    });
  });

  it.each([
    [{ starshield_link_enabled: false }, pairs[1]],
    [{ x_band_link_enabled: false, orbital_traffic_enabled: false }, pairs[2]],
    [pairs[3], pairs[3]],
  ])(
    'sends only supplied fields and receives the full pair',
    async (changes, pair) => {
      vi.mocked(apiClient.put).mockResolvedValue({ data: pair });
      await expect(overviewLinkSettingsApi.update(changes)).resolves.toEqual(
        pair
      );
      expect(apiClient.put).toHaveBeenCalledWith(
        '/api/overview-links/settings',
        changes
      );
    }
  );

  it.each([
    null,
    undefined,
    [],
    {},
    { starshield_link_enabled: false },
    { starshield_link_enabled: false, x_band_link_enabled: null },
    {
      starshield_link_enabled: 'false',
      x_band_link_enabled: true,
      orbital_traffic_enabled: false,
    },
    { starshield_link_enabled: true, x_band_link_enabled: 1 },
  ])('rejects malformed GET and PUT responses %j', async (data) => {
    vi.mocked(apiClient.get).mockResolvedValue({ data });
    vi.mocked(apiClient.put).mockResolvedValue({ data });
    await expect(overviewLinkSettingsApi.get()).rejects.toThrow(
      'Invalid overview link settings'
    );
    await expect(
      overviewLinkSettingsApi.update({
        x_band_link_enabled: false,
        orbital_traffic_enabled: false,
      })
    ).rejects.toThrow('Invalid overview link settings');
  });
});

it.each([undefined, null, 'true', 1])(
  'orbital_is_off_until_confirmed: rejects %j',
  async (value) => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        starshield_link_enabled: true,
        x_band_link_enabled: true,
        orbital_traffic_enabled: value,
      },
    });
    await expect(overviewLinkSettingsApi.get()).rejects.toThrow(
      'Invalid overview link settings'
    );
  }
);

it('retains a confirmed disabled aircraft history layer', async () => {
  const settings = { ...pairs[0], aircraft_history_enabled: false };
  vi.mocked(apiClient.get).mockResolvedValue({ data: settings });
  await expect(overviewLinkSettingsApi.get()).resolves.toEqual(settings);
});

it('defaults aircraft history on for an older server response', async () => {
  const legacy = {
    starshield_link_enabled: true,
    x_band_link_enabled: true,
    orbital_traffic_enabled: false,
  };
  vi.mocked(apiClient.get).mockResolvedValue({ data: legacy });
  await expect(overviewLinkSettingsApi.get()).resolves.toMatchObject({
    aircraft_history_enabled: true,
  });
});

it.each([null, 'false', 0])(
  'rejects invalid aircraft history confirmation %j',
  async (value) => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { ...pairs[0], aircraft_history_enabled: value },
    });
    await expect(overviewLinkSettingsApi.get()).rejects.toThrow(
      'Invalid overview link settings'
    );
  }
);
