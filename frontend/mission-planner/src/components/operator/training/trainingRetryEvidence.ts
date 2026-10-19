import { decodeRetryReplay, type RetryReplay } from './trainingRetryReceipt';
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
  replay?: RetryReplay;
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
  if (candidate.replay !== undefined)
    decodeRetryReplay(candidate.replay, request, candidate.attemptIds);
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
function currentReplay(
  observation: RetryObservation,
  attempts: readonly CommandAttempt[],
  transactions: readonly Transaction[]
): RetryReplay | undefined {
  if (observation.replay) return observation.replay;
  const attempt = attempts.find(
    (item) =>
      !observation.attemptIds.includes(item.id) &&
      sameJson(item.request, observation.request)
  );
  const receipt = transactions.find(
    (item) =>
      item.commandId === observation.request.key &&
      ['accepted', 'accepted_unreadable'].includes(item.status)
  )?.receipt;
  return attempt && receipt
    ? decodeRetryReplay(
        { attempt, receipt },
        observation.request,
        observation.attemptIds
      )
    : undefined;
}
function matchesBackend(
  observation: RetryObservation,
  replay: RetryReplay,
  records: readonly SavedRecord[]
) {
  return (
    observation.attemptIds.length > 0 &&
    replay.receipt.saved_records.every(
      (saved) =>
        saved.mission_id === observation.request.workspace.target.missionId &&
        observation.committedVersions.some(
          (version) =>
            version.record_id === saved.record_id &&
            version.version === saved.version &&
            version.command_id === saved.command_id
        ) &&
        records.some((row) => sameRecord(row, saved))
    )
  );
}
/** Preserve raw reply/attempt facts, never a completion boolean or a send queue. */
export function retainRetryReceipts(
  identity: TrainingIdentity,
  namespace: string,
  observations: readonly RetryObservation[],
  attempts: readonly CommandAttempt[],
  transactions: readonly Transaction[],
  records: readonly SavedRecord[]
): RetryObservation[] {
  return observations.map((raw) => {
    try {
      const observation = decodeRetryObservation(raw, identity, namespace);
      const replay = currentReplay(observation, attempts, transactions);
      return replay && matchesBackend(observation, replay, records)
        ? structuredClone({ ...observation, replay })
        : raw;
    } catch {
      return raw;
    }
  });
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
      const replay = currentReplay(observation, attempts, transactions);
      if (replay && matchesBackend(observation, replay, records))
        return ['lost-receipt-same-key'];
    } catch {
      /* Corrupt, retired-context or unrelated facts cannot prove an outcome. */
    }
  }
  return [];
}
