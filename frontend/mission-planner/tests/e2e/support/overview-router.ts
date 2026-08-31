import type { Page, Request, Route } from '@playwright/test';

import {
  OVERVIEW_SCENARIOS,
  type OverviewScenario,
} from '../fixtures/overview';
import {
  activeLinkPayload,
  gepPayload,
  historyPayload,
  poiPayload,
  routePayload,
  statusPayload,
} from './overview-payloads';

export type OverviewScenarioId = (typeof OVERVIEW_SCENARIOS)[number]['id'];

export interface RecordedOverviewRequest {
  readonly id: string;
  readonly cycle: number;
  readonly event: 'start' | 'complete' | 'failed' | 'blocked';
  readonly method: string;
  readonly url: string;
  readonly firstParty: boolean;
  readonly timestamp: number;
}

export interface OverviewRouter {
  readonly records: readonly RecordedOverviewRequest[];
  readonly cycles: readonly string[];
  scenario(): OverviewScenario;
  setScenario(id: OverviewScenarioId): void;
}

const radarPng = Uint8Array.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49,
  0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x06,
  0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x44,
  0x41, 0x54, 0x78, 0x9c, 0x63, 0xf8, 0xcf, 0xc0, 0xf0, 0x1f, 0x00, 0x05, 0x00,
  0x01, 0xff, 0x89, 0x99, 0x3d, 0x1d, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e,
  0x44, 0xae, 0x42, 0x60, 0x82,
]);

const blockedPatterns = [
  /\/api\/datasources\/proxy/i,
  /\/api\/plugins/i,
  /\/api\/dashboards/i,
  /\/dashboard/i,
  /\/grafana/i,
  /\/login/i,
  /:3000\//,
];

export async function installOverviewRouter(
  page: Page,
  initial: OverviewScenarioId = 'overview-nominal'
): Promise<OverviewRouter> {
  let scenario = scenarioById(initial);
  let cycle = 0;
  const records: RecordedOverviewRequest[] = [];
  const cycles: string[] = [];

  const record = (
    request: Request,
    event: RecordedOverviewRequest['event'],
    firstParty = false
  ) => {
    records.push({
      id: request.headers()['x-correlation-id'] ?? `fixture-${records.length}`,
      cycle,
      event,
      method: request.method(),
      url: request.url(),
      firstParty,
      timestamp: Date.now(),
    });
  };

  await page.context().route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (blockedPatterns.some((pattern) => pattern.test(request.url()))) {
      record(request, 'blocked');
      await route.abort('blockedbyclient');
      return;
    }
    if (url.hostname === 'server.arcgisonline.com') {
      record(request, 'complete');
      await fulfillPng(route, '1777294800');
      return;
    }
    if (url.pathname.startsWith('/api/')) {
      cycle += url.pathname === '/api/status' ? 1 : 0;
      cycles.push(`${cycle}:${url.pathname}:${url.search}`);
      record(request, 'start', true);
      await fulfillApi(route, scenario, url);
      record(request, 'complete', true);
      return;
    }
    await route.continue();
  });

  page.on('requestfailed', (request) => {
    const url = request.url();
    if (!blockedPatterns.some((pattern) => pattern.test(url))) {
      record(request, 'failed', urlIncludesFirstPartyApi(url));
    }
  });

  return {
    get records() {
      return records;
    },
    get cycles() {
      return cycles;
    },
    scenario: () => scenario,
    setScenario: (id) => {
      scenario = scenarioById(id);
    },
  };
}

async function fulfillApi(route: Route, scenario: OverviewScenario, url: URL) {
  if (url.pathname === '/api/status') {
    await route.fulfill(jsonResponse(statusPayload(scenario)));
    return;
  }
  if (url.pathname === '/api/monitoring/history') {
    await route.fulfill(jsonResponse(historyPayload(scenario)));
    return;
  }
  if (url.pathname === '/api/monitoring/ground-entry-point') {
    await route.fulfill(jsonResponse(gepPayload(scenario)));
    return;
  }
  if (url.pathname === '/api/pois/etas') {
    await route.fulfill(
      jsonResponse(poiPayload(scenario, url.searchParams.get('category')))
    );
    return;
  }
  if (url.pathname === '/api/route/coordinates/west') {
    await route.fulfill(jsonResponse(routePayload(scenario, 'west')));
    return;
  }
  if (url.pathname === '/api/route/coordinates/east') {
    await route.fulfill(jsonResponse(routePayload(scenario, 'east')));
    return;
  }
  if (url.pathname === '/api/active-x-link') {
    const state =
      url.searchParams.get('state') === 'warning' ? 'warning' : 'normal';
    await route.fulfill(jsonResponse(activeLinkPayload(scenario, state)));
    return;
  }
  if (
    /^\/api\/weather\/radar\/rainviewer\/\d+\/\d+\/\d+\.png$/.test(url.pathname)
  ) {
    await fulfillPng(route, '1777294800');
    return;
  }
  await route.fulfill({ status: 404, json: { detail: 'fixture_not_found' } });
}

function jsonResponse(json: unknown) {
  return {
    headers: {
      'cache-control': 'no-store',
      'content-type': 'application/json',
      'x-correlation-id': `fixture-${Date.now()}`,
    },
    json,
  };
}

async function fulfillPng(route: Route, frame: string) {
  await route.fulfill({
    body: Buffer.from(radarPng),
    headers: {
      'cache-control': 'public, max-age=60',
      'content-type': 'image/png',
      'x-correlation-id': `fixture-${Date.now()}`,
      'x-radar-frame-timestamp': frame,
    },
  });
}

function scenarioById(id: OverviewScenarioId): OverviewScenario {
  const scenario = OVERVIEW_SCENARIOS.find((item) => item.id === id);
  if (!scenario) throw new Error(`Unknown overview scenario: ${id}`);
  return scenario;
}

function urlIncludesFirstPartyApi(url: string): boolean {
  try {
    return new URL(url).pathname.startsWith('/api/');
  } catch {
    return false;
  }
}
