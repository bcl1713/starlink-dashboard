import type { Pending } from '@/hooks/api/useOperatorJournal';
import type {
  CommandReceipt,
  OperatorCommand,
  SavedRecord,
} from '@/types/operator';
import { isOperatorInput } from './draftRegistry';
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
  draft: DraftEnvelope,
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
          !t ||
          typeof p.workspace.draftId !== 'string' ||
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
