import { useMutation, useQueryClient } from '@tanstack/react-query';
import { overviewHistorySettingsApi } from '@/services/overview-history';

export function useUpdateOverviewHistorySettings() {
  const queryClient = useQueryClient();
  const queryKey = ['overview-history-settings'];
  return useMutation({
    scope: { id: 'overview-history-settings' },
    mutationFn: async (windowSeconds: number) => {
      // Run inside the scope so each queued save cancels obsolete reads.
      await queryClient.cancelQueries({ queryKey });
      return overviewHistorySettingsApi.update(windowSeconds);
    },
    onSuccess: (settings) => {
      // Cancel reads begun during PUT before publishing the confirmed window.
      void queryClient.cancelQueries({ queryKey });
      queryClient.setQueryData(queryKey, settings);
      void queryClient.invalidateQueries({ queryKey });
      void queryClient.invalidateQueries({ queryKey: ['overview-history'] });
    },
  });
}
