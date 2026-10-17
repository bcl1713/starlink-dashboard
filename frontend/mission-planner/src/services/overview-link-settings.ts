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
  flight_events_enabled: true,
  x_band_events_enabled: true,
  ka_events_enabled: true,
  starshield_events_enabled: true,
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
    changes: OverviewLinkSettingsUpdate,
    expectedValues?: OverviewLinkSettingsUpdate
  ): Promise<OverviewLinkSettings> {
    const response = await apiClient.put<unknown>(
      '/api/overview-links/settings',
      expectedValues ? { ...changes, expected_values: expectedValues } : changes
    );
    return confirmedSettings(response.data);
  },
};

export const PRESET_NAMES = ['normal', 'communications', 'weather'] as const;
export type OverviewPresetName = (typeof PRESET_NAMES)[number];
export interface OverviewPreset {
  version: number;
  settings: OverviewLinkSettingsUpdate;
}
export type OverviewPresets = Record<OverviewPresetName, OverviewPreset | null>;
const visibilityFields = new Set([
  ...Object.keys(OVERVIEW_VISIBILITY_DEFAULTS),
  'starshield_link_enabled',
  'x_band_link_enabled',
  'orbital_traffic_enabled',
  'aircraft_history_enabled',
  'country_borders_enabled',
  'state_borders_enabled',
]);
function confirmedPreset(data: unknown): OverviewPreset {
  if (
    !data ||
    typeof data !== 'object' ||
    !('version' in data) ||
    !Number.isSafeInteger(data.version) ||
    Number(data.version) < 1 ||
    !('settings' in data) ||
    !data.settings ||
    typeof data.settings !== 'object' ||
    Object.keys(data.settings).length === 0 ||
    Object.entries(data.settings).some(
      ([key, value]) => !visibilityFields.has(key) || typeof value !== 'boolean'
    )
  ) {
    throw new Error('Invalid Overview preset acknowledgment');
  }
  return data as OverviewPreset;
}
export const overviewPresetsApi = {
  async get(signal?: AbortSignal): Promise<OverviewPresets> {
    const { data } = await apiClient.get('/api/overview-links/presets', {
      signal,
    });
    if (
      !data ||
      typeof data !== 'object' ||
      PRESET_NAMES.some((name) => !(name in data))
    )
      throw new Error('Invalid Overview presets response');
    return Object.fromEntries(
      PRESET_NAMES.map((name) => [
        name,
        data[name] === null ? null : confirmedPreset(data[name]),
      ])
    ) as OverviewPresets;
  },
  async save(
    name: OverviewPresetName,
    settings: OverviewLinkSettingsUpdate,
    expectedVersion: number
  ): Promise<OverviewPreset> {
    const { data } = await apiClient.put(
      `/api/overview-links/presets/${name}`,
      { settings, expected_version: expectedVersion }
    );
    return confirmedPreset(data);
  },
};
