import { expect, type BrowserContext, type Page } from '@playwright/test';
import type { OverviewClockSettings } from '../../../src/services/overview-clock-settings';
import type { OverviewHistorySettings } from '../../../src/services/overview-history';
import type { OverviewLinkSettings } from '../../../src/services/overview-link-settings';

const metrics = [
  'starlink_network_latency_ms_current',
  'starlink_network_throughput_down_mbps_current',
  'starlink_network_throughput_up_mbps_current',
  'starlink_network_packet_loss_percent',
  'starlink_dish_obstruction_percent',
];
export const fixtureRoutes = [
  {
    id: 'route-a',
    name: 'KAAA to KBBB',
    points: [
      { latitude: 35, longitude: -100 },
      { latitude: 40, longitude: -80 },
    ],
  },
  {
    id: 'route-b',
    name: 'KCCC to KDDD',
    points: [
      { latitude: 37, longitude: -90 },
      { latitude: 42, longitude: -70 },
    ],
  },
];

/** Shared confirmed REST state, never injected directly into a query cache.
 * Holds snapshot GET data before awaiting release, so Task 2 can reproduce
 * obsolete-read races. Failure controls apply before any confirmed write.
 */
export async function installOverviewWindowFixture(context: BrowserContext) {
  const state = {
    clocks: {
      clocks: [
        { label: 'Zulu / UTC', time_zone: 'UTC' },
        { label: 'Washington, DC', time_zone: 'America/New_York' },
        { label: 'Omaha, NE', time_zone: 'America/Chicago' },
        { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
      ],
    } as OverviewClockSettings,
    history: { window_seconds: 300 } as OverviewHistorySettings,
    links: {
      starshield_link_enabled: true,
      x_band_link_enabled: true,
      orbital_traffic_enabled: false,
    } as OverviewLinkSettings,
    positionAvailable: true,
    activeLeg: null as 'leg-a' | 'leg-b' | null,
    aircraftHistory: [] as Array<{ latitude: number; longitude: number }>,
  };
  const marker = Math.floor(Date.now() / 1000) - 20;
  const readCounts: Record<string, number> = {};
  const requestLog: Array<{
    seq: number;
    method: string;
    endpoint: string;
    page: string;
    startedAt: number;
    respondedAt?: number;
    status?: number;
    aborted?: boolean;
    held?: boolean;
    body?: unknown;
    response?: unknown;
  }> = [];
  const interruptions: string[] = [];
  const failures: Array<{ endpoint: string; method: string }> = [];
  const holds: Array<{
    endpoint: string;
    method: string;
    wait: Promise<void>;
    pageContains?: string;
  }> = [];
  const mission = () => ({
    id: 'window-mission',
    name: 'Window synchronization mission',
    description: 'Controlled two-window fixture',
    created_at: '2026-10-04T12:00:00Z',
    updated_at: '2026-10-04T12:00:00Z',
    metadata: {},
    legs: fixtureRoutes.map((route, i) => ({
      id: i === 0 ? 'leg-a' : 'leg-b',
      name: i === 0 ? 'First leg' : 'Second leg',
      route_id: route.id,
      transports: {},
      is_active: state.activeLeg === (i === 0 ? 'leg-a' : 'leg-b'),
    })),
  });
  await context.route('**/api/**', async (route) => {
    const request = route.request();
    const endpoint = new URL(request.url()).pathname;
    const method = request.method();
    const entry = {
      seq: requestLog.length + 1,
      method,
      endpoint,
      page: request.frame().url(),
      startedAt: Date.now(),
      body: request.postData() ? request.postDataJSON() : undefined,
    } as (typeof requestLog)[number];
    requestLog.push(entry);
    if (method === 'GET')
      readCounts[endpoint] = (readCounts[endpoint] ?? 0) + 1;
    const interrupted = method === 'GET' ? interruptions.indexOf(endpoint) : -1;
    if (interrupted >= 0) {
      interruptions.splice(interrupted, 1);
      entry.aborted = true;
      entry.respondedAt = Date.now();
      return route.abort('failed');
    }
    const failure = failures.findIndex(
      (control) => control.endpoint === endpoint && control.method === method
    );
    if (failure >= 0) {
      failures.splice(failure, 1);
      entry.status = 503;
      entry.respondedAt = Date.now();
      return route.fulfill({
        status: 503,
        json: { detail: 'Controlled fixture failure' },
      });
    }
    let json: unknown;
    const now = Date.now();
    const observed = new Date(now).toISOString();
    const selected =
      state.activeLeg === 'leg-a'
        ? fixtureRoutes[0]
        : state.activeLeg === 'leg-b'
          ? fixtureRoutes[1]
          : null;
    if (endpoint === '/api/overview-adsb/settings') {
      json = {
        enabled: false,
        mode: 'military_and_included',
        include_hexes: [],
        exclude_hexes: [],
        callsign_substrings: [],
        revision: 0,
      };
    } else if (endpoint === '/api/overview-adsb/traffic') {
      json = {
        settings_revision: 0,
        generated_at_ms: Date.now(),
        contacts: [],
        sources: [],
      };
    } else if (endpoint === '/api/overview-clocks/settings') {
      if (method === 'PUT') state.clocks = request.postDataJSON();
      json = state.clocks;
    } else if (endpoint === '/api/overview-history/settings') {
      if (method === 'PUT') state.history = request.postDataJSON();
      json = state.history;
    } else if (endpoint === '/api/overview-links/settings') {
      if (method === 'PUT')
        state.links = { ...state.links, ...request.postDataJSON() };
      json = state.links;
    } else if (endpoint === '/api/v2/missions/window-mission') {
      json = mission();
    } else if (
      /\/legs\/leg-[ab]\/activate$/.test(endpoint) &&
      method === 'POST'
    ) {
      state.activeLeg = endpoint.includes('leg-a') ? 'leg-a' : 'leg-b';
      json = { leg_id: state.activeLeg };
    } else if (
      endpoint === '/api/v2/missions/window-mission/legs/deactivate' &&
      method === 'POST'
    ) {
      state.activeLeg = null;
      json = { success: true };
    } else if (endpoint === '/api/routes') {
      json = {
        routes: fixtureRoutes.map(({ id, name, points }) => ({
          id,
          name,
          point_count: points.length,
          is_active: id === selected?.id,
        })),
        total: 2,
      };
    } else if (
      fixtureRoutes.some(({ id }) => endpoint === `/api/routes/${id}`)
    ) {
      json = fixtureRoutes.find(({ id }) => endpoint === `/api/routes/${id}`);
    } else if (endpoint === '/api/overview/upcoming-pois') {
      json = {
        state: selected ? 'available' : 'no_active_mission',
        calculated_at: observed,
        flight_phase: selected ? 'in_flight' : null,
        scheduled_departure_time: null,
        current_route_progress: selected ? 20 : null,
        position_observed_at: observed,
        position_state: 'fresh',
        pois: selected
          ? selected.points.map((point, i) => ({
              poi_id: `${selected.id}-${i}`,
              name: selected.name.split(' to ')[i],
              kind: i === 0 ? 'departure' : 'arrival',
              projected_route_progress: i * 100,
              flight_phase: 'in_flight',
              ...point,
              expected_arrival_time: new Date(
                now + (i === 0 ? -600000 : 600000)
              ).toISOString(),
              eta_seconds: i === 0 ? -600 : 600,
              estimated_arrival_time: new Date(
                now + (i === 0 ? -600000 : 600000)
              ).toISOString(),
              eta_type: 'estimated',
              upcoming: i === 1,
              map_retained: true,
            }))
          : [],
      };
    } else if (endpoint === '/api/status') {
      json = {
        timestamp: observed,
        position: state.positionAvailable
          ? { latitude: 35, longitude: -100, altitude: 35000 }
          : null,
        ground_entry_point: { latitude: 36, longitude: -102 },
        metric_availability: {
          latency_ms: true,
          throughput_down_mbps: true,
          throughput_up_mbps: true,
          packet_loss_percent: true,
          obstruction_percent: true,
        },
        network: {
          latency_ms: 54,
          throughput_down_mbps: 58.3,
          throughput_up_mbps: 32,
          packet_loss_percent: 0.004,
        },
        obstruction: { obstruction_percent: 31.24 },
      };
    } else if (endpoint === '/api/overview-history') {
      const end = Math.floor(now / 1000);
      const samples = [
        [marker - 5, 10],
        [marker, 90],
        [end - 1, 20],
      ];
      json = {
        window_seconds: state.history.window_seconds,
        start_timestamp_seconds: end - state.history.window_seconds,
        end_timestamp_seconds: end,
        step_seconds: 5,
        series: {
          ...Object.fromEntries(metrics.map((name) => [name, samples])),
          starlink_dish_latitude_degrees: state.aircraftHistory.map(
            (point, i) => [
              end - (state.aircraftHistory.length - 1 - i) * 5,
              point.latitude,
            ]
          ),
          starlink_dish_longitude_degrees: state.aircraftHistory.map(
            (point, i) => [
              end - (state.aircraftHistory.length - 1 - i) * 5,
              point.longitude,
            ]
          ),
        },
        rolling_5m: Object.fromEntries(
          metrics.map((name) => [
            name,
            { state: 'available', min: samples, avg: samples, max: samples },
          ])
        ),
      };
    } else if (endpoint === '/api/satellites') {
      json = [
        {
          satellite_id: 'X-6',
          transport: 'X',
          longitude: -70,
          slot: null,
          color: '#a855f7',
        },
      ];
    } else if (endpoint === '/api/active-x-link') {
      json = { satellite_id: 'X-6', state: 'normal' };
    } else if (endpoint === '/api/v2/gps/config') {
      json = { enabled: true, ready: true, satellites: 4 };
    } else {
      entry.status = 404;
      entry.respondedAt = Date.now();
      return route.fulfill({
        status: 404,
        json: { detail: `Unconfigured fixture endpoint: ${endpoint}` },
      });
    }
    json = structuredClone(json);
    const held = holds.findIndex(
      (control) =>
        control.endpoint === endpoint &&
        control.method === method &&
        (!control.pageContains || entry.page.includes(control.pageContains))
    );
    if (held >= 0) {
      entry.held = true;
      await holds.splice(held, 1)[0].wait;
    }
    entry.status = 200;
    entry.response = json;
    entry.respondedAt = Date.now();
    await route.fulfill({ json });
  });
  return {
    state,
    marker,
    readCounts,
    requestLog,
    interruptNext(endpoint: string) {
      interruptions.push(endpoint);
    },
    failNext(endpoint: string, method = 'GET') {
      failures.push({ endpoint, method });
    },
    holdNext(endpoint: string, method = 'GET', pageContains?: string) {
      let release!: () => void;
      const wait = new Promise<void>((resolve) => {
        release = resolve;
      });
      holds.push({ endpoint, method, wait, pageContains });
      return release;
    },
  };
}

/** Read the route actually delivered to the mounted Three reconciler. */
export async function renderedWindowRoute(page: Page) {
  return page.evaluate(() => {
    type Fiber = {
      child?: Fiber;
      sibling?: Fiber;
      memoizedProps?: {
        points?: number[][];
        forward?: { maxParticles?: number };
      };
    };
    const roots =
      (
        window as unknown as {
          __overviewEvidenceRoots?: Array<{ current?: Fiber }>;
        }
      ).__overviewEvidenceRoots ?? [];
    const pending = roots.flatMap((root) =>
      root.current ? [root.current] : []
    );
    while (pending.length) {
      const fiber = pending.pop()!;
      if (
        fiber.memoizedProps?.forward?.maxParticles === 1 &&
        fiber.memoizedProps.points
      )
        return fiber.memoizedProps.points;
      if (fiber.child) pending.push(fiber.child);
      if (fiber.sibling) pending.push(fiber.sibling);
    }
    return [];
  });
}

/** Observe retained uPlot data rather than the fixture's response alone. */
export async function retainedHistoryTimes(page: Page) {
  const panel = page.getByRole('region', { name: 'Network latency history' });
  await expect(panel.locator('.uplot')).toBeVisible();
  return panel.evaluate((section) => {
    type Fiber = {
      return: Fiber | null;
      memoizedState?: { memoizedState: unknown; next: unknown } | null;
    };
    type Plot = { root: HTMLElement; data: number[][] };
    const key = Object.keys(section).find((item) =>
      item.startsWith('__reactFiber$')
    )!;
    let fiber: Fiber | null = (section as unknown as Record<string, Fiber>)[
      key
    ];
    const root = section.querySelector('.uplot');
    while (fiber) {
      let hook = fiber.memoizedState;
      while (hook) {
        const plot = (hook.memoizedState as { current?: Plot })?.current;
        if (plot?.root === root) return plot.data[0];
        hook = hook.next as typeof hook;
      }
      fiber = fiber.return;
    }
    return [];
  });
}

/** Observe the panel's selected window and the raw bundle during a held read. */
export async function historyWindowState(page: Page) {
  return page
    .getByRole('region', { name: 'Network latency history' })
    .evaluate((section) => {
      type Fiber = {
        return: Fiber | null;
        memoizedProps?: {
          selectedWindowSeconds?: number;
          history?: { window_seconds: number };
        };
      };
      const key = Object.keys(section).find((item) =>
        item.startsWith('__reactFiber$')
      )!;
      let fiber: Fiber | null = (section as unknown as Record<string, Fiber>)[
        key
      ];
      while (fiber) {
        if (fiber.memoizedProps?.selectedWindowSeconds !== undefined)
          return {
            selected: fiber.memoizedProps.selectedWindowSeconds,
            bundle: fiber.memoizedProps.history?.window_seconds ?? null,
          };
        fiber = fiber.return;
      }
      throw new Error('History panel props unavailable');
    });
}
