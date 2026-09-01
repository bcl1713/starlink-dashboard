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
  /** Wall-clock milliseconds used only for payload freshness and UI state. */
  readonly now?: () => number;
  /** Monotonic milliseconds used only to schedule history network starts. */
  readonly historyScheduleNow?: () => number;
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
export type OverviewSlotData = OverviewDataSnapshot[OverviewSourceKey]['data'];
export type OverviewRadarReport =
  | { readonly ok: true; readonly frameTimestamp: string }
  | { readonly ok: false; readonly error: unknown };
export type OverviewSlotOutcome =
  | { ok: true; data: OverviewSlotData }
  | {
      ok: false;
      error: OverviewSourceError | null;
      data?: OverviewSlotData;
      manualFailure?: boolean;
      pending?: boolean;
    };
export interface OverviewDataController extends OverviewRefreshController {
  readonly radarRefreshToken: number;
  retryRadar(): void;
  reportRadarResult(token: number, result: OverviewRadarReport): void;
}
export interface UseOverviewDataResult {
  readonly snapshot: OverviewDataSnapshot;
  readonly controller: OverviewDataController;
}
