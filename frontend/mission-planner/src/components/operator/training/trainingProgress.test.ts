import { describe, expect, it } from 'vitest';
import {
  createProgress,
  loadProgress,
  moveProgress,
  resetProgress,
  revisitStage,
  saveProgress,
} from './trainingProgress';
import { evaluateStep } from './trainingSteps';

const identity = {
  fixtureVersion: 1,
  origin: 'http://localhost:4567',
  storeId: 'private',
  epoch: 'epoch',
  missionId: 'fictional',
};
const memory = () => {
  const values = new Map<string, string>();
  return {
    values,
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
    removeItem: (key: string) => {
      values.delete(key);
    },
  };
};
describe('training progress is navigation, never write evidence', () => {
  it('Next visits without passing an unevidenced lesson; Back preserves evidence', () => {
    const initial = createProgress(identity);
    const next = moveProgress(initial, 'next');
    expect(next.currentStage).toBe('T02');
    expect(
      evaluateStep('T01', { available: true, fresh: true, outcomes: [] }, next)
        .status
    ).toBe('incomplete');
    const annotated = {
      ...next,
      manualEvidence: [
        {
          outcomeId: 'context-understood',
          observedAt: '2026-10-18T10:00:00Z',
          note: 'Identified the private mission and scope',
        },
      ],
    };
    expect(moveProgress(annotated, 'back').manualEvidence).toEqual(
      annotated.manualEvidence
    );
    expect(annotated.currentStage).toBe('T02');
  });
  it('Skip stays distinct and stale or missing evidence never passes', () => {
    const skipped = moveProgress(createProgress(identity), 'skip');
    expect(
      evaluateStep(
        'T01',
        { available: true, fresh: true, outcomes: [] },
        skipped
      ).status
    ).toBe('skipped');
    expect(
      evaluateStep('T01', { available: false, fresh: false, outcomes: [] })
        .status
    ).toBe('unavailable');
    expect(
      evaluateStep('T01', { available: true, fresh: false, outcomes: [] })
        .status
    ).toBe('unavailable');
  });
  it('requires all outcomes and distinguishes manual observations', () => {
    const progress = createProgress(identity);
    expect(
      evaluateStep(
        'T01',
        { available: true, fresh: true, outcomes: ['private-context-read'] },
        progress
      ).status
    ).toBe('incomplete');
    progress.manualEvidence.push({
      outcomeId: 'context-understood',
      observedAt: '2026-10-18T10:00:00Z',
      note: 'Confirmed mission and UTC context',
    });
    const result = evaluateStep(
      'T01',
      { available: true, fresh: true, outcomes: ['private-context-read'] },
      progress
    );
    expect(result.status).toBe('passed');
    expect(result.manualOutcomes).toEqual(['context-understood']);
  });
  it('round trips only the exact identity and retains other local data on reset', () => {
    const storage = memory();
    const progress = createProgress(identity);
    expect(saveProgress(storage, progress).error).toBeNull();
    expect(loadProgress(storage, identity).progress).toEqual(progress);
    for (const field of [
      'origin',
      'storeId',
      'epoch',
      'missionId',
      'fixtureVersion',
    ] as const) {
      const changed = {
        ...identity,
        [field]: field === 'fixtureVersion' ? 2 : 'other',
      };
      expect(loadProgress(storage, changed).progress).toBeNull();
    }
    storage.setItem('operator-drafts', 'keep');
    expect(resetProgress(storage, identity).error).toBeNull();
    expect(storage.getItem('operator-drafts')).toBe('keep');
    expect(loadProgress(storage, identity).progress).toBeNull();
  });
  it('rejects corrupt persisted values and reports storage errors', () => {
    const storage = memory();
    saveProgress(storage, createProgress(identity));
    const key = [...storage.values.keys()][0];
    for (const bad of [
      {},
      { ...createProgress(identity), currentStage: 'invented' },
      { ...createProgress(identity), skipped: ['unknown'] },
      {
        ...createProgress(identity),
        manualEvidence: [
          { outcomeId: 'call-created', observedAt: 'yesterday', note: 'fake' },
        ],
      },
    ]) {
      storage.setItem(key, JSON.stringify(bad));
      expect(loadProgress(storage, identity).error).toBeTruthy();
    }
    const denied = {
      getItem() {
        throw Error('denied');
      },
      setItem() {
        throw Error('denied');
      },
      removeItem() {
        throw Error('denied');
      },
    };
    expect(loadProgress(denied, identity).error).toContain('denied');
    expect(saveProgress(denied, createProgress(identity)).error).toContain(
      'denied'
    );
    expect(resetProgress(denied, identity).error).toContain('denied');
  });
});

it('revisiting a skipped stage permits checking evidence without claiming success', () => {
  const progress = moveProgress(createProgress(identity), 'skip');
  const resumed = revisitStage(progress, 'T01');
  expect(resumed.currentStage).toBe('T01');
  expect(resumed.skipped).not.toContain('T01');
  expect(progress.skipped).toContain('T01');
  expect(
    evaluateStep('T01', { available: true, fresh: true, outcomes: [] }, resumed)
      .status
  ).toBe('incomplete');
});
it('never labels stale automatic outcomes as verified while retaining explicit human observations', () => {
  const progress = createProgress(identity);
  progress.manualEvidence.push({
    outcomeId: 'context-understood',
    observedAt: '2026-10-18T10:00:00Z',
    note: 'Identified private mission',
  });
  const result = evaluateStep(
    'T01',
    { available: true, fresh: false, outcomes: ['private-context-read'] },
    progress
  );
  expect(result.status).toBe('unavailable');
  expect(result.missing).toContain('private-context-read');
  expect(result.manualOutcomes).toEqual(['context-understood']);
});

it('rejects corrupt command observations without accepting them as progress', () => {
  const storage = memory();
  const progress = createProgress(identity);
  expect(saveProgress(storage, progress).error).toBeNull();
  const entryKey = [...storage.values.keys()][0];
  storage.setItem(
    entryKey,
    JSON.stringify({
      ...progress,
      retryObservations: [
        {
          request: { key: 'not-a-request' },
          attemptIds: ['fake'],
          committedVersions: [],
        },
      ],
    })
  );
  expect(loadProgress(storage, identity).error).toContain('invalid');
  expect(storage.getItem(entryKey)).toContain('not-a-request');
});

it('quarantines retained archive reports from another epoch without accepting file success flags', async () => {
  const fixture = await import('@/test/training-archive-fixtures');
  const storage = memory();
  const progress = createProgress(fixture.identity);
  const raw = structuredClone(fixture.observation('empty'));
  raw.report.identity.epoch = 'foreign';
  saveProgress(storage, progress);
  const key = [...storage.values.keys()][0];
  storage.setItem(
    key,
    JSON.stringify({ ...progress, archiveObservations: [raw] })
  );
  expect(loadProgress(storage, fixture.identity).progress).toBeNull();
  expect(loadProgress(storage, fixture.identity).error).toBeTruthy();
});

it('round-trips valid raw archive reports using only the pinned identity fields', async () => {
  const fixture = await import('@/test/training-archive-fixtures');
  const storage = memory();
  const { decodeArchiveObservation } = await import(
    './trainingArchiveEvidence'
  );
  const progress = {
    ...createProgress(fixture.identity),
    archiveObservations: [
      decodeArchiveObservation(fixture.observation('empty'), fixture.identity),
    ],
  };
  expect(saveProgress(storage, progress).error).toBeNull();
  expect(
    loadProgress(storage, fixture.identity).progress?.archiveObservations
  ).toEqual(progress.archiveObservations);
});
