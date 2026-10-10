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
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Mission, MissionLeg } from '../types/mission';
import type { PlanningView } from '../types/planning';
vi.mock('../hooks/api/useMissions', () => ({
  useMission: vi.fn(),
  useAddLeg: () => ({}),
  useDeleteLeg: vi.fn(() => ({})),
  useActivateLeg: () => ({}),
  useDeactivateAllLegs: () => ({}),
  useDeleteMission: () => ({}),
  useUpdateMission: () => ({}),
}));
vi.mock('../hooks/api/usePlanning', () => ({ usePlanning: vi.fn() }));
vi.mock('../components/missions/MissionSimulationStatus', () => ({
  MissionSimulationStatus: () => null,
}));
vi.mock('../components/missions/AddLegDialog', () => ({
  AddLegDialog: () => null,
}));
vi.mock('../components/missions/SimulateLegDialog', () => ({
  SimulateLegDialog: () => null,
}));
import { useMission, useDeleteLeg } from '../hooks/api/useMissions';
import { usePlanning } from '../hooks/api/usePlanning';
import { MissionDetailPage } from './MissionDetailPage';
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it('renders each managed installed leg once, counts pending cards and keeps legacy actions', () => {
  const installed = (id: string, name: string): MissionLeg => ({
    id,
    name,
    route_id: id,
    transports: { initial_x_satellite_id: 'X-1' },
  });
  const mission: Mission = {
    id: 'm',
    name: 'Synthetic',
    metadata: { itinerary_planning: {} },
    created_at: '',
    updated_at: '',
    legs: [
      installed('one', 'Installed one'),
      installed('three', 'Installed three'),
      installed('legacy', 'Legacy leg'),
    ],
  };
  const view: PlanningView = {
    mission,
    revision: 7,
    expected_legs: [1, 2, 3].map((ordinal) => ({
      input_identity: 'hash',
      review_status: ordinal === 2 ? 'awaiting_kml' : 'needs_review',
      leg: {
        id: `expected-${ordinal}`,
        ordinal,
        departure_airport: 'AAA',
        arrival_airport: 'BBB',
        departure_time: '2026-10-25T12:00:00Z',
        arrival_time: '2026-10-25T13:00:00Z',
        installed_leg_id:
          ordinal === 1 ? 'one' : ordinal === 3 ? 'three' : null,
      },
    })),
  };
  vi.mocked(useMission).mockReturnValue({
    data: mission,
    isLoading: false,
  } as never);
  vi.mocked(usePlanning).mockReturnValue({
    data: view,
    isLoading: false,
  } as never);
  render(
    <MemoryRouter initialEntries={['/missions/m']}>
      <Routes>
        <Route path="/missions/:missionId" element={<MissionDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
  expect(screen.getByText('Leg 1 of 4')).toBeVisible();
  expect(screen.getByText('Leg 3 of 4')).toBeVisible();
  expect(screen.queryByText('Installed one')).toBeNull();
  expect(screen.queryByText('Installed three')).toBeNull();
  expect(screen.getByText('Legacy leg')).toBeVisible();
  expect(screen.getAllByRole('button', { name: 'Activate' })).toHaveLength(3);
  expect(screen.getAllByRole('button', { name: 'Simulate leg…' })).toHaveLength(
    3
  );
  expect(screen.getAllByRole('button', { name: 'Delete' })).toHaveLength(3);
  expect(screen.getByRole('link', { name: 'Upload KML' })).toHaveAttribute(
    'href',
    '/missions/m/legs/expected-2'
  );
});

it.each([
  { state: 'loading', isLoading: true, error: null },
  {
    state: 'failed',
    isLoading: false,
    error: new Error('Planning unavailable'),
  },
])(
  'withholds installed-leg actions when managed planning is $state',
  ({ isLoading, error }) => {
    vi.mocked(useMission).mockReturnValue({
      data: {
        id: 'm',
        name: 'Managed',
        metadata: { itinerary_planning: {} },
        legs: [{ id: 'installed', name: 'Installed managed', route_id: 'r' }],
      },
      isLoading: false,
    } as never);
    vi.mocked(usePlanning).mockReturnValue({
      data: undefined,
      isLoading,
      error,
    } as never);
    render(
      <MemoryRouter initialEntries={['/missions/m']}>
        <Routes>
          <Route path="/missions/:missionId" element={<MissionDetailPage />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Activate' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Simulate leg…' })).toBeNull();
    expect(
      screen.getByText(
        error ? /Unable to load itinerary draft/ : /Loading itinerary draft/
      )
    ).toBeVisible();
  }
);
it('keeps leg actions available for a confirmed unmanaged mission without planning data', () => {
  vi.mocked(useMission).mockReturnValue({
    data: {
      id: 'm',
      name: 'Unmanaged',
      metadata: {},
      legs: [{ id: 'legacy', name: 'Legacy', route_id: 'r' }],
    },
    isLoading: false,
  } as never);
  vi.mocked(usePlanning).mockReturnValue({
    data: undefined,
    isLoading: false,
  } as never);
  render(
    <MemoryRouter initialEntries={['/missions/m']}>
      <Routes>
        <Route path="/missions/:missionId" element={<MissionDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
  expect(screen.getByRole('button', { name: 'Delete' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Activate' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Simulate leg…' })).toBeEnabled();
});

it.each([false, true])(
  'managed Delete sends captured CAS and never retries stale=%s',
  async (stale) => {
    const leg = {
      id: 'installed',
      name: 'Leg',
      route_id: 'route',
      transports: { initial_x_satellite_id: 'X' },
    };
    const mission = {
      id: 'm',
      name: 'Synthetic',
      created_at: '',
      updated_at: '',
      metadata: { itinerary_planning: {} },
      legs: [leg],
    } as Mission;
    const view = {
      mission,
      revision: 7,
      expected_legs: [
        {
          input_identity: 'captured',
          review_status: 'needs_review',
          leg: {
            id: 'card',
            ordinal: 1,
            installed_leg_id: 'installed',
            departure_airport: 'AAA',
            arrival_airport: 'BBB',
          },
        },
      ],
    } as PlanningView;
    const remove = vi.fn();
    if (stale)
      remove.mockRejectedValue({
        response: {
          status: 409,
          data: { detail: { message: 'Reload before deleting' } },
        },
      });
    else remove.mockResolvedValue(undefined);
    vi.mocked(useDeleteLeg).mockReturnValue({ mutateAsync: remove } as never);
    vi.mocked(useMission).mockReturnValue({
      data: mission,
      isLoading: false,
    } as never);
    vi.mocked(usePlanning).mockReturnValue({
      data: view,
      isLoading: false,
    } as never);
    vi.spyOn(window, 'confirm').mockImplementation(() => {
      view.revision = 8;
      view.expected_legs[0].input_identity = 'newer';
      return true;
    });
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <MemoryRouter initialEntries={['/missions/m']}>
        <Routes>
          <Route path="/missions/:missionId" element={<MissionDetailPage />} />
        </Routes>
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() =>
      expect(remove).toHaveBeenCalledWith({
        legId: 'installed',
        planning: { expected_revision: 7, input_identity: 'captured' },
      })
    );
    if (stale) await waitFor(() => expect(window.alert).toHaveBeenCalled());
    expect(remove).toHaveBeenCalledTimes(1);
    vi.restoreAllMocks();
  }
);

it('keeps unmanaged deletion on the historical leg-ID request', async () => {
  const mission: Mission = {
    id: 'm',
    name: 'Legacy mission',
    metadata: {},
    created_at: '',
    updated_at: '',
    legs: [
      {
        id: 'legacy',
        name: 'Legacy leg',
        route_id: 'r',
        transports: { initial_x_satellite_id: 'X' },
      },
    ],
  };
  const remove = vi.fn().mockResolvedValue(undefined);
  vi.mocked(useMission).mockReturnValue({
    data: mission,
    isLoading: false,
  } as never);
  vi.mocked(usePlanning).mockReturnValue({} as never);
  vi.mocked(useDeleteLeg).mockReturnValue({ mutateAsync: remove } as never);
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  render(
    <MemoryRouter initialEntries={['/missions/m']}>
      <Routes>
        <Route path="/missions/:missionId" element={<MissionDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(remove).toHaveBeenCalledWith('legacy'));
  expect(remove).toHaveBeenCalledTimes(1);
  vi.restoreAllMocks();
});
