import type { OperatorFailure, SavedRecord } from '@/types/operator';
import { isOperatorInput } from '../workspace/draftRegistry';
import {
  decodePendingEnvelope,
  type CommandAttempt,
  type PendingEnvelope,
  type TransactionTrayItem,
} from '../workspace/commandRegistry';
import type { TrainingIdentity } from './trainingProgress';
import { decodeRetryReplay, type RetryReplay } from './trainingRetryReceipt';
import { sameJson } from './trainingRecordIdentity';

export interface ConflictObservation {
  identity: TrainingIdentity;
  namespace: string;
  request: PendingEnvelope;
  attemptIds: string[];
  failure: OperatorFailure;
  observedCurrent: SavedRecord;
  reviewedCurrent?: SavedRecord;
  replacement?: RetryReplay;
}
function requestInContext(
  value: unknown,
  identity: TrainingIdentity,
  namespace: string
) {
  const request = decodePendingEnvelope(value),
    t = request.workspace.target;
  if (
    t.storeId !== identity.storeId ||
    t.epoch !== identity.epoch ||
    t.missionId !== identity.missionId ||
    t.sourceMode !== 'simulation' ||
    t.simulationRunId !== namespace ||
    request.command.operation !== 'update'
  )
    throw new Error('Conflict request belongs to another private context');
  return request;
}
function saved(value: unknown): value is SavedRecord {
  const row = value as SavedRecord | undefined;
  return (
    isOperatorInput(row) &&
    !!row &&
    typeof row.record_id === 'string' &&
    !!row.record_id &&
    typeof row.command_id === 'string' &&
    !!row.command_id &&
    Number.isInteger(row.version) &&
    row.version > 0 &&
    Number.isInteger(row.journal_seq) &&
    row.journal_seq > 0 &&
    row.provenance?.source_mode === 'simulation'
  );
}
export function decodeConflictObservation(
  value: unknown,
  identity: TrainingIdentity,
  namespace?: string
): ConflictObservation {
  if (!value || typeof value !== 'object')
    throw new Error('Invalid conflict observation');
  const raw = value as ConflictObservation;
  if (
    !sameJson(raw.identity, identity) ||
    !/^operator-training-v1-[0-9a-f-]{36}$/.test(raw.namespace) ||
    (namespace !== undefined && namespace !== raw.namespace)
  )
    throw new Error('Foreign conflict observation');
  const request = requestInContext(raw.request, identity, raw.namespace);
  if (request.command.operation !== 'update')
    throw new Error('Replacement command required');
  const { record_id, body } = request.command;
  if (
    !raw.failure ||
    raw.failure.status !== 409 ||
    raw.failure.code !== 'version_conflict' ||
    typeof raw.failure.message !== 'string' ||
    typeof raw.failure.retryable !== 'boolean' ||
    !Array.isArray(raw.attemptIds) ||
    !raw.attemptIds.length ||
    raw.attemptIds.length > 100 ||
    !raw.attemptIds.every((id) => typeof id === 'string' && !!id) ||
    new Set(raw.attemptIds).size !== raw.attemptIds.length ||
    !saved(raw.observedCurrent) ||
    raw.observedCurrent.record_id !== record_id ||
    raw.observedCurrent.mission_id !== identity.missionId ||
    raw.observedCurrent.version <= body.expected_version ||
    (raw.failure.current_version !== undefined &&
      (!Number.isInteger(raw.failure.current_version) ||
        raw.failure.current_version <= body.expected_version ||
        raw.failure.current_version > raw.observedCurrent.version))
  )
    throw new Error(
      'A real stale-version attempt and concurrent saved revision are required'
    );
  if (
    raw.reviewedCurrent &&
    (!saved(raw.reviewedCurrent) ||
      raw.reviewedCurrent.record_id !== record_id ||
      raw.reviewedCurrent.mission_id !== identity.missionId ||
      raw.reviewedCurrent.version < raw.observedCurrent.version)
  )
    throw new Error('Reviewed current revision is inconsistent');
  if (raw.replacement) {
    const next = requestInContext(
      raw.replacement.attempt?.request,
      identity,
      raw.namespace
    );
    if (
      !raw.reviewedCurrent ||
      next.key === request.key ||
      next.command.operation !== 'update' ||
      next.command.record_id !== record_id ||
      next.command.body.expected_version !== raw.reviewedCurrent.version ||
      next.workspace.draftId !== request.workspace.draftId ||
      next.workspace.revision <= request.workspace.revision
    )
      throw new Error('Review and a new correctly based command are required');
    decodeRetryReplay(raw.replacement, next, raw.attemptIds);
  }
  return JSON.parse(JSON.stringify(raw)) as ConflictObservation;
}
function attemptFor(
  row: TransactionTrayItem,
  attempts: readonly CommandAttempt[]
) {
  return [...attempts]
    .reverse()
    .find(
      (attempt) =>
        attempt.request.workspace?.draftId === row.draftId &&
        attempt.request.workspace.revision === row.submittedRevision
    );
}
/** On-demand adaptation of existing attempts, structured failures and explicit rereads. */
export function retainConflictObservations(
  identity: TrainingIdentity,
  namespace: string,
  previous: readonly ConflictObservation[],
  tray: readonly TransactionTrayItem[],
  attempts: readonly CommandAttempt[],
  records: readonly SavedRecord[]
): ConflictObservation[] {
  const reads: ConflictObservation[] = [];
  for (const value of previous.slice(-8)) {
    try {
      reads.push(decodeConflictObservation(value, identity, namespace));
    } catch {
      /* Foreign facts cannot resume. */
    }
  }
  for (const row of tray) {
    if (
      row.status !== 'needs_review' ||
      row.failure?.status !== 409 ||
      row.failure.code !== 'version_conflict'
    )
      continue;
    try {
      const original = attemptFor(row, attempts);
      const request = requestInContext(original?.request, identity, namespace);
      if (
        request.command.operation !== 'update' ||
        reads.some((read) => read.request.key === request.key)
      )
        continue;
      const command = request.command;
      const current = records
        .filter((record) => record.record_id === command.record_id)
        .sort((a, b) => b.version - a.version)[0];
      const read = decodeConflictObservation(
        {
          identity,
          namespace,
          request,
          failure: row.failure,
          attemptIds: attempts
            .filter((attempt) => sameJson(attempt.request, request))
            .map((attempt) => attempt.id),
          observedCurrent: current,
        },
        identity,
        namespace
      );
      reads.push(read);
    } catch {
      /* An error label without its real request/current revision is incomplete. */
    }
  }
  for (const read of reads) {
    const row = tray.find(
      (item) => item.draftId === read.request.workspace.draftId
    );
    if (!row) continue;
    if (row.status === 'needs_review' && !row.pending && row.current) {
      try {
        Object.assign(
          read,
          decodeConflictObservation(
            { ...read, reviewedCurrent: row.current },
            identity,
            namespace
          )
        );
      } catch {
        /* A stale or unrelated reread cannot establish review. */
      }
    }
    if (
      row.receipt &&
      ['accepted', 'accepted_unreadable'].includes(row.status)
    ) {
      try {
        const attempt = attemptFor(row, attempts);
        if (!attempt || attempt.request.key !== row.commandId) continue;
        Object.assign(
          read,
          decodeConflictObservation(
            { ...read, replacement: { attempt, receipt: row.receipt } },
            identity,
            namespace
          )
        );
      } catch {
        /* A new receipt must actually match the reviewed command and base. */
      }
    }
  }
  return reads.slice(-8);
}
export function collectConflictEvidence(
  identity: TrainingIdentity,
  namespace: string,
  H: number | undefined,
  records: readonly SavedRecord[],
  values: unknown
): string[] {
  if (
    !Number.isInteger(H) ||
    H === undefined ||
    H < 0 ||
    !Array.isArray(values) ||
    values.length > 8
  )
    return [];
  for (const value of values) {
    try {
      const read = decodeConflictObservation(value, identity, namespace);
      if (
        !read.reviewedCurrent ||
        !read.replacement ||
        read.request.command.operation !== 'update'
      )
        continue;
      const command = read.request.command;
      const actual = (row: SavedRecord) =>
        row.journal_seq <= H &&
        records.some((current) => sameJson(current, row));
      const base = records.find(
        (row) =>
          row.record_id === command.record_id &&
          row.version === command.body.expected_version &&
          row.journal_seq <= H
      );
      const replacement = read.replacement.receipt.saved_records.find(
        (row) => row.record_id === command.record_id
      );
      if (
        base &&
        replacement &&
        actual(read.observedCurrent) &&
        actual(read.reviewedCurrent) &&
        base.journal_seq < read.observedCurrent.journal_seq &&
        read.observedCurrent.journal_seq <= read.reviewedCurrent.journal_seq &&
        replacement.journal_seq > read.reviewedCurrent.journal_seq &&
        read.replacement.receipt.saved_records.every(actual)
      )
        return ['real-conflict-reconciled'];
    } catch {
      /* Flags, missing revisions and foreign contexts are not evidence. */
    }
  }
  return [];
}
