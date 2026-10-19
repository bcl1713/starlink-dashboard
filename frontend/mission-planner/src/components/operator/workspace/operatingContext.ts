import type {
  OperatorHealth,
  OperatorInput,
  SavedRecord,
} from '@/types/operator';
import type { CallAssociation } from '../callAssociation';

export interface OperatingContext {
  state: string;
  mission_id: string | null;
  mission_name: string | null;
  leg_id: string | null;
  leg_name: string | null;
  phase: string | null;
  source_mode: 'live' | 'simulation';
  replay_run_id: string | null;
  operating_context_id?: string | null;
}

export function operatingMission(
  manual: string | null,
  active?: Pick<OperatingContext, 'mission_id'>
) {
  return manual ?? active?.mission_id ?? '';
}

/** Apply once, before the durable draft is created. Never retarget an editor. */
export function defaultAssociation<T extends OperatorInput>(
  input: T,
  association: CallAssociation | null,
  existing: boolean
): T {
  if (existing || !association) return input;
  return {
    ...input,
    scope: association.scope,
    leg_id: association.leg_id,
    payload: {
      ...input.payload,
      previous_leg_id: association.previous_leg_id,
      next_leg_id: association.next_leg_id,
    },
  };
}

export function replayCurrent(record: SavedRecord, health?: OperatorHealth) {
  return (
    !health?.mission_journal ||
    (health.operating_context_id != null
      ? record.provenance.operating_context_id === health.operating_context_id
      : !!health.replay_run_id &&
        record.provenance.replay_run_id === health.replay_run_id)
  );
}

export function activeAssociation(
  context: OperatingContext | undefined,
  mission: { id: string; legs: { id: string; name: string }[] } | undefined
): CallAssociation | null {
  if (
    !context?.leg_id ||
    context.state !== 'available' ||
    (mission !== undefined && context.mission_id !== mission.id)
  )
    return null;
  const legs = mission?.legs ?? [];
  const index = legs.findIndex((leg) => leg.id === context.leg_id);
  const association: CallAssociation = {
    scope: 'leg',
    leg_id: context.leg_id,
    previous_leg_id: null,
    next_leg_id: null,
    label: context.leg_name ?? legs[index]?.name ?? 'Active leg',
  };
  if (index < 0) return association;
  if (context.phase === 'pre_departure') {
    return index === 0
      ? { ...association, scope: 'preflight', leg_id: null, label: 'Preflight' }
      : {
          ...association,
          scope: 'between_legs',
          leg_id: null,
          previous_leg_id: legs[index - 1].id,
          next_leg_id: context.leg_id,
          label: `Before ${association.label}`,
        };
  }
  if (context.phase === 'post_arrival') {
    return index === legs.length - 1
      ? {
          ...association,
          scope: 'postflight',
          leg_id: null,
          label: 'Postflight',
        }
      : {
          ...association,
          scope: 'between_legs',
          leg_id: null,
          previous_leg_id: context.leg_id,
          next_leg_id: legs[index + 1].id,
          label: `After ${association.label}`,
        };
  }
  return association;
}

/** An unfinished requirement is durable; a connection/check is replay evidence. */
export function operationalRelevant(
  record: SavedRecord,
  health?: OperatorHealth
) {
  return (
    replayCurrent(record, health) ||
    (!record.deleted &&
      (record.payload.entry_type === 'conference' ||
        (record.payload.entry_type === 'call' &&
          record.time.occurred_at === null &&
          ['tentative', 'scheduled', 'delayed'].includes(
            record.payload.status
          )) ||
        (record.payload.entry_type === 'issue' &&
          record.payload.status !== 'resolved')))
  );
}
