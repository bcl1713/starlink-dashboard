import { useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  aviationWeatherApi,
  type AviationSettings,
} from '@/services/aviation-weather';
import {
  AviationController,
  emptyAviationView,
} from '@/pages/aviation-weather/aviation-controller';
import { useAviationSettings } from './api/useAviationSettings';
export function useAviationWeather() {
  const settings = useAviationSettings().data;
  const binding = useMemo(() => createAviationBinding(), []);
  const view = useSyncExternalStore(binding.subscribe, binding.snapshot);
  useEffect(() => binding.setSettings(settings), [binding, settings]);
  return view;
}

function createAviationBinding() {
  let controller: AviationController | null = null,
    observed: AviationSettings | undefined,
    view = emptyAviationView;
  return {
    snapshot: () => view,
    setSettings: (next: AviationSettings | undefined) => {
      observed = next;
      controller?.setSettings(next);
    },
    subscribe: (listener: () => void) => {
      const owned = new AviationController(aviationWeatherApi);
      controller = owned;
      const unsubscribe = owned.subscribe(() => {
        view = owned.snapshot();
        listener();
      });
      owned.setVisible(!document.hidden);
      owned.setOnline(navigator.onLine);
      owned.start();
      owned.setSettings(observed);
      const visibility = () => owned.setVisible(!document.hidden),
        online = () => owned.setOnline(navigator.onLine);
      document.addEventListener('visibilitychange', visibility);
      window.addEventListener('online', online);
      window.addEventListener('offline', online);
      return () => {
        document.removeEventListener('visibilitychange', visibility);
        window.removeEventListener('online', online);
        window.removeEventListener('offline', online);
        unsubscribe();
        owned.dispose();
        if (controller === owned) {
          controller = null;
          view = emptyAviationView;
        }
      };
    },
  };
}
