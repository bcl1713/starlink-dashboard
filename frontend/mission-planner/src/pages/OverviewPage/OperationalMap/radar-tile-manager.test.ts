import { describe, expect, it, vi } from 'vitest';

import { createRadarTileManager } from './radar-tile-manager';

const png = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer;

describe('radar tile manager', () => {
  it('captures the visible generation token and reports the oldest frame once', async () => {
    const report = vi.fn();
    const manager = createRadarTileManager({
      loadTile: vi.fn(({ x }) =>
        Promise.resolve({
          bytes: png.slice(0),
          frameTimestamp: String(200 - x),
        })
      ),
      reportRadarResult: report,
      createObjectUrl: vi.fn(() => 'blob:tile'),
      revokeObjectUrl: vi.fn(),
    });

    await manager.loadVisibleTiles({
      token: Number.MAX_SAFE_INTEGER,
      tiles: [
        { z: 1, x: 0, y: 0 },
        { z: 1, x: 1, y: 0 },
      ],
    });

    expect(report).toHaveBeenCalledExactlyOnceWith(Number.MAX_SAFE_INTEGER, {
      ok: true,
      frameTimestamp: '199',
    });
  });

  it('coalesces duplicate tiles, cancels obsolete generations, and revokes URLs', async () => {
    const revokeObjectUrl = vi.fn();
    const report = vi.fn();
    const gates: ((value: {
      bytes: ArrayBuffer;
      frameTimestamp: string;
    }) => void)[] = [];
    const manager = createRadarTileManager({
      loadTile: vi.fn(
        ({
          signal,
        }): Promise<{ bytes: ArrayBuffer; frameTimestamp: string }> => {
          expect(signal.aborted).toBe(false);
          return new Promise((resolve) => gates.push(resolve));
        }
      ),
      reportRadarResult: report,
      createObjectUrl: vi.fn(() => `blob:${gates.length}`),
      revokeObjectUrl,
    });

    const first = manager.loadVisibleTiles({
      token: 1,
      tiles: [
        { z: 1, x: 0, y: 0 },
        { z: 1, x: 0, y: 0 },
      ],
    });
    expect(manager.stats()).toMatchObject({ inFlight: 1, tracked: 1 });
    const second = manager.loadVisibleTiles({
      token: 2,
      tiles: [{ z: 1, x: 1, y: 0 }],
    });
    gates[0]({ bytes: png.slice(0), frameTimestamp: '201' });
    gates[1]({ bytes: png.slice(0), frameTimestamp: '202' });
    await Promise.all([first, second]);

    expect(report).toHaveBeenCalledExactlyOnceWith(2, {
      ok: true,
      frameTimestamp: '202',
    });
    manager.destroy();
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:2');
    expect(manager.stats()).toEqual({ inFlight: 0, tracked: 0, objectUrls: 0 });
  });

  it('reports a visible generation failure once and rejects unbounded tracking', async () => {
    const report = vi.fn();
    const manager = createRadarTileManager({
      loadTile: vi.fn(() => Promise.reject(new Error('network failed'))),
      reportRadarResult: report,
      createObjectUrl: vi.fn(() => 'blob:unused'),
      revokeObjectUrl: vi.fn(),
    });

    await manager.loadVisibleTiles({ token: 3, tiles: [{ z: 1, x: 0, y: 0 }] });
    expect(report).toHaveBeenCalledExactlyOnceWith(3, {
      ok: false,
      error: expect.any(Error),
    });
    report.mockClear();
    await manager.loadVisibleTiles({
      token: 4,
      tiles: Array.from({ length: 97 }, (_, x) => ({ z: 7, x, y: 0 })),
    });
    expect(report).toHaveBeenCalledExactlyOnceWith(4, {
      ok: false,
      error: expect.any(Error),
    });
  });

  it('makes a fresh same-key request for a wrapped retry token', async () => {
    const loadTile = vi.fn(({ x }) =>
      Promise.resolve({
        bytes: png.slice(0),
        frameTimestamp: String(300 + x),
      })
    );
    const manager = createRadarTileManager({
      loadTile,
      reportRadarResult: vi.fn(),
      createObjectUrl: vi.fn(() => `blob:${loadTile.mock.calls.length}`),
      revokeObjectUrl: vi.fn(),
    });

    await manager.loadVisibleTiles({
      token: Number.MAX_SAFE_INTEGER,
      tiles: [{ z: 1, x: 0, y: 0 }],
    });
    await manager.loadVisibleTiles({
      token: 0,
      tiles: [{ z: 1, x: 0, y: 0 }],
    });

    expect(loadTile).toHaveBeenCalledTimes(2);
  });
});
