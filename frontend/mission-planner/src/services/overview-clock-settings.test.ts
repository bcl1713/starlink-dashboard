import { describe, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import { overviewClockSettingsApi } from './overview-clock-settings.ts';
vi.mock('./api-client', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));
describe('overviewClockSettingsApi', () => {
  it('gets the persistent operational-clock settings', async () => {
    const settings = {
      clocks: [
        {
          label: 'Zulu / UTC',
          time_zone: 'UTC',
        },
        {
          label: 'Washington, DC',
          time_zone: 'America/New_York',
        },
        {
          label: 'Omaha, NE',
          time_zone: 'America/Chicago',
        },
        {
          label: 'Tokyo, JP',
          time_zone: 'Asia/Tokyo',
        },
      ],
    };
    vi.mocked(apiClient.get).mockResolvedValue({
      data: settings,
    } as never);
    await expect(overviewClockSettingsApi.get()).resolves.toEqual(settings);
    expect(apiClient.get).toHaveBeenCalledWith('/api/overview-clocks/settings');
  });
  it('replaces the complete editable operational-clock collection', async () => {
    const settings = {
      clocks: [
        {
          label: 'Zulu Custom',
          time_zone: 'UTC',
        },
        {
          label: 'Denver, CO',
          time_zone: 'America/Denver',
        },
        {
          label: 'Omaha, NE',
          time_zone: 'America/Chicago',
        },
        {
          label: 'Tokyo, JP',
          time_zone: 'Asia/Tokyo',
        },
      ],
    };
    vi.mocked(apiClient.put).mockResolvedValue({
      data: settings,
    } as never);
    await expect(overviewClockSettingsApi.update(settings)).resolves.toEqual(
      settings
    );
    expect(apiClient.put).toHaveBeenCalledWith(
      '/api/overview-clocks/settings',
      settings
    );
  });
});
