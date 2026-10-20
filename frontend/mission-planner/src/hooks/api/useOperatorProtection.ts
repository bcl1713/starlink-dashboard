import { useQuery } from '@tanstack/react-query';
import { missionsApi } from '@/services/missions';
import { timelineService } from '@/services/timeline';
import type { SavedRecord } from '@/types/operator';
import { deriveProtection } from '@/components/operator/conferenceProtection';
export function useOperatorProtection(
  missionId: string,
  records: SavedRecord[],
  asOf: string,
  recordsComplete: boolean
) {
  const query = useQuery({
    queryKey: ['operator-protection', missionId, asOf],
    enabled: !!missionId && !!asOf,
    queryFn: async () => {
      const mission = await missionsApi.get(missionId);
      return Promise.all(
        mission.legs.map(async (leg) => ({
          legId: leg.id,
          timeline: await timelineService.getTimeline(missionId, leg.id),
        }))
      );
    },
    retry: false,
    networkMode: 'always',
  });
  return {
    ...query,
    snapshot: deriveProtection(
      records,
      query.data ?? [],
      asOf,
      recordsComplete && !query.isError && !query.isFetching
    ),
  };
}
