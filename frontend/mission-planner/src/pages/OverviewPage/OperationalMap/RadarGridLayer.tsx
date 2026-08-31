import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';

import { getRainViewerRadarTile } from '../../../services/monitoring';
import type { OverviewDataController } from '../overview-data-types';
import { createRadarLayer } from './radar-grid-layer-factory';
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
  const layer = useMemo(
    // The GridLayer identity is stable; its tile callbacks read the latest token.
    // eslint-disable-next-line react-hooks/refs
    () => createRadarLayer(manager, () => token.current),
    [manager]
  );

  useEffect(() => () => manager.destroy(), [manager]);

  useEffect(() => {
    if (!enabled) {
      if (map.hasLayer(layer)) map.removeLayer(layer);
      manager.destroy();
      return;
    }
    ensureRadarPane(map);
    if (!map.hasLayer(layer)) layer.addTo(map);
    layer.refreshVisible();
  }, [enabled, layer, manager, map, radarRefreshToken]);

  useEffect(() => {
    const refresh = () => {
      if (enabled) layer.refreshVisible();
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
