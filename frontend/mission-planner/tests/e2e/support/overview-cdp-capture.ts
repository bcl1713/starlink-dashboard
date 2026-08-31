import { createHash } from 'node:crypto';
import type { Page, TestInfo } from '@playwright/test';

import { writeOverviewArtifact } from './overview-artifacts';
import { installLifecycleObserver } from './overview-lifecycle-observer';
import type {
  CdpNetworkEvent,
  CdpNetworkRecord,
  LifecycleLedger,
} from './overview-lifecycle-types';
import type { OverviewRouter } from './overview-router';

export interface ScreenshotFrameEvidence {
  readonly index: number;
  readonly startMs: number;
  readonly endMs: number;
  readonly gapMs: number;
  readonly sha256: string;
  readonly metadata: {
    readonly source: 'page-screenshot';
    readonly viewport: { width: number; height: number } | null;
  };
}

interface CdpRequestEvent {
  readonly requestId: string;
  readonly timestamp: number;
  readonly type?: string;
  readonly request: { readonly url: string; readonly method: string };
}

interface CdpResponseEvent {
  readonly requestId: string;
  readonly timestamp: number;
  readonly response: { readonly status: number };
}

interface CdpTerminalEvent {
  readonly requestId: string;
  readonly timestamp: number;
  readonly errorText?: string;
}

export async function installElementIdentity(page: Page) {
  await page.addInitScript(() => {
    const ids = new WeakMap<object, string>();
    let next = 0;
    Object.defineProperty(window, '__overviewObjectId', {
      value: (object: object | null | undefined) => {
        if (!object) return null;
        const found = ids.get(object);
        if (found) return found;
        const id = `object-${++next}`;
        ids.set(object, id);
        return id;
      },
    });
  });
}

export async function startCdpNetworkCapture(
  page: Page,
  observe: (record: CdpNetworkRecord) => Promise<void>
) {
  const session = await page.context().newCDPSession(page);
  const records = new Map<string, CdpNetworkRecord>();
  const events: CdpNetworkEvent[] = [];
  const reports: Promise<void>[] = [];
  const report = (record: CdpNetworkRecord) => reports.push(observe(record));
  session.on('Network.requestWillBeSent', (event: CdpRequestEvent) => {
    const record: CdpNetworkRecord = {
      cdpRequestId: event.requestId,
      event: 'Network.requestWillBeSent',
      url: event.request.url,
      method: event.request.method,
      type: event.type ?? 'Other',
      requestTimestamp: event.timestamp,
      responseTimestamp: null,
      terminalTimestamp: null,
      terminalOutcome: 'pending',
      status: null,
      failureText: null,
    };
    events.push({
      name: 'Network.requestWillBeSent',
      cdpRequestId: event.requestId,
      timestamp: event.timestamp,
      url: event.request.url,
      method: event.request.method,
      status: null,
      failureText: null,
    });
    records.set(event.requestId, record);
    report(record);
  });
  session.on('Network.responseReceived', (event: CdpResponseEvent) => {
    const record = records.get(event.requestId);
    if (record) {
      const responseRecord = {
        ...record,
        event: 'Network.responseReceived' as const,
        responseTimestamp: event.timestamp,
        status: event.response.status,
      };
      events.push({
        name: 'Network.responseReceived',
        cdpRequestId: event.requestId,
        timestamp: event.timestamp,
        url: record.url,
        method: record.method,
        status: event.response.status,
        failureText: null,
      });
      records.set(event.requestId, responseRecord);
      report(responseRecord);
    }
  });
  session.on('Network.loadingFinished', (event: CdpTerminalEvent) => {
    terminal(records, events, event, 'finished', null, report);
  });
  session.on('Network.loadingFailed', (event: CdpTerminalEvent) => {
    terminal(
      records,
      events,
      event,
      'failed',
      event.errorText ?? 'unknown',
      report
    );
  });
  await session.send('Network.enable');
  return {
    records: () => [...records.values()],
    events: () => [...events],
    stop: async () => {
      await Promise.all(reports);
      await session.detach();
    },
  };
}

export async function captureCdpContinuity(
  page: Page,
  router: OverviewRouter,
  testInfo: TestInfo,
  name: string
) {
  const observer = await installLifecycleObserver(page);
  const cdp = await startCdpNetworkCapture(page, observer.observeCdp);
  const frames: ScreenshotFrameEvidence[] = [];
  const started = performance.now();
  let previousStart: number | null = null;
  let representative: Buffer | null = null;
  let manualTriggered = false;
  let completedAt: number | null = null;
  try {
    while (performance.now() - started < 12_000) {
      if (!manualTriggered && scheduledTelemetryCycles(router).size >= 3) {
        manualTriggered = true;
        await triggerManualRefreshDuringCapture(page, router);
      }
      const startMs = performance.now();
      const png = await page.screenshot({ type: 'png' });
      if (!representative) representative = png;
      frames.push({
        index: frames.length,
        startMs,
        endMs: performance.now(),
        gapMs: previousStart === null ? 0 : startMs - previousStart,
        sha256: createHash('sha256').update(png).digest('hex'),
        metadata: { source: 'page-screenshot', viewport: page.viewportSize() },
      });
      previousStart = startMs;
      if (continuityCyclesComplete(router)) completedAt ??= performance.now();
      if (completedAt !== null && performance.now() - completedAt >= 250) break;
      await page.waitForTimeout(180);
    }
  } finally {
    await cdp.stop();
  }
  await page.waitForTimeout(75);
  const eventLedger = await observer.stop();
  const payload = {
    viewport: page.viewportSize(),
    captureMetadata: {
      source: 'Playwright Chromium CDP Network domain',
      primaryOracle: 'browser-originated Network lifecycle records',
      supplementalOracle: 'deterministic fixture-router cycle ledger',
      frameCount: frames.length,
      elapsedMs: performance.now() - started,
    },
    frames,
    eventLedger,
    cdpNetworkLedger: cdp.records(),
    cdpNetworkEvents: cdp.events(),
    fixtureRequestLedger: router.records,
    cycles: router.cycles,
  };
  await persistEvidence(testInfo, name, payload, eventLedger, representative);
  return payload;
}

function terminal(
  records: Map<string, CdpNetworkRecord>,
  events: CdpNetworkEvent[],
  event: CdpTerminalEvent,
  outcome: 'finished' | 'failed',
  failureText: string | null,
  report: (record: CdpNetworkRecord) => void
) {
  const record = records.get(event.requestId);
  if (!record) return;
  const terminalRecord = {
    ...record,
    event:
      outcome === 'finished'
        ? ('Network.loadingFinished' as const)
        : ('Network.loadingFailed' as const),
    terminalTimestamp: event.timestamp,
    terminalOutcome: outcome,
    failureText,
  } satisfies CdpNetworkRecord;
  events.push({
    name: terminalRecord.event,
    cdpRequestId: event.requestId,
    timestamp: event.timestamp,
    url: record.url,
    method: record.method,
    status: terminalRecord.status,
    failureText,
  });
  records.set(event.requestId, terminalRecord);
  report(terminalRecord);
}

function scheduledTelemetryCycles(router: OverviewRouter) {
  return new Set(
    router.records
      .filter(
        (record) =>
          record.kind === 'scheduled' &&
          record.source === 'telemetry' &&
          record.event === 'complete'
      )
      .map((record) => record.cycle)
  );
}

function continuityCyclesComplete(router: OverviewRouter) {
  const manualSources = new Set(
    router.records
      .filter(
        (record) => record.kind === 'manual' && record.event === 'complete'
      )
      .map((record) => record.source)
  );
  return (
    scheduledTelemetryCycles(router).size >= 5 &&
    manualSources.has('telemetry') &&
    manualSources.has('history')
  );
}

async function triggerManualRefreshDuringCapture(
  page: Page,
  router: OverviewRouter
) {
  const controls = page.getByRole('button', { name: 'Overview controls' });
  if ((await controls.getAttribute('aria-expanded')) !== 'true')
    await controls.click();
  router.markNextManualCycle();
  await page.getByRole('button', { name: 'Refresh overview' }).click();
}

async function persistEvidence(
  testInfo: TestInfo,
  name: string,
  payload: unknown,
  ledger: LifecycleLedger,
  representative: Buffer | null
) {
  const json = JSON.stringify(payload, null, 2);
  await testInfo.attach(`event-continuity-${name}.json`, {
    body: json,
    contentType: 'application/json',
  });
  await writeOverviewArtifact(`event-continuity-${name}.json`, json);
  await writeOverviewArtifact(
    `event-ledger-${name}.json`,
    JSON.stringify(ledger, null, 2)
  );
  if (representative) {
    await testInfo.attach(`raw-capture-${name}-representative`, {
      body: representative,
      contentType: 'image/png',
    });
    await writeOverviewArtifact(
      `raw-capture-${name}-representative.png`,
      representative
    );
  }
}
