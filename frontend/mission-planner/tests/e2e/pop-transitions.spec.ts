/** Real production Nginx/API journey over CDP. No response interception. */
import { readFile, writeFile } from 'node:fs/promises';
import {
  chromium,
  expect,
  test,
  type Browser,
  type BrowserContext,
} from '@playwright/test';

import type { StatusResponse } from '../../src/services/status';
import type { SimulationRunStatus } from '../../src/services/simulation-run';

const root = process.env.POP_EVIDENCE_ROOT!;
let launched: Browser, browser: Browser, context: BrowserContext;
const recorded: unknown[] = [];
test.beforeAll(async () => {
  const port = process.env.POP_CDP_PORT!;
  launched = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', `--remote-debugging-port=${port}`],
  });
  browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
});
test.afterAll(async () => {
  await context?.close();
  await browser?.close();
  await launched?.close();
  await writeFile(
    root + '/browser-responses.json',
    JSON.stringify(recorded, null, 2)
  );
  await writeFile(
    root + '/browser-cleanup.json',
    JSON.stringify({
      contextClosed: true,
      cdpClosed: true,
      browserClosed: true,
    })
  );
});

test('planner and Overview retain source windows and position drives synthetic IP across boundary', async ({
  request,
}) => {
  const fixtures = JSON.parse(
    await readFile(root + '/source-fixtures.json', 'utf8')
  );
  const page = await context.newPage();
  page.on('response', async (response) => {
    if (response.url().includes('/api/status') && response.ok())
      recorded.push({ path: response.url(), body: await response.json() });
  });
  const crossing = fixtures.crossing;
  await page.goto(
    process.env.POP_ORIGIN +
      `/missions/${crossing.missionId}/legs/${crossing.legId}`
  );
  const panel = page.getByRole('region', {
    name: 'Starshield PoP predictions',
  });
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel('PoP transition details')).toHaveCount(1);
  await expect(panel).toContainText('Los Angeles');
  await expect(panel).toContainText('Dallas');
  await page.screenshot({
    path: root + '/planner-1920x1080.png',
    fullPage: true,
  });

  // Config reset is the ordinary route-free simulation API, with no activated route.
  const configuration = await (await request.get('/api/config')).json();
  const routeFree = [];
  for (const [latitude, longitude, city] of [
    [34.05, -118.24, 'Los Angeles'],
    [32.78, -96.8, 'Dallas'],
  ] as const) {
    const changed = await request.post('/api/config', {
      data: {
        ...configuration,
        update_interval_seconds: 0.2,
        route: {
          ...configuration.route,
          pattern: 'circular',
          radius_km: 0.001,
          latitude_start: latitude,
          longitude_start: longitude,
        },
      },
    });
    expect(changed.ok(), await changed.text()).toBeTruthy();
    let status: StatusResponse;
    await expect
      .poll(
        async () => {
          status = await (await request.get('/api/status')).json();
          return status.pop_observation?.entry?.city;
        },
        { timeout: 15_000 }
      )
      .toBe(city);
    expect(status!.pop_forecast!.transitions).toHaveLength(0);
    expect(status!.pop_observation!.source).toBe('simulation');
    routeFree.push(status);
  }
  expect(routeFree[0].pop_observation!.ip).not.toBe(
    routeFree[1].pop_observation!.ip
  );
  recorded.push({ routeFree });

  // Accelerated replay still traverses the supported captured route/mission clock.
  const base = `/api/v2/missions/${crossing.missionId}/legs/${crossing.legId}`;
  const pacing = { mode: 'target_runtime', runtime_seconds: 40 };
  const preview = await (
    await request.post(base + '/simulation/preview', { data: pacing })
  ).json();
  const activated = await request.post(base + '/activate', {
    data: { simulation: { pacing, plan_token: preview.plan_token } },
  });
  expect(activated.ok(), await activated.text()).toBeTruthy();
  await page.goto(process.env.POP_ORIGIN + '/overview');
  const overview = page.getByRole('region', {
    name: 'Starshield PoP advisories',
  });
  await expect(overview).toBeVisible();
  const samples: { status: StatusResponse; run: SimulationRunStatus }[] = [];
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const status = await (await request.get('/api/status')).json();
    const run = await (await request.get('/api/simulation/run')).json();
    samples.push({ status, run });
    if (run.state === 'completed') break;
    await page.waitForTimeout(300);
  }
  const observations = samples.map((sample) => sample.status.pop_observation);
  expect(
    new Set(observations.map((item) => item!.ip)).size
  ).toBeGreaterThanOrEqual(3);
  expect(observations.map((item) => item!.entry?.city)).toContain('Dallas');
  expect(observations.map((item) => item!.entry?.city)).toContain('Ashburn');
  expect(samples.at(-1)!.run.state).toBe('completed');
  const transitions = crossing.timeline.pop_forecast.transitions;
  for (const transition of transitions) {
    const city =
      transition.crossing.to_pop_id === 'dallas' ? 'Dallas' : 'Ashburn';
    const switched = samples.find(
      (sample) => sample.status.pop_observation?.entry?.city === city
    );
    expect(switched).toBeTruthy();
    const at = Date.parse(switched!.run.run!.simulation_time);
    expect(Math.abs(at - Date.parse(transition.crossing_utc))).toBeLessThan(
      240_000
    );
  }
  recorded.push({ replay: samples });
  await page.screenshot({ path: root + '/overview-1920x1080.png' });
  await request.post(`/api/v2/missions/${crossing.missionId}/legs/deactivate`);
});
