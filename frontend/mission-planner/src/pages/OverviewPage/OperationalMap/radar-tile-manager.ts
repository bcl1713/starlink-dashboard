import type { OverviewDataController } from '../overview-data-types';
import type { RainViewerRadarTile } from '../../../types/monitoring';

export interface RadarTileCoord {
  readonly z: number;
  readonly x: number;
  readonly y: number;
}

interface RadarTileManagerOptions {
  readonly loadTile: (
    coord: RadarTileCoord & { readonly signal: AbortSignal }
  ) => Promise<RainViewerRadarTile>;
  readonly reportRadarResult: OverviewDataController['reportRadarResult'];
  readonly createObjectUrl?: (blob: Blob) => string;
  readonly revokeObjectUrl?: (url: string) => void;
}

interface RecordState {
  readonly key: string;
  readonly generation: number;
  readonly controller: AbortController;
  readonly promise: Promise<RainViewerRadarTile>;
  readonly coord: RadarTileCoord;
  objectUrl: string | null;
  image: HTMLImageElement | null;
  done: ((error?: Error | null, tile?: HTMLElement) => void) | null;
  settled: boolean;
}

const MAX_IN_FLIGHT = 8;
const MAX_TRACKED = 96;

export function createRadarTileManager(options: RadarTileManagerOptions) {
  let generation = 0;
  const records = new Map<string, RecordState>();
  const objectUrls = new Set<string>();
  const createObjectUrl =
    options.createObjectUrl ??
    ((blob: Blob) => globalThis.URL.createObjectURL(blob));
  const revokeObjectUrl =
    options.revokeObjectUrl ??
    ((url: string) => globalThis.URL.revokeObjectURL(url));

  async function loadVisibleTiles({
    token,
    tiles,
  }: {
    readonly token: number;
    readonly tiles: readonly RadarTileCoord[];
  }): Promise<void> {
    generation += 1;
    const currentGeneration = generation;
    const unique = dedupe(tiles);
    cancelExcept(new Set(unique.map(tileKey)));
    if (unique.length > MAX_TRACKED) {
      reportOnce(currentGeneration, token, {
        ok: false,
        error: new Error('Too many radar tiles are visible.'),
      });
      return;
    }
    const outcomes: RainViewerRadarTile[] = [];
    const failures: unknown[] = [];
    for (let index = 0; index < unique.length; index += MAX_IN_FLIGHT) {
      if (currentGeneration !== generation) return;
      const batch = unique.slice(index, index + MAX_IN_FLIGHT);
      const settled = await Promise.allSettled(
        batch.map((coord) => requestRecord(coord))
      );
      for (const result of settled) {
        if (result.status === 'fulfilled') outcomes.push(result.value);
        else failures.push(result.reason);
      }
    }
    if (currentGeneration !== generation) return;
    if (failures.length > 0) {
      reportOnce(currentGeneration, token, { ok: false, error: failures[0] });
      return;
    }
    const frameTimestamp = outcomes
      .map((tile) => tile.frameTimestamp)
      .sort((left, right) => Number(left) - Number(right))[0];
    if (frameTimestamp) {
      reportOnce(currentGeneration, token, { ok: true, frameTimestamp });
    }
  }

  function registerTile(
    coord: RadarTileCoord,
    image: HTMLImageElement,
    done: (error?: Error | null, tile?: HTMLElement) => void
  ): void {
    const key = tileKey(coord);
    const record = records.get(key);
    if (record) {
      record.image = image;
      record.done = once(done);
      if (record.objectUrl) image.src = record.objectUrl;
    } else {
      records.set(key, {
        key,
        generation,
        coord,
        controller: new AbortController(),
        promise: Promise.resolve({
          bytes: new ArrayBuffer(0),
          frameTimestamp: '',
        }),
        objectUrl: null,
        image,
        done: once(done),
        settled: true,
      });
    }
  }

  function unloadTile(coord: RadarTileCoord): void {
    const key = tileKey(coord);
    const record = records.get(key);
    if (!record) return;
    record.controller.abort();
    if (record.objectUrl) revoke(record.objectUrl);
    records.delete(key);
  }

  function requestRecord(coord: RadarTileCoord): Promise<RainViewerRadarTile> {
    const key = tileKey(coord);
    const currentGeneration = generation;
    const existing = records.get(key);
    if (
      existing &&
      existing.generation === currentGeneration &&
      !existing.settled
    )
      return existing.promise;
    const controller = new AbortController();
    if (existing?.generation !== currentGeneration)
      existing?.controller.abort();
    let loaded: Promise<RainViewerRadarTile>;
    try {
      loaded = options.loadTile({ ...coord, signal: controller.signal });
    } catch (error) {
      loaded = Promise.reject(error);
    }
    const promise = loaded
      .then(async (tile) => {
        await replaceUrl(key, tile.bytes);
        const record = records.get(key);
        if (record) {
          record.settled = true;
          record.done?.(null, record.image ?? undefined);
        }
        return tile;
      })
      .catch((error: unknown) => {
        const record = records.get(key);
        if (record) {
          record.settled = true;
          record.done?.(
            error instanceof Error ? error : new Error('Radar tile failed.')
          );
        }
        throw error;
      });
    records.set(key, {
      key,
      generation: currentGeneration,
      coord,
      controller,
      promise,
      objectUrl: existing?.objectUrl ?? null,
      image: existing?.image ?? null,
      done: existing?.done ?? null,
      settled: false,
    });
    return promise;
  }

  async function replaceUrl(key: string, bytes: ArrayBuffer): Promise<void> {
    const record = records.get(key);
    if (!record) return;
    const url = createObjectUrl(new Blob([bytes], { type: 'image/png' }));
    objectUrls.add(url);
    try {
      await decodeUrl(url);
    } catch (error) {
      revoke(url);
      throw error;
    }
    const old = record.objectUrl;
    record.objectUrl = url;
    if (record.image) record.image.src = url;
    if (old) revoke(old);
  }

  function cancelExcept(visible: ReadonlySet<string>): void {
    for (const [key, record] of records) {
      if (!visible.has(key)) {
        record.controller.abort();
        if (record.objectUrl) revoke(record.objectUrl);
        records.delete(key);
      }
    }
  }

  function destroy(): void {
    generation += 1;
    for (const record of records.values()) {
      record.controller.abort();
      if (record.objectUrl) revoke(record.objectUrl);
    }
    records.clear();
  }

  function revoke(url: string): void {
    if (objectUrls.delete(url)) revokeObjectUrl(url);
  }

  function reportOnce(
    currentGeneration: number,
    token: number,
    result: Parameters<OverviewDataController['reportRadarResult']>[1]
  ): void {
    if (currentGeneration === generation)
      options.reportRadarResult(token, result);
  }

  return {
    loadVisibleTiles,
    registerTile,
    unloadTile,
    destroy,
    stats: () => ({
      inFlight: [...records.values()].filter((record) => !record.settled)
        .length,
      tracked: records.size,
      objectUrls: objectUrls.size,
    }),
  };
}

function once(
  done: (error?: Error | null, tile?: HTMLElement) => void
): (error?: Error | null, tile?: HTMLElement) => void {
  let called = false;
  return (error, tile) => {
    if (called) return;
    called = true;
    done(error, tile);
  };
}

async function decodeUrl(url: string): Promise<void> {
  const image = new Image();
  image.src = url;
  if ('decode' in image && typeof image.decode === 'function') {
    await image.decode();
  }
}

function dedupe(tiles: readonly RadarTileCoord[]): RadarTileCoord[] {
  const byKey = new Map<string, RadarTileCoord>();
  for (const tile of tiles) byKey.set(tileKey(tile), tile);
  return [...byKey.values()];
}

export function tileKey({ z, x, y }: RadarTileCoord): string {
  return `${z}/${x}/${y}`;
}
