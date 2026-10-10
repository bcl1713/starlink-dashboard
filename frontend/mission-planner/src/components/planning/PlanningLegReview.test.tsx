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
function setup(initial = view) {
  vi.spyOn(planningApi, 'generateProposal').mockResolvedValue({
    id: 'proposal',
    expected_revision: 8,
    input_identity: 'hash',
    context: { input_identity: 'context' },
    state: 'ready',
    proposed_draft: { initial_x_satellite_id: 'X-eligible' },
  });
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
    expect(planningApi.generateProposal).toHaveBeenCalledTimes(1)
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

it('persists pre-upload manual edits before the one initial proposal', async () => {
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
    expect(planningApi.generateProposal).toHaveBeenCalledOnce()
  );
  expect(save.mock.calls[0][2]).toMatchObject({
    expected_revision: 8,
    draft: { starshield_enabled: false },
  });
  expect(
    vi.mocked(planningApi.generateProposal).mock.calls[0][2]
  ).toMatchObject({ expected_revision: 9, input_identity: 'merged' });
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
  await screen.findByText(
    'Route accepted. Review AR windows and compare the initial proposal before Apply.'
  );
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
  const stage = vi
    .spyOn(planningApi, 'previewRoute')
    .mockResolvedValue({
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
