import {
  useIsMutating,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import {
  overviewLinkSettingsApi,
  type OverviewLinkSettingsUpdate,
  type OverviewLinkSettings,
} from '@/services/overview-link-settings';

export function useUpdateOverviewLinkSettings() {
  const queryClient = useQueryClient();
  const queryKey = ['overview-link-settings'];
  const pending = useIsMutating({ mutationKey: ['overview-display-write'] });
  const mutation = useMutation({
    mutationKey: ['overview-display-write'],
    networkMode: 'always',
    scope: { id: 'overview-link-settings' },
    mutationFn: async (changes: OverviewLinkSettingsUpdate) => {
      // Run inside the mutation scope so queued saves also cancel reads started
      // by the preceding save's invalidation.
      const baseline = queryClient.getQueryData<OverviewLinkSettings>(queryKey);
      const expected = baseline
        ? Object.fromEntries(
            Object.keys(changes).map((field) => [
              field,
              baseline[field as keyof OverviewLinkSettings],
            ])
          )
        : undefined;
      await queryClient.cancelQueries({ queryKey });
      return overviewLinkSettingsApi.update(changes, expected);
    },
    onSuccess: (settings) => {
      // Poll/focus/mount can start another GET during the PUT. Cancel that read
      // synchronously before publishing the full confirmed pair.
      void queryClient.cancelQueries({ queryKey });
      queryClient.setQueryData(queryKey, settings);
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey });
    },
    retry: false,
  });
  return { ...mutation, isPending: mutation.isPending || pending > 0 };
}
