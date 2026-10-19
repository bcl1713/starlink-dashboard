/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { OperatorWorkspace } from './OperatorWorkspace';
import { OperatorWorkspaceProvider } from './OperatorWorkspaceProvider';
import { DraftRegistry } from './draftRegistry';
import * as api from '@/services/operator';
import * as eventsApi from '@/services/operatorEvents';
import { health, page } from '@/test/operator-fixtures';
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
function mount(route = '/operator?workspace=1', ready = false) {
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
  vi.spyOn(eventsApi, 'readEventSnapshot').mockRejectedValue(
    new Error('Optional feed unavailable')
  );
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue({
    ...health,
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
          <OperatorWorkspace />
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
