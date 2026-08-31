import type { Map as LeafletMap } from 'leaflet';

import type {
  OverviewDataController,
  OverviewDataSnapshot,
  OverviewSourcePhase,
} from '../overview-data-types';
import type { OverviewGeometryPoint } from '../geometry';

export type OperationalLayerId =
  | 'weather-radar'
  | 'planned-route-west'
  | 'planned-route-east'
  | 'active-x-band-normal'
  | 'active-x-band-warning'
  | 'position-history-west'
  | 'position-history-east'
  | 'flight-route-markers'
  | 'satellites'
  | 'mission-events'
  | 'ground-entry-point-layer'
  | 'current-position-layer';

export type VectorLayerId = Exclude<OperationalLayerId, 'weather-radar'>;
export type OperationalLayerVisibility = Readonly<
  Record<OperationalLayerId, boolean>
>;

export type OperationalFeatureKind =
  | 'route-segment'
  | 'active-link'
  | 'history-segment'
  | 'poi'
  | 'satellite'
  | 'mission-event'
  | 'ground-entry-point'
  | 'current-position';

export interface OperationalFeatureDetail {
  readonly label: string;
  readonly value: string;
}

export interface OperationalFeature {
  readonly id: string;
  readonly layerId: VectorLayerId;
  readonly kind: OperationalFeatureKind;
  readonly label: string;
  readonly geometry:
    | {
        readonly type: 'point';
        readonly latitude: number;
        readonly longitude: number;
      }
    | {
        readonly type: 'line';
        readonly points: readonly OverviewGeometryPoint[];
      };
  readonly details: readonly OperationalFeatureDetail[];
}

export interface OperationalLayerState {
  readonly id: OperationalLayerId;
  readonly visible: boolean;
  readonly phase: OverviewSourcePhase;
  readonly count: number;
  readonly sourceTimestamp: string | null;
  readonly retainedLastGood: boolean;
  readonly message: string;
}

export interface OperationalMapProps {
  readonly snapshot: OverviewDataSnapshot;
  readonly radarEnabled: boolean;
  readonly radarRefreshToken: number;
  readonly retryRadar: OverviewDataController['retryRadar'];
  readonly reportRadarResult: OverviewDataController['reportRadarResult'];
  readonly onRadarEnabledChange: (enabled: boolean) => void;
  readonly initialLayerVisibility?: OperationalLayerVisibility;
  readonly onLayerVisibilityChange?: (
    visibility: OperationalLayerVisibility
  ) => void;
  readonly onMapReady?: (map: LeafletMap) => void;
}

export interface OperationalMapHandle {
  fitToAvailableLayers(): void;
  focusCoordinates(
    options: Readonly<{
      latitude: number;
      longitude: number;
      zoom: 8;
      motion: 'reduced-aware';
    }>
  ): void;
  getMap(): LeafletMap | null;
}
