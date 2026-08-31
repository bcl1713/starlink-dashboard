import { expect, test, type Page, type TestInfo } from '@playwright/test';

import {
  attachScreenshots,
  expectNoGrafana,
  openOverview,
  writeArtifact,
} from './support/overview-assertions';
import {
  installOverviewRouter,
  type OverviewRouter,
} from './support/overview-router';

const continuityViewports = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'mobile', width: 390, height: 844 },
] as const;

test.describe('Operations overview temporal continuity', () => {
  test.afterEach(async ({ page }) => {
    await page.close();
  });

  for (const viewport of continuityViewports) {
    test(`keeps stable regions alive across scheduled and manual refreshes at ${viewport.name}`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize(viewport);
      const errors: string[] = [];
      page.on('console', (message) => {
        if (message.type() === 'error') errors.push(message.text());
      });
      page.on('pageerror', (error) => errors.push(error.message));
      const router = await installOverviewRouter(page);
      await openOverview(page);
      await settleInitialRequests(router);

      const before = await sampleState(page);
      const frames = await captureCadence(page, testInfo, viewport.name);
      await page.getByRole('button', { name: 'Overview controls' }).click();
      await page.getByLabel('POI category').selectOption('waypoint');
      await page.getByRole('button', { name: 'Refresh overview' }).click();
      await expect.poll(() => router.cycles.length).toBeGreaterThan(12);
      const after = await sampleState(page);

      expect(frames.length).toBeGreaterThanOrEqual(100);
      expect(averageFps(frames)).toBeGreaterThanOrEqual(20);
      expect(
        Math.max(...frames.map((frame) => frame.gapMs))
      ).toBeLessThanOrEqual(100);
      expect(after.boxes.every((box) => box.width > 0 && box.height > 0)).toBe(
        true
      );
      expect(after.mapNode).toBe(before.mapNode);
      expect(after.chartCount).toBeGreaterThanOrEqual(before.chartCount);
      expect(after.panelCount).toBeGreaterThanOrEqual(before.panelCount);
      expect(
        errors.filter((error) => !error.includes('message: canceled'))
      ).toEqual([]);
      await expectNoGrafana(router.records);
      await attachScreenshots(page, testInfo, `continuity-${viewport.name}`);
    });
  }

  for (const scenario of [
    'overview-no-route',
    'overview-sparse',
    'overview-backend-failure',
    'overview-stale',
    'overview-idl',
    'overview-threshold-crossing',
    'overview-radar-failure',
    'overview-recovery',
  ] as const) {
    test(`renders truthful localized state for ${scenario}`, async ({
      page,
    }) => {
      const router = await installOverviewRouter(page, scenario);
      await openOverview(page);
      await settleInitialRequests(router);

      const visibleText = await page.locator('main').innerText();
      expect(visibleText).not.toMatch(/stack|traceback|exception|axios/i);
      expect(
        router.records.filter((record) => record.event === 'failed')
      ).toEqual([]);
    });
  }

  test('preserves controls across mobile rotation', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installOverviewRouter(page);
    await openOverview(page);
    await page.getByRole('button', { name: 'Overview controls' }).click();
    await page.getByLabel('POI category').selectOption('alternate');
    await openLayerDisclosure(page);
    await page.getByLabel('Weather Radar').focus();
    await page.keyboard.press('Space');

    await page.setViewportSize({ width: 844, height: 390 });
    await expect(page.getByLabel('POI category')).toHaveValue('alternate');
    await expect(page.getByLabel('Weather Radar')).not.toBeChecked();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByLabel('POI category')).toHaveValue('alternate');
    await expect(page.getByLabel('Weather Radar')).not.toBeChecked();
  });
});

async function settleInitialRequests(router: OverviewRouter) {
  await expect.poll(() => firstPartyCompleteCount(router)).toBeGreaterThan(6);
}

async function captureCadence(page: Page, testInfo: TestInfo, name: string) {
  const frames = await page.evaluate(
    () =>
      new Promise<{ timestamp: number; gapMs: number; fps: number }[]>(
        (resolve) => {
          const started = performance.now();
          const frames: { timestamp: number; gapMs: number; fps: number }[] =
            [];
          let previous = started;
          const capture = (timestamp: number) => {
            const gapMs = timestamp - previous;
            frames.push({ timestamp, gapMs, fps: 1000 / Math.max(1, gapMs) });
            previous = timestamp;
            if (timestamp - started >= 5200) resolve(frames);
            else requestAnimationFrame(capture);
          };
          requestAnimationFrame(capture);
        }
      )
  );
  await page.screenshot({ fullPage: false });
  await testInfo.attach(`cadence-${name}.json`, {
    body: JSON.stringify({ frames }, null, 2),
    contentType: 'application/json',
  });
  await writeArtifact(
    `cadence-${name}.json`,
    JSON.stringify({ frames }, null, 2)
  );
  return frames;
}

function firstPartyCompleteCount(router: OverviewRouter): number {
  return router.records.filter(
    (record) => record.firstParty && record.event === 'complete'
  ).length;
}

function averageFps(
  frames: readonly { timestamp: number; gapMs: number; fps: number }[]
): number {
  const elapsed = frames.at(-1)?.timestamp ?? 0;
  const started = frames.at(0)?.timestamp ?? 0;
  return (frames.length * 1000) / Math.max(1, elapsed - started);
}

async function openLayerDisclosure(page: Page) {
  await page.locator('details.operational-map__panel').evaluate((details) => {
    if (details instanceof HTMLDetailsElement) details.open = true;
  });
}

async function sampleState(page: Page) {
  return page.evaluate(() => {
    const boxes = [
      '.overview-map-region',
      '.overview-summary-region',
      '.overview-right-rail',
    ].map((selector) => {
      const box = document.querySelector(selector)?.getBoundingClientRect();
      return { width: box?.width ?? 0, height: box?.height ?? 0 };
    });
    return {
      boxes,
      chartCount: document.querySelectorAll('canvas, svg').length,
      mapNode: document
        .querySelector('.leaflet-container')
        ?.getAttribute('class'),
      panelCount: document.querySelectorAll('section').length,
    };
  });
}
