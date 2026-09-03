import { expect } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface OverviewGeometryOptions {
  poiNames?: readonly string[];
  selectedInterval?: string | RegExp;
  freshness?: RegExp;
}

export const overviewInventoryNames = [
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
] as const;

const overlaps = (left: Box, right: Box) =>
  !(
    left.x + left.width <= right.x ||
    right.x + right.width <= left.x ||
    left.y + left.height <= right.y ||
    right.y + right.height <= left.y
  );

async function assertReadableInViewport(locator: Locator) {
  await expect(locator).toBeVisible();
  const measurement = await locator.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return {
      box: { x: box.x, y: box.y, width: box.width, height: box.height },
      fontSize: Number.parseFloat(getComputedStyle(element).fontSize),
    };
  });
  expect(measurement.box.width).toBeGreaterThan(0);
  expect(measurement.box.height).toBeGreaterThan(0);
  expect(measurement.box.x).toBeGreaterThanOrEqual(0);
  expect(measurement.box.y).toBeGreaterThanOrEqual(0);
  expect(measurement.box.x + measurement.box.width).toBeLessThanOrEqual(1920);
  expect(measurement.box.y + measurement.box.height).toBeLessThanOrEqual(1080);
  expect(measurement.fontSize).toBeGreaterThanOrEqual(12);
  return measurement.box;
}

export async function enterOverviewFullscreen(page: Page) {
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
  return root;
}

export async function measureOverviewGeometry(
  page: Page,
  options: OverviewGeometryOptions = {}
) {
  const {
    poiNames = [],
    selectedInterval = /Selected interval:/,
    freshness = /Updated|stale|failure|No successful/,
  } = options;
  const root = page.getByTestId('overview-root');
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
    root.getByText(selectedInterval, {
      exact: typeof selectedInterval === 'string',
    }),
    root.getByText(freshness, { exact: false }).last(),
  ];
  const inventoryBoxes = [];
  for (const region of inventory) {
    inventoryBoxes.push(await assertReadableInViewport(region));
  }
  const poiBoxes = [];
  for (const name of poiNames) {
    expect(name).toHaveLength(200);
    poiBoxes.push(
      await assertReadableInViewport(root.getByText(name, { exact: true }))
    );
  }
  for (let left = 0; left < poiBoxes.length; left += 1) {
    for (let right = left + 1; right < poiBoxes.length; right += 1) {
      expect(overlaps(poiBoxes[left], poiBoxes[right])).toBe(false);
    }
  }
  for (const control of await root.locator('button, select').all()) {
    await assertReadableInViewport(control);
  }

  const cards = await root.locator('.overview-card').evaluateAll((elements) =>
    elements.map((element) => {
      const box = element.getBoundingClientRect();
      return {
        label: element.querySelector('h2')?.textContent ?? 'clock',
        x: box.x,
        y: box.y,
        width: box.width,
        height: box.height,
        clippedHorizontally: element.scrollWidth > element.clientWidth,
        clippedVertically: element.scrollHeight > element.clientHeight,
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
      };
    })
  );
  expect(cards.filter((card) => card.clippedHorizontally)).toEqual([]);
  expect(cards.filter((card) => card.clippedVertically)).toEqual([]);
  for (let left = 0; left < cards.length; left += 1) {
    for (let right = left + 1; right < cards.length; right += 1) {
      expect(overlaps(cards[left], cards[right])).toBe(false);
    }
  }

  const dimensions = await root.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const mapBox = element
      .querySelector('.overview-map')!
      .getBoundingClientRect();
    return {
      viewport: { width: innerWidth, height: innerHeight },
      rootBox: { x: box.x, y: box.y, width: box.width, height: box.height },
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
  expect(dimensions.rootBox).toEqual({ x: 0, y: 0, width: 1920, height: 1080 });
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
  expect(await root.locator('details').count()).toBe(0);
  expect(inventoryBoxes).toHaveLength(14);
  expect(await root.locator('[data-clock]').count()).toBe(4);
  expect(await root.getByRole('listitem').count()).toBe(5);
  return { dimensions, cards, inventory: inventoryBoxes };
}

export async function measureOverviewFrame(page: Page) {
  const root = page.getByTestId('overview-root');
  const regions = [
    ...Array.from({ length: 4 }, (_, index) =>
      root.locator('[data-clock]').nth(index)
    ),
    ...[
      'Current position map',
      'Top applicable POIs',
      'Latency',
      'Throughput',
      'Ground entry point',
      'Obstruction',
      'Packet loss',
      'Refresh',
    ].map((name) => root.getByRole('heading', { name }).locator('..')),
  ];
  const boxes = [];
  for (const region of regions) {
    boxes.push(await assertReadableInViewport(region));
  }
  const dimensions = await root.evaluate((element) => {
    const rootBox = element.getBoundingClientRect();
    const mapBox = element
      .querySelector('.overview-map')!
      .getBoundingClientRect();
    const cards = [
      ...element.querySelectorAll<HTMLElement>('.overview-card'),
    ].map((card) => ({
      label: card.querySelector('h2')?.textContent ?? 'clock',
      clientWidth: card.clientWidth,
      clientHeight: card.clientHeight,
      scrollWidth: card.scrollWidth,
      scrollHeight: card.scrollHeight,
    }));
    return {
      rootBox: {
        x: rootBox.x,
        y: rootBox.y,
        width: rootBox.width,
        height: rootBox.height,
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
      cards,
    };
  });
  expect(dimensions.rootBox).toEqual({ x: 0, y: 0, width: 1920, height: 1080 });
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
  expect(
    dimensions.cards.filter(
      (card) =>
        card.scrollWidth > card.clientWidth ||
        card.scrollHeight > card.clientHeight
    )
  ).toEqual([]);
  expect(boxes).toHaveLength(12);
  return dimensions;
}
