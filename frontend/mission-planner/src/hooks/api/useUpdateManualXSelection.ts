import { useMutation, useQueryClient } from '@tanstack/react-query';
import { activeXLinkApi } from '@/services/active-x-link';

export function useUpdateManualXSelection() {
  const client = useQueryClient();
  const queryKey = ['active-x-link'];
  return useMutation({
    scope: { id: 'manual-x-selection' },
    mutationFn: async (satelliteId: string | null) => {
      await client.cancelQueries({ queryKey });
      return activeXLinkApi.update(satelliteId);
    },
    onSuccess: (selection) => {
      void client.cancelQueries({ queryKey });
      client.setQueryData(queryKey, selection);
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey });
    },
    retry: false,
  });
}
