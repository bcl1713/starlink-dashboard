import { expect, test, type Page } from '@playwright/test';

test.use({ viewport: { width: 1920, height: 1080 }, video: 'on' });
const metrics = [
  'starlink_network_latency_ms_current',
  'starlink_network_throughput_down_mbps_current',
  'starlink_network_throughput_up_mbps_current',
  'starlink_network_packet_loss_percent',
  'starlink_dish_obstruction_percent',
];

// Fullscreen events precede React's shell update and container-query layout.
// Wait for the requested viewport, shell height, and distinguishing rail mode.
async function waitForLayout(
  page: Page,
  viewport: { width: number; height: number },
  fullscreen: boolean,
  fixed: boolean
) {
  await expect
    .poll(() =>
      page.evaluate(() => {
        const overview = document.querySelector('.overview-page')!;
        const rail = document.querySelector('.overview-bottom-overlays')!;
        const navigation = document.querySelector(
          'nav[aria-label="Primary navigation"]'
        );
        const container = overview.getBoundingClientRect();
        const navigationHeight =
          navigation?.getBoundingClientRect().height ?? 0;
        return {
          fullscreen: document.fullscreenElement === document.documentElement,
          navigation: !!navigation,
          width: innerWidth,
          height: innerHeight,
          containerWidth: Math.round(container.width),
          containerFillsShell:
            Math.abs(container.height + navigationHeight - innerHeight) <= 1,
          position: getComputedStyle(rail).position,
          railWidth:
            getComputedStyle(rail).position === 'absolute'
              ? Math.round(rail.getBoundingClientRect().width)
              : null,
        };
      })
    )
    .toEqual({
      fullscreen,
      navigation: !fullscreen,
      width: viewport.width,
      height: viewport.height,
      containerWidth: viewport.width,
      containerFillsShell: true,
      position: fixed ? 'absolute' : 'relative',
      railWidth: fixed ? 440 : null,
    });
}

test('keeps five readable glass cards separate from POIs through missing-data states', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000); // State coverage plus ordinary/fullscreen font-size matrix.
  let stale = false;
  let failedHistory = false;
  let emptyPois = false;
  for (const [endpoint, json] of [
    ['routes', { routes: [], total: 0 }],
    ['satellites', []],
    ['active-x-link', { satellite_id: null }],
    ['overview-history/settings', { window_seconds: 300 }],
    [
      'overview-clocks/settings',
      {
        clocks: Array.from({ length: 4 }, (_, i) => ({
          label: [
            'Zulu / UTC',
            'Washington, DC',
            'Andrews AFB',
            'La Jolla, CA',
          ][i],
          time_zone: 'UTC',
        })),
      },
    ],
  ] as const)
    await page.route(`**/api/${endpoint}`, (route) => route.fulfill({ json }));
  await page.route('**/api/status', (route) =>
    route.fulfill({
      json: {
        timestamp: new Date(Date.now() - (stale ? 25_000 : 0)).toISOString(),
        metric_availability: {
          latency_ms: true,
          throughput_down_mbps: true,
          throughput_up_mbps: true,
          packet_loss_percent: true,
          obstruction_percent: true,
        },
        network: {
          latency_ms: 54.347,
          throughput_down_mbps: 58.347,
          throughput_up_mbps: 32,
          packet_loss_percent: 0.004,
        },
        obstruction: { obstruction_percent: 31.236 },
      },
    })
  );
  await page.route('**/api/overview/upcoming-pois', (route) =>
    route.fulfill({
      json: {
        state: emptyPois ? 'no_active_mission' : 'available',
        calculated_at: new Date().toISOString(),
        pois: emptyPois
          ? []
          : Array.from({ length: 5 }, (_, i) => ({
              poi_id: `poi-${i}`,
              name: `Waypoint ${i}`,
              kind: 'x_band_transition',
              latitude: 35 + i,
              longitude: -100 + i,
              expected_arrival_time: new Date(
                Date.now() + 600_000
              ).toISOString(),
              eta_seconds: 600,
              estimated_arrival_time: new Date(
                Date.now() + 600_000
              ).toISOString(),
              eta_type: 'estimated',
              upcoming: true,
              map_retained: true,
            })),
      },
    })
  );
  await page.route('**/api/overview-history', (route) => {
    if (failedHistory)
      return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    const end = Math.floor(Date.now() / 1000);
    const series = (offset: number) =>
      Array.from({ length: 61 }, (_, i) => [
        end - 300 + i * 5,
        20 + (i % 13) + offset,
      ]);
    return route.fulfill({
      json: {
        window_seconds: 300,
        start_timestamp_seconds: end - 300,
        end_timestamp_seconds: end,
        step_seconds: 5,
        series: Object.fromEntries(
          metrics.map((metric) => [metric, series(0)])
        ),
        rolling_5m: Object.fromEntries(
          metrics.map((metric) => [
            metric,
            {
              state: 'available',
              min: series(-4),
              avg: series(-1),
              max: series(4),
            },
          ])
        ),
      },
    });
  });
  await page.goto('/overview');
  await page.getByRole('button', { name: 'Enter fullscreen overview' }).click();
  await waitForLayout(page, { width: 1920, height: 1080 }, true, true);
  const cards = page.locator('[data-metric-panel]');
  await expect(cards.locator('.uplot')).toHaveCount(5);
  await expect(cards.locator('.overview-metric-history__latest')).toHaveText([
    '54 ms',
    '58.3 Mbps',
    '32 Mbps',
    '<0.01%',
    '31.24%',
  ]);
  const geometry = () =>
    page.evaluate(() => {
      const box = (selector: string) =>
        document.querySelector(selector)!.getBoundingClientRect().toJSON();
      const panels = [...document.querySelectorAll('[data-metric-panel]')];
      return {
        cards: panels.map((node) => node.getBoundingClientRect().toJSON()),
        plots: [
          ...document.querySelectorAll('.overview-metric-history__viewport'),
        ].map((node) => node.getBoundingClientRect().height),
        fonts: [
          ...document.querySelectorAll('.overview-metric-history__latest'),
        ].map((node) => parseFloat(getComputedStyle(node).fontSize)),
        overflow: panels.some(
          (node) =>
            node.scrollHeight > node.clientHeight ||
            node.scrollWidth > node.clientWidth
        ),
        pageOverflow:
          document.querySelector('.overview-page')!.scrollHeight >
          document.querySelector('.overview-page')!.clientHeight,
        poi: box('[aria-label="Upcoming POIs"]'),
        clocks: box('.overview-clock-panel'),
        legend: box('.globe-legend'),
        context: box('[aria-label="Network history context"]'),
      };
    });
  const assertGeometry = (state: Awaited<ReturnType<typeof geometry>>) => {
    expect(state.overflow).toBe(false);
    expect(state.pageOverflow).toBe(false);
    expect(state.fonts).toEqual(Array(5).fill(36));
    expect(state.plots.every((height) => height >= 48)).toBe(true);
    expect(state.context.top).toBeGreaterThan(state.clocks.bottom);
    for (const card of state.cards) {
      expect(card.x).toBe(20);
      expect(card.width).toBe(440);
      expect(card.bottom).toBeLessThanOrEqual(1060);
      expect(card.top).toBeGreaterThan(state.clocks.bottom);
      expect(card.right).toBeLessThan(state.poi.left);
      expect(card.right).toBeLessThan(state.legend.left);
    }
    expect(state.poi.right).toBeLessThan(state.legend.left);
    expect(state.poi.bottom).toBeLessThanOrEqual(1060);
  };
  assertGeometry(await geometry());
  const context = page.getByLabel('Network history context');
  await expect(context.getByText('LAST 5 MIN', { exact: true })).toBeVisible();
  await expect(context.getByText('fresh', { exact: true })).toHaveClass(
    /overview-visually-hidden/
  );
  await expect(context.getByText('Rolling statistics: 5 minutes')).toHaveClass(
    /overview-visually-hidden/
  );
  expect((await context.boundingBox())!.height).toBeLessThanOrEqual(42);
  await expect(
    context.locator('.overview-metric-history-panels__error')
  ).toHaveCount(0);
  await expect(
    page.locator('.overview-metric-history__age').first()
  ).toHaveClass(/overview-visually-hidden/);
  await expect(
    page.locator('.overview-metric-history__time-axis').first()
  ).toHaveCSS('height', '1px');
  await page.screenshot({
    path: testInfo.outputPath('216-fresh-1920x1080.png'),
  });
  // Disable only the optional blur branch, reproducing unsupported-blur CSS.
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
  await expect(cards.first().locator('.overview-metric-history')).toHaveCSS(
    'background-color',
    'rgba(7, 18, 30, 0.9)'
  );
  await expect(cards.first().locator('.overview-metric-history')).toHaveCSS(
    'backdrop-filter',
    'none'
  );
  assertGeometry(await geometry());
  await page.screenshot({
    path: testInfo.outputPath('216-without-backdrop-blur-1920x1080.png'),
  });
  await page.evaluate(
    (rules) =>
      rules.forEach(({ sheetIndex, index, cssText }) =>
        document.styleSheets[sheetIndex].insertRule(cssText, index)
      ),
    blurRules
  );
  stale = true;
  failedHistory = true;
  await expect(cards.locator('.overview-metric-history__latest')).toHaveText(
    Array(5).fill('Unavailable'),
    { timeout: 15_000 }
  );
  await expect(
    page.getByText('History refresh unavailable', { exact: true })
  ).toBeVisible();
  assertGeometry(await geometry());
  await expect(
    cards.first().locator('.overview-metric-history__age')
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('216-stale-1920x1080.png'),
  });
  emptyPois = true;
  await expect(
    page.getByLabel('Upcoming POIs').locator('tbody tr')
  ).toHaveCount(0, { timeout: 12_000 });
  assertGeometry(await geometry());
  await page.evaluate(() => document.exitFullscreen());
  await waitForLayout(page, { width: 1920, height: 1080 }, false, false);
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 844, height: 390 },
    { width: 360, height: 800 },
  ]) {
    await page.setViewportSize(viewport);
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
      )
      .toBe(true);
    await cards.last().scrollIntoViewIfNeeded();
    await expect(cards.last()).toBeInViewport();
    await expect(
      page.getByRole('button', { name: 'Enter fullscreen overview' })
    ).toHaveCount(1);
  }
  // Reduced text must preserve clock clearance and pixel-sized card fit floors.
  for (const rootSize of [8, 12, 16]) {
    await page.evaluate((size) => {
      document.documentElement.style.fontSize = `${size}px`;
    }, rootSize);
    for (const viewport of [
      { width: 1920, height: 900 },
      { width: 1200, height: 1080 },
      { width: 1920, height: 1080 },
      { width: 1920, height: 1280 },
    ]) {
      await page.setViewportSize(viewport);
      for (const fullscreen of [false, true]) {
        if (fullscreen)
          await page
            .getByRole('button', { name: 'Enter fullscreen overview' })
            .click();
        const fixed =
          viewport.width === 1920 &&
          (viewport.height === 1280 ||
            (fullscreen && viewport.height === 1080));
        await waitForLayout(page, viewport, fullscreen, fixed);
        await page
          .locator('.overview-page')
          .evaluate((node) => node.scrollTo(0, 0));
        await expect
          .poll(async () => {
            const state = await geometry();
            return !state.overflow && state.context.top > state.clocks.bottom;
          })
          .toBe(true);
        const state = await geometry();
        expect(state.pageOverflow).toBe(!fixed);
        expect(state.plots.every((height) => height >= 48)).toBe(true);
        expect(
          await cards.evaluateAll((nodes) =>
            nodes.every((node) => {
              const plot = node
                .querySelector('.overview-metric-history__viewport')!
                .getBoundingClientRect();
              const card = node.getBoundingClientRect();
              return plot.top >= card.top && plot.bottom <= card.bottom;
            })
          )
        ).toBe(true);
        await page.screenshot({
          path: testInfo.outputPath(
            `216-root${rootSize}-${viewport.width}x${viewport.height}-${fullscreen ? 'fullscreen' : 'ordinary'}.png`
          ),
        });
        await cards.last().scrollIntoViewIfNeeded();
        await expect(cards.last()).toBeInViewport();
        await page.getByLabel('Upcoming POIs').scrollIntoViewIfNeeded();
        await expect(page.getByLabel('Upcoming POIs')).toBeInViewport();
        if (fullscreen) {
          await page.evaluate(() => document.exitFullscreen());
          await waitForLayout(
            page,
            viewport,
            false,
            viewport.width === 1920 && viewport.height === 1280
          );
        }
      }
    }
  }
  // Root/default text enlargement must select readable flow before clocks can
  // collide with the fixed desktop rail, in ordinary and native fullscreen.
  await page.evaluate(() => {
    document.documentElement.style.fontSize = '24px';
  });
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 1920, height: 1440 },
  ]) {
    await page.setViewportSize(viewport);
    for (const fullscreen of [false, true]) {
      if (fullscreen)
        await page
          .getByRole('button', { name: 'Enter fullscreen overview' })
          .click();
      await waitForLayout(page, viewport, fullscreen, false);
      await page
        .locator('.overview-page')
        .evaluate((node) => node.scrollTo(0, 0));
      await expect
        .poll(async () => {
          const state = await geometry();
          return state.context.top > state.clocks.bottom && !state.overflow;
        })
        .toBe(true);
      const context = page.getByLabel('Network history context');
      const clock = await page.locator('.overview-clock-panel').boundingBox();
      expect((await context.boundingBox())!.y).toBeGreaterThanOrEqual(
        clock!.y + clock!.height
      );
      await expect
        .poll(() =>
          page
            .locator('.overview-page')
            .evaluate((node) => node.scrollHeight > node.clientHeight)
        )
        .toBe(true);
      await page.screenshot({
        path: testInfo.outputPath(
          `216-root24-${viewport.width}x${viewport.height}-${fullscreen ? 'fullscreen' : 'ordinary'}.png`
        ),
      });
      await cards.last().scrollIntoViewIfNeeded();
      await expect(cards.last()).toBeInViewport();
      if (fullscreen) {
        await page.evaluate(() => document.exitFullscreen());
        await waitForLayout(page, viewport, false, false);
      }
    }
  }
});
