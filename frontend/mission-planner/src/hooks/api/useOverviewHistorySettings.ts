import { overviewRefreshOptions } from './overview-refresh-options';
import { useQuery } from '@tanstack/react-query';
import { overviewHistorySettingsApi } from '@/services/overview-history';
export function useOverviewHistorySettings(live = false) {
  return useQuery({
    queryKey: ['overview-history-settings'],
    queryFn: ({ signal }) => overviewHistorySettingsApi.get(signal),
    retry: false,
    ...overviewRefreshOptions(live),
  });
}
