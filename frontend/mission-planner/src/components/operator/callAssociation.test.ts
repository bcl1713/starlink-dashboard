import { expect, it } from 'vitest';
import { inferCallAssociation } from './callAssociation';
const legs = [
  {
    id: 'a',
    name: 'Outbound',
    start: '2026-10-20T10:00:00Z',
    end: '2026-10-20T12:00:00Z',
  },
  {
    id: 'b',
    name: 'Return',
    start: '2026-10-20T14:00:00Z',
    end: '2026-10-20T16:00:00Z',
  },
];
it('infers the itinerary phase at the selected UTC time', () => {
  expect(inferCallAssociation(legs, '2026-10-20T09:00:00Z')).toMatchObject({
    scope: 'preflight',
    leg_id: null,
  });
  expect(inferCallAssociation(legs, '2026-10-20T11:00:00Z')).toMatchObject({
    scope: 'leg',
    leg_id: 'a',
  });
  expect(inferCallAssociation(legs, '2026-10-20T13:00:00Z')).toMatchObject({
    scope: 'between_legs',
    previous_leg_id: 'a',
    next_leg_id: 'b',
  });
  expect(inferCallAssociation(legs, '2026-10-20T17:00:00Z')).toMatchObject({
    scope: 'postflight',
  });
});
it('does not guess with missing, overlapping or invalid timing', () => {
  expect(inferCallAssociation([], null)).toBeNull();
  expect(
    inferCallAssociation([{ ...legs[0], end: null }], legs[0].start)
  ).toBeNull();
  expect(
    inferCallAssociation(
      [legs[0], { ...legs[1], start: legs[0].start }],
      legs[0].start
    )
  ).toBeNull();
  expect(
    inferCallAssociation([{ ...legs[0], end: legs[0].start }], legs[0].start)
  ).toBeNull();
});
