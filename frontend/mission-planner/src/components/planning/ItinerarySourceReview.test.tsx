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
import { ItinerarySourceReview } from './ItinerarySourceReview';
import { planningApi } from '../../services/planning';
import { routesApi } from '../../services/routes';
import type { PlanningView } from '../../types/planning';
vi.mock('../common/RouteMap', () => ({ RouteMap: () => null }));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('autosaves two source reviews through the shared queue without losing either leg', async () => {
  let view = {
    mission: { id: 'm', legs: [], metadata: {} },
    revision: 1,
    expected_legs: ['a', 'b'].map((id, index) => ({
      input_identity: id,
      review_status: 'needs_review',
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
          starshield_enabled: true,
          no_ars_confirmed: false,
        },
      },
    })),
  } as unknown as PlanningView;
  const client = new QueryClient();
  client.setQueryData(['planning', 'm'], view);
  vi.spyOn(planningApi, 'satelliteOptions').mockResolvedValue({
    satellites: [
      {
        id: 'X',
        label: 'X',
        transport: 'X',
        eligible: true,
        longitude: 0,
        latitude: 0,
      },
    ],
  });
  vi.spyOn(routesApi, 'get').mockResolvedValue({
    id: 'r',
    name: 'Synthetic',
    points: [],
  });
  const generate = vi.spyOn(planningApi, 'generateProposal');
  const save = vi
    .spyOn(planningApi, 'saveDraft')
    .mockImplementation(async (_m, leg, request) => {
      expect(request.expected_revision).toBe(view.revision);
      view = {
        ...view,
        revision: view.revision + 1,
        expected_legs: view.expected_legs.map((card) =>
          card.leg.id === leg
            ? {
                ...card,
                input_identity: leg + '-saved',
                leg: { ...card.leg, draft: request.draft },
              }
            : card
        ),
      };
      return view;
    });
  render(
    <QueryClientProvider client={client}>
      <ItinerarySourceReview view={view} />
    </QueryClientProvider>
  );
  const inputs = await screen.findAllByLabelText(/confirm no AR windows/i);
  fireEvent.click(inputs[0]);
  fireEvent.click(inputs[1]);
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls.map((call) => call[2].expected_revision)).toEqual([
    1, 2,
  ]);
  const persisted = client.getQueryData<PlanningView>(['planning', 'm'])!;
  expect(
    persisted.expected_legs.map((card) => card.leg.draft?.no_ars_confirmed)
  ).toEqual([true, true]);
  expect(generate).not.toHaveBeenCalled();
});
