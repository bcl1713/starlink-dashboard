import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import {
  APP_NAVIGATION_ITEMS,
  AppShell,
} from './App';

vi.mock('./pages/OverviewPage', () => ({
  OverviewPage: () => <h1>Operations Overview</h1>,
}));
vi.mock('./pages/MissionsPage', () => ({
  MissionsPage: () => <h1>Missions</h1>,
}));
vi.mock('./pages/MissionDetailPage', () => ({
  MissionDetailPage: () => <h1>Mission Detail</h1>,
}));
vi.mock('./pages/LegDetailPage', () => ({
  LegDetailPage: () => <h1>Leg Detail</h1>,
}));
vi.mock('./pages/SatelliteManagerPage', () => ({
  default: () => <h1>Satellites</h1>,
}));
vi.mock('./pages/POIManagerPage', () => ({
  POIManagerPage: () => <h1>POIs</h1>,
}));
vi.mock('./pages/RouteManagerPage', () => ({
  RouteManagerPage: () => <h1>Routes</h1>,
}));
vi.mock('./pages/DataExportPage', () => ({
  DataExportPage: () => <h1>Data Export</h1>,
}));
vi.mock('./pages/ConfigurationPage', () => ({
  ConfigurationPage: () => <h1>Configuration</h1>,
}));

function LocationProbe() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output aria-label="location">{location.pathname}</output>
      <button type="button" onClick={() => navigate(-1)}>
        Back
      </button>
    </>
  );
}

function renderShell(entries: string[]) {
  return render(
    <MemoryRouter initialEntries={entries}>
      <AppShell />
      <LocationProbe />
    </MemoryRouter>
  );
}

describe('App shell routing', () => {
  it('publishes navigation order with Overview first', () => {
    expect(APP_NAVIGATION_ITEMS.map((item) => [item.to, item.label])).toEqual([
      ['/overview', 'Overview'],
      ['/missions', 'Missions'],
      ['/satellites', 'Satellites'],
      ['/pois', 'POIs'],
      ['/routes', 'Routes'],
      ['/export', 'Data Export'],
      ['/configuration', 'Configuration'],
    ]);
  });

  it('replaces the root entry with the overview route', async () => {
    renderShell(['/']);

    expect(await screen.findByRole('heading', { name: 'Operations Overview' }))
      .toBeInTheDocument();
    expect(screen.getByLabelText('location')).toHaveTextContent('/overview');

    fireEvent.click(screen.getByRole('link', { name: 'Missions' }));
    expect(screen.getByLabelText('location')).toHaveTextContent('/missions');

    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByLabelText('location')).toHaveTextContent('/overview');
  });

  it('keeps existing routes addressable without a catch-all redirect', () => {
    const routes = [
      ['/missions', 'Missions'],
      ['/missions/alpha', 'Mission Detail'],
      ['/missions/alpha/legs/bravo', 'Leg Detail'],
      ['/satellites', 'Satellites'],
      ['/pois', 'POIs'],
      ['/routes', 'Routes'],
      ['/export', 'Data Export'],
      ['/configuration', 'Configuration'],
    ];

    for (const [path, heading] of routes) {
      const { unmount } = renderShell([path]);
      expect(screen.getByLabelText('location')).toHaveTextContent(path);
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
      unmount();
    }
  });

  it('renders one main, a first-focusable skip link, and current overview nav', () => {
    render(
      <MemoryRouter initialEntries={['/overview']}>
        <AppShell />
      </MemoryRouter>
    );

    const links = screen.getAllByRole('link');
    expect(links[0]).toHaveAccessibleName('Skip to main content');
    expect(links[0]).toHaveAttribute('href', '#main-content');
    expect(screen.getAllByRole('main')).toHaveLength(1);
    expect(screen.getByRole('main')).toHaveAttribute('tabIndex', '-1');

    const navigation = screen.getByRole('navigation', {
      name: 'Primary navigation',
    });
    const brand = within(navigation).getByRole('link', {
      name: 'Mission Planner',
    });
    const overview = within(navigation).getByRole('link', { name: 'Overview' });
    expect(brand).toHaveAttribute('href', '/overview');
    expect(brand).not.toHaveAttribute('aria-current');
    expect(overview).toHaveAttribute('aria-current', 'page');
  });
});
