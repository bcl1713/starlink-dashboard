import { useQuery } from '@tanstack/react-query';
import { overviewUpcomingPoisApi } from '@/services/overview-upcoming-pois';

export function useOverviewUpcomingPois() {
  return useQuery({
    queryKey: ['overview-upcoming-pois'],
    queryFn: overviewUpcomingPoisApi.get,
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}
