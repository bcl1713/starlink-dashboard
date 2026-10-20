import type { CallContinuityProjection, PopForecast } from '@/types/pop';
import { apiClient } from './api-client';
import type { TransportConfig } from '../types/mission';
import type { OverviewPoiKind } from './overview-upcoming-pois';

export interface TimelineSegment {
  id: string;
  start_time: string;
  end_time: string;
  status: string;
  x_state?: string;
  ka_state?: string;
  ku_state?: string;
  reasons?: string[];
  impacted_transports?: string[];
  latitude?: number;
  longitude?: number;
  metadata?: Record<string, unknown>;
}

export interface RouteSample {
  timestamp: string;
  latitude: number;
  longitude: number;
  altitude?: number | null;
  coverage?: string[];
}

export interface KaCoverageEvent {
  timestamp: string;
  event_type: string;
  reason: string;
  coverage: string[];
  satellite_id?: string | null;
}

export interface Timeline {
  call_capability_revision?: string | null;
  pop_forecast?: PopForecast | null;
  call_continuity?: CallContinuityProjection | null;
  map_pois?: Array<{
    name: string;
    kind: OverviewPoiKind;
    latitude: number;
    longitude: number;
    expected_arrival_time?: string | null;
    description?: string | null;
  }>;
  mission_leg_id: string;
  created_at: string;
  segments: TimelineSegment[];
  advisories?: unknown[];
  statistics?: Record<string, unknown>;
  samples?: RouteSample[] | null;
  coverage_events?: KaCoverageEvent[];
  route_basis?: 'planned' | 'derived_estimate';
  derived_route_estimate?: DerivedRouteEstimate | null;
}

export interface DerivedRouteAnchor {
  segment_index: number;
  fraction: number;
  progress_nm: number;
  latitude: number;
  longitude: number;
  connector_nm: number;
}

export interface DerivedRouteEstimate {
  available: boolean;
  estimated: boolean;
  unavailable_reason?: string | null;
  points?: Array<{
    latitude: number;
    longitude: number;
    altitude?: number | null;
    provenance: string;
  }>;
  planned_distance_nm?: number;
  derived_distance_nm?: number;
  planned_duration_seconds?: number;
  derived_duration_seconds?: number;
  delta_seconds?: number;
  speed_knots?: number | null;
  speed_source?: string | null;
  confidence?: string;
  warnings?: string[];
  leave_anchor?: DerivedRouteAnchor | null;
  rejoin_anchor?: DerivedRouteAnchor | null;
}

export interface TimelinePreviewRequest {
  transports: TransportConfig;
  adjusted_departure_time?: string;
}

export const timelineService = {
  async getTimeline(
    missionId: string,
    legId: string
  ): Promise<Timeline | null> {
    try {
      const response = await apiClient.get(
        `/api/v2/missions/${missionId}/legs/${legId}/timeline`
      );
      return response.data;
    } catch (error) {
      console.error(`Timeline not available for leg ${legId}:`, error);
      return null;
    }
  },

  async previewTimeline(
    missionId: string,
    legId: string,
    request: TimelinePreviewRequest,
    signal?: AbortSignal
  ): Promise<Timeline | null> {
    try {
      const response = await apiClient.post(
        `/api/v2/missions/${missionId}/legs/${legId}/timeline/preview`,
        request,
        { signal }
      );
      return response.data;
    } catch (error: unknown) {
      // Don't log abort errors as they're expected when requests are cancelled
      if (
        error &&
        typeof error === 'object' &&
        'name' in error &&
        error.name !== 'AbortError'
      ) {
        console.error(
          `Failed to generate timeline preview for leg ${legId}:`,
          error
        );
      }
      return null;
    }
  },
};
