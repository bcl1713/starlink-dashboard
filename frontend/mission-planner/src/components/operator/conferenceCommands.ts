import type { CallAssociation } from './callAssociation';
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
export function participationDraft(
  missionId: string,
  conferenceId: string | null = null
): ParticipationInput {
  return {
    schema_version: 1,
    record_type: 'participation',
    mission_id: missionId,
    scope: 'mission',
    leg_id: null,
    time: { ...unknownTime },
    payload: {
      schema_version: 1,
      entry_type: 'participation',
      title: 'Unknown customer',
      note: '',
      previous_leg_id: null,
      next_leg_id: null,
      participant: null,
      call_id: null,
      conference_id: conferenceId,
      state: 'connected',
      resumes_participation_id: null,
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
  now: string,
  association?: CallAssociation | null,
  sessionCurrent = true
): OperatorCommand {
  const input = recordInput(record);
  if (input.record_type !== 'conference' || record.deleted)
    throw new Error('Select an active conference');
  const status = input.payload.status;
  const previousSession =
    !sessionCurrent || sessionOutsideContext(record, association);
  if (action !== 'close' && action !== 'establish' && previousSession)
    throw new Error(
      'Establish this conference here before reporting current activity.'
    );
  if (
    (action === 'verify' && status !== 'established') ||
    (action === 'restore_connection' && status !== 'interrupted') ||
    (action === 'establish' &&
      !previousSession &&
      ((status === 'established' && !!input.payload.verified_at) ||
        status === 'interrupted')) ||
    (action === 'close' && status === 'closed') ||
    (action === 'interrupt' &&
      (status === 'closed' || status === 'interrupted'))
  )
    throw new Error('Conference state changed; refresh before this action');
  if (
    action === 'establish' &&
    association &&
    (status !== 'preparing' || !sessionCurrent)
  ) {
    input.scope = association?.scope ?? 'mission';
    input.leg_id = association?.leg_id ?? null;
    input.payload.previous_leg_id = association?.previous_leg_id ?? null;
    input.payload.next_leg_id = association?.next_leg_id ?? null;
  }
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
    input.payload.verified_at = action === 'establish' ? now : null;
  }
  return {
    operation: 'update',
    record_id: record.record_id,
    body: {
      ...input,
      expected_version: record.version,
      ...(action === 'establish' ? { establish_session: true } : {}),
    },
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
  input.connect_customer = true;
  return joinCommand(input, now);
}

/** A report on another leg is historical activity, never current bridge availability. */
export function sessionOutsideContext(
  record: SavedRecord,
  current?: CallAssociation | null
) {
  if (!current) return false;
  if (record.scope === 'mission' || record.scope !== current.scope) return true;
  if (record.scope === 'leg') return current.leg_id !== record.leg_id;
  return (
    record.scope === 'between_legs' &&
    (record.payload.previous_leg_id !== current.previous_leg_id ||
      record.payload.next_leg_id !== current.next_leg_id)
  );
}
