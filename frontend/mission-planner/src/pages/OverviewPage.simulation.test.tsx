// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, type ReactNode } from 'react';
import { runningStatus, completedStatus } from '@/test/simulation-run-fixtures';
import type { SimulationRunStatus } from '@/services/simulation-run';
vi.hoisted(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  );
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
    }),
  });
});
const state = vi.hoisted(() => ({
  run: undefined as SimulationRunStatus | undefined,
  failed: false,
  mounts: 0,
  historyReads: 0,
  routeReads: 0,
  geometry: undefined as unknown,
}));
vi.mock('@/hooks/api/useSimulationRun', () => ({
  useSimulationRun: () => ({ data: state.run, isError: state.failed }),
  useSimulationRunRoute: () => ({ data: state.geometry }),
}));
vi.mock('@react-three/fiber', () => ({
  Canvas: function Canvas() {
    useEffect(() => {
      state.mounts++;
    }, []);
    return <div data-testid="canvas" />;
  },
}));
vi.mock('@react-three/drei', () => ({
  Html: () => null,
  Stars: () => null,
  CameraControls: () => null,
  CameraControlsImpl: class {},
}));
vi.mock('@/hooks/useCurrentTime', () => ({
  useCurrentTime: () => Date.parse('2026-10-05T00:00:00Z'),
}));
vi.mock('@/hooks/api/useRoutes', () => ({
  useRoutes: () => ({ data: [] }),
  useRoute: () => {
    state.routeReads++;
    return {};
  },
}));
vi.mock('@/hooks/api/useStatus', () => ({ useStatus: () => ({}) }));
vi.mock('@/hooks/api/useOverviewHistory', () => ({
  useOverviewHistory: () => {
    state.historyReads++;
    return { data: { series: {} } };
  },
}));
vi.mock('@/hooks/api/useSatellites', () => ({
  useSatellites: () => ({ data: [] }),
}));
vi.mock('@/hooks/api/useActiveXLink', () => ({ useActiveXLink: () => ({}) }));
vi.mock('@/hooks/api/useOverviewLinkSettings', () => ({
  useOverviewLinkSettings: () => ({}),
}));
vi.mock('@/hooks/useOverviewAdsbLayer', () => ({
  useOverviewAdsbLayer: () => ({ contacts: [] }),
}));
vi.mock('@/hooks/useOrbitalTraffic', () => ({ useOrbitalTraffic: () => ({}) }));
vi.mock('@/hooks/api/useOverviewHistorySettings', () => ({
  useOverviewHistorySettings: () => ({ data: { window_seconds: 300 } }),
}));
vi.mock('@/hooks/api/useOverviewUpcomingPois', () => ({
  useOverviewUpcomingPois: () => ({}),
}));
vi.mock('@/hooks/api/useOverviewClockSettings', () => ({
  useOverviewClockSettings: () => ({
    data: {
      clocks: [
        {
          key: 'utc',
          label: 'UTC',
          time_zone: 'UTC',
          location: 'UTC',
          latitude: null,
          longitude: null,
        },
      ],
    },
  }),
}));
import { OverviewPage } from './OverviewPage';
afterEach(cleanup);
beforeEach(() => {
  state.run = undefined;
  state.failed = false;
  state.mounts = 0;
  state.historyReads = 0;
  state.routeReads = 0;
  state.geometry = undefined;
});
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrap = (children: ReactNode) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const view = render(wrap(<OverviewPage />));
  return {
    ...view,
    rerenderOverview: () => view.rerender(wrap(<OverviewPage />)),
  };
}
it('hides all five network cards and header while retaining Canvas and history', () => {
  const view = mount(),
    canvas = screen.getByTestId('canvas');
  expect(screen.getByLabelText('Overview metric history')).toBeVisible();
  expect(screen.getByLabelText('Network history context')).toBeVisible();
  state.run = runningStatus();
  view.rerenderOverview();
  expect(screen.queryByLabelText('Overview metric history')).toBeNull();
  expect(screen.queryByLabelText('Network history context')).toBeNull();
  expect(screen.getByLabelText('Simulation run')).toBeVisible();
  expect(screen.getByText('SIMULATED TIME')).toBeVisible();
  expect(screen.getByTestId('canvas')).toBe(canvas);
  expect(state.mounts).toBe(1);
  expect(state.historyReads).toBeGreaterThan(1);
  expect(state.routeReads).toBeGreaterThan(1);
  state.failed = true;
  view.rerenderOverview();
  expect(screen.queryByLabelText('Overview metric history')).toBeNull();
  state.run = completedStatus();
  state.failed = false;
  view.rerenderOverview();
  expect(screen.getByLabelText('Overview metric history')).toBeVisible();
  expect(screen.queryByText('SIMULATED TIME')).toBeNull();
  expect(screen.getByTestId('canvas')).toBe(canvas);
  expect(state.mounts).toBe(1);
});
it.each(['cancelled', 'failed', 'idle'] as const)(
  'restores the network rail in %s state',
  (terminal) => {
    state.run = runningStatus();
    const view = mount();
    state.run =
      terminal === 'idle'
        ? { ...runningStatus(), state: 'idle', run: null }
        : { ...runningStatus(), state: terminal };
    view.rerenderOverview();
    expect(screen.getByLabelText('Overview metric history')).toBeVisible();
    expect(state.mounts).toBe(1);
  }
);
