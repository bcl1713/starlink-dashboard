/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { planningApi } from '../../services/planning';
import { routesApi } from '../../services/routes';
import type { ExpectedLegCard, PlanningView } from '../../types/planning';
vi.mock('../common/RouteMap', () => ({ RouteMap: () => null }));
import { PlanningLegReview } from './PlanningLegReview';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
const card: ExpectedLegCard = {
  input_identity: 'hash',
  review_status: 'awaiting_kml',
  leg: {
    id: 'stable-3',
    ordinal: 3,
    departure_airport: 'AAA',
    arrival_airport: 'BBB',
    departure_time: '2026-10-25T12:00:00Z',
    arrival_time: '2026-10-25T13:00:00Z',
    ar_rows: [],
    ar_section_status: 'empty',
    draft: { permitted_satellite_ids: [], starshield_enabled: true },
  },
};
const view = {
  mission: { id: 'm', legs: [] },
  revision: 7,
  expected_legs: [card],
} as unknown as PlanningView;
function setup(initial = view) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(['planning', 'm'], initial);
  vi.spyOn(planningApi, 'read').mockResolvedValue(initial);
  vi.spyOn(planningApi, 'satelliteOptions').mockResolvedValue({
    satellites: [
      {
        id: 'X-eligible',
        label: 'X eligible',
        transport: 'X',
        eligible: true,
        longitude: 10,
        latitude: 0,
      },
    ],
  });
  vi.spyOn(routesApi, 'get').mockResolvedValue({
    id: 'r',
    name: 'Synthetic route',
    points: [],
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PlanningLegReview missionId="m" legId="stable-3" />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return client;
}
it('uploads for selected expected leg and starts AR-first review after acceptance', async () => {
  const preview = vi.spyOn(planningApi, 'previewRoute').mockResolvedValue({
    preview_id: 'p',
    expected_revision: 7,
    binding: {
      route_id: 'r',
      content_hash: 'hash',
      source_id: 's',
      filename: 'other.kml',
    },
    discrepancy_errors: [{ code: 'endpoints', message: 'Endpoints differ' }],
    expires_at: '2026-10-26T12:00:00Z',
  });
  const accept = vi.spyOn(planningApi, 'acceptRoute').mockResolvedValue({
    ...view,
    revision: 8,
    expected_legs: [
      {
        ...card,
        review_status: 'needs_review',
        leg: {
          ...card.leg,
          route: {
            route_id: 'r',
            content_hash: 'hash',
            source_id: 's',
            filename: 'other.kml',
          },
        },
      },
    ],
  });
  setup();
  expect(
    screen
      .getAllByRole('tab')
      .map((tab) => tab.textContent)
      .slice(0, 2)
  ).toEqual(['AR windows', 'X-band plan']);
  const file = new File(['synthetic'], 'other.kml');
  fireEvent.change(screen.getByLabelText('KML for leg 3'), {
    target: { files: [file] },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Preview selected-leg KML' })
  );
  await screen.findByText('Endpoints differ');
  expect(screen.getByText('Accept route and review AR windows')).toBeDisabled();
  fireEvent.click(screen.getByLabelText('Acknowledge: Endpoints differ'));
  fireEvent.click(screen.getByText('Accept route and review AR windows'));
  await waitFor(() => expect(accept).toHaveBeenCalled());
  expect(preview.mock.calls[0]).toEqual(['m', 'stable-3', file, 7]);
  expect(accept.mock.calls[0][2]).toEqual({
    preview_id: 'p',
    expected_revision: 7,
    discrepancy_acknowledgments: ['endpoints'],
  });
  expect(screen.getByRole('tab', { name: 'AR windows' })).toHaveAttribute(
    'data-state',
    'active'
  );
  await waitFor(() =>
    expect(screen.getByRole('tab', { name: 'AR windows' })).toHaveFocus()
  );
});
it('preserves file/corrections on failure and explains stale draft saves', async () => {
  vi.spyOn(planningApi, 'previewRoute').mockRejectedValue(
    new Error('Invalid KML')
  );
  vi.spyOn(planningApi, 'saveDraft').mockRejectedValue(
    new Error('Stale', { cause: { response: { status: 409 } } })
  );
  setup();
  await screen.findByLabelText('Starshield enabled for this plan');
  fireEvent.click(screen.getByLabelText('Starshield enabled for this plan'));
  const file = new File(['synthetic'], 'bad.kml');
  fireEvent.change(screen.getByLabelText('KML for leg 3'), {
    target: { files: [file] },
  });
  fireEvent.click(screen.getByText('Preview selected-leg KML'));
  await screen.findByText('Invalid KML');
  expect(
    screen.getByLabelText('Starshield enabled for this plan')
  ).not.toBeChecked();
  expect(
    (screen.getByLabelText('KML for leg 3') as HTMLInputElement).files?.[0]
  ).toBe(file);
  fireEvent.click(screen.getByText('Save draft'));
  await screen.findByText(/Reload the mission before retrying/);
  expect(
    screen.getByLabelText('Starshield enabled for this plan')
  ).not.toBeChecked();
});
it('saves no-AR confirmation and per-leg operational settings, then reloads them', async () => {
  const save = vi
    .spyOn(planningApi, 'saveDraft')
    .mockImplementation(async (_m, _l, request) => ({
      ...view,
      revision: 8,
      expected_legs: [
        {
          ...card,
          leg: {
            ...card.leg,
            draft: request.draft,
            ar_section_status: request.ar_section_status ?? 'empty',
          },
        },
      ],
    }));
  const client = setup();
  await screen.findByLabelText('Starshield enabled for this plan');
  fireEvent.click(screen.getByLabelText('Starshield enabled for this plan'));
  fireEvent.click(screen.getByLabelText(/confirm no AR windows/i));
  fireEvent.click(screen.getByText('Save draft'));
  await screen.findByText('Draft saved.');
  expect(save.mock.calls[0][2]).toMatchObject({
    expected_revision: 7,
    draft: { starshield_enabled: false, no_ars_confirmed: true },
    ar_section_status: 'empty',
  });
  const stored = client.getQueryData<PlanningView>(['planning', 'm'])!;
  cleanup();
  vi.restoreAllMocks();
  setup(stored);
  expect(screen.getByLabelText(/confirm no AR windows/i)).toBeChecked();
  await screen.findByLabelText('Starshield enabled for this plan');
  expect(
    screen.getByLabelText('Starshield enabled for this plan')
  ).not.toBeChecked();
  expect(
    screen.getByRole('button', { name: 'Save reviewed plan' })
  ).toBeDisabled();
});
it('guards return/cancel and saves the revision on which local edits began', async () => {
  const save = vi.spyOn(planningApi, 'saveDraft').mockResolvedValue(view);
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const client = setup();
  await screen.findByLabelText('Starshield enabled for this plan');
  fireEvent.click(screen.getByLabelText('Starshield enabled for this plan'));
  fireEvent.click(screen.getByText('Return to mission'));
  expect(confirm).toHaveBeenCalledWith(
    'You have unsaved changes. Are you sure you want to leave?'
  );
  fireEvent.click(screen.getByText('Cancel'));
  expect(confirm).toHaveBeenCalledTimes(2);
  client.setQueryData(['planning', 'm'], { ...view, revision: 9 });
  await screen.findByText(/newer revision/);
  fireEvent.click(screen.getByText('Save draft'));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][2].expected_revision).toBe(7);
});
it('disables edits during a pending save so the response cannot overwrite new input', async () => {
  let resolveSave!: (value: PlanningView) => void;
  vi.spyOn(planningApi, 'saveDraft').mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveSave = resolve;
      })
  );
  setup();
  await screen.findByLabelText('Starshield enabled for this plan');
  fireEvent.click(screen.getByText('Save draft'));
  await screen.findByText('Saving…');
  expect(
    screen.getByLabelText('Starshield enabled for this plan')
  ).toBeDisabled();
  resolveSave(view);
  await screen.findByText('Draft saved.');
  expect(
    screen.getByLabelText('Starshield enabled for this plan')
  ).toBeEnabled();
});
