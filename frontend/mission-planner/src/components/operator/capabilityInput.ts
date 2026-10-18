import type { CapabilityInput, SavedRecord } from '@/types/operator';
import { unknownTime } from './issueForms';
export function capabilityInput(
  missionId: string,
  record?: SavedRecord
): CapabilityInput {
  return {
    schema_version: 1,
    record_type: 'journal_entry',
    mission_id: missionId,
    scope: record?.scope ?? 'mission',
    leg_id: record?.leg_id ?? null,
    time: record?.time ?? { ...unknownTime },
    payload:
      record?.payload.entry_type === 'capability_assessment'
        ? record.payload
        : {
            schema_version: 1,
            entry_type: 'capability_assessment',
            title: '',
            note: '',
            previous_leg_id: null,
            next_leg_id: null,
            functional_status: 'unknown',
            redundancy_status: 'unknown',
            functional_observed_at: null,
            redundancy_observed_at: null,
            functional_time_precision: 'unknown',
            redundancy_time_precision: 'unknown',
          },
  };
}
