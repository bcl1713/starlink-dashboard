import { expect, type Page } from '@playwright/test';

const metrics = [
  'starlink_network_latency_ms_current',
  'starlink_network_throughput_down_mbps_current',
  'starlink_network_throughput_up_mbps_current',
  'starlink_network_packet_loss_percent',
  'starlink_dish_obstruction_percent',
];

/** Real scene/panels with controlled API responses, including retained errors. */
export async function compositionFixture(page: Page) {
  const state = {
    now: null as number | null,
    errors: false,
    stale: false,
    staleAgeSeconds: 600,
    route: true,
    satellite: 'X-6' as string | null,
    nextName: 'Atlantic handoff',
    destination: 'RKSO',
    arrival: 'intermediate' as 'intermediate' | 'destination' | 'departure',
    windowSeconds: 300,
  };
  await page.route('**/api/**', async (route) => {
    const endpoint = new URL(route.request().url()).pathname;
    const now = state.now ?? Date.now();
    const observed = new Date(
      now - (state.stale ? state.staleAgeSeconds * 1000 : 0)
    ).toISOString();
    if (state.errors && endpoint !== '/api/overview-history/settings')
      return route.fulfill({ status: 503, json: { detail: 'Fixture outage' } });
    if (endpoint === '/api/overview-clocks/settings')
      return route.fulfill({
        json: {
          clocks: [
            ['Zulu / UTC', 'UTC'],
            ['Washington, DC', 'America/New_York'],
            ['Omaha, NE', 'America/Chicago'],
            ['Tokyo, JP', 'Asia/Tokyo'],
          ].map(([label, time_zone]) => ({ label, time_zone })),
        },
      });
    if (endpoint === '/api/overview-history/settings') {
      if (route.request().method() === 'PUT')
        state.windowSeconds = route.request().postDataJSON().window_seconds;
      return route.fulfill({ json: { window_seconds: state.windowSeconds } });
    }
    if (endpoint === '/api/status')
      return route.fulfill({
        json: {
          timestamp: observed,
          position: { latitude: 35, longitude: -100, altitude: 35000 },
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
        },
      });
    if (endpoint === '/api/satellites')
      return route.fulfill({
        json: [{ satellite_id: 'X-6', transport: 'X', longitude: -70 }],
      });
    if (endpoint === '/api/active-x-link')
      return route.fulfill({
        json: { satellite_id: state.satellite, state: 'normal' },
      });
    if (endpoint === '/api/routes')
      return route.fulfill({
        json: {
          routes: state.route ? [{ id: 'route', is_active: true }] : [],
          total: state.route ? 1 : 0,
        },
      });
    if (endpoint === '/api/routes/route')
      return route.fulfill({
        json: {
          id: 'route',
          name: 'Operational route',
          points: [
            { latitude: 35, longitude: -100 },
            { latitude: 38, longitude: -90 },
            { latitude: 45, longitude: -80 },
          ],
        },
      });
    if (endpoint === '/api/overview/upcoming-pois') {
      if (!state.route)
        return route.fulfill({
          json: {
            state: 'route_unavailable',
            calculated_at: new Date(now).toISOString(),
            pois: [],
          },
        });
      const phase =
        state.arrival === 'departure' ? 'pre_departure' : 'in_flight';
      return route.fulfill({
        json: {
          state: 'available',
          calculated_at: new Date(now).toISOString(),
          flight_phase: phase,
          scheduled_departure_time: new Date(now - 720_000).toISOString(),
          position_state: state.stale ? 'stale' : 'fresh',
          position_observed_at: observed,
          pois: [
            {
              poi_id: 'departure',
              name: 'KADW',
              kind: 'departure',
              upcoming: phase === 'pre_departure',
              projected_route_progress: 0,
              latitude: 35,
              longitude: -100,
            },
            {
              poi_id: 'next',
              name: state.nextName,
              kind: 'x_band_transition',
              upcoming: state.arrival === 'intermediate',
              projected_route_progress: 40,
              latitude: 38,
              longitude: -90,
              map_retained: true,
              estimated_arrival_time: new Date(now + 183_600_000).toISOString(),
              eta_type: 'estimated',
            },
            {
              poi_id: 'destination',
              name: state.destination,
              kind: 'arrival',
              upcoming: true,
              projected_route_progress: 100,
              latitude: 45,
              longitude: -80,
              map_retained: true,
              estimated_arrival_time: new Date(now + 190_800_000).toISOString(),
              eta_type: 'estimated',
            },
          ],
        },
      });
    }
    if (endpoint === '/api/overview-history') {
      const end = Math.floor(now / 1000);
      const series = (offset: number) =>
        Array.from({ length: 61 }, (_, i) => [
          end - state.windowSeconds + (i * state.windowSeconds) / 60,
          20 + (i % 13) + offset,
        ]);
      return route.fulfill({
        json: {
          window_seconds: state.windowSeconds,
          start_timestamp_seconds: end - state.windowSeconds,
          end_timestamp_seconds: end,
          step_seconds: state.windowSeconds / 60,
          series: {
            ...Object.fromEntries(metrics.map((metric) => [metric, series(0)])),
            starlink_dish_latitude_degrees: [
              [end - 5, 34],
              [end, 35],
            ],
            starlink_dish_longitude_degrees: [
              [end - 5, -101],
              [end, -100],
            ],
          },
          rolling_5m: Object.fromEntries(
            metrics.map((metric) => [
              metric,
              {
                state: 'available',
                min: series(-4),
                avg: series(-1),
                max: series(4),
              },
            ])
          ),
        },
      });
    }
    return route.fulfill({ json: {} });
  });
  return state;
}

export async function desktopGeometry(page: Page) {
  return page.evaluate(() => {
    const get = (selector: string) =>
      document.querySelector<HTMLElement>(selector)!;
    const box = (selector: string) => get(selector).getBoundingClientRect();
    const pageBox = box('.overview-page');
    const panels = [
      ...document.querySelectorAll<HTMLElement>(
        '.operational-clock, .overview-clock-panel--message, .overview-metric-history, .overview-metric-history-panels__header, .overview-planned-satellite, .globe-legend, .overview-map-status, .overview-arrival, .overview-fullscreen-control'
      ),
    ];
    const clock = box('.overview-clock-panel');
    const metric = box('.overview-metric-history-panels');
    const satellite = box('.overview-planned-satellite');
    const arrival = box('.overview-arrival');
    const legend = box('.globe-legend');
    const bounds = panels.map((node) => node.getBoundingClientRect());
    return {
      fits: panels.every(
        (node) =>
          node.scrollHeight <= node.clientHeight + 1 &&
          node.scrollWidth <= node.clientWidth + 1
      ),
      contained: bounds.every(
        (r) =>
          r.left >= pageBox.left &&
          r.right <= pageBox.right + 1 &&
          r.top >= pageBox.top &&
          r.bottom <= pageBox.bottom + 1
      ),
      overlaps: bounds.flatMap((a, i) =>
        bounds
          .slice(i + 1)
          .filter(
            (b) =>
              a.left < b.right - 1 &&
              a.right > b.left + 1 &&
              a.top < b.bottom - 1 &&
              a.bottom > b.top + 1
          )
      ).length,
      scroll:
        get('.app-route-content').scrollHeight >
          get('.app-route-content').clientHeight + 1 ||
        get('.overview-page').scrollHeight >
          get('.overview-page').clientHeight + 1,
      documentScroll: document.documentElement.scrollHeight > innerHeight + 1,
      horizontalOverflow:
        document.documentElement.scrollWidth > innerWidth ||
        get('.overview-page').scrollWidth > get('.overview-page').clientWidth,
      metricWidth: Math.round(metric.width),
      clearWidth: Math.min(satellite.left, legend.left) - metric.right - 40,
      clearHeight: arrival.top - clock.bottom - 40,
      plots: [
        ...document.querySelectorAll('.overview-metric-history__viewport'),
      ].map((node) => node.getBoundingClientRect().height),
      panels: bounds.map((r) => r.toJSON()),
    };
  });
}

export async function expectDesktopFit(page: Page, broad = true) {
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'desktop'
  );
  await expect
    .poll(async () => {
      const g = await desktopGeometry(page);
      return {
        fits: g.fits,
        contained: g.contained,
        overlaps: g.overlaps,
        scroll: g.scroll,
        documentScroll: g.documentScroll,
        horizontalOverflow: g.horizontalOverflow,
      };
    })
    .toEqual({
      fits: true,
      contained: true,
      overlaps: 0,
      scroll: false,
      documentScroll: false,
      horizontalOverflow: false,
    });
  const g = await desktopGeometry(page);
  expect(g.metricWidth).toBe(440);
  expect(g.plots).toHaveLength(5);
  expect(g.plots.every((height) => height >= 48)).toBe(true);
  if (broad) {
    expect(g.clearWidth).toBeGreaterThanOrEqual(900);
    expect(g.clearHeight).toBeGreaterThanOrEqual(500);
  }
}
