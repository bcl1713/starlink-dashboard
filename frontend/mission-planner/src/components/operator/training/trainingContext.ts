import type { Mission } from '@/types/mission';
import type { OperatorHealth } from '@/types/operator';
import type { TrainingIdentity } from './trainingProgress';

export function trainingContext(
  health: OperatorHealth | undefined,
  mission: Mission | undefined,
  origin: string
): { identity: TrainingIdentity; prerequisiteIds: string[] } | null {
  if (
    !health?.ready ||
    !health.enabled ||
    !health.store_id ||
    !health.api_epoch ||
    health.source_mode !== 'simulation' ||
    !/^operator-training-v1-[0-9a-f-]{36}$/.test(
      health.simulation_run_id ?? ''
    ) ||
    !mission
  )
    return null;
  const marker = mission.metadata.operator_training_fixture;
  if (!marker || typeof marker !== 'object') return null;
  const value = marker as Record<string, unknown>;
  if (
    value.version !== 1 ||
    value.namespace !== health.simulation_run_id ||
    !Array.isArray(value.prerequisite_record_ids) ||
    !value.prerequisite_record_ids.every((id) => typeof id === 'string' && !!id)
  )
    return null;
  return {
    identity: {
      fixtureVersion: 1,
      origin,
      storeId: health.store_id,
      epoch: health.api_epoch,
      missionId: mission.id,
    },
    prerequisiteIds: [...value.prerequisite_record_ids],
  };
}
