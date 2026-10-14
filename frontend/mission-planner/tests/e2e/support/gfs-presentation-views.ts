import { installWeatherProbe } from './overview-weather-probe';
import { windSnapshot } from './gfs-wind-probe';
import { expect, type Page } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
export async function captureGfsViews(
  page: Page,
  label: string,
  outputPath: (name: string) => string
) {
  const sizes = [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
  ];
  for (const size of sizes) {
    console.log(`Capture ${label} ${size.width}x${size.height}`);
    await page.setViewportSize(size);
    await page.bringToFront();
    await expect.poll(() => page.evaluate(() => innerWidth)).toBe(size.width);
    await expect(page.locator('.overview-page')).toHaveAttribute(
      'data-layout',
      size.width === 390 ? 'stacked' : 'desktop'
    );
    const legend = page.getByLabel('Atmosphere legend');
    if (!(await legend.isVisible()))
      await page.getByRole('button', { name: 'Legend', exact: true }).click();
    await expect(legend).toBeVisible();
    const labels = async () => {
      const rects = await legend
        .locator('.gfs-wind-legend__labels span')
        .evaluateAll((nodes) =>
          nodes.map((n) => {
            const r = n.getBoundingClientRect();
            return { left: r.left, right: r.right };
          })
        );
      rects
        .slice(1)
        .forEach((r, i) =>
          expect(r.left).toBeGreaterThanOrEqual(rects[i].right)
        );
    };
    await labels();
    const screenshotSession = await page.context().newCDPSession(page);
    try {
      const { data } = await screenshotSession.send('Page.captureScreenshot', {
        format: 'png',
        fromSurface: true,
        captureBeyondViewport: false,
      });
      await writeFile(
        outputPath(`${label}-${size.width}.png`),
        Buffer.from(data, 'base64')
      );
    } finally {
      await screenshotSession.detach();
    }
    if (size.width === 1920) {
      // A fresh page avoids headless Chrome retaining its previous fullscreen
      // surface across repeated entries; it reads the same saved settings.
      const mode = (await windSnapshot(page))?.mode;
      if (!mode) throw Error('No admitted mode for fullscreen capture');
      const viewURL = page.url();
      await page
        .getByRole('link', { name: 'Configuration', exact: true })
        .click();
      await expect(page.locator('.overview-globe canvas')).toHaveCount(0);
      const fullscreen = await page.context().newPage();
      const errors: string[] = [],
        providers: string[] = [];
      fullscreen.on('pageerror', (error) => errors.push(error.message));
      fullscreen.on('request', (request) => {
        if (
          /noaa-gfs|aviationweather\.gov|rainviewer\.com/.test(
            new URL(request.url()).hostname
          )
        )
          providers.push(request.url());
      });
      try {
        await fullscreen.setViewportSize(size);
        const reduced = await page.evaluate(
          () => matchMedia('(prefers-reduced-motion: reduce)').matches
        );
        await fullscreen.emulateMedia({
          reducedMotion: reduced ? 'reduce' : 'no-preference',
        });
        await installWeatherProbe(fullscreen);
        await fullscreen.bringToFront();
        await fullscreen.goto(viewURL);
        await expect(fullscreen.getByLabel('Atmosphere legend')).toContainText(
          mode === 'winds' ? 'Wind speed' : 'Temperature',
          { timeout: 180000 }
        );
        await fullscreen.bringToFront();
        await fullscreen
          .getByRole('button', { name: 'Enter fullscreen overview' })
          .click();
        await expect
          .poll(() => fullscreen.evaluate(() => !!document.fullscreenElement))
          .toBe(true);
        await expect
          .poll(() => fullscreen.evaluate(() => [innerWidth, innerHeight]))
          .toEqual([1920, 1080]);
        const rects = await fullscreen
          .getByLabel('Atmosphere legend')
          .locator('.gfs-wind-legend__labels span')
          .evaluateAll((nodes) =>
            nodes.map((n) => {
              const r = n.getBoundingClientRect();
              return { left: r.left, right: r.right };
            })
          );
        rects
          .slice(1)
          .forEach((r, i) =>
            expect(r.left).toBeGreaterThanOrEqual(rects[i].right)
          );
        const cdp = await fullscreen.context().newCDPSession(fullscreen);
        try {
          const { data } = await cdp.send('Page.captureScreenshot', {
            format: 'png',
            fromSurface: true,
            captureBeyondViewport: false,
          });
          await writeFile(
            outputPath(`${label}-fullscreen.png`),
            Buffer.from(data, 'base64')
          );
        } finally {
          await cdp.detach();
        }
        expect(errors).toEqual([]);
        expect(providers).toEqual([]);
      } finally {
        await fullscreen.close();
        await page.bringToFront();
        await page.getByRole('link', { name: 'Overview', exact: true }).click();
        await expect
          .poll(async () => (await windSnapshot(page))?.mode, {
            timeout: 60000,
          })
          .toBe(mode);
      }
    }
  }
}
