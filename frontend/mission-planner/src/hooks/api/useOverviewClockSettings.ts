import { overviewClockSettingsApi } from '@/services/overview-clock-settings';
import { useQuery } from '@tanstack/react-query';

export function useOverviewClockSettings() {
  return useQuery({
    queryKey: ['overview-clock-settings'],
    queryFn: overviewClockSettingsApi.get,
    retry: false,
  });
}
