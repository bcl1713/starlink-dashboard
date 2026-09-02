import { expect, test } from '@playwright/test';

test.describe('Mission Planner API origin', () => {
  test('loads an empty mission collection through the same-origin API proxy', async ({
    page,
  }) => {
    const missionRequests: string[] = [];

    await page.route(
      'http://localhost:5173/api/v2/missions**',
      async (route) => {
        missionRequests.push(route.request().url());
        await route.fulfill({
          headers: { 'X-Total-Count': '0' },
          json: [],
        });
      }
    );

    await page.goto('/missions');

    await expect(
      page.getByText('No missions yet', { exact: true })
    ).toBeVisible();
    await expect(page.getByText(/Error loading missions/)).not.toBeVisible();
    expect(missionRequests).toHaveLength(1);
    expect(missionRequests[0]).toMatch(
      /^http:\/\/localhost:5173\/api\/v2\/missions\?/
    );
  });

  test('runs overview lanes only through origin-relative API routes', async ({
    page,
  }) => {
    const apiRequests: string[] = [];
    const forbiddenRequests: string[] = [];
    const expectedPaths = [
      '/api/status',
      '/api/monitoring/history',
      '/api/monitoring/ground-entry-point',
      '/api/pois/etas',
    ];
    const now = '2026-09-02T12:00:00Z';
    const metrics = [
      'latitude_degrees',
      'longitude_degrees',
      'latency_ms',
      'throughput_down_mbps',
      'throughput_up_mbps',
      'packet_loss_percent',
    ];

    page.on('request', (request) => {
      if (!['fetch', 'xhr'].includes(request.resourceType())) return;
      const url = new URL(request.url());
      if (url.origin !== 'http://localhost:5173')
        forbiddenRequests.push(request.url());
      if (/grafana|prometheus|:3000|:9090/i.test(request.url())) {
        forbiddenRequests.push(request.url());
      }
      if (url.pathname.startsWith('/api/')) apiRequests.push(request.url());
    });
    await page.route('http://localhost:5173/api/**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/api/status') {
        await route.fulfill({
          json: {
            source: 'simulation',
            timestamp: now,
            observed_at: now,
            received_at: now,
            position: {
              latitude: 41,
              longitude: -96,
              altitude: 1,
              speed: 0,
              heading: 0,
            },
            network: {
              latency_ms: 20,
              throughput_down_mbps: 100,
              throughput_up_mbps: 10,
              packet_loss_percent: 1,
            },
            obstruction: { obstruction_percent: 2 },
            environmental: {
              signal_quality_percent: 98,
              uptime_seconds: 10,
              temperature_celsius: null,
            },
          },
        });
      } else if (path === '/api/monitoring/history') {
        await route.fulfill({
          json: {
            generated_at: now,
            window_start: '2026-09-02T11:30:00Z',
            window_end: now,
            range_seconds: 1800,
            step_seconds: 1,
            series: metrics.map((metric) => ({ metric, samples: [] })),
          },
        });
      } else if (path === '/api/monitoring/ground-entry-point') {
        await route.fulfill({
          json: {
            available: false,
            observed_at: null,
            generated_at: now,
            display: null,
            city: null,
            region: null,
            country: null,
            latitude: null,
            longitude: null,
          },
        });
      } else if (path === '/api/pois/etas') {
        await route.fulfill({ json: { pois: [], total: 0, timestamp: now } });
      } else {
        await route.abort('blockedbyclient');
      }
    });

    await page.goto('/overview');
    await expect(
      page.getByRole('heading', { name: 'Connectivity overview' })
    ).toBeVisible();
    await expect(page.getByText('20.0 ms', { exact: true })).toBeVisible();
    await expect
      .poll(() => new Set(apiRequests.map((url) => new URL(url).pathname)).size)
      .toBe(4);

    const paths = new Set(apiRequests.map((url) => new URL(url).pathname));
    expect(paths).toEqual(new Set(expectedPaths));
    expect(
      apiRequests.every(
        (url) => new URL(url).origin === 'http://localhost:5173'
      )
    ).toBe(true);
    expect(forbiddenRequests).toEqual([]);
  });

  test('downloads data exports through the same-origin API proxy', async ({
    page,
  }) => {
    const exportRequests: string[] = [];

    await page.route(
      'http://localhost:5173/api/export/starlink-csv**',
      async (route) => {
        exportRequests.push(route.request().url());
        await route.fulfill({
          headers: { 'Content-Type': 'text/csv' },
          body: 'timestamp,latitude\n',
        });
      }
    );

    await page.goto('/export');
    await page.getByRole('button', { name: 'Export CSV' }).click();

    await expect.poll(() => exportRequests).toHaveLength(1);
    expect(exportRequests[0]).toMatch(
      /^http:\/\/localhost:5173\/api\/export\/starlink-csv\?/
    );
  });
});
