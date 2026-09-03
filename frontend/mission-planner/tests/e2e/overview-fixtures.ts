import type { Page } from '@playwright/test';
import poiFixture from '../../src/services/fixtures/poi-eta-list-response.json' with { type: 'json' };

const metrics = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
];
const now = '2026-09-03T09:00:00Z';

export async function installOverviewRoutes(page: Page) {
  let statusRequests = 0;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/status') {
      statusRequests += 1;
      await route.fulfill({
        json: {
          source: 'simulation',
          timestamp: now,
          observed_at: now,
          received_at: now,
          position: {
            latitude: 41,
            longitude: -96,
            altitude: 35000,
            speed: 420,
            heading: 95,
          },
          network: {
            latency_ms: 27,
            throughput_down_mbps: 142,
            throughput_up_mbps: 18,
            packet_loss_percent: 0.4,
          },
          obstruction: { obstruction_percent: 1.2 },
          environmental: {
            signal_quality_percent: 98,
            uptime_seconds: 3600,
            temperature_celsius: null,
          },
        },
      });
      return;
    }
    if (path === '/api/monitoring/history') {
      await route.fulfill({
        json: {
          generated_at: now,
          window_start: '2026-09-03T08:30:00Z',
          window_end: now,
          range_seconds: 1800,
          step_seconds: 1,
          series: metrics.map((metric) => ({
            metric,
            samples:
              metric === 'latency_ms'
                ? [
                    { timestamp: '2026-09-03T08:59:58Z', value: 21 },
                    { timestamp: '2026-09-03T08:59:59Z', value: 33 },
                  ]
                : metric === 'packet_loss_percent'
                  ? [
                      { timestamp: '2026-09-03T08:59:58Z', value: 0.2 },
                      { timestamp: '2026-09-03T08:59:59Z', value: 0.8 },
                    ]
                  : [],
          })),
        },
      });
      return;
    }
    if (path === '/api/monitoring/ground-entry-point') {
      await route.fulfill({
        json: {
          available: true,
          observed_at: now,
          generated_at: now,
          display: 'Omaha, Nebraska, US',
          city: 'Omaha',
          region: 'Nebraska',
          country: 'US',
          latitude: 41.2565,
          longitude: -95.9345,
        },
      });
      return;
    }
    if (path === '/api/pois/etas') {
      const template = poiFixture.pois[0];
      await route.fulfill({
        json: {
          pois: Array.from({ length: 5 }, (_, index) => ({
            ...template,
            poi_id: `poi-${index + 1}`,
            name: `Waypoint ${index + 1} with safe operational label`,
            eta_seconds: (index + 1) * 60,
          })),
          total: 5,
          timestamp: now,
        },
      });
      return;
    }
    await route.abort('blockedbyclient');
  });
  return () => statusRequests;
}
