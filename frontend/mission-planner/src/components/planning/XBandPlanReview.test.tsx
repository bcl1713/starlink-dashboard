/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { XBandPlanReview } from './XBandPlanReview';
import type {
  ExpectedLeg,
  PlanningDraft,
  PlanningEvaluation,
} from '../../types/planning';
afterEach(cleanup);
const leg: ExpectedLeg = {
  id: 'l',
  ordinal: 1,
  departure_airport: 'AAA',
  arrival_airport: 'BBB',
  departure_time: '2026-10-25T12:00:00Z',
  arrival_time: '2026-10-25T13:00:00Z',
};
const draft: PlanningDraft = {
  initial_x_satellite_id: 'WEST',
  permitted_satellite_ids: ['WEST'],
  locks: [],
};
function setup(
  props: Partial<React.ComponentProps<typeof XBandPlanReview>> = {}
) {
  const onChange = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <XBandPlanReview
        leg={leg}
        draft={draft}
        options={{
          satellites: [
            { id: 'WEST', label: 'West', transport: 'X', eligible: true },
          ],
        }}
        onChange={onChange}
        {...props}
      />
    </QueryClientProvider>
  );
  return onChange;
}
it('emits explicit initial lock and preserves the selected assignment', () => {
  const change = setup();
  fireEvent.click(screen.getByLabelText('Lock initial satellite'));
  expect(change).toHaveBeenCalledWith(
    expect.objectContaining({
      locks: [
        expect.objectContaining({
          kind: 'initial',
          target_satellite_id: 'WEST',
        }),
      ],
    })
  );
});
it('distinguishes policy outage, physical state, backup and safety guidance', () => {
  const evaluation = {
    context: { input_identity: 'ctx' },
    outage_seconds: 60,
    swap_count: 0,
    longest_gap_seconds: 60,
    backup_gaps: [
      {
        start_time: leg.departure_time,
        end_time: leg.arrival_time,
        reasons: ['gap'],
      },
    ],
    intervals: [
      {
        start_time: leg.departure_time,
        end_time: leg.arrival_time,
        satellite_id: 'WEST',
        physical_x_state: 'available',
        policy_x_state: 'offline',
        physical_ka_state: 'available',
        physical_ku_state: 'available',
        policy_ka_state: 'available',
        policy_ku_state: 'available',
        physical_reasons: [],
        policy_reasons: ['prefer_starshield:x_aft_cone'],
        safety_reasons: ['takeoff guidance'],
      },
    ],
  } as PlanningEvaluation;
  setup({ evaluation });
  expect(
    screen.getByText('X-band outage under Starshield preference')
  ).toBeInTheDocument();
  expect(screen.getByText(/Physical X: available/)).toBeInTheDocument();
  expect(screen.getByText(/Backup guidance/)).toBeInTheDocument();
  expect(screen.getByText(/Safety guidance/)).toBeInTheDocument();
});
