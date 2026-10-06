import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  aviationWeatherApi,
  type AviationLayer,
  type AviationSettings,
} from '@/services/aviation-weather';
export const aviationSettingsKey = ['aviation-weather', 'settings'];
function accept(
  previous: AviationSettings | undefined,
  next: AviationSettings
) {
  return previous && previous.revision > next.revision ? previous : next;
}
export function useAviationSettings() {
  const client = useQueryClient();
  const [active, setActive] = useState(
    () => !document.hidden && navigator.onLine
  );
  const query = useQuery({
    queryKey: aviationSettingsKey,
    queryFn: ({ signal }) => aviationWeatherApi.getSettings(signal),
    enabled: active,
    retry: false,
    refetchInterval: active ? 5000 : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    structuralSharing: (old, next) =>
      accept(old as AviationSettings | undefined, next as AviationSettings),
  });
  const { refetch } = query;
  useEffect(() => {
    const sync = () => {
      const available = !document.hidden && navigator.onLine;
      setActive(available);
      if (!available)
        void client.cancelQueries({ queryKey: aviationSettingsKey });
      else void refetch();
    };
    document.addEventListener('visibilitychange', sync);
    window.addEventListener('online', sync);
    window.addEventListener('offline', sync);
    return () => {
      document.removeEventListener('visibilitychange', sync);
      window.removeEventListener('online', sync);
      window.removeEventListener('offline', sync);
    };
  }, [client, refetch]);
  return query;
}
export function useSaveAviationSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (changes: Partial<Pick<AviationSettings, AviationLayer>>) =>
      aviationWeatherApi.updateSettings(changes),
    onSuccess: (next) => {
      client.setQueryData<AviationSettings>(aviationSettingsKey, (previous) =>
        accept(previous, next)
      );
    },
  });
}
