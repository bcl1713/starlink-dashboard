import { useEffect, useState, useSyncExternalStore } from 'react';
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
import { usePrefersReducedMotion } from './usePrefersReducedMotion';
export function useGfsWeather() {
  const settings = useAviationSettings().data;
  const reducedMotion = usePrefersReducedMotion();
  const [binding] = useState(() => createBinding(reducedMotion));
  const view = useSyncExternalStore(binding.subscribe, binding.snapshot);
  useEffect(() => binding.setSettings(settings), [binding, settings]);
  useEffect(
    () => binding.setReducedMotion(reducedMotion),
    [binding, reducedMotion]
  );
  return view;
}
function createBinding(initialMotion: boolean) {
  let controller: GfsController | null = null,
    observed: AviationSettings | undefined,
    view = emptyGfsView;
  let reducedMotion = initialMotion;
  return {
    snapshot: () => view,
    setReducedMotion: (reduced: boolean) => {
      reducedMotion = reduced;
      controller?.setReducedMotion(reduced);
    },
    setSettings: (next: AviationSettings | undefined) => {
      observed = next;
      if (next) controller?.setSettings(next);
    },
    subscribe: (listener: () => void) => {
      const owned = new GfsController(aviationWeatherApi, {
        draw: createGridDrawing,
      });
      controller = owned;
      owned.setReducedMotion(reducedMotion);
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
