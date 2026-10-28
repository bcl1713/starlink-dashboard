import { expect, it } from 'vitest';
import { record } from '@/test/operator-fixtures';
import { callDraft } from './callDraft';
import {
  callCommand,
  callTestReported,
  customerConnectionReady,
} from './callCommands';
const call = { ...record, ...callDraft(undefined, 'planned', 'mission-a') };
it('starts and finishes without inventing bridge or customer states', () => {
  const start = callCommand(call, 'start', '2026-10-20T11:00:00Z');
  expect(start).toMatchObject({
    operation: 'update',
    record_id: call.record_id,
    body: {
      expected_version: 1,
      payload: { status: 'scheduled' },
      time: { occurred_at: '2026-10-20T11:00:00Z', end_state: 'ongoing' },
    },
  });
  if (start.operation !== 'update') throw new Error('expected update');
  const running = { ...call, ...start.body };
  expect(callCommand(running, 'finish', '2026-10-20T11:10:00Z')).toMatchObject({
    body: {
      payload: { status: 'completed' },
      time: { ended_at: '2026-10-20T11:10:00Z', end_state: 'known' },
    },
  });
  expect(() => callCommand(call, 'finish', '2026-10-20T11:10:00Z')).toThrow();
});
it('records testing as an observation, separately from conference verification', () => {
  const running = {
    ...call,
    time: { ...call.time, occurred_at: '2026-10-20T11:00:00Z' },
  };
  const test = callCommand(running, 'test', '2026-10-20T11:01:00Z');
  expect(test).toMatchObject({
    operation: 'create',
    body: {
      record_type: 'journal_entry',
      payload: { entry_type: 'call_observation' },
    },
  });
  if (test.operation !== 'create') throw new Error('expected observation');
  expect(callTestReported(call, [{ ...record, ...test.body }])).toBe(true);
  expect(
    callTestReported({ ...call, record_id: 'other' }, [
      { ...record, ...test.body },
    ])
  ).toBe(false);
});
it('keeps a test observation inside the existing title length contract', () => {
  const long = {
    ...call,
    payload: { ...call.payload, party: 'A'.repeat(200) },
    time: { ...call.time, occurred_at: '2026-10-20T11:00:00Z' },
  };
  const command = callCommand(long, 'test', '2026-10-20T11:01:00Z');
  if (command.operation !== 'create') throw new Error('expected observation');
  expect(command.body.payload.title.length).toBeLessThanOrEqual(200);
});

it('establishes a direct call with a two-way check, retaining reported transport', () => {
  const direct = {
    ...call,
    payload: { ...call.payload, direct_transport: 'Ka' },
  };
  const command = callCommand(direct, 'establish', '2026-10-20T11:00:00Z');
  expect(command).toMatchObject({
    operation: 'update',
    body: {
      expected_version: 1,
      time: { occurred_at: '2026-10-20T11:00:00Z', end_state: 'ongoing' },
      payload: {
        established_at: '2026-10-20T11:00:00Z',
        direct_transport: 'Ka',
        conference_id: null,
      },
    },
  });
  if (command.operation !== 'update') throw new Error('expected update');
  const established = { ...direct, ...command.body };
  expect(customerConnectionReady(direct, [])).toBe(false);
  expect(customerConnectionReady(established, [])).toBe(true);
});
it('requires current combined bridge establishment before customer connection', () => {
  const linked = {
    ...call,
    payload: { ...call.payload, conference_id: 'bridge' },
  };
  const bridge = {
    ...record,
    record_id: 'bridge',
    record_type: 'conference' as const,
    payload: {
      ...record.payload,
      entry_type: 'conference' as const,
      status: 'established' as const,
      verified_at: null,
    },
  };
  expect(customerConnectionReady(linked, [bridge])).toBe(false);
  const checked = {
    ...bridge,
    payload: { ...bridge.payload, verified_at: '2026-10-20T11:00:00Z' },
  };
  expect(customerConnectionReady(linked, [checked])).toBe(true);
  expect(customerConnectionReady(linked, [checked], () => false)).toBe(false);
});
