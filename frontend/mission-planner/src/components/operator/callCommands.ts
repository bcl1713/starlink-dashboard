import type {
  OperatorCommand,
  SavedRecord,
  JournalInput,
} from '@/types/operator';
import { callDraft } from './callDraft';
import { unknownTime } from './conferenceCommands';
export type CallAction =
  | 'establish'
  | 'start'
  | 'test'
  | 'finish'
  | 'cancel'
  | 'connect';
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
  if (intent === 'establish') {
    if (input.payload.conference_id)
      throw new Error(
        'Establish the associated conference before connecting this customer.'
      );
    input.payload.established_at = now;
    if (!input.time.occurred_at)
      input.time = {
        ...input.time,
        occurred_at: now,
        precision: 'exact',
        end_state: 'ongoing',
      };
  } else if (intent === 'start') {
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
    body: {
      ...input,
      expected_version: record.version,
      ...(intent === 'establish' ? { establish_session: true } : {}),
    },
  };
}

/** Readiness is reported evidence, never inferred from a selected transport. */
export function customerConnectionReady(
  call: SavedRecord,
  records: SavedRecord[],
  isSessionCurrent: (record: SavedRecord) => boolean = () => true
): boolean {
  if (
    call.deleted ||
    call.payload.entry_type !== 'call' ||
    ['completed', 'cancelled'].includes(call.payload.status)
  )
    return false;
  if (!call.payload.conference_id)
    return (
      !!call.payload.established_at &&
      Number.isFinite(Date.parse(call.payload.established_at)) &&
      isSessionCurrent(call)
    );
  const conferenceId = call.payload.conference_id;
  const bridge = records.find(
    (r) => r.record_id === conferenceId && r.mission_id === call.mission_id
  );
  return (
    !!bridge &&
    !bridge.deleted &&
    bridge.payload.entry_type === 'conference' &&
    bridge.payload.status === 'established' &&
    !!bridge.payload.verified_at &&
    isSessionCurrent(bridge)
  );
}

/** Future requirements do not consume a bridge until actual activity begins. */
export function conferenceCloseBlockers(
  conference: SavedRecord,
  records: SavedRecord[]
): SavedRecord[] {
  const associatedCalls = records.filter(
    (r) =>
      !r.deleted &&
      r.mission_id === conference.mission_id &&
      r.payload.entry_type === 'call' &&
      r.payload.conference_id === conference.record_id
  );
  const callIds = new Set(associatedCalls.map((r) => r.record_id));
  return records.filter((r) => {
    if (r.deleted || r.mission_id !== conference.mission_id) return false;
    if (r.payload.entry_type === 'call')
      return (
        callIds.has(r.record_id) &&
        !!r.time.occurred_at &&
        !r.time.ended_at &&
        !['completed', 'cancelled'].includes(r.payload.status)
      );
    if (
      r.payload.entry_type !== 'participation' ||
      (r.payload.conference_id !== conference.record_id &&
        !callIds.has(r.payload.call_id ?? ''))
    )
      return false;
    return (
      r.payload.state !== 'left' &&
      (r.payload.state !== 'interrupted' ||
        !r.time.ended_at ||
        r.time.end_state !== 'known')
    );
  });
}
