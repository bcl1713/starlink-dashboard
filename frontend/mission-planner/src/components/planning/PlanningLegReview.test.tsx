/** @vitest-environment jsdom */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  transportAvailabilityApi,
  type AvailabilityView,
} from '@/services/transportAvailability';
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
    draft: {
      permitted_satellite_ids: ['X-eligible'],
      access_confirmation: { satellite_ids: ['X-eligible'], confirmed: true },
      starshield_enabled: true,
    },
  },
};
const view = {
  mission: { id: 'm', legs: [] },
  revision: 7,
  expected_legs: [card],
} as unknown as PlanningView;
function Location() {
  return <output aria-label="Current route">{useLocation().pathname}</output>;
}
function setup(initial = view, availability?: AvailabilityView) {
  vi.spyOn(planningApi, 'generateProposal').mockImplementation(
    async (_m, _l, request) => ({
      id: 'proposal',
      expected_revision: request.expected_revision,
      input_identity: request.input_identity,
      context: { input_identity: 'context' },
      state: 'ready',
      proposed_draft: { initial_x_satellite_id: 'X-eligible' },
    })
  );
  vi.spyOn(planningApi, 'previewDraft').mockResolvedValue({
    context: { input_identity: 'context' },
    outage_seconds: 0,
    swap_count: 0,
    longest_gap_seconds: 0,
    errors: [],
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(['planning', 'm'], initial);
  if (availability) {
    client.setQueryData(['transport-availability', 'm'], availability);
    vi.spyOn(transportAvailabilityApi, 'read').mockResolvedValue(availability);
  }
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
        <Location />
        <PlanningLegReview missionId="m" legId="stable-3" />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return client;
}
it('binds the leg preview to its captured saved input identity', async () => {
  const ready = structuredClone(view);
  ready.expected_legs[0].leg.route = {
    route_id: 'r',
    source_id: 's',
    content_hash: 'route',
    filename: 'route.kml',
  };
  ready.expected_legs[0].leg.draft!.initial_x_satellite_id = 'X-eligible';
  setup(ready);
  await waitFor(() => expect(planningApi.previewDraft).toHaveBeenCalled());
  expect(vi.mocked(planningApi.previewDraft).mock.calls[0][2]).toMatchObject({
    input_identity: 'hash',
  });
  const signal = vi.mocked(planningApi.previewDraft).mock.calls[0][3];
  expect(signal?.aborted).toBe(false);
  cleanup();
  expect(signal?.aborted).toBe(true);
});
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
  await waitFor(() =>
    expect(planningApi.generateProposal).not.toHaveBeenCalled()
  );
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

it('keeps manual work after stale Apply and only re-optimizes explicitly', async () => {
  const bound = {
    ...view,
    expected_legs: [
      {
        ...card,
        leg: {
          ...card.leg,
          route: {
            route_id: 'r',
            content_hash: 'hash',
            source_id: 's',
            filename: 'r.kml',
          },
          draft: {
            permitted_satellite_ids: ['X-eligible'],
            initial_x_satellite_id: 'X-eligible',
            starshield_enabled: true,
            no_ars_confirmed: true,
            access_confirmation: {
              satellite_ids: ['X-eligible'],
              confirmed: true,
            },
          },
        },
      },
    ],
  } as PlanningView;
  const save = vi
    .spyOn(planningApi, 'saveDraft')
    .mockImplementation(async (_m, _l, request) => ({
      ...bound,
      revision: 8,
      expected_legs: [
        {
          ...bound.expected_legs[0],
          input_identity: 'saved',
          leg: { ...bound.expected_legs[0].leg, draft: request.draft },
        },
      ],
    }));
  vi.spyOn(planningApi, 'applyProposal').mockRejectedValue({
    response: { status: 409 },
  });
  setup(bound);
  fireEvent.mouseDown(screen.getByRole('tab', { name: 'X-band plan' }), {
    button: 0,
    ctrlKey: false,
  });
  await screen.findByLabelText('Lock initial satellite');
  fireEvent.click(screen.getByLabelText('Lock initial satellite'));
  expect(planningApi.generateProposal).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Re-optimize' }));
  await screen.findByRole('button', { name: 'Apply proposal' });
  expect(save).toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Apply proposal' }));
  await screen.findByText(/Your entered corrections are preserved here/);
  expect(screen.getByLabelText('Lock initial satellite')).toBeChecked();
});

it('saves reviewed plan and selects the next unbound expected leg', async () => {
  const bound = {
    ...view,
    expected_legs: [
      {
        ...card,
        leg: {
          ...card.leg,
          route: {
            route_id: 'r',
            source_id: 's',
            content_hash: 'h',
            filename: 'r.kml',
          },
          draft: {
            permitted_satellite_ids: ['X-eligible'],
            initial_x_satellite_id: 'X-eligible',
            access_confirmation: {
              satellite_ids: ['X-eligible'],
              confirmed: true,
            },
            starshield_enabled: true,
            no_ars_confirmed: true,
          },
        },
      },
      { ...card, leg: { ...card.leg, id: 'next', ordinal: 4 } },
    ],
  } as PlanningView;
  const reviewed = vi
    .spyOn(planningApi, 'saveReviewed')
    .mockResolvedValue({ ...bound, revision: 8 });
  setup(bound);
  await screen.findByLabelText(
    'I confirm this satellite plan and Starshield enablement'
  );
  fireEvent.click(
    screen.getByLabelText(
      'I confirm this satellite plan and Starshield enablement'
    )
  );
  const button = screen.getByRole('button', {
    name: 'Save reviewed plan and upload next leg',
  });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await waitFor(() =>
    expect(screen.getByLabelText('Current route')).toHaveTextContent(
      '/missions/m/legs/next'
    )
  );
  expect(reviewed.mock.calls[0][2]).toMatchObject({
    expected_revision: 7,
    input_identity: 'hash',
    satellite_plan_confirmed: true,
    no_ars_confirmed: true,
  });
});

it('persists pre-upload manual edits without generating an implicit proposal', async () => {
  const initial = {
    ...view,
    expected_legs: [
      {
        ...card,
        leg: {
          ...card.leg,
          draft: {
            permitted_satellite_ids: ['X-eligible'],
            access_confirmation: {
              satellite_ids: ['X-eligible'],
              confirmed: true,
            },
            starshield_enabled: true,
          },
        },
      },
    ],
  } as PlanningView;
  const binding = {
    route_id: 'r',
    content_hash: 'hash',
    source_id: 's',
    filename: 'r.kml',
  };
  vi.spyOn(planningApi, 'previewRoute').mockResolvedValue({
    preview_id: 'p',
    expected_revision: 7,
    binding,
    expires_at: '2026-10-26T12:00:00Z',
  });
  vi.spyOn(planningApi, 'acceptRoute').mockResolvedValue({
    ...initial,
    revision: 8,
    expected_legs: [
      {
        ...initial.expected_legs[0],
        leg: { ...initial.expected_legs[0].leg, route: binding },
      },
    ],
  });
  const save = vi
    .spyOn(planningApi, 'saveDraft')
    .mockImplementation(async (_m, _l, r) => ({
      ...initial,
      revision: 9,
      expected_legs: [
        {
          ...initial.expected_legs[0],
          input_identity: 'merged',
          leg: {
            ...initial.expected_legs[0].leg,
            route: binding,
            draft: r.draft,
          },
        },
      ],
    }));
  setup(initial);
  await screen.findByLabelText('Starshield enabled for this plan');
  fireEvent.click(screen.getByLabelText('Starshield enabled for this plan'));
  fireEvent.change(screen.getByLabelText('KML for leg 3'), {
    target: { files: [new File(['synthetic'], 'r.kml')] },
  });
  fireEvent.click(screen.getByText('Preview selected-leg KML'));
  await screen.findByText('Accept route and review AR windows');
  fireEvent.click(screen.getByText('Accept route and review AR windows'));
  await waitFor(() =>
    expect(planningApi.generateProposal).not.toHaveBeenCalled()
  );
  expect(save.mock.calls[0][2]).toMatchObject({
    expected_revision: 8,
    draft: { starshield_enabled: false },
  });
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
it('guards return/cancel and saves unchanged leg inputs at the newest observed revision', async () => {
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
  expect(save.mock.calls[0][2].expected_revision).toBe(9);
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

it('disables draft edits during deferred route acceptance and enables them after the response', async () => {
  let resolveAccept!: (value: PlanningView) => void;
  const binding = {
    route_id: 'r',
    content_hash: 'hash',
    source_id: 's',
    filename: 'accepted.kml',
  };
  vi.spyOn(planningApi, 'previewRoute').mockResolvedValue({
    preview_id: 'p',
    expected_revision: 7,
    binding,
    expires_at: '2026-10-26T12:00:00Z',
  });
  const accept = vi.spyOn(planningApi, 'acceptRoute').mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveAccept = resolve;
      })
  );
  const save = vi.spyOn(planningApi, 'saveDraft').mockResolvedValue(view);
  setup();
  await screen.findByLabelText('Starshield enabled for this plan');
  fireEvent.change(screen.getByLabelText('KML for leg 3'), {
    target: { files: [new File(['synthetic'], 'accepted.kml')] },
  });
  fireEvent.click(screen.getByText('Preview selected-leg KML'));
  await screen.findByText('Accept route and review AR windows');
  fireEvent.click(screen.getByText('Accept route and review AR windows'));
  await waitFor(() => expect(accept).toHaveBeenCalled());
  expect(
    screen.getByLabelText('Starshield enabled for this plan')
  ).toBeDisabled();
  expect(screen.getByLabelText('AR section correction')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  resolveAccept({
    ...view,
    revision: 8,
    expected_legs: [{ ...card, leg: { ...card.leg, route: binding } }],
  });
  await screen.findByText('Route accepted. Review AR windows first.');
  expect(
    screen.getByLabelText('Starshield enabled for this plan')
  ).toBeEnabled();
  fireEvent.click(screen.getByLabelText('Starshield enabled for this plan'));
  fireEvent.click(screen.getByText('Save draft'));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][2]).toMatchObject({
    expected_revision: 8,
    draft: { starshield_enabled: false },
  });
});

it.each([false, true])(
  'freezes explicit reload throughout a deferred response (dirty=%s)',
  async (dirty) => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const client = setup();
    const control = await screen.findByLabelText(
      'Starshield enabled for this plan'
    );
    await waitFor(() =>
      expect(client.isFetching({ queryKey: ['planning', 'm'] })).toBe(0)
    );
    if (dirty) fireEvent.click(control);
    let resolveRead!: (value: PlanningView) => void;
    vi.mocked(planningApi.read).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRead = resolve;
        })
    );
    fireEvent.click(screen.getByRole('button', { name: 'Reload saved draft' }));
    await waitFor(() => expect(resolveRead).toBeDefined());
    expect(control).toBeDisabled();
    act(() => (control as HTMLInputElement).click());
    expect((control as HTMLInputElement).checked).toBe(!dirty);
    expect(confirm).toHaveBeenCalledTimes(dirty ? 1 : 0);
    resolveRead(view);
    await screen.findByText('Saved draft reloaded.');
    expect(control).toBeEnabled();
    expect(control).toBeChecked();
    act(() => (control as HTMLInputElement).click());
    expect(control).not.toBeChecked();
  }
);

it('preserves dirty edits when reload fails despite retained query data', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
  const client = setup();
  const control = await screen.findByLabelText(
    'Starshield enabled for this plan'
  );
  await waitFor(() =>
    expect(client.isFetching({ queryKey: ['planning', 'm'] })).toBe(0)
  );
  fireEvent.click(control);
  let rejectRead!: (error: Error) => void;
  vi.mocked(planningApi.read).mockImplementationOnce(
    () =>
      new Promise((_resolve, reject) => {
        rejectRead = reject;
      })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Reload saved draft' }));
  await waitFor(() => expect(rejectRead).toBeDefined());
  rejectRead(new Error('Reload connection failed'));
  await waitFor(() =>
    expect(client.getQueryState(['planning', 'm'])?.status).toBe('error')
  );
  expect(client.getQueryData(['planning', 'm'])).toEqual(view);
  await screen.findByText('Reload connection failed');
  expect(screen.queryByText('Saved draft reloaded.')).not.toBeInTheDocument();
  expect(control).toBeEnabled();
  expect(control).not.toBeChecked();
  confirm.mockReturnValue(false);
  fireEvent.click(screen.getByText('Cancel'));
  expect(confirm).toHaveBeenLastCalledWith(
    'You have unsaved changes. Are you sure you want to leave?'
  );
});

it('exposes managed Update Route with cancel and retains installed route until reviewed save', async () => {
  const installed = structuredClone(view);
  installed.expected_legs[0].leg.route = {
    route_id: 'old',
    source_id: 'old',
    content_hash: 'oldhash',
    filename: 'old.kml',
  };
  installed.expected_legs[0].leg.installed_leg_id = 'installed';
  setup(installed);
  const stage = vi.spyOn(planningApi, 'previewRoute').mockResolvedValue({
    preview_id: 'p',
    expected_revision: 7,
    binding: {
      route_id: 'new',
      source_id: 'new',
      content_hash: 'newhash',
      filename: 'new.kml',
    },
    expires_at: '2099-01-01T00:00:00Z',
    discrepancy_errors: [],
  });
  const accept = vi.spyOn(planningApi, 'acceptRoute');
  fireEvent.click(screen.getByRole('button', { name: 'Update Route' }));
  fireEvent.change(screen.getByLabelText('KML for leg 3'), {
    target: { files: [new File(['synthetic'], 'new.kml')] },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Preview selected-leg KML' })
  );
  await waitFor(() => expect(stage).toHaveBeenCalled());
  fireEvent.click(
    screen.getByRole('button', { name: 'Cancel route replacement' })
  );
  expect(accept).not.toHaveBeenCalled();
  expect(screen.getByText('Accepted route: old.kml')).toBeVisible();
  expect(planningApi.generateProposal).not.toHaveBeenCalled();
});

it('keeps replacement preview and local corrections when acceptance CAS is stale', async () => {
  const installed = structuredClone(view);
  installed.expected_legs[0].leg.route = {
    route_id: 'old',
    source_id: 'old',
    content_hash: 'oldhash',
    filename: 'old.kml',
  };
  setup(installed);
  vi.spyOn(planningApi, 'previewRoute').mockResolvedValue({
    preview_id: 'p',
    expected_revision: 7,
    binding: {
      route_id: 'new',
      source_id: 'new',
      content_hash: 'newhash',
      filename: 'new.kml',
    },
    expires_at: '2099-01-01T00:00:00Z',
    discrepancy_errors: [{ code: 'different', message: 'Times differ' }],
  });
  const accept = vi
    .spyOn(planningApi, 'acceptRoute')
    .mockRejectedValue({ response: { status: 409 } });
  fireEvent.change(screen.getByLabelText('KML for leg 3'), {
    target: { files: [new File(['synthetic'], 'new.kml')] },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Preview selected-leg KML' })
  );
  const acknowledgment = await screen.findByLabelText(
    'Acknowledge: Times differ'
  );
  expect(
    screen.getByRole('button', { name: 'Accept route and review AR windows' })
  ).toBeDisabled();
  fireEvent.click(acknowledgment);
  fireEvent.click(
    screen.getByRole('button', { name: 'Accept route and review AR windows' })
  );
  await screen.findByText(/Planning state changed/);
  expect(accept).toHaveBeenCalledWith('m', 'stable-3', {
    preview_id: 'p',
    expected_revision: 7,
    discrepancy_acknowledgments: ['different'],
  });
  expect(screen.getByText('Accepted route: old.kml')).toBeVisible();
  expect(acknowledgment).toBeChecked();
  expect(planningApi.generateProposal).not.toHaveBeenCalled();
});

it.each(['ready', 'stale identity', 'older generation revision'])(
  'resumes persisted %s proposal on mount and explicit reload without generation or application',
  async (state) => {
    const reference = {
      id: 'persisted',
      leg_id: card.leg.id,
      expected_revision: 7,
      input_identity: 'hash',
      state: 'ready',
    };
    const persisted = {
      id: 'persisted',
      expected_revision: state === 'older generation revision' ? 6 : 7,
      input_identity: state === 'stale identity' ? 'old' : 'hash',
      context: { input_identity: 'context' },
      state: 'ready' as const,
      proposed_draft: { initial_x_satellite_id: 'X-eligible' },
    };
    const read = vi
      .spyOn(planningApi, 'readProposal')
      .mockResolvedValue(persisted);
    const apply = vi.spyOn(planningApi, 'applyProposal');
    setup({
      ...view,
      mission: {
        ...view.mission,
        metadata: { itinerary_planning: { proposal_refs: [reference] } },
      },
    });
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'X-band plan' }), {
      button: 0,
      ctrlKey: false,
    });
    await screen.findByRole('region', { name: 'Proposal comparison' });
    expect(
      screen.getByRole('button', { name: 'Apply proposal' })
    ).toHaveProperty('disabled', state === 'stale identity');
    if (state === 'stale identity')
      expect(screen.getByText(/Proposal is stale/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: /Reload saved draft/ }));
    await waitFor(() => expect(read).toHaveBeenCalledTimes(2));
    expect(planningApi.generateProposal).not.toHaveBeenCalled();
    expect(apply).not.toHaveBeenCalled();
  }
);

it('keeps edits made while a persisted proposal retrieval is pending and marks it stale', async () => {
  let resolve!: (
    value: Awaited<ReturnType<typeof planningApi.readProposal>>
  ) => void;
  vi.spyOn(planningApi, 'readProposal').mockReturnValue(
    new Promise((done) => {
      resolve = done;
    })
  );
  setup({
    ...view,
    mission: {
      ...view.mission,
      metadata: {
        itinerary_planning: {
          proposal_refs: [
            {
              id: 'persisted',
              leg_id: card.leg.id,
              expected_revision: 7,
              input_identity: 'hash',
              state: 'ready',
            },
          ],
        },
      },
    },
  });
  fireEvent.mouseDown(screen.getByRole('tab', { name: 'X-band plan' }), {
    button: 0,
    ctrlKey: false,
  });
  await screen.findByLabelText('Starshield enabled for this plan');
  fireEvent.click(screen.getByLabelText('Starshield enabled for this plan'));
  await act(async () =>
    resolve({
      id: 'persisted',
      expected_revision: 7,
      input_identity: 'hash',
      context: { input_identity: 'context' },
      state: 'ready',
      proposed_draft: { starshield_enabled: true },
    })
  );
  expect(screen.getByLabelText(/Starshield enabled/i)).not.toBeChecked();
  expect(screen.getByText(/Proposal is stale/)).toBeVisible();
  expect(planningApi.generateProposal).not.toHaveBeenCalled();
});

it.each(['Apply', 'Save'] as const)(
  'ignores an obsolete preview conflict after %s and keeps the accepted draft usable',
  async (mutation) => {
    const bound = structuredClone(view);
    bound.expected_legs[0].leg.route = {
      route_id: 'r',
      source_id: 's',
      content_hash: 'hash',
      filename: 'r.kml',
    };
    bound.expected_legs[0].leg.draft = {
      ...card.leg.draft,
      initial_x_satellite_id: 'X-eligible',
      no_ars_confirmed: true,
    };
    bound.mission.metadata = {
      itinerary_planning: {
        proposal_refs: [
          { id: 'persisted', leg_id: card.leg.id, state: 'ready' },
        ],
      },
    };
    vi.spyOn(planningApi, 'readProposal').mockResolvedValue({
      id: 'persisted',
      expected_revision: 7,
      input_identity: 'hash',
      context: { input_identity: 'context' },
      state: 'ready',
      proposed_draft: {
        ...bound.expected_legs[0].leg.draft,
        starshield_enabled: false,
      },
    });
    if (mutation === 'Save')
      bound.expected_legs[0].leg.draft!.starshield_enabled = false;
    const accepted = structuredClone(bound);
    accepted.revision = 8;
    accepted.expected_legs[0].input_identity = 'accepted';
    accepted.expected_legs[0].leg.draft!.starshield_enabled = false;
    const apply = vi
      .spyOn(planningApi, 'applyProposal')
      .mockResolvedValue(accepted);
    const save = vi
      .spyOn(planningApi, 'saveDraft')
      .mockResolvedValue({ ...accepted, revision: 9 });
    if (mutation === 'Save') save.mockResolvedValueOnce(accepted);
    setup(bound);
    let rejectObsolete!: (error: unknown) => void;
    vi.mocked(planningApi.previewDraft).mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectObsolete = reject;
        })
    );
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'X-band plan' }), {
      button: 0,
      ctrlKey: false,
    });
    await screen.findByRole('button', { name: 'Apply proposal' });
    await waitFor(() => expect(rejectObsolete).toBeDefined());
    expect(
      vi.mocked(planningApi.previewDraft).mock.calls[0][2].expected_revision
    ).toBe(7);
    fireEvent.click(
      screen.getByRole('button', {
        name: mutation === 'Apply' ? 'Apply proposal' : 'Save draft',
      })
    );
    await screen.findByText(
      mutation === 'Apply'
        ? 'Proposal applied to the draft. Review availability before saving.'
        : 'Draft saved.'
    );
    await waitFor(() =>
      expect(planningApi.previewDraft).toHaveBeenCalledTimes(2)
    );
    expect(vi.mocked(planningApi.previewDraft).mock.calls[1][2]).toMatchObject({
      expected_revision: 8,
      draft: { starshield_enabled: false },
    });
    await act(async () => rejectObsolete({ response: { status: 409 } }));
    expect(
      screen.queryByText(/Planning state changed/)
    ).not.toBeInTheDocument();
    expect(
      screen.getByLabelText('Starshield enabled for this plan')
    ).not.toBeChecked();
    expect(
      screen.getByLabelText('Starshield enabled for this plan')
    ).toBeEnabled();
    if (mutation === 'Apply')
      expect(
        screen.queryByRole('button', { name: 'Apply proposal' })
      ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByLabelText(
        'I confirm this satellite plan and Starshield enablement'
      )
    );
    expect(
      screen.getByRole('button', { name: 'Save reviewed plan' })
    ).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() =>
      expect(save).toHaveBeenCalledTimes(mutation === 'Apply' ? 1 : 2)
    );
    expect(save.mock.calls.at(-1)![2]).toMatchObject({
      expected_revision: 8,
      draft: { starshield_enabled: false },
    });
    expect(apply).toHaveBeenCalledTimes(mutation === 'Apply' ? 1 : 0);
    expect(planningApi.generateProposal).not.toHaveBeenCalled();
  }
);

it('route acceptance does not optimize before AR review', async () => {
  vi.spyOn(planningApi, 'previewRoute').mockResolvedValue({
    preview_id: 'p',
    expected_revision: 7,
    binding: {
      route_id: 'r',
      source_id: 's',
      content_hash: 'hash',
      filename: 'route.kml',
    },
    discrepancy_errors: [],
    expires_at: '2030-01-01T00:00:00Z',
  });
  vi.spyOn(planningApi, 'acceptRoute').mockResolvedValue({
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
            source_id: 's',
            content_hash: 'hash',
            filename: 'route.kml',
          },
        },
      },
    ],
  });
  setup();
  fireEvent.change(screen.getByLabelText('KML for leg 3'), {
    target: { files: [new File(['kml'], 'route.kml')] },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Preview selected-leg KML' })
  );
  await screen.findByRole('button', {
    name: 'Accept route and review AR windows',
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Accept route and review AR windows' })
  );
  await screen.findByText('Accepted route: route.kml');
  expect(planningApi.generateProposal).not.toHaveBeenCalled();
  fireEvent.mouseDown(screen.getByRole('tab', { name: 'X-band plan' }), {
    button: 0,
    ctrlKey: false,
  });
  expect(screen.getByRole('button', { name: 'Generate plans' })).toBeDisabled();
});

it('autosaves source prerequisites without a Save click or implicit generation', async () => {
  const bound = structuredClone(view);
  bound.expected_legs[0].leg.route = {
    route_id: 'r',
    source_id: 's',
    content_hash: 'hash',
    filename: 'route.kml',
  };
  const save = vi
    .spyOn(planningApi, 'saveDraft')
    .mockImplementation(async (_m, _l, request) => ({
      ...bound,
      revision: 8,
      expected_legs: [
        {
          ...bound.expected_legs[0],
          input_identity: 'saved',
          leg: { ...bound.expected_legs[0].leg, draft: request.draft },
        },
      ],
    }));
  setup(bound);
  fireEvent.click(await screen.findByLabelText(/confirm no AR windows/i));
  await waitFor(() => expect(save).toHaveBeenCalledOnce());
  expect(save.mock.calls[0][2].draft.no_ars_confirmed).toBe(true);
  expect(planningApi.generateProposal).not.toHaveBeenCalled();
});
it('does not blindly retry a failed autosave and retains the edited prerequisite', async () => {
  const save = vi
    .spyOn(planningApi, 'saveDraft')
    .mockRejectedValue({ response: { status: 409 } });
  setup();
  const input = await screen.findByLabelText(
    'Starshield enabled for this plan'
  );
  vi.useFakeTimers();
  try {
    fireEvent.click(input);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600);
    });
    expect(save).toHaveBeenCalledOnce();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(save).toHaveBeenCalledOnce();
    expect(input).not.toBeChecked();
    expect(
      screen.getByText(/Your entered corrections are preserved here/)
    ).toBeVisible();
  } finally {
    vi.useRealTimers();
  }
});

it('reviews_a_wholly_failed_X_leg_without_satellites_or_extra_confirmation', async () => {
  const ready = structuredClone(view);
  const leg = ready.expected_legs[0].leg;
  leg.route = {
    route_id: 'r',
    source_id: 's',
    content_hash: 'route',
    filename: 'route.kml',
  };
  leg.draft = {
    no_ars_confirmed: true,
    permitted_satellite_ids: [],
    access_confirmation: null,
    initial_x_satellite_id: null,
  };
  const availability: AvailabilityView = {
    mission_id: 'm',
    revision: 1,
    defaults: {},
    leg_overrides: {},
    history: [],
    simulation_run_id: null,
    as_of: '2026-10-25T12:00:00Z',
    active_leg_id: null,
    effective: null,
    operator_actions_allowed: false,
    operator_actions_unavailable_reason: 'No active leg',
    legs: [
      {
        leg_id: 'stable-3',
        planned: { X: true, Ka: true, Ku: true },
        effective: { X: false, Ka: true, Ku: true },
        overrides: {},
        x_configuration_required: false,
      },
    ],
  };
  setup(ready, availability);
  const save = vi
    .spyOn(planningApi, 'saveReviewed')
    .mockResolvedValue({ ...ready, revision: 8 });
  await waitFor(() => expect(planningApi.previewDraft).toHaveBeenCalled());
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Save reviewed plan' })
    ).toBeEnabled()
  );
  expect(screen.queryByLabelText(/I confirm this satellite plan/)).toBeNull();
  expect(screen.queryByLabelText(/I confirm service access/)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Save reviewed plan' }));
  await waitFor(() =>
    expect(save).toHaveBeenCalledWith(
      'm',
      'stable-3',
      expect.objectContaining({ satellite_plan_confirmed: false })
    )
  );
});

it('simulation_only_failure_does_not_waive_canonical_live_X_prerequisites', async () => {
  const ready = structuredClone(view);
  ready.expected_legs[0].leg.route = {
    route_id: 'r',
    source_id: 's',
    content_hash: 'route',
    filename: 'route.kml',
  };
  ready.expected_legs[0].leg.draft = {
    no_ars_confirmed: true,
    permitted_satellite_ids: [],
    initial_x_satellite_id: null,
  };
  setup(ready, {
    mission_id: 'm',
    revision: 1,
    defaults: {},
    leg_overrides: {},
    history: [],
    simulation_run_id: 'simulation',
    as_of: '2026-10-25T12:00:00Z',
    active_leg_id: null,
    effective: null,
    operator_actions_allowed: false,
    operator_actions_unavailable_reason: 'Inactive',
    legs: [
      {
        leg_id: 'stable-3',
        planned: { X: true, Ka: true, Ku: true },
        effective: { X: false, Ka: true, Ku: true },
        planning_effective: { X: true, Ka: true, Ku: true },
        overrides: {},
        x_configuration_required: true,
      },
    ],
  });
  await screen.findByText(
    /Select permitted X-band satellites before optimization/
  );
  expect(
    screen.getByRole('button', { name: 'Save reviewed plan' })
  ).toBeDisabled();
  expect(planningApi.previewDraft).not.toHaveBeenCalled();
});
