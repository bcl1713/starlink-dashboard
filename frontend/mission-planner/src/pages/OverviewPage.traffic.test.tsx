vi.mock('./weather/OverviewWeatherLayer', () => ({
  OverviewWeatherLayer: () => null,
}));
vi.mock('./weather/OverviewWeatherCameraObserver', () => ({
  OverviewWeatherCameraObserver: () => null,
}));
vi.mock('@/hooks/useOverviewWeatherLayer', () => ({
  useOverviewWeatherLayer: () => ({
    configuredEnabled: false,
    visible: false,
    state: 'off',
    frameTimeMs: null,
    ageMs: null,
    atlas: null,
    detailContext: null,
    detailPairs: [],
    work: null,
    onDemand: () => {},
  }),
}));
vi.mock('@/hooks/useOverviewAdsbLayer', () => ({
  useOverviewAdsbLayer: () => ({
    contacts: [],
    sources: [],
    settings: undefined,
    settingsError: false,
    trafficError: false,
  }),
}));
vi.mock('@/hooks/api/useSimulationRun', () => ({
  useSimulationRun: () => ({}),
  useSimulationRunRoute: () => ({}),
}));
/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  cleanup,
  render as renderTesting,
  screen,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ComponentProps, ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
const clients: QueryClient[] = [];
function render(node: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  return renderTesting(node, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
});
import type { OrbitalTrafficState } from './orbital/lifecycle';
import { spriteSnapshot } from './orbital/sprite-test-fixtures';
import { selectRoute, emptyRoutingState } from './orbital/routing';
import { sceneToEcefKm } from './orbital/coordinates';
import { globePosition } from './globe-coordinates';
import { projectAircraftScenePosition } from './x-band-active-link-projection';
import type { StatusResponse } from '@/services/status';
import type { AnimatedFlowLineProps } from './AnimatedFlowLine';
import type { OverviewMapController } from './OverviewMapController';
import type { StarMarker } from './OverviewStarMarker';
import type { OverviewMetricHistoryPanels } from './OverviewMetricHistoryPanels';

const orbital = vi.hoisted(() => ({
  state: {
    previous: null,
    current: null,
    route: null,
    spritesReady: false,
    status: { kind: 'off', diagnostics: null },
  } as OrbitalTrafficState,
  draws: 0,
}));
vi.mock('@/hooks/useOrbitalTraffic', () => ({
  useOrbitalTraffic: () => orbital.state,
}));
vi.mock('./orbital/OrbitalSprites', () => ({
  OrbitalSprites: () => {
    orbital.draws++;
    return null;
  },
}));
const queries = vi.hoisted(() => ({
  status: {} as Record<string, unknown>,
  links: {} as Record<string, unknown>,
  selection: {} as Record<string, unknown>,
  satellites: {} as Record<string, unknown>,
}));
const scene = vi.hoisted(() => ({
  flows: new Map<string, AnimatedFlowLineProps>(),
  markers: new Map<string, ComponentProps<typeof StarMarker>>(),
  camera: undefined as ComponentProps<typeof OverviewMapController> | undefined,
  metrics: undefined as
    | ComponentProps<typeof OverviewMetricHistoryPanels>
    | undefined,
  canvas: undefined as Record<string, unknown> | undefined,
  now: Date.parse('2026-10-03T00:00:00Z'),
}));
// Only WebGL boundaries are replaced. Canvas mounts children so real page
// guards, projections and policies decide which scene props reach the renderer.
vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children, ...props }: ComponentProps<'div'>) => {
    scene.canvas = props;
    return <div>{children}</div>;
  },
}));
vi.mock('@react-three/drei', () => ({
  Html: ({ children }: ComponentProps<'div'>) => <>{children}</>,
  CameraControlsImpl: class {},
  Stars: () => null,
}));
vi.mock('./CityLitGlobe', () => ({ CityLitGlobe: () => null }));
vi.mock('./OverviewLabelLayout', () => ({ OverviewLabelLayout: () => null }));
vi.mock('./AnimatedFlowLine', async () => {
  const { useId, useLayoutEffect } = await import('react');
  return {
    AnimatedFlowLine: (props: AnimatedFlowLineProps) => {
      const id = useId();
      useLayoutEffect(() => {
        scene.flows.set(id, props);
        return () => {
          scene.flows.delete(id);
        };
      });
      return null;
    },
  };
});
vi.mock('./OverviewStarMarker', async () => {
  const { useId, useLayoutEffect } = await import('react');
  return {
    StarMarker: (props: ComponentProps<typeof StarMarker>) => {
      const id = useId();
      useLayoutEffect(() => {
        scene.markers.set(id, props);
        return () => {
          scene.markers.delete(id);
        };
      });
      return null;
    },
  };
});
vi.mock('./OverviewMapController', () => ({
  OverviewMapController: (
    props: ComponentProps<typeof OverviewMapController>
  ) => {
    scene.camera = props;
    return null;
  },
}));
vi.mock('./OverviewMetricHistoryPanels', () => ({
  OverviewMetricHistoryPanels: (
    props: ComponentProps<typeof OverviewMetricHistoryPanels>
  ) => {
    scene.metrics = props;
    return null;
  },
}));
vi.mock('@/hooks/useCurrentTime', () => ({ useCurrentTime: () => scene.now }));
vi.mock('@/hooks/api/useStatus', () => ({ useStatus: () => queries.status }));
vi.mock('@/hooks/api/useOverviewLinkSettings', () => ({
  useOverviewLinkSettings: () => queries.links,
}));
vi.mock('@/hooks/api/useActiveXLink', () => ({
  useActiveXLink: () => queries.selection,
}));
vi.mock('@/hooks/api/useSatellites', () => ({
  useSatellites: () => queries.satellites,
}));
vi.mock('../hooks/api/useRoutes', () => ({
  useRoutes: () => ({ data: [{ id: 'route', is_active: true }] }),
  useRoute: () => ({
    data: {
      points: [
        { latitude: 0, longitude: 0 },
        { latitude: 1, longitude: 1 },
      ],
    },
  }),
}));
vi.mock('@/hooks/api/useOverviewHistory', () => ({
  useOverviewHistory: () => ({
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
  }),
}));
vi.mock('@/hooks/api/useOverviewHistorySettings', () => ({
  useOverviewHistorySettings: () => ({ data: { window_seconds: 300 } }),
}));
vi.mock('@/hooks/api/useOverviewClockSettings', () => ({
  useOverviewClockSettings: () => ({ data: { clocks: [] } }),
}));
vi.mock('@/hooks/api/useOverviewUpcomingPois', () => ({
  useOverviewUpcomingPois: () => ({
    data: { state: 'no_generated_pois', pois: [] },
  }),
}));
vi.mock('./overview-traffic-arc', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('./overview-traffic-arc')>();
  return { ...actual, projectTrafficArc: vi.fn(actual.projectTrafficArc) };
});
import { projectTrafficArc } from './overview-traffic-arc';
import { OverviewPage } from './OverviewPage';

function status(): StatusResponse {
  return {
    timestamp: '2026-10-03T00:00:00Z',
    position: {
      latitude: 0,
      longitude: 0,
      altitude: 35000,
      speed: 450,
      heading: 90,
    },
    ground_entry_point: { latitude: 10, longitude: 20 },
    network: {
      throughput_up_mbps: 500,
      throughput_down_mbps: 50,
      latency_ms: 20,
      packet_loss_percent: 25,
    },
    metric_availability: {
      throughput_up_mbps: true,
      throughput_down_mbps: true,
      latency_ms: true,
      packet_loss_percent: true,
    },
  };
}
function settings(starshield: boolean, xBand: boolean) {
  queries.links = {
    data: { starshield_link_enabled: starshield, x_band_link_enabled: xBand },
  };
}
function traffic() {
  return [...scene.flows.values()].find(
    (props) => props.core?.color === '#c084fc'
  );
}
function xBand() {
  return [...scene.flows.values()].find(
    (props) => props.points.length === 2 && props.forward
  );
}
function expectPreset() {
  expect(xBand()?.forward).toMatchObject({
    enabled: true,
    speed: 0.5,
    size: 4.8,
    brightness: 1.35,
    color: '#fbbf24',
    maxParticles: 100,
  });
  expect(xBand()?.reverse).toMatchObject({
    enabled: true,
    speed: 0.5,
    size: 4.8,
    brightness: 1.35,
    color: '#67e8f9',
    maxParticles: 100,
  });
  expect(xBand()?.forward?.rate).toBeCloseTo(1.2944666963);
  expect(xBand()?.reverse?.rate).toBeCloseTo(1.2944666963);
  expect(xBand()?.forward?.failure).toBeUndefined();
  expect(xBand()?.reverse?.failure).toBeUndefined();
}
function expectUnchangedLayers() {
  const flows = [...scene.flows.values()];
  expect(
    flows.find((props) => props.forward?.maxParticles === 1)?.forward
  ).toMatchObject({ enabled: true, rate: 1, speed: 0.1, color: '#ffb000' });
  expect(flows.find((props) => props.core?.color === '#d9ffff')).toBeDefined();
  expect([...scene.markers.values()].map((props) => props.color)).toEqual([
    '#c084fc',
    '#FF6B6B',
    '#72b7ff',
  ]);
  expect(screen.getByText('GEP')).toBeInTheDocument();
  expect(
    screen.getByRole('region', { name: 'Planned satellite' })
  ).toHaveTextContent('X-6');
  expect(scene.metrics?.status).toBe(queries.status.data);
  expect(scene.camera).toMatchObject({
    aircraft: { latitude: 0, longitude: 0 },
    intent: 'automatic',
    followAvailable: true,
    resetRevision: 0,
  });
  expect(scene.camera?.route.length).toBeGreaterThanOrEqual(2);
  expect(scene.canvas).toMatchObject({
    camera: { position: [0, 0, 22], fov: 45 },
  });
}
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
beforeEach(() => {
  orbital.state = {
    previous: null,
    current: null,
    route: null,
    spritesReady: false,
    status: { kind: 'off', diagnostics: null },
  };
  orbital.draws = 0;
  vi.mocked(projectTrafficArc).mockClear();
  scene.now = Date.parse('2026-10-03T00:00:00Z');
  vi.spyOn(Date, 'now').mockImplementation(() => scene.now);
  queries.status = { data: status() };
  settings(true, true);
  queries.selection = { data: { satellite_id: 'X-6', state: 'normal' } };
  queries.satellites = {
    data: [
      {
        satellite_id: 'X-6',
        transport: 'X',
        longitude: 0,
        slot: null,
        color: '#FF6B6B',
      },
    ],
  };
});

describe('Overview traffic scene integration', () => {
  it('clears traffic on the first failed status attempt while retries retain cached data', () => {
    const view = render(<OverviewPage />);
    expect(traffic()?.canAnimate?.()).toBe(true);
    expect(xBand()?.canAnimate?.()).toBe(true);
    queries.status = { data: status(), error: null, failureCount: 1 };
    view.rerender(<OverviewPage />);
    expect(traffic()).toBeUndefined();
    expect(xBand()?.forward?.enabled).toBe(false);
    expect(xBand()?.reverse?.enabled).toBe(false);
    expect(xBand()?.canAnimate?.()).toBe(false);
    expect(scene.metrics?.status).toEqual(status());
    queries.status = { data: status(), error: null, failureCount: 0 };
    view.rerender(<OverviewPage />);
    expect(traffic()?.canAnimate?.()).toBe(true);
    expectPreset();
  });
  it('retains X-band endpoints through clock and equivalent query updates', () => {
    const view = render(<OverviewPage />);
    const initialPoints = xBand()?.points;
    expect(initialPoints).toHaveLength(2);
    scene.now += 1_000;
    view.rerender(<OverviewPage />);
    expect(xBand()?.points).toBe(initialPoints);
    queries.status = {
      data: { ...status(), network: { throughput_up_mbps: 0 } },
    };
    queries.satellites = {
      data: [
        {
          satellite_id: 'X-6',
          transport: 'X',
          longitude: 0,
          slot: null,
          color: '#FF6B6B',
        },
      ],
    };
    view.rerender(<OverviewPage />);
    expect(xBand()?.points).toBe(initialPoints);
    expectPreset();
    queries.status = {
      data: {
        ...status(),
        position: { latitude: 1, longitude: 0, altitude: 35000 },
      },
    };
    view.rerender(<OverviewPage />);
    expect(xBand()?.points).not.toBe(initialPoints);
    const movedPoints = xBand()?.points;
    queries.satellites = {
      data: [{ satellite_id: 'X-6', transport: 'X', longitude: 20 }],
    };
    view.rerender(<OverviewPage />);
    expect(xBand()?.points).not.toBe(movedPoints);
    const shiftedPoints = xBand()?.points;
    queries.satellites = {
      data: [{ satellite_id: 'X-7', transport: 'X', longitude: 20 }],
    };
    queries.selection = { data: { satellite_id: 'X-7', state: 'normal' } };
    view.rerender(<OverviewPage />);
    expect(xBand()?.points).not.toBe(shiftedPoints);
    queries.satellites = { data: [] };
    view.rerender(<OverviewPage />);
    expect(xBand()).toBeUndefined();
    expect(screen.queryByText('Planned satellite link')).toBeNull();
    expect(traffic()).toBeDefined();
  });
  it.each([
    [true, true],
    [true, false],
    [false, true],
    [false, false],
  ])(
    'draws only confirmed links and matching legend for %s/%s',
    (starshield, satellite) => {
      settings(starshield, satellite);
      render(<OverviewPage />);
      expect(Boolean(traffic())).toBe(starshield);
      expect(Boolean(xBand())).toBe(satellite);
      expect(Boolean(screen.queryByText('Traffic path'))).toBe(starshield);
      expect(Boolean(screen.queryByText('Planned satellite link'))).toBe(
        satellite
      );
      expect(scene.flows.size).toBe(2 + Number(starshield) + Number(satellite));
      if (!starshield) expect(projectTrafficArc).not.toHaveBeenCalled();
      expectUnchangedLayers();
    }
  );
  it('sends measured upload/download only to the aircraft–PoP arc', () => {
    render(<OverviewPage />);
    const arc = traffic();
    expect(arc?.points).toHaveLength(129);
    expect(arc?.points[0]?.[0]).toBeCloseTo(2.003345);
    expect(arc?.points[0]?.slice(1)).toEqual([0, -0]);
    expect(arc?.points.at(-1)?.[0]).toBeCloseTo(1.850834);
    expect(arc?.points.at(-1)?.[1]).toBeCloseTo(0.347297);
    expect(arc?.points.at(-1)?.[2]).toBeCloseTo(-0.673648);
    expect(arc?.forward).toMatchObject({
      enabled: true,
      rate: 5,
      speed: 0.5,
      color: '#fbbf24',
      size: 9.5,
      brightness: 3.4,
      maxParticles: 100,
      failure: { probability: 0.25 },
    });
    expect(arc?.reverse?.rate).toBeCloseTo(3.1623570553);
    expect(arc?.reverse?.color).toBe('#67e8f9');
    expectPreset();
    expect(scene.metrics?.status).toEqual(status());
    expect(screen.getByText('Traffic path').previousElementSibling).toHaveStyle(
      { background: '#c084fc' }
    );
  });
  it('stops warning X-band immediately without changing traffic style or activity', () => {
    const view = render(<OverviewPage />);
    const initial = traffic();
    queries.selection = { data: { satellite_id: 'X-6', state: 'warning' } };
    view.rerender(<OverviewPage />);
    expect(xBand()?.forward?.enabled).toBe(false);
    expect(xBand()?.reverse?.enabled).toBe(false);
    expect(xBand()?.canAnimate?.()).toBe(false);
    expect(xBand()?.core?.color).toBe('#ef4444');
    expect(traffic()).toMatchObject({
      points: initial?.points,
      outer: initial?.outer,
      glow: initial?.glow,
      core: initial?.core,
      forward: initial?.forward,
      reverse: initial?.reverse,
    });
    expect(traffic()?.canAnimate?.()).toBe(true);
    expect(screen.getByLabelText('Map status')).toHaveTextContent(
      'Planned link warning'
    );
    settings(true, false);
    view.rerender(<OverviewPage />);
    expect(xBand()).toBeUndefined();
    expect(screen.queryByText('Planned satellite link')).toBeNull();
    expect(screen.getByLabelText('Map status')).toHaveTextContent(
      'Planned link warning'
    );
    expect(
      screen.getByRole('region', { name: 'Planned satellite' })
    ).toHaveTextContent('X-6');
  });
  it.each(['loading', 'failed'])(
    'hides both links without confirmed settings during %s',
    (state) => {
      queries.links =
        state === 'loading'
          ? { isLoading: true }
          : { error: new Error('GET failed') };
      render(<OverviewPage />);
      expect(traffic()).toBeUndefined();
      expect(xBand()).toBeUndefined();
      expect(screen.queryByText('Traffic path')).toBeNull();
      expect(screen.queryByText('Planned satellite link')).toBeNull();
      expect(projectTrafficArc).not.toHaveBeenCalled();
      expectUnchangedLayers();
    }
  );
  it('retains the last confirmed pair on settings refresh failure and updates without reload', () => {
    settings(false, true);
    const view = render(<OverviewPage />);
    queries.links.error = new Error('refresh failed');
    view.rerender(<OverviewPage />);
    expect(traffic()).toBeUndefined();
    expectPreset();
    settings(true, false);
    view.rerender(<OverviewPage />);
    expect(traffic()).toBeDefined();
    expect(xBand()).toBeUndefined();
  });
  it('expires both frame guards at ten seconds before the next render tick', () => {
    render(<OverviewPage />);
    const arc = traffic();
    const satellite = xBand();
    const constructionCount = vi.mocked(projectTrafficArc).mock.calls.length;
    scene.now += 9_999;
    expect(arc?.canAnimate?.()).toBe(true);
    expect(satellite?.canAnimate?.()).toBe(true);
    scene.now += 1;
    expect(arc?.canAnimate?.()).toBe(false);
    expect(satellite?.canAnimate?.()).toBe(false);
    expect(projectTrafficArc).toHaveBeenCalledTimes(constructionCount);
  });
  it.each(['stale', 'refresh failed'])(
    'omits the arc and stops retained X-band for %s position',
    (condition) => {
      if (condition === 'stale') scene.now += 10_000;
      else queries.status.error = new Error('refresh failed');
      render(<OverviewPage />);
      expect(traffic()).toBeUndefined();
      expect(screen.queryByText('Traffic path')).toBeNull();
      expect(projectTrafficArc).not.toHaveBeenCalled();
      expect(xBand()?.forward?.enabled).toBe(false);
      expect(xBand()?.reverse?.enabled).toBe(false);
      expect(xBand()?.canAnimate?.()).toBe(false);
      expect(screen.getByText('Planned satellite link')).toBeInTheDocument();
    }
  );
  it.each([null, { latitude: 91, longitude: 0 }])(
    'omits unavailable/invalid PoP without substituting satellite',
    (pop) => {
      queries.status = { data: { ...status(), ground_entry_point: pop } };
      render(<OverviewPage />);
      expect(traffic()).toBeUndefined();
      expect(screen.queryByText('Traffic path')).toBeNull();
      expectPreset();
      expect(xBand()?.canAnimate?.()).toBe(true);
    }
  );
  it('retains the arc across new status objects and rebuilds on endpoint changes', () => {
    const view = render(<OverviewPage />);
    const initialPoints = traffic()?.points;
    const calls = vi.mocked(projectTrafficArc).mock.calls.length;
    queries.status = {
      data: {
        ...status(),
        network: { ...status().network, throughput_up_mbps: 4 },
      },
    };
    view.rerender(<OverviewPage />);
    expect(traffic()?.points).toBe(initialPoints);
    expect(projectTrafficArc).toHaveBeenCalledTimes(calls);
    expect(traffic()?.forward?.rate).toBeCloseTo(1.2944666963);
    queries.status = {
      data: {
        ...status(),
        position: { latitude: 1, longitude: 0, altitude: 35000 },
      },
    };
    view.rerender(<OverviewPage />);
    expect(traffic()?.points).not.toBe(initialPoints);
    const movedPoints = traffic()?.points;
    queries.status = {
      data: {
        ...status(),
        position: { latitude: 1, longitude: 0, altitude: 40000 },
      },
    };
    view.rerender(<OverviewPage />);
    expect(traffic()?.points).not.toBe(movedPoints);
    const raisedPoints = traffic()?.points;
    queries.status = {
      data: {
        ...status(),
        position: { latitude: 1, longitude: 0, altitude: 40000 },
        ground_entry_point: { latitude: 11, longitude: 20 },
      },
    };
    view.rerender(<OverviewPage />);
    expect(traffic()?.points).not.toBe(raisedPoints);
  });
  it('keeps normal X-band activity when measured directions are unavailable', () => {
    queries.status = { data: { ...status(), metric_availability: {} } };
    render(<OverviewPage />);
    expect(traffic()?.forward?.enabled).toBe(false);
    expect(traffic()?.reverse?.enabled).toBe(false);
    expect(traffic()?.canAnimate?.()).toBe(false);
    expectPreset();
    expect(xBand()?.canAnimate?.()).toBe(true);
  });
  it('keeps available download without inventing latency/loss modulation', () => {
    queries.status = {
      data: {
        ...status(),
        metric_availability: { throughput_down_mbps: true },
      },
    };
    render(<OverviewPage />);
    expect(traffic()?.forward?.enabled).toBe(false);
    expect(traffic()?.reverse).toMatchObject({
      enabled: true,
      size: 9.5,
      brightness: 3.4,
      failure: undefined,
    });
    expect(traffic()?.canAnimate?.()).toBe(true);
    expectPreset();
  });
  it.each(['unknown', 'selection failed', 'catalog failed'])(
    'stops only X-band activity for %s selection',
    (condition) => {
      if (condition === 'unknown')
        queries.selection = { data: { satellite_id: 'X-6', state: null } };
      if (condition === 'selection failed')
        queries.selection.error = new Error('refresh failed');
      if (condition === 'catalog failed')
        queries.satellites.error = new Error('refresh failed');
      render(<OverviewPage />);
      expect(xBand()?.forward?.enabled).toBe(false);
      expect(xBand()?.reverse?.enabled).toBe(false);
      expect(xBand()?.canAnimate?.()).toBe(false);
      expect(traffic()?.forward?.enabled).toBe(true);
      expect(traffic()?.canAnimate?.()).toBe(true);
    }
  );
});

it('exactly_one_measured_flow_owner uses the inferred route and retains disconnected dots plus fallback', () => {
  const telemetry = status();
  telemetry.ground_entry_point = { latitude: 0, longitude: 0 };
  queries.status = { data: telemetry };
  queries.links = {
    data: {
      starshield_link_enabled: true,
      x_band_link_enabled: true,
      orbital_traffic_enabled: true,
    },
  };
  const s = spriteSnapshot();
  const endpoints = {
    aircraft: sceneToEcefKm(projectAircraftScenePosition(telemetry)!.position),
    pop: sceneToEcefKm(globePosition(0, 0, 2)),
  };
  const route = selectRoute(s, endpoints, emptyRoutingState('a')).route!;
  orbital.state = {
    previous: null,
    current: s,
    route,
    spritesReady: true,
    status: { kind: 'ready', diagnostics: null },
  };
  const view = render(<OverviewPage />);
  expect(traffic()?.points).toHaveLength(3);
  expect(
    [...scene.flows.values()].filter((p) => p.core?.color === '#c084fc')
  ).toHaveLength(1);
  expect(traffic()?.forward?.maxParticles).toBe(100);
  expect(traffic()?.reverse?.maxParticles).toBe(100);
  expect(screen.getByText('Satellites')).toBeInTheDocument();
  expectPreset();
  const key = traffic()?.particleKey;
  queries.status = {
    data: {
      ...telemetry,
      position: { ...telemetry.position, altitude: 36000 },
    },
  };
  view.rerender(<OverviewPage />);
  expect(traffic()?.particleKey).toBe(key);
  orbital.state = { ...orbital.state, route: null };
  view.rerender(<OverviewPage />);
  expect(traffic()?.points.length).toBeGreaterThan(3);
  expect(screen.getByText('Satellites')).toBeInTheDocument();
  expect(traffic()?.particleKey).not.toBe(key);
  orbital.state = {
    ...orbital.state,
    current: null,
    spritesReady: false,
    status: { kind: 'worker-failed', diagnostics: null },
  };
  view.rerender(<OverviewPage />);
  expect(screen.queryByText('Satellites')).toBeNull();
  expect(traffic()?.points.length).toBeGreaterThan(3);
});

it('toggles the aircraft history line and legend while retaining graph data and other layers', () => {
  const view = render(<OverviewPage />);
  const historyLine = () =>
    [...scene.flows.values()].find((props) => props.core?.color === '#d9ffff');
  expect(historyLine()).toBeDefined();
  expect(screen.getByText('Track history')).toBeInTheDocument();
  const history = scene.metrics?.history;
  queries.links = {
    data: {
      starshield_link_enabled: true,
      x_band_link_enabled: true,
      orbital_traffic_enabled: false,
      aircraft_history_enabled: false,
    },
  };
  view.rerender(<OverviewPage />);
  expect(historyLine()).toBeUndefined();
  expect(screen.queryByText('Track history')).toBeNull();
  expect(scene.metrics?.history).toEqual(history);
  expect(scene.metrics?.selectedWindowSeconds).toBe(300);
  expect(traffic()).toBeDefined();
  expect(xBand()).toBeDefined();
  expect(screen.getByText('Aircraft', { exact: true })).toBeInTheDocument();
  queries.links = {
    data: { ...(queries.links.data as object), aircraft_history_enabled: true },
  };
  view.rerender(<OverviewPage />);
  expect(historyLine()).toBeDefined();
  expect(screen.getByText('Track history')).toBeInTheDocument();
});
