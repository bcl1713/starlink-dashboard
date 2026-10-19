import { expect, it } from 'vitest';
import { input, record } from '@/test/operator-fixtures';
import type { DraftEnvelope } from '../workspace/types';
import {
  collectClientEvidence,
  decodeClientObservation,
  retainClientObservation,
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

it('matches a reported approximate UTC time after normal backend precision canonicalization', () => {
  const short = {
    ...draft,
    input: {
      ...input,
      time: { ...input.time, occurred_at: '2026-10-17T10:11:12Z' },
    },
  };
  const row = {
    ...saved,
    time: { ...saved.time, occurred_at: '2026-10-17T10:11:12.000000Z' },
  };
  expect(
    collect(
      [observation(1, false, [short]), observation(2, true, [short])],
      [row]
    )
  ).toContain('offline-draft-retained');
});

it('keeps all three completed recovery observations through later draft work within the eight-read bound', () => {
  const other = {
    ...draft,
    draftId: 'other',
    target: {
      ...draft.target,
      newDraftId: 'other',
      scope: 'leg' as const,
      legId: 'leg-two',
    },
    input: { ...input, scope: 'leg' as const, leg_id: 'leg-two' },
  };
  const storage = {
    ...draft,
    draftId: 'storage',
    target: { ...draft.target, newDraftId: 'storage' },
    input: {
      ...input,
      payload: { ...input.payload, title: 'Storage retained' },
    },
  };
  const memory = {
    ...storage,
    persistence: {
      state: 'memory_only' as const,
      message: 'Quota unavailable',
    },
  };
  const second = {
    ...saved,
    record_id: 'saved-storage',
    command_id: 'server-storage',
    journal_seq: 2,
    payload: storage.input.payload,
  };
  const backend = [saved, second];
  let reads = [
    observation(1),
    observation(2, true, [draft, other]),
    observation(3, false, [draft, other]),
    observation(4, true, [draft, other]),
    { ...observation(5, true, [other, memory]), journalH: 1 },
    { ...observation(6, true, [other, storage]), journalH: 1 },
    { ...observation(7, true, [other]), journalH: 2 },
  ];
  const expected = [
    'draft-switch-retained',
    'offline-draft-retained',
    'storage-unavailable-recovery',
  ];
  expect(
    collectClientEvidence(identity, namespace, 2, backend, reads, 100)
  ).toEqual(expect.arrayContaining(expected));
  for (let at = 8; at < 20; at++) {
    reads = retainClientObservation(
      identity,
      namespace,
      2,
      true,
      [
        {
          ...other,
          revision: at,
          input: {
            ...other.input,
            payload: {
              ...other.input.payload,
              note: `Later retained work ${at}`,
            },
          },
        },
      ],
      reads,
      at,
      backend
    );
    expect(reads.length).toBeLessThanOrEqual(8);
    expect(
      collectClientEvidence(identity, namespace, 2, backend, reads, 100)
    ).toEqual(expect.arrayContaining(expected));
  }
});
