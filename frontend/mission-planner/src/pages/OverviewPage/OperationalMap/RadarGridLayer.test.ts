import { describe, expect, it, vi } from 'vitest';
import type { Coords } from 'leaflet';

import { createRadarLayer } from './radar-grid-layer-factory';

type Done = (error?: Error | null, tile?: HTMLElement) => void;

describe('RadarGridLayer', () => {
  it('creates a real Leaflet GridLayer tile image with frozen options', () => {
    const manager = {
      loadVisibleTiles: vi.fn(),
      registerTile: vi.fn(),
      unloadTile: vi.fn(),
      destroy: vi.fn(),
      stats: vi.fn(),
    };
    const layer = createRadarLayer(manager, () => 0);
    const done = vi.fn();

    const tile = (
      layer as unknown as {
        createTile(coords: Coords, done: Done): HTMLElement;
      }
    ).createTile({ x: 2, y: 3, z: 4 } as Coords, done);

    expect(tile).toBeInstanceOf(HTMLImageElement);
    expect(manager.registerTile).toHaveBeenCalledExactlyOnceWith(
      { z: 4, x: 2, y: 3 },
      tile,
      done
    );
    expect(manager.loadVisibleTiles).toHaveBeenCalledWith({
      token: 0,
      tiles: [{ z: 4, x: 2, y: 3 }],
    });
    expect(layer.options).toMatchObject({
      attribution: 'Weather radar © Rain Viewer / MeteoLab Inc.',
      keepBuffer: 0,
      maxZoom: 7,
      minZoom: 0,
      opacity: 0.7,
      pane: 'weather-radar',
      updateWhenIdle: true,
    });
  });
});
