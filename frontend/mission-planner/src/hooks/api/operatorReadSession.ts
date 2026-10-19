import { infiniteQueryOptions, useQuery } from '@tanstack/react-query';
import { getOperatorHealth, readOperatorRecords } from '@/services/operator';
import type { OperatorHealth } from '@/types/operator';

export function useOperatorHealth(enabled = true) {
  return useQuery({
    queryKey: ['operator-health'],
    queryFn: getOperatorHealth,
    retry: false,
    enabled,
    refetchInterval: enabled ? 15000 : false,
    networkMode: 'always',
  });
}

export function operatorIdentity(health?: OperatorHealth) {
  return health?.ready && health.store_id && health.api_epoch
    ? JSON.stringify([
        health.store_id,
        health.api_epoch,
        health.source_mode,
        health.mission_journal
          ? (health.operating_context_id ??
            health.replay_run_id ??
            `idle:${health.simulation_run_id}`)
          : health.simulation_run_id,
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
    | 'participation'
    | 'issue'
    | 'transport_decision' = 'journal_entry'
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

/** Only a replay change, never an epoch/store/mode change, permits receipt recovery. */
export function sameJournalIdentity(
  before: string | null,
  after: string | null
) {
  try {
    const a = JSON.parse(before ?? 'null'),
      b = JSON.parse(after ?? 'null');
    return (
      Array.isArray(a) &&
      Array.isArray(b) &&
      a.length === 4 &&
      b.length === 4 &&
      a[2] === 'simulation' &&
      a.slice(0, 3).every((value, index) => value === b[index])
    );
  } catch {
    return false;
  }
}
