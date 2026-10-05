import { writeFile } from 'node:fs/promises';
import { cpus, platform, release } from 'node:os';
import {
  expect,
  type Browser,
  type Page,
  type APIRequestContext,
  type TestInfo,
} from '@playwright/test';
import { seedSimulationRunMission } from './simulation-run-mission';
import { finishRun, renderedTrailCount } from './simulation-run-observations';
import { simulationRunSchema } from '../../../src/services/simulation-run';
import {
  installOverviewRouteProbe,
  renderedRoutePoints,
} from './overview-route-probe';
import { projectRouteArc } from '../../../src/pages/globe-route-projection';
import { ROUTE_OVERLAY_RADIUS } from '../../../src/pages/globe-render-radii';
export async function runTargetJourney(
  {
    browser,
    page,
    request,
  }: { browser: Browser; page: Page; request: APIRequestContext },
  info: TestInfo
) {
  const seed = await seedSimulationRunMission(request);
  const second = await browser.newContext({
    baseURL: process.env.SIMULATION_ACCEPTANCE_BASE_URL,
    viewport: { width: 1920, height: 1080 },
    screen: { width: 1920, height: 1080 },
    recordVideo: {
      dir: info.outputPath('second-video'),
      size: { width: 1920, height: 1080 },
    },
  });
  try {
    await second.addInitScript(() =>
      localStorage.setItem('overview.follow-aircraft', 'true')
    );
    const overview = await second.newPage();
    await installOverviewRouteProbe(overview);
    await overview.goto('/overview');
    await expect(overview.locator('canvas').first()).toBeVisible();
    await overview.evaluate(() => {
      Object.assign(window, {
        __pacedCanvas: document.querySelector('canvas'),
      });
    });
    const followBefore = await overview.evaluate(() =>
      localStorage.getItem('overview.follow-aircraft')
    );
    await page.goto(`/missions/${seed.missionId}`);
    await page.getByRole('button', { name: 'Simulate leg…' }).click();
    await page.getByLabel('Target runtime', { exact: true }).check();
    await page.getByLabel('Runtime seconds').fill('120');
    await page.getByRole('button', { name: 'Preview', exact: true }).click();
    await expect(page.getByLabel('Simulation preview')).toContainText('10×');
    const activation = page.waitForResponse(
      (response) =>
        response.url().endsWith('/activate') &&
        response.request().method() === 'POST'
    );
    await page.getByRole('button', { name: 'Start simulation' }).click();
    const started = await activation;
    expect(started.ok()).toBeTruthy();
    const startStatus = simulationRunSchema.parse(
        (await started.json()).simulation_run
      ),
      startAt = performance.now();
    await expect(overview.getByLabel('Simulation run')).toContainText(
      'Running',
      {
        timeout: 3000,
      }
    );
    const propagationMs = performance.now() - startAt;
    await expect(overview.getByLabel('Overview metric history')).toHaveCount(0);
    await expect(overview.getByText('SIMULATED TIME')).toBeVisible();
    await overview.screenshot({ path: info.outputPath('running-desktop.png') });
    await expect(page.getByLabel('Simulation run')).toContainText('Running', {
      timeout: 3000,
    });
    const missionsPropagationMs = performance.now() - startAt;
    expect(missionsPropagationMs).toBeLessThanOrEqual(3000);
    await page.screenshot({ path: info.outputPath('missions-running.png') });
    await expect(
      overview.getByLabel('Departure and arrival')
    ).not.toContainText('No active mission leg.', { timeout: 3000 });
    await second.setOffline(true);
    await expect(overview.getByLabel('Simulation run')).toContainText(
      'Refresh unavailable',
      { timeout: 3000 }
    );
    await expect(overview.getByLabel('Overview metric history')).toHaveCount(0);
    const frozen = await overview
      .locator('.operational-clock__time')
      .allTextContents();
    await overview.waitForTimeout(1500);
    expect(
      await overview.locator('.operational-clock__time').allTextContents()
    ).toEqual(frozen);
    await overview.screenshot({ path: info.outputPath('stale-running.png') });
    await second.setOffline(false);
    await expect(overview.getByLabel('Simulation run')).not.toContainText(
      'Refresh unavailable',
      { timeout: 3000 }
    );
    expect(await page.evaluate(() => document.visibilityState)).toBe('visible');
    expect(await overview.evaluate(() => document.visibilityState)).toBe(
      'visible'
    );
    const geometry = await (
      await request.get(`/api/simulation/run/${startStatus.run!.run_id}/route`)
    ).json();
    await expect
      .poll(() => renderedRoutePoints(overview))
      .toEqual(projectRouteArc(geometry.route.points, ROUTE_OVERLAY_RADIUS, 8));
    await overview.setViewportSize({ width: 390, height: 844 });
    await overview.screenshot({
      path: info.outputPath('running-responsive.png'),
    });
    await overview.setViewportSize({ width: 1920, height: 1080 });
    await overview
      .getByRole('button', { name: 'Enter fullscreen overview' })
      .click();
    await expect
      .poll(() => overview.evaluate(() => Boolean(document.fullscreenElement)))
      .toBe(true);
    await overview.screenshot({
      path: info.outputPath('running-fullscreen.png'),
    });
    const final = await finishRun(request, seed),
      completedAt = performance.now();
    await expect(overview.getByLabel('Simulation run')).toContainText(
      'Completed',
      { timeout: 3000 }
    );
    await expect(page.getByLabel('Simulation run')).toContainText('Completed', {
      timeout: 3000,
    });
    const terminalPropagationMs = performance.now() - completedAt;
    expect(terminalPropagationMs).toBeLessThanOrEqual(3000);
    await page.screenshot({ path: info.outputPath('missions-completed.png') });
    await expect(overview.getByLabel('Overview metric history')).toBeVisible();
    await expect(overview.getByText('SIMULATED TIME')).toHaveCount(0);
    expect(
      await overview.evaluate(
        () =>
          document.querySelector('canvas') ===
          (window as unknown as { __pacedCanvas: Element }).__pacedCanvas
      )
    ).toBe(true);
    expect(
      await overview.evaluate(() =>
        localStorage.getItem('overview.follow-aircraft')
      )
    ).toBe(followBefore);
    await expect
      .poll(() => renderedTrailCount(overview), { timeout: 30_000 })
      .toBeGreaterThan(1);
    await overview.screenshot({
      path: info.outputPath('restored-fullscreen.png'),
    });
    await overview.evaluate(() => document.exitFullscreen());
    await expect
      .poll(() => overview.evaluate(() => Boolean(document.fullscreenElement)))
      .toBe(false);
    await overview.screenshot({
      path: info.outputPath('restored-desktop.png'),
    });
    await writeFile(
      info.outputPath('result.json'),
      JSON.stringify(
        {
          sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
          seed,
          startStatus,
          final,
          elapsedBrowserMs: performance.now() - startAt,
          propagationMs,
          missionsPropagationMs,
          terminalPropagationMs,
          browser: browser.version(),
          os: `${platform()} ${release()}`,
          cpu: cpus()[0]?.model,
          cpuCount: cpus().length,
          gpu: await overview.evaluate(() => {
            const canvas = document.querySelector('canvas');
            const gl = canvas?.getContext('webgl2');
            const debug = gl?.getExtension('WEBGL_debug_renderer_info');
            return gl && debug
              ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)
              : 'unavailable';
          }),
        },
        null,
        2
      )
    );
    expect(final.run!.elapsed_real_seconds).toBeGreaterThanOrEqual(120);
    expect(final.run!.elapsed_real_seconds).toBeLessThanOrEqual(121);
  } finally {
    await second.close();
  }
}
