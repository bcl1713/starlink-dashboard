import { createHash } from 'node:crypto';
import type { Page, TestInfo } from '@playwright/test';

import { writeOverviewArtifact } from './overview-artifacts';
import { startCdpNetworkCapture } from './overview-cdp-network';
import { EVIDENCE_LIMITS } from './overview-evidence-limits';
import { installLifecycleObserver } from './overview-lifecycle-observer';
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
    cdpRetention: cdp.retention(),
    fixtureRequestLedger: router.records,
    cycles: router.cycles,
  };
  const artifact = {
    captureMetadata: payload.captureMetadata,
    frames: payload.frames,
    eventLedger: {
      installedAt: eventLedger.installedAt,
      stoppedAt: eventLedger.stoppedAt,
      mutations: eventLedger.mutations,
      identityTransitions: eventLedger.identityTransitions,
      retention: eventLedger.retention,
      sampleCount: eventLedger.samples.length,
      sampleIndex: eventLedger.samples.map((sample) => ({
        at: sample.at,
        phase: sample.phase,
        cdpRequestId: sample.request?.cdpRequestId ?? null,
      })),
    },
    cdpNetworkLedger: payload.cdpNetworkLedger,
    cdpNetworkEvents: payload.cdpNetworkEvents,
    cdpRetention: payload.cdpRetention,
    fixtureRequestLedger: payload.fixtureRequestLedger.map((record) => ({
      id: record.id,
      cycle: record.cycle,
      event: record.event,
      kind: record.kind,
      source: record.source,
      method: record.method,
      url: new URL(record.url).pathname,
      status: record.status,
      outcome: record.outcome,
      firstParty: record.firstParty,
    })),
    cycles: payload.cycles,
  };
  await persistEvidence(testInfo, name, artifact, representative);
  return payload;
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
  representative: Buffer | null
) {
  const json = JSON.stringify(payload, null, 2);
  await testInfo.attach(`event-continuity-${name}.json`, {
    body: json,
    contentType: 'application/json',
  });
  await writeOverviewArtifact(`event-continuity-${name}.json`, json);
  if (representative) {
    await testInfo.attach(`raw-capture-${name}-representative`, {
      body: representative,
      contentType: 'image/png',
    });
    await writeOverviewArtifact(
      `raw-capture-${name}-representative.png`,
      representative,
      EVIDENCE_LIMITS.screenshotBytes
    );
  }
}
