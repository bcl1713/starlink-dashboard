import apiClient from './api-client';
import type { MissionTimelineSnapshot } from '@/types/missionTimeline';

export async function readMissionTimeline(
  missionId: string,
  signal?: AbortSignal
): Promise<MissionTimelineSnapshot> {
  return (
    await apiClient.get<MissionTimelineSnapshot>(
      '/api/v2/operator/events/mission-timeline',
      { params: { mission_id: missionId }, signal }
    )
  ).data;
}
