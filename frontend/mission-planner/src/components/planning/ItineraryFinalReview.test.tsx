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
import { ItineraryFinalReview } from './ItineraryFinalReview';
import { planningApi } from '../../services/planning';
import type { PlanningView } from '../../types/planning';
const view = {
  mission: { id: 'm', legs: [], metadata: {} },
  revision: 3,
  expected_legs: ['a', 'b'].map((id, index) => ({
    input_identity: id,
    review_status: 'needs_review',
    computation_status: 'applied',
    leg: {
      id,
      ordinal: index + 1,
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
        initial_x_satellite_id: 'X',
        starshield_enabled: true,
      },
    },
  })),
} as unknown as PlanningView;
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function setup(mapError = false) {
  const client = new QueryClient();
  client.setQueryData(['planning', 'm'], view);
  vi.spyOn(planningApi, 'previewDraft').mockResolvedValue({
    context: { input_identity: 'ctx' },
    outage_seconds: 120,
    swap_count: 0,
    longest_gap_seconds: 60,
    backup_gaps: [],
    errors: [],
    map_diagnostics: mapError
      ? [
          {
            code: 'route_timing_missing',
            message: 'Attach a timed route before publication',
            action: 'replace_route',
          },
        ]
      : [],
  });
  const publish = vi
    .spyOn(planningApi, 'publishReviewed')
    .mockResolvedValue({
      ...view,
      revision: 4,
      mission: {
        ...view.mission,
        legs: [{ id: 'installed-a' }, { id: 'installed-b' }] as never,
      },
    });
  render(
    <QueryClientProvider client={client}>
      <ItineraryFinalReview view={view} />
    </QueryClientProvider>
  );
  return { publish, client };
}
it('requires explicit plan and gap decisions then publishes the selected batch once', async () => {
  const { publish, client } = setup();
  await screen.findByText('Leg 2: 120 seconds of X-band outage');
  const button = screen.getByRole('button', { name: 'Publish reviewed plans' });
  expect(button).toBeDisabled();
  expect(publish).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByLabelText(
      'I approve the selected satellite plans and Starshield settings'
    )
  );
  expect(button).toBeDisabled();
  fireEvent.click(
    screen.getByLabelText(
      'I acknowledge the listed X-band outages and backup gaps'
    )
  );
  fireEvent.click(button);
  await waitFor(() => expect(publish).toHaveBeenCalledOnce());
  expect(publish.mock.calls[0][1].entries.map((entry) => entry.leg_id)).toEqual(
    ['a', 'b']
  );
  expect(
    publish.mock.calls[0][1].entries.every(
      (entry) =>
        entry.review.expected_revision === 3 &&
        entry.review.satellite_plan_confirmed &&
        entry.review.gap_acknowledged
    )
  ).toBe(true);
  expect(client.getQueryData<PlanningView>(['planning', 'm'])?.revision).toBe(
    4
  );
});
it('surfaces a specific map limitation before approval and blocks publication', async () => {
  const { publish } = setup(true);
  expect(
    (await screen.findAllByText('Attach a timed route before publication'))
      .length
  ).toBe(2);
  expect(
    screen.getByRole('button', { name: 'Publish reviewed plans' })
  ).toBeDisabled();
  expect(publish).not.toHaveBeenCalled();
});
