import { useEffect, useMemo } from 'react';
import { useMap } from 'react-leaflet';

import { getRainViewerRadarTile } from '../../../services/monitoring';
import type { OverviewDataController } from '../overview-data-types';
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
  const manager = useMemo(
    () =>
      createRadarTileManager({
        loadTile: getRainViewerRadarTile,
        reportRadarResult,
      }),
    [reportRadarResult]
  );

  useEffect(() => () => manager.destroy(), [manager]);

  useEffect(() => {
    if (!enabled) {
      manager.destroy();
      return;
    }
    const center = map.getCenter();
    const zoom = Math.max(0, Math.min(7, Math.floor(map.getZoom())));
    const scale = 2 ** zoom;
    const x = Math.max(
      0,
      Math.min(scale - 1, Math.floor(((center.lng + 180) / 360) * scale))
    );
    const y = Math.max(
      0,
      Math.min(scale - 1, Math.floor(((90 - center.lat) / 180) * scale))
    );
    void manager.loadVisibleTiles({
      token: radarRefreshToken,
      tiles: [{ z: zoom, x, y }],
    });
  }, [enabled, manager, map, radarRefreshToken]);

  return null;
}
