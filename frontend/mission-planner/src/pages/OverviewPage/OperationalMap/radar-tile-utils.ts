import type { RadarTileCoord } from './radar-tile-types';
import type { RecordState } from './radar-tile-types';

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === 'AbortError'
    : error instanceof Error && error.name === 'AbortError';
}

export function once(
  done: (error?: Error | null, tile?: HTMLElement) => void
): (error?: Error | null, tile?: HTMLElement) => void {
  let called = false;
  return (error, tile) => {
    if (called) return;
    called = true;
    done(error, tile);
  };
}

export async function decodeUrl(url: string): Promise<void> {
  const image = new Image();
  image.src = url;
  if ('decode' in image && typeof image.decode === 'function') {
    await image.decode();
  }
}

export function dedupe(tiles: readonly RadarTileCoord[]): RadarTileCoord[] {
  const byKey = new Map<string, RadarTileCoord>();
  for (const tile of tiles) byKey.set(tileKey(tile), tile);
  return [...byKey.values()];
}

export function tileKey({ z, x, y }: RadarTileCoord): string {
  return `${z}/${x}/${y}`;
}

export function radarStats(records: ReadonlyMap<string, RecordState>) {
  return {
    inFlight: [...records.values()].filter((record) => !record.settled).length,
    tracked: records.size,
  };
}
