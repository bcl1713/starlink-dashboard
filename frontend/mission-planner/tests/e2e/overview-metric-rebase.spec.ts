import { writeFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { mountMetricPanelFixture } from './support/metric-panel-fixture';

function recoveryHistory(end: number) {
  return {
    window_seconds: 60,
    start_timestamp_seconds: end - 60,
    end_timestamp_seconds: end,
    step_seconds: 1,
    series: {
      starlink_network_latency_ms_current: Array.from(
        { length: 61 },
        (_, i) => [end - 60 + i, 20 + (i % 10)]
      ),
    },
    rolling_5m: {
      starlink_network_latency_ms_current: {
        state: 'available',
        min: [],
        avg: [],
        max: [],
      },
    },
  };
}

for (const arrival of [
  'before visibility',
  'after visibility',
  'after freeze',
] as const) {
  test(`recovers painted history after twenty minutes asleep ${arrival}`, async ({
    page,
  }, info) => {
    await mountMetricPanelFixture(page);
    const render = (history: unknown) =>
      page.evaluate((history) => {
        (
          window as unknown as { renderPanel: (history: unknown) => void }
        ).renderPanel(history);
      }, history);
    const start = Math.floor(Date.now() / 1000);
    await render(recoveryHistory(start));
    const canvas = await page.locator('canvas').elementHandle();
    const visibility = (hidden: boolean) =>
      page.evaluate((hidden) => {
        Object.defineProperty(document, 'hidden', {
          configurable: true,
          value: hidden,
        });
        document.dispatchEvent(new Event('visibilitychange'));
      }, hidden);
    if (arrival === 'after freeze') {
      const session = await page.context().newCDPSession(page);
      try {
        await session.send('Page.setWebLifecycleState', { state: 'frozen' });
        await session.send('Page.setWebLifecycleState', { state: 'active' });
      } finally {
        await session.detach();
      }
    } else await visibility(true);
    await page.clock.setFixedTime(new Date((start + 1200) * 1000));
    if (arrival === 'after visibility') await visibility(false);
    await render(recoveryHistory(start + 1200));
    if (arrival === 'before visibility') await visibility(false);
    await page.waitForTimeout(100);
    const result = await page
      .locator('.overview-metric-history__viewport')
      .evaluate((viewport) => {
        const canvas = viewport.querySelector('canvas')!;
        const surface = viewport.firstElementChild!;
        const box = viewport.getBoundingClientRect();
        const raster = canvas.getBoundingClientRect();
        const { data, width, height } = canvas
          .getContext('2d')!
          .getImageData(0, 0, canvas.width, canvas.height);
        let painted = 0;
        for (let x = 0; x < width; x++) {
          const screenX = raster.left + (x / width) * raster.width;
          if (screenX < box.left || screenX > box.right) continue;
          for (let y = 0; y < height; y++)
            if (data[(y * width + x) * 4 + 3] > 100) painted++;
        }
        return {
          offset: new DOMMatrixReadOnly(getComputedStyle(surface).transform)
            .m41,
          budget: (box.width * 7.5) / 60,
          painted,
          left: raster.left,
          viewportLeft: box.left,
        };
      });
    expect(Math.abs(result.offset)).toBeLessThanOrEqual(result.budget + 1);
    expect(result.painted).toBeGreaterThan(100);
    expect(result.left).toBeLessThanOrEqual(result.viewportLeft + 1);
    expect(
      await canvas!.evaluate(
        (node) => node === document.querySelector('canvas')
      )
    ).toBe(true);
    await writeFile(
      info.outputPath('sleep-recovery.json'),
      JSON.stringify({ arrival, ...result }, null, 2)
    );
    await page.screenshot({ path: info.outputPath('sleep-recovery.png') });
  });
}

test('bounds repeated compositor corrections instead of drifting out of view', async ({
  page,
}, info) => {
  await mountMetricPanelFixture(page);
  const offsets = [];
  for (let i = 0; i < 20; i++) {
    const end = await page.evaluate(() => Math.floor(Date.now() / 1000));
    await page.evaluate((history) => {
      (
        window as unknown as { renderPanel: (history: unknown) => void }
      ).renderPanel(history);
      // Delay compositor startup while producer timestamps stay on real UTC.
      const blockedAt = performance.now();
      while (performance.now() - blockedAt < 350) {
        // Controlled main-thread stall, followed by a roughly one-second poll.
      }
    }, recoveryHistory(end));
    await page.waitForTimeout(100);
    const state = await page
      .locator('.overview-metric-history__surface')
      .evaluate((surface) => ({
        offset: new DOMMatrixReadOnly(getComputedStyle(surface).transform).m41,
        duration: parseFloat(getComputedStyle(surface).transitionDuration),
      }));
    offsets.push(state);
    expect(Math.abs(state.offset)).toBeLessThanOrEqual(51);
    expect(state.duration).toBeLessThanOrEqual(7.5);
    await page.waitForTimeout(550);
  }
  await writeFile(
    info.outputPath('bounded-corrections.json'),
    JSON.stringify(offsets, null, 2)
  );
});

test.describe('Overview retained-sample rebase', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });
  for (const deviceScaleFactor of [1, 1.5, 2]) {
    test.describe(`display scale ${deviceScaleFactor}`, () => {
      test.use({ deviceScaleFactor });
      test(`preserves a retained sample after delayed transition startup at scale ${deviceScaleFactor}`, async ({
        page,
      }, testInfo) => {
        await page.emulateMedia({ reducedMotion: 'no-preference' });
        await mountMetricPanelFixture(page);
        const result = await page.evaluate(async () => {
          const renderPanel = (
            window as unknown as { renderPanel: (history: unknown) => void }
          ).renderPanel;
          const start = Math.floor(Date.now() / 1000);
          const marker = start - 20;
          const history = (end: number) => ({
            window_seconds: 60,
            start_timestamp_seconds: end - 60,
            end_timestamp_seconds: end,
            step_seconds: 1,
            series: {
              starlink_network_latency_ms_current: [
                [marker - 5, 10],
                [marker, 90],
                [end, 10],
              ],
            },
            rolling_5m: {
              starlink_network_latency_ms_current: {
                state: 'available',
                min: [],
                avg: [],
                max: [],
              },
            },
          });
          const frame = () =>
            new Promise<void>((resolve) =>
              requestAnimationFrame(() => resolve())
            );
          renderPanel(history(start));
          await frame();
          await frame();
          renderPanel(history(start + 1));
          // Hold the main thread before the queued transition-start task can run.
          // This deliberately amplifies the clock/compositor mismatch from #234.
          const blockedAt = performance.now();
          while (performance.now() - blockedAt < 350) {
            // A controlled long task; do not turn this into an asynchronous wait.
          }
          await new Promise((resolve) => setTimeout(resolve, 600));
          await frame();
          const position = (end: number) => {
            const canvas = document.querySelector('canvas')!;
            const rect = canvas.getBoundingClientRect();
            const surface = document.querySelector(
              '.overview-metric-history__surface'
            )!;
            return {
              t: performance.now(),
              x: rect.left + ((marker - (end - 60 - 7.5)) / 75) * rect.width,
              transform: getComputedStyle(surface).transform,
            };
          };
          const before = position(start + 1);
          renderPanel(history(start + 2));
          // uPlot commits scales/raster in a microtask within the same frame.
          await new Promise<void>((resolve) => queueMicrotask(resolve));
          const after = position(start + 2);
          return {
            before,
            after,
            residual: after.x - before.x + ((after.t - before.t) * 400) / 60000,
          };
        });
        await writeFile(
          testInfo.outputPath('delayed-transition-rebase.json'),
          JSON.stringify(result, null, 2)
        );
        expect(Math.abs(result.residual)).toBeLessThanOrEqual(1);
      });
    });
  }
});
