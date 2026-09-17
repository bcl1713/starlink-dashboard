import { useQuery } from '@tanstack/react-query';
import { overviewHistoryApi } from '@/services/overview-history';
export function useOverviewHistory() {
  return useQuery({
    queryKey: ['overview-history'],
    queryFn: overviewHistoryApi.get,
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}
