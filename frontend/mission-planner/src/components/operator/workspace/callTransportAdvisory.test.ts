import { expect, it } from 'vitest';
import { callDraft } from '../callDraft';
import { conferenceDraft } from '../conferenceCommands';
import { record } from '@/test/operator-fixtures';
import { eventFixture } from '@/test/operator-event-fixtures';
import type { SavedRecord } from '@/types/operator';
import type { MissionTimelineSnapshot } from '@/types/missionTimeline';
import { callTransportAdvisory } from './callTransportAdvisory';
const call = {
  ...record,
  ...callDraft(undefined, 'planned', 'mission-a'),
  record_id: 'call',
  scope: 'leg',
  leg_id: 'leg-a',
  time: {
    ...record.time,
    planned_start_at: '2026-10-28T13:55:00Z',
    planned_end_at: '2026-10-28T14:25:00Z',
  },
  payload: {
    ...callDraft(undefined, 'planned', 'mission-a').payload,
    conference_id: 'bridge',
  },
} as SavedRecord;
const bridge = {
  ...record,
  ...conferenceDraft('mission-a'),
  record_id: 'bridge',
  payload: {
    ...conferenceDraft('mission-a').payload,
    configured_transport: 'Ka',
    intended_transport: 'X',
  },
} as SavedRecord;
const snapshot = {
  mission_id: 'mission-a',
  as_of: '2026-10-28T13:45:00Z',
  sources: [{ source: 'model:leg-a', aligned: true, freshness: 'fresh' }],
  legs: [
    {
      leg_id: 'leg-a',
      coverage: 'available',
      reason: null,
      scheduled_departure_at: '2026-10-28T12:00:00Z',
      scheduled_arrival_at: '2026-10-28T17:00:00Z',
    },
  ],
  events: [
    eventFixture({
      kind: 'restriction',
      leg_id: 'leg-a',
      transport: 'Ka',
      due_at: '2026-10-28T13:50:00Z',
      end_at: '2026-10-28T14:10:00Z',
      source_ref: 'model:leg-a',
      significance: 'unavailable',
    }),
  ],
} as MissionTimelineSnapshot;
it('uses reported assignment and source-backed restriction intervals', () => {
  const result = callTransportAdvisory(call, [call, bridge], snapshot, false);
  expect(result.assignment).toBe('Ka Commercial');
  expect(result.intended).toBe('X-Band');
  expect(result.status).toBe('overlap');
  expect(result.windows[0].due_at).toBe('2026-10-28T13:50:00Z');
});
it('recomputes on reschedule and assignment changes', () => {
  const later = {
    ...call,
    time: { ...call.time, planned_start_at: '2026-10-28T14:15:00Z' },
  };
  expect(
    callTransportAdvisory(later, [later, bridge], snapshot, false).status
  ).toBe('no_known_overlap');
  const changed = {
    ...bridge,
    payload: { ...bridge.payload, configured_transport: 'X' },
  } as SavedRecord;
  expect(
    callTransportAdvisory(call, [call, changed], snapshot, false).windows
  ).toHaveLength(0);
});
it('keeps stale, missing, ad hoc and untimed coverage unknown', () => {
  expect(
    callTransportAdvisory(call, [call, bridge], snapshot, true).status
  ).toBe('unknown');
  expect(callTransportAdvisory(call, [call], snapshot, false).status).toBe(
    'unknown'
  );
  const adhoc = {
    ...call,
    payload: {
      ...call.payload,
      conference_id: null,
      direct_transport: 'Training Relay',
    },
  } as SavedRecord;
  expect(callTransportAdvisory(adhoc, [adhoc], snapshot, false).status).toBe(
    'unknown'
  );
  const untimed = { ...call, time: { ...call.time, planned_end_at: null } };
  expect(
    callTransportAdvisory(untimed, [untimed, bridge], snapshot, false).status
  ).toBe('unknown');
  const uncertain = {
    ...snapshot,
    events: [
      {
        ...snapshot.events[0],
        due_at: null,
        time_basis: 'live_unavailable' as const,
      },
    ],
  };
  expect(
    callTransportAdvisory(call, [call, bridge], uncertain, false).status
  ).toBe('unknown');
});
it('supports direct calls and distinguishes PoP transition advisories', () => {
  const direct = {
    ...call,
    payload: { ...call.payload, conference_id: null, direct_transport: 'Ka' },
  } as SavedRecord;
  expect(callTransportAdvisory(direct, [direct], snapshot, false).status).toBe(
    'overlap'
  );
  const pop = {
    ...snapshot,
    events: [
      {
        ...snapshot.events[0],
        kind: 'pop_advisory' as const,
        transport: 'Ka',
        advisory_type: 'transition_window' as const,
      },
    ],
  };
  expect(callTransportAdvisory(direct, [direct], pop, false).status).toBe(
    'advisory'
  );
  const other = {
    ...snapshot,
    events: [{ ...snapshot.events[0], leg_id: 'another' }],
  };
  expect(
    callTransportAdvisory(call, [call, bridge], other, false).windows
  ).toHaveLength(0);
});
it('keeps intended-only assignments and unbounded coverage unknown', () => {
  const intended = {
    ...bridge,
    payload: { ...bridge.payload, configured_transport: null },
  } as SavedRecord;
  expect(
    callTransportAdvisory(call, [call, intended], snapshot, false).status
  ).toBe('unknown');
  const outside = {
    ...call,
    time: { ...call.time, planned_end_at: '2026-10-28T18:00:00Z' },
  };
  expect(
    callTransportAdvisory(
      outside,
      [outside, bridge],
      { ...snapshot, events: [] },
      false
    ).status
  ).toBe('unknown');
});

it('does not infer transport schedule coverage from fresh but partial models', () => {
  const partial = {
    ...snapshot,
    events: [],
    legs: [
      {
        ...snapshot.legs[0],
        coverage: 'partial' as const,
        reason: 'Ka coverage unavailable',
      },
    ],
  };
  expect(
    callTransportAdvisory(call, [call, bridge], partial, false).status
  ).toBe('unknown');
});
