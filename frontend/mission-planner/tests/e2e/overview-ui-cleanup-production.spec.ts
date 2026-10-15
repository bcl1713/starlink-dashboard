import { expect, test } from '@playwright/test';
import { seedOverviewWindowMission } from './support/overview-window-mission';
import {
  installOverviewRouteProbe,
  renderedRoutePoints,
} from './support/overview-route-probe';

test.use({ viewport: { width: 1920, height: 1080 } });

// This suite runs against isolated production images. No API interception.
test('saved visibility reaches another Overview window and configuration stays organized', async ({
  context,
  request,
}, info) => {
  expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
  const endpoint = '/api/overview-links/settings';
  const initial = await (await request.get(endpoint)).json();
  const seed = await seedOverviewWindowMission(request);
  const activation = await request.post(
    `/api/v2/missions/${seed.missionId}/legs/${seed.firstLegId}/activate`
  );
  expect(activation.status(), await activation.text()).toBe(200);
  const overview = await context.newPage();
  const editing = await context.newPage();
  try {
    await installOverviewRouteProbe(overview);
    await overview.goto('/overview');
    await expect(overview.locator('.overview-globe canvas')).toBeVisible();
    await expect.poll(() => renderedRoutePoints(overview)).not.toEqual([]);
    const identity = overview.getByLabel('Overview display identity');
    await expect(identity).toHaveText(/^Overview [a-f0-9]{6}$/);
    await expect(
      overview
        .getByLabel('Globe legend')
        .getByLabel('Overview display identity')
    ).toBeVisible();
    expect(
      await identity.evaluate((node) =>
        parseFloat(getComputedStyle(node).fontSize)
      )
    ).toBeLessThanOrEqual(12);
    expect(
      await overview
        .locator('.overview-display-controls')
        .getByLabel('Overview display identity')
        .count()
    ).toBe(0);
    await overview.screenshot({
      path: info.outputPath('overview-desktop.png'),
    });
    await editing.goto('/configuration');
    await expect(
      editing.getByRole('switch', { name: 'Operational clocks panel' })
    ).toBeEnabled();
    await expect(
      editing.getByRole('switch', { name: 'Precipitation radar' })
    ).toHaveCount(0);
    await editing.screenshot({
      path: info.outputPath('configuration-overview.png'),
    });
    const groups = [
      [
        'Overview',
        [
          ['Operational clocks panel', 'operational_clocks_enabled'],
          ['Departure and arrival panel', 'arrival_panel_enabled'],
          ['Planned satellite panel', 'planned_satellite_panel_enabled'],
          ['Map status panel', 'map_status_enabled'],
          ['Map legend', 'legend_enabled'],
          ['Planned route', 'planned_route_enabled'],
          ['Points of interest', 'poi_markers_enabled'],
        ],
      ],
      [
        'Network Traffic',
        [
          ['Configured satellite markers', 'configured_satellites_enabled'],
          ['Ground entry point', 'ground_entry_point_enabled'],
          ['Network latency panel', 'latency_panel_enabled'],
          ['Downlink throughput panel', 'downlink_panel_enabled'],
          ['Uplink throughput panel', 'uplink_panel_enabled'],
          ['Packet loss panel', 'packet_loss_panel_enabled'],
          ['Dish obstruction panel', 'obstruction_panel_enabled'],
        ],
      ],
      [
        'Aircraft Traffic',
        [
          ['Own aircraft marker', 'aircraft_marker_enabled'],
          ['Aircraft history', 'aircraft_history_enabled'],
        ],
      ],
    ] as const;
    for (const [tab, controls] of groups) {
      await editing.getByRole('tab', { name: tab, exact: true }).click();
      if (tab === 'Network Traffic')
        await expect(
          editing.getByRole('switch', { name: 'Aircraft history' })
        ).toHaveCount(0);
      for (const [name, field] of controls) {
        const control = editing.getByRole('switch', { name, exact: true });
        await expect(control).toBeEnabled();
        await expect(control).toBeChecked();
        await control.click();
        await expect(control).not.toBeChecked();
        const confirmed = await request.get(endpoint);
        expect(confirmed.headers().server).toMatch(/nginx/);
        expect((await confirmed.json())[field]).toBe(false);
      }
    }
    await expect(overview.locator('.overview-top-overlays')).toHaveCount(0, {
      timeout: 10000,
    });
    await expect(overview.getByLabel('Departure and arrival')).toHaveCount(0);
    await expect(overview.getByLabel('Planned satellite')).toHaveCount(0);
    await expect(overview.getByLabel('Map status')).toHaveCount(0);
    await expect(overview.getByLabel('Globe legend')).toHaveCount(0);
    await expect(overview.locator('[data-metric-panel]')).toHaveCount(0);
    await expect(overview.getByLabel('Map POIs')).toHaveCount(0);
    await expect(overview.getByLabel('Configured map satellites')).toHaveCount(
      0
    );
    await expect.poll(() => renderedRoutePoints(overview)).toEqual([]);
    await expect(identity).toBeVisible();
    await expect(
      overview.getByRole('button', { name: 'Enter fullscreen overview' })
    ).toBeVisible();
    await overview.screenshot({
      path: info.outputPath('overview-minimal-desktop.png'),
    });
    // A single restored graph must use the full rail and retain its readout.
    await editing.getByRole('tab', { name: 'Network Traffic' }).click();
    await editing
      .getByRole('switch', { name: 'Network latency panel' })
      .click();
    await expect(overview.locator('[data-metric-panel]')).toHaveCount(1, {
      timeout: 10000,
    });
    await expect(
      overview.locator('[data-metric-panel="latency"]')
    ).toBeVisible();
    await overview.screenshot({
      path: info.outputPath('overview-one-graph.png'),
    });
    await overview.setViewportSize({ width: 390, height: 844 });
    await expect
      .poll(
        async () =>
          (
            await overview
              .locator('[data-metric-panel="latency"]')
              .boundingBox()
          )?.width ?? 0
      )
      .toBeGreaterThan(300);
    await overview.screenshot({
      path: info.outputPath('overview-one-graph-mobile.png'),
      fullPage: true,
    });
    await overview.setViewportSize({ width: 1920, height: 1080 });
    await editing.getByRole('tab', { name: 'Weather', exact: true }).click();
    for (const name of [
      'Precipitation radar',
      'METAR / SPECI observations',
      'TAF terminal forecasts',
      'International SIGMET advisories',
      'GFS winds',
      'GFS air temperature',
    ]) {
      await expect(
        editing.getByRole('switch', { name, exact: true })
      ).toBeVisible();
    }
    await editing.screenshot({
      path: info.outputPath('configuration-weather.png'),
    });
    expect((await request.put(endpoint, { data: initial })).status()).toBe(200);
    await expect(overview.locator('[data-metric-panel]')).toHaveCount(5, {
      timeout: 10000,
    });
    await expect.poll(() => renderedRoutePoints(overview)).not.toEqual([]);
    await expect(
      overview
        .getByLabel('Globe legend')
        .getByLabel('Overview display identity')
    ).toBeVisible();
    await overview.bringToFront();
    await overview
      .getByRole('button', { name: 'Enter fullscreen overview' })
      .click();
    await expect
      .poll(() => overview.evaluate(() => Boolean(document.fullscreenElement)))
      .toBe(true);
    await expect(identity).toBeVisible();
    await overview.screenshot({
      path: info.outputPath('overview-fullscreen.png'),
    });
    await overview.evaluate(() => document.exitFullscreen());
    await expect
      .poll(() => overview.evaluate(() => Boolean(document.fullscreenElement)))
      .toBe(false);
    for (const [width, height] of [
      [1024, 600],
      [390, 844],
    ]) {
      await overview.setViewportSize({ width, height });
      await editing.setViewportSize({ width, height });
      await expect(overview.locator('.overview-globe canvas')).toBeVisible();
      await expect(
        editing.getByRole('switch', { name: 'GFS winds' })
      ).toBeVisible();
      for (const page of [overview, editing]) {
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth
          )
        ).toBe(true);
      }
      await overview.screenshot({
        path: info.outputPath(`overview-${width}x${height}.png`),
        fullPage: true,
      });
      await editing.screenshot({
        path: info.outputPath(`configuration-weather-${width}x${height}.png`),
        fullPage: true,
      });
      await editing
        .getByRole('tab', { name: 'Aircraft Traffic', exact: true })
        .click();
      await expect(
        editing.getByRole('switch', { name: 'Aircraft history' })
      ).toBeVisible();
      await editing.screenshot({
        path: info.outputPath(`configuration-aircraft-${width}x${height}.png`),
        fullPage: true,
      });
      await editing.getByRole('tab', { name: 'Weather', exact: true }).click();
    }
  } finally {
    await request.put(endpoint, { data: initial });
    await request.post(`/api/v2/missions/${seed.missionId}/legs/deactivate`);
    await request.delete(`/api/v2/missions/${seed.missionId}`);
    await editing.close();
    await overview.close();
  }
});
