/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
vi.mock('../hooks/api/useMissions', () => ({
  useMission: vi.fn(),
  useUpdateLeg: () => ({ isPending: false }),
  useUpdateLegRoute: () => ({ isPending: false }),
}));
vi.mock('../hooks/api/useTimeline', () => ({
  useTimeline: () => ({ data: undefined }),
}));
vi.mock('../hooks/api/useTimelinePreview', () => ({
  useTimelinePreview: () => ({
    preview: null,
    isCalculating: false,
    error: null,
  }),
}));
vi.mock('./LegDetailPage/useLegData', () => ({
  useLegData: () => ({
    satelliteConfig: { xband_transitions: [], ka_outages: [], ku_outages: [] },
    aarConfig: { segments: [], manualTracks: [] },
    routeCoordinates: [],
    availableWaypoints: [],
    waypointNames: [],
    availableSatellites: [],
    kaTransitions: [],
    hasUnsavedChanges: false,
    setSatelliteConfig: vi.fn(),
    setAARConfig: vi.fn(),
    setHasUnsavedChanges: vi.fn(),
  }),
}));
vi.mock('../hooks/api/usePlanning', () => ({ usePlanning: vi.fn() }));
vi.mock('../components/planning/PlanningLegReview', () => ({
  PlanningLegReview: ({ legId }: { legId: string }) => (
    <output>Review {legId}</output>
  ),
}));
import { useMission } from '../hooks/api/useMissions';
import { usePlanning } from '../hooks/api/usePlanning';
import { LegDetailPage } from './LegDetailPage';
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it.each(['expected', 'installed'])(
  'resolves %s IDs from manifest before requiring executable MissionLeg data',
  (id) => {
    vi.mocked(useMission).mockReturnValue({
      data: { id: 'm', legs: [], metadata: { itinerary_planning: {} } },
      isLoading: false,
    } as never);
    vi.mocked(usePlanning).mockReturnValue({
      data: {
        expected_legs: [
          { leg: { id: 'expected', installed_leg_id: 'installed' } },
        ],
      },
      isLoading: false,
    } as never);
    render(
      <MemoryRouter initialEntries={[`/missions/m/legs/${id}`]}>
        <Routes>
          <Route
            path="/missions/:missionId/legs/:legId"
            element={<LegDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('Review expected')).toBeVisible();
  }
);
it('keeps unmanaged legs on the existing manual controls and name-based AR flow', () => {
  vi.mocked(useMission).mockReturnValue({
    data: {
      id: 'm',
      metadata: {},
      legs: [
        {
          id: 'manual',
          route_id: 'r',
          name: 'Manual',
          transports: { initial_x_satellite_id: 'X-1' },
        },
      ],
    },
    isLoading: false,
  } as never);
  vi.mocked(usePlanning).mockReturnValue({
    data: undefined,
    isLoading: false,
  } as never);
  render(
    <MemoryRouter initialEntries={['/missions/m/legs/manual']}>
      <Routes>
        <Route
          path="/missions/:missionId/legs/:legId"
          element={<LegDetailPage />}
        />
      </Routes>
    </MemoryRouter>
  );
  expect(screen.getByText('Leg Configuration')).toBeVisible();
  expect(screen.getByRole('tab', { name: 'X-Band' })).toBeVisible();
  expect(screen.getByRole('tab', { name: 'AAR Segments' })).toBeVisible();
  expect(screen.getByText('Save Changes')).toBeVisible();
  expect(screen.queryByText('Review manual')).toBeNull();
  expect(vi.mocked(usePlanning).mock.calls[0]).toEqual(['m', false]);
});
