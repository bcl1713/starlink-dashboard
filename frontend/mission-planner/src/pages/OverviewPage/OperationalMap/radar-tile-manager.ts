import type { RainViewerRadarTile } from '../../../types/monitoring';
import type {
  RadarTileCoord,
  RadarTileManagerOptions,
  RecordState,
} from './radar-tile-types';
import {
  decodeUrl,
  dedupe,
  isAbortError,
  once,
  radarStats,
  tileKey,
} from './radar-tile-utils';

export type { RadarTileCoord } from './radar-tile-types';

const MAX_IN_FLIGHT = 8,
  MAX_TRACKED = 96;

export function createRadarTileManager(options: RadarTileManagerOptions) {
  let generationId = 0;
  let requestId = 0;
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
    generationId += 1;
    const currentGeneration = generationId;
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
      if (currentGeneration !== generationId) return;
      const batch = unique.slice(index, index + MAX_IN_FLIGHT);
      const settled = await Promise.allSettled(
        batch.map((coord) => requestRecord(coord))
      );
      for (const result of settled) {
        if (result.status === 'fulfilled') {
          if (result.value) outcomes.push(result.value);
        } else failures.push(result.reason);
      }
    }
    if (currentGeneration !== generationId) return;
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
      record.cleanupImage?.();
      record.image = image;
      record.done = once(done);
      record.cleanupImage = bindImage(record);
      if (record.objectUrl) image.src = record.objectUrl;
    } else {
      const nextRequestId = requestId + 1;
      const next: RecordState = {
        key,
        generationId,
        requestId: nextRequestId,
        controller: new AbortController(),
        promise: Promise.resolve({
          bytes: new ArrayBuffer(0),
          frameTimestamp: '',
        }),
        objectUrl: null,
        candidateUrl: null,
        image,
        done: once(done),
        settled: true,
        cleanupImage: null,
      };
      next.cleanupImage = bindImage(next);
      records.set(key, {
        ...next,
      });
    }
  }

  function unloadTile(coord: RadarTileCoord): void {
    const key = tileKey(coord);
    const record = records.get(key);
    if (!record) return;
    record.controller.abort();
    disposeRecord(record);
    records.delete(key);
  }

  function requestRecord(
    coord: RadarTileCoord
  ): Promise<RainViewerRadarTile | null> {
    const key = tileKey(coord);
    const currentGeneration = generationId;
    const existing = records.get(key);
    if (
      existing &&
      existing.generationId === currentGeneration &&
      !existing.settled
    )
      return existing.promise;
    const controller = new AbortController();
    if (existing?.generationId !== currentGeneration)
      existing?.controller.abort();
    const currentRequest = requestId + 1;
    requestId = currentRequest;
    let loaded: Promise<RainViewerRadarTile>;
    try {
      loaded = options.loadTile({ ...coord, signal: controller.signal });
    } catch (error) {
      loaded = Promise.reject(error);
    }
    const promise: Promise<RainViewerRadarTile | null> = loaded
      .then(async (tile) => {
        await replaceUrl(key, currentRequest, tile.bytes);
        const record = findRecord(key, currentRequest);
        if (record) {
          record.settled = true;
        }
        return tile;
      })
      .catch((error: unknown) => {
        const record = findRecord(key, currentRequest);
        if (!record || isAbortError(error) || controller.signal.aborted) {
          return null;
        }
        if (record) {
          record.settled = true;
          record.done?.(
            error instanceof Error ? error : new Error('Radar tile failed.')
          );
        }
        throw error;
      });
    existing?.cleanupImage?.();
    const nextRecord: RecordState = {
      key,
      generationId: currentGeneration,
      requestId: currentRequest,
      controller,
      promise,
      objectUrl: existing?.objectUrl ?? null,
      candidateUrl: null,
      image: existing?.image ?? null,
      done: existing?.done ?? null,
      settled: false,
      cleanupImage: null,
    };
    nextRecord.cleanupImage = bindImage(nextRecord);
    records.set(key, nextRecord);
    return promise;
  }

  async function replaceUrl(
    key: string,
    currentRequest: number,
    bytes: ArrayBuffer
  ): Promise<void> {
    const url = createObjectUrl(new Blob([bytes], { type: 'image/png' }));
    objectUrls.add(url);
    const record = findRecord(key, currentRequest);
    if (!record) {
      revoke(url);
      return;
    }
    try {
      await decodeUrl(url);
    } catch (error) {
      revoke(url);
      throw error;
    }
    const current = findRecord(key, currentRequest);
    if (!current) {
      revoke(url);
      return;
    }
    if (current.candidateUrl) revoke(current.candidateUrl);
    current.candidateUrl = url;
    if (current.image) current.image.src = url;
  }

  function cancelExcept(visible: ReadonlySet<string>): void {
    for (const [key, record] of records) {
      if (!visible.has(key)) {
        record.controller.abort();
        disposeRecord(record);
        records.delete(key);
      }
    }
  }

  function destroy(): void {
    generationId += 1;
    for (const record of records.values()) {
      record.controller.abort();
      disposeRecord(record);
    }
    records.clear();
  }

  function bindImage(record: RecordState): () => void {
    const image = record.image;
    if (!image) return () => undefined;
    const onLoad = () => {
      const current = findRecord(record.key, record.requestId);
      if (!current || current.image !== image || !current.candidateUrl) return;
      const old = current.objectUrl;
      current.objectUrl = current.candidateUrl;
      current.candidateUrl = null;
      if (old) revoke(old);
      current.done?.(null, image);
    };
    const onError = () => {
      const current = findRecord(record.key, record.requestId);
      if (!current || current.image !== image || !current.candidateUrl) return;
      revoke(current.candidateUrl);
      current.candidateUrl = null;
      current.done?.(new Error('Radar tile image failed.'));
    };
    image.addEventListener('load', onLoad);
    image.addEventListener('error', onError);
    return () => {
      image.removeEventListener('load', onLoad);
      image.removeEventListener('error', onError);
    };
  }

  function disposeRecord(record: RecordState): void {
    record.cleanupImage?.();
    record.cleanupImage = null;
    if (record.candidateUrl) revoke(record.candidateUrl);
    if (record.objectUrl) revoke(record.objectUrl);
    record.candidateUrl = null;
    record.objectUrl = null;
  }

  function findRecord(key: string, currentRequest: number): RecordState | null {
    const record = records.get(key);
    return record?.requestId === currentRequest ? record : null;
  }

  function revoke(url: string): void {
    if (objectUrls.delete(url)) revokeObjectUrl(url);
  }

  function reportOnce(
    currentGeneration: number,
    token: number,
    result: Parameters<RadarTileManagerOptions['reportRadarResult']>[1]
  ): void {
    if (currentGeneration === generationId)
      options.reportRadarResult(token, result);
  }

  return {
    loadVisibleTiles,
    registerTile,
    unloadTile,
    destroy,
    stats: () => ({
      ...radarStats(records),
      objectUrls: objectUrls.size,
    }),
  };
}
