import type { SavedRecord } from '@/types/operator';
import type { EventSnapshot } from '@/types/operatorEvents';
import {
  parseSimulationRun,
  type SimulationRunStatus,
} from '@/services/simulation-run';
import type { TrainingIdentity } from './trainingProgress';
import { trainingSourceSchema } from './trainingReplayEvidence';
import { sameJson } from './trainingRecordIdentity';

export interface JournalObservation {
  origin: string;
  fixtureVersion: number;
  source: ReturnType<typeof trainingSourceSchema.parse>;
  status: SimulationRunStatus;
  records: SavedRecord[];
}
/** Raw bounded reads, revalidated against the current complete backend history. */
export function decodeJournalObservation(
  value: unknown,
  identity: TrainingIdentity,
  namespace?: string
): JournalObservation {
  if (!value || typeof value !== 'object')
    throw new Error('Invalid journal observation');
  const raw = value as JournalObservation;
  const source = trainingSourceSchema.parse(raw.source);
  const status = parseSimulationRun(raw.status);
  if (
    raw.origin !== identity.origin ||
    raw.fixtureVersion !== identity.fixtureVersion ||
    source.store_id !== identity.storeId ||
    source.api_epoch !== identity.epoch ||
    source.mission_id !== identity.missionId ||
    (namespace !== undefined && source.simulation_run_id !== namespace) ||
    status.service_mode !== 'simulation' ||
    Date.parse(status.served_at) !== Date.parse(source.as_of) ||
    (status.run &&
      (status.run.mission_id !== identity.missionId ||
        Date.parse(status.run.started_at) > Date.parse(source.as_of))) ||
    !Array.isArray(raw.records) ||
    raw.records.length > 1000 ||
    !raw.records.every(
      (row) =>
        row &&
        row.mission_id === identity.missionId &&
        row.provenance?.source_mode === 'simulation' &&
        typeof row.record_id === 'string' &&
        row.record_id.length > 0 &&
        Number.isInteger(row.version) &&
        row.version > 0 &&
        Number.isInteger(row.journal_seq) &&
        row.journal_seq > 0 &&
        row.journal_seq <= source.H
    ) ||
    new Set(raw.records.map((row) => `${row.record_id}:${row.version}`))
      .size !== raw.records.length
  )
    throw new Error('Journal read does not match this private mission');
  return {
    origin: raw.origin,
    fixtureVersion: raw.fixtureVersion,
    source,
    status,
    records: raw.records,
  };
}

export function retainJournalObservation(
  identity: TrainingIdentity,
  namespace: string,
  snapshot: EventSnapshot,
  status: SimulationRunStatus,
  records: readonly SavedRecord[],
  previous: readonly JournalObservation[]
): JournalObservation[] {
  const retained: JournalObservation[] = [];
  function keep(value: unknown) {
    try {
      const read = decodeJournalObservation(value, identity, namespace);
      if (!read.records.length) return;
      // First read per leg/runtime preserves an earlier boundary across later edits.
      if (
        !retained.some(
          (other) =>
            other.status.runtime_id === read.status.runtime_id &&
            other.status.run?.leg_id === read.status.run?.leg_id
        )
      )
        retained.push(read);
    } catch {
      /* Incomplete or foreign reads cannot establish preservation. */
    }
  }
  previous.slice(-4).forEach(keep);
  const unique = [
    ...new Map(
      records.map((row) => [`${row.record_id}:${row.version}`, row])
    ).values(),
  ];
  keep({
    origin: identity.origin,
    fixtureVersion: identity.fixtureVersion,
    source: snapshot,
    status,
    records: unique,
  });
  // Keep the first boundary for each of the private mission's two legs.
  // Later idle/restart reads must not evict the evidence of the earlier flight.
  const legs = new Map<string, JournalObservation>();
  for (const read of retained) {
    const run = read.status.run;
    if (
      run &&
      ['running', 'completed'].includes(read.status.state) &&
      !legs.has(run.leg_id) &&
      legs.size < 2
    )
      legs.set(run.leg_id, read);
  }
  const boundaries = [...legs.values()];
  const later = retained.filter((read) => !boundaries.includes(read));
  const selected = new Set([
    ...boundaries,
    ...later.slice(-(4 - boundaries.length)),
  ]);
  return retained.filter((read) => selected.has(read));
}

export function collectJournalContinuityEvidence(
  identity: TrainingIdentity,
  namespace: string,
  legs: readonly { id: string; route_id: string }[],
  asOf: string,
  H: number,
  records: readonly SavedRecord[],
  prerequisiteIds: readonly string[],
  values: unknown
): string[] {
  if (
    !Array.isArray(values) ||
    values.length > 4 ||
    !Number.isInteger(H) ||
    H < 0 ||
    !Number.isFinite(Date.parse(asOf))
  )
    return [];
  const reads: JournalObservation[] = [];
  for (const value of values) {
    try {
      const read = decodeJournalObservation(value, identity, namespace);
      if (
        read.source.H <= H &&
        Date.parse(read.source.as_of) <= Date.parse(asOf) &&
        read.records.length &&
        read.records.every((row) =>
          records.some((current) => sameJson(current, row))
        )
      )
        reads.push(read);
    } catch {
      /* Persisted completion flags and foreign facts are never evidence. */
    }
  }
  const learnerRows = (read: JournalObservation) =>
    read.records.filter(
      (row) => !prerequisiteIds.includes(row.record_id) || row.version > 1
    );
  const ordered = (a: JournalObservation, b: JournalObservation) =>
    a.source.H <= b.source.H &&
    Date.parse(a.source.as_of) <= Date.parse(b.source.as_of);
  const leg = (read: JournalObservation, index: number) => {
    const run = read.status.run;
    return (
      !!run &&
      ['running', 'completed'].includes(read.status.state) &&
      run.leg_id === legs[index]?.id &&
      run.route_id === legs[index]?.route_id
    );
  };
  const outcomes: string[] = [];
  if (
    reads.some(
      (first) =>
        leg(first, 0) &&
        reads.some(
          (second) =>
            leg(second, 1) &&
            ordered(first, second) &&
            first.status.run!.run_id !== second.status.run!.run_id &&
            Date.parse(first.source.as_of) <=
              Date.parse(second.status.run!.started_at) &&
            learnerRows(first).some((row) =>
              second.records.some((saved) => sameJson(row, saved))
            )
        )
    )
  )
    outcomes.push('stable-journal-across-legs');
  if (
    reads.some(
      (before) =>
        learnerRows(before).length > 0 &&
        reads.some(
          (after) =>
            before.status.runtime_id !== after.status.runtime_id &&
            ordered(before, after) &&
            before.records.every((row) =>
              after.records.some((saved) => sameJson(row, saved))
            )
        )
    )
  )
    outcomes.push('restart-preserved-records');
  return outcomes;
}
