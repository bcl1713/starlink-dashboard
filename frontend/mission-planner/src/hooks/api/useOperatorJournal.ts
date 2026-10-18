import { createClientId } from '@/lib/clientId';
import { useEffect, useRef, useState } from 'react';
import {
  operatorIdentity,
  operatorRecordsOptions,
  useOperatorHealth,
} from './operatorReadSession';
export { useOperatorHealth } from './operatorReadSession';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import {
  operatorFailure,
  readOperatorRecord,
  readOperatorRecords,
  saveOperatorCommand,
} from '@/services/operator';
import type {
  CommandReceipt,
  OperatorCommand,
  OperatorFailure,
  OperatorHealth,
  ReadRecord,
  SavedRecord,
} from '@/types/operator';
import type { DraftTarget } from '@/components/operator/workspace/types';
export interface Pending {
  command: OperatorCommand;
  key: string;
  epoch: string;
  identity: string;
  draftKey?: string;
  workspace?: { draftId: string; revision: number; target: DraftTarget };
}
export function useOperatorJournal(
  missionId: string,
  recordType:
    | 'journal_entry'
    | 'call'
    | 'conference'
    | 'participation'
    | 'issue'
    | 'transport_decision' = 'journal_entry',
  options: {
    durable?: boolean;
    pendingStorageKey?: string;
    requirePersistence?: boolean;
    readRecords?: boolean;
    healthPolling?: boolean;
    onReceipt?: (request: Pending, receipt: CommandReceipt) => void;
  } = {}
) {
  const client = useQueryClient();
  const health = useOperatorHealth(options.healthPolling !== false);
  const identity = operatorIdentity(health.data);
  const session = useRef<string | null>(null);
  if (session.current === null && identity) session.current = identity;
  const identityChanged = !!identity && session.current !== identity;
  const records = useInfiniteQuery({
    ...operatorRecordsOptions(missionId, identity, recordType),
    enabled:
      options.readRecords !== false &&
      !!missionId &&
      !!identity &&
      !health.isError,
  });
  const pendingKey =
    options.pendingStorageKey ??
    (options.durable
      ? `operator-367-pending:${missionId}:${recordType}`
      : null);
  const loadedKey = useRef<string | null>(null);
  const [storageError, setStorageError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  const inFlight = useRef(false);
  const reconciliationTarget = useRef<{
    recordId?: string;
    identity: string;
  } | null>(null);
  const [reconcileError, setReconcileError] = useState<string | null>(null);
  const [missingInNewStore, setMissingInNewStore] = useState(false);
  const recoveryIdentity = useRef<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<OperatorFailure | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [latest, setLatest] = useState<ReadRecord | null>(null);
  useEffect(() => {
    if (identityChanged) {
      setBlocked(true);
      setSaved(false);
      setError({
        code: 'epoch_mismatch',
        message: 'Store changed. Reread and reconcile before saving.',
        retryable: false,
      });
    }
  }, [identityChanged]);
  function openEditor(record?: SavedRecord, acknowledged = false) {
    if (blocked || identityChanged || !session.current) return;
    setSaved(acknowledged);
    reconciliationTarget.current = {
      recordId: record?.record_id,
      identity: session.current,
    };
  }
  function keep(value: Pending | null) {
    pendingRef.current = value;
    setPending(value);
    if (pendingKey) {
      try {
        if (value) sessionStorage.setItem(pendingKey, JSON.stringify(value));
        else sessionStorage.removeItem(pendingKey);
        setStorageError(null);
      } catch {
        setStorageError(
          'Pending save could not be retained across reload. Keep this page open.'
        );
        return !options.requirePersistence;
      }
    }
    return true;
  }
  useEffect(() => {
    if (!pendingKey || !identity || loadedKey.current === pendingKey) return;
    loadedKey.current = pendingKey;
    try {
      const raw = sessionStorage.getItem(pendingKey);
      if (!raw) return;
      const request = JSON.parse(raw) as Pending;
      if (
        !request.command ||
        typeof request.key !== 'string' ||
        typeof request.epoch !== 'string' ||
        typeof request.identity !== 'string'
      )
        throw new Error('Invalid pending request');
      pendingRef.current = request;
      setPending(request);
      reconciliationTarget.current = {
        recordId:
          'record_id' in request.command
            ? request.command.record_id
            : undefined,
        identity: request.identity,
      };
      if (request.identity !== identity) {
        session.current = request.identity;
        setBlocked(true);
        setError({
          code: 'epoch_mismatch',
          message:
            'Older-store save quarantined. Reread and reconcile before continuing.',
          retryable: false,
        });
      }
    } catch {
      setStorageError(
        'Saved pending request unavailable. Reread saved state before continuing.'
      );
      setBlocked(true);
    }
  }, [pendingKey, identity]);
  function stillSameStore(request: Pending) {
    return (
      operatorIdentity(
        client.getQueryData<OperatorHealth>(['operator-health'])
      ) === request.identity
    );
  }
  async function refresh() {
    // Summary reads must never delay journal receipt acknowledgment or recovery.
    void client.invalidateQueries({ queryKey: ['operator-brief', missionId] });
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
    setSaved(false);
    setError(null);
    try {
      const receipt = await saveOperatorCommand(
        request.command,
        request.key,
        request.epoch
      );
      setSaved(true);
      // The owner may be on a different route/mission by the time this arrives.
      options.onReceipt?.(request, receipt);
      if (!keep(null) && options.requirePersistence) setBlocked(true);
      if (request.draftKey) {
        try {
          sessionStorage.removeItem(request.draftKey);
        } catch {
          setStorageError(
            'Save acknowledged, but the submitted draft could not be retired. Discard it before saving again.'
          );
        }
      }
      if (!stillSameStore(request)) return;
      await refresh();
      // A replay receipt can predate later corrections. Reopen the current row.
      let current: SavedRecord | undefined;
      try {
        current = (await readOperatorRecord(receipt.saved_records[0].record_id))
          .record;
      } catch {
        /* Saved receipt is still valid; current reads remain separately unavailable. */
      }
      if (!stillSameStore(request)) return;
      setLatest(null);
      reconciliationTarget.current = {
        recordId: current?.record_id ?? receipt.saved_records[0].record_id,
        identity: request.identity,
      };
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
  async function save(
    command: OperatorCommand,
    context: {
      draftKey?: string;
      captureCurrentTime?: boolean;
      captureDimensions?: ('functional' | 'redundancy')[];
      workspace?: Pending['workspace'];
    } = {}
  ) {
    if (
      inFlight.current ||
      pendingRef.current ||
      blocked ||
      identityChanged ||
      !session.current ||
      health.isError ||
      !health.data?.ready ||
      !health.data.api_epoch
    )
      return;
    const frozen = JSON.parse(JSON.stringify(command)) as OperatorCommand;
    if (context.captureCurrentTime || context.captureDimensions?.length) {
      inFlight.current = true;
      setSaving(true);
      setSaved(false);
      setError(null);
      try {
        const current = await readOperatorRecords({
          mission_id: missionId,
          record_type: recordType,
        });
        if (frozen.operation === 'create' || frozen.operation === 'update') {
          if (context.captureCurrentTime)
            frozen.body.time = {
              ...frozen.body.time,
              occurred_at: current.as_of,
              ended_at: null,
              precision: 'exact',
              end_state: 'instant',
            };
          if (frozen.body.payload.entry_type === 'capability_assessment') {
            for (const dimension of context.captureDimensions ?? []) {
              frozen.body.payload[`${dimension}_observed_at`] = current.as_of;
              if (
                frozen.body.payload[`${dimension}_time_precision`] === 'unknown'
              )
                frozen.body.payload[`${dimension}_time_precision`] = 'exact';
            }
          }
        }
      } catch (caught) {
        setError(operatorFailure(caught));
        return undefined;
      } finally {
        inFlight.current = false;
        setSaving(false);
      }
    }
    const request = {
      command: frozen,
      draftKey: context.draftKey,
      key: createClientId(),
      epoch: health.data.api_epoch,
      identity: session.current,
      ...(context.workspace ? { workspace: context.workspace } : {}),
    };
    reconciliationTarget.current = {
      recordId: 'record_id' in command ? command.record_id : undefined,
      identity: request.identity,
    };
    setReconcileError(null);
    setMissingInNewStore(false);
    if (!keep(request)) return;
    return execute(request);
  }
  async function retry() {
    const request = pendingRef.current;
    if (!request || blocked || identityChanged || inFlight.current) return;
    // Always reread health; an uncertain command cannot cross a store epoch.
    const fresh = await health.refetch();
    if (!fresh.data?.ready || fresh.isError) return;
    if (operatorIdentity(fresh.data) !== request.identity) {
      setBlocked(true);
      setError({
        code: 'epoch_mismatch',
        message: 'Store changed. Reread and reconcile before saving.',
        retryable: false,
      });
      return;
    }
    if (options.requirePersistence && !keep(request)) return;
    return execute(request);
  }
  function releaseReconciliation() {
    if (!keep(null)) return false;
    session.current = identity;
    setBlocked(false);
    setError(null);
    setLatest(null);
    setReconcileError(null);
    setMissingInNewStore(false);
    reconciliationTarget.current = null;
    return true;
  }
  function recoverMissing() {
    if (
      !missingInNewStore ||
      recoveryIdentity.current !== identity ||
      !blocked ||
      inFlight.current
    )
      return false;
    return releaseReconciliation();
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
      const freshIdentity = operatorIdentity(fresh.data);
      try {
        await client.fetchInfiniteQuery({
          ...operatorRecordsOptions(missionId, freshIdentity, recordType),
          staleTime: 0,
        });
      } catch {
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
            target.identity !== freshIdentity
          ) {
            setMissingInNewStore(true);
            recoveryIdentity.current = freshIdentity;
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
      const confirmed = await health.refetch();
      if (
        confirmed.isError ||
        operatorIdentity(confirmed.data) !== freshIdentity
      ) {
        setReconcileError(
          'Store changed during reread. Your draft is retained; reread again.'
        );
        return false;
      }
      if (!releaseReconciliation()) return false;
      session.current = freshIdentity;
      reconciliationTarget.current =
        current && freshIdentity
          ? { recordId: current.record_id, identity: freshIdentity }
          : null;
      return { current };
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  }
  return {
    health,
    storageError,
    records,
    pending,
    saving,
    saved,
    identity,
    openEditor,
    error,
    blocked: blocked || identityChanged,
    latest,
    reconcileError,
    missingInNewStore,
    recoverMissing,
    save,
    retry,
    reconcile,
  };
}
