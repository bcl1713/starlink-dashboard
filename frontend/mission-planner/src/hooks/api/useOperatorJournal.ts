import { useRef, useState } from 'react';
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  getOperatorHealth,
  operatorFailure,
  readOperatorRecord,
  readOperatorRecords,
  saveOperatorCommand,
} from '@/services/operator';
import type {
  CommandReceipt,
  OperatorCommand,
  OperatorFailure,
  ReadRecord,
  SavedRecord,
} from '@/types/operator';
export function useOperatorHealth() {
  return useQuery({
    queryKey: ['operator-health'],
    queryFn: getOperatorHealth,
    retry: false,
    refetchInterval: 15000,
    networkMode: 'always',
  });
}
interface Pending {
  command: OperatorCommand;
  key: string;
  epoch: string;
}
export function useOperatorJournal(missionId: string) {
  const client = useQueryClient();
  const health = useOperatorHealth();
  const records = useInfiniteQuery({
    queryKey: ['operator-records', missionId],
    queryFn: ({ pageParam }) =>
      readOperatorRecords(
        {
          mission_id: missionId,
          record_type: 'journal_entry',
          include_removed: true,
        },
        pageParam
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.cursor ?? undefined,
    enabled: !!missionId && health.data?.ready === true && !health.isError,
    retry: false,
    networkMode: 'always',
  });
  const [pending, setPending] = useState<Pending | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  const inFlight = useRef(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<OperatorFailure | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [latest, setLatest] = useState<ReadRecord | null>(null);
  function keep(value: Pending | null) {
    pendingRef.current = value;
    setPending(value);
  }
  async function refresh() {
    await client.invalidateQueries({
      queryKey: ['operator-records', missionId],
    });
    await client.invalidateQueries({ queryKey: ['operator-history'] });
  }
  async function execute(
    request: Pending
  ): Promise<{ receipt: CommandReceipt; current?: SavedRecord } | undefined> {
    if (inFlight.current) return;
    inFlight.current = true;
    setSaving(true);
    setError(null);
    try {
      const receipt = await saveOperatorCommand(
        request.command,
        request.key,
        request.epoch
      );
      keep(null);
      setLatest(null);
      await refresh();
      // A replay receipt can predate later corrections. Reopen the current row.
      let current: SavedRecord | undefined;
      try {
        current = (await readOperatorRecord(receipt.saved_records[0].record_id))
          .record;
      } catch {
        /* Saved receipt is still valid; current reads remain separately unavailable. */
      }
      return { receipt, current };
    } catch (caught) {
      const failure = operatorFailure(caught);
      setError(failure);
      if (failure.status && failure.status < 500) keep(null);
      if (failure.status === 409) {
        setBlocked(true);
        if ('record_id' in request.command) {
          try {
            setLatest(await readOperatorRecord(request.command.record_id));
          } catch {
            /* Draft remains usable when latest cannot be read. */
          }
        }
        await refresh();
        await health.refetch();
      }
      return undefined;
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  }
  async function save(command: OperatorCommand) {
    if (
      inFlight.current ||
      pendingRef.current ||
      blocked ||
      health.isError ||
      !health.data?.ready ||
      !health.data.api_epoch
    )
      return;
    const request = {
      command: JSON.parse(JSON.stringify(command)) as OperatorCommand,
      key: crypto.randomUUID(),
      epoch: health.data.api_epoch,
    };
    keep(request);
    return execute(request);
  }
  async function retry() {
    const request = pendingRef.current;
    if (!request || blocked || inFlight.current) return;
    // Always reread health; an uncertain command cannot cross a store epoch.
    const fresh = await health.refetch();
    if (!fresh.data?.ready || fresh.isError) return;
    if (fresh.data.api_epoch !== request.epoch) {
      setBlocked(true);
      setError({
        code: 'epoch_mismatch',
        message: 'Store changed. Reread and reconcile before saving.',
        retryable: false,
      });
      return;
    }
    return execute(request);
  }
  async function reconcile() {
    if (inFlight.current) return false;
    const fresh = await health.refetch();
    if (fresh.isError || !fresh.data?.ready) return false;
    const reread = await records.refetch();
    if (reread.isError) return false;
    const id =
      latest?.record.record_id ??
      (pendingRef.current && 'record_id' in pendingRef.current.command
        ? pendingRef.current.command.record_id
        : undefined);
    let current: SavedRecord | undefined;
    if (id) {
      try {
        current = (await readOperatorRecord(id)).record;
      } catch {
        return false;
      }
    }
    keep(null);
    setBlocked(false);
    setError(null);
    setLatest(null);
    return { current };
  }
  return {
    health,
    records,
    pending,
    saving,
    error,
    blocked,
    latest,
    save,
    retry,
    reconcile,
  };
}
