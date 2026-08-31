import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import './test/app-route-service-mocks';
import { APP_NAVIGATION_ITEMS, AppShell } from './App';

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
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={entries}>
        <AppShell />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('App shell routing', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockReturnValue({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    });
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: vi.fn(() => null), setItem: vi.fn() },
    });
    Object.defineProperty(window, 'ResizeObserver', {
      configurable: true,
      value: class ResizeObserver {
        observe() {}
        disconnect() {}
      },
    });
  });

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

  it('replaces root and keeps browser back at overview', async () => {
    renderShell(['/']);

    expect(
      await screen.findByRole('heading', { name: 'Operations Overview' })
    ).toBeInTheDocument();
    expect(screen.getByLabelText('location')).toHaveTextContent('/overview');

    fireEvent.click(screen.getByRole('link', { name: 'Missions' }));
    expect(
      await screen.findByRole('heading', { name: 'Missions' })
    ).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByLabelText('location')).toHaveTextContent('/overview');
  });

  it.each([
    ['/overview', 'Operations Overview'],
    ['/missions', 'Missions'],
    ['/missions/alpha/legs/bravo', 'Leg Configuration'],
    ['/satellites', 'Satellite Manager'],
    ['/pois', 'Points of Interest'],
    ['/routes', 'Route Manager'],
    ['/export', 'Data Export'],
    ['/configuration', 'Configuration'],
  ])('renders production page identity for %s', async (path, heading) => {
    const { unmount } = renderShell([path]);
    expect(screen.getByLabelText('location')).toHaveTextContent(path);
    expect(await screen.findByRole('heading', { name: heading })).toBeVisible();
    unmount();
  });

  it('renders production mission detail identity for a dynamic route', async () => {
    const { unmount } = renderShell(['/missions/alpha']);
    expect(screen.getByLabelText('location')).toHaveTextContent(
      '/missions/alpha'
    );
    expect(await screen.findByText('Alpha Mission')).toBeVisible();
    expect(screen.getByText('ID: alpha')).toBeVisible();
    unmount();
  });

  it('does not catch unknown paths', async () => {
    renderShell(['/unknown']);
    await waitFor(() => expect(screen.getByRole('main')).toBeEmptyDOMElement());
    expect(screen.getByLabelText('location')).toHaveTextContent('/unknown');
  });

  it('renders compact navigation classes, close behavior, one main, and skip link', () => {
    renderShell(['/overview']);

    const links = screen.getAllByRole('link');
    expect(links[0]).toHaveAccessibleName('Skip to main content');
    expect(links[0]).toHaveAttribute('href', '#main-content');
    expect(screen.getAllByRole('main')).toHaveLength(1);

    const navigation = screen.getByRole('navigation', {
      name: 'Primary navigation',
    });
    const menu = within(navigation).getByRole('button', {
      name: 'Toggle navigation',
    });
    expect(menu).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(menu);
    expect(menu).toHaveAttribute('aria-expanded', 'true');
    const mobileMissions = within(navigation).getAllByRole('link', {
      name: 'Missions',
    })[1];
    expect(mobileMissions).toHaveClass('flex', 'min-h-11', 'min-w-11');
    fireEvent.click(mobileMissions);
    expect(menu).toHaveAttribute('aria-expanded', 'false');
  });
});
