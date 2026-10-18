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
it('invalidates checked source evidence when the event generation changes without a journal write', async () => {
  const { isCurrentTrainingEvidence } = await import('./trainingEvidence');
  const checked = {
    identity: 'private',
    H: 9,
    checkedAt: 50,
    eventGeneration: 'first-inputs',
    available: true,
    fresh: true,
    outcomes: ['current-model-sources'],
  };
  expect(
    isCurrentTrainingEvidence(checked, 'private', 9, 100, 'first-inputs')
  ).toBe(true);
  expect(
    isCurrentTrainingEvidence(checked, 'private', 9, 100, 'new-inputs')
  ).toBe(false);
});
it('never calls a consecutive suffix the complete call history', () => {
  const second: SavedRecord = {
    ...note,
    record_type: 'call',
    version: 2,
    previous_version: 1,
    payload: {
      ...note.payload,
      entry_type: 'call',
      status: 'scheduled',
      conference_id: null,
    },
  };
  const third: SavedRecord = {
    ...second,
    version: 3,
    previous_version: 2,
    command_id: 'third',
  };
  const evidence = {
    ...source,
    records: [third],
    history: [second, third],
    historyComplete: true,
    receipts: [second, third].map((r) => ({
      schema_version: 1 as const,
      command_id: r.command_id,
      saved_records: [r],
    })),
  };
  expect(collectRecordEvidence(evidence).outcomes).not.toContain(
    'call-history'
  );
});

function callRecord(
  id: string,
  status: import('@/types/operator').CallPayload['status'],
  version = 1
): SavedRecord {
  return {
    ...note,
    record_type: 'call',
    record_id: id,
    version,
    previous_version: version > 1 ? version - 1 : null,
    command_id: `${id}-${version}`,
    journal_seq: version,
    time: {
      ...note.time,
      occurred_at: null,
      ended_at: null,
      precision: 'unknown',
      end_state: 'unknown',
      planned_start_at: status === 'scheduled' ? '2026-10-18T16:00:00Z' : null,
    },
    payload: {
      ...note.payload,
      entry_type: 'call',
      title: id,
      status,
      conference_id: null,
      prep_lead_minutes: 10,
    },
  };
}
function authoritative(
  records: SavedRecord[],
  history = records,
  prerequisiteIds: string[] = []
) {
  return {
    ...source,
    records,
    history,
    prerequisiteIds,
    historyComplete: true,
    receipts: [],
  };
}
it('accepts a reported completed call with unknown actual end without treating an unperformed planned call as that exercise', () => {
  const completed = callRecord('completed', 'completed');
  expect(collectRecordEvidence(authoritative([completed])).outcomes).toEqual(
    expect.arrayContaining(['call-completed', 'call-unknown-time'])
  );
  const planned = callRecord('planned', 'scheduled');
  expect(
    collectRecordEvidence(authoritative([planned])).outcomes
  ).not.toContain('call-unknown-time');
});
it('counts learner edits of planned prerequisites without awarding their seeded creation', () => {
  const initial = callRecord('prerequisite', 'scheduled');
  const changed = {
    ...callRecord('prerequisite', 'scheduled', 2),
    time: { ...initial.time, planned_start_at: '2026-10-18T17:00:00Z' },
  };
  const outcomes = collectRecordEvidence(
    authoritative([changed], [initial, changed], ['prerequisite'])
  ).outcomes;
  expect(outcomes).toContain('call-rescheduled');
  expect(outcomes).not.toContain('call-created');
});
it('does not accept a historic correction that also replays a lifecycle change', () => {
  const original: SavedRecord = {
    ...note,
    record_type: 'issue',
    payload: {
      ...note.payload,
      entry_type: 'issue',
      status: 'monitoring',
      update_text: 'Original report',
    },
  };
  const changed: SavedRecord = {
    ...original,
    version: 2,
    previous_version: 1,
    command_id: 'changed',
    journal_seq: 2,
    payload: {
      ...original.payload,
      entry_type: 'issue',
      status: 'resolved',
      corrects_version: 1,
      update_text: 'Corrected report',
    },
  };
  expect(
    collectRecordEvidence(authoritative([changed], [original, changed]))
      .outcomes
  ).not.toContain('issue-historical-correction');
});
it('recognizes independent capability observations even when their actual time is unknown', () => {
  const assessment: SavedRecord = {
    ...note,
    payload: {
      ...note.payload,
      entry_type: 'capability_assessment',
      functional_status: 'functional',
      redundancy_status: 'unknown',
      functional_observed_at: null,
      redundancy_observed_at: null,
      functional_time_precision: 'unknown',
      redundancy_time_precision: 'unknown',
    },
  };
  expect(collectRecordEvidence(authoritative([assessment])).outcomes).toContain(
    'capability-independent'
  );
});
it('retains applied-only evidence in history and accepts independent checks with known results and unknown times', () => {
  const first: SavedRecord = {
    ...note,
    record_type: 'transport_decision',
    payload: {
      ...note.payload,
      entry_type: 'transport_decision',
      reason: '',
      call_id: null,
      conference_id: null,
      services: ['Voice', 'Video'].map((service) => ({
        row_id: service,
        service,
        intended: null,
        requested: null,
        applied: { transport: 'Ka', time: { at: null, precision: 'unknown' } },
        checked: null,
      })),
    },
  };
  if (first.payload.entry_type !== 'transport_decision') throw Error('fixture');
  const checked: SavedRecord = {
    ...first,
    version: 2,
    previous_version: 1,
    command_id: 'checked',
    journal_seq: 2,
    payload: {
      ...first.payload,
      services: first.payload.services.map((row) => ({
        ...row,
        checked: {
          result: 'satisfactory',
          time: { at: null, precision: 'unknown' },
          note: '',
        },
      })),
    },
  };
  expect(
    collectRecordEvidence(authoritative([checked], [first, checked])).outcomes
  ).toEqual(
    expect.arrayContaining([
      'applied-only-report',
      'independent-service-checks',
    ])
  );
});
it('retains verified and restored conference history after closing a bridge reused by later calls', () => {
  const base: SavedRecord = {
    ...note,
    record_type: 'conference',
    record_id: 'bridge',
    payload: {
      ...note.payload,
      entry_type: 'conference',
      status: 'established',
      verified_at: '2026-10-18T16:00:00Z',
    },
  };
  const interrupted: SavedRecord = {
    ...base,
    version: 2,
    previous_version: 1,
    command_id: 'interrupt',
    journal_seq: 2,
    payload: {
      ...base.payload,
      entry_type: 'conference',
      status: 'interrupted',
      verified_at: null,
    },
  };
  const restored: SavedRecord = {
    ...base,
    version: 3,
    previous_version: 2,
    command_id: 'restore-bridge',
    journal_seq: 3,
  };
  const closed: SavedRecord = {
    ...base,
    version: 4,
    previous_version: 3,
    command_id: 'close',
    journal_seq: 4,
    payload: {
      ...base.payload,
      entry_type: 'conference',
      status: 'closed',
      verified_at: null,
    },
  };
  const calls = ['first-call', 'later-call'].map((id) => {
    const call = callRecord(id, 'scheduled');
    return {
      ...call,
      payload: {
        ...call.payload,
        entry_type: 'call' as const,
        status: 'scheduled' as const,
        conference_id: 'bridge',
      },
    };
  });
  const outcomes = collectRecordEvidence(
    authoritative(
      [closed, ...calls],
      [base, interrupted, restored, closed, ...calls]
    )
  ).outcomes;
  expect(outcomes).toEqual(
    expect.arrayContaining([
      'conference-established-verified',
      'conference-interrupted-restored',
      'conference-reused-closed',
    ])
  );
});
it('proves overlapping reports from complete journal order but never infers it from missing transitions', () => {
  const participant = (
    id: string,
    state: 'connected' | 'left',
    version: number,
    seq: number
  ): SavedRecord => ({
    ...note,
    record_type: 'participation',
    record_id: id,
    version,
    previous_version: version > 1 ? version - 1 : null,
    journal_seq: seq,
    command_id: `${id}-${version}`,
    time: {
      ...note.time,
      occurred_at: null,
      ended_at: null,
      precision: 'unknown',
      end_state: 'unknown',
    },
    payload: {
      ...note.payload,
      entry_type: 'participation',
      call_id: null,
      conference_id: 'bridge',
      participant: id,
      state,
      resumes_participation_id: null,
    },
  });
  const a = participant('a', 'connected', 1, 1),
    b = participant('b', 'connected', 1, 2);
  const aLeft = participant('a', 'left', 2, 3),
    bLeft = participant('b', 'left', 2, 4);
  expect(
    collectRecordEvidence(authoritative([aLeft, bLeft], [a, b, aLeft, bLeft]))
      .outcomes
  ).toEqual(
    expect.arrayContaining([
      'participation-overlap',
      'participation-joined-left',
    ])
  );
  const earlyLeft = { ...aLeft, journal_seq: 2 },
    lateJoin = { ...b, journal_seq: 3 };
  const partial = {
    ...authoritative([earlyLeft, lateJoin], [a, lateJoin]),
    historyComplete: false,
    receipts: [a, earlyLeft, lateJoin].map((row) => ({
      schema_version: 1 as const,
      command_id: row.command_id,
      saved_records: [row],
    })),
  };
  expect(collectRecordEvidence(partial).outcomes).not.toContain(
    'participation-overlap'
  );
});
it('compares full receipt records semantically and rejects a mismatching saved payload', () => {
  const reordered: SavedRecord = {
    ...note,
    payload: Object.fromEntries(
      Object.entries(note.payload).reverse()
    ) as SavedRecord['payload'],
  };
  const evidence = {
    ...source,
    records: [reordered],
    receipts: [
      {
        schema_version: 1 as const,
        command_id: note.command_id,
        saved_records: [note],
      },
    ],
  };
  expect(collectRecordEvidence(evidence).outcomes).toContain('scoped-note');
  expect(
    collectRecordEvidence({
      ...evidence,
      records: [
        {
          ...reordered,
          payload: { ...reordered.payload, title: 'Different write' },
        },
      ],
    }).outcomes
  ).not.toContain('scoped-note');
});
it('retains an earlier follow-up clear and historical correction after a later ordinary update', () => {
  const original: SavedRecord = {
    ...note,
    record_type: 'issue',
    payload: {
      ...note.payload,
      entry_type: 'issue',
      status: 'monitoring',
      follow_up_at: '2026-10-18T16:00:00Z',
      update_text: 'Original message',
    },
  };
  const clear: SavedRecord = {
    ...original,
    version: 2,
    previous_version: 1,
    journal_seq: 2,
    command_id: 'clear',
    payload: {
      ...original.payload,
      entry_type: 'issue',
      status: 'monitoring',
      follow_up_at: null,
    },
  };
  const correction: SavedRecord = {
    ...clear,
    version: 3,
    previous_version: 2,
    journal_seq: 3,
    command_id: 'correct',
    payload: {
      ...clear.payload,
      entry_type: 'issue',
      status: 'monitoring',
      corrects_version: 1,
      update_text: 'Corrected message',
    },
  };
  const later: SavedRecord = {
    ...correction,
    version: 4,
    previous_version: 3,
    journal_seq: 4,
    command_id: 'later',
    payload: {
      ...correction.payload,
      entry_type: 'issue',
      status: 'monitoring',
      corrects_version: null,
      follow_up_at: '2026-10-18T17:00:00Z',
      update_text: 'New follow-up',
    },
  };
  expect(
    collectRecordEvidence(
      authoritative([later], [original, clear, correction, later])
    ).outcomes
  ).toEqual(
    expect.arrayContaining([
      'issue-followup-cleared',
      'issue-historical-correction',
    ])
  );
});
it('treats conflicting immutable response bodies as unavailable evidence', () => {
  const contradictory = {
    ...note,
    payload: { ...note.payload, title: 'Conflicting immutable version' },
  };
  expect(
    collectRecordEvidence(authoritative([note], [contradictory])).available
  ).toBe(false);
});
it('never reuses checked evidence whose source reports unavailable or stale', async () => {
  const { isCurrentTrainingEvidence } = await import('./trainingEvidence');
  const checked = {
    identity: 'private',
    H: 9,
    checkedAt: 50,
    available: true,
    fresh: true,
    outcomes: ['scoped-note'],
  };
  expect(
    isCurrentTrainingEvidence(
      { ...checked, available: false },
      'private',
      9,
      100
    )
  ).toBe(false);
  expect(
    isCurrentTrainingEvidence({ ...checked, fresh: false }, 'private', 9, 100)
  ).toBe(false);
});
