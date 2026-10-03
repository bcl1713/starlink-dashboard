import { writeFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { compositionFixture } from './support/overview-composition';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

for (const height of [1080, 900, 768, 640]) {
  test.describe(`Overview 1920x${height}`, () => {
    test.use({
      viewport: { width: 1920, height },
      screen: { width: 1920, height },
    });

    test('keeps metrics, legend and arrival separate in ordinary and native fullscreen views', async ({
      page,
      browser,
    }, info) => {
      await compositionFixture(page);
      const texture = page.waitForResponse(
        (response) =>
          response.url().endsWith('/earth-day-hi.jpg') && response.ok()
      );
      await page.goto('/overview');
      await expect(page.locator('[data-metric-panel] .uplot')).toHaveCount(5);
      await expect(page.getByLabel('Departure and arrival')).toContainText(
        'RKSO'
      );
      // Responsive camera framing shifts Earth into the clear area beside the
      // planning card. Sampling the canvas center can instead hit dark space.
      const samplePoint = await page.evaluate(() => {
        if (
          document
            .querySelector('.overview-page')!
            .getAttribute('data-layout') === 'desktop'
        )
          return { x: 0.5, y: 0.5 };
        const globe = document
          .querySelector('.overview-globe')!
          .getBoundingClientRect();
        const planning = document
          .querySelector('.overview-satellite-overlays')!
          .getBoundingClientRect();
        const arrival = document
          .querySelector('.overview-arrival')!
          .getBoundingClientRect();
        return {
          x: (12 + (globe.width - planning.width - 36) / 2) / globe.width,
          y: (12 + (globe.height - arrival.height - 24) / 2) / globe.height,
        };
      });
      await waitForGlobeVisualReady(page, texture, samplePoint);

      for (const mode of ['ordinary', 'fullscreen']) {
        if (mode === 'fullscreen') {
          await page.getByRole('button', { name: /fullscreen/i }).click();
          await expect
            .poll(() => page.evaluate(() => !!document.fullscreenElement))
            .toBe(true);
        }

        const geometry = () =>
          page.evaluate(() => {
            const panels = [
              ...document.querySelectorAll<HTMLElement>(
                '[aria-label="Network history context"], [aria-label="Globe legend"], [aria-label="Departure and arrival"], [data-metric-panel]'
              ),
            ];
            const boxes = panels.map((panel) => ({
              name: panel.getAttribute('aria-label'),
              ...panel.getBoundingClientRect().toJSON(),
            }));
            return {
              viewport: { width: innerWidth, height: innerHeight },
              layout: document
                .querySelector('.overview-page')!
                .getAttribute('data-layout'),
              boxes,
              plotWidths: [
                ...document.querySelectorAll('[data-metric-panel]'),
              ].map((panel) => panel.getBoundingClientRect().width),
              overlaps: boxes.flatMap((a, index) =>
                boxes
                  .slice(index + 1)
                  .filter(
                    (b) =>
                      a.left < b.right &&
                      b.left < a.right &&
                      a.top < b.bottom &&
                      b.top < a.bottom
                  )
                  .map((b) => [a.name, b.name])
              ),
              clipped: panels
                .filter(
                  (panel) =>
                    panel.scrollWidth > panel.clientWidth + 1 ||
                    panel.scrollHeight > panel.clientHeight + 1
                )
                .map((panel) => panel.getAttribute('aria-label')),
              horizontalOverflow:
                document.documentElement.scrollWidth > innerWidth,
            };
          });
        await expect.poll(async () => (await geometry()).overlaps).toEqual([]);
        const measured = await geometry();
        expect(measured.viewport).toEqual({ width: 1920, height });
        expect(measured.boxes).toHaveLength(8);
        expect(measured.clipped).toEqual([]);
        expect(measured.horizontalOverflow).toBe(false);
        expect(measured.plotWidths.every((width) => width >= 170)).toBe(true);
        for (const box of measured.boxes) {
          expect(box.width).toBeGreaterThan(0);
          expect(box.height).toBeGreaterThan(0);
        }
        for (const panel of await page
          .locator(
            '[data-metric-panel], [aria-label="Departure and arrival"], [aria-label="Globe legend"], [aria-label="Network history context"]'
          )
          .all()) {
          await panel.scrollIntoViewIfNeeded();
          await expect(panel).toBeInViewport();
        }
        await page
          .getByLabel('Network history context')
          .scrollIntoViewIfNeeded();
        await writeFile(
          info.outputPath(`${mode}-geometry.json`),
          JSON.stringify({ browser: browser.version(), ...measured }, null, 2)
        );
        await page.screenshot({ path: info.outputPath(`${mode}.png`) });
      }
    });
  });
}
