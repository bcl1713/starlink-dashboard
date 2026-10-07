import apiClient from './api-client';

// Additive preferences preserve the existing layout on older installations.
export const OVERVIEW_VISIBILITY_DEFAULTS = {
  operational_clocks_enabled: true,
  arrival_panel_enabled: true,
  planned_satellite_panel_enabled: true,
  map_status_enabled: true,
  legend_enabled: true,
  latency_panel_enabled: true,
  downlink_panel_enabled: true,
  uplink_panel_enabled: true,
  packet_loss_panel_enabled: true,
  obstruction_panel_enabled: true,
  aircraft_marker_enabled: true,
  planned_route_enabled: true,
  poi_markers_enabled: true,
  ground_entry_point_enabled: true,
  configured_satellites_enabled: true,
} as const;

export type OverviewVisibilityField = keyof typeof OVERVIEW_VISIBILITY_DEFAULTS;

export interface OverviewLinkSettings
  extends Partial<Record<OverviewVisibilityField, boolean>> {
  starshield_link_enabled: boolean;
  x_band_link_enabled: boolean;
  orbital_traffic_enabled: boolean;
  aircraft_history_enabled: boolean;
  country_borders_enabled: boolean;
  state_borders_enabled: boolean;
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
      typeof data.aircraft_history_enabled !== 'boolean') ||
    ('country_borders_enabled' in data &&
      typeof data.country_borders_enabled !== 'boolean') ||
    Object.keys(OVERVIEW_VISIBILITY_DEFAULTS).some(
      (field) => field in data && typeof Reflect.get(data, field) !== 'boolean'
    ) ||
    ('state_borders_enabled' in data &&
      typeof data.state_borders_enabled !== 'boolean')
  ) {
    throw new Error('Invalid overview link settings');
  }
  return {
    ...Object.fromEntries(
      Object.keys(OVERVIEW_VISIBILITY_DEFAULTS).map((field) => [
        field,
        field in data ? Reflect.get(data, field) : true,
      ])
    ),
    starshield_link_enabled: data.starshield_link_enabled,
    x_band_link_enabled: data.x_band_link_enabled,
    orbital_traffic_enabled: data.orbital_traffic_enabled,
    // Older servers omit this additive preference; retain their visible trail.
    aircraft_history_enabled:
      'aircraft_history_enabled' in data &&
      typeof data.aircraft_history_enabled === 'boolean'
        ? data.aircraft_history_enabled
        : true,
    country_borders_enabled:
      'country_borders_enabled' in data
        ? (data.country_borders_enabled as boolean)
        : false,
    state_borders_enabled:
      'state_borders_enabled' in data
        ? (data.state_borders_enabled as boolean)
        : false,
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
