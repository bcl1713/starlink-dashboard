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
import { sourceFor } from './overview-router-sources';

export type OverviewScenarioId = (typeof OVERVIEW_SCENARIOS)[number]['id'];

export interface RecordedOverviewRequest {
  readonly id: string;
  readonly cycle: number;
  readonly event: 'start' | 'complete' | 'error' | 'failed' | 'blocked';
  readonly kind: 'initial' | 'scheduled' | 'manual';
  readonly source: string;
  readonly method: string;
  readonly url: string;
  readonly status: number | null;
  readonly outcome: 'pending' | 'complete' | 'error' | 'transport-failed';
  readonly firstParty: boolean;
  readonly startedAt: number;
  readonly completedAt: number | null;
}

export interface OverviewRouter {
  readonly records: readonly RecordedOverviewRequest[];
  readonly cycles: readonly string[];
  scenario(): OverviewScenario;
  setScenario(id: OverviewScenarioId): void;
  markNextManualCycle(): void;
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
  let requestSequence = 0;
  let nextManualRemaining = 0;
  const records: RecordedOverviewRequest[] = [];
  const cycles: string[] = [];

  const startRecord = (
    request: Request,
    kind: RecordedOverviewRequest['kind'],
    firstParty = false
  ): RecordedOverviewRequest => {
    const record = {
      id: `fixture-${++requestSequence}`,
      cycle,
      event: 'start' as const,
      kind,
      source: sourceFor(new URL(request.url())),
      method: request.method(),
      url: request.url(),
      status: null,
      outcome: 'pending' as const,
      firstParty,
      startedAt: performance.now(),
      completedAt: null,
    };
    records.push(record);
    return record;
  };

  const finishRecord = (
    started: RecordedOverviewRequest,
    event: RecordedOverviewRequest['event'],
    status: number | null
  ) =>
    records.push({
      ...started,
      event,
      status,
      outcome:
        event === 'complete'
          ? 'complete'
          : event === 'failed'
            ? 'transport-failed'
            : 'error',
      completedAt: performance.now(),
    });

  await page.context().route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (blockedPatterns.some((pattern) => pattern.test(request.url()))) {
      const started = startRecord(request, 'initial');
      finishRecord(started, 'blocked', null);
      await route.abort('blockedbyclient');
      return;
    }
    if (url.hostname === 'server.arcgisonline.com') {
      const started = startRecord(request, 'initial');
      const response = await fulfillPng(route, started.id, '1777294800');
      finishRecord(
        started,
        response.status >= 400 ? 'error' : 'complete',
        response.status
      );
      return;
    }
    if (url.pathname.startsWith('/api/')) {
      cycle += url.pathname === '/api/status' ? 1 : 0;
      const kind =
        nextManualRemaining > 0
          ? 'manual'
          : cycle <= 1
            ? 'initial'
            : 'scheduled';
      if (nextManualRemaining > 0) nextManualRemaining -= 1;
      cycles.push(`${cycle}:${url.pathname}:${url.search}`);
      const started = startRecord(request, kind, true);
      const response = await fulfillApi(route, scenario, url, started.id);
      finishRecord(
        started,
        response.status >= 400 ? 'error' : 'complete',
        response.status
      );
      return;
    }
    await route.continue();
  });

  page.on('requestfailed', (request) => {
    const url = request.url();
    if (!blockedPatterns.some((pattern) => pattern.test(url))) {
      const started = startRecord(
        request,
        'initial',
        urlIncludesFirstPartyApi(url)
      );
      finishRecord(started, 'failed', null);
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
    markNextManualCycle: () => {
      nextManualRemaining = 12;
    },
  };
}

async function fulfillApi(
  route: Route,
  scenario: OverviewScenario,
  url: URL,
  id: string
) {
  if (scenario.id === 'overview-backend-failure') {
    await route.fulfill(errorResponse(id, 503, 'overview_backend_unavailable'));
    return { status: 503 };
  }
  if (
    scenario.id === 'overview-radar-failure' &&
    /^\/api\/weather\/radar\/rainviewer\/\d+\/\d+\/\d+\.png$/.test(url.pathname)
  ) {
    await route.fulfill(errorResponse(id, 502, 'radar_unavailable'));
    return { status: 502 };
  }
  if (url.pathname === '/api/status') {
    await route.fulfill(jsonResponse(id, statusPayload(scenario)));
    return { status: 200 };
  }
  if (url.pathname === '/api/monitoring/history') {
    await route.fulfill(jsonResponse(id, historyPayload(scenario)));
    return { status: 200 };
  }
  if (url.pathname === '/api/monitoring/ground-entry-point') {
    await route.fulfill(jsonResponse(id, gepPayload(scenario)));
    return { status: 200 };
  }
  if (url.pathname === '/api/pois/etas') {
    await route.fulfill(
      jsonResponse(id, poiPayload(scenario, url.searchParams.get('category')))
    );
    return { status: 200 };
  }
  if (url.pathname === '/api/route/coordinates/west') {
    await route.fulfill(jsonResponse(id, routePayload(scenario, 'west')));
    return { status: 200 };
  }
  if (url.pathname === '/api/route/coordinates/east') {
    await route.fulfill(jsonResponse(id, routePayload(scenario, 'east')));
    return { status: 200 };
  }
  if (url.pathname === '/api/active-x-link') {
    const state =
      url.searchParams.get('state') === 'warning' ? 'warning' : 'normal';
    await route.fulfill(jsonResponse(id, activeLinkPayload(scenario, state)));
    return { status: 200 };
  }
  if (
    /^\/api\/weather\/radar\/rainviewer\/\d+\/\d+\/\d+\.png$/.test(url.pathname)
  ) {
    return fulfillPng(route, id, '1777294800');
  }
  await route.fulfill(errorResponse(id, 404, 'fixture_not_found'));
  return { status: 404 };
}

function jsonResponse(id: string, json: unknown) {
  return {
    headers: {
      'cache-control': 'no-store',
      'content-type': 'application/json',
      'x-correlation-id': id,
    },
    json,
  };
}

function errorResponse(id: string, status: number, detail: string) {
  return {
    status,
    headers: {
      'cache-control': 'no-store',
      'content-type': 'application/json',
      'x-correlation-id': id,
    },
    json: { detail },
  };
}

async function fulfillPng(route: Route, id: string, frame: string) {
  await route.fulfill({
    body: Buffer.from(radarPng),
    headers: {
      'cache-control': 'public, max-age=60',
      'content-type': 'image/png',
      'x-correlation-id': id,
      'x-radar-frame-timestamp': frame,
    },
  });
  return { status: 200 };
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
