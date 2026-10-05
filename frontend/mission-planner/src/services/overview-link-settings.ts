import apiClient from './api-client';

export interface OverviewLinkSettings {
  starshield_link_enabled: boolean;
  x_band_link_enabled: boolean;
  orbital_traffic_enabled: boolean;
  aircraft_history_enabled: boolean;
}

export type OverviewLinkSettingsUpdate = Partial<OverviewLinkSettings>;

function confirmedSettings(data: unknown): OverviewLinkSettings {
  if (
    !data ||
    typeof data !== 'object' ||
    !('starshield_link_enabled' in data) ||
    !('x_band_link_enabled' in data) ||
    !('orbital_traffic_enabled' in data) ||
    typeof data.orbital_traffic_enabled !== 'boolean' ||
    typeof data.starshield_link_enabled !== 'boolean' ||
    typeof data.x_band_link_enabled !== 'boolean' ||
    ('aircraft_history_enabled' in data &&
      typeof data.aircraft_history_enabled !== 'boolean')
  ) {
    throw new Error('Invalid overview link settings');
  }
  return {
    starshield_link_enabled: data.starshield_link_enabled,
    x_band_link_enabled: data.x_band_link_enabled,
    orbital_traffic_enabled: data.orbital_traffic_enabled,
    // Older servers omit this additive preference; retain their visible trail.
    aircraft_history_enabled:
      'aircraft_history_enabled' in data &&
      typeof data.aircraft_history_enabled === 'boolean'
        ? data.aircraft_history_enabled
        : true,
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
