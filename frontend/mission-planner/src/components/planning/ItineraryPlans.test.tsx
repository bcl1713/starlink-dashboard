/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { planningApi } from '../../services/planning';
import type { PlanningProposal, PlanningView } from '../../types/planning';
import { ItineraryPlans } from './ItineraryPlans';

const initial = {
  mission: { id: 'm', legs: [], metadata: {} },
  revision: 1,
  expected_legs: ['a', 'b'].map((id) => ({
    input_identity: id,
    review_status: 'needs_review',
    leg: {
      id,
      ordinal: id === 'a' ? 1 : 2,
      departure_airport: 'AAA',
      arrival_airport: 'BBB',
      departure_time: '2026-10-25T12:00:00Z',
      arrival_time: '2026-10-25T13:00:00Z',
      ar_section_status: 'empty',
      ar_rows: [],
      route: {
        route_id: id,
        source_id: id,
        content_hash: id,
        filename: id + '.kml',
      },
      draft: {
        permitted_satellite_ids: ['X'],
        access_confirmation: { satellite_ids: ['X'], confirmed: true },
        no_ars_confirmed: true,
        starshield_enabled: true,
      },
    },
  })),
} as unknown as PlanningView;
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function setup(view = initial) {
  const client = new QueryClient();
  client.setQueryData(['planning', 'm'], view);
  vi.spyOn(planningApi, 'read').mockResolvedValue(view);
  vi.spyOn(planningApi, 'readProposal').mockImplementation(
    async (_m, _l, id) => ({
      id,
      expected_revision: 1,
      input_identity: _l,
      state: 'ready',
      context: { input_identity: 'ctx' },
      proposed_draft: { initial_x_satellite_id: 'X' },
    })
  );
  const generate = vi
    .spyOn(planningApi, 'generateProposal')
    .mockImplementation(async (_m, leg, request) => ({
      id: leg + '-proposal',
      expected_revision: request.expected_revision,
      input_identity: request.input_identity,
      state: 'ready',
      context: { input_identity: 'ctx' },
      proposed_draft: { initial_x_satellite_id: 'X' },
    }));
  const apply = vi
    .spyOn(planningApi, 'applyProposals')
    .mockResolvedValue({ ...view, revision: 2 });
  render(
    <QueryClientProvider client={client}>
      <ItineraryPlans view={view} />
    </QueryClientProvider>
  );
  return { generate, apply };
}
it('one deliberate action generates ready legs and one explicit action applies selected plans', async () => {
  const { generate, apply } = setup();
  fireEvent.click(
    await screen.findByRole('button', { name: 'Generate plans' })
  );
  await screen.findByText('Leg 2: ready');
  expect(generate.mock.calls.map((call) => call[1])).toEqual(['a', 'b']);
  expect(apply).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Apply selected plans' }));
  await waitFor(() => expect(apply).toHaveBeenCalledOnce());
  expect(apply.mock.calls[0][1].entries.map((entry) => entry.leg_id)).toEqual([
    'a',
    'b',
  ]);
});
it('retries only failed legs while retaining successful comparisons', async () => {
  const { generate } = setup();
  let failed = true;
  generate.mockImplementation(async (_m, leg, request) => {
    if (leg === 'b' && failed) {
      failed = false;
      throw new Error('worker failed');
    }
    return {
      id: leg + '-proposal',
      expected_revision: request.expected_revision,
      input_identity: request.input_identity,
      state: 'ready',
      context: { input_identity: 'ctx' },
      proposed_draft: { initial_x_satellite_id: 'X' },
    } as PlanningProposal;
  });
  fireEvent.click(
    await screen.findByRole('button', { name: 'Generate plans' })
  );
  await screen.findByText(/Leg 2: failed/);
  fireEvent.click(screen.getByRole('button', { name: 'Retry failed legs' }));
  await screen.findByText('Leg 2: ready');
  expect(generate.mock.calls.map((call) => call[1])).toEqual(['a', 'b', 'b']);
  expect(
    screen.getAllByRole('region', { name: 'Proposal comparison' })
  ).toHaveLength(2);
});
it('blocks first generation until every selected source prerequisite is reviewed', async () => {
  const changed = structuredClone(initial);
  changed.expected_legs[1].leg.draft!.no_ars_confirmed = false;
  const { generate } = setup(changed);
  expect(
    await screen.findByRole('button', { name: 'Generate plans' })
  ).toBeDisabled();
  expect(generate).not.toHaveBeenCalled();
});
