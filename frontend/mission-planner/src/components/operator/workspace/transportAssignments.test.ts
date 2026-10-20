import { expect, it } from 'vitest';
import { record } from '@/test/operator-fixtures';
import { assignmentInput, latestAssignment } from './transportAssignments';

it('records IDs, names and active association without carrying checks', () => {
  const input = assignmentInput(
    'mission-a',
    { id: 'svc', name: 'Data' },
    { id: 'path', name: 'Terrestrial' },
    '2026-10-19T12:00:00Z',
    {
      scope: 'leg',
      leg_id: 'leg-a',
      previous_leg_id: null,
      next_leg_id: null,
      label: 'Leg 1',
    }
  );
  expect(input.leg_id).toBe('leg-a');
  expect(input.payload.services[0]).toMatchObject({
    service_id: 'svc',
    service: 'Data',
    checked: null,
    applied: { transport_id: 'path', transport: 'Terrestrial' },
  });
  const first = { ...record, ...input, journal_seq: 1 };
  const second = {
    ...first,
    record_id: 'second',
    journal_seq: 2,
    payload: {
      ...input.payload,
      services: [
        {
          ...input.payload.services[0],
          applied: {
            transport: 'X',
            time: { at: null, precision: 'unknown' as const },
          },
        },
      ],
    },
  };
  expect(
    latestAssignment([first, second], { id: 'svc', name: 'Renamed' }, 'leg-a')
      ?.transport
  ).toBe('X');
  expect(
    latestAssignment([second, first], { id: 'svc', name: 'Renamed' }, 'leg-a')
      ?.transport
  ).toBe('X');
  expect(
    latestAssignment([first], { id: 'svc', name: 'Renamed' }, 'leg-b')
  ).toBeNull();
});
