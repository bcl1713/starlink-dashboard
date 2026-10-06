import { expect, test, type Page } from '@playwright/test';
import { installAdsbFixture, freshContact } from './support/adsb-fixture';
import { adsbSettings } from '../../src/test/adsb-fixtures';
import {
  observeOverviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';

// 27-02 Leg 1 archive coordinates: Exit precedes Enter on the westbound route.
const points = [
  { latitude: 38.810795, longitude: -76.867386 },
  { latitude: 47.05615630363365, longitude: -117.0571439064211 },
  { latitude: 47.15588629729729, longitude: -118.31891558108107 },
  { latitude: 61.251354, longitude: -149.80652 },
];

async function labelGeometry(page: Page) {
  return page.evaluate(() => {
    const visible = (node: HTMLElement) =>
      node.offsetWidth > 0 && getComputedStyle(node).visibility === 'visible';
    const roots = [
      ...document.querySelectorAll<HTMLElement>('[data-overview-label-id]'),
    ];
    const labels = roots.flatMap((root) => {
      const source = root.querySelector<HTMLElement>('[data-label-source]')!;
      if (!visible(source)) return [];
      const anchor = root.getBoundingClientRect(),
        box = source.getBoundingClientRect();
      const leader =
        root.querySelector('[data-label-leader]')?.getAttribute('d') ?? '';
      const coords =
        leader.match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/gi)?.map(Number) ?? [];
      return [
        {
          id: root.dataset.overviewLabelId!,
          kind: root.dataset.labelKind,
          anchor: { x: anchor.x, y: anchor.y },
          box: box.toJSON(),
          leader: coords,
        },
      ];
    });
    const panels = [
      ...document.querySelectorAll<HTMLElement>(
        '.overview-planned-satellite,.overview-arrival,.globe-legend,.overview-fullscreen-control,.overview-map-status,.overview-map-controls,.overview-top-overlays,.overview-metrics-overlays'
      ),
    ]
      .filter(visible)
      .map((node) => node.getBoundingClientRect().toJSON());
    return { labels, panels };
  });
}

test.beforeEach(async ({ context, page }) => {
  const traffic = await installAdsbFixture(context);
  traffic.setContacts([
    freshContact({ latitude: 45, longitude: -108, callsign: 'RCH123' }),
  ]);
  traffic.setSettings(adsbSettings({ include_hexes: ['00AB12'] }));
  await context.route('**/api/routes', (route) =>
    route.fulfill({
      json: {
        routes: [
          {
            id: 'label-leg-1',
            name: '27-02 Leg 1',
            is_active: true,
            point_count: points.length,
          },
        ],
        total: 1,
      },
    })
  );
  await context.route('**/api/routes/label-leg-1', (route) =>
    route.fulfill({ json: { id: 'label-leg-1', points } })
  );
  await context.route('**/api/overview/upcoming-pois', (route) =>
    route.fulfill({
      json: {
        state: 'available',
        calculated_at: new Date().toISOString(),
        flight_phase: 'pre_departure',
        scheduled_departure_time: null,
        current_route_progress: 0,
        position_observed_at: null,
        position_state: 'unavailable',
        pois: points.map((point, index) => ({
          poi_id: ['departure', 'commka-exit', 'commka-enter', 'arrival'][
            index
          ],
          name: ['KADW', 'CommKa\nExit', 'CommKa\nEnter', 'PAED'][index],
          kind: [
            'departure',
            'ka_coverage_exit',
            'ka_coverage_entry',
            'arrival',
          ][index],
          ...point,
          projected_route_progress: [0, 54.0603, 55.5912, 100][index],
          flight_phase: 'pre_departure',
          expected_arrival_time: null,
          eta_seconds: null,
          estimated_arrival_time: null,
          eta_type: null,
          upcoming: true,
          map_retained: true,
        })),
      },
    })
  );
  await observeOverviewCamera(page);
});

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 704, height: 900 },
]) {
  test(`keeps 27-02 callouts attached and visible label layers clear at ${viewport.width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize(viewport);
    await page.goto('/overview');
    await settledOverviewCamera(page);
    await expect(page.locator('[data-poi-label="commka-enter"]')).toBeVisible();
    await expect(page.locator('[data-poi-label="commka-exit"]')).toBeVisible();
    await expect
      .poll(async () => (await labelGeometry(page)).labels.length)
      .toBeGreaterThanOrEqual(6);
    const { labels, panels } = await labelGeometry(page);
    const enter = labels.find((label) => label.id === 'poi:commka-enter')!;
    const exit = labels.find((label) => label.id === 'poi:commka-exit')!;
    const order = exit.anchor.x - enter.anchor.x;
    expect(
      order *
        (exit.box.x + exit.box.width / 2 - (enter.box.x + enter.box.width / 2))
    ).toBeGreaterThanOrEqual(0);
    const overlaps = (
      a: { x: number; y: number; width: number; height: number },
      b: typeof a
    ) =>
      a.x < b.x + b.width &&
      a.x + a.width > b.x &&
      a.y < b.y + b.height &&
      a.y + a.height > b.y;
    for (const [index, label] of labels.entries()) {
      expect(label.leader).toHaveLength(4);
      const end = {
        x: label.anchor.x + label.leader[2],
        y: label.anchor.y + label.leader[3],
      };
      expect(end.x).toBeGreaterThanOrEqual(label.box.x - 1);
      expect(end.x).toBeLessThanOrEqual(label.box.right + 1);
      expect(end.y).toBeGreaterThanOrEqual(label.box.y - 1);
      expect(end.y).toBeLessThanOrEqual(label.box.bottom + 1);
      expect(
        Math.min(
          Math.abs(end.x - label.box.x),
          Math.abs(end.x - label.box.right),
          Math.abs(end.y - label.box.y),
          Math.abs(end.y - label.box.bottom)
        )
      ).toBeLessThan(1.5);
      for (const other of labels.slice(index + 1))
        expect(overlaps(label.box, other.box)).toBe(false);
      for (const panel of panels)
        expect(overlaps(label.box, panel)).toBe(false);
    }
    expect(new Set(labels.map((label) => label.kind))).toEqual(
      new Set(['poi', 'adsb', 'gep'])
    );
    await page.screenshot({
      path: info.outputPath(`27-02-callouts-${viewport.width}.png`),
    });
    if (viewport.width === 1920) {
      const before = await page
        .locator('[data-poi-label="commka-enter"]')
        .getAttribute('data-poi-label-offset');
      await page.waitForTimeout(1200);
      expect(
        await page
          .locator('[data-poi-label="commka-enter"]')
          .getAttribute('data-poi-label-offset')
      ).toBe(before);
      await page
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
      await settledOverviewCamera(page);
      await expect(
        page.locator('[data-poi-label="commka-enter"]')
      ).toBeVisible();
      await page.screenshot({
        path: info.outputPath('27-02-callouts-fullscreen.png'),
      });
    }
  });
}

test('deconflicts configured GEO labels when their anchors come into view', async ({
  page,
  context,
}, info) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await context.route('**/api/satellites', (route) =>
    route.fulfill({
      json: [
        {
          satellite_id: 'GEO-visible',
          transport: 'X',
          longitude: 60,
          slot: null,
          color: '#FF6B6B',
        },
      ],
    })
  );
  await page.goto('/overview');
  await settledOverviewCamera(page);
  await expect(
    page.locator(
      '[data-overview-label-id="satellite:GEO-visible"] [data-label-source]'
    )
  ).not.toBeVisible();
  await page.evaluate(async () => {
    const state = window.__overviewEvidenceRoots
      ?.find(
        (root) =>
          root.containerInfo?.getState &&
          document.contains(root.containerInfo.getState().gl.domElement)
      )
      ?.containerInfo?.getState?.();
    const controls = state?.controls as unknown as {
      dollyTo: (distance: number, transition: boolean) => Promise<void>;
    };
    await controls.dollyTo(28, false);
  });
  await settledOverviewCamera(page);
  await expect(
    page.locator(
      '[data-overview-label-id="satellite:GEO-visible"] [data-label-source]'
    )
  ).toBeVisible();
  const { labels, panels } = await labelGeometry(page);
  const satellite = labels.find((label) => label.kind === 'satellite')!;
  expect(satellite.leader).toHaveLength(4);
  for (const panel of panels)
    expect(
      satellite.box.x >= panel.right ||
        satellite.box.right <= panel.x ||
        satellite.box.y >= panel.bottom ||
        satellite.box.bottom <= panel.y
    ).toBe(true);
  await page.screenshot({
    path: info.outputPath('configured-geo-callout.png'),
  });
});

test('keeps a crowded local disclosure on screen and moves other labels clear of its open list', async ({
  page,
  context,
}, info) => {
  await page.setViewportSize({ width: 704, height: 900 });
  await context.route('**/api/overview/upcoming-pois', (route) =>
    route.fulfill({
      json: {
        state: 'available',
        calculated_at: new Date().toISOString(),
        flight_phase: 'pre_departure',
        scheduled_departure_time: null,
        current_route_progress: 0,
        position_observed_at: null,
        position_state: 'unavailable',
        pois: Array.from({ length: 40 }, (_, i) => ({
          poi_id: `crowded-${i}`,
          name: `Crowded CommKa boundary ${i}`,
          kind: 'ka_coverage_entry',
          ...points[1],
          projected_route_progress: 54,
          flight_phase: 'pre_departure',
          expected_arrival_time: null,
          eta_seconds: null,
          estimated_arrival_time: null,
          eta_type: null,
          upcoming: true,
          map_retained: true,
        })),
      },
    })
  );
  const workers: string[] = [];
  page.on('worker', (worker) => workers.push(worker.url()));
  await page.goto('/overview');
  await settledOverviewCamera(page);
  const summary = page.locator('.overview-label-group:visible summary').first();
  await expect(summary).toBeVisible();
  await summary.focus();
  await page.keyboard.press('Enter');
  const list = page.locator('.overview-label-group[open] ul');
  await expect(list).toBeVisible();
  expect(await list.locator('li').count()).toBeGreaterThan(1);
  const names = await page.evaluate(() => {
    const roots = [
      ...document.querySelectorAll<HTMLElement>('[data-label-kind="poi"]'),
    ];
    return roots.flatMap((root) => {
      const source = root.querySelector<HTMLElement>('[data-label-source]')!;
      const group = root.querySelector<HTMLDetailsElement>('details')!;
      return [
        ...(getComputedStyle(source).visibility === 'visible'
          ? [source.textContent]
          : []),
        ...(group.style.display === 'block'
          ? [...group.querySelectorAll('li')].map((item) => item.textContent)
          : []),
      ];
    });
  });
  expect(new Set(names).size).toBe(40);
  await expect
    .poll(async () => {
      const popup = await list.boundingBox();
      if (!popup) return false;
      const { labels } = await labelGeometry(page);
      return labels.every(
        ({ box }) =>
          box.x >= popup.x + popup.width ||
          box.right <= popup.x ||
          box.y >= popup.y + popup.height ||
          box.bottom <= popup.y
      );
    })
    .toBe(true);
  const popup = await list.boundingBox();
  const canvas = await page.locator('.overview-map-stage canvas').boundingBox();
  expect(popup!.x).toBeGreaterThanOrEqual(canvas!.x);
  expect(popup!.y).toBeGreaterThanOrEqual(canvas!.y);
  expect(popup!.x + popup!.width).toBeLessThanOrEqual(
    canvas!.x + canvas!.width
  );
  expect(popup!.y + popup!.height).toBeLessThanOrEqual(
    canvas!.y + canvas!.height
  );
  expect(
    workers.some((url) => url.includes('overview-label-layout.worker'))
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath('crowded-label-disclosure.png'),
  });
  await page.keyboard.press('Escape');
  await expect(list).not.toBeVisible();
  await expect(summary).toBeFocused();
});
