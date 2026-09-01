import L from 'leaflet';
import { expect, vi } from 'vitest';

import { createRadarLayer } from './radar-grid-layer-factory';
import { createRadarTileManager } from './radar-tile-manager';
import type { RadarTileCoord } from './radar-tile-types';

const png = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer;

export function createAttachedHarness(options: { deferred?: boolean } = {}) {
  const container = document.createElement('div');
  container.style.width = '512px';
  container.style.height = '512px';
  document.body.append(container);
  const map = L.map(container).setView([0, 0], 2);
  map.createPane('weather-radar');
  let token = 10;
  let nextUrl = 0;
  let active = 0;
  let maxActive = 0;
  const gates: Gate[] = [];
  const loadTile = vi.fn(() => {
    active += 1;
    maxActive = Math.max(maxActive, active);
    if (!options.deferred) {
      active -= 1;
      return Promise.resolve({ bytes: png.slice(0), frameTimestamp: '100' });
    }
    return new Promise<{ bytes: ArrayBuffer; frameTimestamp: string }>(
      (resolve, reject) => {
        gates.push({
          resolve: (value) => {
            active -= 1;
            resolve(value);
          },
          reject: (error) => {
            active -= 1;
            reject(error);
          },
        });
      }
    );
  });
  const report = vi.fn();
  const manager = createRadarTileManager({
    loadTile,
    reportRadarResult: report,
    createObjectUrl: vi.fn(() => `blob:${(nextUrl += 1)}`),
    revokeObjectUrl: vi.fn(),
  });
  const layer = createRadarLayer(manager, {
    token: () => token,
    enabledEpoch: () => 1,
  });
  layer.addTo(map);
  return {
    get gateCount() {
      return gates.length;
    },
    get maxActive() {
      return maxActive;
    },
    get token() {
      return token;
    },
    set token(next: number) {
      token = next;
    },
    layer,
    loadTile,
    manager,
    map,
    report,
    reset() {
      manager.destroy();
      layer.visibleTiles.clear();
      loadTile.mockClear();
      report.mockClear();
      nextUrl = 0;
      active = 0;
      maxActive = 0;
      gates.length = 0;
    },
    create(coord: RadarTileCoord, done: () => void) {
      return (
        layer as typeof layer & {
          createTile(coords: L.Coords, done: () => void): HTMLElement;
        }
      ).createTile(coord as L.Coords, done) as HTMLImageElement;
    },
    async finishAll(images: readonly HTMLImageElement[]) {
      for (const image of images) {
        await waitForSrc(image, 'blob:');
        image.dispatchEvent(new Event('load'));
      }
      await flush();
    },
    resolveBatch(from: number, to: number, rejectIndex?: number) {
      for (let index = from; index < to; index += 1) {
        if (index === rejectIndex)
          gates[index]?.reject(new Error('partial failed'));
        else {
          gates[index]?.resolve({
            bytes: png.slice(0),
            frameTimestamp: String(index),
          });
        }
      }
    },
    destroy() {
      manager.destroy();
      map.remove();
      container.remove();
    },
  };
}

interface Gate {
  readonly resolve: (value: {
    bytes: ArrayBuffer;
    frameTimestamp: string;
  }) => void;
  readonly reject: (error: Error) => void;
}

export function trackUrls() {
  let next = 0;
  const active = new Set<string>();
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => {
    const url = `blob:${(next += 1)}`;
    active.add(url);
    return url;
  });
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation((url) => {
    active.delete(url);
  });
  return { active };
}

export async function flush(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

export async function lastLoad(spy: {
  readonly mock: {
    readonly results: readonly {
      readonly type: string;
      readonly value: unknown;
    }[];
  };
}) {
  const result = spy.mock.results.at(-1);
  const value = result?.type === 'return' ? result.value : null;
  if (value && typeof (value as PromiseLike<void>).then === 'function') {
    await value;
  }
}

export async function waitForSrc(image: HTMLImageElement, expected: string) {
  for (let count = 0; count < 20; count += 1) {
    await flush();
    if (image.src.includes(expected)) return;
  }
  expect(image.src).toContain(expected);
}

export async function finishChanged(
  images: readonly HTMLImageElement[],
  oldSources: readonly string[]
) {
  await Promise.all(
    images.map((image, index) =>
      waitFor(
        () => image.src !== oldSources[index] && image.src.includes('blob:')
      )
    )
  );
  for (const image of images) image.dispatchEvent(new Event('load'));
  await flush();
}

export async function waitFor(ready: () => boolean) {
  for (let count = 0; count < 20; count += 1) {
    await flush();
    if (ready()) return;
  }
  expect(ready()).toBe(true);
}
