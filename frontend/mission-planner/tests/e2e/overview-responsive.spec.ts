import { expect, test } from '@playwright/test';
import {
  compositionFixture,
  expectDesktopFit,
} from './support/overview-composition';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

// Catches fixed-background fallback, duplicate trees and incorrect scroll owners.
test.use({ video: 'on' });
for (const [width, height, columns] of [
  [390, 844, 2],
  [360, 800, 1],
]) {
  test(`portrait ${width} uses page flow and reaches five charts`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height });
    await compositionFixture(page);
    const texture = page.waitForResponse(
      (r) => r.url().endsWith('/earth-day-hi.jpg') && r.ok()
    );
    await page.goto('/overview');
    await expect(page.locator('.overview-page')).toHaveAttribute(
      'data-layout',
      'stacked'
    );
    // The responsive frame intentionally places Earth beside the planning card.
    // Check the center of that measured clear area, rather than the canvas center.
    const point = await page.evaluate(() => {
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
    await waitForGlobeVisualReady(page, texture, point);
    await info.attach('geometry', {
      body: JSON.stringify(
        await page.evaluate(() => ({
          viewport: [innerWidth, innerHeight],
          overview: document
            .querySelector('.overview-page')
            ?.getBoundingClientRect()
            .toJSON(),
          root: getComputedStyle(document.documentElement).fontSize,
          layout: document
            .querySelector('.overview-page')
            ?.getAttribute('data-layout'),
        }))
      ),
      contentType: 'application/json',
    });
    await expect(page.locator('.overview-page')).toHaveAttribute(
      'data-layout',
      'stacked'
    );
    await expect(page.locator('.overview-globe')).toHaveCSS(
      'position',
      'absolute'
    );
    await expect(page.locator('[data-metric-panel] .uplot')).toHaveCount(5);
    expect(
      await page
        .locator('.overview-metric-history-panels')
        .evaluate(
          (el) => getComputedStyle(el).gridTemplateColumns.split(' ').length
        )
    ).toBe(columns);
    for (const card of await page.locator('[data-metric-panel]').all()) {
      await card.scrollIntoViewIfNeeded();
      await expect(card).toBeInViewport();
    }
    expect(
      await page.evaluate(() => ({
        outer:
          document.querySelector('.app-route-content')!.scrollHeight >
          document.querySelector('.app-route-content')!.clientHeight,
        rail: getComputedStyle(
          document.querySelector('.overview-metrics-overlays')!
        ).overflowY,
        horizontal: document.documentElement.scrollWidth > innerWidth,
      }))
    ).toEqual({ outer: true, rail: 'visible', horizontal: false });
    await page.screenshot({
      path: info.outputPath('portrait.png'),
      fullPage: true,
    });
  });
}
test('landscape keeps stage visible while rail scrolls', async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 844, height: 390 });
  await compositionFixture(page);
  await page.goto('/overview');
  await expect(page.locator('[data-metric-panel] .uplot')).toHaveCount(5);
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'landscape'
  );
  const stage = await page.locator('.overview-map-stage').boundingBox();
  const rail = await page.locator('.overview-metrics-overlays').boundingBox();
  expect(stage!.width).toBeGreaterThanOrEqual(560);
  expect(stage!.height).toBeGreaterThanOrEqual(220);
  expect(rail!.width).toBeGreaterThanOrEqual(210);
  expect(rail!.width).toBeLessThanOrEqual(240);
  for (const card of await page.locator('[data-metric-panel]').all()) {
    await card.scrollIntoViewIfNeeded();
    await expect(card).toBeInViewport();
  }
  expect((await page.locator('.overview-map-stage').boundingBox())!.y).toBe(
    stage!.y
  );
  const overlap = await page.evaluate(() => {
    const boxes = [
      ...document.querySelectorAll(
        '.overview-planned-satellite,.overview-arrival,.globe-legend,.overview-fullscreen-control'
      ),
    ].map((el) => el.getBoundingClientRect());
    return boxes.some((a, i) =>
      boxes
        .slice(i + 1)
        .some(
          (b) =>
            a.left < b.right - 1 &&
            a.right > b.left + 1 &&
            a.top < b.bottom - 1 &&
            a.bottom > b.top + 1
        )
    );
  });
  expect(overlap).toBe(false);
  expect(
    await page
      .locator('.app-route-content')
      .evaluate((el) => el.scrollHeight > el.clientHeight + 1)
  ).toBe(false);
  await page.screenshot({ path: info.outputPath('landscape.png') });
});
test('scaled desktop chooses measured readable layout and preserves nodes', async ({
  page,
}) => {
  await page.setViewportSize({ width: 2000, height: 1333 });
  await compositionFixture(page);
  await page.goto('/overview');
  await expect(page.locator('[data-metric-panel] .uplot')).toHaveCount(5);
  const globe = await page.locator('.overview-globe canvas').elementHandle();
  const plots = await page.locator('.uplot').elementHandles();
  await expectDesktopFit(page);
  await page.evaluate(() => (document.documentElement.style.fontSize = '24px'));
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'stacked'
  );
  expect(
    (await page.locator('.overview-metrics-overlays').boundingBox())!.width
  ).toBeLessThanOrEqual(1200);
  await page.locator('[data-metric-panel]').last().scrollIntoViewIfNeeded();
  await expect(page.locator('[data-metric-panel]').last()).toBeInViewport();
  expect(
    await globe!.evaluate(
      (node) => node === document.querySelector('.overview-globe canvas')
    )
  ).toBe(true);
  for (let i = 0; i < 5; i++)
    expect(
      await plots[i].evaluate(
        (node, index) => node === document.querySelectorAll('.uplot')[index],
        i
      )
    ).toBe(true);
});

// Catches overflow escape that clips truthful content or oscillates after resize.
for (const variant of [
  'long',
  'stale',
  'errors',
  'destination',
  'departure',
  'no-route',
]) {
  test(`responsive ${variant} content remains reachable through rotation`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const fixture = await compositionFixture(page);
    if (variant === 'long') {
      fixture.nextName = 'Next '.repeat(24);
      fixture.destination = 'Destination '.repeat(12);
      fixture.satellite = 'S'.repeat(128);
    }
    if (variant === 'stale') fixture.stale = true;
    if (variant === 'errors') fixture.errors = true;
    if (variant === 'destination') fixture.arrival = 'destination';
    if (variant === 'departure') fixture.arrival = 'departure';
    if (variant === 'no-route') fixture.route = false;
    await page.goto('/overview');
    if (variant === 'errors')
      await expect(
        page.getByText('Operational clocks unavailable')
      ).toBeVisible();
    else await expect(page.locator('.uplot')).toHaveCount(5);
    for (const viewport of [
      { width: 390, height: 844 },
      { width: 844, height: 390 },
      { width: 360, height: 800 },
    ]) {
      await page.setViewportSize(viewport);
      for (const selector of [
        '.overview-arrival',
        '.overview-planned-satellite',
        '.globe-legend',
        '.overview-fullscreen-control',
        '[data-metric-panel]',
      ]) {
        for (const panel of await page.locator(selector).all()) {
          await panel.scrollIntoViewIfNeeded();
          await expect(panel).toBeInViewport();
          expect(
            await panel.evaluate(
              (el) =>
                el.scrollWidth <= el.clientWidth + 1 &&
                el.scrollHeight <= el.clientHeight + 1
            )
          ).toBe(true);
        }
      }
      expect(
        await page
          .locator('.overview-page')
          .evaluate((el) => el.scrollWidth <= el.clientWidth + 1)
      ).toBe(true);
    }
    if (variant === 'long') {
      await expect(page.getByLabel('Departure and arrival')).toContainText(
        fixture.nextName.trim()
      );
      await expect(page.getByLabel('Planned satellite')).toContainText(
        fixture.satellite!
      );
    }
    if (variant === 'stale')
      await expect(page.locator('.overview-metric-history__latest')).toHaveText(
        Array(5).fill('Unavailable')
      );
    if (variant === 'departure')
      await expect(page.getByLabel('Departure and arrival')).toContainText(
        'AGO'
      );
  });
}
test('landscape rotation, enlarged text and legend use a stable reachable tree', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await compositionFixture(page);
  await page.goto('/overview');
  await expect(page.locator('.uplot')).toHaveCount(5);
  const canvas = await page.locator('.overview-globe canvas').elementHandle();
  await page.setViewportSize({ width: 844, height: 390 });
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'landscape'
  );
  const toggle = page.getByRole('button', { name: 'Legend', exact: true });
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'stacked'
  );
  await page.keyboard.press('Escape');
  await expect(toggle).toBeFocused();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await page.evaluate(() => (document.documentElement.style.fontSize = '24px'));
  await page.locator('[data-metric-panel]').last().scrollIntoViewIfNeeded();
  await expect(page.locator('[data-metric-panel]').last()).toBeInViewport();
  expect(
    await canvas!.evaluate(
      (node) => node === document.querySelector('.overview-globe canvas')
    )
  ).toBe(true);
});
