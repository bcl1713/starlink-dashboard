import { createRadarLayer } from './radar-grid-layer-factory';
import { createRadarTileManager } from './radar-tile-manager';

const radarTestManagers = new Set<ReturnType<typeof createRadarTileManager>>();
const radarTestLayers = new Set<ReturnType<typeof createRadarLayer>>();

export const radarGridLayerTestInternals = Object.freeze({
  enabled: import.meta.env.MODE === 'test',
  managers: radarTestManagers,
  layers: radarTestLayers,
  reset() {
    radarTestManagers.clear();
    radarTestLayers.clear();
  },
});
