/** @vitest-environment jsdom */
import {
  cleanup,
  render as renderTesting,
  screen,
  within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
function render(node: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return renderTesting(node, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
const queries = vi.hoisted(() => ({
  status: {} as Record<string, unknown>,
  history: {} as Record<string, unknown>,
  satellites: {} as Record<string, unknown>,
  selection: {} as Record<string, unknown>,
  routes: {} as Record<string, unknown>,
  route: {} as Record<string, unknown>,
  pois: {} as Record<string, unknown>,
  links: {} as Record<string, unknown>,
  adsb: { contacts: [] as ReturnType<typeof projectAdsbContacts> },
}));
// WebGL is an external renderer; this suite exercises real DOM overlays with
// independently controlled API states. Scene rendering has browser coverage.
vi.mock('@/hooks/useOverviewAdsbLayer', () => ({
  useOverviewAdsbLayer: () => queries.adsb,
}));
vi.mock('@react-three/fiber', () => ({ Canvas: () => null }));
vi.mock('@react-three/drei', () => ({
  Html: () => null,
  CameraControls: () => null,
  CameraControlsImpl: class {},
  Stars: () => null,
}));
vi.mock('./OverviewMetricHistoryPanels', () => ({
  OverviewMetricHistoryPanels: () => null,
}));
vi.mock('@/hooks/useCurrentTime', () => ({
  useCurrentTime: () => Date.parse('2026-10-02T00:00:00Z'),
}));
vi.mock('../hooks/api/useRoutes', () => ({
  useRoutes: () => queries.routes,
  useRoute: () => queries.route,
}));
vi.mock('@/hooks/api/useStatus', () => ({ useStatus: () => queries.status }));
vi.mock('@/hooks/api/useOverviewHistory', () => ({
  useOverviewHistory: () => queries.history,
}));
vi.mock('@/hooks/api/useSatellites', () => ({
  useSatellites: () => queries.satellites,
}));
vi.mock('@/hooks/api/useActiveXLink', () => ({
  useActiveXLink: () => queries.selection,
}));
vi.mock('@/hooks/api/useOverviewLinkSettings', () => ({
  useOverviewLinkSettings: () => queries.links,
}));
vi.mock('@/hooks/api/useOverviewClockSettings', () => ({
  useOverviewClockSettings: () => ({ data: { clocks: [] } }),
}));
vi.mock('@/hooks/api/useOverviewHistorySettings', () => ({
  useOverviewHistorySettings: () => ({ data: { window_seconds: 300 } }),
}));
vi.mock('@/hooks/api/useUpdateOverviewHistorySettings', () => ({
  useUpdateOverviewHistorySettings: () => ({ mutate: vi.fn() }),
}));
vi.mock('@/hooks/api/useOverviewUpcomingPois', () => ({
  useOverviewUpcomingPois: () => queries.pois,
}));
import { OverviewPage } from './OverviewPage';
import { ADSB_NOW, adsbContact, adsbSettings } from '@/test/adsb-fixtures';
import { projectAdsbContacts } from './adsb/overview-adsb-state';
afterEach(cleanup);
beforeEach(() => {
  queries.adsb.contacts = [];
  queries.links = {
    data: { starshield_link_enabled: true, x_band_link_enabled: true },
  };
  queries.status = {
    data: {
      timestamp: '2026-10-02T00:00:00Z',
      position: { latitude: 0, longitude: 0, altitude: 35000 },
      ground_entry_point: { latitude: 0, longitude: 0 },
    },
  };
  queries.history = { data: { series: {} } };
  queries.satellites = {
    data: [{ satellite_id: 'X-6', transport: 'X', longitude: 0 }],
  };
  queries.selection = { data: { satellite_id: 'X-6', state: 'warning' } };
  queries.routes = { data: [] };
  queries.route = {};
  queries.pois = { data: { state: 'no_generated_pois', pois: [] } };
});
describe('Overview layer and exception integration', () => {
  it('keeps aircraft, GEP and selected planning link with no route', () => {
    render(<OverviewPage />);
    const legend = screen.getByLabelText('Globe legend');
    expect(
      within(legend)
        .getAllByRole('listitem')
        .map((row) => row.textContent)
    ).toEqual([
      'Aircraft',
      'Ground entry point',
      'Traffic path',
      'Planned satellite link',
    ]);
    expect(screen.getByLabelText('Map status').textContent).toContain(
      'No active route.'
    );
    expect(screen.getByLabelText('Map status').textContent).toContain(
      'Planned link warning'
    );
    expect(
      screen.getByRole('region', { name: 'Planned satellite' }).textContent
    ).toContain('X-6');
    expect(screen.getAllByLabelText('Globe legend')).toHaveLength(1);
    expect(screen.getAllByLabelText('Departure and arrival')).toHaveLength(1);
    expect(
      screen.getAllByRole('button', { name: 'Enter fullscreen overview' })
    ).toHaveLength(1);
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByRole('table')).toBeNull();
  });
  it('preserves the selected ID when its geometry is unavailable', () => {
    queries.satellites = { data: [] };
    render(<OverviewPage />);
    expect(screen.queryByText('Planned satellite link')).toBeNull();
    expect(
      screen.getByRole('region', { name: 'Planned satellite' }).textContent
    ).toContain('X-6');
    expect(screen.getByLabelText('Map status').textContent).toContain(
      'Planned link unavailable'
    );
  });
  it('keeps cached layer samples while clearly reporting query failures', () => {
    queries.selection.error = new Error('refresh failed');
    queries.status.error = new Error('refresh failed');
    queries.satellites.error = new Error('refresh failed');
    render(<OverviewPage />);
    expect(screen.getByText('Planned satellite link')).not.toBeNull();
    expect(screen.getByText('UNAVAILABLE')).not.toBeNull();
    expect(screen.getByLabelText('Map status').textContent).toContain(
      'Satellite selection unavailable'
    );
    expect(screen.getByLabelText('Map status').textContent).toContain(
      'Last-known planned link warning'
    );
    expect(screen.getByLabelText('Map status').textContent).toContain(
      'Status refresh unavailable'
    );
  });
  it('retains configured satellite identity independently of occluded scene labels', () => {
    render(<OverviewPage />);
    expect(
      within(
        screen.getByRole('list', { name: 'Configured map satellites' })
      ).getByText('X-6')
    ).not.toBeNull();
  });
  it('omits invalid aircraft coordinates without affecting valid GEP', () => {
    queries.status = {
      data: {
        timestamp: '2026-10-02T00:00:00Z',
        position: { latitude: 91, longitude: 0 },
        ground_entry_point: { latitude: 0, longitude: 0 },
      },
    };
    render(<OverviewPage />);
    expect(screen.queryByText('Aircraft', { exact: true })).toBeNull();
    expect(
      screen.getByText('Ground entry point', { exact: true })
    ).not.toBeNull();
    expect(screen.getByText('Position unavailable')).not.toBeNull();
  });
  it('matches route and history entries to renderable geometry', () => {
    queries.routes = { data: [{ id: 'route', is_active: true }] };
    queries.route = {
      data: {
        points: [
          { latitude: 0, longitude: 0 },
          { latitude: 1, longitude: 1 },
        ],
      },
    };
    queries.history = {
      data: {
        series: {
          starlink_dish_latitude_degrees: [
            [1, 0],
            [2, 1],
          ],
          starlink_dish_longitude_degrees: [
            [1, 0],
            [2, 1],
          ],
        },
      },
    };
    render(<OverviewPage />);
    expect(
      within(screen.getByLabelText('Globe legend')).getAllByRole('listitem')
    ).toHaveLength(6);
  });
  it('keeps every retained POI name accessible without scene labels', () => {
    queries.pois = {
      data: {
        state: 'available',
        pois: [
          {
            poi_id: 'a',
            name: 'First coincident POI',
            latitude: 0,
            longitude: 0,
            map_retained: true,
          },
          {
            poi_id: 'b',
            name: 'Second coincident POI',
            latitude: 0,
            longitude: 0,
            map_retained: true,
          },
        ],
      },
    };
    render(<OverviewPage />);
    expect(
      within(screen.getByRole('list', { name: 'Map POIs' }))
        .getAllByRole('listitem')
        .map((item) => item.textContent)
    ).toEqual(['First coincident POI', 'Second coincident POI']);
  });
});

it('uses active contacts for the ADS-B legend and clears it on expiry or disable', () => {
  queries.adsb.contacts = projectAdsbContacts(
    [adsbContact()],
    adsbSettings(),
    ADSB_NOW
  );
  const view = render(<OverviewPage />);
  expect(screen.getByText('ADS-B aircraft')).not.toBeNull();
  expect(
    screen.getByRole('list', { name: 'Visible ADS-B aircraft' })
  ).not.toBeNull();
  queries.adsb.contacts = [];
  view.rerender(<OverviewPage />);
  expect(screen.queryByText('ADS-B aircraft')).toBeNull();
  expect(screen.queryByRole('dialog')).toBeNull();
});
