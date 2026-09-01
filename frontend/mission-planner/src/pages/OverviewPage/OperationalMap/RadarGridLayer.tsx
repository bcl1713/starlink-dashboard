import { useEffect, useMemo } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';

import type { OverviewDataController } from '../overview-data-types';
import { createRadarGridLayerController } from './radar-grid-layer-controller';
import { radarGridLayerTestInternals } from './radar-grid-layer-test-internals';

interface RadarGridLayerProps {
  readonly enabled: boolean;
  readonly radarRefreshToken: number;
  readonly reportRadarResult: OverviewDataController['reportRadarResult'];
}

export function RadarGridLayer({
  enabled,
  radarRefreshToken,
  reportRadarResult,
}: RadarGridLayerProps) {
  const map = useMap();
  const controller = useMemo(
    () =>
      createRadarGridLayerController({
        radarRefreshToken: 0,
        reportRadarResult,
      }),
    [reportRadarResult]
  );
  const { layer, manager } = controller;

  useEffect(() => {
    controller.setToken(radarRefreshToken);
  }, [controller, radarRefreshToken]);

  useEffect(() => {
    if (!radarGridLayerTestInternals.enabled) return;
    radarTestManagers.add(manager);
    radarTestLayers.add(layer);
    return () => {
      radarTestManagers.delete(manager);
      radarTestLayers.delete(layer);
    };
  }, [layer, manager]);

  useEffect(() => () => manager.destroy(), [manager]);

  useEffect(() => {
    if (!enabled) {
      if (map.hasLayer(layer)) map.removeLayer(layer);
      manager.destroy();
      controller.incrementEnabledEpoch();
      return;
    }
    controller.incrementEnabledEpoch();
    ensureRadarPane(map);
    if (!map.hasLayer(layer)) layer.addTo(map);
    layer.scheduleRefresh();
  }, [controller, enabled, layer, manager, map, radarRefreshToken]);

  useEffect(() => {
    const refresh = () => {
      if (enabled) layer.scheduleRefresh();
    };
    map.on('moveend zoomend', refresh);
    return () => {
      map.off('moveend zoomend', refresh);
      if (map.hasLayer(layer)) map.removeLayer(layer);
      manager.destroy();
    };
  }, [enabled, layer, manager, map]);

  return null;
}

function ensureRadarPane(map: L.Map): void {
  if (map.getPane('weather-radar')) return;
  const pane = map.createPane('weather-radar');
  pane.style.zIndex = '200';
}

const { managers: radarTestManagers, layers: radarTestLayers } =
  radarGridLayerTestInternals;
