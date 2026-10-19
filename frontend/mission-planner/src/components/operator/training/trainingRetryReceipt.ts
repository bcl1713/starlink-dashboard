import type { CommandReceipt, SavedRecord } from '@/types/operator';
import { isOperatorInput } from '../workspace/draftRegistry';
import {
  decodePendingEnvelope,
  type CommandAttempt,
  type PendingEnvelope,
} from '../workspace/commandRegistry';
import { sameJson } from './trainingRecordIdentity';

export interface RetryReplay {
  attempt: CommandAttempt;
  receipt: CommandReceipt;
}
function canonicalUtc(value: string) {
  const match =
    /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(?:Z|\+00:00)$/.exec(
      value
    );
  return match ? `${match[1]}.${(match[2] ?? '').padEnd(6, '0')}Z` : value;
}
function sameInputValue(expected: unknown, actual: unknown, key = ''): boolean {
  if (
    typeof expected === 'string' &&
    typeof actual === 'string' &&
    (key === 'at' || key.endsWith('_at'))
  )
    return canonicalUtc(expected) === canonicalUtc(actual);
  if (Array.isArray(expected))
    return (
      Array.isArray(actual) &&
      expected.length === actual.length &&
      expected.every((value, index) => sameInputValue(value, actual[index]))
    );
  if (expected && typeof expected === 'object')
    return (
      !!actual &&
      typeof actual === 'object' &&
      Object.entries(expected).every(
        ([field, value]) =>
          Object.prototype.hasOwnProperty.call(actual, field) &&
          sameInputValue(
            value,
            (actual as Record<string, unknown>)[field],
            field
          )
      )
    );
  return expected === actual;
}
function principalMatches(request: PendingEnvelope, row: SavedRecord) {
  const command = request.command;
  if (row.operation !== command.operation) return false;
  if (
    command.operation !== 'create' &&
    (row.record_id !== command.record_id ||
      row.version !== command.body.expected_version + 1)
  )
    return false;
  if (command.operation === 'create' && row.version !== 1) return false;
  if (command.operation === 'remove' || command.operation === 'restore')
    return true;
  const body = command.body;
  if (!isOperatorInput(body)) return false;
  return (
    row.mission_id === body.mission_id &&
    row.record_type === body.record_type &&
    row.scope === body.scope &&
    row.leg_id === body.leg_id &&
    sameInputValue(body.time, row.time) &&
    sameInputValue(body.payload, row.payload)
  );
}
/** Validate raw observed reply facts; current complete backend history remains required. */
export function decodeRetryReplay(
  value: unknown,
  request: PendingEnvelope,
  originalAttemptIds: readonly string[]
): RetryReplay {
  if (!value || typeof value !== 'object')
    throw new Error('Invalid retained retry reply');
  const replay = value as RetryReplay;
  if (
    !replay.attempt ||
    typeof replay.attempt.id !== 'string' ||
    !replay.attempt.id ||
    originalAttemptIds.includes(replay.attempt.id) ||
    !sameJson(decodePendingEnvelope(replay.attempt.request), request)
  )
    throw new Error(
      'Retained retry does not match the original frozen request'
    );
  const receipt = replay.receipt;
  if (
    !receipt ||
    receipt.schema_version !== 1 ||
    typeof receipt.command_id !== 'string' ||
    !receipt.command_id ||
    !Array.isArray(receipt.saved_records) ||
    !receipt.saved_records.length ||
    receipt.saved_records.length > 20 ||
    !receipt.saved_records.every(
      (row) =>
        isOperatorInput(row) &&
        typeof row.record_id === 'string' &&
        Number.isInteger(row.version) &&
        row.version > 0 &&
        row.command_id === receipt.command_id &&
        row.provenance?.source_mode === 'simulation'
    ) ||
    !receipt.saved_records.some((row) => principalMatches(request, row))
  )
    throw new Error('Retained receipt does not confirm this command');
  return replay;
}
