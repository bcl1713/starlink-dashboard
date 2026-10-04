import { writeFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { mountMetricPanelFixture } from './support/metric-panel-fixture';

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
