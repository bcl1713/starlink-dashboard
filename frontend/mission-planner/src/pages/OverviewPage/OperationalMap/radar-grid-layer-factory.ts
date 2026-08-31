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

interface RadarLayerState {
  readonly token: () => number;
  readonly enabledEpoch: () => number;
}

export function createRadarLayer(
  manager: ReturnType<typeof createRadarTileManager>,
  state: RadarLayerState
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
      const tiles = [...this.visibleTiles.values()];
      const visibleKey = tiles.map(tileKey).sort().join(',');
      const token = state.token();
      const key = `${token}:${state.enabledEpoch()}:${visibleKey}`;
      if (this.lastRefreshKey === key) return;
      this.lastRefreshKey = key;
      void manager.loadVisibleTiles({ token, tiles });
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
  (layer as RadarLayer & { lastRefreshKey: string | null }).lastRefreshKey =
    null;
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
