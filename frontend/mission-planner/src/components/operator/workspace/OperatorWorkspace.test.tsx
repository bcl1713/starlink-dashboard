/** @vitest-environment jsdom */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { OperatorJournalPage } from '@/pages/OperatorJournalPage';
import { OperatorWorkspaceProvider } from './OperatorWorkspaceProvider';
import { DraftRegistry } from './draftRegistry';
import { conferenceDraft } from '../conferenceCommands';
import { callDraft } from '../callDraft';
import * as api from '@/services/operator';
import * as eventsApi from '@/services/operatorEvents';
import {
  transportAvailabilityApi,
  type AvailabilityView,
} from '@/services/transportAvailability';
import * as timelineApi from '@/services/missionTimeline';
import { eventSnapshot, eventFixture } from '@/test/operator-event-fixtures';
import { health, page, record } from '@/test/operator-fixtures';
const missionState = vi.hoisted(() => ({
  pending: false,
  error: false,
  retry: vi.fn(),
  mission: undefined as
    | undefined
    | { id: string; name: string; legs: { id: string; name: string }[] },
}));
vi.mock('@/hooks/api/useMissions', () => ({
  useMission: () => ({
    data: missionState.mission,
    isPending: missionState.pending,
    isError: missionState.error,
    refetch: missionState.retry,
  }),
  useMissionsPage: () => ({ data: { missions: [] } }),
}));
const clients: QueryClient[] = [];
afterEach(() => {
  missionState.mission = undefined;
  missionState.pending = false;
  missionState.error = false;
  missionState.retry.mockReset();
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  sessionStorage.clear();
  localStorage.clear();
  vi.restoreAllMocks();
});
function mount(route = '/operator', ready = false, source = health) {
  if (!vi.isMockFunction(api.readOperatingContext))
    vi.spyOn(api, 'readOperatingContext').mockResolvedValue({
      state: 'no_active_mission',
      mission_id: null,
      mission_name: null,
      leg_id: null,
      leg_name: null,
      phase: null,
      source_mode: 'live',
      replay_run_id: null,
    });
  if (!vi.isMockFunction(timelineApi.readMissionTimeline))
    vi.spyOn(timelineApi, 'readMissionTimeline').mockRejectedValue(
      new Error('Optional timeline unavailable')
    );
  if (!vi.isMockFunction(eventsApi.readEventSnapshot))
    vi.spyOn(eventsApi, 'readEventSnapshot').mockRejectedValue(
      new Error('Optional feed unavailable')
    );
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue({
    ...source,
    ready,
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  const registry = new DraftRegistry(sessionStorage);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <OperatorWorkspaceProvider registry={registry}>
          <OperatorJournalPage />
        </OperatorWorkspaceProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { client, registry };
}
it('renders a cold workspace before any training context or checked evidence exists', () => {
  mount();
  expect(screen.getByRole('button', { name: 'Help' })).toBeTruthy();
  expect(
    screen.getByRole('heading', { name: 'Choose a mission' })
  ).toBeTruthy();
});
it('explains separate nonproduction setup instead of opening training in an ordinary instance', () => {
  mount();
  fireEvent.click(screen.getByRole('button', { name: 'Help' }));
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Guided mission walkthrough',
    })
  );
  expect(
    screen.getByText(/Training requires a separate private instance/)
  ).toBeTruthy();
  expect(
    screen.queryByRole('complementary', { name: 'Guided mission walkthrough' })
  ).toBeNull();
});

it('waits for selected mission identity before enabling the guide launcher', () => {
  missionState.pending = true;
  mount('/operator?workspace=1&mission_id=loading-private-mission');
  fireEvent.click(screen.getByRole('button', { name: 'Help' }));
  const button = screen.getByRole('button', {
    name: 'Guided mission walkthrough',
  }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  expect(
    screen.getByText(
      'Checking the selected mission and private training identity…'
    )
  ).toBeTruthy();
});
it('offers an explicit failed mission read retry without treating it as an unmarked training instance', () => {
  missionState.error = true;
  mount('/operator?workspace=1&mission_id=unavailable-private-mission');
  fireEvent.click(screen.getByRole('button', { name: 'Help' }));
  expect(
    (
      screen.getByRole('button', {
        name: 'Guided mission walkthrough',
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true);
  expect(screen.getByText(/Mission details could not be loaded/)).toBeTruthy();
  fireEvent.click(
    screen.getByRole('button', { name: 'Retry mission details' })
  );
  expect(missionState.retry).toHaveBeenCalledTimes(1);
  expect(
    screen.queryByText(/Training requires a separate private instance/)
  ).toBeNull();
});

it('links the selected mission to its existing Missions records destination', () => {
  mount('/operator?workspace=1&mission_id=mission%20%2F%20one');
  expect(
    screen.getByRole('link', { name: 'Mission records' }).getAttribute('href')
  ).toBe('/missions/mission%20%2F%20one');
});

it.each(['live', 'simulation'] as const)(
  'automatically follows %s mission and leg while preserving a parked draft and historical override',
  async (mode) => {
    missionState.mission = {
      id: 'active',
      name: 'Active mission',
      legs: [
        { id: 'a', name: 'First leg' },
        { id: 'b', name: 'Second leg' },
      ],
    };
    let active = {
      state: 'available',
      mission_id: 'active',
      mission_name: 'Active mission',
      leg_id: 'a',
      leg_name: 'First leg',
      phase: 'in_flight',
      source_mode: mode,
      replay_run_id: mode === 'simulation' ? 'run-a' : null,
    };
    vi.spyOn(api, 'readOperatingContext').mockImplementation(
      async () => active
    );
    vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
    const { client, registry } = mount('/operator?workspace=1', true);
    await waitFor(() =>
      expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe(
        'active'
      )
    );
    fireEvent.click(screen.getByRole('button', { name: 'Note' }));
    await waitFor(() => expect(registry.listDrafts()).toHaveLength(1));
    const original = registry.listDrafts()[0];
    expect(original.target.legId).toBe('a');
    active = { ...active, leg_id: 'b', leg_name: 'Second leg' };
    await client.invalidateQueries({
      queryKey: ['operator-operating-context'],
    });
    await waitFor(() =>
      expect(screen.getByLabelText('Operating context').textContent).toContain(
        'Second leg'
      )
    );
    expect(registry.listDrafts()[0].target.legId).toBe('a');
    // Closing parks the draft; a new note follows the new active leg.
    fireEvent.click(
      screen.getByRole('button', { name: 'Keep draft and return' })
    );
    fireEvent.click(screen.getByRole('button', { name: 'Note' }));
    expect(
      registry
        .listDrafts()
        .map((draft) => draft.target.legId)
        .sort()
    ).toEqual(['a', 'b']);
    fireEvent.click(
      screen.getByRole('button', { name: 'Keep draft and return' })
    );
    vi.mocked(api.readOperatingContext).mockRejectedValue(
      new Error('Mission source offline')
    );
    await client.invalidateQueries({
      queryKey: ['operator-operating-context'],
    });
    await waitFor(() =>
      expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('')
    );
    expect(registry.listDrafts()).toHaveLength(2);
  }
);

it('preserves deliberate historical browsing across active mission changes and returns to automatic selection on request', async () => {
  let active = {
    state: 'available',
    mission_id: 'active',
    mission_name: 'Active mission',
    leg_id: 'a',
    leg_name: 'First',
    phase: 'in_flight',
    source_mode: 'live' as const,
    replay_run_id: null,
  };
  vi.spyOn(api, 'readOperatingContext').mockImplementation(async () => active);
  const { client } = mount('/operator?workspace=1&mission_id=historical');
  await waitFor(() =>
    expect(screen.getByLabelText('Operating context').textContent).toContain(
      'Active mission'
    )
  );
  active = {
    ...active,
    mission_id: 'next-mission',
    mission_name: 'Next mission',
  };
  await client.invalidateQueries({ queryKey: ['operator-operating-context'] });
  await waitFor(() =>
    expect(screen.getByLabelText('Operating context').textContent).toContain(
      'Next mission'
    )
  );
  expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe(
    'historical'
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Return to active mission' })
  );
  expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe(
    'next-mission'
  );
});

it('renders newly accepted and older ordinary-Activate conference definitions without historical clone buttons', async () => {
  missionState.mission = {
    id: 'mission-a',
    name: 'Fictional mission',
    legs: [{ id: 'leg-1', name: 'Outbound' }],
  };
  const source = {
    ...health,
    source_mode: 'simulation' as const,
    mission_journal: true,
    simulation_run_id: 'default',
    replay_run_id: null,
    operating_context_id: 'ordinary:runtime:1:route',
  };
  vi.spyOn(api, 'readOperatingContext').mockResolvedValue({
    state: 'available',
    mission_id: 'mission-a',
    mission_name: 'Fictional mission',
    leg_id: 'leg-1',
    leg_name: 'Outbound',
    phase: 'pre_departure',
    source_mode: 'simulation',
    replay_run_id: null,
    operating_context_id: source.operating_context_id,
  });
  const accepted = {
    ...record,
    ...conferenceDraft('mission-a'),
    payload: { ...conferenceDraft('mission-a').payload, title: 'CABLES' },
    provenance: {
      ...record.provenance,
      source_mode: 'simulation' as const,
      replay_run_id: null,
      operating_context_id: source.operating_context_id,
    },
  };
  const older = {
    ...accepted,
    record_id: 'older-conference',
    payload: { ...accepted.payload, title: 'Existing accepted conference' },
    provenance: { ...accepted.provenance, operating_context_id: null },
  };
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(
    page([accepted, older])
  );
  mount(
    '/operator?workspace=1&mission_id=mission-a&view=communications',
    true,
    source
  );
  await screen.findByRole('heading', { name: /CABLES/ });
  expect(
    screen.getByRole('heading', { name: /Existing accepted conference/ })
  ).toBeTruthy();
  expect(screen.queryByText(/No conferences recorded/)).toBeNull();
  expect(screen.queryByRole('button', { name: /Reuse definition/ })).toBeNull();
});

it.each(['now', 'communications'])(
  'shows prominent active call and bridge sections in %s',
  async (view) => {
    vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
    mount(`/operator?workspace=1&mission_id=mission-a&view=${view}`, true);
    expect(
      await screen.findByRole('heading', { name: 'Active Calls' })
    ).toBeTruthy();
    expect(
      screen.getByRole('heading', { name: 'Active Bridges' })
    ).toBeTruthy();
    if (view === 'now') {
      const headings = screen
        .getAllByRole('heading')
        .map((heading) => heading.textContent);
      expect(headings).toContain('Active Bridges');
      expect(headings).toContain('Mission timeline');
      expect(headings).not.toContain('Mission activity');
    }
  }
);

it('shows pending immediately and the authoritative accepted conference while list refresh is still waiting', async () => {
  missionState.mission = {
    id: 'mission-a',
    name: 'Fictional mission',
    legs: [],
  };
  let acknowledged = false;
  let accept!: (value: {
    schema_version: 1;
    command_id: string;
    saved_records: (typeof accepted)[];
  }) => void;
  const accepted = {
    ...record,
    ...conferenceDraft('mission-a'),
    payload: { ...conferenceDraft('mission-a').payload, title: 'FAST BRIDGE' },
  };
  const releaseReads: (() => void)[] = [];
  const reads = vi
    .spyOn(api, 'readOperatorRecords')
    .mockImplementation(async () => {
      if (acknowledged)
        await new Promise<void>((resolve) => releaseReads.push(resolve));
      return page([]);
    });
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(
    page([accepted]).items[0]
  );
  const save = vi.spyOn(api, 'saveOperatorCommand').mockImplementation(
    () =>
      new Promise((resolve) => {
        accept = resolve;
      })
  );
  const { client } = mount(
    '/operator?workspace=1&mission_id=mission-a&view=communications',
    true
  );
  const createButton = (
    await screen.findAllByRole('button', { name: 'Create conference' })
  )[0] as HTMLButtonElement;
  await waitFor(() => expect(createButton.disabled).toBe(false));
  fireEvent.click(createButton);
  fireEvent.change(await screen.findByLabelText('Conference name (optional)'), {
    target: { value: 'FAST BRIDGE' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save conference' }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  expect(
    screen.getAllByText(/saving.*FAST BRIDGE|FAST BRIDGE.*saving/).length
  ).toBeGreaterThan(0);
  expect(screen.queryByRole('heading', { name: 'FAST BRIDGE' })).toBeNull();
  const started = performance.now();
  try {
    await act(async () => {
      acknowledged = true;
      accept({
        schema_version: 1,
        command_id: 'fast-receipt',
        saved_records: [accepted],
      });
    });
    await screen.findByRole('heading', { name: 'FAST BRIDGE' });
    expect(performance.now() - started).toBeLessThan(300);
    expect(save).toHaveBeenCalledTimes(1);
    expect(releaseReads.length).toBeGreaterThan(0);
    await waitFor(() =>
      expect(
        (screen.getByRole('button', { name: 'Establish' }) as HTMLButtonElement)
          .disabled
      ).toBe(false)
    );
    const snapshot = client
      .getQueryCache()
      .findAll({ queryKey: ['operator-records', 'mission-a'] })
      .find(
        (query) =>
          query.queryKey[3] === 'workspace-all' &&
          query.state.data !== undefined
      )?.state.data;
    expect(snapshot).toMatchObject({ pages: [{ items: [] }] });
    expect(reads).toHaveBeenCalled();
  } finally {
    await act(async () => {
      releaseReads.forEach((resolve) => resolve());
    });
  }
});

it('offers manual destination in Now without a mission or ready operator journal', async () => {
  const { manualDestinationApi } = await import(
    '@/services/manual-destination'
  );
  vi.spyOn(manualDestinationApi, 'get').mockResolvedValue({
    destination: null,
  });
  mount('/operator', false);
  expect(
    await screen.findByRole('region', { name: 'Manual destination' })
  ).toBeTruthy();
  const save = await screen.findByRole('button', { name: 'Save destination' });
  expect((save as HTMLButtonElement).disabled).toBe(false);
  expect(screen.getByLabelText('Destination name')).toBeTruthy();
});

it('keeps_now_view_availability_actions_usable_with_the_journal_disabled', async () => {
  const state: AvailabilityView = {
    mission_id: 'mission-a',
    revision: 0,
    defaults: {},
    leg_overrides: {},
    history: [],
    simulation_run_id: null,
    as_of: '2026-10-25T12:00:00Z',
    active_leg_id: 'l',
    effective: { X: true, Ka: true, Ku: true },
    operator_actions_allowed: true,
    operator_actions_unavailable_reason: null,
    legs: [],
  };
  vi.spyOn(transportAvailabilityApi, 'read').mockResolvedValue(state);
  const action = vi
    .spyOn(transportAvailabilityApi, 'action')
    .mockResolvedValue({ ...state, revision: 1 });
  mount('/operator?workspace=1&mission_id=mission-a&view=now', false, {
    ...health,
    enabled: false,
  });
  const row = await screen.findByRole('group', { name: 'X-band availability' });
  const button = within(row).getByRole('button', {
    name: 'Unavailable for rest of mission',
  });
  expect(button).toHaveProperty('disabled', false);
  fireEvent.click(button);
  await waitFor(() =>
    expect(action).toHaveBeenCalledWith(
      'mission-a',
      expect.objectContaining({
        transport: 'X',
        action: 'unavailable',
        expected_simulation_run_id: null,
      })
    )
  );
});
it('opens the referenced call from the mission timeline', async () => {
  const input = callDraft(undefined, 'planned', 'mission-a');
  const call = {
    ...record,
    ...input,
    time: { ...record.time, planned_start_at: '2026-10-17T17:00:00Z' },
    payload: {
      ...input.payload,
      title: 'Specific briefing',
      status: 'scheduled' as const,
      prep_lead_minutes: 10,
    },
  };
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([call]));
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page([call]).items[0]);
  vi.spyOn(timelineApi, 'readMissionTimeline').mockResolvedValue({
    ...eventSnapshot({
      events: [
        eventFixture({ title: 'Briefing due', source_ref: call.record_id }),
      ],
    }),
    legs: [],
  });
  const { registry } = mount('/operator?mission_id=mission-a', true);
  await screen.findByText('Specific briefing');
  const row = (await screen.findByText('Briefing due')).closest('li')!;
  fireEvent.click(within(row).getByText('Details'));
  fireEvent.click(within(row).getByRole('button', { name: 'Open source' }));
  await screen.findByRole('dialog', { name: 'Edit call' });
  expect(registry.listDrafts()[0].target.recordId).toBe(call.record_id);
  expect(registry.listDrafts()[0].input.payload.title).toBe(
    'Specific briefing'
  );
});

it('keeps the full timeline across operating views and retains the editor draft', async () => {
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  vi.spyOn(timelineApi, 'readMissionTimeline').mockResolvedValue({
    ...eventSnapshot({
      events: [
        eventFixture({ title: 'Persistent X window', kind: 'restriction' }),
      ],
    }),
    legs: [],
  });
  const { registry } = mount('/operator?mission_id=mission-a', true);
  await screen.findByText('Persistent X window');
  for (const view of ['Communications', 'Transport', 'Issues', 'Now']) {
    fireEvent.click(screen.getByRole('button', { name: view }));
    expect(
      screen.getByRole('region', { name: 'Mission timeline' })
    ).toBeTruthy();
    expect(screen.getByText('Persistent X window')).toBeTruthy();
    expect(
      screen.queryByRole('region', { name: 'Mission activity' })
    ).toBeNull();
  }
  fireEvent.click(screen.getByRole('button', { name: 'Note' }));
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Unsaved mission note' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Keep draft and return' })
  );
  const draft = registry.listDrafts()[0];
  expect(draft.input.payload.title).toBe('Unsaved mission note');
  fireEvent.click(screen.getByRole('button', { name: 'Transport' }));
  expect(registry.listDrafts()[0].input.payload.title).toBe(
    'Unsaved mission note'
  );
  expect(screen.getByText('Persistent X window')).toBeTruthy();
});

it('keeps optional alert acknowledgment and pending reconciliation available in its drawer', async () => {
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  vi.spyOn(eventsApi, 'readEventSnapshot').mockResolvedValue(eventSnapshot());
  sessionStorage.setItem(
    'operator-event-pending:mission-a',
    JSON.stringify({
      missionId: 'mission-a',
      identity: JSON.stringify(['store', 'epoch-a', 'live', null]),
      epoch: 'epoch-a',
      key: 'retained-key',
      body: {
        schema_version: 1,
        occurrence_id: 'occurrence-a',
        severity_generation: 2,
        snapshot_token: 'snapshot-token',
      },
    })
  );
  mount('/operator?mission_id=mission-a&view=transport', true);
  fireEvent.click(
    screen.getByRole('button', { name: 'Open operational alerts' })
  );
  const drawer = await screen.findByRole('dialog', {
    name: 'Operational Alerts',
  });
  expect(
    await within(drawer).findByRole('button', { name: 'Acknowledge' })
  ).toBeTruthy();
  expect(
    within(drawer).getByRole('button', { name: 'Retry acknowledgment' })
  ).toBeTruthy();
  expect(
    within(drawer).getByRole('button', { name: 'Dismiss request and refresh' })
  ).toBeTruthy();
});
