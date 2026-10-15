import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { overviewAdsbApi } from '@/services/overview-adsb';
export function useOverviewAdsbTraffic(enabled: boolean) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['overview-adsb-traffic'],
    queryFn: ({ signal }) => overviewAdsbApi.getTraffic(signal),
    enabled,
    retry: false,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: 'always',
  });
  const { refetch } = query;
  useEffect(() => {
    if (!enabled) {
      void queryClient.cancelQueries({ queryKey: ['overview-adsb-traffic'] });
      return;
    }
    const visible = () => {
      if (!document.hidden) void refetch();
    };
    document.addEventListener('visibilitychange', visible);
    return () => document.removeEventListener('visibilitychange', visible);
  }, [enabled, refetch, queryClient]);
  return query;
}
