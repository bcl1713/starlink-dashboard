import { useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  aviationWeatherApi,
  type AviationSettings,
} from '@/services/aviation-weather';
import {
  AviationController,
  emptyAviationView,
  type AviationLayerView,
} from '@/pages/aviation-weather/aviation-controller';
import { useAviationSettings } from './api/useAviationSettings';
import { useRouteSigmets } from './api/useRouteSigmets';
export function useAviationWeather(externalSigmet?: AviationLayerView) {
  const settings = useAviationSettings().data;
  const source = useRouteSigmets();
  const binding = useMemo(() => createAviationBinding(), []);
  const view = useSyncExternalStore(binding.subscribe, binding.snapshot);
  useEffect(() => binding.setSettings(settings), [binding, settings]);
  const sigmet = useMemo<AviationLayerView>(
    () =>
      externalSigmet ??
      (!settings?.sigmet
        ? { state: 'off' }
        : source.available && source.snapshot && source.collection
          ? {
              state:
                source.snapshot.sigmet_product.state === 'stale' ||
                source.nowMs >= source.snapshot.sigmet_product.fresh_until_ms!
                  ? 'stale'
                  : 'current',
              product: source.snapshot.sigmet_product,
              data: source.collection,
            }
          : { state: source.error ? 'unavailable' : 'loading' }),
    [externalSigmet, settings, source]
  );
  useEffect(() => binding.setExternalSigmet(sigmet), [binding, sigmet]);
  return externalSigmet
    ? {
        ...view,
        now: Math.max(view.now, source.nowMs ?? 0),
        layers: { ...view.layers, sigmet: externalSigmet },
      }
    : view;
}

function createAviationBinding() {
  let controller: AviationController | null = null,
    observed: AviationSettings | undefined,
    view = emptyAviationView,
    externalSigmet: AviationLayerView = { state: 'off' };
  return {
    snapshot: () => view,
    setSettings: (next: AviationSettings | undefined) => {
      observed = next;
      controller?.setSettings(next);
    },
    setExternalSigmet: (next: AviationLayerView) => {
      externalSigmet = next;
      controller?.setExternalSigmet(next);
    },
    subscribe: (listener: () => void) => {
      const owned = new AviationController(
        aviationWeatherApi,
        fetch,
        undefined,
        { externalSigmet: true }
      );
      controller = owned;
      const unsubscribe = owned.subscribe(() => {
        view = owned.snapshot();
        listener();
      });
      owned.setVisible(!document.hidden);
      owned.setOnline(navigator.onLine);
      owned.start();
      owned.setSettings(observed);
      owned.setExternalSigmet(externalSigmet);
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
