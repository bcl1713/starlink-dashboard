import { useQuery } from '@tanstack/react-query';
import { overviewUpcomingPoisApi } from '@/services/overview-upcoming-pois';

export function useOverviewUpcomingPois(pacedRun = false) {
  return useQuery({
    queryKey: ['overview-upcoming-pois'],
    queryFn: overviewUpcomingPoisApi.get,
    refetchInterval: pacedRun ? 1_000 : 5_000,
    refetchIntervalInBackground: true,
    retry: false,
  });
}
