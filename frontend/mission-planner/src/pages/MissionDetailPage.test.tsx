/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Mission, MissionLeg } from '../types/mission';
import type { PlanningView } from '../types/planning';
vi.mock('../hooks/api/useMissions', () => ({
  useMission: vi.fn(),
  useAddLeg: () => ({}),
  useDeleteLeg: () => ({}),
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
import { useMission } from '../hooks/api/useMissions';
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
  expect(
    screen.getAllByRole('button', { name: 'Delete' })
  ).toHaveLength(1);
  expect(screen.getByRole('link', { name: 'Upload KML' })).toHaveAttribute(
    'href',
    '/missions/m/legs/expected-2'
  );
});
