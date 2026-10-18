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
