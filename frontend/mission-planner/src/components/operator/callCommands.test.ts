import { expect, it } from 'vitest';
import { record } from '@/test/operator-fixtures';
import { callDraft } from './callDraft';
import { callCommand, callTestReported } from './callCommands';
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
