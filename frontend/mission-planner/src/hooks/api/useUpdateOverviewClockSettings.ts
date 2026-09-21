import { useMutation, useQueryClient } from '@tanstack/react-query';
import { overviewClockSettingsApi } from '@/services/overview-clock-settings';
export function useUpdateOverviewClockSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: overviewClockSettingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['overview-clock-settings'],
      });
    },
  });
}
