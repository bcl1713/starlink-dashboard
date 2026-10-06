import { useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  aviationWeatherApi,
  type AviationSettings,
} from '@/services/aviation-weather';
import {
  GfsController,
  emptyGfsView,
} from '@/pages/aviation-weather/gfs-controller';
import { createGridDrawing } from '@/pages/aviation-weather/grid-renderer';
import { useAviationSettings } from './api/useAviationSettings';
export function useGfsWeather() {
  const settings = useAviationSettings().data,
    binding = useMemo(() => createBinding(), []);
  const view = useSyncExternalStore(binding.subscribe, binding.snapshot);
  useEffect(() => binding.setSettings(settings), [binding, settings]);
  return view;
}
function createBinding() {
  let controller: GfsController | null = null,
    observed: AviationSettings | undefined,
    view = emptyGfsView;
  return {
    snapshot: () => view,
    setSettings: (next: AviationSettings | undefined) => {
      observed = next;
      if (next) controller?.setSettings(next);
    },
    subscribe: (listener: () => void) => {
      const owned = new GfsController(aviationWeatherApi, {
        draw: createGridDrawing,
      });
      controller = owned;
      const unsubscribe = owned.subscribe(() => {
        view = owned.getSnapshot();
        listener();
      });
      owned.setVisible(!document.hidden);
      owned.setOnline(navigator.onLine);
      if (observed) owned.setSettings(observed);
      owned.start();
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
        owned.stop();
        if (controller === owned) {
          controller = null;
          view = emptyGfsView;
        }
      };
    },
  };
}
