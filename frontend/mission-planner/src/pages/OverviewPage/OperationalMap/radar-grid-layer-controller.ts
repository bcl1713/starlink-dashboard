import { getRainViewerRadarTile } from '../../../services/monitoring';
import type { OverviewDataController } from '../overview-data-types';
import { createRadarLayer, type RadarLayer } from './radar-grid-layer-factory';
import { createRadarTileManager } from './radar-tile-manager';

export interface RadarGridLayerController {
  readonly manager: ReturnType<typeof createRadarTileManager>;
  readonly layer: RadarLayer;
  setToken(token: number): void;
  incrementEnabledEpoch(): void;
}

export function createRadarGridLayerController({
  radarRefreshToken,
  reportRadarResult,
}: {
  readonly radarRefreshToken: number;
  readonly reportRadarResult: OverviewDataController['reportRadarResult'];
}): RadarGridLayerController {
  let token = radarRefreshToken;
  let enabledEpoch = 0;
  const manager = createRadarTileManager({
    loadTile: getRainViewerRadarTile,
    reportRadarResult,
  });
  const layer = createRadarLayer(manager, {
    token: () => token,
    enabledEpoch: () => enabledEpoch,
  });

  return {
    manager,
    layer,
    setToken(nextToken) {
      token = nextToken;
    },
    incrementEnabledEpoch() {
      enabledEpoch += 1;
    },
  };
}
