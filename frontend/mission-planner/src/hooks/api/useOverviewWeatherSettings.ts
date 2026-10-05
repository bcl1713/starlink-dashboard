import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  overviewWeatherApi,
  acceptWeatherObservation,
  type WeatherSettingsObservation,
} from '@/services/overview-weather';

export const weatherSettingsKey = ['overview-weather-settings'];

export function useOverviewWeatherSettings() {
  const [visible, setVisible] = useState(() => !document.hidden);
  const client = useQueryClient();
  const query = useQuery({
    queryKey: weatherSettingsKey,
    queryFn: async ({ signal }): Promise<WeatherSettingsObservation> => ({
      settings: await overviewWeatherApi.getSettings(signal),
      receivedAtMono: performance.now(),
    }),
    enabled: visible,
    retry: false,
    refetchInterval: visible ? 5000 : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: 'always',
    refetchOnReconnect: false,
    structuralSharing: (old, next) =>
      acceptWeatherObservation(
        old as WeatherSettingsObservation | undefined,
        next as WeatherSettingsObservation
      ),
  });
  const { refetch } = query;
  useEffect(() => {
    const visibility = () => {
      setVisible(!document.hidden);
      if (document.hidden)
        void client.cancelQueries({ queryKey: weatherSettingsKey });
    };
    const online = () => {
      if (!document.hidden) void refetch();
    };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('online', online);
    return () => {
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('online', online);
    };
  }, [client, refetch]);
  return query;
}
