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
  readonly controller: AbortController;
  readonly promise: Promise<RainViewerRadarTile>;
  objectUrl: string | null;
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

  function requestRecord(coord: RadarTileCoord): Promise<RainViewerRadarTile> {
    const key = tileKey(coord);
    const existing = records.get(key);
    if (existing) return existing.promise;
    const controller = new AbortController();
    const promise = options
      .loadTile({ ...coord, signal: controller.signal })
      .then((tile) => {
        replaceUrl(key, tile.bytes);
        return tile;
      });
    records.set(key, { key, controller, promise, objectUrl: null });
    return promise;
  }

  function replaceUrl(key: string, bytes: ArrayBuffer): void {
    const record = records.get(key);
    if (!record) return;
    if (record.objectUrl) revoke(record.objectUrl);
    const url = createObjectUrl(new Blob([bytes], { type: 'image/png' }));
    record.objectUrl = url;
    objectUrls.add(url);
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
    destroy,
    stats: () => ({
      inFlight: records.size,
      tracked: records.size,
      objectUrls: objectUrls.size,
    }),
  };
}

function dedupe(tiles: readonly RadarTileCoord[]): RadarTileCoord[] {
  const byKey = new Map<string, RadarTileCoord>();
  for (const tile of tiles) byKey.set(tileKey(tile), tile);
  return [...byKey.values()];
}

export function tileKey({ z, x, y }: RadarTileCoord): string {
  return `${z}/${x}/${y}`;
}
