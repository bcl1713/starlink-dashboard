import { expect, test } from '@playwright/test';
import {
  compositionFixture,
  expectDesktopFit,
} from './support/overview-composition';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

test.use({ viewport: { width: 1920, height: 1080 }, video: 'on' });
let fixture: Awaited<ReturnType<typeof compositionFixture>>;
test.beforeEach(async ({ page }) => {
  fixture = await compositionFixture(page);
  const texture = page.waitForResponse(
    (r) => r.url().endsWith('/earth-day-hi.jpg') && r.ok()
  );
  await page.goto('/overview');
  await waitForGlobeVisualReady(page, texture);
  await expect(page.locator('.uplot')).toHaveCount(5);
});

// Catches planning identifiers consuming the fullscreen/legend slots.
test('long content remains readable', async ({ page }, testInfo) => {
  fixture.satellite = 'X'.repeat(128);
  fixture.nextName = 'Atlantic handoff '.repeat(8).slice(0, 120);
  fixture.destination = 'Destination airport '.repeat(6).slice(0, 120);
  await page.reload();
  const card = page.getByRole('region', { name: 'Planned satellite' });
  const arrival = page.getByLabel('Departure and arrival');
  await expect(card).toContainText(fixture.satellite);
  await expect(arrival).toContainText(fixture.nextName);
  await expect(arrival).toContainText(fixture.destination);
  await expect(arrival.locator('time')).toHaveCount(2);
  for (const fullscreen of [false, true]) {
    if (fullscreen) {
      await page
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
      await expect
        .poll(() => page.evaluate(() => !!document.fullscreenElement))
        .toBe(true);
    }
    await expectDesktopFit(page);
    await page.screenshot({
      path: testInfo.outputPath(
        `long-${fullscreen ? 'fullscreen' : 'ordinary'}.png`
      ),
    });
  }
});

// Catches unreadable fixed-state wrapping and exceptions hidden by layout.
test('exceptions retain desktop fit', async ({ page }, testInfo) => {
  fixture.route = false;
  fixture.satellite = null;
  fixture.stale = true;
  await page.reload();
  await expect(page.getByLabel('Map status')).toContainText('No active route.');
  await expect(page.getByLabel('Globe legend')).toContainText('Aircraft');
  await expect(page.getByLabel('Globe legend')).toContainText(
    'Ground entry point'
  );
  await expect(
    page.getByRole('region', { name: 'Planned satellite' })
  ).toContainText('NO SATELLITE SELECTED');
  await expectDesktopFit(page);
  fixture.errors = true;
  const card = page.getByRole('region', { name: 'Planned satellite' });
  await expect(card).toContainText('UNAVAILABLE', { timeout: 20_000 });
  await expect(page.getByLabel('Network history context')).toContainText(
    'History refresh unavailable',
    { timeout: 20_000 }
  );
  await expectDesktopFit(page);
  const lines = await card.locator('strong').evaluate((node) => {
    const range = document.createRange();
    range.selectNodeContents(node);
    return range.getClientRects().length;
  });
  expect(lines).toBe(1);
  await page.screenshot({
    path: testInfo.outputPath('all-refresh-errors.png'),
  });
});

test('destination only and late departure retain fit', async ({ page }) => {
  fixture.arrival = 'destination';
  await page.reload();
  const arrival = page.getByLabel('Departure and arrival');
  await expect(arrival.locator('section')).toHaveCount(1);
  await expect(arrival.getByRole('heading')).toContainText('LANDING');
  await expectDesktopFit(page);
  fixture.arrival = 'departure';
  await page.reload();
  await expect(arrival.getByRole('heading')).toContainText(
    'SCHEDULED DEPARTURE'
  );
  await expect(arrival.locator('.overview-arrival__countdown')).toHaveText(
    '12 MIN AGO'
  );
  await expectDesktopFit(page);
});

test('clock query failures remain readable', async ({ page }) => {
  fixture.errors = true;
  await page.reload();
  const message = page.getByText('Operational clocks unavailable');
  await expect(message).toBeVisible();
  await expect(message).toHaveCSS('color', 'rgb(248, 250, 252)');
  await expectDesktopFit(page);
});

// Conservative contrast bound: glass composited over a fully white backdrop.
test('secondary labels remain readable over bright terrain', async ({
  page,
}) => {
  const contrast = await page
    .locator(
      '.operational-clock__label, .overview-metric-history__value-axis, .overview-metric-history-panels__age, .globe-legend__items li'
    )
    .evaluateAll((nodes) => {
      const luminance = (rgb: number[]) => {
        const linear = rgb.map((value) => {
          const channel = value / 255;
          return channel <= 0.04045
            ? channel / 12.92
            : ((channel + 0.055) / 1.055) ** 2.4;
        });
        return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
      };
      return nodes.map((node) => {
        const panel = node.closest(
          '.operational-clock, .overview-metric-history, .overview-metric-history-panels__header, .globe-legend'
        )!;
        const parse = (value: string) => value.match(/[\d.]+/g)!.map(Number);
        const foreground = parse(getComputedStyle(node).color);
        const background = parse(getComputedStyle(panel).backgroundColor);
        const alpha = background[3] ?? 1;
        const composite = background
          .slice(0, 3)
          .map((value) => value * alpha + 255 * (1 - alpha));
        const values = [luminance(foreground), luminance(composite)];
        return (Math.max(...values) + 0.05) / (Math.min(...values) + 0.05);
      });
    });
  expect(contrast.length).toBeGreaterThan(4);
  expect(Math.min(...contrast)).toBeGreaterThanOrEqual(4.5);
});

test('backdrop fallback preserves contrast and geometry', async ({
  page,
}, testInfo) => {
  test.setTimeout(120_000); // Two scene loads and four full-size software captures.
  // Natural solar calculation at midnight UTC illuminates the Asia-facing pose.
  const solarTime = new Date();
  solarTime.setUTCHours(0, 0, 0, 0);
  fixture.now = solarTime.getTime();
  await page.clock.setFixedTime(solarTime);
  const texture = page.waitForResponse(
    (r) => r.url().endsWith('/earth-day-hi.jpg') && r.ok()
  );
  await page.reload();
  await waitForGlobeVisualReady(page, texture);
  await page.getByRole('button', { name: 'Enter fullscreen overview' }).click();
  await expect
    .poll(() => page.evaluate(() => !!document.fullscreenElement))
    .toBe(true);
  await expectDesktopFit(page);
  await page.mouse.move(1020, 520);
  // Exercise the shipped wheel listener without 38 software compositor waits.
  await page.locator('.overview-globe canvas').evaluate((canvas) => {
    for (let i = 0; i < 38; i++)
      canvas.dispatchEvent(
        new WheelEvent('wheel', {
          deltaY: -120,
          bubbles: true,
          cancelable: true,
        })
      );
  });
  await page.waitForTimeout(600); // Settle the shipped OrbitControls damping.
  await page.mouse.down();
  await page.mouse.move(1640, 550);
  await page.mouse.up();
  await page.waitForTimeout(600);
  await page.screenshot({ path: testInfo.outputPath('terrain-with-blur.png') });
  const blurRules = await page.evaluate(() =>
    [...document.styleSheets].flatMap((sheet, sheetIndex) =>
      [...sheet.cssRules].flatMap((rule, index) => {
        if (
          !(rule instanceof CSSSupportsRule) ||
          !rule.cssText.includes('--overview-glass')
        )
          return [];
        const cssText = rule.cssText;
        sheet.deleteRule(index);
        return [{ sheetIndex, index, cssText }];
      })
    )
  );
  expect(blurRules).toHaveLength(1);
  const panels = page.locator(
    '.overview-metric-history, .operational-clock, .overview-planned-satellite, .globe-legend, .overview-arrival'
  );
  for (const panel of await panels.all()) {
    await expect(panel).toHaveCSS('background-color', 'rgba(7, 18, 30, 0.9)');
    await expect(panel).toHaveCSS('backdrop-filter', 'none');
  }
  expect(
    await page
      .locator(
        '.overview-metric-history__latest, .operational-clock__time, .uplot canvas'
      )
      .evaluateAll((nodes) =>
        nodes.every((node) => getComputedStyle(node).filter === 'none')
      )
  ).toBe(true);
  await expectDesktopFit(page);
  await page.screenshot({
    path: testInfo.outputPath('terrain-opaque-fallback.png'),
  });
  await page.mouse.move(1020, 520);
  await page.mouse.down();
  await page.mouse.move(490, 520);
  await page.mouse.up();
  await page.waitForTimeout(600);
  await page.screenshot({
    path: testInfo.outputPath('ocean-opaque-fallback.png'),
  });
  await page.evaluate(
    (rules) =>
      rules.forEach(({ sheetIndex, index, cssText }) =>
        document.styleSheets[sheetIndex].insertRule(cssText, index)
      ),
    blurRules
  );
  await expectDesktopFit(page);
  await page.screenshot({ path: testInfo.outputPath('ocean-with-blur.png') });
});
