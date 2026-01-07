import { useQuery } from '@tanstack/react-query';
import { timelineService, type Timeline } from '../../services/timeline';

export function useTimeline(missionId: string, legId: string) {
  return useQuery<Timeline | null>({
    queryKey: ['timeline', missionId, legId],
    queryFn: () => timelineService.getTimeline(missionId, legId),
    enabled: !!missionId && !!legId,
  });
}
