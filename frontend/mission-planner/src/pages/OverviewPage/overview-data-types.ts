import type {
  ActiveXLink,
  GetMonitoringHistoryArgs,
  GroundEntryPoint,
  MonitoringHistory,
  OverviewPOIFilter,
  OverviewStatus,
  POIETAFilter,
  POIETAResponse,
  RouteCoordinates,
} from '../../types/monitoring';
import type { OverviewRefreshCadence } from './preferences';
import type { OverviewRefreshController } from './useOverviewRefresh';

export type OverviewSourceKey =
  | 'telemetry'
  | 'history'
  | 'activeLink'
  | 'pois'
  | 'satellites'
  | 'missionEvents'
  | 'route'
  | 'groundEntryPoint'
  | 'radar';
export const SOURCE_LABELS = {
  telemetry: 'Telemetry',
  history: 'History',
  activeLink: 'Active link',
  pois: 'POIs',
  satellites: 'Satellite ETAs',
  missionEvents: 'Mission events',
  route: 'Route',
  groundEntryPoint: 'Ground entry point',
  radar: 'Weather radar',
} as const satisfies Record<OverviewSourceKey, string>;
export const SOURCE_ORDER = [
  'telemetry',
  'history',
  'activeLink',
  'pois',
  'satellites',
  'missionEvents',
  'route',
  'groundEntryPoint',
  'radar',
] as const satisfies readonly OverviewSourceKey[];
export type OverviewCanonicalFreshnessKey =
  | 'telemetry'
  | 'history'
  | 'activeLink'
  | 'pois'
  | 'route'
  | 'groundEntryPoint'
  | 'radar';
export type OverviewSourcePhase =
  | 'initial-loading'
  | 'ready'
  | 'refreshing'
  | 'error'
  | 'stale'
  | 'paused'
  | 'unavailable';
export type OverviewFreshnessState = 'fresh' | 'stale' | 'unknown';
export type OverviewAvailability = 'unknown' | 'available' | 'unavailable';
export interface OverviewSourceError {
  readonly code: 'invalid-data' | 'request-failed';
  readonly message: 'Source data was invalid.' | 'Source refresh failed.';
}
export interface OverviewSourceSlot<T> {
  readonly data: T | undefined;
  readonly phase: OverviewSourcePhase;
  readonly availability: OverviewAvailability;
  readonly freshness: OverviewFreshnessState;
  readonly sourceTimestamp: string | null;
  readonly transportLastAttemptAt: number | null;
  readonly transportLastSuccessAt: number | null;
  readonly pending: boolean;
  readonly paused: boolean;
  readonly error: OverviewSourceError | null;
}
export interface OverviewActiveLinkData {
  readonly normal: ActiveXLink;
  readonly warning: ActiveXLink;
}
export interface OverviewRouteData {
  readonly west: RouteCoordinates;
  readonly east: RouteCoordinates;
}
export interface OverviewRadarData {
  readonly frameTimestamp: string;
}
export interface OverviewDataServices {
  getStatus(signal?: AbortSignal): Promise<OverviewStatus>;
  getMonitoringHistory(
    args?: GetMonitoringHistoryArgs
  ): Promise<MonitoringHistory>;
  getGroundEntryPoint(signal?: AbortSignal): Promise<GroundEntryPoint>;
  getPOIETAs(
    filter?: POIETAFilter,
    signal?: AbortSignal
  ): Promise<POIETAResponse>;
  getSatelliteETAs(signal?: AbortSignal): Promise<POIETAResponse>;
  getMissionEventETAs(signal?: AbortSignal): Promise<POIETAResponse>;
  getRouteCoordinates(
    direction: 'west' | 'east',
    signal?: AbortSignal
  ): Promise<RouteCoordinates>;
  getActiveXLink(
    state: 'normal' | 'warning',
    signal?: AbortSignal
  ): Promise<ActiveXLink>;
}
export interface OverviewVisibility {
  isHidden(): boolean;
  subscribe(listener: () => void): () => void;
}
export interface UseOverviewDataOptions {
  readonly cadence: OverviewRefreshCadence;
  readonly poiFilter: OverviewPOIFilter;
  readonly radarEnabled: boolean;
  readonly services?: OverviewDataServices;
  readonly now?: () => number;
  readonly visibility?: OverviewVisibility;
}
export type OverviewInitialState =
  | 'initial-loading'
  | 'ready'
  | 'partial-error'
  | 'total-error';
export type OverviewManualResult = 'idle' | 'success' | 'partial' | 'failure';
export interface OverviewDataSnapshot {
  readonly telemetry: OverviewSourceSlot<OverviewStatus>;
  readonly history: OverviewSourceSlot<MonitoringHistory>;
  readonly activeLink: OverviewSourceSlot<OverviewActiveLinkData>;
  readonly pois: OverviewSourceSlot<POIETAResponse>;
  readonly satellites: OverviewSourceSlot<POIETAResponse>;
  readonly missionEvents: OverviewSourceSlot<POIETAResponse>;
  readonly route: OverviewSourceSlot<OverviewRouteData>;
  readonly groundEntryPoint: OverviewSourceSlot<GroundEntryPoint>;
  readonly radar: OverviewSourceSlot<OverviewRadarData>;
  readonly initialState: OverviewInitialState;
  readonly manualResult: OverviewManualResult;
  readonly globalTransportLastSuccessAt: number | null;
  readonly announcement: string | null;
}
export interface OverviewDataController extends OverviewRefreshController {
  reportRadarResult(
    result:
      | { readonly ok: true; readonly frameTimestamp: string }
      | { readonly ok: false; readonly error: unknown }
  ): void;
}
export interface UseOverviewDataResult {
  readonly snapshot: OverviewDataSnapshot;
  readonly controller: OverviewDataController;
}

export function batchAnnouncement(
  snapshot: OverviewDataSnapshot,
  before: { [K in OverviewSourceKey]: OverviewDataSnapshot[K] },
  after: { [K in OverviewSourceKey]: OverviewDataSnapshot[K] },
  manualResult: OverviewManualResult
): string | null {
  const manual =
    manualResult !== snapshot.manualResult && manualResult === 'success'
      ? 'Manual refresh complete.'
      : manualResult !== snapshot.manualResult && manualResult === 'partial'
        ? 'Manual refresh completed with partial failures.'
        : manualResult !== snapshot.manualResult && manualResult === 'failure'
          ? 'Manual refresh failed.'
          : null;
  if (manual) return dedupe(snapshot.announcement, manual);
  const projected = projectInitial(after);
  const initial =
    snapshot.initialState !== 'ready' && projected === 'ready'
      ? 'Overview ready.'
      : snapshot.initialState !== 'total-error' && projected === 'total-error'
        ? 'Overview data failed to load.'
        : null;
  if (initial) return dedupe(snapshot.announcement, initial);
  for (const kind of ['error', 'stale', 'recovery'] as const) {
    for (const source of SOURCE_ORDER) {
      const previous = before[source];
      const next = after[source];
      const message =
        kind === 'error' && !previous.error && next.error
          ? `${SOURCE_LABELS[source]} refresh failed.`
          : kind === 'stale' &&
              previous.freshness !== 'stale' &&
              next.freshness === 'stale'
            ? `${SOURCE_LABELS[source]} data is stale.`
            : kind === 'recovery' &&
                (previous.error || previous.freshness === 'stale') &&
                !next.error &&
                next.freshness !== 'stale'
              ? `${SOURCE_LABELS[source]} recovered.`
              : null;
      if (message) return dedupe(snapshot.announcement, message);
    }
  }
  return snapshot.announcement;
}

function dedupe(previous: string | null, next: string): string | null {
  return previous === next ? previous : next;
}

function projectInitial(slots: {
  [K in OverviewSourceKey]: OverviewDataSnapshot[K];
}): OverviewInitialState {
  const required = [slots.telemetry, slots.history, slots.pois];
  if (required.some((slot) => slot.data === undefined && slot.error === null)) {
    return 'initial-loading';
  }
  if (required.every((slot) => slot.data === undefined && slot.error)) {
    return 'total-error';
  }
  return Object.values(slots).some((slot) => slot.error)
    ? 'partial-error'
    : 'ready';
}
