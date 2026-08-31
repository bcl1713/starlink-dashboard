import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createAttachedHarness,
  finishChanged,
  flush,
  lastLoad,
  trackUrls,
  waitFor,
  waitForSrc,
} from './radar-grid-layer-test-harness';

beforeEach(() => {
  Object.defineProperty(HTMLImageElement.prototype, 'decode', {
    configurable: true,
    value: vi.fn(() => Promise.resolve()),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('RadarGridLayer real attachment', () => {
  it('reconciles manual createTile and tileunload calls on an attached layer with map refreshes, disable, retry, and wrapped token zero', async () => {
    const harness = createAttachedHarness();
    const loadVisible = vi.spyOn(harness.manager, 'loadVisibleTiles');
    harness.reset();
    loadVisible.mockClear();
    const done = vi.fn();
    const tiles = Array.from({ length: 3 }, (_, x) =>
      harness.create({ z: 2, x, y: 1 }, done)
    );

    await flush();
    expect(loadVisible).toHaveBeenCalledTimes(1);
    expect(harness.loadTile).toHaveBeenCalledTimes(3);
    await harness.finishAll(tiles);
    await lastLoad(loadVisible);
    expect(harness.report).toHaveBeenCalledExactlyOnceWith(10, {
      ok: true,
      frameTimestamp: '100',
    });

    harness.map.fire('moveend');
    harness.layer.scheduleRefresh();
    await flush();
    expect(loadVisible).toHaveBeenCalledTimes(1);
    harness.map.fire('zoomend');
    harness.layer.scheduleRefresh();
    await flush();
    expect(loadVisible).toHaveBeenCalledTimes(1);
    const afterInitial = [tiles[0].src, tiles[2].src];
    harness.layer.fire('tileunload', { coords: { z: 2, x: 1, y: 1 } });
    await flush();
    expect(loadVisible).toHaveBeenCalledTimes(2);
    await finishChanged([tiles[0], tiles[2]], afterInitial);
    await flush();
    harness.manager.destroy();
    harness.map.removeLayer(harness.layer);
    expect(harness.manager.stats()).toEqual({
      inFlight: 0,
      tracked: 0,
      objectUrls: 0,
    });

    harness.token = Number.MAX_SAFE_INTEGER;
    harness.layer.addTo(harness.map);
    const retryTiles = [
      harness.create({ z: 2, x: 0, y: 1 }, vi.fn()),
      harness.create({ z: 2, x: 2, y: 1 }, vi.fn()),
    ];
    await flush();
    await harness.finishAll(retryTiles);
    await flush();
    expect(harness.loadTile).toHaveBeenCalledTimes(10);
    harness.token = 0;
    const afterMaxToken = retryTiles.map((tile) => tile.src);
    harness.layer.scheduleRefresh();
    await flush();
    await finishChanged(retryTiles, afterMaxToken);
    await flush();
    expect(harness.loadTile).toHaveBeenCalledTimes(15);
    harness.destroy();
  });

  it('holds service concurrency at eight and reports a partial batch failure once', async () => {
    const harness = createAttachedHarness({ deferred: true });
    const loadVisible = vi.spyOn(harness.manager, 'loadVisibleTiles');
    harness.reset();
    loadVisible.mockClear();
    const tiles = Array.from({ length: 16 }, (_, x) =>
      harness.create({ z: 3, x, y: 0 }, vi.fn())
    );

    await flush();
    expect(harness.maxActive).toBe(8);
    expect(harness.maxActive).toBeLessThanOrEqual(8);
    harness.resolveBatch(0, 8);
    for (const image of tiles.slice(0, 8)) {
      await waitForSrc(image, 'blob:');
      image.dispatchEvent(new Event('load'));
    }
    await flush();
    await waitFor(() => harness.gateCount >= 16);
    expect(harness.maxActive).toBe(8);
    harness.resolveBatch(8, 16, 12);
    await harness.finishAll(tiles.filter((_, index) => index !== 12));
    await lastLoad(loadVisible);

    expect(harness.report).toHaveBeenCalledExactlyOnceWith(10, {
      ok: false,
      error: expect.any(Error),
    });
    harness.destroy();
  });

  it('rejects decode failures, restores target image errors, and ignores superseded candidates', async () => {
    const urls = trackUrls();
    const harness = createAttachedHarness();
    const loadVisible = vi.spyOn(harness.manager, 'loadVisibleTiles');
    harness.reset();
    loadVisible.mockClear();
    const image = harness.create({ z: 4, x: 0, y: 0 }, vi.fn());
    await flush();
    await waitForSrc(image, 'blob:1');
    image.dispatchEvent(new Event('load'));
    await lastLoad(loadVisible);
    expect(image.src).toContain('blob:1');

    harness.token = 11;
    harness.layer.scheduleRefresh();
    await flush();
    await waitForSrc(image, 'blob:2');
    image.dispatchEvent(new Event('error'));
    await lastLoad(loadVisible);
    expect(image.src).toContain('blob:1');
    expect(urls.active.has('blob:2')).toBe(false);
    expect(harness.report).toHaveBeenLastCalledWith(11, {
      ok: false,
      error: expect.any(Error),
    });

    vi.mocked(HTMLImageElement.prototype.decode).mockRejectedValueOnce(
      new Error('decode failed')
    );
    harness.token = 12;
    harness.layer.scheduleRefresh();
    await flush();
    await lastLoad(loadVisible);
    expect(harness.report).toHaveBeenLastCalledWith(12, {
      ok: false,
      error: expect.any(Error),
    });

    harness.token = 13;
    harness.layer.scheduleRefresh();
    await flush();
    await waitForSrc(image, 'blob:4');
    harness.token = 14;
    harness.layer.scheduleRefresh();
    await flush();
    image.dispatchEvent(new Event('load'));
    await waitForSrc(image, 'blob:5');
    image.dispatchEvent(new Event('load'));
    await lastLoad(loadVisible);
    expect(image.src).toContain('blob:5');
    expect(urls.active.has('blob:4')).toBe(false);
    harness.destroy();
  });
});
