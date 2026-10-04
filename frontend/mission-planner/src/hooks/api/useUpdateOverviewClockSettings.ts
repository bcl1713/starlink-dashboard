import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  overviewClockSettingsApi,
  type OverviewClockSettings,
} from '@/services/overview-clock-settings';

export function useUpdateOverviewClockSettings() {
  const queryClient = useQueryClient();
  const queryKey = ['overview-clock-settings'];
  return useMutation({
    scope: { id: 'overview-clock-settings' },
    mutationFn: async (settings: OverviewClockSettings) => {
      // Queued saves must also cancel the preceding save's invalidation read.
      await queryClient.cancelQueries({ queryKey });
      return overviewClockSettingsApi.update(settings);
    },
    onSuccess: (settings) => {
      // A poll/focus/mount read may have started during the PUT.
      void queryClient.cancelQueries({ queryKey });
      queryClient.setQueryData(queryKey, settings);
      void queryClient.invalidateQueries({ queryKey });
    },
  });
}
