import { overviewRefreshOptions } from './overview-refresh-options';
import { useQuery } from '@tanstack/react-query';
import { overviewLinkSettingsApi } from '@/services/overview-link-settings';

export function useOverviewLinkSettings(live = false) {
  return useQuery({
    queryKey: ['overview-link-settings'],
    queryFn: ({ signal }) => overviewLinkSettingsApi.get(signal),
    retry: false,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    ...overviewRefreshOptions(live),
  });
}
