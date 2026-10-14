/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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
    <>
      <output>Review {legId}</output>
      <input aria-label="Local managed correction" defaultValue="" />
    </>
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

it('keeps the managed editor mounted when refetch fails with retained planning data', () => {
  vi.mocked(useMission).mockReturnValue({
    data: { id: 'm', legs: [], metadata: { itinerary_planning: {} } },
    isLoading: false,
  } as never);
  const saved = {
    data: { expected_legs: [{ leg: { id: 'expected' } }] },
    isLoading: false,
  };
  vi.mocked(usePlanning).mockReturnValue(saved as never);
  const page = () => (
    <MemoryRouter initialEntries={['/missions/m/legs/expected']}>
      <Routes>
        <Route
          path="/missions/:missionId/legs/:legId"
          element={<LegDetailPage />}
        />
      </Routes>
    </MemoryRouter>
  );
  const mounted = render(page());
  const control = screen.getByLabelText('Local managed correction');
  fireEvent.change(control, { target: { value: 'Keep local AR correction' } });
  vi.mocked(usePlanning).mockReturnValue({
    ...saved,
    error: new Error('Reload failed'),
  } as never);
  mounted.rerender(page());
  expect(screen.getByLabelText('Local managed correction')).toBe(control);
  expect(control).toHaveValue('Keep local AR correction');
});

it('keeps editing unavailable when the initial planning load fails without data', () => {
  vi.mocked(useMission).mockReturnValue({
    data: { id: 'm', legs: [], metadata: { itinerary_planning: {} } },
    isLoading: false,
  } as never);
  vi.mocked(usePlanning).mockReturnValue({
    data: undefined,
    isLoading: false,
    error: new Error('Initial load failed'),
  } as never);
  render(
    <MemoryRouter initialEntries={['/missions/m/legs/expected']}>
      <Routes>
        <Route
          path="/missions/:missionId/legs/:legId"
          element={<LegDetailPage />}
        />
      </Routes>
    </MemoryRouter>
  );
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Unable to resolve the expected leg'
  );
  expect(
    screen.queryByLabelText('Local managed correction')
  ).not.toBeInTheDocument();
});
