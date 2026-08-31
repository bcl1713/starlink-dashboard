import { describe, expect, it, vi } from 'vitest';
import type { Coords } from 'leaflet';

import { createRadarLayer } from './radar-grid-layer-factory';

type Done = (error?: Error | null, tile?: HTMLElement) => void;

describe('RadarGridLayer', () => {
  it('registers tile images synchronously and reconciles once after boundary', async () => {
    const manager = {
      loadVisibleTiles: vi.fn(),
      registerTile: vi.fn(),
      unloadTile: vi.fn(),
      destroy: vi.fn(),
      stats: vi.fn(),
    };
    const layer = createRadarLayer(manager, {
      token: () => 0,
      enabledEpoch: () => 0,
    });
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
    expect(manager.loadVisibleTiles).not.toHaveBeenCalled();
    await Promise.resolve();
    expect(manager.loadVisibleTiles).toHaveBeenCalledExactlyOnceWith({
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

  it('unloads tiles neutrally and schedules a reconciled generation', async () => {
    const manager = {
      loadVisibleTiles: vi.fn(),
      registerTile: vi.fn(),
      unloadTile: vi.fn(),
      destroy: vi.fn(),
      stats: vi.fn(),
    };
    const layer = createRadarLayer(manager, {
      token: () => 11,
      enabledEpoch: () => 0,
    });
    const api = layer as unknown as {
      createTile(coords: Coords, done: Done): HTMLElement;
    };

    api.createTile({ x: 0, y: 0, z: 1 } as Coords, vi.fn());
    api.createTile({ x: 1, y: 0, z: 1 } as Coords, vi.fn());
    layer.fire('tileunload', { coords: { x: 0, y: 0, z: 1 } });
    await Promise.resolve();

    expect(manager.unloadTile).toHaveBeenCalledExactlyOnceWith({
      z: 1,
      x: 0,
      y: 0,
    });
    expect(manager.loadVisibleTiles).toHaveBeenCalledExactlyOnceWith({
      token: 11,
      tiles: [{ z: 1, x: 1, y: 0 }],
    });
  });
});
