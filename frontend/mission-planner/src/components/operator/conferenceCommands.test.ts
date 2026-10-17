import { describe, expect, it } from 'vitest';
import { record } from '@/test/operator-fixtures';
import {
  conferenceCommand,
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
