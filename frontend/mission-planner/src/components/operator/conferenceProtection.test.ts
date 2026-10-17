import { describe, it, expect } from 'vitest';
import { record } from '@/test/operator-fixtures';
import type { SavedRecord } from '@/types/operator';
import type { Timeline } from '@/services/timeline';
import { deriveProtection } from './conferenceProtection';
const now = '2026-10-17T16:00:00Z';
const customer: SavedRecord = {
  ...record,
  record_type: 'participation',
  payload: {
    ...record.payload,
    entry_type: 'participation',
    call_id: null,
    conference_id: 'conference',
    state: 'connected',
  },
};
const timeline: Timeline = {
  mission_leg_id: 'leg-a',
  created_at: now,
  segments: [
    {
      id: 'gap',
      start_time: now,
      end_time: '2026-10-17T16:10:00Z',
      status: 'degraded',
      ka_state: 'offline',
      x_state: 'available',
      ku_state: 'available',
    },
  ],
  pop_forecast: {
    revision: 'r1',
    catalog_fingerprint: 'synthetic',
    status: 'ready',
    transitions: [],
  },
  call_continuity: {
    revision: 'r1',
    intervals: [],
    planned_communications_outage_seconds: 0,
    pop_call_outage_seconds: 0,
    longest_call_outage_seconds: 0,
  },
};
describe('supported modeled protection', () => {
  it('protects unknown-start customers and labels unknown transport relevance', () => {
    const result = deriveProtection(
      [customer],
      [{ legId: 'leg-a', timeline }],
      now,
      true
    );
    expect(result.items).toHaveLength(1);
    expect(result.items[0]).toMatchObject({
      participationId: 'record-a',
      classification: 'modeled_offline',
      relevance: 'unknown',
    });
    expect(result.limitations.join(' ')).toMatch(
      /Operator-planned transport changes are not included/
    );
  });
  it('never turns missing, stale, mismatched or partial inputs into all-clear', () => {
    for (const source of [
      null,
      { ...timeline, mission_leg_id: 'other' },
      { ...timeline, created_at: '2026-01-01T00:00:00Z' },
    ]) {
      expect(
        deriveProtection(
          [customer],
          [{ legId: 'leg-a', timeline: source }],
          now,
          true
        ).coverage
      ).not.toBe('available');
    }
    expect(
      deriveProtection([customer], [{ legId: 'leg-a', timeline }], now, false)
        .coverage
    ).not.toBe('available');
  });
  it('does not infer scheduled changes from configured/intended snapshot differences', () => {
    const conference: SavedRecord = {
      ...record,
      record_id: 'conference',
      record_type: 'conference',
      payload: {
        ...record.payload,
        entry_type: 'conference',
        status: 'established',
        configured_transport: 'X',
        intended_transport: 'Ka',
      },
    };
    const result = deriveProtection(
      [customer, conference],
      [{ legId: 'leg-a', timeline }],
      now,
      true
    );
    expect(result.items).toHaveLength(1);
    expect(result.items[0].relevance).toBe('intended');
    expect(result.items.some((item) => item.source === 'routing_change')).toBe(
      false
    );
  });
  it('uses half-open boundaries and ignores ordinary telemetry', () => {
    const ended = {
      ...timeline,
      segments: [
        {
          ...timeline.segments[0],
          end_time: now,
          start_time: '2026-10-17T15:00:00Z',
        },
      ],
    };
    expect(
      deriveProtection(
        [customer],
        [{ legId: 'leg-a', timeline: ended }],
        now,
        true
      ).items
    ).toHaveLength(0);
    expect(
      deriveProtection(
        [
          {
            ...customer,
            payload: { ...customer.payload, state: 'left' },
          } as SavedRecord,
        ],
        [{ legId: 'leg-a', timeline }],
        now,
        true
      ).items
    ).toHaveLength(0);
  });
});

it('does not infer current input alignment from an equal frozen clock timestamp', () => {
  expect(
    deriveProtection([customer], [{ legId: 'leg-a', timeline }], now, true)
      .coverage
  ).toBe('partial');
});
