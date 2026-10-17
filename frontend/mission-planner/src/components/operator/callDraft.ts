import type { CallInput, SavedRecord } from '@/types/operator';
export function callDraft(
  record: SavedRecord | undefined,
  mode: 'planned' | 'retrospective',
  missionId: string
): CallInput {
  if (record) {
    if (record.payload.entry_type !== 'call')
      throw new Error('Select a call record.');
    return {
      schema_version: 1,
      record_type: 'call',
      mission_id: record.mission_id,
      leg_id: record.leg_id,
      scope: record.scope,
      time: { ...record.time },
      payload: {
        ...record.payload,
        prep_lead_minutes: record.payload.prep_lead_minutes ?? null,
      },
    };
  }
  return {
    schema_version: 1,
    record_type: 'call',
    mission_id: missionId,
    leg_id: null,
    scope: 'mission',
    time: {
      occurred_at: null,
      ended_at: null,
      precision: 'unknown',
      end_state: 'unknown',
      planned_start_at: null,
      planned_end_at: null,
    },
    payload: {
      schema_version: 1,
      entry_type: 'call',
      title: mode === 'planned' ? 'Planned call' : 'Unscheduled call',
      note: '',
      previous_leg_id: null,
      next_leg_id: null,
      status: mode === 'planned' ? 'scheduled' : 'completed',
      conference_id: null,
      party: null,
      coordinator: null,
      communications_kind: null,
      prep_lead_minutes: mode === 'planned' ? 10 : null,
    },
  };
}
