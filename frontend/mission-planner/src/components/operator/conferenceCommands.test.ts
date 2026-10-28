import { describe, expect, it } from 'vitest';
import { record } from '@/test/operator-fixtures';
import {
  conferenceCommand,
  sessionOutsideContext,
  leaveCommand,
  resumeCommand,
} from './conferenceCommands';
import type { SavedRecord } from '@/types/operator';
const now = '2026-10-17T16:00:00Z';
const conference: SavedRecord = {
  ...record,
  record_type: 'conference',
  payload: {
    ...record.payload,
    entry_type: 'conference',
    status: 'interrupted',
    verified_at: null,
  },
};
const participation: SavedRecord = {
  ...record,
  record_type: 'participation',
  payload: {
    ...record.payload,
    entry_type: 'participation',
    call_id: null,
    conference_id: 'conference-a',
    state: 'interrupted',
  },
};
describe('captured conference commands', () => {
  it('restores conference without claiming verification', () => {
    const command = conferenceCommand(conference, 'restore_connection', now);
    expect(command.body).toMatchObject({
      expected_version: 1,
      time: { occurred_at: now },
      payload: { status: 'established', verified_at: null },
    });
    expect(() => conferenceCommand(conference, 'verify', now)).toThrow();
  });
  it('restores customer into a new interval preserving predecessor', () => {
    const command = resumeCommand(participation, now);
    expect(command.operation).toBe('create');
    expect(command.body).toMatchObject({
      connect_customer: true,
      time: { occurred_at: now, ended_at: null, end_state: 'ongoing' },
      payload: { state: 'connected', resumes_participation_id: 'record-a' },
    });
    expect(participation.payload).toHaveProperty('state', 'interrupted');
  });
  it('leaves unknown-start customers without inventing a start', () => {
    const unknown = {
      ...participation,
      time: {
        ...record.time,
        occurred_at: null,
        precision: 'unknown' as const,
        end_state: 'unknown' as const,
      },
      payload: { ...participation.payload, state: 'connected' },
    } as SavedRecord;
    expect(leaveCommand(unknown, 'left', now).body).toMatchObject({
      time: { occurred_at: null, ended_at: null, end_state: 'unknown' },
      payload: { state: 'left' },
    });
  });
});

it('creates participation payloads accepted by the closed public contract', async () => {
  const { participationDraft } = await import('./conferenceCommands');
  const draft = participationDraft('mission-a', 'conference-a');
  expect(draft.payload).toEqual({
    schema_version: 1,
    entry_type: 'participation',
    title: 'Unknown customer',
    note: '',
    previous_leg_id: null,
    next_leg_id: null,
    participant: null,
    call_id: null,
    conference_id: 'conference-a',
    state: 'connected',
    resumes_participation_id: null,
  });
});

it('reestablishes the saved configuration on a later leg with fresh verification and preserved identity', () => {
  const closed = {
    ...conference,
    scope: 'leg' as const,
    leg_id: 'outbound',
    payload: {
      ...conference.payload,
      entry_type: 'conference' as const,
      status: 'closed' as const,
      coordinator: 'Saved coordinator',
      configured_transport: 'Ka' as const,
    },
  };
  const command = conferenceCommand(closed, 'establish', now, {
    scope: 'leg',
    leg_id: 'return',
    previous_leg_id: null,
    next_leg_id: null,
    label: 'Return',
  });
  expect(command).toMatchObject({
    operation: 'update',
    record_id: closed.record_id,
    body: {
      expected_version: closed.version,
      scope: 'leg',
      leg_id: 'return',
      payload: {
        status: 'established',
        verified_at: now,
        coordinator: 'Saved coordinator',
        configured_transport: 'Ka',
      },
    },
  });
  expect(closed.leg_id).toBe('outbound');
  expect(closed.payload.status).toBe('closed');
});
it('does not move an open session or clear independent customer reports on close', () => {
  const established = {
    ...conference,
    scope: 'leg' as const,
    leg_id: 'outbound',
    payload: {
      ...conference.payload,
      entry_type: 'conference' as const,
      status: 'established' as const,
    },
  };
  const association = {
    scope: 'leg' as const,
    leg_id: 'return',
    previous_leg_id: null,
    next_leg_id: null,
    label: 'Return',
  };
  expect(() =>
    conferenceCommand(established, 'verify', now, association)
  ).toThrow(/establish/i);
  expect(
    conferenceCommand(established, 'close', now, association)
  ).toMatchObject({
    operation: 'update',
    body: { scope: 'leg', leg_id: 'outbound', payload: { status: 'closed' } },
  });
});
it('preserves an explicit association when current timing is unavailable', () => {
  const chosen = {
    ...conference,
    scope: 'leg' as const,
    leg_id: 'operator-chosen-leg',
    payload: {
      ...conference.payload,
      entry_type: 'conference' as const,
      status: 'preparing' as const,
    },
  };
  expect(conferenceCommand(chosen, 'establish', now, null)).toMatchObject({
    body: { scope: 'leg', leg_id: 'operator-chosen-leg' },
  });
});
it('keeps the first establishment on the explicitly saved leg', () => {
  const chosen = {
    ...conference,
    scope: 'leg' as const,
    leg_id: 'operator-chosen-leg',
    payload: {
      ...conference.payload,
      entry_type: 'conference' as const,
      status: 'preparing' as const,
    },
  };
  const current = {
    scope: 'leg' as const,
    leg_id: 'current-leg',
    previous_leg_id: null,
    next_leg_id: null,
    label: 'Current leg',
  };
  expect(conferenceCommand(chosen, 'establish', now, current)).toMatchObject({
    body: { scope: 'leg', leg_id: 'operator-chosen-leg' },
  });
});

it('does not carry an open leg report through a known ground gap', () => {
  expect(
    sessionOutsideContext(
      { ...conference, scope: 'leg', leg_id: 'outbound' },
      {
        scope: 'between_legs',
        leg_id: null,
        previous_leg_id: 'outbound',
        next_leg_id: 'return',
        label: 'Between legs',
      }
    )
  ).toBe(true);
});
it('does not replace a deliberately unassigned initial activity with an inferred leg', () => {
  const chosen = {
    ...conference,
    scope: 'mission' as const,
    leg_id: null,
    payload: {
      ...conference.payload,
      entry_type: 'conference' as const,
      status: 'preparing' as const,
    },
  };
  expect(
    conferenceCommand(chosen, 'establish', now, {
      scope: 'leg',
      leg_id: 'inferred',
      previous_leg_id: null,
      next_leg_id: null,
      label: 'Inferred',
    })
  ).toMatchObject({ body: { scope: 'mission', leg_id: null } });
});

it('explicitly reestablishes a retained verified definition without duplicating it', () => {
  const retained = {
    ...conference,
    payload: {
      ...conference.payload,
      entry_type: 'conference' as const,
      status: 'established' as const,
      verified_at: now,
    },
  };
  const command = conferenceCommand(retained, 'establish', now, null, false);
  expect(command).toMatchObject({
    operation: 'update',
    record_id: retained.record_id,
    body: {
      establish_session: true,
      expected_version: retained.version,
      payload: { status: 'established', verified_at: now },
    },
  });
  expect(retained.payload.verified_at).toBe(now);
});

it('establishes and reports the two-way distant-end check in one versioned command', () => {
  const preparing = {
    ...conference,
    payload: { ...conference.payload, status: 'preparing' },
  } as SavedRecord;
  expect(conferenceCommand(preparing, 'establish', now)).toMatchObject({
    operation: 'update',
    body: {
      expected_version: 1,
      establish_session: true,
      time: { occurred_at: now },
      payload: { status: 'established', verified_at: now },
    },
  });
});
