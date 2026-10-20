import { createClientId } from '@/lib/clientId';
import type { SavedRecord } from '@/types/operator';
import type { CallAssociation } from '../callAssociation';
import { newTransportDraft } from '../transportForms';

export function assignmentInput(
  missionId: string,
  service: { id: string; name: string },
  transport: { id: string; name: string },
  now: string,
  association: CallAssociation | null
) {
  const input = newTransportDraft(missionId).input;
  if (association) {
    input.scope = association.scope;
    input.leg_id = association.leg_id;
    input.payload.previous_leg_id = association.previous_leg_id;
    input.payload.next_leg_id = association.next_leg_id;
  }
  input.time = {
    ...input.time,
    occurred_at: now,
    precision: 'exact',
    end_state: 'instant',
  };
  input.payload.title = service.name;
  input.payload.services = [
    {
      row_id: createClientId(),
      service_id: service.id,
      service: service.name,
      intended: null,
      requested: null,
      applied: {
        transport_id: transport.id,
        transport: transport.name,
        time: { at: now, precision: 'exact' },
      },
      checked: null,
    },
  ];
  return input;
}

/** Journal sequence decides recording order; drafts and checks never participate. */
export function latestAssignment(
  records: SavedRecord[],
  service: { id: string; name: string },
  legId: string | null
) {
  for (const record of [...records].sort(
    (a, b) => b.journal_seq - a.journal_seq
  )) {
    if (
      record.deleted ||
      (record.leg_id !== null && record.leg_id !== legId) ||
      record.payload.entry_type !== 'transport_decision'
    )
      continue;
    const row = record.payload.services.find((row) =>
      row.service_id
        ? row.service_id === service.id
        : row.service.toLocaleLowerCase() === service.name.toLocaleLowerCase()
    );
    if (row?.applied) return row.applied;
  }
  return null;
}
