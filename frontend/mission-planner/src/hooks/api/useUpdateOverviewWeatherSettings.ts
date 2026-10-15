import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  overviewWeatherApi,
  acceptWeatherObservation,
  type WeatherSettingsObservation,
} from '@/services/overview-weather';
import { weatherSettingsKey } from './useOverviewWeatherSettings';

export function useUpdateOverviewWeatherSettings() {
  const client = useQueryClient();
  return useMutation({
    scope: { id: 'overview-weather-settings' },
    mutationFn: async (update: { enabled: boolean }) => {
      await client.cancelQueries({ queryKey: weatherSettingsKey });
      return overviewWeatherApi.updateSettings(update);
    },
    onSuccess: async (settings) => {
      await client.cancelQueries({ queryKey: weatherSettingsKey });
      client.setQueryData<WeatherSettingsObservation>(
        weatherSettingsKey,
        (old) =>
          acceptWeatherObservation(old, {
            settings,
            receivedAtMono: performance.now(),
          })
      );
    },
    retry: false,
  });
}
