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
  solarTimes: [] as number[],
}));
vi.mock('@/hooks/api/useSimulationRun', () => ({
  useSimulationRun: () => ({ data: state.run, isError: state.failed }),
  useSimulationRunRoute: () => ({ data: state.geometry }),
}));
vi.mock('./solar-position', async (importOriginal) => {
  const original = await importOriginal<typeof import('./solar-position')>();
  return {
    ...original,
    sunLightPosition: (date: Date, distance: number) => {
      state.solarTimes.push(date.getTime());
      return original.sunLightPosition(date, distance);
    },
  };
});
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
  state.solarTimes = [];
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
  expect(screen.queryByLabelText('Simulation run')).toBeNull();
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
  expect(screen.queryByLabelText('Simulation run')).toBeNull();
  expect(screen.queryByText('SIMULATED TIME')).toBeNull();
  expect(state.solarTimes.at(-1)).toBe(
    Date.parse(state.run.run!.simulation_time)
  );
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

it('places simulated time below the clocks and lights the globe at mission time', () => {
  state.run = runningStatus();
  mount();
  const clocks = screen
    .getAllByLabelText('Operational clocks')
    .find((node) => node.tagName === 'ASIDE')!;
  const label = screen.getByText('SIMULATED TIME');
  expect(clocks.contains(label)).toBe(false);
  expect(
    clocks.compareDocumentPosition(label) & Node.DOCUMENT_POSITION_FOLLOWING
  ).toBeTruthy();
  expect(state.solarTimes.at(-1)).toBe(
    Date.parse(state.run.run!.simulation_time)
  );
});
