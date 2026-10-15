import { useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  overviewWeatherApi,
  type WeatherSettingsObservation,
} from '@/services/overview-weather';
import { WeatherAtlasLoader } from '@/pages/weather/weather-atlas';
import { WeatherController } from '@/pages/weather/weather-controller';
import {
  browserWeatherClock,
  emptyWeatherView,
} from '@/pages/weather/weather-state';
import { useOverviewWeatherSettings } from './api/useOverviewWeatherSettings';

export function useOverviewWeatherLayer() {
  const settings = useOverviewWeatherSettings().data;
  // Subscribe owns the runtime, so StrictMode cleanup/remount gets a fresh owner.
  const binding = useMemo(() => createWeatherBinding(), []);
  const view = useSyncExternalStore(binding.subscribe, binding.snapshot);
  useEffect(() => {
    binding.setSettings(settings);
  }, [binding, settings]);
  return view;
}

function createWeatherBinding() {
  let controller: WeatherController | null = null;
  let observation: WeatherSettingsObservation | undefined;
  let view = emptyWeatherView;
  return {
    snapshot: () => view,
    setSettings: (next: WeatherSettingsObservation | undefined) => {
      observation = next;
      controller?.setSettings(next);
    },
    subscribe: (listener: () => void) => {
      const owned = new WeatherController(
        overviewWeatherApi,
        new WeatherAtlasLoader(fetch, browserWeatherClock),
        browserWeatherClock
      );
      controller = owned;
      const unsubscribe = owned.subscribe(() => {
        view = owned.snapshot();
        listener();
      });
      owned.setVisible(!document.hidden);
      owned.setSettings(observation);
      const visibility = () => owned.setVisible(!document.hidden);
      const reconnect = () => owned.reconnect();
      const disconnect = () => owned.disconnect();
      document.addEventListener('visibilitychange', visibility);
      window.addEventListener('online', reconnect);
      window.addEventListener('offline', disconnect);
      return () => {
        document.removeEventListener('visibilitychange', visibility);
        window.removeEventListener('online', reconnect);
        window.removeEventListener('offline', disconnect);
        unsubscribe();
        owned.dispose();
        controller = null;
        view = emptyWeatherView;
      };
    },
  };
}
