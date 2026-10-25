import { expect, it } from 'vitest';
import { planningSourceReady } from './planning-prerequisites';
import type { ExpectedLeg } from '@/types/planning';
it('unavailable_X_does_not_require_satellite_access_or_resolved_X_geometry', () => {
  const leg = {
    route: { content_hash: 'r' },
    ar_section_status: 'empty',
    ar_rows: [],
  } as unknown as ExpectedLeg;
  expect(
    planningSourceReady(
      leg,
      {
        no_ars_confirmed: true,
        unresolved_x_transitions: [
          {
            id: 'x',
            target_satellite_id: 'missing',
            latitude: 0,
            longitude: 0,
          },
        ],
      },
      'empty',
      false
    )
  ).toBe(true);
  expect(
    planningSourceReady(leg, { no_ars_confirmed: true }, 'empty', true)
  ).toBe(false);
  expect(
    planningSourceReady(leg, { no_ars_confirmed: false }, 'empty', false)
  ).toBe(false);
});
