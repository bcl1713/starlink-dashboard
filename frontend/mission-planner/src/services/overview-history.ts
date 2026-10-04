import apiClient from './api-client';
export type OverviewHistorySample = [number, number];
export interface OverviewHistoryRollup {
  state: 'available' | 'unavailable';
  min: OverviewHistorySample[];
  avg: OverviewHistorySample[];
  max: OverviewHistorySample[];
}
export interface OverviewHistoryBundle {
  window_seconds: number;
  start_timestamp_seconds: number;
  end_timestamp_seconds: number;
  step_seconds: number;
  series: Record<string, OverviewHistorySample[]>;
  /** Optional for previously cached responses; absence means aggregates unavailable. */
  rolling_5m?: Record<string, OverviewHistoryRollup>;
}

export interface OverviewHistorySettings {
  window_seconds: number;
}

export const overviewHistoryApi = {
  async get(signal?: AbortSignal): Promise<OverviewHistoryBundle> {
    const response = await apiClient.get<OverviewHistoryBundle>(
      '/api/overview-history',
      { signal }
    );
    return response.data;
  },
};

export const overviewHistorySettingsApi = {
  async get(signal?: AbortSignal): Promise<OverviewHistorySettings> {
    const response = await apiClient.get<OverviewHistorySettings>(
      '/api/overview-history/settings',
      { signal }
    );
    return response.data;
  },
  async update(windowSeconds: number): Promise<OverviewHistorySettings> {
    const response = await apiClient.put<OverviewHistorySettings>(
      '/api/overview-history/settings',
      {
        window_seconds: windowSeconds,
      }
    );
    return response.data;
  },
};
