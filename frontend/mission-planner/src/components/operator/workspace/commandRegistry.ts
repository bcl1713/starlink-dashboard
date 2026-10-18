import type { Pending } from '@/hooks/api/useOperatorJournal';
import type {
  CommandReceipt,
  OperatorCommand,
  SavedRecord,
} from '@/types/operator';
import { isDraftTarget, isOperatorInput } from './draftRegistry';
import type { DraftEnvelope, DraftTarget } from './types';

export const pendingPrefix = 'operator-workspace-pending:v1:';
export const targetIdentity = (target: DraftTarget) =>
  JSON.stringify([
    target.storeId,
    target.epoch,
    target.sourceMode,
    target.simulationRunId,
  ]);
export const commandLane = (target: DraftTarget) =>
  JSON.stringify([targetIdentity(target), target.missionId, target.recordType]);
export type PendingEnvelope = Pending & {
  workspace: NonNullable<Pending['workspace']>;
};
export type TransactionStatus =
  | 'saving'
  | 'uncertain'
  | 'accepted'
  | 'accepted_unreadable'
  | 'needs_review'
  | 'quarantined'
  | 'storage_error'
  | 'failed';
export interface TransactionTrayItem {
  lane: string;
  commandId: string;
  draftId: string;
  submittedRevision: number;
  target: DraftTarget;
  title: string;
  status: TransactionStatus;
  message: string | null;
  pending?: PendingEnvelope;
  receipt?: CommandReceipt;
  current?: SavedRecord;
}

/** Adapt typed editor input; lifecycle actions still supply existing builders. */
export function draftCommand(draft: DraftEnvelope): OperatorCommand {
  if (!draft.target.recordId) return { operation: 'create', body: draft.input };
  if (!draft.baseVersion)
    throw new Error('Reread this record before submitting a replacement.');
  return {
    operation: 'update',
    record_id: draft.target.recordId,
    body: { ...draft.input, expected_version: draft.baseVersion },
  };
}

export function assertCommandTarget(
  draft: Pick<DraftEnvelope, 'target' | 'baseVersion'>,
  command: OperatorCommand
): void {
  if (
    (command.operation === 'create') !== (draft.target.recordId === null) ||
    ('record_id' in command && command.record_id !== draft.target.recordId)
  ) {
    throw new Error('Command does not match the pinned record target.');
  }
  if (command.operation === 'create' || command.operation === 'update') {
    const body = command.body;
    if (
      body.payload.entry_type === 'issue' &&
      (body.payload.corrects_version ?? null) !== draft.target.correctionVersion
    ) {
      throw new Error(
        'Command does not match the pinned historical correction target.'
      );
    }
    if (
      body.mission_id !== draft.target.missionId ||
      body.record_type !== draft.target.recordType ||
      body.scope !== draft.target.scope ||
      body.leg_id !== draft.target.legId ||
      body.payload.previous_leg_id !== draft.target.previousLegId ||
      body.payload.next_leg_id !== draft.target.nextLegId
    ) {
      throw new Error(
        'Command does not match the pinned mission and scope target.'
      );
    }
  }
  if (
    command.operation !== 'create' &&
    command.body.expected_version !== draft.baseVersion
  ) {
    throw new Error(
      'Command does not match the draft base version. Reread before continuing.'
    );
  }
}

export function loadPendingOwners(storage: Storage | null): {
  requests: PendingEnvelope[];
  errors: string[];
} {
  const result: { requests: PendingEnvelope[]; errors: string[] } = {
    requests: [],
    errors: [],
  };
  if (!storage) return result;
  try {
    for (let i = 0; i < storage.length; i++) {
      const key = storage.key(i);
      if (!key?.startsWith(pendingPrefix)) continue;
      try {
        const p = JSON.parse(storage.getItem(key)!) as PendingEnvelope;
        const t = p.workspace?.target;
        if (
          !isDraftTarget(t) ||
          p.workspace.schemaVersion !== 1 ||
          typeof p.workspace.draftId !== 'string' ||
          !p.workspace.draftId ||
          (t.recordId === null
            ? t.newDraftId !== p.workspace.draftId
            : t.newDraftId !== null) ||
          (p.command?.operation === 'create'
            ? p.workspace.baseVersion !== null
            : !Number.isInteger(p.workspace.baseVersion) ||
              Number(p.workspace.baseVersion) < 1) ||
          !Number.isInteger(p.workspace.revision) ||
          p.workspace.revision < 1 ||
          typeof p.key !== 'string' ||
          typeof p.epoch !== 'string' ||
          p.identity !== targetIdentity(t) ||
          p.epoch !== t.epoch ||
          key !== pendingPrefix + commandLane(t) ||
          !['create', 'update', 'remove', 'restore'].includes(
            p.command?.operation
          )
        )
          throw new Error('Invalid pending envelope');
        if (
          p.command.operation === 'create' ||
          p.command.operation === 'update'
        ) {
          if (
            !isOperatorInput(p.command.body) ||
            p.command.body.mission_id !== t.missionId ||
            p.command.body.record_type !== t.recordType
          )
            throw new Error('Mismatched pending target');
        }
        if (p.command.body.schema_version !== 1)
          throw new Error('Invalid command schema');
        assertCommandTarget(
          { target: t, baseVersion: p.workspace.baseVersion },
          p.command
        );
        result.requests.push(p);
      } catch {
        result.errors.push(
          'A stored save is invalid and remains quarantined for recovery.'
        );
      }
    }
  } catch {
    result.errors.push('Pending save storage unavailable. Keep this tab open.');
  }
  return result;
}
