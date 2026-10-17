import { infiniteQueryOptions, useQuery } from '@tanstack/react-query';
import { getOperatorHealth, readOperatorRecords } from '@/services/operator';
import type { OperatorHealth } from '@/types/operator';

export function useOperatorHealth() {
  return useQuery({
    queryKey: ['operator-health'],
    queryFn: getOperatorHealth,
    retry: false,
    refetchInterval: 15000,
    networkMode: 'always',
  });
}

export function operatorIdentity(health?: OperatorHealth) {
  return health?.ready && health.store_id && health.api_epoch
    ? JSON.stringify([
        health.store_id,
        health.api_epoch,
        health.source_mode,
        health.simulation_run_id,
      ])
    : null;
}

export function operatorRecordsOptions(
  missionId: string,
  identity: string | null,
  recordType:
    | 'journal_entry'
    | 'call'
    | 'conference'
    | 'participation' = 'journal_entry'
) {
  return infiniteQueryOptions({
    queryKey: ['operator-records', missionId, identity, recordType],
    queryFn: ({ pageParam }) =>
      readOperatorRecords(
        {
          mission_id: missionId,
          record_type: recordType,
          include_removed: true,
        },
        pageParam
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.cursor ?? undefined,
    retry: false,
    networkMode: 'always',
  });
}
