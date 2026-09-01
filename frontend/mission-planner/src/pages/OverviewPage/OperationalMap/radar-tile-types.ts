import type { OverviewDataController } from '../overview-data-types';
import type { RainViewerRadarTile } from '../../../types/monitoring';

export interface RadarTileCoord {
  readonly z: number;
  readonly x: number;
  readonly y: number;
}

export interface RadarTileManagerOptions {
  readonly loadTile: (
    coord: RadarTileCoord & { readonly signal: AbortSignal }
  ) => Promise<RainViewerRadarTile>;
  readonly reportRadarResult: OverviewDataController['reportRadarResult'];
  readonly createObjectUrl?: (blob: Blob) => string;
  readonly revokeObjectUrl?: (url: string) => void;
}

export interface RecordState {
  readonly key: string;
  readonly generationId: number;
  readonly requestId: number;
  readonly controller: AbortController;
  readonly promise: Promise<RainViewerRadarTile | null>;
  objectUrl: string | null;
  candidateUrl: string | null;
  image: HTMLImageElement | null;
  done: ((error?: Error, tile?: HTMLElement) => void) | null;
  settled: boolean;
  cleanupImage: (() => void) | null;
  visibleLoad: Promise<void> | null;
  resolveVisibleLoad: (() => void) | null;
  rejectVisibleLoad: ((error: Error) => void) | null;
}
