#!/usr/bin/env node
/**
 * Neutral headed-browser card. Python owns descriptor-bound launch; this card
 * only attaches over CDP and owns the native window/screenshot assertions.
 */
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';

const [cdpUrl, evidenceRoot] = process.argv.slice(2);
if (!cdpUrl || !evidenceRoot) throw new Error('usage: platform-card.mjs <cdp-url> <evidence-root>');

let browser;
try {
  await mkdir(evidenceRoot, { recursive: true, mode: 0o700 });
  browser = await chromium.connectOverCDP(cdpUrl);
  const context = browser.contexts()[0];
  const page = context.pages()[0] ?? await context.newPage();
  const session = await context.newCDPSession(page);
  const target = await session.send('Browser.getWindowForTarget');
  const resized = await session.send('Browser.setContentsSize', {
    windowId: target.windowId, width: 1920, height: 1080,
  });
  const bounds = await session.send('Browser.getWindowBounds', { windowId: target.windowId });
  await page.goto('data:text/html,<title>platform-neutral</title>', { waitUntil: 'load' });
  const metrics = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    visualWidth: window.visualViewport?.width,
    visualHeight: window.visualViewport?.height,
    dpr: window.devicePixelRatio,
  }));
  const screenshot = await page.screenshot({ path: `${evidenceRoot}/neutral.png` });
  // PNG IHDR dimensions; decoded raster authority without image-tool substitution.
  const raster = [screenshot.readUInt32BE(16), screenshot.readUInt32BE(20)];
  if (metrics.innerWidth !== 1920 || metrics.innerHeight !== 1080 ||
      metrics.visualWidth !== 1920 || metrics.visualHeight !== 1080 ||
      metrics.dpr !== 1 || raster[0] !== 1920 || raster[1] !== 1080) {
    throw new Error(`neutral metrics mismatch: ${JSON.stringify({ metrics, raster })}`);
  }
  await writeFile(`${evidenceRoot}/metrics.json`, JSON.stringify({ target, resized, bounds, metrics, raster }), { mode: 0o600 });
  process.stdout.write(JSON.stringify({ metrics: { innerWidth: 1920, innerHeight: 1080, dpr: 1, raster } }));
} finally {
  // The Python descriptor-owner terminates Chrome/Xvfb in its single finally path.
  await browser?.close();
}
