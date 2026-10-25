/** @vitest-environment jsdom */
vi.mock('../hooks/api/useTransportAvailability', () => ({
  useTransportAvailability: () => ({ data: undefined }),
}));
vi.mock('../components/planning/TransportAvailabilityControls', () => ({
  TransportAvailabilityControls: () => null,
}));
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import type { TransportConfig } from '../types/mission';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
vi.mock('../hooks/api/useMissions', () => ({
  useMission: vi.fn(),
  useUpdateLeg: () => ({ isPending: false, mutateAsync: saveLeg }),
  useUpdateLegRoute: () => ({ isPending: false }),
}));
vi.mock('../hooks/api/useTimeline', () => ({
  useTimeline: () => ({ data: undefined }),
}));
vi.mock('../hooks/api/useTimelinePreview', () => ({
  useTimelinePreview: vi.fn(() => ({
    preview: null,
    isCalculating: false,
    error: null,
  })),
}));
vi.mock('./LegDetailPage/useLegData', () => ({
  useLegData: ({ legTransports }: { legTransports?: TransportConfig }) => ({
    satelliteConfig: {
      xband_starting_satellite: legTransports?.initial_x_satellite_id,
      xband_transitions: legTransports?.x_transitions ?? [],
      ka_outages: legTransports?.ka_outages ?? [],
      ku_outages: legTransports?.ku_overrides ?? [],
    },
    aarConfig: {
      segments: legTransports?.aar_windows ?? [],
      manualTracks: legTransports?.manual_aar_tracks ?? [],
    },
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
vi.mock('./LegDetailPage/LegConfigTabs', async () => {
  const actual = await vi.importActual<
    typeof import('./LegDetailPage/LegConfigTabs')
  >('./LegDetailPage/LegConfigTabs');
  return {
    LegConfigTabs: (
      props: React.ComponentProps<typeof actual.LegConfigTabs>
    ) => (
      <>
        <actual.LegConfigTabs {...props} />
        <button
          onClick={() =>
            void props.onManualTrackSave({
              id: 'track',
              name: 'Manual track',
              points: [
                { latitude: 0, longitude: 0 },
                { latitude: 1, longitude: 1 },
              ],
            })
          }
        >
          Save manual track fixture
        </button>
      </>
    ),
  };
});
import { useTimelinePreview } from '../hooks/api/useTimelinePreview';
import { useMission } from '../hooks/api/useMissions';
import { usePlanning } from '../hooks/api/usePlanning';
import { LegDetailPage } from './LegDetailPage';
const saveLeg = vi.hoisted(() => vi.fn());
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

it.each([false, true])(
  'preserves Starshield enablement %s when saving an imported leg',
  async (enabled) => {
    saveLeg.mockResolvedValue({});
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    vi.mocked(useMission).mockReturnValue({
      data: {
        id: 'm',
        metadata: {},
        legs: [
          {
            id: 'imported',
            route_id: 'r',
            name: 'Imported',
            transports: {
              initial_x_satellite_id: 'WGS4',
              starshield_enabled: enabled,
            },
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
      <MemoryRouter initialEntries={['/missions/m/legs/imported']}>
        <Routes>
          <Route
            path="/missions/:missionId/legs/:legId"
            element={<LegDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    );
    fireEvent.click(screen.getByText('Save Changes'));
    expect(saveLeg).toHaveBeenCalledWith(
      expect.objectContaining({
        transports: expect.objectContaining({ starshield_enabled: enabled }),
      })
    );
  }
);

it.each(['preview', 'save', 'manual-track'])(
  'preserves captured planning policy and context in the %s transport projection',
  async (operation) => {
    saveLeg.mockResolvedValue({});
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    const anchor = {
      route_id: 'r',
      content_hash: 'c'.repeat(64),
      segment_index: 0,
      fraction: 0.5,
      occurrence_id: 'middle',
      source_time: '2035-01-01T00:30:00Z',
      latitude: 0,
      longitude: 0,
    };
    const transports = {
      x_transitions: [
        {
          id: 'swap',
          latitude: 0,
          longitude: 0,
          target_satellite_id: 'X-2',
          anchor,
        },
      ],
      aar_windows: [
        {
          id: 'ar',
          start_waypoint_name: 'IN',
          end_waypoint_name: 'OUT',
          start_anchor: anchor,
          end_anchor: { ...anchor, fraction: 0.6 },
        },
      ],
      initial_x_satellite_id: 'X-1',
      starshield_enabled: true,
      planning_policy: 'prefer_starshield_v1',
      evaluation_context: { input_identity: 'captured-input' },
      planning_inputs: {
        route_json: '{}',
        anchor_route_json: '{}',
        structural_draft_json: '{}',
        constraints_json: '{}',
        start_time: '2035-01-01T00:00:00Z',
        end_time: '2035-01-01T01:00:00Z',
        satellites: [],
        starshield_enabled: true,
      },
    };
    const original = structuredClone(transports);
    vi.mocked(useMission).mockReturnValue({
      data: {
        id: 'm',
        metadata: {},
        legs: [
          {
            id: 'canonical',
            name: 'Captured policy',
            route_id: 'r',
            transports,
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
      <MemoryRouter initialEntries={['/missions/m/legs/canonical']}>
        <Routes>
          <Route
            path="/missions/:missionId/legs/:legId"
            element={<LegDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    );
    if (operation === 'preview') {
      expect(
        vi.mocked(useTimelinePreview).mock.calls.at(-1)?.[2]?.transports
      ).toEqual(expect.objectContaining(original));
    } else {
      fireEvent.click(
        screen.getByText(
          operation === 'save' ? 'Save Changes' : 'Save manual track fixture'
        )
      );
      await waitFor(() =>
        expect(saveLeg).toHaveBeenCalledWith(
          expect.objectContaining({
            transports: expect.objectContaining(original),
          })
        )
      );
    }
    expect(transports).toEqual(original);
  }
);
