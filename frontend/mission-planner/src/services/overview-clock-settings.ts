import apiClient from './api-client';
export interface OverviewClockSetting {
  label: string;
  time_zone: string;
}
export interface OverviewClockSettings {
  clocks: OverviewClockSetting[];
}
export const overviewClockSettingsApi = {
  async get(): Promise<OverviewClockSettings> {
    const response = await apiClient.get<OverviewClockSettings>(
      '/api/overview-clocks/settings'
    );
    return response.data;
  },
  async update(
    settings: OverviewClockSettings
  ): Promise<OverviewClockSettings> {
    const response = await apiClient.put<OverviewClockSettings>(
      '/api/overview-clocks/settings',
      settings
    );
    return response.data;
  },
};
