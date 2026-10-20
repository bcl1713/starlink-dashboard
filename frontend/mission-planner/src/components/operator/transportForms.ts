import { createClientId } from '@/lib/clientId';
import type { OperatorCommand, SavedRecord } from '@/types/operator';
import type {
  TransportChangeReport,
  TransportDraft,
  TransportServiceRow,
} from '@/types/operatorTransport';
import { unknownTime } from './issueForms';

export const emptyReportTime = () => ({
  at: null,
  precision: 'unknown' as const,
});
export function newServiceRow(): TransportServiceRow {
  return {
    row_id: createClientId(),
    service: '',
    intended: null,
    requested: null,
    applied: null,
    checked: null,
  };
}
export function newTransportDraft(
  missionId: string,
  current?: SavedRecord
): TransportDraft {
  if (current?.payload.entry_type === 'transport_decision')
    return {
      input: {
        schema_version: 1,
        record_type: 'transport_decision',
        mission_id: current.mission_id,
        scope: current.scope,
        leg_id: current.leg_id,
        time: { ...current.time },
        payload: structuredClone(current.payload),
      },
      replacement_check_row_ids: [],
    };
  return {
    input: {
      schema_version: 1,
      record_type: 'transport_decision',
      mission_id: missionId,
      scope: 'mission',
      leg_id: null,
      time: { ...unknownTime },
      payload: {
        schema_version: 1,
        entry_type: 'transport_decision',
        title: '',
        note: '',
        previous_leg_id: null,
        next_leg_id: null,
        reason: '',
        call_id: null,
        conference_id: null,
        services: [newServiceRow()],
      },
    },
    replacement_check_row_ids: [],
  };
}
export function replaceApplication(
  row: TransportServiceRow,
  applied: TransportChangeReport | null
): TransportServiceRow {
  return JSON.stringify(row.applied) === JSON.stringify(applied)
    ? { ...row, applied }
    : { ...row, applied, checked: null };
}
export function toTransportCommand(
  draft: TransportDraft,
  current?: SavedRecord
): Extract<OperatorCommand, { operation: 'create' | 'update' }> {
  const input = structuredClone(draft.input);
  const services = input.payload.services;
  if (services.length < 1 || services.length > 32)
    throw new Error('Use 1–32 services.');
  if (new Set(services.map((s) => s.row_id)).size !== services.length)
    throw new Error('Duplicate service rows.');
  const validUtc = (v: string | null) =>
    v === null ||
    (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(v) &&
      Number.isFinite(Date.parse(v)));
  for (const s of services) {
    s.service = s.service.trim();
    if (!s.service || s.service.length > 200)
      throw new Error('Service must contain 1–200 characters.');
    for (const r of [s.requested, s.applied, s.checked]) {
      if (
        r &&
        (!validUtc(r.time.at) ||
          (r.time.at === null) !== (r.time.precision === 'unknown'))
      )
        throw new Error(
          'Enter a complete UTC report time or leave it unknown.'
        );
    }
  }
  for (const v of [
    input.time.planned_start_at,
    input.time.planned_end_at,
    input.time.occurred_at,
    input.time.ended_at,
  ])
    if (!validUtc(v)) throw new Error('Enter a complete UTC time.');
  if (
    input.time.planned_end_at &&
    (!input.time.planned_start_at ||
      Date.parse(input.time.planned_end_at) <
        Date.parse(input.time.planned_start_at))
  )
    throw new Error('Planned end must follow start.');
  if (input.payload.reason.length > 1000 || input.payload.note.length > 8000)
    throw new Error('Reason or note exceeds its limit.');
  input.payload.title = services
    .map((s) => s.service)
    .join(', ')
    .slice(0, 200);
  return current
    ? {
        operation: 'update',
        record_id: current.record_id,
        body: {
          ...input,
          expected_version: current.version,
          replacement_check_row_ids: draft.replacement_check_row_ids,
        },
      }
    : { operation: 'create', body: input };
}
