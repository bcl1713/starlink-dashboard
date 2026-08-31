import L from 'leaflet';

import {
  OPERATIONAL_LAYERS,
  RADAR_ATTRIBUTION,
} from './operational-map-contract';
import {
  type RadarTileCoord,
  type createRadarTileManager,
} from './radar-tile-manager';
import { tileKey } from './radar-tile-utils';

type Done = (error?: Error | null, tile?: HTMLElement) => void;

export interface RadarLayer extends L.GridLayer {
  visibleTiles: Map<string, RadarTileCoord>;
  refreshVisible(): void;
  scheduleRefresh(): void;
}

export function createRadarLayer(
  manager: ReturnType<typeof createRadarTileManager>,
  currentToken: () => number
): RadarLayer {
  const radar = OPERATIONAL_LAYERS[0];
  const RadarLayerClass = L.GridLayer.extend({
    createTile(coords: L.Coords, done: Done) {
      const coord = { z: coords.z, x: coords.x, y: coords.y };
      const key = tileKey(coord);
      const image = document.createElement('img');
      image.alt = '';
      this.visibleTiles.set(key, coord);
      manager.registerTile(coord, image, done);
      this.scheduleRefresh();
      return image;
    },
    refreshVisible() {
      void manager.loadVisibleTiles({
        token: currentToken(),
        tiles: [...this.visibleTiles.values()],
      });
    },
    scheduleRefresh() {
      if (this.refreshScheduled) return;
      this.refreshScheduled = true;
      queueMicrotask(() => {
        this.refreshScheduled = false;
        this.refreshVisible();
      });
    },
  });
  const LayerCtor = RadarLayerClass as unknown as new (
    options: L.GridLayerOptions
  ) => RadarLayer;
  const layer = new LayerCtor({
    attribution: RADAR_ATTRIBUTION,
    keepBuffer: 0,
    maxZoom: radar.maxZoom,
    minZoom: radar.minZoom,
    opacity: radar.opacity,
    pane: 'weather-radar',
    updateWhenIdle: true,
  });
  layer.visibleTiles = new Map<string, RadarTileCoord>();
  (layer as RadarLayer & { refreshScheduled: boolean }).refreshScheduled =
    false;
  layer.on('tileunload', (event: L.TileEvent) => {
    const coords = event.coords;
    if (!coords) return;
    const coord = { z: coords.z, x: coords.x, y: coords.y };
    layer.visibleTiles.delete(tileKey(coord));
    manager.unloadTile(coord);
    layer.scheduleRefresh();
  });
  return layer;
}
