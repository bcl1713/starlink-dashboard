import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  overviewLinkSettingsApi,
  type OverviewLinkSettingsUpdate,
} from '@/services/overview-link-settings';

export function useUpdateOverviewLinkSettings() {
  const queryClient = useQueryClient();
  const queryKey = ['overview-link-settings'];
  return useMutation({
    scope: { id: 'overview-link-settings' },
    mutationFn: async (changes: OverviewLinkSettingsUpdate) => {
      // Run inside the mutation scope so queued saves also cancel reads started
      // by the preceding save's invalidation.
      await queryClient.cancelQueries({ queryKey });
      return overviewLinkSettingsApi.update(changes);
    },
    onSuccess: (settings) => {
      // Poll/focus/mount can start another GET during the PUT. Cancel that read
      // synchronously before publishing the full confirmed pair.
      void queryClient.cancelQueries({ queryKey });
      queryClient.setQueryData(queryKey, settings);
      void queryClient.invalidateQueries({ queryKey });
    },
    retry: false,
  });
}
