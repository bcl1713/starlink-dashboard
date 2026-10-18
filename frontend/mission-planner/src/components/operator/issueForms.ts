import { revisionUtc } from './revisionUtc';
import type { IssueInput, SavedRecord, RecordTime } from '@/types/operator';
export const issueButton =
  'min-h-11 rounded-md border px-3 disabled:opacity-50';
export const issueField =
  'min-h-11 w-full min-w-0 rounded-md border bg-background px-3 py-2';
export const unknownTime: RecordTime = {
  occurred_at: null,
  ended_at: null,
  precision: 'unknown',
  end_state: 'unknown',
  planned_start_at: null,
  planned_end_at: null,
};
export function instant(time: string | null): RecordTime {
  return time
    ? {
        ...unknownTime,
        occurred_at: time,
        precision: 'exact',
        end_state: 'instant',
      }
    : { ...unknownTime };
}
export function utcValue(value: string | null | undefined) {
  return value?.slice(0, 19) ?? '';
}
export function parseUtc(value: string) {
  return value ? new Date(value + 'Z').toISOString() : null;
}
export function issueInput(
  missionId: string,
  record?: SavedRecord
): IssueInput {
  if (record?.payload.entry_type === 'issue')
    return {
      schema_version: 1,
      record_type: 'issue',
      mission_id: record.mission_id,
      scope: record.scope,
      leg_id: record.leg_id,
      time: record.time,
      payload: {
        ...record.payload,
        update_text: '',
        corrects_version: null,
        corrected_update_at: null,
      },
    };
  return {
    schema_version: 1,
    record_type: 'issue',
    mission_id: missionId,
    scope: 'mission',
    leg_id: null,
    time: { ...unknownTime },
    payload: {
      schema_version: 1,
      entry_type: 'issue',
      title: '',
      note: '',
      previous_leg_id: null,
      next_leg_id: null,
      status: 'open',
      priority: null,
      mitigation: 'unknown',
      functional_area: null,
      responsible_party: null,
      follow_up_at: null,
      update_text: '',
      capability_id: null,
      call_id: null,
      conference_id: null,
      transport: null,
      corrects_version: null,
      corrected_update_at: null,
    },
  };
}

export const operatorUtc = (value: string | null | undefined) =>
  revisionUtc(value ?? null);
