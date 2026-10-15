import { expect, test } from '@playwright/test';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';
import {
  compositionFixture,
  desktopGeometry,
  expectDesktopFit,
} from './support/overview-composition';

test.use({ viewport: { width: 1920, height: 1080 }, video: 'on' });
let fixture: Awaited<ReturnType<typeof compositionFixture>>;

test.beforeEach(async ({ page }) => {
  fixture = await compositionFixture(page);
  const texture = page.waitForResponse(
    (r) => r.url().endsWith('/earth-day-hi.jpg') && r.ok()
  );
  await page.goto('/overview');
  await waitForGlobeVisualReady(page, texture);
  await expect(page.locator('[data-metric-panel] .uplot')).toHaveCount(5);
});

// Catches the old height threshold that makes ordinary 1080p scroll.
test('ordinary desktop fits every overlay', async ({ page }, testInfo) => {
  await testInfo.attach('baseline-geometry', {
    body: JSON.stringify(await desktopGeometry(page)),
    contentType: 'application/json',
  });
  await expect(page.locator('.operational-clock')).toHaveCount(4);
  await expect(
    page.getByRole('region', { name: 'Planned satellite' })
  ).toHaveCount(1);
  await expect(page.getByLabel('Globe legend')).toHaveCount(1);
  await expect(page.getByLabel('Departure and arrival')).toHaveCount(1);
  await expect(page.getByRole('table')).toHaveCount(0);
  await expect(
    page.getByText('Current network metrics', { exact: true })
  ).toHaveCount(0);
  await expect(page.locator('.overview-metric-history__latest')).toHaveText([
    '54 ms',
    '58.3 Mbps',
    '32 Mbps',
    '<0.01%',
    '31.24%',
  ]);
  await expectDesktopFit(page);
  await expect(
    page.getByRole('button', { name: 'Enter fullscreen overview' })
  ).toBeInViewport();
  await page.screenshot({ path: testInfo.outputPath('ordinary-desktop.png') });
});

test('stale network retains desktop fit', async ({ page }) => {
  fixture.stale = true;
  await page.reload();
  await expect(page.locator('.overview-metric-history__latest')).toHaveText(
    Array(5).fill('Unavailable')
  );
  await expect(page.getByLabel('Network history context')).toContainText(
    'Last observed'
  );
  await expectDesktopFit(page);
});

test('retained failed queries fit as observation age grows', async ({
  page,
}) => {
  await page.clock.install({ time: new Date() });
  fixture.errors = true;
  await page.clock.fastForward(120_000);
  await expect(page.getByLabel('Network history context')).toContainText(
    'History refresh unavailable',
    { timeout: 15_000 }
  );
  await expect(page.locator('.overview-metric-history__latest')).toHaveText(
    Array(5).fill('Unavailable')
  );
  await expectDesktopFit(page);
});

// Catches duplicate trees or renderer/plot remounts on native fullscreen change.
test('fullscreen round trip preserves scene and history', async ({
  page,
}, testInfo) => {
  const canvas = await page.locator('.overview-globe canvas').elementHandle();
  const plot = await page.locator('.uplot').first().elementHandle();
  await page.getByRole('button', { name: 'Enter fullscreen overview' }).click();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.fullscreenElement === document.documentElement
      )
    )
    .toBe(true);
  await expectDesktopFit(page);
  await expect(
    page.getByRole('navigation', { name: 'Primary navigation' })
  ).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Enter fullscreen overview' })
  ).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('native-fullscreen.png') });
  await page.evaluate(() => document.exitFullscreen());
  await expect(
    page.getByRole('navigation', { name: 'Primary navigation' })
  ).toBeVisible();
  await expectDesktopFit(page);
  expect(
    await canvas!.evaluate(
      (node) => node === document.querySelector('.overview-globe canvas')
    )
  ).toBe(true);
  expect(
    await plot!.evaluate((node) => node === document.querySelector('.uplot'))
  ).toBe(true);
  await page.getByRole('link', { name: 'Configuration', exact: true }).click();
  await expect(page.getByLabel('Overview history window')).toHaveValue('300');
  await page.getByLabel('Overview history window').selectOption('900');
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await expect(page.getByLabel('Network history context')).toContainText(
    'LAST 15 MIN'
  );
  await expectDesktopFit(page);
});

// Catches collisions at fit boundaries and controls lost in reachable flow.
test('text and viewport changes preserve one reachable tree', async ({
  page,
}) => {
  test.setTimeout(180_000);
  const canvas = await page.locator('.overview-globe canvas').elementHandle();
  const plot = await page.locator('.uplot').first().elementHandle();
  for (const rootSize of [8, 12, 16, 24]) {
    await page.evaluate((size) => {
      document.documentElement.style.fontSize = `${size}px`;
    }, rootSize);
    for (const viewport of [
      { width: 1920, height: 1080 },
      { width: 1920, height: 900 },
      { width: 1500, height: 1080 },
      { width: 1536, height: 1080 },
    ]) {
      await page.setViewportSize(viewport);
      for (const fullscreen of [false, true]) {
        if (fullscreen)
          await page
            .getByRole('button', { name: 'Enter fullscreen overview' })
            .click();
        await expect
          .poll(() =>
            page.evaluate(
              () => document.fullscreenElement === document.documentElement
            )
          )
          .toBe(fullscreen);
        const fixed = rootSize <= 16 && viewport.height === 1080;
        if (fixed) await expectDesktopFit(page, viewport.width === 1920);
        else {
          await expect(page.locator('.overview-page')).toHaveAttribute(
            'data-layout',
            'stacked'
          );
          expect((await desktopGeometry(page)).fits).toBe(true);
          await page
            .locator('[data-metric-panel]')
            .last()
            .scrollIntoViewIfNeeded();
          await expect(
            page.locator('[data-metric-panel]').last()
          ).toBeInViewport();
          await page
            .getByLabel('Departure and arrival')
            .scrollIntoViewIfNeeded();
          await expect(
            page.getByLabel('Departure and arrival')
          ).toBeInViewport();
        }
        expect((await desktopGeometry(page)).horizontalOverflow).toBe(false);
        if (fullscreen) {
          await page.evaluate(() => document.exitFullscreen());
          await expect
            .poll(() =>
              page.evaluate(() => document.fullscreenElement === null)
            )
            .toBe(true);
        }
        await expect(
          page.getByRole('button', { name: 'Enter fullscreen overview' })
        ).toHaveCount(1);
      }
    }
  }
  await page.evaluate(() => {
    document.documentElement.style.fontSize = '16px';
  });
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 844, height: 390 },
    { width: 360, height: 800 },
  ]) {
    await page.setViewportSize(viewport);
    await page.locator('[data-metric-panel]').last().scrollIntoViewIfNeeded();
    await expect(page.locator('[data-metric-panel]').last()).toBeInViewport();
    await page
      .getByRole('button', { name: 'Enter fullscreen overview' })
      .scrollIntoViewIfNeeded();
    await expect(
      page.getByRole('button', { name: 'Enter fullscreen overview' })
    ).toBeInViewport();
    expect((await desktopGeometry(page)).horizontalOverflow).toBe(false);
  }
  expect(
    await canvas!.evaluate(
      (node) => node === document.querySelector('.overview-globe canvas')
    )
  ).toBe(true);
  expect(
    await plot!.evaluate((node) => node === document.querySelector('.uplot'))
  ).toBe(true);
});
