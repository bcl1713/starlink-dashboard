import type {
  OperatorCommand,
  SavedRecord,
  JournalInput,
} from '@/types/operator';
import { callDraft } from './callDraft';
import { unknownTime } from './conferenceCommands';
export type CallAction = 'start' | 'test' | 'finish' | 'cancel' | 'connect';
const reference = (record: SavedRecord) =>
  `Call record: ${record.record_id}\nOperator-reported call test; bridge verification is separate.`;
export function callTestReported(call: SavedRecord, records: SavedRecord[]) {
  return records.some(
    (r) =>
      !r.deleted &&
      r.mission_id === call.mission_id &&
      r.payload.entry_type === 'call_observation' &&
      r.payload.note === reference(call)
  );
}
export function callCommand(
  record: SavedRecord,
  intent: Exclude<CallAction, 'connect'>,
  now: string
): OperatorCommand {
  const input = callDraft(record, 'planned', record.mission_id);
  if (
    record.deleted ||
    ['completed', 'cancelled'].includes(input.payload.status)
  )
    throw new Error('This call is no longer active.');
  if (intent === 'test') {
    if (!input.time.occurred_at)
      throw new Error('Start the call before reporting its test.');
    const observation: JournalInput = {
      schema_version: 1,
      record_type: 'journal_entry',
      mission_id: record.mission_id,
      scope: record.scope,
      leg_id: record.leg_id,
      time: {
        ...unknownTime,
        occurred_at: now,
        precision: 'exact',
        end_state: 'instant',
      },
      payload: {
        schema_version: 1,
        entry_type: 'call_observation',
        title:
          `Call tested · ${input.payload.party ?? input.payload.title}`.slice(
            0,
            200
          ),
        note: reference(record),
        previous_leg_id: input.payload.previous_leg_id,
        next_leg_id: input.payload.next_leg_id,
      },
    };
    return { operation: 'create', body: observation };
  }
  if (intent === 'start') {
    if (input.time.occurred_at)
      throw new Error('This call has already started.');
    input.time = {
      ...input.time,
      occurred_at: now,
      precision: 'exact',
      end_state: 'ongoing',
    };
  } else if (intent === 'finish') {
    if (
      !input.time.occurred_at ||
      Date.parse(now) < Date.parse(input.time.occurred_at)
    )
      throw new Error('A valid actual start is required before finishing.');
    input.time = { ...input.time, ended_at: now, end_state: 'known' };
    input.payload.status = 'completed';
  } else input.payload.status = 'cancelled';
  return {
    operation: 'update',
    record_id: record.record_id,
    body: { ...input, expected_version: record.version },
  };
}
