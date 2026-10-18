import type { EventSnapshot } from '@/types/operatorEvents';
import type { TrainingIdentity } from './trainingProgress';
import type { TrainingEvidence } from './trainingSteps';

export function collectEventEvidence(source: {
  identity: TrainingIdentity;
  namespace: string;
  snapshot: EventSnapshot | null;
  receivedAt: number | null;
  browserNow: number;
  activeLegId: string | null;
  activeModelIdentity: string | null;
}): TrainingEvidence {
  const { snapshot, identity } = source;
  const fresh =
    source.receivedAt !== null &&
    source.browserNow >= source.receivedAt &&
    source.browserNow - source.receivedAt < 30_000;
  const available =
    !!snapshot &&
    snapshot.store_id === identity.storeId &&
    snapshot.api_epoch === identity.epoch &&
    snapshot.mission_id === identity.missionId &&
    snapshot.source_mode === 'simulation' &&
    snapshot.simulation_run_id === source.namespace &&
    !snapshot.truncated &&
    !snapshot.cursor;
  if (!available || !snapshot) return { available: false, fresh, outcomes: [] };
  const outcomes = new Set<string>(['private-context-read']);
  const events = snapshot.events.filter(
    (event) => event.mission_id === identity.missionId
  );
  const now = Date.parse(snapshot.as_of);
  if (
    Number.isFinite(now) &&
    events.some((event) => event.state === 'overdue') &&
    events.some(
      (event) =>
        event.kind === 'call_start' &&
        event.due_at &&
        Date.parse(event.due_at) > now &&
        event.state === 'upcoming'
    )
  )
    outcomes.add('future-next-with-overdue');
  if (
    events.some(
      (event) =>
        event.notification.acknowledged &&
        event.notification.acknowledged_at &&
        event.notification.generation &&
        !event.notification.retired
    )
  )
    outcomes.add('event-acknowledged');
  if (events.some((event) => event.discrepancies.length))
    outcomes.add('participation-discrepancy');
  if (
    source.activeLegId &&
    source.activeModelIdentity &&
    snapshot.sources.some(
      (capture) =>
        capture.source === `model:${source.activeLegId}` &&
        capture.input_identity === source.activeModelIdentity &&
        capture.freshness === 'fresh' &&
        capture.aligned &&
        capture.captured_at &&
        Number.isFinite(Date.parse(capture.captured_at))
    )
  )
    outcomes.add('current-model-sources');
  return { available, fresh, outcomes: [...outcomes] };
}

/** Normal replay status is distinct from the fixture's stable journal namespace. */
export function collectReplayEvidence(
  snapshot: EventSnapshot,
  status: import('@/services/simulation-run').SimulationRunStatus,
  legs: readonly { id: string; route_id: string }[]
): string[] {
  const run = status.run;
  if (
    !run ||
    status.service_mode !== 'simulation' ||
    snapshot.source_mode !== 'simulation' ||
    snapshot.mission_id !== run.mission_id ||
    !['running', 'completed'].includes(status.state)
  )
    return [];
  const index = legs.findIndex(
    (leg) => leg.id === run.leg_id && leg.route_id === run.route_id
  );
  if (index < 0) return [];
  const outcomes: string[] =
    index === 0
      ? ['first-leg-replay']
      : index === 1
        ? ['second-leg-replay']
        : [];
  if (
    Date.parse(snapshot.as_of) === Date.parse(status.served_at) &&
    snapshot.sources.some(
      (capture) =>
        capture.source === `model:${run.leg_id}` &&
        capture.aligned &&
        capture.freshness === 'fresh' &&
        !!capture.input_identity &&
        capture.captured_at &&
        Date.parse(capture.captured_at) >= Date.parse(run.started_at) &&
        Date.parse(capture.captured_at) <= Date.parse(status.served_at)
    )
  )
    outcomes.push('current-model-sources');
  return outcomes;
}
