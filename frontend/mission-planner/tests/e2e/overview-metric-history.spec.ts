import { writeFile } from 'node:fs/promises';
import { buildSync } from 'esbuild';
import { expect, test } from '@playwright/test';

test.use({ video: { mode: 'on', size: { width: 1920, height: 1080 } } });
const metrics = [
  'starlink_network_latency_ms_current',
  'starlink_network_throughput_down_mbps_current',
  'starlink_network_throughput_up_mbps_current',
  'starlink_network_packet_loss_percent',
  'starlink_dish_obstruction_percent',
];
// Default empty fixtures keep these diagnostic tests independent of a backend.
// Later test-owned routes override them where populated data is required.
test.beforeEach(async ({ page }) => {
  for (const [endpoint, json] of [
    ['routes', { routes: [], total: 0 }],
    ['satellites', []],
    ['active-x-link', { satellite_id: null }],
    ['overview/upcoming-pois', { state: 'no_active_mission', pois: [] }],
    ['overview-clocks/settings', { clocks: [] }],
    ['status', { timestamp: new Date().toISOString() }],
  ] as const)
    await page.route(`**/api/${endpoint}`, (route) => route.fulfill({ json }));
});
const initial = Math.floor(Date.now() / 1000);
function bundle(end = initial, windowSeconds = 1800) {
  return {
    window_seconds: windowSeconds,
    start_timestamp_seconds: end - windowSeconds,
    end_timestamp_seconds: end,
    step_seconds: 5,
    series: Object.fromEntries(
      metrics.map((metric, index) => [
        metric,
        Array.from({ length: 5 }, (_, sample) => [
          end - 25 + sample * 5,
          index + sample + 1,
        ]),
      ])
    ),
    rolling_5m: Object.fromEntries(
      metrics.map((metric, index) => [
        metric,
        {
          state: 'available',
          min: Array.from({ length: 5 }, (_, sample) => [
            end - 25 + sample * 5,
            index + sample + 0.5,
          ]),
          avg: Array.from({ length: 5 }, (_, sample) => [
            end - 25 + sample * 5,
            index + sample + 1,
          ]),
          max: Array.from({ length: 5 }, (_, sample) => [
            end - 25 + sample * 5,
            index + sample + 1.5,
          ]),
        },
      ])
    ),
  };
}

test.describe('Overview metric history', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });
  for (const deviceScaleFactor of [1, 1.5, 2]) {
    test.describe(`display scale ${deviceScaleFactor}`, () => {
      test.use({ deviceScaleFactor });
      test('keeps one retained sample moving without a rebase jump after a delayed poll', async ({
        page,
      }) => {
        test.setTimeout(120_000);
        const start = Math.floor(Date.now() / 1000);
        const marker = start - 20;
        let responses = 0;
        let sampling = false;
        let freshEnd = 0;
        await page.route('**/api/overview-history/settings', (route) =>
          route.fulfill({ json: { window_seconds: 60 } })
        );
        await page.route('**/api/overview-history', async (route) => {
          const poll = responses++;
          if (poll === 1) {
            while (!sampling)
              await new Promise((resolve) => setTimeout(resolve, 100));
            freshEnd = Math.floor(Date.now() / 1000);
          }
          if (poll === 2)
            await new Promise((resolve) => setTimeout(resolve, 3_000));
          const end = poll === 0 ? start : freshEnd + (poll - 1) * 5;
          await route.fulfill({
            json: {
              window_seconds: 60,
              start_timestamp_seconds: end - 60,
              end_timestamp_seconds: end,
              step_seconds: 5,
              series: {
                [metrics[0]]: [
                  [marker - 5, 10],
                  [marker, 90],
                  [end - 5, 10],
                ],
              },
              rolling_5m: {
                [metrics[0]]: { state: 'available', min: [], avg: [], max: [] },
              },
            },
          });
        });
        await page.route('**/api/routes', (route) =>
          route.fulfill({ json: { routes: [], total: 0 } })
        );
        await page.route('**/api/overview/upcoming-pois', (route) =>
          route.fulfill({ json: { state: 'no_active_mission', pois: [] } })
        );
        await page.route('**/api/overview-clocks/settings', (route) =>
          route.fulfill({ json: { clocks: [] } })
        );
        await page.route('**/api/status', (route) =>
          route.fulfill({
            json: { timestamp: new Date(start * 1000).toISOString() },
          })
        );
        await page.route('**/api/satellites', (route) =>
          route.fulfill({ json: [] })
        );
        await page.route('**/api/active-x-link', (route) =>
          route.fulfill({ json: { satellite_id: null } })
        );
        await page.goto('/overview', { waitUntil: 'commit' });
        const panel = page.getByRole('region', {
          name: 'Network latency history',
        });
        const canvas = panel.locator('.uplot canvas').first();
        // Cold Overview/WebGL bootstrap can outlast the default 5s assertion wait.
        // Require the first response and its chart state, not merely a mounted panel.
        // A slow boot may legitimately exhaust the freshness margin before sampling.
        // The polled value exposes fixture and UI state if readiness times out.
        await expect
          .poll(
            async () => {
              const { status, opacityVisible } = await page.evaluate(() => {
                const section = document.querySelector(
                  'section[aria-label="Network latency history"]'
                );
                const canvas = section?.querySelector('.uplot canvas');
                let opacityVisible = Boolean(canvas);
                for (let node = canvas; node; node = node.parentElement)
                  if (Number(getComputedStyle(node).opacity) === 0)
                    opacityVisible = false;
                return {
                  status:
                    section?.querySelector('[role="status"]')?.textContent ??
                    (section ? '' : 'panel not mounted'),
                  opacityVisible,
                };
              });
              return {
                firstResponse: responses > 0,
                status,
                canvasVisible: opacityVisible && (await canvas.isVisible()),
              };
            },
            { timeout: 35_000, message: 'first latency history chart is ready' }
          )
          .toEqual({
            firstResponse: true,
            status: expect.stringMatching(/^(|Waiting for fresh history)$/),
            canvasVisible: true,
          });
        // Canvas bitmap dimensions include DPR; its CSS size must match uPlot's
        // logical size so timestamps and compositor motion use the same scale.
        const geometry = await canvas.evaluate((node) => ({
          canvas: node.getBoundingClientRect().width,
          plot: node.closest('.uplot')!.getBoundingClientRect().width,
        }));
        expect(Math.abs(geometry.canvas - geometry.plot)).toBeLessThan(1);
        sampling = true;
        // Read a retained sample's actual viewport position on every animation frame.
        // uPlot's committed scale is needed because a response changes the canvas origin.
        const positions = await panel.evaluate(async (section, marker) => {
          type Fiber = {
            return: Fiber | null;
            memoizedState?: { memoizedState: unknown; next: unknown } | null;
          };
          type Plot = {
            root: HTMLElement;
            data: number[][];
            scales: { x: { min: number; max: number } };
          };
          const key = Object.keys(section).find((item) =>
            item.startsWith('__reactFiber$')
          )!;
          const samples: { t: number; x: number; end: number }[] = [];
          let bundlesSeen = 0;
          let lastEnd: number | undefined;
          let thirdStarted = Infinity;
          const startTime = performance.now();
          while (performance.now() - startTime < 30_000) {
            await new Promise<void>((resolve) =>
              requestAnimationFrame(() => resolve())
            );
            let fiber: Fiber | null = (
              section as unknown as Record<string, Fiber>
            )[key];
            let plot: Plot | undefined;
            const root = section.querySelector('.uplot');
            while (fiber && !plot) {
              let hook = fiber.memoizedState;
              while (hook && !plot) {
                const value = (hook.memoizedState as { current?: Plot })
                  ?.current;
                if (value?.root === root) plot = value;
                hook = hook.next as typeof hook;
              }
              fiber = fiber.return;
            }
            if (!plot?.data[0].includes(marker)) continue;
            const canvas = section.querySelector(
              '.uplot canvas'
            ) as HTMLCanvasElement;
            const rect = canvas.getBoundingClientRect();
            const end = plot.scales.x.max - 7.5;
            if (end !== lastEnd) {
              bundlesSeen++;
              lastEnd = end;
              if (bundlesSeen === 3) thirdStarted = performance.now();
            }
            samples.push({
              t: performance.now(),
              x:
                rect.left +
                ((marker - plot.scales.x.min) /
                  (plot.scales.x.max - plot.scales.x.min)) *
                  rect.width,
              end,
            });
            if (performance.now() - thirdStarted > 1_000) break;
          }
          return samples;
        }, marker);
        const committedEnds = [...new Set(positions.map(({ end }) => end))];
        expect(committedEnds.length).toBeGreaterThanOrEqual(3);
        for (let i = 2; i < committedEnds.length; i++)
          expect(committedEnds[i] - committedEnds[i - 1]).toBe(5);
        const width = await panel
          .locator('.overview-metric-history__viewport')
          .evaluate((node) => node.clientWidth);
        const speed = width / 60 / 1000;
        const freshBundle = positions.filter(
          ({ end }) => end === committedEnds[1]
        );
        const moving = freshBundle.find(({ t }) => t - freshBundle[0].t >= 700);
        expect(
          moving,
          'fresh bundle must have a measurable animation interval'
        ).toBeDefined();
        const dt = moving!.t - freshBundle[0].t;
        const dx = moving!.x - freshBundle[0].x;
        expect(
          dx,
          'real sample must move left at viewport pixels per second'
        ).toBeLessThan(-speed * dt + 2);
        expect(dx, 'sample must not outrun the viewport clock').toBeGreaterThan(
          -speed * dt - 2
        );
        for (let i = 1; i < positions.length; i++) {
          const dx = positions[i].x - positions[i - 1].x;
          const dt = positions[i].t - positions[i - 1].t;
          expect(
            dx,
            `sample jumped right at ${positions[i].end}`
          ).toBeLessThanOrEqual(1.5);
          expect(
            dx,
            `sample jumped left at ${positions[i].end}`
          ).toBeGreaterThanOrEqual(-1.5 - speed * dt);
        }
      });
    });
  }
  test('keeps a real left-edge stroke through two rebases and clips it on exit', async ({
    page,
  }) => {
    test.setTimeout(100_000);
    const start = Math.floor(Date.now() / 1000);
    let requested = 0;
    let fulfilled = -1;
    let initialInspected = false;
    const edge = start - 60;
    await page.route('**/api/overview-history/settings', (route) =>
      route.fulfill({ json: { window_seconds: 60 } })
    );
    await page.route('**/api/overview-history', async (route) => {
      const poll = requested++;
      // Keep the initial edge frame observable even on a slow WebGL boot.
      if (poll === 1)
        while (!initialInspected)
          await new Promise((resolve) => setTimeout(resolve, 100));
      const end = start + poll * 5;
      await route.fulfill({
        json: {
          window_seconds: 60,
          start_timestamp_seconds: end - 60,
          end_timestamp_seconds: end,
          step_seconds: 1,
          series: {
            [metrics[0]]:
              poll === 0
                ? [
                    [edge + 3, 90],
                    [edge + 4, 90],
                  ]
                : [
                    [end - 10, 10],
                    [end - 9, 10],
                  ],
          },
          rolling_5m: {
            [metrics[0]]: {
              state: 'available',
              min: [],
              avg: [],
              max: [
                [end - 10, 90],
                [end - 9, 90],
              ],
            },
          },
        },
      });
      fulfilled = poll;
    });
    await page.route('**/api/routes', (route) =>
      route.fulfill({ json: { routes: [], total: 0 } })
    );
    await page.route('**/api/overview/upcoming-pois', (route) =>
      route.fulfill({ json: { state: 'no_active_mission', pois: [] } })
    );
    await page.route('**/api/overview-clocks/settings', (route) =>
      route.fulfill({ json: { clocks: [] } })
    );
    await page.route('**/api/status', (route) =>
      route.fulfill({
        json: { timestamp: new Date(start * 1000).toISOString() },
      })
    );
    await page.route('**/api/satellites', (route) =>
      route.fulfill({ json: [] })
    );
    await page.route('**/api/active-x-link', (route) =>
      route.fulfill({ json: { satellite_id: null } })
    );
    await page.goto('/overview', { waitUntil: 'commit' });
    const panel = page.getByRole('region', { name: 'Network latency history' });
    const canvas = panel.locator('.uplot canvas').first();
    await expect(canvas).toBeVisible();
    for (const poll of [0, 1, 2, 3]) {
      const end = start + poll * 5;
      await expect
        .poll(
          async () => {
            if (fulfilled < poll) return false;
            return panel.evaluate(
              (section, { end, edge, poll }) => {
                // Read the committed uPlot instance from React's plot ref. This
                // test-only inspection does not change production rendering.
                type Fiber = {
                  return: Fiber | null;
                  memoizedState?: {
                    memoizedState: unknown;
                    next: unknown;
                  } | null;
                };
                type Plot = {
                  root: HTMLElement;
                  data: number[][];
                  scales: { x: { min: number; max: number } };
                };
                const fiberKey = Object.keys(section).find((key) =>
                  key.startsWith('__reactFiber$')
                );
                let fiber = fiberKey
                  ? ((section as unknown as Record<string, Fiber>)[
                      fiberKey
                    ] as Fiber)
                  : null;
                const root = section.querySelector('.uplot');
                let plot: Plot | undefined;
                while (fiber && !plot) {
                  let hook = fiber.memoizedState;
                  while (hook && !plot) {
                    const value = (hook.memoizedState as { current?: Plot })
                      ?.current;
                    if (value?.root === root) plot = value;
                    hook = hook.next as typeof hook;
                  }
                  fiber = fiber.return;
                }
                if (!plot || plot.scales.x.max !== end + 7.5) return false;
                const markerInData = plot.data[0].includes(edge + 4);
                if (markerInData !== Boolean(poll < 3)) return false;
                if (poll === 3) return true; // Safe cutoff is now edge + 7.5.
                const viewport = section.querySelector(
                  '.overview-metric-history__viewport'
                )!;
                const el = section.querySelector(
                  '.uplot canvas'
                ) as HTMLCanvasElement;
                const canvasRect = el.getBoundingClientRect();
                const clip = viewport.getBoundingClientRect();
                const x =
                  ((edge + 4 - plot.scales.x.min) /
                    (plot.scales.x.max - plot.scales.x.min)) *
                  el.width;
                const screenX =
                  canvasRect.left + (x / el.width) * canvasRect.width;
                const inside =
                  screenX > clip.left + 2 && screenX < clip.right - 2;
                // Wait until the whole stroke is beyond the clipped viewport.
                if (poll === 2 ? screenX >= clip.left - 2 : !inside)
                  return false;
                if (x < 1 || x >= el.width - 1) return false;
                const { data, width, height } = el
                  .getContext('2d')!
                  .getImageData(0, 0, el.width, el.height);
                for (let y = 1; y < height / 5; y++)
                  for (
                    let px = Math.max(0, Math.floor(x - 7));
                    px <= Math.min(width - 1, Math.ceil(x + 7));
                    px++
                  ) {
                    const i = (y * width + px) * 4;
                    if (
                      data[i] < 170 &&
                      data[i + 1] > 175 &&
                      data[i + 2] > 185 &&
                      data[i + 3] > 0
                    )
                      return true;
                  }
                return false;
              },
              { end, edge, poll }
            );
          },
          {
            timeout: 25_000,
            message: `fulfilled poll ${poll} committed marker data and clipped paint`,
          }
        )
        .toBe(true);
      if (poll === 0) initialInspected = true;
    }
  });
  test('rebases painted samples across three five-second history polls', async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const start = Math.floor(Date.now() / 1000);
    let requests = 0;
    let completed = 0;
    const observed: [number, number][] = Array.from(
      { length: 25 },
      (_, index) => [start - 125 + index * 5, index === 19 ? 90 : 10]
    );
    await page.route('**/api/overview-history/settings', (route) =>
      route.fulfill({ json: { window_seconds: 300 } })
    );
    await page.route('**/api/routes', (route) =>
      route.fulfill({ json: { routes: [], total: 0 } })
    );
    await page.route('**/api/overview/upcoming-pois', (route) =>
      route.fulfill({ json: { state: 'no_active_mission', pois: [] } })
    );
    await page.route('**/api/overview-clocks/settings', (route) =>
      route.fulfill({ json: { clocks: [] } })
    );
    await page.route('**/api/status', (route) =>
      route.fulfill({
        json: { timestamp: new Date(start * 1000).toISOString() },
      })
    );
    await page.route('**/api/satellites', (route) =>
      route.fulfill({ json: [] })
    );
    await page.route('**/api/active-x-link', (route) =>
      route.fulfill({ json: { satellite_id: null } })
    );
    await page.route('**/api/overview-history', async (route) => {
      const poll = requests++;
      // A request starts before its response can update the painted chart.
      if (poll === 1)
        await new Promise((resolve) => setTimeout(resolve, 1_000));
      if (poll > 0 && poll <= 3)
        observed.push([start + (poll - 1) * 5, 10 + poll * 10]);
      const end = start + poll * 5;
      await route.fulfill({
        json: {
          window_seconds: 300,
          start_timestamp_seconds: end - 300,
          end_timestamp_seconds: end,
          step_seconds: 5,
          series: { [metrics[0]]: observed },
          rolling_5m: {
            [metrics[0]]: {
              state: 'available',
              min: observed.map(([time]) => [time, 5]),
              avg: observed.map(([time]) => [time, 7]),
              max: observed.map(([time]) => [time, 9]),
            },
          },
        },
      });
      completed++;
    });
    await page.goto('/overview', { waitUntil: 'commit' });
    const panel = page.getByRole('region', { name: 'Network latency history' });
    const canvas = panel.locator('.uplot canvas').first();
    await expect(canvas).toBeVisible({ timeout: 20_000 });
    for (let poll = 0; poll <= 3; poll++) {
      const end = start + poll * 5;
      // The response and uPlot's queued canvas commit are separate events.
      // Keep both real-pixel oracles inside one bounded, per-bundle wait.
      await expect
        .poll(
          async () => {
            if (completed <= poll) return { spike: false, fresh: false };
            return canvas.evaluate(
              (node, { end, spike, time, value, freshRequired }) => {
                const el = node as HTMLCanvasElement;
                const image = el
                  .getContext('2d')!
                  .getImageData(0, 0, el.width, el.height);
                const isCyan = (x: number, y: number) => {
                  if (x < 0 || x >= el.width || y < 0 || y >= el.height)
                    return false;
                  const i = (y * el.width + x) * 4;
                  return (
                    image.data[i] < 170 &&
                    image.data[i + 1] > 175 &&
                    image.data[i + 2] > 185 &&
                    image.data[i + 3] > 0
                  );
                };
                const dpr = el.width / el.getBoundingClientRect().width;
                const expected = ((spike - (end - 307.5)) / 315) * el.width;
                let spikePainted = false;
                // The cyan observed peak alone reaches the top fifth.
                for (let y = 1; y < el.height / 5 && !spikePainted; y++)
                  for (let x = 0; x < el.width; x++)
                    if (isCyan(x, y) && Math.abs(x - expected) / dpr < 4) {
                      spikePainted = true;
                      break;
                    }
                if (!freshRequired) return { spike: spikePainted, fresh: true };
                // upper = ceil(peak * 1.1) = 100 for this fixture.
                const upper = Math.ceil(90 * 1.1);
                const x = Math.round(((time - (end - 307.5)) / 315) * el.width);
                const y = Math.round((1 - value / upper) * el.height);
                let freshPainted = false;
                for (let dy = -4; dy <= 4 && !freshPainted; dy++)
                  for (let dx = -4; dx <= 4; dx++)
                    if (isCyan(x + dx, y + dy)) {
                      freshPainted = true;
                      break;
                    }
                return { spike: spikePainted, fresh: freshPainted };
              },
              {
                end,
                spike: start - 30,
                time: start + (poll - 1) * 5,
                value: 10 + poll * 10,
                freshRequired: poll > 0,
              }
            );
          },
          {
            timeout: 30_000,
            message: `poll ${poll}: fulfilled bundle has rebased spike and arriving observed pixel`,
          }
        )
        .toEqual({ spike: true, fresh: true });
      // A later scheduled poll may finish during a slow pixel wait.
      expect(completed).toBeGreaterThanOrEqual(poll + 1);
    }
  });
  test('marks all five charts unavailable on the first failed fetch, then recovers', async ({
    page,
  }) => {
    let fail = true;
    let windowSeconds = 1800;
    await page.route('**/api/overview-history/settings', (route) => {
      if (route.request().method() === 'PUT')
        windowSeconds = (
          route.request().postDataJSON() as { window_seconds: number }
        ).window_seconds;
      return route.fulfill({ json: { window_seconds: windowSeconds } });
    });
    await page.route('**/api/overview-history', (route) =>
      fail
        ? route.fulfill({ status: 503, json: { detail: 'unavailable' } })
        : route.fulfill({
            json: bundle(Math.floor(Date.now() / 1000), windowSeconds),
          })
    );
    await page.goto('/overview', { waitUntil: 'commit' });
    const panels = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    await expect(panels).toHaveCount(5);
    await expect(panels.getByRole('status')).toHaveText(
      Array(5).fill('History unavailable')
    );
    await expect(panels.locator('.uplot')).toHaveCount(0);
    fail = false;
    await page.getByLabel('Aircraft history window').selectOption('900');
    await expect(panels.getByRole('status')).toHaveCount(0, {
      timeout: 10_000,
    });
    await expect(panels.locator('.uplot')).toHaveCount(5);
  });
  test('fits five shared-query plots above POIs while preserving globe and legend', async ({
    page,
  }, testInfo) => {
    let requests = 0;
    const requestTimes: number[] = [];
    let end = initial;
    let windowSeconds = 1800;
    let fail = false;
    await page.route('**/api/overview-history', async (route) => {
      requests++;
      requestTimes.push(Date.now());
      if (fail)
        await route.fulfill({ status: 503, json: { detail: 'unavailable' } });
      else {
        end = Math.floor(Date.now() / 1000);
        await route.fulfill({ json: bundle(end, windowSeconds) });
      }
    });
    await page.route('**/api/overview-history/settings', async (route) => {
      if (route.request().method() === 'PUT') {
        windowSeconds = (
          route.request().postDataJSON() as { window_seconds: number }
        ).window_seconds;
        end += 5;
      }
      await route.fulfill({ json: { window_seconds: windowSeconds } });
    });
    await page.route('**/api/overview/upcoming-pois', async (route) => {
      await route.fulfill({ json: { state: 'no_active_mission', pois: [] } });
    });
    await page.route('**/api/routes', async (route) => {
      await route.fulfill({ json: { routes: [], total: 0 } });
    });
    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: new Date(initial * 1000).toISOString(),
          network: { latency_ms: 42 },
        },
      });
    });
    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({ json: [] });
    });
    await page.route('**/api/active-x-link', async (route) => {
      await route.fulfill({ json: { satellite_id: null } });
    });
    await page.route('**/api/overview-clocks/settings', async (route) => {
      await route.fulfill({
        json: {
          clocks: [
            { label: 'Zulu / UTC', time_zone: 'UTC' },
            { label: 'Washington, DC', time_zone: 'America/New_York' },
            { label: 'Omaha, NE', time_zone: 'America/Chicago' },
            { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
          ],
        },
      });
    });
    const texture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.ok()
    );
    await page.goto('/overview', { waitUntil: 'commit' });
    await expect(texture).resolves.toBeTruthy();
    const canvas = page.locator('.overview-page canvas').last();
    await expect(canvas).toBeVisible();
    await page.evaluate(
      () =>
        new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
    );
    const graphs = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    await expect(graphs).toHaveCount(5);
    await expect(graphs.locator('.uplot')).toHaveCount(5);
    const settledRequests = requests;
    expect(settledRequests).toBeGreaterThanOrEqual(1);
    const pois = await page.getByLabel('Upcoming POIs').boundingBox();
    const top = await page.locator('.overview-clock-panel').boundingBox();
    const legend = await page.getByLabel('Globe legend').boundingBox();
    await page.screenshot({
      path: testInfo.outputPath('overview-history-1920x1080.png'),
      animations: 'disabled',
    });
    for (const panel of await graphs.all()) {
      const box = await panel.boundingBox();
      expect(box && pois && box.y + box.height <= pois.y).toBeTruthy();
      expect(
        box &&
          top &&
          (box.y >= top.y + top.height ||
            box.x + box.width <= top.x ||
            box.x >= top.x + top.width)
      ).toBeTruthy();
      expect(box && box.y >= 0 && box.y + box.height <= 1080).toBeTruthy();
      expect(box && legend && box.x + box.width <= legend.x).toBeTruthy();
      for (const name of ['Observed', 'Average (5m)', 'Low–high envelope (5m)'])
        await expect(
          page.getByLabel('Graph traces').getByText(name, { exact: true })
        ).toBeVisible();
      await expect(
        panel.locator('.overview-metric-history__latest')
      ).toBeVisible();
      expect(
        await panel.evaluate((node) => node.scrollHeight <= node.clientHeight)
      ).toBe(true);
    }
    await expect(canvas).toBeVisible();
    expect(
      await canvas.evaluate(
        (node) => document.elementFromPoint(960, 570) === node
      )
    ).toBe(true);
    await page.mouse.move(960, 570);
    await page.mouse.down();
    await page.mouse.move(1100, 610, { steps: 8 });
    await page.mouse.up();
    await expect(page.getByLabel('Globe legend')).toBeVisible();

    const axis = graphs
      .first()
      .locator('.overview-metric-history__time-axis span:last-child');
    const surface = graphs.first().locator('.overview-metric-history__surface');
    const left = async () =>
      surface.evaluate(
        (node) => new DOMMatrix(getComputedStyle(node).transform).m41
      );
    const before = await axis.textContent();
    // A poll rebases the transform to zero; compare only within one bundle.
    await expect
      .poll(
        async () => {
          const bundleRequests = requests;
          const first = await left();
          await page.waitForTimeout(500);
          const second = await left();
          return requests === bundleRequests && second < first - 0.005;
        },
        { timeout: 12_000 }
      )
      .toBe(true);
    await expect
      .poll(() => axis.textContent(), { timeout: 8_000 })
      .not.toBe(before);
    await expect
      .poll(() => requests, { timeout: 8_000 })
      .toBeGreaterThan(settledRequests);
    // Every scheduled tick issues one GET, not five child-panel requests.
    for (let index = 1; index < requestTimes.length; index++)
      expect(
        requestTimes[index] - requestTimes[index - 1]
      ).toBeGreaterThanOrEqual(4_000);
    const beforeWindow = requests;
    const beforeWindowAxis = await graphs
      .first()
      .locator('.overview-metric-history__time-axis span:first-child')
      .textContent();
    await page.getByLabel('Aircraft history window').selectOption('900');
    await expect.poll(() => requests).toBeGreaterThan(beforeWindow);
    await expect
      .poll(() =>
        graphs
          .first()
          .locator('.overview-metric-history__time-axis span:first-child')
          .textContent()
      )
      .not.toBe(beforeWindowAxis);
    await expect(graphs.first().getByRole('status')).toHaveCount(0);
    const plottedBeforeFailure = await graphs
      .first()
      .locator('.uplot canvas')
      .first()
      .evaluate((node) => (node as HTMLCanvasElement).toDataURL());
    fail = true;
    const beforeFailure = requests;
    await expect
      .poll(() => requests, { timeout: 8_000 })
      .toBeGreaterThan(beforeFailure);
    await expect(graphs.first().getByRole('status')).toContainText(
      'Last-known history; refresh unavailable'
    );
    expect(
      await graphs
        .first()
        .locator('.uplot canvas')
        .first()
        .evaluate((node) => (node as HTMLCanvasElement).toDataURL())
    ).toBe(plottedBeforeFailure);
    fail = false;
    const beforeRecovery = requests;
    await expect
      .poll(() => requests, { timeout: 8_000 })
      .toBeGreaterThan(beforeRecovery);
    await expect(graphs.first().getByRole('status')).toHaveCount(0);
  });

  test('reflows legibly before two graph columns become cramped', async ({
    page,
  }) => {
    await page.route('**/api/overview-history', async (route) => {
      await route.fulfill({ json: bundle() });
    });
    await page.route('**/api/overview-history/settings', async (route) => {
      await route.fulfill({ json: { window_seconds: 1800 } });
    });
    await page.setViewportSize({ width: 800, height: 1080 });
    await page.goto('/overview', { waitUntil: 'commit' });
    const panels = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    await expect(panels).toHaveCount(5);
    for (const width of [800, 752, 705, 704]) {
      await page.setViewportSize({ width, height: 1080 });
      await expect(page.getByLabel('Upcoming POIs')).toBeVisible();
      await page.locator('.overview-page').evaluate(async (node) => {
        await new Promise<void>((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
        );
        await Promise.all(
          node
            .getAnimations({ subtree: true })
            .filter((animation) =>
              Number.isFinite(Number(animation.effect?.getTiming().iterations))
            )
            .map((animation) => animation.finished.catch(() => undefined))
        );
      });
      const pois = await page.getByLabel('Upcoming POIs').boundingBox();
      const boxes = await Promise.all(
        (await panels.all()).map((panel) => panel.boundingBox())
      );
      expect(boxes.every((box) => box && box.width >= 300)).toBe(true);
      expect(
        boxes.every((box) => box && pois && box.y + box.height <= pois.y)
      ).toBe(true);
      expect(
        boxes.every(
          (box, index) =>
            index === 0 ||
            (box &&
              boxes[index - 1] &&
              box.y >= boxes[index - 1]!.y + boxes[index - 1]!.height)
        )
      ).toBe(true);
      expect(
        await page
          .locator('.overview-page')
          .evaluate((node) => getComputedStyle(node).overflowY)
      ).toBe('auto');
      await expect(
        page.getByLabel('Graph traces').getByText('Observed', { exact: true })
      ).toBeVisible();
    }
  });
});

test.describe('Overview provenance motion recording', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });
  test('records zero, partial loss, recovery, gap, duration, resize and resume', async ({
    page,
  }, testInfo) => {
    test.setTimeout(90_000);
    const start = Math.floor(Date.now() / 1000);
    let windowSeconds = 60;
    let phase: 'fresh' | 'partial' | 'recovered' | 'stale' = 'fresh';
    let lastTimestamp = Date.now() - 1000;
    let histories = 0;
    const requestTimes: number[] = [];
    await page.route('**/api/overview-history/settings', (route) => {
      if (route.request().method() === 'PUT')
        windowSeconds = route.request().postDataJSON().window_seconds;
      return route.fulfill({ json: { window_seconds: windowSeconds } });
    });
    await page.route('**/api/overview-history', (route) => {
      histories++;
      requestTimes.push(Date.now());
      const end = Math.floor(Date.now() / 1000);
      const times = [
        start - 40,
        start - 35,
        start - 30,
        start - 25,
        start - 20,
        start - 15,
        start - 10,
        start - 5,
        start,
      ];
      if (end > start) times.push(end);
      return route.fulfill({
        json: {
          window_seconds: windowSeconds,
          start_timestamp_seconds: end - windowSeconds,
          end_timestamp_seconds: end,
          step_seconds: 5,
          series: Object.fromEntries(
            metrics.map((metric) => [
              metric,
              times.map((time) => [time, time === start - 20 ? null : 60]),
            ])
          ),
          rolling_5m: Object.fromEntries(
            metrics.map((metric) => [
              metric,
              {
                state: 'available',
                min: times.map((time) => [time, 20]),
                avg: times.map((time) => [time, 40]),
                max: times.map((time) => [time, 80]),
              },
            ])
          ),
        },
      });
    });
    await page.route('**/api/status', (route) => {
      // Collection predates this request, as in a real telemetry batch. A
      // response timestamp newer than the UI's age tick correctly fails closed.
      if (phase !== 'stale') lastTimestamp = Date.now() - 1000;
      return route.fulfill({
        json: {
          timestamp: new Date(lastTimestamp).toISOString(),
          metric_availability: {
            latency_ms: true,
            throughput_down_mbps: phase !== 'partial',
            throughput_up_mbps: true,
            packet_loss_percent: true,
            obstruction_percent: true,
          },
          network: {
            latency_ms: 7,
            throughput_down_mbps: phase === 'partial' ? null : 0,
            throughput_up_mbps: 2,
            packet_loss_percent: 0.2,
          },
          obstruction: { obstruction_percent: 3 },
          position: {
            latitude: 0,
            longitude: -50,
            altitude: 10000,
            heading: 90,
          },
        },
      });
    });
    for (const [endpoint, json] of [
      ['routes', { routes: [], total: 0 }],
      ['satellites', []],
      ['active-x-link', { satellite_id: null }],
      ['overview/upcoming-pois', { state: 'no_active_mission', pois: [] }],
      ['overview-clocks/settings', { clocks: [] }],
    ] as const)
      await page.route(`**/api/${endpoint}`, (route) =>
        route.fulfill({ json })
      );
    await page.goto('/overview', { waitUntil: 'commit' });
    const panels = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    const context = page.getByLabel('Network history context');
    // Scope by the descriptor wrapper, not text shared with the lower axis.
    const down = page.locator(
      '[data-metric-panel="downlink"] .overview-metric-history__latest'
    );
    await expect(panels.locator('.uplot')).toHaveCount(5);
    await expect(context.getByRole('status')).toHaveText('Network fresh');
    await expect(down).toHaveText('0 Mbps');
    const labels = () =>
      panels
        .locator('h3, .overview-metric-history__latest')
        .evaluateAll((nodes) =>
          nodes.map((node) => {
            const { x, y, width, height } = node.getBoundingClientRect();
            return [x, y, width, height];
          })
        );
    const before = await labels();
    const gap = await panels
      .first()
      .locator('section')
      .evaluate(
        (section, { start }) => {
          type Fiber = {
            return: Fiber | null;
            memoizedState?: { memoizedState: unknown; next: unknown } | null;
          };
          type Plot = {
            root: HTMLElement;
            scales: {
              x: { min: number; max: number };
              y: { min: number; max: number };
            };
          };
          const key = Object.keys(section).find((key) =>
            key.startsWith('__reactFiber$')
          )!;
          let fiber = (section as unknown as Record<string, Fiber>)[key];
          let plot: Plot | undefined;
          while (fiber && !plot) {
            let hook = fiber.memoizedState;
            while (hook && !plot) {
              const value = (hook.memoizedState as { current?: Plot })?.current;
              if (value?.root === section.querySelector('.uplot')) plot = value;
              hook = hook.next as typeof hook;
            }
            fiber = fiber.return!;
          }
          if (!plot) throw new Error('committed plot absent');
          const canvas = section.querySelector('canvas')!;
          const ctx = canvas.getContext('2d')!;
          return [start - 30, start - 20, start - 10].map((time) => {
            const x = Math.round(
              ((time - plot!.scales.x.min) /
                (plot!.scales.x.max - plot!.scales.x.min)) *
                canvas.width
            );
            const y = Math.round((1 - 30 / plot!.scales.y.max) * canvas.height);
            return [...ctx.getImageData(x, y, 1, 1).data];
          });
        },
        { start }
      );
    expect(gap[0][3]).toBeGreaterThan(0);
    expect(gap[1][3]).toBe(0);
    expect(gap[2][3]).toBeGreaterThan(0);
    phase = 'partial';
    await expect(context.getByRole('status')).toHaveText('Network partial');
    await expect(down).toHaveText('Unavailable');
    phase = 'recovered';
    await expect(context.getByRole('status')).toHaveText('Network fresh');
    await expect(down).toHaveText('0 Mbps');
    await expect
      .poll(() => histories, { timeout: 20_000 })
      .toBeGreaterThanOrEqual(3);
    expect(await labels()).toEqual(before);
    await page.mouse.move(960, 500);
    await page.mouse.wheel(0, -4000);
    await page.waitForTimeout(600); // Let OrbitControls damping settle for capture.
    await expect(context.getByRole('status')).toHaveText('Network fresh');
    await expect(down).toHaveText('0 Mbps');
    await page.screenshot({
      path: testInfo.outputPath('overview-provenance-1920x1080.png'),
    });
    await page.mouse.move(960, 500);
    await page.mouse.down();
    await page.mouse.move(1260, 550, { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(600);
    await expect(context.getByRole('status')).toHaveText('Network fresh');
    await expect(down).toHaveText('0 Mbps');
    expect(await labels()).toEqual(before);
    await page.screenshot({
      path: testInfo.outputPath('overview-provenance-rotated-1920x1080.png'),
    });
    await page.setViewportSize({ width: 1600, height: 1080 });
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.getByLabel('Aircraft history window').selectOption('900');
    await expect(
      context.getByText('Display: 15 minutes', { exact: true })
    ).toBeVisible();
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        value: true,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await page.waitForTimeout(1000);
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        value: false,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    phase = 'stale';
    await expect(context.getByRole('status')).toHaveText('Network stale', {
      timeout: 10_000,
    });
    await expect(down).toHaveText('Unavailable');
    await expect(
      page.locator(
        '[data-metric-panel="downlink"] .overview-metric-history__age'
      )
    ).toContainText('Last observed 0 Mbps');
    await writeFile(
      testInfo.outputPath('provenance-motion.json'),
      JSON.stringify(
        {
          fixture: true,
          gap,
          histories,
          requestTimes,
          visibility: 'synthetic document.hidden + visibilitychange',
          recording: 'Playwright video, 1920x1080',
        },
        null,
        2
      )
    );
  });
});

// Real panel + real uPlot; only the producer is controlled. Raster positions,
// not predicted timestamp coordinates, catch broken compositor rebases.
test.describe('painted four-series motion fixture', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });
  for (const cadence of [1, 5]) {
    test(`keeps painted trace and envelope cusps aligned at ${cadence}s rebases`, async ({
      page,
    }, testInfo) => {
      const built = buildSync({
        stdin: {
          contents: `import React from 'react';
            import {createRoot} from 'react-dom/client';
            import {flushSync} from 'react-dom';
            import {OverviewMetricHistoryPanel} from './src/pages/OverviewMetricHistoryPanel';
            import {OVERVIEW_METRIC_GRAPHS} from './src/pages/overview-metric-history';
            const root = createRoot(document.getElementById('fixture'));
            window.renderPanel = (history, windowSeconds = 60) => flushSync(() => root.render(
              React.createElement(OverviewMetricHistoryPanel, {
                descriptor: OVERVIEW_METRIC_GRAPHS[0], history, error: false,
                selectedWindowSeconds: windowSeconds, nowMs: Date.now(),
                readout: {value: 7, state: 'fresh', ageMs: 0, observedAtMs: Date.now()}
              })));
          `,
          resolveDir: process.cwd(),
          loader: 'tsx',
        },
        bundle: true,
        jsx: 'automatic',
        write: false,
        outfile: 'fixture.js',
        define: { 'process.env.NODE_ENV': '"production"' },
      });
      await page.setContent('<div id="fixture" style="width:480px"></div>');
      await page.addStyleTag({
        content: built.outputFiles.find((file) => file.path.endsWith('.css'))!
          .text,
      });
      await page.addStyleTag({
        content:
          '.overview-metric-history__viewport {flex:0 0 auto;width:400px;height:80px} .overview-metric-history {background:#111827;color:white}',
      });
      await page.addScriptTag({
        content: built.outputFiles.find((file) => file.path.endsWith('.js'))!
          .text,
      });
      const result = await page.evaluate(async (cadence) => {
        const renderPanel = (
          window as unknown as {
            renderPanel: (history: unknown, window?: number) => void;
          }
        ).renderPanel;
        const start = Math.floor(Date.now() / 1000);
        const marker = start - 20;
        const times = [marker - 10, marker, marker + 10, start];
        const values = (low: number, peak: number, end: number) =>
          [...times, ...(end > start ? [end] : [])].map((time, index) => [
            time,
            index === 1 ? peak : low,
          ]);
        const history = (end: number) => ({
          window_seconds: 60,
          start_timestamp_seconds: end - 60,
          end_timestamp_seconds: end,
          step_seconds: 10,
          series: { starlink_network_latency_ms_current: values(70, 80, end) },
          rolling_5m: {
            starlink_network_latency_ms_current: {
              state: 'available',
              min: values(10, 20, end),
              avg: values(30, 40, end),
              max: values(50, 60, end),
            },
          },
        });
        renderPanel(history(start));
        await new Promise((resolve) => setTimeout(resolve, 100));
        const section = document.querySelector('section')!;
        const labelBoxes = () =>
          [
            ...section.querySelectorAll(
              'h3, .overview-metric-history__latest, .overview-metric-history__value-axis, .overview-metric-history__time-axis'
            ),
          ].map((node) => {
            const { x, y, width, height } = node.getBoundingClientRect();
            return [x, y, width, height];
          });
        const labels = labelBoxes();
        const samples: { t: number; end: number; positions: number[] }[] = [];
        const began = performance.now();
        let end = start;
        let refreshes = 0;
        while (performance.now() - began < cadence * 2000 + 400) {
          await new Promise<void>((resolve) =>
            requestAnimationFrame(() => resolve())
          );
          if (
            refreshes < 2 &&
            performance.now() - began >= (refreshes + 1) * cadence * 1000
          ) {
            end = start + ++refreshes * cadence;
            renderPanel(history(end));
            // uPlot queues its raster commit in a microtask. Drain it before
            // reading pixels: the old bitmap + new transform inside this same
            // JS task is never a composited browser frame.
            await new Promise<void>((resolve) => queueMicrotask(resolve));
          }
          const canvas = section.querySelector('canvas')!;
          const rect = canvas.getBoundingClientRect();
          const { data, width, height } = canvas
            .getContext('2d')!
            .getImageData(0, 0, canvas.width, canvas.height);
          const extrema = [Infinity, Infinity, Infinity, Infinity];
          const xs: number[][] = [[], [], [], []];
          // Cyan observed, white dashed average, upper/lower alpha-band edges.
          for (let x = 0; x < width; x++) {
            let top = Infinity,
              bottom = -Infinity;
            for (let y = 0; y < height; y++) {
              const i = (y * width + x) * 4;
              const r = data[i],
                g = data[i + 1],
                b = data[i + 2],
                a = data[i + 3];
              const category =
                a > 100 && r < 180 && g > 175 && b > 185
                  ? 0
                  : a > 100 && r > 200 && g > 200 && b > 200
                    ? 1
                    : -1;
              if (category >= 0) {
                if (y < extrema[category]) {
                  extrema[category] = y;
                  xs[category] = [];
                }
                if (y === extrema[category]) xs[category].push(x);
              }
              if (
                a >= 30 &&
                a <= 50 &&
                r > 160 &&
                r < 200 &&
                g > 180 &&
                b > 200
              ) {
                top = Math.min(top, y);
                bottom = Math.max(bottom, y);
              }
            }
            for (const [category, y] of [
              [2, top],
              [3, bottom],
            ]) {
              if (!Number.isFinite(y)) continue;
              if (y < extrema[category]) {
                extrema[category] = y;
                xs[category] = [];
              }
              if (y === extrema[category]) xs[category].push(x);
            }
          }
          const positions = xs.map(
            (points) =>
              rect.left +
              (points.reduce((a, b) => a + b, 0) / points.length / width) *
                rect.width
          );
          samples.push({ t: performance.now(), end, positions });
        }
        const labelsAfter = labelBoxes();
        const viewport = section.querySelector(
          '.overview-metric-history__viewport'
        ) as HTMLElement;
        viewport.style.width = '300px';
        await new Promise((resolve) => setTimeout(resolve, 100));
        const resized = section
          .querySelector('canvas')!
          .getBoundingClientRect().width;
        Object.defineProperty(document, 'hidden', {
          configurable: true,
          value: true,
        });
        document.dispatchEvent(new Event('visibilitychange'));
        await new Promise((resolve) => setTimeout(resolve, 50));
        const surface = section.querySelector(
          '.overview-metric-history__surface'
        )!;
        const frozen = getComputedStyle(surface).transform;
        await new Promise((resolve) => setTimeout(resolve, 800));
        const hidden = getComputedStyle(surface).transform;
        Object.defineProperty(document, 'hidden', {
          configurable: true,
          value: false,
        });
        document.dispatchEvent(new Event('visibilitychange'));
        const resumed = getComputedStyle(surface).transform;
        return {
          samples,
          refreshes,
          labels,
          labelsAfter,
          resized,
          frozen,
          hidden,
          resumed,
        };
      }, cadence);
      await writeFile(
        testInfo.outputPath(`painted-${cadence}s.json`),
        JSON.stringify(result, null, 2)
      );
      expect(result.refreshes).toBe(2);
      expect(result.labelsAfter).toEqual(result.labels);
      expect(result.resized).toBe(375);
      expect(result.hidden).toBe(result.frozen);
      expect(result.resumed).toBe(result.frozen);
      expect(new Set(result.samples.map(({ end }) => end)).size).toBe(3);
      for (const sample of result.samples)
        expect(sample.positions.every(Number.isFinite)).toBe(true);
      for (const end of new Set(result.samples.map((sample) => sample.end))) {
        const frames = result.samples.filter((sample) => sample.end === end);
        const first = frames[0],
          last = frames.at(-1)!;
        expect(last.t - first.t).toBeGreaterThan(200);
        for (let trace = 0; trace < 4; trace++)
          expect(
            Math.abs(
              last.positions[trace] -
                first.positions[trace] +
                ((last.t - first.t) * 400) / 60000
            )
          ).toBeLessThanOrEqual(1);
      }
      for (let i = 1; i < result.samples.length; i++) {
        const previous = result.samples[i - 1],
          current = result.samples[i];
        const elapsed = (current.t - previous.t) / 1000;
        for (let trace = 0; trace < 4; trace++) {
          expect(
            Math.abs(current.positions[trace] - previous.positions[trace])
          ).toBeLessThanOrEqual(1 + (elapsed * 400) / 60);
        }
      }
      await page.screenshot({
        path: testInfo.outputPath(`painted-${cadence}s.png`),
      });
    });
  }
});
