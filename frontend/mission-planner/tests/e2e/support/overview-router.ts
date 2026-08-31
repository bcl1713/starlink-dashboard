import type { Page, Request, Route } from '@playwright/test';

import type { OverviewScenario } from '../fixtures/overview';
import {
  activeLinkPayload,
  gepPayload,
  historyPayload,
  type LatencyPayloadOverride,
  poiPayload,
  routePayload,
  statusPayload,
} from './overview-payloads';
import {
  errorResponse,
  fulfillBasemap,
  fulfillPng,
  fulfillSourceError,
  jsonResponse,
} from './overview-router-responses';
import { sourceFor } from './overview-router-sources';
import {
  overviewScenarioById as scenarioById,
  type OverviewScenarioId,
} from './overview-empty-scenario';

export type { OverviewScenarioId };

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
  failSourceOnce(source: string, status: number, detail: string): void;
  failNextBasemap(): void;
  setLatency(payload: LatencyPayloadOverride | null): void;
  markNextManualCycle(): void;
  setLifecycleReporter(
    reporter: ((record: RecordedOverviewRequest) => void) | null
  ): void;
}

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
  let basemapFailures = 0;
  let latencyOverride: LatencyPayloadOverride | null = null;
  const sourceFailures = new Map<string, { status: number; detail: string }>();
  const records: RecordedOverviewRequest[] = [];
  const cycles: string[] = [];
  let lifecycleReporter: ((record: RecordedOverviewRequest) => void) | null =
    null;

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
    lifecycleReporter?.(record);
    return record;
  };

  const finishRecord = (
    started: RecordedOverviewRequest,
    event: RecordedOverviewRequest['event'],
    status: number | null
  ) => {
    const record: RecordedOverviewRequest = {
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
    };
    records.push(record);
    lifecycleReporter?.(record);
  };

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
      const response =
        basemapFailures > 0
          ? await fulfillSourceError(route, started.id, 503, 'basemap_error')
          : await fulfillBasemap(route, started.id);
      if (basemapFailures > 0) basemapFailures -= 1;
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
      const sourceFailure = sourceFailures.get(started.source);
      const response = sourceFailure
        ? await fulfillSourceError(
            route,
            started.id,
            sourceFailure.status,
            sourceFailure.detail
          )
        : await fulfillApi(route, scenario, url, started.id, latencyOverride);
      if (sourceFailure) sourceFailures.delete(started.source);
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
    failSourceOnce: (source, status, detail) => {
      sourceFailures.set(source, { status, detail });
    },
    failNextBasemap: () => {
      basemapFailures += 1;
    },
    setLatency: (payload) => {
      latencyOverride = payload;
    },
    markNextManualCycle: () => {
      nextManualRemaining = 12;
    },
    setLifecycleReporter: (reporter) => {
      lifecycleReporter = reporter;
    },
  };
}

async function fulfillApi(
  route: Route,
  scenario: OverviewScenario,
  url: URL,
  id: string,
  latencyOverride: LatencyPayloadOverride | null
) {
  if (scenario.id === 'overview-backend-failure') {
    await route.fulfill(errorResponse(id, 503, 'overview_backend_unavailable'));
    return { status: 503 };
  }
  if (
    (scenario.id === 'overview-radar-failure' ||
      scenario.id === 'overview-empty') &&
    /^\/api\/weather\/radar\/rainviewer\/\d+\/\d+\/\d+\.png$/.test(url.pathname)
  ) {
    await route.fulfill(errorResponse(id, 502, 'radar_unavailable'));
    return { status: 502 };
  }
  if (url.pathname === '/api/status') {
    await route.fulfill(
      jsonResponse(id, statusPayload(scenario, latencyOverride ?? undefined))
    );
    return { status: 200 };
  }
  if (url.pathname === '/api/monitoring/history') {
    await route.fulfill(
      jsonResponse(id, historyPayload(scenario, latencyOverride ?? undefined))
    );
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

function urlIncludesFirstPartyApi(url: string): boolean {
  try {
    return new URL(url).pathname.startsWith('/api/');
  } catch {
    return false;
  }
}
