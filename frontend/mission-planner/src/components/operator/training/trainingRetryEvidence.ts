import type { CommandReceipt, SavedRecord } from '@/types/operator';
import {
  decodePendingEnvelope,
  type CommandAttempt,
  type PendingEnvelope,
  type TransactionStatus,
} from '../workspace/commandRegistry';
import type { TrainingIdentity } from './trainingProgress';
import { sameJson, sameRecord } from './trainingRecordIdentity';

type Version = Pick<SavedRecord, 'record_id' | 'version' | 'command_id'>;
export interface RetryObservation {
  request: PendingEnvelope;
  attemptIds: string[];
  committedVersions: Version[];
}
type Transaction = {
  commandId: string;
  status: TransactionStatus;
  pending?: PendingEnvelope;
  receipt?: CommandReceipt;
};
function matchesContext(
  request: PendingEnvelope,
  identity: TrainingIdentity,
  namespace: string
) {
  const t = request.workspace.target;
  return (
    t.storeId === identity.storeId &&
    t.epoch === identity.epoch &&
    t.missionId === identity.missionId &&
    t.sourceMode === 'simulation' &&
    t.simulationRunId === namespace
  );
}
/** Raw observations only; never replayed as commands or accepted as completion flags. */
export function decodeRetryObservation(
  value: unknown,
  identity: TrainingIdentity,
  namespace?: string
): RetryObservation {
  if (!value || typeof value !== 'object')
    throw new Error('Invalid retry observation');
  const candidate = value as RetryObservation;
  const request = decodePendingEnvelope(candidate.request);
  if (
    !matchesContext(
      request,
      identity,
      namespace ?? request.workspace.target.simulationRunId ?? ''
    ) ||
    !request.workspace.target.simulationRunId ||
    !Array.isArray(candidate.attemptIds) ||
    candidate.attemptIds.length > 100 ||
    !candidate.attemptIds.every((id) => typeof id === 'string' && !!id) ||
    !Array.isArray(candidate.committedVersions) ||
    candidate.committedVersions.length > 1000 ||
    !candidate.committedVersions.every(
      (row) =>
        row &&
        typeof row.record_id === 'string' &&
        Number.isInteger(row.version) &&
        row.version > 0 &&
        typeof row.command_id === 'string'
    )
  )
    throw new Error('Retry observation does not match this private mission');
  return candidate;
}
export function captureRetryObservation(
  identity: TrainingIdentity,
  namespace: string,
  transaction: Transaction,
  attempts: readonly CommandAttempt[],
  records: readonly SavedRecord[]
): RetryObservation | null {
  if (transaction.status !== 'uncertain' || !transaction.pending) return null;
  try {
    const request = decodePendingEnvelope(transaction.pending);
    if (
      !matchesContext(request, identity, namespace) ||
      request.key !== transaction.commandId
    )
      return null;
    const attemptIds = attempts
      .filter((item) => sameJson(item.request, request))
      .map((item) => item.id);
    if (!attemptIds.length) return null;
    return structuredClone({
      request,
      attemptIds,
      committedVersions: records
        .filter(
          (row) =>
            row.mission_id === identity.missionId &&
            row.provenance.source_mode === 'simulation'
        )
        .map(({ record_id, version, command_id }) => ({
          record_id,
          version,
          command_id,
        })),
    });
  } catch {
    return null;
  }
}
/** Exact retry is credited only when the first committed version predates it. */
export function collectRetryEvidence(
  identity: TrainingIdentity,
  namespace: string,
  observations: readonly RetryObservation[],
  attempts: readonly CommandAttempt[],
  transactions: readonly Transaction[],
  records: readonly SavedRecord[]
): string[] {
  for (const raw of observations) {
    try {
      const observation = decodeRetryObservation(raw, identity, namespace);
      const { request } = observation;
      const retried = attempts.some(
        (item) =>
          !observation.attemptIds.includes(item.id) &&
          sameJson(item.request, request)
      );
      if (!retried || !observation.attemptIds.length) continue;
      const receipt = transactions.find(
        (item) =>
          item.commandId === request.key &&
          ['accepted', 'accepted_unreadable'].includes(item.status)
      )?.receipt;
      if (!receipt?.saved_records.length) continue;
      if (
        receipt.saved_records.every(
          (saved) =>
            saved.command_id === receipt.command_id &&
            saved.mission_id === identity.missionId &&
            saved.provenance.source_mode === 'simulation' &&
            observation.committedVersions.some(
              (version) =>
                version.record_id === saved.record_id &&
                version.version === saved.version &&
                version.command_id === saved.command_id
            ) &&
            records.some((row) => sameRecord(row, saved))
        )
      )
        return ['lost-receipt-same-key'];
    } catch {
      /* Invalid, stale or foreign observations cannot establish an outcome. */
    }
  }
  return [];
}
