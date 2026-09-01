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

type Done = (error?: Error, tile?: HTMLElement) => void;

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
  class RadarLayerClass extends L.GridLayer implements RadarLayer {
    visibleTiles = new Map<string, RadarTileCoord>();
    private refreshScheduled = false;
    private lastRefreshKey: string | null = null;

    createTile(coords: L.Coords, done: Done): HTMLElement {
      const coord = { z: coords.z, x: coords.x, y: coords.y };
      const key = tileKey(coord);
      const image = document.createElement('img');
      image.alt = '';
      this.visibleTiles.set(key, coord);
      manager.registerTile(coord, image, done);
      this.scheduleRefresh();
      return image;
    }

    refreshVisible(): void {
      const tiles = [...this.visibleTiles.values()];
      const visibleKey = tiles.map(tileKey).sort().join(',');
      const token = state.token();
      const key = `${token}:${state.enabledEpoch()}:${visibleKey}`;
      if (this.lastRefreshKey === key) return;
      this.lastRefreshKey = key;
      void manager.loadVisibleTiles({ token, tiles });
    }

    scheduleRefresh(): void {
      if (this.refreshScheduled) return;
      this.refreshScheduled = true;
      queueMicrotask(() => {
        this.refreshScheduled = false;
        this.refreshVisible();
      });
    }
  }
  const layer = new RadarLayerClass({
    attribution: RADAR_ATTRIBUTION,
    keepBuffer: 0,
    maxZoom: radar.maxZoom,
    minZoom: radar.minZoom,
    opacity: radar.opacity,
    pane: 'weather-radar',
    updateWhenIdle: true,
  });
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
