import apiClient from './api-client';
export type OverviewHistorySample = [number, number];
export interface OverviewHistoryBundle {
  window_seconds: number;
  start_timestamp_seconds: number;
  end_timestamp_seconds: number;
  step_seconds: number;
  series: Record<string, OverviewHistorySample[]>;
}

export interface OverviewHistorySettings {
  window_seconds: number;
}

export const overviewHistoryApi = {
  async get(): Promise<OverviewHistoryBundle> {
    const response = await apiClient.get<OverviewHistoryBundle>(
      '/api/overview-history'
    );
    return response.data;
  },
};

export const overviewHistorySettingsApi = {
  async get(): Promise<OverviewHistorySettings> {
    const response = await apiClient.get<OverviewHistorySettings>(
      '/api/overview-history/settings'
    );
    return response.data;
  },
};
