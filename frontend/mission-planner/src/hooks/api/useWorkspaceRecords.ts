import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import {
  infiniteQueryOptions,
  useInfiniteQuery,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import {
  operatorFailure,
  readOperatorChanges,
  readOperatorRecords,
} from '@/services/operator';
import type {
  OperatorHealth,
  ReadRecord,
  RecordPage,
  RecordDeparture,
  SavedRecord,
} from '@/types/operator';
import { operatorIdentity } from './operatorReadSession';

class RecordSourceChanged extends Error {}
class InvalidRecordCheckpoint extends Error {}

function sourceStamp(source: OperatorHealth) {
  return JSON.stringify([
    source.store_id,
    source.api_epoch,
    source.source_mode,
    source.simulation_run_id,
    source.replay_run_id ?? null,
    source.operating_context_id ?? null,
    !!source.mission_journal,
  ]);
}

function validate(
  page: RecordPage,
  missionId: string,
  identity: string | null,
  expected?: OperatorHealth
) {
  if (
    !page.source ||
    !identity ||
    page.source.mission_id !== missionId ||
    operatorIdentity(page.source) !== identity ||
    (expected && sourceStamp(page.source) !== sourceStamp(expected)) ||
    page.items.some((item) => item.record.mission_id !== missionId)
  )
    throw new RecordSourceChanged(
      'Saved records source changed; waiting for current context.'
    );
  if (
    (page.departures ?? []).some(
      (row) =>
        !row.record_id ||
        !Number.isSafeInteger(row.version) ||
        row.version < 1 ||
        !Number.isSafeInteger(row.journal_seq) ||
        row.journal_seq < 1 ||
        row.journal_seq > page.H
    )
  )
    throw new InvalidRecordCheckpoint('Invalid saved records departure.');
  if (!Number.isSafeInteger(page.H) || page.H < 0)
    throw new InvalidRecordCheckpoint('Invalid saved records checkpoint.');
}

export function workspaceRecordsOptions(
  missionId: string,
  identity: string | null,
  expected?: OperatorHealth
) {
  return infiniteQueryOptions({
    queryKey: ['operator-records', missionId, identity, 'workspace-all'],
    queryFn: async ({ pageParam, signal }) => {
      const page = await readOperatorRecords(
        { mission_id: missionId, include_removed: true },
        pageParam,
        { signal, sourceIdentity: identity }
      );
      validate(page, missionId, identity, expected);
      return page;
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.cursor ?? undefined,
    retry: false,
    networkMode: 'always',
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  });
}

/** Highest authoritative saved version wins, including removal/restoration. */
export function mergeWorkspaceRecords(...groups: ReadRecord[][]): ReadRecord[] {
  const merged = new Map<string, ReadRecord>();
  for (const group of groups)
    for (const item of group) {
      const previous = merged.get(item.record.record_id);
      if (!previous || previous.record.version <= item.record.version)
        merged.set(item.record.record_id, item);
    }
  return [...merged.values()];
}

function mergeDepartures(...groups: RecordDeparture[][]): RecordDeparture[] {
  const merged = new Map<string, RecordDeparture>();
  for (const row of groups.flat()) {
    const previous = merged.get(row.record_id);
    if (!previous || previous.version < row.version)
      merged.set(row.record_id, row);
  }
  return [...merged.values()];
}

interface Updates {
  departures: RecordDeparture[];
  H: number;
  items: ReadRecord[];
  changed: boolean;
}
interface CurrentRecords {
  departures: RecordDeparture[];
  source?: string;
  overlayFloor?: number;
  resetOverlays?: boolean;
  items: ReadRecord[];
  quarantined: boolean;
}
function requiresReset(error: unknown) {
  const failure = operatorFailure(error);
  return (
    error instanceof RecordSourceChanged ||
    error instanceof InvalidRecordCheckpoint ||
    failure.status === 422 ||
    ['store_epoch_changed', 'store_context_changed'].includes(failure.code)
  );
}

/** Workspace owns polling; editor observers pass owner=false and share saved data. */
export function useWorkspaceRecords(
  missionId: string,
  identity: string | null,
  owner = true
) {
  const client = useQueryClient();
  const [visible, setVisible] = useState(() => !document.hidden);
  const health = client.getQueryData<OperatorHealth>(['operator-health']);
  const expected = operatorIdentity(health) === identity ? health : undefined;
  const options = workspaceRecordsOptions(missionId, identity, expected);
  const key = options.queryKey;
  const updateKey = ['operator-record-updates', missionId, identity];
  const currentKey = ['operator-record-current', missionId, identity];
  const current = useQuery<CurrentRecords>({
    queryKey: currentKey,
    queryFn: async () => ({ items: [], departures: [], quarantined: true }),
    initialData: { items: [], departures: [], quarantined: true },
    enabled: false,
  });
  const enabled = !!missionId && !!identity;
  const records = useInfiniteQuery({
    ...options,
    enabled,
    // Only failed bootstrap reads retry on the foreground timer. Idle snapshots
    // and their original pagination cursors do not get periodically reread.
    refetchInterval:
      owner && visible
        ? (query) => (query.state.status === 'error' ? 2000 : false)
        : false,
    refetchIntervalInBackground: false,
  });
  const updates = useQuery({
    queryKey: updateKey,
    enabled: owner && visible && enabled && !!records.data && !records.isError,
    queryFn: async ({ signal }) => {
      const baseline =
        client.getQueryData<InfiniteData<RecordPage>>(key)?.pages[0];
      if (!baseline) throw new Error('Waiting for saved records baseline.');
      validate(baseline, missionId, identity, expected);
      const previous = client.getQueryData<Updates>(updateKey);
      const after = previous?.H ?? baseline.H;
      let cursor: string | undefined;
      let H: number | undefined;
      const staged: ReadRecord[] = [];
      const departures: RecordDeparture[] = [];
      const seen = new Set<string>();
      do {
        const page = await readOperatorChanges(
          missionId,
          identity!,
          after,
          cursor,
          signal
        );
        signal.throwIfAborted();
        validate(page, missionId, identity, baseline.source);
        if (page.H < after || (H !== undefined && page.H !== H))
          throw new InvalidRecordCheckpoint('Saved records batch changed.');
        H = page.H;
        staged.push(...page.items);
        departures.push(...(page.departures ?? []));
        cursor = page.cursor ?? undefined;
        if (cursor && seen.has(cursor))
          throw new InvalidRecordCheckpoint('Repeated saved records cursor.');
        if (cursor) seen.add(cursor);
      } while (cursor);
      return {
        H: H!,
        items: mergeWorkspaceRecords(previous?.items ?? [], staged),
        departures: mergeDepartures(previous?.departures ?? [], departures),
        changed: staged.length > 0 || departures.length > 0,
      };
    },
    retry: false,
    networkMode: 'always',
    refetchInterval: owner && visible ? 2000 : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  });
  const {
    data: baselineData,
    isError: baselineError,
    refetch: refetchBaseline,
  } = records;
  const { refetch: refetchUpdates } = updates;
  const refresh = useCallback(() => {
    if (!owner || document.hidden) return;
    if (baselineData && !baselineError)
      void refetchUpdates({ cancelRefetch: false });
    else void refetchBaseline({ cancelRefetch: false });
  }, [owner, baselineData, baselineError, refetchBaseline, refetchUpdates]);
  useEffect(() => {
    if (!owner) return;
    const visibility = () => {
      setVisible(!document.hidden);
      if (!document.hidden) refresh();
    };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('online', refresh);
    window.addEventListener('focus', refresh);
    return () => {
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('online', refresh);
      window.removeEventListener('focus', refresh);
    };
  }, [client, owner, missionId, identity, refresh]);
  useEffect(
    () => () => {
      if (owner)
        void client.cancelQueries({
          queryKey: ['operator-record-updates', missionId, identity],
          exact: true,
        });
    },
    [client, owner, missionId, identity]
  );
  const handled = useRef<unknown>(null);
  const resetError = requiresReset(updates.error)
    ? updates.error
    : records.data && requiresReset(records.error)
      ? records.error
      : null;
  useEffect(() => {
    if (!owner || !resetError || handled.current === resetError) return;
    handled.current = resetError;
    // Quarantine belongs to the shared read generation, not a query error that
    // resetQueries clears. Passive editors must observe the same barrier.
    client.setQueryData<CurrentRecords>(currentKey, (previous) => ({
      ...previous,
      resetOverlays: true,
      items: [],
      departures: previous?.departures ?? [],
      quarantined: true,
    }));
    // Query cancellation reverts/ignores old promises even if a transport ignores
    // abort. Reset discards every page/cursor and the old overlay generation.
    void client.cancelQueries({ queryKey: updateKey, exact: true });
    void client.resetQueries({ queryKey: key, exact: true });
    void client.resetQueries({ queryKey: updateKey, exact: true });
    // The new baseline and next bounded update tick recover this lane. Do not
    // recursively refetch here: a source changing repeatedly must not spin.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, owner, resetError, missionId, identity]);
  const sourceChanged =
    requiresReset(records.error) || requiresReset(updates.error);
  useLayoutEffect(() => {
    if (!records.data || records.isError || sourceChanged) return;
    // Keep the highest version ever displayed in this validated generation.
    // Snapshot replacement may move a newer record beyond the loaded pages;
    // an older retained delta must never become visible again in its place.
    client.setQueryData<CurrentRecords>(currentKey, (previous) => ({
      items: mergeWorkspaceRecords(
        previous?.quarantined ? [] : (previous?.items ?? []),
        records.data.pages.flatMap((page) => page.items),
        updates.data?.items ?? []
      ),
      departures: mergeDepartures(
        previous?.source === sourceStamp(records.data.pages[0].source!)
          ? previous.departures
          : [],
        updates.data?.departures ?? []
      ),
      // A fresh or replacement baseline supersedes older local confirmations,
      // even when a moved record is absent and no departure was observed. Later
      // snapshot pages supply authoritative members; drafts/base versions stay
      // in their separate registry. New confirmations above H still supplement.
      overlayFloor: previous?.resetOverlays
        ? records.data.pages[0].H
        : (previous?.overlayFloor ?? records.data.pages[0].H),
      resetOverlays: false,
      source: sourceStamp(records.data.pages[0].source!),
      quarantined: false,
    }));
    // Primitive key contents identify the generation; current.data is deliberately
    // not a dependency because this effect is the writer of that cache entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    client,
    missionId,
    identity,
    records.data,
    records.isError,
    sourceChanged,
    updates.data,
  ]);
  const quarantined = sourceChanged || (current.data?.quarantined ?? true);
  useEffect(() => {
    if (!owner || !sourceChanged) return;
    void client.invalidateQueries(
      { queryKey: ['operator-health'] },
      { cancelRefetch: false }
    );
    void client.invalidateQueries(
      { queryKey: ['operator-operating-context'] },
      { cancelRefetch: false }
    );
  }, [client, owner, sourceChanged]);
  useEffect(() => {
    if (!owner || !updates.data?.changed) return;
    let active = true;
    for (const name of ['mission-timeline', 'operator-events']) {
      const filters = { queryKey: [name, missionId, identity], exact: true };
      // Explicit cancellation also covers a bootstrap request with no cached
      // data. Its late pre-save result must not absorb the post-change refresh.
      void client.cancelQueries(filters).then(() => {
        if (active) return client.invalidateQueries(filters);
      });
    }
    return () => {
      active = false;
    };
  }, [client, owner, missionId, identity, updates.data]);
  const departures = mergeDepartures(
    current.data?.departures ?? [],
    updates.data?.departures ?? []
  );
  const departedVersions = new Map(
    departures.map((row) => [row.record_id, row.version])
  );
  const isCurrentMember = (record: SavedRecord) =>
    (departedVersions.get(record.record_id) ?? 0) < record.version;
  return {
    ...records,
    items:
      !enabled || quarantined
        ? []
        : mergeWorkspaceRecords(
            current.data?.items ?? [],
            records.data?.pages.flatMap((page) => page.items) ?? [],
            updates.data?.items ?? []
          ).filter((item) => isCurrentMember(item.record)),
    isError: records.isError || updates.isError,
    quarantined,
    acceptsOverlay: (record: SavedRecord) =>
      !quarantined &&
      isCurrentMember(record) &&
      record.journal_seq > (current.data?.overlayFloor ?? 0),
    refresh,
  };
}
