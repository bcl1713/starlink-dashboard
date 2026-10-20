import { expect, it } from 'vitest';
import { runningStatus } from '@/test/simulation-run-fixtures';
import { eventSnapshot } from '@/test/operator-event-fixtures';
import {
  retainReplayObservation,
  collectHistoricalReplayEvidence,
} from './trainingReplayEvidence';
import { createProgress, loadProgress, saveProgress } from './trainingProgress';

const identity = {
  fixtureVersion: 1,
  origin: 'http://localhost:56533',
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
  simulation_run_id: namespace,
  source_mode: 'simulation',
  as_of: status.served_at,
  sources: [
    {
      source: 'model:leg-1',
      revision: '1',
      generation: '1',
      input_identity: 'first-model-inputs',
      captured_at: status.served_at,
      freshness: 'fresh',
      aligned: true,
      guardable: true,
      reason: null,
    },
  ],
});

it('retains actual first and second replay/source observations across serialization and later idle checks', () => {
  const first = retainReplayObservation(
    identity,
    namespace,
    legs,
    snapshot,
    status,
    []
  );
  expect(first).toHaveLength(1);
  const later = {
    ...status,
    run: {
      ...status.run!,
      run_id: 'run-2',
      leg_id: 'leg-2',
      route_id: 'route-2',
    },
  };
  const feed = {
    ...snapshot,
    sources: snapshot.sources.map((source) => ({
      ...source,
      source: 'model:leg-2',
    })),
  };
  const both = retainReplayObservation(
    identity,
    namespace,
    legs,
    feed,
    later,
    first
  );
  expect(both).toHaveLength(2);
  const reloaded = JSON.parse(JSON.stringify(both));
  expect(
    collectHistoricalReplayEvidence(
      identity,
      namespace,
      legs,
      snapshot.as_of,
      snapshot.H,
      reloaded
    )
  ).toEqual(
    expect.arrayContaining([
      'first-leg-replay',
      'second-leg-replay',
      'current-model-sources',
    ])
  );
  const idle = { ...status, state: 'idle' as const, run: null };
  expect(
    retainReplayObservation(identity, namespace, legs, snapshot, idle, reloaded)
  ).toEqual(reloaded);
});

it('never retains another store/epoch/mission/namespace, partial source snapshot or mismatched replay time', () => {
  for (const changed of [
    { ...snapshot, store_id: 'other' },
    { ...snapshot, api_epoch: 'other' },
    { ...snapshot, mission_id: 'other' },
    { ...snapshot, simulation_run_id: 'other' },
    { ...snapshot, truncated: true },
    { ...snapshot, cursor: 'remaining' },
    { ...snapshot, as_of: '2026-10-04T23:58:00Z' },
  ])
    expect(
      retainReplayObservation(identity, namespace, legs, changed, status, [])
    ).toEqual([]);
});

it('rechecks retained raw facts against the current identity, journal boundary and leg route rather than trusting progress flags', () => {
  const first = retainReplayObservation(
    identity,
    namespace,
    legs,
    snapshot,
    status,
    []
  );
  const read = (
    observations: unknown,
    currentIdentity = identity,
    currentLegs = legs,
    H = snapshot.H,
    asOf = snapshot.as_of
  ) =>
    collectHistoricalReplayEvidence(
      currentIdentity,
      namespace,
      currentLegs,
      asOf,
      H,
      observations
    );
  expect(read([{ passed: true, outcomes: ['first-leg-replay'] }])).toEqual([]);
  expect(read(first, { ...identity, epoch: 'restored-epoch' })).toEqual([]);
  expect(
    read(first, identity, [{ ...legs[0], route_id: 'replaced-route' }])
  ).toEqual([]);
  expect(read(first, identity, legs, snapshot.H - 1)).toEqual([]);
  expect(
    read(first, identity, legs, snapshot.H, '2026-10-04T23:58:00Z')
  ).toEqual([]);
});

it('keeps a real replay exercise distinct from missing or stale model inputs', () => {
  const stale = {
    ...snapshot,
    sources: snapshot.sources.map((source) => ({
      ...source,
      freshness: 'stale' as const,
    })),
  };
  const observations = retainReplayObservation(
    identity,
    namespace,
    legs,
    stale,
    status,
    []
  );
  const outcomes = collectHistoricalReplayEvidence(
    identity,
    namespace,
    legs,
    snapshot.as_of,
    snapshot.H,
    observations
  );
  expect(outcomes).toContain('first-leg-replay');
  expect(outcomes).not.toContain('current-model-sources');
  const second = {
    ...status,
    run: { ...status.run!, leg_id: 'leg-2', route_id: 'route-2' },
  };
  const secondFeed = {
    ...snapshot,
    sources: snapshot.sources.map((source) => ({
      ...source,
      source: 'model:leg-2',
    })),
  };
  const both = retainReplayObservation(
    identity,
    namespace,
    legs,
    secondFeed,
    second,
    observations
  );
  const scoped = collectHistoricalReplayEvidence(
    identity,
    namespace,
    legs,
    snapshot.as_of,
    snapshot.H,
    both
  );
  expect(scoped).toContain('second-leg-model-sources');
  expect(scoped).not.toContain('first-leg-model-sources');
});

it('resumes only validated raw observations in the same private progress identity', () => {
  const values = new Map<string, string>();
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
    removeItem: (key: string) => {
      values.delete(key);
    },
  };
  const replayObservations = retainReplayObservation(
    identity,
    namespace,
    legs,
    snapshot,
    status,
    []
  );
  expect(
    saveProgress(storage, { ...createProgress(identity), replayObservations })
      .error
  ).toBeNull();
  expect(loadProgress(storage, identity).progress?.replayObservations).toEqual(
    replayObservations
  );
  const [key, text] = [...values.entries()][0];
  const corrupt = JSON.parse(text);
  corrupt.replayObservations[0].source.api_epoch = 'foreign';
  values.set(key, JSON.stringify(corrupt));
  expect(loadProgress(storage, identity).progress).toBeNull();
  expect(loadProgress(storage, identity).error).toBeTruthy();
});

it('retains an unavailable advisory read even when aligned model inputs remain available', () => {
  const missing = {
    ...snapshot,
    sources: [
      ...snapshot.sources,
      {
        ...snapshot.sources[0],
        source: 'model:leg-1:live-pop',
        freshness: 'unknown' as const,
        aligned: false,
        guardable: false,
        input_identity: null,
        captured_at: null,
        reason: 'Timing unavailable',
      },
    ],
  };
  let reads = retainReplayObservation(
    identity,
    namespace,
    legs,
    missing,
    status,
    []
  );
  reads = retainReplayObservation(
    identity,
    namespace,
    legs,
    snapshot,
    status,
    reads
  );
  expect(
    collectHistoricalReplayEvidence(
      identity,
      namespace,
      legs,
      snapshot.as_of,
      snapshot.H,
      reads
    )
  ).toContain('unavailable-model-inputs');
});
