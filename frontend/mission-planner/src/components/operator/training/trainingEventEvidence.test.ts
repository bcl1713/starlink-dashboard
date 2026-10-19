import { expect, it } from 'vitest';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
import { collectEventEvidence } from './trainingEventEvidence';
const identity = {
  origin: 'http://localhost',
  fixtureVersion: 1,
  storeId: 'store',
  epoch: 'epoch-a',
  missionId: 'mission-a',
};
const snapshot = eventSnapshot({
  source_mode: 'simulation',
  simulation_run_id: 'private-training',
  events: [
    eventFixture({ state: 'overdue' }),
    eventFixture({
      event_id: 'future',
      state: 'upcoming',
      due_at: '2026-10-17T17:00:00Z',
    }),
  ],
});
const source = {
  identity,
  namespace: 'private-training',
  snapshot,
  receivedAt: 1000,
  browserNow: 1500,
  activeLegId: 'leg-one',
  activeModelIdentity: null,
};
it('reads future plus overdue independently and rejects wrong-context or incomplete event snapshots', () => {
  expect(collectEventEvidence(source).outcomes).toContain(
    'future-next-with-overdue'
  );
  for (const changed of [
    { ...snapshot, store_id: 'other' },
    { ...snapshot, api_epoch: 'other' },
    { ...snapshot, mission_id: 'other' },
    { ...snapshot, simulation_run_id: 'other' },
    { ...snapshot, truncated: true },
    { ...snapshot, cursor: 'more' },
  ])
    expect(
      collectEventEvidence({ ...source, snapshot: changed }).available
    ).toBe(false);
  expect(collectEventEvidence({ ...source, browserNow: 32000 }).fresh).toBe(
    false
  );
});
it('acknowledgment requires the current backend occurrence and reported timestamp', () => {
  expect(collectEventEvidence(source).outcomes).not.toContain(
    'event-acknowledged'
  );
  const acknowledged = eventFixture();
  acknowledged.notification.acknowledged = true;
  acknowledged.notification.acknowledged_at = '2026-10-17T16:00:00Z';
  expect(
    collectEventEvidence({
      ...source,
      snapshot: { ...snapshot, events: [acknowledged] },
    }).outcomes
  ).toContain('event-acknowledged');
});
it('requires fresh aligned source identity rather than treating unknown inputs as a clear model', () => {
  const capture = {
    source: 'model:leg-one',
    revision: '1',
    generation: '1',
    input_identity: 'active-leg-inputs',
    captured_at: snapshot.as_of,
    freshness: 'fresh' as const,
    aligned: true,
    guardable: true,
    reason: null,
  };
  const current = {
    ...source,
    activeModelIdentity: capture.input_identity,
    snapshot: { ...snapshot, sources: [capture] },
  };
  expect(collectEventEvidence(current).outcomes).toContain(
    'current-model-sources'
  );
  for (const changed of [
    { ...capture, freshness: 'unknown' as const },
    { ...capture, aligned: false },
    { ...capture, input_identity: 'prior-leg' },
  ])
    expect(
      collectEventEvidence({
        ...current,
        snapshot: { ...snapshot, sources: [changed] },
      }).outcomes
    ).not.toContain('current-model-sources');
});
it('pins replay evidence to the actual mission leg, route and served source time', async () => {
  const { collectReplayEvidence } = await import('./trainingEventEvidence');
  const { runningStatus } = await import('@/test/simulation-run-fixtures');
  const status = runningStatus();
  const legs = [
    { id: 'leg-1', route_id: 'route-1' },
    { id: 'leg-2', route_id: 'route-2' },
  ];
  const feed = eventSnapshot({
    mission_id: 'mission-1',
    source_mode: 'simulation',
    as_of: status.served_at,
    sources: [
      {
        source: 'model:leg-1',
        revision: '1',
        generation: '1',
        input_identity: 'current-inputs',
        captured_at: status.served_at,
        freshness: 'fresh',
        aligned: true,
        guardable: true,
        reason: null,
      },
    ],
  });
  expect(collectReplayEvidence(feed, status, legs)).toEqual(
    expect.arrayContaining(['first-leg-replay', 'current-model-sources'])
  );
  expect(
    collectReplayEvidence(
      { ...feed, as_of: '2026-10-04T23:58:00Z' },
      status,
      legs
    )
  ).not.toContain('current-model-sources');
  expect(
    collectReplayEvidence(feed, status, [
      { id: 'leg-1', route_id: 'prior-route' },
    ])
  ).not.toContain('first-leg-replay');
  expect(
    collectReplayEvidence({ ...feed, mission_id: 'other' }, status, legs)
  ).toEqual([]);
});

it('credits an explicit unavailable active-leg model read without inferring an outage or aligned inputs', async () => {
  const { collectReplayEvidence } = await import('./trainingEventEvidence');
  const { runningStatus } = await import('@/test/simulation-run-fixtures');
  const status = runningStatus();
  const legs = [{ id: 'leg-1', route_id: 'route-1' }];
  const unavailable = {
    source: 'model:leg-1:live-pop',
    revision: null,
    generation: null,
    input_identity: null,
    captured_at: null,
    freshness: 'unknown' as const,
    aligned: false,
    guardable: false,
    reason: 'Live timing unavailable',
  };
  const feed = eventSnapshot({
    mission_id: 'mission-1',
    source_mode: 'simulation',
    as_of: status.served_at,
    sources: [unavailable],
  });
  expect(collectReplayEvidence(feed, status, legs)).toContain(
    'unavailable-model-inputs'
  );
  expect(collectReplayEvidence(feed, status, legs)).not.toContain(
    'current-model-sources'
  );
  for (const sources of [
    [],
    [{ ...unavailable, source: 'model:other:live-pop' }],
    [{ ...unavailable, reason: null }],
    [{ ...unavailable, captured_at: '2099-01-01T00:00:00Z' }],
  ])
    expect(
      collectReplayEvidence({ ...feed, sources }, status, legs)
    ).not.toContain('unavailable-model-inputs');
  expect(
    collectReplayEvidence(
      { ...feed, as_of: '2020-01-01T00:00:00Z' },
      status,
      legs
    )
  ).not.toContain('unavailable-model-inputs');
});
