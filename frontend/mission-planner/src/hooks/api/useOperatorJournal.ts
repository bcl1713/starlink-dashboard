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
  const reconciliationTarget = useRef<{
    recordId?: string;
    epoch: string;
  } | null>(null);
  const [reconcileError, setReconcileError] = useState<string | null>(null);
  const [missingInNewStore, setMissingInNewStore] = useState(false);
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
      reconciliationTarget.current = null;
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
      if (failure.status && failure.status < 500) {
        keep(null);
        if (failure.status !== 409) reconciliationTarget.current = null;
      }
      if (failure.status === 409) {
        setBlocked(true);
        if ('record_id' in request.command) {
          try {
            setLatest(await readOperatorRecord(request.command.record_id));
          } catch {
            setReconcileError(
              'Latest saved entry could not be read. Reread again after recovery.'
            );
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
    reconciliationTarget.current = {
      recordId: 'record_id' in command ? command.record_id : undefined,
      epoch: request.epoch,
    };
    setReconcileError(null);
    setMissingInNewStore(false);
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
  function releaseReconciliation() {
    keep(null);
    setBlocked(false);
    setError(null);
    setLatest(null);
    setReconcileError(null);
    setMissingInNewStore(false);
    reconciliationTarget.current = null;
  }
  function recoverMissing() {
    if (!missingInNewStore || !blocked || inFlight.current) return false;
    releaseReconciliation();
    return true;
  }
  async function reconcile() {
    if (inFlight.current) return false;
    inFlight.current = true;
    setSaving(true);
    setMissingInNewStore(false);
    try {
      const fresh = await health.refetch();
      if (fresh.isError || !fresh.data?.ready) {
        setReconcileError(
          'Operator store could not be reread. Try again after recovery.'
        );
        return false;
      }
      const reread = await records.refetch();
      if (reread.isError) {
        setReconcileError(
          'Journal entries could not be reread. Your draft is retained.'
        );
        return false;
      }
      const target = reconciliationTarget.current;
      let current: SavedRecord | undefined;
      if (target?.recordId) {
        try {
          current = (await readOperatorRecord(target.recordId)).record;
        } catch (caught) {
          if (
            operatorFailure(caught).status === 404 &&
            fresh.data.api_epoch &&
            target.epoch !== fresh.data.api_epoch
          ) {
            setMissingInNewStore(true);
            setReconcileError(
              'Entry is absent from the current store. The old save cannot be replayed. Keep your draft as a new entry or discard it after releasing the old save.'
            );
          } else
            setReconcileError(
              'Latest saved entry could not be read. Your draft is retained; reread again after recovery.'
            );
          return false;
        }
      }
      releaseReconciliation();
      return { current };
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  }
  return {
    health,
    records,
    pending,
    saving,
    error,
    blocked,
    latest,
    reconcileError,
    missingInNewStore,
    recoverMissing,
    save,
    retry,
    reconcile,
  };
}
