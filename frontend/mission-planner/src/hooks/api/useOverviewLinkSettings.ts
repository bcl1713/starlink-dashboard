import { useQuery } from '@tanstack/react-query';
import { overviewLinkSettingsApi } from '@/services/overview-link-settings';

export function useOverviewLinkSettings() {
  return useQuery({
    queryKey: ['overview-link-settings'],
    queryFn: ({ signal }) => overviewLinkSettingsApi.get(signal),
    retry: false,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
}
