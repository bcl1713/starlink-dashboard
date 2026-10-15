import type { Page } from '@playwright/test';
import type { StatusResponse } from '../../../src/services/status';
import type { OverviewLinkSettings } from '../../../src/services/overview-link-settings';

export async function trafficPathFixture(page: Page) {
  const state = {
    settings: {
      starshield_link_enabled: true,
      x_band_link_enabled: true,
      orbital_traffic_enabled: false,
    } as OverviewLinkSettings,
    getError: false,
    getStarted: false,
    saveError: false,
    selectionError: false,
    statusError: false,
    delayGet: false,
    releaseGet: () => {},
    selection: 'normal',
    expired: false,
    status: {
      position: {
        latitude: 0,
        longitude: -50,
        altitude: 35000,
        heading: 90,
        speed: 450,
      },
      ground_entry_point: { latitude: 10, longitude: -35 },
      network: {
        throughput_up_mbps: 500,
        throughput_down_mbps: 50,
        latency_ms: 20,
        packet_loss_percent: 0,
      },
      metric_availability: {
        throughput_up_mbps: true,
        throughput_down_mbps: true,
        latency_ms: true,
        packet_loss_percent: true,
      },
    } as Omit<StatusResponse, 'timestamp'>,
  };
  // Native Date, performance and animation frames keep rendering measurements
  // meaningful. Every successful poll has a fresh acquisition timestamp.
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/overview-adsb/settings')
      return route.fulfill({
        json: {
          enabled: false,
          mode: 'military_and_included',
          include_hexes: [],
          exclude_hexes: [],
          callsign_substrings: [],
          revision: 0,
        },
      });
    if (path === '/api/overview-adsb/traffic')
      return route.fulfill({
        json: {
          settings_revision: 0,
          generated_at_ms: Date.now(),
          contacts: [],
          sources: [],
        },
      });
    if (path === '/api/overview-links/settings') {
      if (route.request().method() === 'PUT') {
        if (state.saveError)
          return route.fulfill({
            status: 503,
            json: { detail: 'write unavailable' },
          });
        state.settings = {
          ...state.settings,
          ...route.request().postDataJSON(),
        };
      } else if (state.delayGet) {
        state.getStarted = true;
        await new Promise<void>((resolve) => {
          state.releaseGet = resolve;
        });
      }
      return route.fulfill({
        status: state.getError ? 503 : 200,
        json: state.getError ? { detail: 'read unavailable' } : state.settings,
      });
    }
    if (path === '/api/status') {
      if (state.statusError)
        return route.fulfill({
          status: 503,
          json: { detail: 'status unavailable' },
        });
      const now = Date.now();
      return route.fulfill({
        json: {
          ...state.status,
          timestamp: new Date(now - (state.expired ? 11000 : 0)).toISOString(),
        },
      });
    }
    if (path === '/api/satellites')
      return route.fulfill({
        json: [{ satellite_id: 'X-6', transport: 'X', longitude: -50 }],
      });
    if (path === '/api/active-x-link')
      return route.fulfill({
        status: state.selectionError ? 503 : 200,
        json: state.selectionError
          ? { detail: 'unavailable' }
          : { satellite_id: 'X-6', state: state.selection },
      });
    if (path === '/api/routes')
      return route.fulfill({
        json: { routes: [{ id: 'traffic-route', is_active: true }], total: 1 },
      });
    if (path === '/api/routes/traffic-route')
      return route.fulfill({
        json: {
          id: 'traffic-route',
          name: 'Traffic acceptance route',
          points: [
            { latitude: 0, longitude: -50 },
            { latitude: 10, longitude: -35 },
          ],
        },
      });
    if (path === '/api/overview-clocks/settings')
      return route.fulfill({
        json: {
          clocks: [
            { label: 'UTC', time_zone: 'UTC' },
            { label: 'East', time_zone: 'America/New_York' },
            { label: 'Central', time_zone: 'America/Chicago' },
            { label: 'West', time_zone: 'America/Los_Angeles' },
          ],
        },
      });
    if (path === '/api/overview-history/settings')
      return route.fulfill({ json: { window_seconds: 300 } });
    if (path === '/api/overview-history')
      return route.fulfill({
        json: {
          window_seconds: 300,
          start_timestamp_seconds: 1791028500,
          end_timestamp_seconds: 1791028800,
          step_seconds: 5,
          series: {
            starlink_dish_latitude_degrees: [
              [1791028790, 0],
              [1791028800, 1],
            ],
            starlink_dish_longitude_degrees: [
              [1791028790, -50],
              [1791028800, -49],
            ],
          },
        },
      });
    if (path === '/api/overview/upcoming-pois')
      return route.fulfill({ json: { state: 'no_active_mission', pois: [] } });
    return route.fulfill({ json: {} });
  });
  return state;
}
