import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createRadarTileManager } from './radar-tile-manager';

const png = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer;

beforeEach(() => {
  Object.defineProperty(HTMLImageElement.prototype, 'decode', {
    configurable: true,
    value: vi.fn(() => Promise.resolve()),
  });
});

describe('radar visible target load lifecycle', () => {
  it('keeps generation pending until the registered visible target image loads', async () => {
    const report = vi.fn();
    const image = document.createElement('img');
    const manager = createRadarTileManager({
      loadTile: vi.fn(() =>
        Promise.resolve({ bytes: png.slice(0), frameTimestamp: '500' })
      ),
      reportRadarResult: report,
      createObjectUrl: vi.fn(() => 'blob:visible'),
      revokeObjectUrl: vi.fn(),
    });
    const coord = { z: 2, x: 3, y: 4 };
    manager.registerTile(coord, image, vi.fn());

    const pending = manager.loadVisibleTiles({ token: 5, tiles: [coord] });
    await waitForSrc(image, 'blob:visible');

    expect(report).not.toHaveBeenCalled();
    image.dispatchEvent(new Event('load'));
    await pending;

    expect(report).toHaveBeenCalledExactlyOnceWith(5, {
      ok: true,
      frameTimestamp: '500',
    });
  });

  it('revokes a failed visible candidate and restores the retained target URL', async () => {
    const report = vi.fn();
    const done = vi.fn();
    const image = document.createElement('img');
    const revokeObjectUrl = vi.fn();
    let url = 0;
    const manager = createRadarTileManager({
      loadTile: vi.fn(() =>
        Promise.resolve({ bytes: png.slice(0), frameTimestamp: '501' })
      ),
      reportRadarResult: report,
      createObjectUrl: vi.fn(() => `blob:${(url += 1)}`),
      revokeObjectUrl,
    });
    const coord = { z: 3, x: 4, y: 5 };
    manager.registerTile(coord, image, done);
    const first = manager.loadVisibleTiles({ token: 1, tiles: [coord] });
    await waitForSrc(image, 'blob:1');
    image.dispatchEvent(new Event('load'));
    await first;
    const failureDone = vi.fn();
    manager.registerTile(coord, image, failureDone);

    const second = manager.loadVisibleTiles({ token: 2, tiles: [coord] });
    await waitForSrc(image, 'blob:2');
    image.dispatchEvent(new Event('error'));
    await second;

    expect(image.src).toContain('blob:1');
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:2');
    expect(revokeObjectUrl).not.toHaveBeenCalledWith('blob:1');
    expect(done).toHaveBeenCalledExactlyOnceWith(undefined, image);
    expect(failureDone).toHaveBeenCalledExactlyOnceWith(expect.any(Error));
    expect(report).toHaveBeenLastCalledWith(2, {
      ok: false,
      error: expect.any(Error),
    });
  });
});

async function waitForSrc(
  image: HTMLImageElement,
  expected: string
): Promise<void> {
  for (let count = 0; count < 10; count += 1) {
    await Promise.resolve();
    await Promise.resolve();
    if (image.src.includes(expected)) return;
  }
  expect(image.src).toContain(expected);
}
