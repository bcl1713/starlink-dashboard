import { describe, expect, it } from 'vitest';
import { record } from '@/test/operator-fixtures';
import { preparationAt, shiftCallTime } from './callTiming';
import { callDraft } from './callDraft';
import type { SavedRecord } from '@/types/operator';
const call: SavedRecord = {
  ...record,
  record_type: 'call',
  payload: {
    ...record.payload,
    entry_type: 'call',
    status: 'scheduled',
    conference_id: null,
  },
  time: { ...record.time, planned_start_at: '2026-10-17T23:30:00Z' },
};
describe('call timing', () => {
  it.each([
    [120, '2026-10-18T01:30:00.000Z'],
    [-15, '2026-10-17T23:15:00.000Z'],
  ])('shifts %s minutes without inventing duration', (minutes, want) => {
    const result = shiftCallTime(call.time, minutes);
    expect(result.planned_start_at).toBe(want);
    expect(result.planned_end_at).toBeNull();
    expect(result.occurred_at).toBe(record.time.occurred_at);
  });
  it('preserves known duration across midnight', () => {
    expect(
      shiftCallTime(
        { ...call.time, planned_end_at: '2026-10-18T00:00:00Z' },
        120
      ).planned_end_at
    ).toBe('2026-10-18T02:00:00.000Z');
  });
  it.each([1.5, Infinity, NaN, 525601])('rejects invalid shifts %s', (n) =>
    expect(() => shiftCallTime(call.time, n)).toThrow()
  );
  it('rejects shifting an unknown planned start', () =>
    expect(() => shiftCallTime(record.time, 1)).toThrow());
  it.each([
    [undefined, null],
    [null, null],
    [0, '2026-10-17T23:30:00.000Z'],
    [10, '2026-10-17T23:20:00.000Z'],
  ])('derives prep only from known lead %s', (lead, want) => {
    expect(
      preparationAt({
        ...call,
        payload: {
          ...call.payload,
          entry_type: 'call',
          status: 'scheduled',
          conference_id: null,
          prep_lead_minutes: lead,
        },
      })
    ).toBe(want);
  });
  it.each(['cancelled', 'completed'] as const)(
    'suppresses %s preparation',
    (status) => {
      expect(
        preparationAt({
          ...call,
          payload: {
            ...call.payload,
            entry_type: 'call',
            status,
            conference_id: null,
            prep_lead_minutes: 10,
          },
        })
      ).toBeNull();
    }
  );
  it('suppresses removed preparation', () =>
    expect(preparationAt({ ...call, deleted: true })).toBeNull());
});
describe('call drafts', () => {
  it('defaults new planned calls only', () => {
    expect(
      callDraft(undefined, 'planned', 'demo').payload.prep_lead_minutes
    ).toBe(10);
    const retro = callDraft(undefined, 'retrospective', 'demo');
    expect(retro.payload.prep_lead_minutes).toBeNull();
    expect(retro.time.planned_start_at).toBeNull();
    expect(retro.payload.status).toBe('completed');
  });
  it.each([undefined, null, 0, 25])(
    'roundtrips edited lead %s without create defaults',
    (lead) => {
      const original: SavedRecord = {
        ...call,
        payload: {
          ...call.payload,
          entry_type: 'call',
          status: 'scheduled',
          conference_id: null,
          prep_lead_minutes: lead,
        },
      };
      const draft = callDraft(original, 'planned', 'demo');
      expect(draft.payload.prep_lead_minutes).toBe(lead ?? null);
      expect(draft.mission_id).toBe(call.mission_id);
    }
  );
});
