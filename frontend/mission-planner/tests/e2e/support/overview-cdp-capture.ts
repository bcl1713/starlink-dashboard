import { createHash } from 'node:crypto';
import type { Page, TestInfo } from '@playwright/test';

import type { OverviewRouter } from './overview-router';
import { writeOverviewArtifact } from './overview-artifacts';
import { installLifecycleObserver } from './overview-lifecycle-observer';
import type { LifecycleLedger } from './overview-lifecycle-types';

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
  const pendingReports: Promise<void>[] = [];
  const reportErrors: string[] = [];
  router.setLifecycleReporter((record) => {
    pendingReports.push(
      observer.report(record).catch((error: unknown) => {
        reportErrors.push(
          error instanceof Error ? error.message : String(error)
        );
      })
    );
  });

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
    router.setLifecycleReporter(null);
  }
  await Promise.all(pendingReports);
  await page.waitForTimeout(75);
  const eventLedger = await observer.stop();
  if (reportErrors.length) {
    throw new Error(`Lifecycle reporter failed: ${reportErrors.join('; ')}`);
  }

  const elapsedMs = performance.now() - started;
  const rawGaps = frames.slice(1).map((frame) => frame.gapMs);
  const captureMetadata = {
    source: 'timestamped Playwright page screenshots',
    primaryOracle: 'event-driven lifecycle ledger',
    visualClaimLimit:
      'Supporting captures are undersampled relative to faster transient events.',
    frameCount: frames.length,
    elapsedMs,
    achievedFps:
      frames.length > 1
        ? ((frames.length - 1) * 1000) /
          (frames.at(-1)!.startMs - frames[0]!.startMs)
        : 0,
    minGapMs: rawGaps.length ? Math.min(...rawGaps) : null,
    maxGapMs: rawGaps.length ? Math.max(...rawGaps) : null,
  };
  const payload = {
    viewport: page.viewportSize(),
    elapsedMs,
    captureMetadata,
    frames,
    eventLedger,
    requestLedger: router.records,
    cycles: router.cycles,
  };
  await persistEvidence(testInfo, name, payload, eventLedger, representative);
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
  if ((await controls.getAttribute('aria-expanded')) !== 'true') {
    await controls.click();
  }
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
  const ledgerJson = JSON.stringify(ledger, null, 2);
  await testInfo.attach(`event-continuity-${name}.json`, {
    body: json,
    contentType: 'application/json',
  });
  await writeOverviewArtifact(`event-continuity-${name}.json`, json);
  await writeOverviewArtifact(`event-ledger-${name}.json`, ledgerJson);
  if (representative) {
    await testInfo.attach(`raw-cadence-${name}-representative`, {
      body: representative,
      contentType: 'image/png',
    });
    await writeOverviewArtifact(
      `raw-cadence-${name}-representative.png`,
      representative
    );
  }
}
