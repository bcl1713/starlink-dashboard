import { expect, it } from 'vitest';
import { input, record } from '@/test/operator-fixtures';
import type { DraftEnvelope } from '../workspace/types';
import {
  collectClientEvidence,
  decodeClientObservation,
} from './trainingClientEvidence';
const identity = {
  origin: 'http://localhost',
  fixtureVersion: 1,
  storeId: 'store',
  epoch: 'epoch-a',
  missionId: 'mission-a',
};
const namespace = 'operator-training-v1-cc098a03-573a-4a89-ad78-167690ba631e';
const draft: DraftEnvelope = {
  schemaVersion: 1,
  draftId: 'draft-a',
  revision: 2,
  baseVersion: null,
  baseRecord: null,
  input,
  persistence: { state: 'durable', message: null },
  target: {
    storeId: 'store',
    epoch: 'epoch-a',
    missionId: 'mission-a',
    sourceMode: 'simulation',
    simulationRunId: namespace,
    recordType: 'journal_entry',
    recordId: null,
    newDraftId: 'draft-a',
    scope: 'mission',
    legId: null,
    previousLegId: null,
    nextLegId: null,
    correctionVersion: null,
  },
};
const observation = (at: number, online = true, drafts = [draft]) => ({
  identity,
  namespace,
  observedAt: at,
  journalH: 0,
  online,
  drafts,
});
const saved = {
  ...record,
  provenance: { ...record.provenance, source_mode: 'simulation' as const },
};
const collect = (values: unknown, records = [saved]) =>
  collectClientEvidence(identity, namespace, 1, records, values, 100);
it('requires an unchanged parked draft while a new different-scope draft appears', () => {
  const second = {
    ...draft,
    draftId: 'draft-b',
    target: {
      ...draft.target,
      newDraftId: 'draft-b',
      scope: 'leg' as const,
      legId: 'leg-two',
    },
    input: { ...input, scope: 'leg' as const, leg_id: 'leg-two' },
  };
  expect(
    collect([observation(1), observation(2, true, [draft, second])])
  ).toContain('draft-switch-retained');
  expect(
    collect([observation(1), observation(2, true, [second])])
  ).not.toContain('draft-switch-retained');
});
it('requires raw offline and reconnected draft reads plus a later matching backend revision', () => {
  const reads = [observation(1, false), observation(2)];
  expect(collect(reads)).toContain('offline-draft-retained');
  expect(collect(reads, [])).not.toContain('offline-draft-retained');
  expect(collect([observation(1), observation(2)])).not.toContain(
    'offline-draft-retained'
  );
  expect(
    collect(reads, [
      { ...saved, payload: { ...saved.payload, note: 'different' } },
    ])
  ).not.toContain('offline-draft-retained');
  expect(
    collect([observation(1, false), { ...observation(2), journalH: 2 }])
  ).not.toContain('offline-draft-retained');
});
it('requires memory-only then durable draft retention and a later real save for storage recovery', () => {
  const failed = {
    ...draft,
    persistence: {
      state: 'memory_only' as const,
      message: 'Storage unavailable',
    },
  };
  const reads = [observation(1, true, [failed]), observation(2)];
  expect(collect(reads)).toContain('storage-unavailable-recovery');
  expect(collect(reads, [])).not.toContain('storage-unavailable-recovery');
});
it('rejects foreign, future, malformed and generic completion flags', () => {
  for (const value of [
    { passed: true },
    { ...observation(1), identity: { ...identity, epoch: 'other' } },
    {
      ...observation(1),
      drafts: [{ ...draft, input: { ...input, mission_id: 'other' } }],
    },
  ])
    expect(() => decodeClientObservation(value, identity, namespace)).toThrow();
  expect(collect([observation(101, false), observation(102)])).toEqual([]);
});
