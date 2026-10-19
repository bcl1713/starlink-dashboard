import { expect, it } from 'vitest';
import { runningStatus } from '@/test/simulation-run-fixtures';
import { eventSnapshot } from '@/test/operator-event-fixtures';
import { record } from '@/test/operator-fixtures';
import {
  retainJournalObservation,
  collectJournalContinuityEvidence,
} from './trainingJournalEvidence';

const identity = {
  origin: 'http://localhost:56533',
  fixtureVersion: 1,
  storeId: 'store',
  epoch: 'epoch-a',
  missionId: 'mission-1',
};
const namespace = 'operator-training-v1-cc098a03-573a-4a89-ad78-167690ba631e';
const legs = [
  { id: 'leg-1', route_id: 'route-1' },
  { id: 'leg-2', route_id: 'route-2' },
];
const status = runningStatus();
const snapshot = eventSnapshot({
  mission_id: identity.missionId,
  source_mode: 'simulation',
  simulation_run_id: namespace,
  as_of: status.served_at,
  H: 10,
});
const saved = {
  ...record,
  mission_id: identity.missionId,
  journal_seq: 9,
  provenance: { ...record.provenance, source_mode: 'simulation' as const },
};
const second = {
  ...status,
  run: {
    ...status.run!,
    run_id: 'second-run',
    started_at: status.served_at,
    leg_id: 'leg-2',
    route_id: 'route-2',
  },
};
const read = (values: unknown, records = [saved], H = 10) =>
  collectJournalContinuityEvidence(
    identity,
    namespace,
    legs,
    snapshot.as_of,
    H,
    records,
    [],
    values
  );

it('proves continuity from two actual leg reads and a restart from a changed runtime with preserved raw revisions', () => {
  const first = retainJournalObservation(
    identity,
    namespace,
    snapshot,
    status,
    [saved],
    []
  );
  expect(read(first)).toEqual([]);
  const both = retainJournalObservation(
    identity,
    namespace,
    snapshot,
    second,
    [saved],
    first
  );
  expect(read(both)).toEqual(['stable-journal-across-legs']);
  const restarted = {
    ...status,
    runtime_id: 'new-runtime',
    revision: 0,
    state: 'idle' as const,
    run: null,
  };
  const after = retainJournalObservation(
    identity,
    namespace,
    snapshot,
    restarted,
    [saved],
    both
  );
  expect(read(JSON.parse(JSON.stringify(after)))).toEqual(
    expect.arrayContaining([
      'stable-journal-across-legs',
      'restart-preserved-records',
    ])
  );
});

it('requires an unchanged learner revision, complete current history and matching route/context/boundaries', () => {
  const first = retainJournalObservation(
    identity,
    namespace,
    snapshot,
    status,
    [saved],
    []
  );
  const both = retainJournalObservation(
    identity,
    namespace,
    snapshot,
    second,
    [saved],
    first
  );
  expect(read(both, [])).toEqual([]);
  expect(read(both, [{ ...saved, reason: 'contradictory' }])).toEqual([]);
  expect(read(both, [saved], 9)).toEqual([]);
  for (const change of [
    { epoch: 'restored' },
    { storeId: 'foreign' },
    { origin: 'http://foreign' },
  ])
    expect(
      collectJournalContinuityEvidence(
        { ...identity, ...change },
        namespace,
        legs,
        snapshot.as_of,
        10,
        [saved],
        [],
        both
      )
    ).toEqual([]);
  expect(
    collectJournalContinuityEvidence(
      identity,
      namespace,
      [{ ...legs[0], route_id: 'changed' }, legs[1]],
      snapshot.as_of,
      10,
      [saved],
      [],
      both
    )
  ).toEqual([]);
  expect(
    collectJournalContinuityEvidence(
      identity,
      namespace,
      legs,
      snapshot.as_of,
      10,
      [saved],
      [saved.record_id],
      both
    )
  ).toEqual([]);
  expect(
    read([{ passed: true, outcomes: ['restart-preserved-records'] }])
  ).toEqual([]);
});

it('does not infer restart from reload, nor continuity from one repeated run or empty seeded reads', () => {
  const first = retainJournalObservation(
    identity,
    namespace,
    snapshot,
    status,
    [saved],
    []
  );
  expect(
    read(
      retainJournalObservation(
        identity,
        namespace,
        snapshot,
        status,
        [saved],
        first
      )
    )
  ).toEqual([]);
  expect(
    read(
      retainJournalObservation(
        identity,
        namespace,
        snapshot,
        { ...second, run: { ...second.run!, run_id: status.run!.run_id } },
        [saved],
        first
      )
    )
  ).toEqual([]);
  expect(
    read(
      retainJournalObservation(identity, namespace, snapshot, second, [], first)
    )
  ).toEqual([]);
  expect(
    retainJournalObservation(
      identity,
      namespace,
      { ...snapshot, api_epoch: 'foreign' },
      status,
      [saved],
      []
    )
  ).toEqual([]);
});

it('persists only structurally valid raw reads and rejects dropped revisions after a changed runtime', async () => {
  const { createProgress, saveProgress, loadProgress } = await import(
    './trainingProgress'
  );
  const values = new Map<string, string>();
  const storage = {
    getItem: (k: string) => values.get(k) ?? null,
    setItem: (k: string, v: string) => {
      values.set(k, v);
    },
    removeItem: (k: string) => {
      values.delete(k);
    },
  };
  const first = retainJournalObservation(
    identity,
    namespace,
    snapshot,
    status,
    [saved],
    []
  );
  expect(
    saveProgress(storage, {
      ...createProgress(identity),
      journalObservations: first,
    }).error
  ).toBeNull();
  expect(loadProgress(storage, identity).progress?.journalObservations).toEqual(
    first
  );
  const after = retainJournalObservation(
    identity,
    namespace,
    snapshot,
    { ...status, runtime_id: 'new-runtime', state: 'idle', run: null },
    [{ ...saved, record_id: 'different' }],
    first
  );
  expect(
    read(after, [saved, { ...saved, record_id: 'different' }])
  ).not.toContain('restart-preserved-records');
  const [key, text] = [...values.entries()][0];
  const corrupt = JSON.parse(text);
  corrupt.journalObservations[0].source.api_epoch = 'foreign';
  values.set(key, JSON.stringify(corrupt));
  expect(loadProgress(storage, identity).progress).toBeNull();
});
