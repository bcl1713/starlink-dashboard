import apiClient from './api-client';

export interface OverviewLinkSettings {
  starshield_link_enabled: boolean;
  x_band_link_enabled: boolean;
}

export type OverviewLinkSettingsUpdate = Partial<OverviewLinkSettings>;

function confirmedSettings(data: unknown): OverviewLinkSettings {
  if (
    !data ||
    typeof data !== 'object' ||
    !('starshield_link_enabled' in data) ||
    !('x_band_link_enabled' in data) ||
    typeof data.starshield_link_enabled !== 'boolean' ||
    typeof data.x_band_link_enabled !== 'boolean'
  ) {
    throw new Error('Invalid overview link settings');
  }
  return {
    starshield_link_enabled: data.starshield_link_enabled,
    x_band_link_enabled: data.x_band_link_enabled,
  };
}

export const overviewLinkSettingsApi = {
  async get(signal?: AbortSignal): Promise<OverviewLinkSettings> {
    const response = await apiClient.get<unknown>(
      '/api/overview-links/settings',
      {
        signal,
      }
    );
    return confirmedSettings(response.data);
  },
  async update(
    changes: OverviewLinkSettingsUpdate
  ): Promise<OverviewLinkSettings> {
    const response = await apiClient.put<unknown>(
      '/api/overview-links/settings',
      changes
    );
    return confirmedSettings(response.data);
  },
};
