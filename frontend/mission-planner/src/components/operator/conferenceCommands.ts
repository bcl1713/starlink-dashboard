import type {
  ConferenceInput,
  ParticipationInput,
  OperatorCommand,
  SavedRecord,
  RecordTime,
} from '@/types/operator';
export type ConferenceAction =
  | 'establish'
  | 'verify'
  | 'interrupt'
  | 'restore_connection'
  | 'close';
export const unknownTime: RecordTime = {
  occurred_at: null,
  ended_at: null,
  precision: 'unknown',
  end_state: 'unknown',
  planned_start_at: null,
  planned_end_at: null,
};
export function conferenceDraft(missionId: string): ConferenceInput {
  return {
    schema_version: 1,
    record_type: 'conference',
    mission_id: missionId,
    scope: 'mission',
    leg_id: null,
    time: { ...unknownTime },
    payload: {
      schema_version: 1,
      entry_type: 'conference',
      title: 'Conference',
      note: '',
      previous_leg_id: null,
      next_leg_id: null,
      status: 'preparing',
      verified_at: null,
      intended_transport: null,
      configured_transport: null,
      configuration_reported_at: null,
      coordinator: null,
    },
  };
}
export function recordInput(
  record: SavedRecord
): ConferenceInput | ParticipationInput {
  const {
    schema_version,
    record_type,
    mission_id,
    scope,
    leg_id,
    time,
    payload,
  } = record;
  if (record_type !== 'conference' && record_type !== 'participation')
    throw new Error('Select a conference or customer');
  return {
    schema_version,
    record_type,
    mission_id,
    scope,
    leg_id,
    time: { ...time },
    payload: { ...payload },
  } as ConferenceInput | ParticipationInput;
}
export function conferenceCommand(
  record: SavedRecord,
  action: ConferenceAction,
  now: string
): OperatorCommand {
  const input = recordInput(record);
  if (input.record_type !== 'conference' || record.deleted)
    throw new Error('Select an active conference');
  const status = input.payload.status;
  if (
    (action === 'verify' && status !== 'established') ||
    (action === 'restore_connection' && status !== 'interrupted') ||
    (action === 'establish' &&
      (status === 'established' || status === 'interrupted')) ||
    (action === 'close' && status === 'closed') ||
    (action === 'interrupt' &&
      (status === 'closed' || status === 'interrupted'))
  )
    throw new Error('Conference state changed; refresh before this action');
  input.time = {
    ...unknownTime,
    occurred_at: now,
    precision: 'exact',
    end_state: 'instant',
  };
  if (action === 'verify') input.payload.verified_at = now;
  else {
    input.payload.status =
      action === 'close'
        ? 'closed'
        : action === 'interrupt'
          ? 'interrupted'
          : 'established';
    input.payload.verified_at = null;
  }
  return {
    operation: 'update',
    record_id: record.record_id,
    body: { ...input, expected_version: record.version },
  };
}
export function joinCommand(
  input: ParticipationInput,
  now: string
): OperatorCommand {
  return {
    operation: 'create',
    body: {
      ...input,
      time: {
        ...unknownTime,
        occurred_at: now,
        precision: 'exact',
        end_state: 'ongoing',
      },
      payload: { ...input.payload, state: 'connected' },
    },
  };
}
export function leaveCommand(
  record: SavedRecord,
  state: 'left' | 'interrupted',
  now: string
): OperatorCommand {
  const input = recordInput(record);
  if (
    input.record_type !== 'participation' ||
    input.payload.state !== 'connected' ||
    record.deleted
  )
    throw new Error('Customer is not currently reported connected');
  input.payload.state = state;
  input.time = input.time.occurred_at
    ? { ...input.time, ended_at: now, end_state: 'known' }
    : { ...unknownTime };
  return {
    operation: 'update',
    record_id: record.record_id,
    body: { ...input, expected_version: record.version },
  };
}
export function resumeCommand(
  record: SavedRecord,
  now: string
): OperatorCommand {
  const input = recordInput(record);
  if (
    input.record_type !== 'participation' ||
    input.payload.state !== 'interrupted' ||
    record.deleted
  )
    throw new Error('Select an interrupted customer connection');
  input.payload.resumes_participation_id = record.record_id;
  return joinCommand(input, now);
}
