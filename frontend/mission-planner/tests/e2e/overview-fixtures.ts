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
const generatedAt = Date.now();
const now = new Date(generatedAt).toISOString();
const staleObservedAt = new Date(generatedAt - 120_000).toISOString();
const windowStart = new Date(generatedAt - 1_800_000).toISOString();
const firstSample = new Date(generatedAt - 2000).toISOString();
const secondSample = new Date(generatedAt - 1000).toISOString();

type SourceName = 'status' | 'pois' | 'gep';

interface OverviewRouteOptions {
  poiNameLength?: number;
  failedSources?: readonly SourceName[];
  staleStatus?: boolean;
}

export interface OverviewRouteTracker {
  (): number;
  starts: () => readonly number[];
  paths: () => readonly string[];
  setFailed: (source: SourceName, failed: boolean) => void;
}

export async function installOverviewRoutes(
  page: Page,
  options: OverviewRouteOptions = {}
): Promise<OverviewRouteTracker> {
  let statusRequests = 0;
  const statusStarts: number[] = [];
  const requestPaths: string[] = [];
  const failed = new Set(options.failedSources ?? []);
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    requestPaths.push(path);
    if (path === '/api/status') {
      statusRequests += 1;
      statusStarts.push(performance.now());
      if (failed.has('status')) {
        await route.fulfill({ status: 503, json: { detail: 'unavailable' } });
        return;
      }
      await route.fulfill({
        json: {
          source: 'simulation',
          timestamp: options.staleStatus ? staleObservedAt : now,
          observed_at: options.staleStatus ? staleObservedAt : now,
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
          window_start: windowStart,
          window_end: now,
          range_seconds: 1800,
          step_seconds: 1,
          series: metrics.map((metric) => ({
            metric,
            samples:
              metric === 'latency_ms'
                ? [
                    { timestamp: firstSample, value: 21 },
                    { timestamp: secondSample, value: 33 },
                  ]
                : metric === 'packet_loss_percent'
                  ? [
                      { timestamp: firstSample, value: 0.2 },
                      { timestamp: secondSample, value: 0.8 },
                    ]
                  : [],
          })),
        },
      });
      return;
    }
    if (path === '/api/monitoring/ground-entry-point') {
      if (failed.has('gep')) {
        await route.fulfill({ status: 503, json: { detail: 'unavailable' } });
        return;
      }
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
      if (failed.has('pois')) {
        await route.fulfill({ status: 503, json: { detail: 'unavailable' } });
        return;
      }
      const template = poiFixture.pois[0];
      await route.fulfill({
        json: {
          pois: Array.from({ length: 5 }, (_, index) => {
            const prefix = `Waypoint ${index + 1} `;
            const name = options.poiNameLength
              ? prefix.padEnd(options.poiNameLength, 'x')
              : `${prefix}with safe operational label`;
            return {
              ...template,
              poi_id: `poi-${index + 1}`,
              name,
              eta_seconds: (index + 1) * 60,
            };
          }),
          total: 5,
          timestamp: now,
        },
      });
      return;
    }
    await route.abort('blockedbyclient');
  });
  const tracker = (() => statusRequests) as OverviewRouteTracker;
  tracker.starts = () => [...statusStarts];
  tracker.paths = () => [...requestPaths];
  tracker.setFailed = (source, isFailed) => {
    if (isFailed) failed.add(source);
    else failed.delete(source);
  };
  return tracker;
}
