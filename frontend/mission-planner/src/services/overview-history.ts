import apiClient from './api-client';
export type OverviewHistorySample = [number, number];
export interface OverviewHistoryBundle {
  window_seconds: number;
  start_timestamp_seconds: number;
  end_timestamp_seconds: number;
  step_seconds: number;
  series: Record<string, OverviewHistorySample[]>;
}
export const overviewHistoryApi = {
  async get(): Promise<OverviewHistoryBundle> {
    const response = await apiClient.get<OverviewHistoryBundle>(
      '/api/overview-history'
    );
    return response.data;
  },
};
