import { writeFile } from 'node:fs/promises';
import { expect, test, type Page, type Response } from '@playwright/test';
import { ROUTE_OVERLAY_RADIUS } from '../../src/pages/globe-render-radii';
import { projectRouteArc } from '../../src/pages/globe-route-projection';
import type { RouteDetail } from '../../src/services/routes';
import { seedOverviewWindowMission } from './support/overview-window-mission';
import {
  installOverviewRouteProbe,
  renderedRoutePoints,
} from './support/overview-route-probe';
import {
  settledOverviewCamera,
  expectSameCamera,
} from './support/overview-camera';
import {
  retainedHistoryTimes,
  historyWindowState,
} from './support/overview-window-fixture';

async function explore(page: Page) {
  const automatic = await settledOverviewCamera(page);
  const toggle = page.getByRole('button', { name: 'Explore map', exact: true });
  if (await toggle.isVisible()) await toggle.click();
  const box = (await page.locator('.overview-globe canvas').boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.6);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5, {
    steps: 10,
  });
  await page.mouse.up();
  const manual = await settledOverviewCamera(page);
  expect(manual.position).not.toEqual(automatic.position);
  return manual;
}
for (const fullscreen of [false, true]) {
  test(`real Nginx saves and mission lifecycle reach ${fullscreen ? 'native fullscreen' : 'ordinary'} Overview without focus or remount`, async ({
    context,
    request,
  }, info) => {
    const sha = process.env.ACCEPTANCE_CANDIDATE_SHA;
    expect(sha, 'runner must bind evidence to an exact candidate').toMatch(
      /^[a-f0-9]{40}$/
    );
    const log: unknown[] = [];
    const timings: Record<string, number> = {};
    const observations: Record<string, unknown> = {};
    const reads: Record<string, number> = {};
    context.on('response', (response) => {
      const pathname = new URL(response.url()).pathname;
      if (!pathname.startsWith('/api/')) return;
      const req = response.request();
      const page = req.frame().url();
      log.push({
        endpoint: pathname,
        method: req.method(),
        status: response.status(),
        at: Date.now(),
        page,
      });
      if (req.method() === 'GET' && page.includes('/overview'))
        reads[pathname] = (reads[pathname] ?? 0) + 1;
    });
    // No page/context route handlers: every application response is real.
    const seed = await seedOverviewWindowMission(request);
    observations.seed = seed;
    async function confirmed(response: Response) {
      expect(response.status(), response.url()).toBe(200);
      expect(new URL(response.url()).origin).toBe(info.project.use.baseURL);
      expect(response.headers().server).toMatch(/nginx/);
      const at = Date.now();
      observations[
        `${response.request().method()} ${new URL(response.url()).pathname}`
      ] = await response.json();
      return at;
    }
    async function visible(
      name: string,
      at: number,
      assertion: (remaining: number) => Promise<void>
    ) {
      await assertion(Math.max(1, 8000 - (Date.now() - at)));
      timings[name] = Date.now() - at;
      expect(timings[name], name).toBeLessThanOrEqual(8000);
      expect(
        await editing.evaluate(() => document.hasFocus()),
        `${name}: editor stays foreground`
      ).toBe(true);
    }
    const overview = await context.newPage();
    await installOverviewRouteProbe(overview);
    let navigations = 0;
    overview.on('framenavigated', (frame) => {
      if (frame === overview.mainFrame()) navigations++;
    });
    const editing = await context.newPage();
    try {
      await overview.goto('/overview');
      await expect(
        overview.getByText('No active route.', { exact: true })
      ).toBeVisible({ timeout: 20000 });
      if (fullscreen) {
        await overview
          .getByRole('button', { name: 'Enter fullscreen overview' })
          .click();
        await expect
          .poll(() => overview.evaluate(() => !!document.fullscreenElement))
          .toBe(true);
      }
      const manual = await explore(overview);
      const baseline = navigations;
      const canvas = await overview
        .locator('.overview-globe canvas')
        .elementHandle();
      await expect(overview.locator('.uplot')).toHaveCount(5, {
        timeout: 20000,
      });
      const plots = await overview.locator('.uplot').elementHandles();
      const retained = await retainedHistoryTimes(overview);
      expect(retained.length).toBeGreaterThan(0);
      const marker = retained[retained.length - 1];
      observations.retainedSample = marker;
      observations.cameraBefore = manual;
      const draft = await context.newPage();
      await draft.goto('/configuration');
      await draft
        .getByLabel('Clock 3 label')
        .fill('Unsubmitted production draft');
      await editing.goto('/configuration');
      await editing.bringToFront();
      await editing.getByLabel('Clock 3 label').fill('Honolulu operations');
      await editing.getByLabel('Clock 3 timezone').fill('Pacific/Honolulu');
      const saved = editing.waitForResponse(
        (r) =>
          r.url().endsWith('/api/overview-clocks/settings') &&
          r.request().method() === 'PUT'
      );
      await editing
        .getByRole('button', { name: 'Save operational clocks' })
        .click();
      const savedAt = await confirmed(await saved);
      const clock = overview.getByRole('region', {
        name: 'Honolulu operations operational clock',
        exact: true,
      });
      await visible('clock', savedAt, (remaining) =>
        expect(clock).toBeVisible({ timeout: remaining })
      );
      const time = await clock.locator('time').evaluate((node) => ({
        at: node.getAttribute('datetime')!,
        text: node.textContent,
      }));
      expect(time.text).toBe(
        new Intl.DateTimeFormat('en-GB', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hourCycle: 'h23',
          timeZone: 'Pacific/Honolulu',
        }).format(new Date(time.at))
      );
      observations.clock = time;
      const clocks = await request.get('/api/overview-clocks/settings');
      expect(clocks.status()).toBe(200);
      expect((await clocks.json()).clocks[2]).toEqual({
        label: 'Honolulu operations',
        time_zone: 'Pacific/Honolulu',
      });
      await expect(draft.getByLabel('Clock 3 label')).toHaveValue(
        'Unsubmitted production draft'
      );
      expectSameCamera(manual, await settledOverviewCamera(overview));
      for (const [label, field] of [
        ['Starshield data link', 'starshield_link_enabled'],
        ['X-band data link', 'x_band_link_enabled'],
      ]) {
        const saved = editing.waitForResponse(
          (r) =>
            r.url().endsWith('/api/overview-links/settings') &&
            r.request().method() === 'PUT'
        );
        await editing.getByRole('switch', { name: label }).uncheck();
        const at = await confirmed(await saved);
        await visible(field, at, (remaining) =>
          expect(overview.getByLabel('Globe legend')).not.toContainText(
            label.startsWith('Starshield')
              ? 'Traffic path'
              : 'Planned satellite link',
            { timeout: remaining }
          )
        );
        const links = await request.get('/api/overview-links/settings');
        expect((await links.json())[field]).toBe(false);
      }
      const historySaved = editing.waitForResponse(
        (r) =>
          r.url().endsWith('/api/overview-history/settings') &&
          r.request().method() === 'PUT'
      );
      await editing.getByLabel('Overview history window').selectOption('900');
      const historyAt = await confirmed(await historySaved);
      await visible('history-window', historyAt, (remaining) =>
        expect
          .poll(() => historyWindowState(overview), { timeout: remaining })
          .toEqual({ selected: 900, bundle: 900 })
      );
      expect(await retainedHistoryTimes(overview)).toContain(marker);
      // Browser-local storage event changes intent, independently of REST.
      const followAt = Date.now();
      await editing.getByLabel('Follow aircraft on Overview').check();
      await visible('browser-follow', followAt, (remaining) =>
        expect(
          overview.getByText('Following aircraft', { exact: true })
        ).toBeVisible({ timeout: remaining })
      );
      await editing.getByLabel('Follow aircraft on Overview').uncheck();
      await expect(
        overview.getByText('Following aircraft', { exact: true })
      ).toHaveCount(0);
      // Re-establish manual intent before mission route changes.
      const missionManual = await settledOverviewCamera(overview);
      await editing.goto(`/missions/${seed.missionId}`);
      await editing.bringToFront();
      for (const [index, legId] of [
        seed.firstLegId,
        seed.secondLegId,
      ].entries()) {
        const routeId = index === 0 ? seed.firstRouteId : seed.secondRouteId;
        const routeResponse = await request.get(`/api/routes/${routeId}`);
        expect(routeResponse.status()).toBe(200);
        const expectedRoute: RouteDetail = await routeResponse.json();
        expect(expectedRoute.id).toBe(routeId);
        observations[routeId] = expectedRoute;
        const endpoint = `/api/v2/missions/${seed.missionId}/legs/${legId}/activate`;
        const activated = editing.waitForResponse(
          (r) => r.url().endsWith(endpoint) && r.request().method() === 'POST'
        );
        await editing
          .getByRole('button', { name: 'Activate', exact: true })
          .first()
          .click();
        const at = await confirmed(await activated);
        await visible(`activate-${index}`, at, async (remaining) => {
          await expect
            .poll(() => renderedRoutePoints(overview), { timeout: remaining })
            .toEqual(
              projectRouteArc(expectedRoute.points!, ROUTE_OVERLAY_RADIUS, 8)
            );
          await expect(overview.getByLabel('Map POIs')).toContainText(
            index === 0 ? 'KAAA' : 'KCCC',
            { timeout: Math.max(1, 8000 - (Date.now() - at)) }
          );
          await expect(
            overview.getByLabel('Departure and arrival')
          ).toContainText('SCHEDULED DEPARTURE', {
            timeout: Math.max(1, 8000 - (Date.now() - at)),
          });
        });
        const pois = await request.get('/api/overview/upcoming-pois');
        expect(pois.status()).toBe(200);
        const generated = await pois.json();
        expect(generated.state).toBe('available');
        expect(
          generated.pois.some((poi: { name: string }) =>
            poi.name.includes(index === 0 ? 'KBBB' : 'KDDD')
          )
        ).toBe(true);
        observations[`generated-${index}`] = generated;
        const stored = await request.get(`/api/v2/missions/${seed.missionId}`);
        expect(
          (await stored.json()).legs
            .filter((leg: { is_active: boolean }) => leg.is_active)
            .map((leg: { id: string }) => leg.id)
        ).toEqual([legId]);
        expectSameCamera(missionManual, await settledOverviewCamera(overview));
      }
      // Updating the active leg recalculates its real timeline and generated POIs.
      await editing.goto(
        `/missions/${seed.missionId}/legs/${seed.secondLegId}`
      );
      await editing.bringToFront();
      const adjusted = new Date(Date.now() + 7200000);
      adjusted.setUTCSeconds(0, 0);
      await expect(editing.locator('#departure-date')).toBeVisible({
        timeout: 20000,
      });
      await editing
        .locator('#departure-date')
        .fill(adjusted.toISOString().slice(0, 10));
      await editing
        .locator('#departure-time')
        .fill(adjusted.toISOString().slice(11, 16));
      const edited = editing.waitForResponse(
        (r) =>
          r.url().endsWith(`/legs/${seed.secondLegId}`) &&
          r.request().method() === 'PUT'
      );
      editing.once('dialog', (dialog) => dialog.accept());
      await editing.getByRole('button', { name: 'Apply', exact: true }).click();
      const editAt = await confirmed(await edited);
      await visible('active-leg-timing', editAt, (remaining) =>
        expect(
          overview.getByLabel('Departure and arrival').locator('time')
        ).toHaveAttribute('datetime', adjusted.toISOString(), {
          timeout: remaining,
        })
      );
      const changedPois = await request.get('/api/overview/upcoming-pois');
      const changed = await changedPois.json();
      expect(new Date(changed.scheduled_departure_time).toISOString()).toBe(
        adjusted.toISOString()
      );
      observations.editedGenerated = changed;
      await editing.goto(`/missions/${seed.missionId}`);
      editing.once('dialog', (dialog) => dialog.accept());
      const deactivated = editing.waitForResponse(
        (r) =>
          r.url().endsWith('/legs/deactivate') &&
          r.request().method() === 'POST'
      );
      await editing
        .getByRole('button', { name: 'Deactivate All', exact: true })
        .click();
      const at = await confirmed(await deactivated);
      await visible('deactivation', at, async (remaining) => {
        await expect
          .poll(() => renderedRoutePoints(overview), { timeout: remaining })
          .toEqual([]);
        await expect(overview.getByLabel('Map POIs').locator('li')).toHaveCount(
          0,
          { timeout: Math.max(1, 8000 - (Date.now() - at)) }
        );
        await expect(
          overview.getByLabel('Departure and arrival')
        ).toContainText('No active mission leg.', {
          timeout: Math.max(1, 8000 - (Date.now() - at)),
        });
      });
      expectSameCamera(missionManual, await settledOverviewCamera(overview));
      expect(
        await canvas!.evaluate(
          (node) => node === document.querySelector('.overview-globe canvas')
        )
      ).toBe(true);
      // History-window change intentionally recreates plots; clocks/mission changes do not recreate Canvas.
      observations.initialPlotCount = plots.length;
      expect(await retainedHistoryTimes(overview)).toContain(marker);
      expect(navigations).toBe(baseline);
      expect(await overview.evaluate(() => !!document.fullscreenElement)).toBe(
        fullscreen
      );
      observations.fullscreen = fullscreen;
      observations.navigations = { baseline, final: navigations };
      observations.cameraAfter = await settledOverviewCamera(overview);
      for (const endpoint of [
        '/api/overview-clocks/settings',
        '/api/overview-history/settings',
        '/api/overview-links/settings',
        '/api/routes',
        '/api/satellites',
        '/api/overview/upcoming-pois',
        '/api/status',
        '/api/overview-history',
      ])
        expect(reads[endpoint], endpoint).toBeGreaterThan(1);
      await overview.screenshot({
        path: info.outputPath(fullscreen ? 'fullscreen.png' : 'desktop.png'),
      });
    } finally {
      const path = info.outputPath('real-window-evidence.json');
      await writeFile(
        path,
        JSON.stringify(
          {
            sha,
            origin: info.project.use.baseURL,
            fixtures: false,
            timings,
            observations,
            reads,
            requestLog: log,
          },
          null,
          2
        )
      );
      await info.attach('real-window-evidence', {
        path,
        contentType: 'application/json',
      });
    }
  });
}
