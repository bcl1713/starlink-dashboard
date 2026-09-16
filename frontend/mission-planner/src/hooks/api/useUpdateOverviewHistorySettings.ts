import { useMutation, useQueryClient } from '@tanstack/react-query';
import { overviewHistorySettingsApi } from '@/services/overview-history';
export function useUpdateOverviewHistorySettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: overviewHistorySettingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['overview-history-settings'],
      });
      queryClient.invalidateQueries({
        queryKey: ['overview-history'],
      });
    },
  });
}
