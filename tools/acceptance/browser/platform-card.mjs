#!/usr/bin/env node
/** Platform card: attaches only after Python owns readiness and lifecycle. */
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(
  resolve(ROOT, 'frontend/mission-planner/package.json'),
);
const { chromium } = require('@playwright/test');

const [cdpUrl] = process.argv.slice(2);
if (!cdpUrl) throw new Error('usage: platform-card.mjs <cdp-url>');
let browser;
try {
  browser = await chromium.connectOverCDP(cdpUrl);
  const context = browser.contexts()[0];
  const page = context.pages()[0] ?? await context.newPage();
  const session = await context.newCDPSession(page);
  const target = await session.send('Browser.getWindowForTarget');
  const resized = await session.send('Browser.setContentsSize', { windowId: target.windowId, width: 1920, height: 1080 });
  const bounds = await session.send('Browser.getWindowBounds', { windowId: target.windowId });
  if (!target.windowId || resized === undefined || !bounds?.bounds) throw new Error('native window resize did not return a window result');
  await page.goto('data:text/html,<title>platform-neutral</title>', { waitUntil: 'load' });
  const metrics = await page.evaluate(() => ({
    innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    visualWidth: window.visualViewport?.width, visualHeight: window.visualViewport?.height,
    dpr: window.devicePixelRatio,
  }));
  const screenshot = await page.screenshot();
  const raster = await page.evaluate(async (encoded) => {
    const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
    const image = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
    const result = [image.width, image.height]; image.close(); return result;
  }, screenshot.toString('base64'));
  const cardMetrics = { ...metrics, raster, nativeResize: true };
  if (metrics.innerWidth !== 1920 || metrics.innerHeight !== 1080 || metrics.visualWidth !== 1920 || metrics.visualHeight !== 1080 || metrics.dpr !== 1 || raster[0] !== 1920 || raster[1] !== 1080) throw new Error(`neutral metrics mismatch: ${JSON.stringify(cardMetrics)}`);
  const artifacts = { 'neutral.png': screenshot.toString('base64'), 'metrics.json': Buffer.from(JSON.stringify({ target, resized, bounds, metrics: cardMetrics })).toString('base64') };
  process.stdout.write(JSON.stringify({ browserVersion: await browser.version(), metrics: cardMetrics, artifacts }));
} finally {
  await browser?.close();
}
