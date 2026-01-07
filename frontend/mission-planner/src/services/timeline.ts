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

export interface Timeline {
  mission_leg_id: string;
  created_at: string;
  segments: TimelineSegment[];
  advisories?: unknown[];
  statistics?: Record<string, unknown>;
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
};
