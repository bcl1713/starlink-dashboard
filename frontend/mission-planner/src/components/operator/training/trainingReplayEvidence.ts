import { z } from 'zod';
import {
  parseSimulationRun,
  type SimulationRunStatus,
} from '@/services/simulation-run';
import type { EventSnapshot } from '@/types/operatorEvents';
import type { TrainingIdentity } from './trainingProgress';
import { collectReplayEvidence } from './trainingEventEvidence';

const timestamp = z
  .string()
  .refine((value) => Number.isFinite(Date.parse(value)));
const sourceSchema = z.object({
  schema_version: z.literal(1),
  store_id: z.string().min(1),
  api_epoch: z.string().min(1),
  mission_id: z.string().min(1),
  source_mode: z.literal('simulation'),
  simulation_run_id: z.string().regex(/^operator-training-v1-[0-9a-f-]{36}$/),
  as_of: timestamp,
  H: z.number().int().nonnegative(),
  generation: z.string().min(1),
  snapshot_token: z.string().min(1),
  cursor: z.null(),
  truncated: z.literal(false),
  coverage: z.enum(['available', 'partial', 'unknown']),
  sources: z
    .array(
      z.object({
        source: z.string().min(1),
        revision: z.string().nullable(),
        generation: z.string().nullable(),
        input_identity: z.string().nullable(),
        captured_at: timestamp.nullable(),
        freshness: z.enum(['fresh', 'stale', 'unknown', 'disabled']),
        aligned: z.boolean(),
        guardable: z.boolean(),
        reason: z.string().nullable(),
      })
    )
    .max(100),
});
export interface ReplayObservation {
  origin: string;
  fixtureVersion: number;
  source: z.infer<typeof sourceSchema>;
  status: SimulationRunStatus;
}
type Leg = { id: string; route_id: string };

/** Retained raw read responses prove an earlier exercise, never current availability. */
export function decodeReplayObservation(
  value: unknown,
  identity: TrainingIdentity,
  namespace?: string
): ReplayObservation {
  if (!value || typeof value !== 'object')
    throw new Error('Invalid retained replay observation');
  const raw = value as ReplayObservation;
  const source = sourceSchema.parse(raw.source);
  const status = parseSimulationRun(raw.status);
  if (
    raw.origin !== identity.origin ||
    raw.fixtureVersion !== identity.fixtureVersion ||
    source.store_id !== identity.storeId ||
    source.api_epoch !== identity.epoch ||
    source.mission_id !== identity.missionId ||
    (namespace !== undefined && source.simulation_run_id !== namespace) ||
    status.service_mode !== 'simulation' ||
    !['running', 'completed'].includes(status.state) ||
    !status.run ||
    status.run.mission_id !== identity.missionId ||
    Date.parse(status.served_at) !== Date.parse(source.as_of) ||
    Date.parse(status.run.started_at) > Date.parse(source.as_of)
  )
    throw new Error(
      'Retained replay belongs to another or inconsistent private context'
    );
  return {
    origin: raw.origin,
    fixtureVersion: raw.fixtureVersion,
    source,
    status,
  };
}

export function collectHistoricalReplayEvidence(
  identity: TrainingIdentity,
  namespace: string,
  legs: readonly Leg[],
  asOf: string,
  H: number,
  values: unknown
): string[] {
  if (
    !Array.isArray(values) ||
    values.length > 12 ||
    !Number.isInteger(H) ||
    H < 0 ||
    !Number.isFinite(Date.parse(asOf))
  )
    return [];
  const outcomes = new Set<string>();
  for (const value of values) {
    try {
      const observation = decodeReplayObservation(value, identity, namespace);
      if (
        observation.source.H > H ||
        Date.parse(observation.source.as_of) > Date.parse(asOf)
      )
        continue;
      for (const outcome of collectReplayEvidence(
        observation.source,
        observation.status,
        legs
      ))
        outcomes.add(outcome);
    } catch {
      /* Corrupt or foreign read facts cannot establish an exercise. */
    }
  }
  return [...outcomes];
}

export function retainReplayObservation(
  identity: TrainingIdentity,
  namespace: string,
  legs: readonly Leg[],
  snapshot: EventSnapshot,
  status: SimulationRunStatus,
  previous: readonly ReplayObservation[]
): ReplayObservation[] {
  const retained: ReplayObservation[] = [];
  function keep(raw: unknown) {
    try {
      const observation = decodeReplayObservation(raw, identity, namespace);
      const outcomes = collectReplayEvidence(
        observation.source,
        observation.status,
        legs
      );
      if (!outcomes.length) return;
      // Retain an aligned and an unavailable sample per leg, so later missing
      // inputs cannot erase the earlier real aligned observation.
      const sameKind = (other: ReplayObservation) =>
        other.status.run!.leg_id === observation.status.run!.leg_id &&
        collectReplayEvidence(other.source, other.status, legs).includes(
          'current-model-sources'
        ) === outcomes.includes('current-model-sources');
      const index = retained.findIndex(sameKind);
      if (index >= 0) retained[index] = observation;
      else retained.push(observation);
    } catch {
      /* An unavailable current read never manufactures a milestone. */
    }
  }
  previous.slice(-12).forEach(keep);
  keep({
    origin: identity.origin,
    fixtureVersion: identity.fixtureVersion,
    source: snapshot,
    status,
  });
  return retained.slice(-12);
}
