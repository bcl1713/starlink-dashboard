import { expect, test } from '@playwright/test';
import { installOverviewRoutes } from './overview-fixtures';

function overlaps(
  left: { x: number; y: number; width: number; height: number },
  right: { x: number; y: number; width: number; height: number }
) {
  return !(
    left.x + left.width <= right.x ||
    right.x + right.width <= left.x ||
    left.y + left.height <= right.y ||
    right.y + right.height <= left.y
  );
}

test.describe('Operations overview display', () => {
  test('1920x1080 fullscreen keeps the complete readable inventory in one screen', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    const statusCount = await installOverviewRoutes(page);
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    await page.goto('/overview');
    await expect(
      page.getByText('Waypoint 5 with safe operational label')
    ).toBeVisible();
    await expect(page.getByText('27.0 ms', { exact: true })).toBeVisible();
    await expect(
      page.getByText('21.0 / 27.0 / 33.0 ms', { exact: true })
    ).toBeVisible();
    await expect(
      page.getByText('Average 0.5% · Max 0.8%', { exact: true })
    ).toBeVisible();
    const mapBeforeEntry = await page
      .locator('.current-position-map')
      .elementHandle();
    await page.getByLabel('Refresh cadence').selectOption('paused');
    const root = page.getByTestId('overview-root');
    const rootHandle = await root.elementHandle();

    await page.getByRole('button', { name: 'Enter fullscreen' }).click();
    await expect
      .poll(() => page.evaluate(() => document.fullscreenElement?.tagName))
      .toBe('MAIN');
    expect(
      await page.evaluate(
        (element) => document.fullscreenElement === element,
        rootHandle
      )
    ).toBe(true);
    await expect(root).toBeFocused();
    expect(
      await page.evaluate(
        (map) => document.querySelector('.current-position-map') === map,
        mapBeforeEntry
      )
    ).toBe(true);
    expect(
      await page
        .getByLabel('Refresh cadence')
        .locator('option')
        .allTextContents()
    ).toEqual([
      '1 second',
      '2 second',
      '5 second',
      '10 second',
      '30 second',
      'Paused',
    ]);

    const inventoryNames = [
      'clock-utc',
      'clock-local',
      'clock-takeoff',
      'clock-landing',
      'current-position-map',
      'top-applicable-pois',
      'latency',
      'download',
      'upload',
      'ground-entry-point',
      'obstruction',
      'packet-loss',
      'selected-interval',
      'last-update',
    ];
    const inventory = [
      ...Array.from({ length: 4 }, (_, index) =>
        root.locator('[data-clock]').nth(index)
      ),
      root.getByRole('heading', { name: 'Current position map' }).locator('..'),
      root.getByRole('heading', { name: 'Top applicable POIs' }).locator('..'),
      root.getByRole('heading', { name: 'Latency' }).locator('..'),
      root.getByText('Download 142.0 Mbps', { exact: true }),
      root.getByText('Upload 18.0 Mbps', { exact: true }),
      root.getByRole('heading', { name: 'Ground entry point' }).locator('..'),
      root.getByRole('heading', { name: 'Obstruction' }).locator('..'),
      root.getByRole('heading', { name: 'Packet loss' }).locator('..'),
      root.getByText('Selected interval: Paused', { exact: true }),
      root.getByText(/Updated|stale/, { exact: false }).last(),
    ];
    const boxes = [];
    for (const region of inventory) {
      await expect(region).toBeVisible();
      const box = await region.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.width).toBeGreaterThan(0);
      expect(box!.height).toBeGreaterThan(0);
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.y).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(1920);
      expect(box!.y + box!.height).toBeLessThanOrEqual(1080);
      const fontSize = await region.evaluate((element) =>
        Number.parseFloat(getComputedStyle(element).fontSize)
      );
      expect(fontSize).toBeGreaterThanOrEqual(12);
      boxes.push(box!);
    }

    const cardBoxes = await root
      .locator('.overview-card')
      .evaluateAll((cards) =>
        cards.map((card) => {
          const box = card.getBoundingClientRect();
          return {
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            clippedHorizontally: card.scrollWidth > card.clientWidth,
            clippedVertically: card.scrollHeight > card.clientHeight,
          };
        })
      );
    expect(cardBoxes.every((card) => !card.clippedHorizontally)).toBe(true);
    expect(cardBoxes.every((card) => !card.clippedVertically)).toBe(true);
    for (let left = 0; left < cardBoxes.length; left += 1) {
      for (let right = left + 1; right < cardBoxes.length; right += 1) {
        expect(overlaps(cardBoxes[left], cardBoxes[right])).toBe(false);
      }
    }

    const dimensions = await root.evaluate((element) => {
      const box = element.getBoundingClientRect();
      const mapBox = element
        .querySelector('.overview-map')!
        .getBoundingClientRect();
      return {
        viewport: { width: innerWidth, height: innerHeight },
        rootBox: {
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
        },
        mapBox: { width: mapBox.width, height: mapBox.height },
        root: {
          clientWidth: element.clientWidth,
          clientHeight: element.clientHeight,
          scrollWidth: element.scrollWidth,
          scrollHeight: element.scrollHeight,
        },
        document: {
          clientWidth: document.documentElement.clientWidth,
          clientHeight: document.documentElement.clientHeight,
          scrollWidth: document.documentElement.scrollWidth,
          scrollHeight: document.documentElement.scrollHeight,
        },
      };
    });
    expect(dimensions.viewport).toEqual({ width: 1920, height: 1080 });
    expect(dimensions.rootBox).toEqual({
      x: 0,
      y: 0,
      width: 1920,
      height: 1080,
    });
    expect(dimensions.mapBox.width).toBeGreaterThanOrEqual(960);
    expect(dimensions.mapBox.height).toBeGreaterThanOrEqual(500);
    expect(dimensions.root.scrollWidth).toBeLessThanOrEqual(
      dimensions.root.clientWidth
    );
    expect(dimensions.root.scrollHeight).toBeLessThanOrEqual(
      dimensions.root.clientHeight
    );
    expect(dimensions.document.scrollWidth).toBeLessThanOrEqual(
      dimensions.document.clientWidth
    );
    expect(dimensions.document.scrollHeight).toBeLessThanOrEqual(
      dimensions.document.clientHeight
    );
    process.stdout.write(
      `OVERVIEW_GEOMETRY ${JSON.stringify({
        dimensions,
        inventory: boxes.map((box, index) => ({
          name: inventoryNames[index],
          ...box,
        })),
      })}\n`
    );
    if (process.env.OVERVIEW_SCREENSHOT) {
      await page.screenshot({
        path: process.env.OVERVIEW_SCREENSHOT,
        fullPage: false,
      });
    }
    expect(boxes).toHaveLength(14);
    expect(await root.locator('[data-clock]').count()).toBe(4);
    expect(await root.getByRole('listitem').count()).toBe(5);
    const beforeManual = statusCount();
    await page.getByRole('button', { name: 'Refresh live status' }).click();
    await expect.poll(statusCount).toBe(beforeManual + 1);
    await page.waitForTimeout(500);
    expect(statusCount()).toBe(beforeManual + 1);
    expect(consoleErrors).toEqual([]);

    await page.getByRole('button', { name: 'Exit fullscreen' }).click();
    await expect
      .poll(() => page.evaluate(() => document.fullscreenElement))
      .toBeNull();
    await expect(
      page.getByRole('button', { name: 'Enter fullscreen' })
    ).toBeFocused();
    await expect(page.getByLabel('Refresh cadence')).toHaveValue('paused');
  });

  test('fullscreen rejection leaves the overview usable with a visible fallback', async ({
    page,
  }) => {
    await installOverviewRoutes(page);
    await page.addInitScript(() => {
      Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
        configurable: true,
        value: () => Promise.reject(new Error('denied by browser policy')),
      });
    });
    await page.goto('/overview');
    await page.getByRole('button', { name: 'Enter fullscreen' }).click();

    await expect(page.getByRole('status')).toContainText(
      'Fullscreen was unavailable'
    );
    await expect(page.getByLabel('Refresh cadence')).toHaveValue('1');
    await expect(
      page.getByRole('button', { name: 'Refresh live status' })
    ).toBeVisible();
    expect(await page.evaluate(() => document.fullscreenElement)).toBeNull();
  });

  test('normal desktop and narrow layouts keep controls reachable without horizontal overflow', async ({
    page,
  }) => {
    await installOverviewRoutes(page);
    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto('/overview');
      await expect(
        page.getByRole('button', { name: 'Enter fullscreen' })
      ).toBeVisible();
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth
      );
      expect(overflow).toBeLessThanOrEqual(0);
    }
  });
});
