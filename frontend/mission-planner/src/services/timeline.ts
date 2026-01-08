import { apiClient } from './api-client';

export interface TimelineSegment {
  id: string;
  start_time: string;
  end_time: string;
  status: string;
  x_state?: string;
  ka_state?: string;
  ku_state?: string;
  reasons?: string[];
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

export interface Timeline {
  mission_leg_id: string;
  created_at: string;
  segments: TimelineSegment[];
  advisories?: unknown[];
  statistics?: Record<string, unknown>;
  samples?: RouteSample[] | null;
}

export interface TimelinePreviewRequest {
  transports: {
    initial_x_satellite_id: string;
    initial_ka_satellite_ids: string[];
    x_transitions: Array<{
      latitude: number;
      longitude: number;
      to_satellite: string;
    }>;
    ka_outages: Array<{
      start_time: string;
      duration_seconds: number;
    }>;
    aar_windows: Array<{
      start_waypoint: string;
      end_waypoint: string;
    }>;
    ku_overrides: Array<Record<string, unknown>>;
  };
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
