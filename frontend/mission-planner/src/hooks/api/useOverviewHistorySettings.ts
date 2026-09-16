import { useQuery } from '@tanstack/react-query';
import { overviewHistorySettingsApi } from '@/services/overview-history';
export function useOverviewHistorySettings() {
  return useQuery({
    queryKey: ['overview-history-settings'],
    queryFn: overviewHistorySettingsApi.get,
    retry: false,
  });
}
