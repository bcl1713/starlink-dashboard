import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';

import { getRainViewerRadarTile } from '../../../services/monitoring';
import type { OverviewDataController } from '../overview-data-types';
import { createRadarLayer } from './radar-grid-layer-factory';
import { radarGridLayerTestInternals } from './radar-grid-layer-test-internals';
import { createRadarTileManager } from './radar-tile-manager';

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
  const token = useRef(radarRefreshToken);
  const enabledEpoch = useRef(0);
  useEffect(() => {
    token.current = radarRefreshToken;
  }, [radarRefreshToken]);
  const manager = useMemo(
    () =>
      createRadarTileManager({
        loadTile: getRainViewerRadarTile,
        reportRadarResult,
      }),
    [reportRadarResult]
  );
  /* eslint-disable react-hooks/refs */
  const layer = useMemo(
    () =>
      createRadarLayer(manager, {
        token: () => token.current,
        enabledEpoch: () => enabledEpoch.current,
      }),
    [manager]
  );
  /* eslint-enable react-hooks/refs */

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
      enabledEpoch.current += 1;
      return;
    }
    enabledEpoch.current += 1;
    ensureRadarPane(map);
    if (!map.hasLayer(layer)) layer.addTo(map);
    layer.scheduleRefresh();
  }, [enabled, layer, manager, map, radarRefreshToken]);

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
