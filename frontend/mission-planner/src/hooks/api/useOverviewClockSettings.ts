import { overviewRefreshOptions } from './overview-refresh-options';
import { overviewClockSettingsApi } from '@/services/overview-clock-settings';
import { useQuery } from '@tanstack/react-query';

export function useOverviewClockSettings(live = false) {
  return useQuery({
    queryKey: ['overview-clock-settings'],
    queryFn: ({ signal }) => overviewClockSettingsApi.get(signal),
    retry: false,
    ...overviewRefreshOptions(live),
  });
}
