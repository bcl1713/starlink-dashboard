import { expect, it } from 'vitest';
import { record } from '@/test/operator-fixtures';
import { collectRecordEvidence } from './trainingEvidence';
import type { SavedRecord } from '@/types/operator';
const note: SavedRecord = {
  ...record,
  mission_id: 'fictional',
  provenance: { ...record.provenance, source_mode: 'simulation' },
};
const source = {
  missionId: 'fictional',
  ready: true,
  complete: true,
  historyComplete: false,
  fresh: true,
  records: [note],
  history: [note],
  prerequisiteIds: [] as string[],
  receipts: [
    {
      schema_version: 1 as const,
      command_id: note.command_id,
      saved_records: [note],
    },
  ],
};
it('counts real learner records and excludes prerequisite, other mission and removed records', () => {
  expect(collectRecordEvidence(source).outcomes).toContain('scoped-note');
  expect(
    collectRecordEvidence({ ...source, prerequisiteIds: [note.record_id] })
      .outcomes
  ).not.toContain('scoped-note');
  expect(
    collectRecordEvidence({
      ...source,
      records: [{ ...note, mission_id: 'other' }],
    }).outcomes
  ).not.toContain('scoped-note');
  expect(
    collectRecordEvidence({ ...source, records: [{ ...note, deleted: true }] })
      .outcomes
  ).not.toContain('scoped-note');
});
it('never treats partial, stale or unavailable reads as all clear', () => {
  expect(collectRecordEvidence({ ...source, complete: false }).available).toBe(
    false
  );
  expect(collectRecordEvidence({ ...source, ready: false }).available).toBe(
    false
  );
  expect(collectRecordEvidence({ ...source, fresh: false }).fresh).toBe(false);
});
it('requires actual command receipt matching the saved record version', () => {
  expect(
    collectRecordEvidence({ ...source, receipts: [] }).outcomes
  ).not.toContain('scoped-note');
  expect(
    collectRecordEvidence({ ...source, records: [{ ...note, version: 2 }] })
      .outcomes
  ).not.toContain('scoped-note');
});
it('requires original left interval and a distinct linked new interval to prove resume', () => {
  const left: SavedRecord = {
    ...note,
    record_type: 'participation',
    record_id: 'left',
    payload: {
      ...note.payload,
      entry_type: 'participation',
      call_id: null,
      conference_id: 'bridge',
      participant: 'Meridian',
      state: 'left',
      resumes_participation_id: null,
    },
    time: {
      ...note.time,
      occurred_at: '2026-10-18T10:00:00Z',
      ended_at: '2026-10-18T10:02:00Z',
      end_state: 'known',
    },
  };
  const resumed: SavedRecord = {
    ...left,
    record_id: 'resumed',
    command_id: 'resume',
    payload: {
      ...left.payload,
      entry_type: 'participation',
      state: 'connected',
      call_id: null,
      conference_id: 'bridge',
      participant: 'Meridian',
      resumes_participation_id: 'left',
    },
    time: {
      ...left.time,
      occurred_at: '2026-10-18T10:03:00Z',
      ended_at: null,
      end_state: 'ongoing',
    },
  };
  const evidence = {
    ...source,
    records: [left, resumed],
    history: [left, resumed],
    receipts: [left, resumed].map((r) => ({
      schema_version: 1 as const,
      command_id: r.command_id,
      saved_records: [r],
    })),
  };
  expect(collectRecordEvidence(evidence).outcomes).toContain(
    'participation-resumed-new-interval'
  );
  expect(
    collectRecordEvidence({ ...evidence, records: [resumed] }).outcomes
  ).not.toContain('participation-resumed-new-interval');
});
it('verifies applied-only from the saved payload rather than a guide flag', () => {
  const applied: SavedRecord = {
    ...note,
    record_type: 'transport_decision',
    payload: {
      ...note.payload,
      entry_type: 'transport_decision',
      reason: '',
      call_id: null,
      conference_id: null,
      services: [
        {
          row_id: 'voice',
          service: 'Voice',
          intended: null,
          requested: null,
          applied: {
            transport: 'Ka',
            time: { at: null, precision: 'unknown' },
          },
          checked: null,
        },
      ],
    },
  };
  const current = {
    ...source,
    records: [applied],
    receipts: [
      {
        schema_version: 1 as const,
        command_id: applied.command_id,
        saved_records: [applied],
      },
    ],
  };
  expect(collectRecordEvidence(current).outcomes).toContain(
    'applied-only-report'
  );
  expect(
    collectRecordEvidence({ ...current, receipts: [] }).outcomes
  ).not.toContain('applied-only-report');
});
it('requires a preserved original version before accepting historical issue correction', () => {
  const original: SavedRecord = {
    ...note,
    record_type: 'issue',
    payload: {
      ...note.payload,
      entry_type: 'issue',
      status: 'monitoring',
      corrects_version: null,
    },
  };
  const corrected: SavedRecord = {
    ...original,
    version: 2,
    previous_version: 1,
    command_id: 'correct',
    operation: 'update',
    payload: {
      ...original.payload,
      entry_type: 'issue',
      status: 'monitoring',
      corrects_version: 1,
    },
  };
  const current = {
    ...source,
    records: [corrected],
    history: [original, corrected],
    receipts: [original, corrected].map((r) => ({
      schema_version: 1 as const,
      command_id: r.command_id,
      saved_records: [r],
    })),
  };
  expect(collectRecordEvidence(current).outcomes).toContain(
    'issue-historical-correction'
  );
  expect(
    collectRecordEvidence({ ...current, history: [corrected] }).outcomes
  ).not.toContain('issue-historical-correction');
});

it('revalidates a learner write from complete authoritative history after receipts leave memory', () => {
  expect(
    collectRecordEvidence({ ...source, receipts: [], historyComplete: true })
      .outcomes
  ).toContain('scoped-note');
  expect(
    collectRecordEvidence({
      ...source,
      receipts: [],
      historyComplete: true,
      history: [],
    }).outcomes
  ).not.toContain('scoped-note');
});

it('never matches absent identities or missing evidence during cold load', async () => {
  const { isCurrentTrainingEvidence } = await import('./trainingEvidence');
  expect(isCurrentTrainingEvidence(null, undefined, undefined, 100)).toBe(
    false
  );
  const checked = {
    identity: 'private',
    H: 9,
    checkedAt: 50,
    available: true,
    fresh: true,
    outcomes: ['scoped-note'],
  };
  expect(isCurrentTrainingEvidence(checked, 'private', 9, 100)).toBe(true);
  expect(isCurrentTrainingEvidence(checked, 'other', 9, 100)).toBe(false);
  expect(isCurrentTrainingEvidence(checked, 'private', 10, 100)).toBe(false);
  expect(isCurrentTrainingEvidence(checked, 'private', 9, 31000)).toBe(false);
});
it('accepts the preserved interrupted interval used by the real Restore connection command', () => {
  const earlier: SavedRecord = {
    ...note,
    record_type: 'participation',
    record_id: 'interrupted',
    payload: {
      ...note.payload,
      entry_type: 'participation',
      call_id: null,
      conference_id: 'bridge',
      participant: 'Meridian',
      state: 'interrupted',
      resumes_participation_id: null,
    },
    time: {
      ...note.time,
      occurred_at: '2026-10-18T10:00:00Z',
      ended_at: '2026-10-18T10:02:00Z',
      end_state: 'known',
    },
  };
  const current: SavedRecord = {
    ...earlier,
    record_id: 'restored',
    command_id: 'restore',
    payload: {
      ...earlier.payload,
      entry_type: 'participation',
      call_id: null,
      conference_id: 'bridge',
      participant: 'Meridian',
      state: 'connected',
      resumes_participation_id: earlier.record_id,
    },
    time: {
      ...earlier.time,
      occurred_at: '2026-10-18T10:03:00Z',
      ended_at: null,
      end_state: 'ongoing',
    },
  };
  const evidence = {
    ...source,
    records: [earlier, current],
    history: [earlier, current],
    historyComplete: true,
    receipts: [],
  };
  expect(collectRecordEvidence(evidence).outcomes).toContain(
    'participation-resumed-new-interval'
  );
});
