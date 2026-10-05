import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  overviewAdsbApi,
  type AdsbSettings,
  type AdsbSettingsUpdate,
} from '@/services/overview-adsb';
export function useUpdateOverviewAdsbSettings() {
  const client = useQueryClient();
  const key = ['overview-adsb-settings'];
  return useMutation({
    scope: { id: 'overview-adsb-settings' },
    mutationFn: async (changes: AdsbSettingsUpdate) => {
      await client.cancelQueries({ queryKey: key });
      return overviewAdsbApi.updateSettings(changes);
    },
    onSuccess: (settings) => {
      void client.cancelQueries({ queryKey: key });
      client.setQueryData<AdsbSettings>(key, (old) =>
        old && old.revision > settings.revision ? old : settings
      );
      void client.invalidateQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: ['overview-adsb-traffic'] });
      void client.invalidateQueries({ queryKey: ['overview-adsb-catalog'] });
    },
    retry: false,
  });
}
