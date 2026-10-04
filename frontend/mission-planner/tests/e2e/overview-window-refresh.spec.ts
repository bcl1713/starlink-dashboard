import { writeFile } from 'node:fs/promises';
import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { ROUTE_OVERLAY_RADIUS } from '../../src/pages/globe-render-radii';
import { projectRouteArc } from '../../src/pages/globe-route-projection';
import {
  observeOverviewCamera,
  settledOverviewCamera,
  expectSameCamera,
} from './support/overview-camera';
import {
  fixtureRoutes,
  installOverviewWindowFixture,
  renderedWindowRoute,
  retainedHistoryTimes,
  historyWindowState,
} from './support/overview-window-fixture';

test.use({ viewport: { width: 1920, height: 1080 } });
async function explore(page: Page) {
  const automatic = await settledOverviewCamera(page);
  const toggle = page.getByRole('button', { name: 'Explore map', exact: true });
  const gated = await toggle.isVisible();
  if (gated) await toggle.click();
  const box = (await page.locator('.overview-globe canvas').boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.6);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5, {
    steps: 10,
  });
  await page.mouse.up();
  const manual = await settledOverviewCamera(page);
  expect(manual.position).not.toEqual(automatic.position);
  if (gated) await page.keyboard.press('Escape');
  return manual;
}
async function attach(
  testInfo: TestInfo,
  fixture: Awaited<ReturnType<typeof installOverviewWindowFixture>>,
  timings: Record<string, number>
) {
  const path = testInfo.outputPath('controlled-window-evidence.json');
  await writeFile(
    path,
    JSON.stringify(
      {
        timings,
        requestLog: fixture.requestLog,
        readCounts: fixture.readCounts,
      },
      null,
      2
    )
  );
  await testInfo.attach('controlled-window-evidence.json', {
    path,
    contentType: 'application/json',
  });
}

for (const fullscreen of [false, true]) {
  test(`saved clock label/timezone reaches ${fullscreen ? 'fullscreen' : 'ordinary'} Overview without focus, remount or draft loss`, async ({
    context,
  }, testInfo) => {
    const fixture = await installOverviewWindowFixture(context);
    const timings: Record<string, number> = {};
    try {
      const overview = await context.newPage();
      await observeOverviewCamera(overview);
      let navigations = 0;
      overview.on('framenavigated', (frame) => {
        if (frame === overview.mainFrame()) navigations++;
      });
      await overview.goto('/overview');
      await expect(
        overview.getByRole('region', {
          name: 'Omaha, NE operational clock',
          exact: true,
        })
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
      const initialNavigations = navigations;
      const canvas = await overview
        .locator('.overview-globe canvas')
        .elementHandle();
      const plots = await overview.locator('.uplot').elementHandles();
      expect(plots).toHaveLength(5);
      await expect
        .poll(() => retainedHistoryTimes(overview))
        .toContain(fixture.marker);
      const initialReads = fixture.requestLog.filter(
        (entry) =>
          entry.page.includes('/overview') &&
          entry.endpoint === '/api/overview-history'
      ).length;
      const draft = await context.newPage();
      await draft.goto('/configuration');
      await draft
        .getByLabel('Clock 3 label')
        .fill('Unsubmitted operator draft');
      const editing = await context.newPage();
      await editing.goto('/configuration');
      await editing.bringToFront();
      // A rejected draft must never replace confirmed clocks in either view.
      const endpoint = '/api/overview-clocks/settings';
      fixture.failNext(endpoint, 'PUT');
      await editing.getByLabel('Clock 3 label').fill('Rejected clock draft');
      const rejected = editing.waitForResponse(
        (r) => r.url().endsWith(endpoint) && r.request().method() === 'PUT'
      );
      await editing
        .getByRole('button', { name: 'Save operational clocks' })
        .click();
      expect((await rejected).status()).toBe(503);
      await expect(editing.getByRole('alert')).toContainText('Unable to save');
      expect(fixture.state.clocks.clocks[2].label).toBe('Omaha, NE');
      await expect(
        overview.getByRole('region', {
          name: 'Omaha, NE operational clock',
          exact: true,
        })
      ).toBeVisible();
      // Interrupt the next Overview read while leaving the editor focused.
      fixture.interruptNext(endpoint);
      await expect
        .poll(
          () =>
            fixture.requestLog.some(
              (entry) =>
                entry.endpoint === endpoint &&
                entry.aborted &&
                entry.page.includes('/overview')
            ),
          { timeout: 8000 }
        )
        .toBe(true);
      // The existing error UI hides clocks while the confirmed cache is retained.
      await expect(
        overview.getByRole('alert', { name: 'Operational clocks', exact: true })
      ).toContainText('Operational clocks unavailable');
      await expect(
        overview.getByRole('region', {
          name: 'Rejected clock draft operational clock',
          exact: true,
        })
      ).toHaveCount(0);
      expect(await retainedHistoryTimes(overview)).toContain(fixture.marker);
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
      const response = await saved;
      expect(response.status()).toBe(200);
      const savedAt = Date.now();
      const clock = overview.getByRole('region', {
        name: 'Honolulu operations operational clock',
        exact: true,
      });
      await expect(clock).toBeVisible({ timeout: 8000 });
      timings.clockResponseToVisibleMs = Date.now() - savedAt;
      expect(timings.clockResponseToVisibleMs).toBeLessThanOrEqual(8000);
      // Fixed observed timestamp from the time element avoids a ticking-clock race.
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
      await expect(draft.getByLabel('Clock 3 label')).toHaveValue(
        'Unsubmitted operator draft'
      );
      expectSameCamera(manual, await settledOverviewCamera(overview));
      expect(
        await canvas!.evaluate(
          (node) => node === document.querySelector('.overview-globe canvas')
        )
      ).toBe(true);
      for (let i = 0; i < plots.length; i++)
        expect(
          await plots[i].evaluate(
            (node, index) =>
              node === document.querySelectorAll('.uplot')[index],
            i
          )
        ).toBe(true);
      await expect
        .poll(
          () =>
            fixture.requestLog.filter(
              (entry) =>
                entry.page.includes('/overview') &&
                entry.endpoint === '/api/overview-history'
            ).length,
          { timeout: 8000 }
        )
        .toBeGreaterThan(initialReads);
      expect(await retainedHistoryTimes(overview)).toContain(fixture.marker);
      expect(navigations).toBe(initialNavigations);
      // Native fullscreen remains an observed state throughout the refresh.
      const fullscreenAtEnd = await overview.evaluate(
        () => !!document.fullscreenElement
      );
      expect(fullscreenAtEnd).toBe(fullscreen);
      timings.fullscreenAtEnd = Number(fullscreenAtEnd);
      await overview.screenshot({
        path: testInfo.outputPath('refreshed-overview.png'),
      });
    } finally {
      await attach(testInfo, fixture, timings);
    }
  });
}

test('mission activation, switching and deactivation converge route geometry and generated POIs while editing stays foreground', async ({
  context,
}, testInfo) => {
  const fixture = await installOverviewWindowFixture(context);
  const timings: Record<string, number> = {};
  try {
    const overview = await context.newPage();
    await observeOverviewCamera(overview);
    let navigations = 0;
    overview.on('framenavigated', (frame) => {
      if (frame === overview.mainFrame()) navigations++;
    });
    await overview.goto('/overview');
    await expect(
      overview.getByText('No active route.', { exact: true })
    ).toBeVisible({ timeout: 20000 });
    const manual = await explore(overview);
    const initialNavigations = navigations;
    const canvas = await overview
      .locator('.overview-globe canvas')
      .elementHandle();
    const editing = await context.newPage();
    await editing.goto('/missions/window-mission');
    await editing.bringToFront();
    for (const [index, leg] of ['leg-a', 'leg-b'].entries()) {
      const endpoint = `/api/v2/missions/window-mission/legs/${leg}/activate`;
      const saved = editing.waitForResponse(
        (r) => r.url().endsWith(endpoint) && r.request().method() === 'POST'
      );
      await editing
        .getByRole('button', { name: 'Activate', exact: true })
        .nth(0)
        .click();
      expect((await saved).status()).toBe(200);
      const savedAt = Date.now();
      await expect
        .poll(() => renderedWindowRoute(overview), { timeout: 8000 })
        .toEqual(
          projectRouteArc(fixtureRoutes[index].points, ROUTE_OVERLAY_RADIUS, 8)
        );
      await expect(overview.getByLabel('Map POIs')).toContainText(
        index === 0 ? 'KBBB' : 'KDDD',
        { timeout: Math.max(1, 8000 - (Date.now() - savedAt)) }
      );
      timings[leg] = Date.now() - savedAt;
      expect(timings[leg]).toBeLessThanOrEqual(8000);
      expectSameCamera(manual, await settledOverviewCamera(overview));
    }
    editing.once('dialog', (dialog) => dialog.accept());
    const deactivated = editing.waitForResponse(
      (r) =>
        r.url().endsWith('/legs/deactivate') && r.request().method() === 'POST'
    );
    await editing
      .getByRole('button', { name: 'Deactivate All', exact: true })
      .click();
    expect((await deactivated).status()).toBe(200);
    const savedAt = Date.now();
    await expect(
      overview.getByText('No active route.', { exact: true })
    ).toBeVisible({ timeout: 8000 });
    await expect(overview.getByLabel('Map POIs').locator('li')).toHaveCount(0, {
      timeout: Math.max(1, 8000 - (Date.now() - savedAt)),
    });
    expect(await renderedWindowRoute(overview)).toEqual([]);
    timings.deactivation = Date.now() - savedAt;
    expect(timings.deactivation).toBeLessThanOrEqual(8000);
    expectSameCamera(manual, await settledOverviewCamera(overview));
    expect(
      await canvas!.evaluate(
        (node) => node === document.querySelector('.overview-globe canvas')
      )
    ).toBe(true);
    expect(navigations).toBe(initialNavigations);
  } finally {
    await attach(testInfo, fixture, timings);
  }
});

test('history rejects a delayed old-window bundle, then recovers and retains samples after a failed window save', async ({
  context,
}, testInfo) => {
  const fixture = await installOverviewWindowFixture(context);
  const timings: Record<string, number> = {};
  let release: (() => void) | undefined;
  try {
    const overview = await context.newPage();
    await overview.goto('/overview');
    await expect
      .poll(() => retainedHistoryTimes(overview))
      .toContain(fixture.marker);
    const editing = await context.newPage();
    await editing.goto('/configuration');
    await editing.bringToFront();
    release = fixture.holdNext('/api/overview-history', 'GET', '/overview');
    await expect
      .poll(
        () =>
          fixture.requestLog.some(
            (entry) =>
              entry.endpoint === '/api/overview-history' &&
              entry.page.includes('/overview') &&
              entry.held
          ),
        { timeout: 8000 }
      )
      .toBe(true);
    const held = fixture.requestLog.find(
      (entry) =>
        entry.endpoint === '/api/overview-history' &&
        entry.page.includes('/overview') &&
        entry.held
    )!;
    const saved = editing.waitForResponse(
      (r) =>
        r.url().endsWith('/api/overview-history/settings') &&
        r.request().method() === 'PUT'
    );
    await editing.getByLabel('Overview history window').selectOption('900');
    expect((await saved).status()).toBe(200);
    const savedAt = Date.now();
    await expect
      .poll(() => historyWindowState(overview), { timeout: 8000 })
      .toEqual({ selected: 900, bundle: 300 });
    timings.historySettingsResponseToSelectedMs = Date.now() - savedAt;
    const panel = overview.getByRole('region', {
      name: 'Network latency history',
    });
    await expect(panel.getByRole('status')).toHaveText('Waiting for history');
    await expect(panel.locator('.uplot')).toHaveCount(0);
    const obsoleteArrived = overview.waitForResponse((r) =>
      r.url().endsWith('/api/overview-history')
    );
    release();
    release = undefined;
    await obsoleteArrived;
    expect((held.response as { window_seconds: number }).window_seconds).toBe(
      300
    );
    await expect(panel.getByRole('status')).toHaveText('Waiting for history');
    await expect(panel.locator('.uplot')).toHaveCount(0);
    await expect
      .poll(() => historyWindowState(overview), { timeout: 8000 })
      .toEqual({ selected: 900, bundle: 900 });
    await expect
      .poll(() => retainedHistoryTimes(overview))
      .toContain(fixture.marker);
    const plot = await panel.locator('.uplot').elementHandle();
    fixture.failNext('/api/overview-history/settings', 'PUT');
    const rejected = editing.waitForResponse(
      (r) =>
        r.url().endsWith('/api/overview-history/settings') &&
        r.request().method() === 'PUT'
    );
    await editing.getByLabel('Overview history window').selectOption('3600');
    expect((await rejected).status()).toBe(503);
    await expect(editing.getByRole('alert')).toContainText(
      'Unable to save Overview history window'
    );
    await expect(editing.getByLabel('Overview history window')).toHaveValue(
      '900'
    );
    expect(await historyWindowState(overview)).toEqual({
      selected: 900,
      bundle: 900,
    });
    expect(await retainedHistoryTimes(overview)).toContain(fixture.marker);
    expect(
      await plot!.evaluate(
        (node) =>
          node ===
          document.querySelector(
            '[aria-label="Network latency history"] .uplot'
          )
      )
    ).toBe(true);
    await overview.screenshot({
      path: testInfo.outputPath('history-recovered.png'),
    });
  } finally {
    release?.();
    await attach(testInfo, fixture, timings);
  }
});
