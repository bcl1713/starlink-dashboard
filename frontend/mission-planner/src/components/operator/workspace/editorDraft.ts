import type {
  OperatorHealth,
  OperatorInput,
  SavedRecord,
} from '@/types/operator';
import type { DraftRegistry } from './draftRegistry';

/** Open the complete editor target/base in its first durable write. */
export function createEditorDraft(
  registry: DraftRegistry,
  source: OperatorHealth,
  input: OperatorInput,
  record?: SavedRecord
) {
  if (!source.enabled || !source.ready || !source.store_id || !source.api_epoch)
    throw new Error('Operator store is not ready for a new editor target.');
  return registry.createDraft(
    {
      storeId: source.store_id,
      epoch: source.api_epoch,
      sourceMode: source.source_mode,
      simulationRunId: source.simulation_run_id,
      missionId: input.mission_id,
      recordType: input.record_type,
      recordId: record?.record_id ?? null,
      newDraftId: null,
      scope: input.scope,
      legId: input.leg_id,
      previousLegId: input.payload.previous_leg_id,
      nextLegId: input.payload.next_leg_id,
      correctionVersion: null,
    },
    input,
    record ?? null
  );
}
