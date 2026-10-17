import { useMutation, useQueryClient } from '@tanstack/react-query';
import { overviewHistorySettingsApi } from '@/services/overview-history';

export function useUpdateOverviewHistorySettings() {
  const queryClient = useQueryClient();
  const queryKey = ['overview-history-settings'];
  return useMutation({
    networkMode: 'always',
    retry: false,
    scope: { id: 'overview-history-settings' },
    mutationFn: async (windowSeconds: number) => {
      // Run inside the scope so each queued save cancels obsolete reads.
      const baseline = queryClient.getQueryData<{ window_seconds: number }>(
        queryKey
      );
      await queryClient.cancelQueries({ queryKey });
      return overviewHistorySettingsApi.update(
        windowSeconds,
        baseline?.window_seconds
      );
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey });
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
