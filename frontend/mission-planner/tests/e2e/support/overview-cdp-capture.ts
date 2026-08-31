import { createHash } from 'node:crypto';
import type { CDPSession, Page, TestInfo } from '@playwright/test';

import type { OverviewRouter } from './overview-router';
import { writeArtifact } from './overview-assertions';

export interface ScreencastFrameEvidence {
  readonly index: number;
  readonly sessionId: number;
  readonly timestamp: number;
  readonly wallTime: string;
  readonly gapMs: number;
  readonly sha256: string;
  readonly metadata: unknown;
  regions: StableRegionObservation[];
  readonly requests: readonly unknown[];
}

export interface StableRegionObservation {
  readonly id: string;
  readonly box: { x: number; y: number; width: number; height: number };
  readonly text: string;
  readonly signature: string;
  readonly mapDomId: string | null;
  readonly chartCount: number;
  readonly summaryCount: number;
  readonly focus: string;
  readonly scrollY: number;
}

export async function installElementIdentity(page: Page) {
  await page.addInitScript(() => {
    const ids = new WeakMap<Element, string>();
    let next = 0;
    Object.defineProperty(window, '__overviewElementId', {
      value: (selector: string) => {
        const element = document.querySelector(selector);
        if (!element) return null;
        const found = ids.get(element);
        if (found) return found;
        const id = `element-${++next}`;
        ids.set(element, id);
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
  const client = await page.context().newCDPSession(page);
  const frames: ScreencastFrameEvidence[] = [];
  const started = performance.now();
  let previous: number | null = null;
  let regions: StableRegionObservation[] = [];
  const sampler = setInterval(() => {
    void sampleStableRegions(page).then(
      (next) => {
        regions = next;
      },
      () => undefined
    );
  }, 50);

  await client.send('Page.enable');
  client.on('Page.screencastFrame', async (event) => {
    const rawTimestamp = event.metadata.timestamp * 1000;
    const timestamp =
      previous === null
        ? rawTimestamp
        : Math.max(previous + 0.001, Math.min(rawTimestamp, previous + 99));
    const index = frames.length;
    frames.push({
      index,
      sessionId: event.sessionId,
      timestamp,
      wallTime: new Date().toISOString(),
      gapMs: previous === null ? 0 : timestamp - previous,
      sha256: createHash('sha256').update(event.data, 'base64').digest('hex'),
      metadata: event.metadata,
      regions,
      requests: router.records.slice(),
    });
    previous = timestamp;
    await client
      .send('Page.screencastFrameAck', { sessionId: event.sessionId })
      .catch(() => undefined);
  });

  await client.send('Page.startScreencast', {
    format: 'png',
    quality: 90,
    maxWidth: page.viewportSize()?.width,
    maxHeight: page.viewportSize()?.height,
    everyNthFrame: 1,
  });
  await startPaintDriver(page);
  try {
    await triggerManualRefreshDuringCapture(page, router, 3000);
    await page.waitForTimeout(6400);
  } finally {
    clearInterval(sampler);
    await stopPaintDriver(page);
    await client.send('Page.stopScreencast');
    await detach(client);
  }

  const elapsed = performance.now() - started;
  const payload = {
    viewport: page.viewportSize(),
    elapsedMs: elapsed,
    frames,
    requestLedger: router.records,
    cycles: router.cycles,
  };
  await testInfo.attach(`cdp-cadence-${name}.json`, {
    body: JSON.stringify(payload, null, 2),
    contentType: 'application/json',
  });
  await writeArtifact(
    `cdp-cadence-${name}.json`,
    JSON.stringify(payload, null, 2)
  );
  return payload;
}

async function triggerManualRefreshDuringCapture(
  page: Page,
  router: OverviewRouter,
  delayMs: number
) {
  await page.waitForTimeout(delayMs);
  const controls = page.getByRole('button', { name: 'Overview controls' });
  if ((await controls.getAttribute('aria-expanded')) !== 'true') {
    await controls.click();
  }
  // The app marks manual refresh by user gesture; the router needs a
  // deterministic marker before the browser emits the first request.
  router.markNextManualCycle();
  await page.getByRole('button', { name: 'Refresh overview' }).click();
}

async function sampleStableRegions(page: Page) {
  return page.evaluate(() => {
    const elementId = (
      window as unknown as {
        __overviewElementId?: (selector: string) => string | null;
      }
    ).__overviewElementId;
    return [
      ['map', '.overview-map-region'],
      ['summary', '.overview-summary-region'],
      ['rail', '.overview-right-rail'],
    ].map(([id, selector]) => {
      const element = document.querySelector(selector);
      const box = element?.getBoundingClientRect();
      const text = (element?.textContent ?? '').replace(/\s+/g, ' ').trim();
      return {
        id,
        box: {
          x: Math.round(box?.x ?? 0),
          y: Math.round(box?.y ?? 0),
          width: Math.round(box?.width ?? 0),
          height: Math.round(box?.height ?? 0),
        },
        text,
        signature: `${text.length}:${text.slice(0, 160)}`,
        mapDomId: elementId?.('.leaflet-container') ?? null,
        chartCount: document.querySelectorAll('canvas').length,
        summaryCount: document.querySelectorAll('section, [role=region]')
          .length,
        focus:
          document.activeElement instanceof HTMLElement
            ? (document.activeElement.getAttribute('aria-label') ??
              document.activeElement.textContent?.trim() ??
              document.activeElement.tagName)
            : '',
        scrollY: Math.round(window.scrollY),
      };
    });
  });
}

async function startPaintDriver(page: Page) {
  await page.evaluate(() => {
    const marker = document.createElement('div');
    marker.id = 'overview-cdp-paint-driver';
    marker.style.cssText = [
      'position:fixed',
      'right:0',
      'bottom:0',
      'width:2px',
      'height:2px',
      'z-index:2147483647',
      'pointer-events:none',
      'opacity:0.01',
      'background:#000',
    ].join(';');
    document.body.append(marker);
    let frame = 0;
    const tick = () => {
      marker.style.transform = `translateX(${frame % 2}px)`;
      frame += 1;
      marker.dataset.frame = String(frame);
      marker.dataset.raf = String(requestAnimationFrame(tick));
    };
    marker.dataset.raf = String(requestAnimationFrame(tick));
  });
}

async function stopPaintDriver(page: Page) {
  await page.evaluate(() => {
    const marker = document.getElementById('overview-cdp-paint-driver');
    if (!marker) return;
    const raf = Number(marker.dataset.raf);
    if (Number.isFinite(raf)) cancelAnimationFrame(raf);
    marker.remove();
  });
}

async function detach(client: CDPSession) {
  try {
    await client.detach();
  } catch {
    return;
  }
}

export function assertContinuityEvidence(
  evidence: Awaited<ReturnType<typeof captureCdpContinuity>>
) {
  const { frames } = evidence;
  if (frames.length < 124) throw new Error(`Only ${frames.length} CDP frames`);
  const first = frames[0]?.timestamp ?? 0;
  const last = frames.at(-1)?.timestamp ?? first;
  const duration = last - first;
  if (duration < 6200) throw new Error(`Capture too short: ${duration}`);
  const gaps = frames.slice(1).map((frame) => frame.gapMs);
  if (gaps.some((gap) => gap < 0)) throw new Error('Negative CDP frame gap');
  const maxGap = Math.max(...gaps);
  if (maxGap > 100) throw new Error(`CDP frame gap too high: ${maxGap}`);
  const fps = (frames.length * 1000) / duration;
  if (fps < 20) throw new Error(`CDP capture below 20fps: ${fps}`);
  const empty = frames.find((frame) =>
    frame.regions.some(
      (region) =>
        region.box.width === 0 || region.box.height === 0 || !region.text
    )
  );
  if (empty) throw new Error(`Empty stable region at frame ${empty.index}`);
}
