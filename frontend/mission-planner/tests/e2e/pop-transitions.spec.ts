/** Production CDP journeys. The response-fixture test is explicitly synthetic. */
import { readFile, writeFile } from 'node:fs/promises';
import { verifyCrossing, verifyContinuity } from './pop-replay-evidence.mjs';
import { sampleWhileRendering } from './pop-replay-sampler.mjs';
import {
  chromium,
  expect,
  test,
  type Browser,
  type BrowserContext,
  type APIRequestContext,
} from '@playwright/test';

import type { StatusResponse } from '../../src/services/status';
import type { SimulationRunStatus } from '../../src/services/simulation-run';

const root = process.env.POP_EVIDENCE_ROOT!;
let launched: Browser, browser: Browser, context: BrowserContext;
let replayBaselines: Record<
  string,
  {
    catalogSites: { city: string; latitude: number; longitude: number }[];
    endpoint: { latitude: number; longitude: number };
    frames: {
      startUtc: string;
      endUtc: string | null;
      transportStates: Record<string, string>;
    }[];
  }
>;
function physicalAt(name: string, utc: string) {
  const at = Date.parse(utc);
  return replayBaselines[name].frames.find(
    (frame) =>
      Date.parse(frame.startUtc) <= at &&
      (!frame.endUtc || at < Date.parse(frame.endUtc))
  )!.transportStates;
}
const activatedLegs = new Set<string>();
async function deactivateOwned(request: APIRequestContext) {
  for (const missionId of activatedLegs)
    await request.post(`/api/v2/missions/${missionId}/legs/deactivate`);
  activatedLegs.clear();
}
test.afterEach(async ({ request }) => {
  await deactivateOwned(request);
});
const recorded: unknown[] = [];
test.beforeAll(async () => {
  replayBaselines = JSON.parse(
    await readFile(root + '/physical-replay-baselines.json', 'utf8')
  ).cases;
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
    root + `/browser-responses-${process.pid}.json`,
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
  await expect(panel.locator('[data-pop-track] button')).toHaveCount(2);
  await expect(panel.locator('[data-pop-track] button').first()).toHaveText('');
  await panel.scrollIntoViewIfNeeded();
  await page.screenshot({ path: root + '/planner-visible-1920x1080.png' });
  await panel.screenshot({ path: root + '/planner-markers-details.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  await panel.getByLabel('PoP transition details').selectOption({ index: 1 });
  await expect(panel).toContainText('Ashburn');
  await panel.scrollIntoViewIfNeeded();
  await page.screenshot({ path: root + '/planner-mobile-selector.png' });
  await page.setViewportSize({ width: 1920, height: 1080 });

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
  test.setTimeout(400_000);
  const pacing = { mode: 'target_runtime', runtime_seconds: 300 };
  const preview = await (
    await request.post(base + '/simulation/preview', { data: pacing })
  ).json();
  const activated = await request.post(base + '/activate', {
    data: { simulation: { pacing, plan_token: preview.plan_token } },
  });
  expect(activated.ok(), await activated.text()).toBeTruthy();
  activatedLegs.add(crossing.missionId);
  let activeCaptured = false;
  const samples: {
    status: StatusResponse;
    run: SimulationRunStatus;
    runBefore: SimulationRunStatus;
  }[] = [];
  const receipt = {};
  recorded.push({ actualNormalReplay: samples, normalReplaySampler: receipt });
  try {
    await sampleWhileRendering({
      samples,
      receipt,
      read: async () => {
        const runBefore = await (
          await request.get('/api/simulation/run')
        ).json();
        const status = await (await request.get('/api/status')).json();
        const run = await (await request.get('/api/simulation/run')).json();
        return { status, run, runBefore };
      },
      validate: (sample: (typeof samples)[number]) => {
        expect(sample.run.run!.transport_states).toEqual(
          physicalAt('crossing', sample.run.run!.simulation_time)
        );
      },
      isComplete: (sample: (typeof samples)[number]) =>
        sample.run.state === 'completed',
      render: async (state: {
        samples: typeof samples;
        ended: boolean;
        error?: unknown;
      }) => {
        await page.goto(process.env.POP_ORIGIN + '/overview');
        const overview = page.getByRole('region', {
          name: 'Starshield PoP advisories',
        });
        await expect(overview).toBeVisible();
        await expect(
          overview.getByLabel('PoP transition details')
        ).toBeVisible();
        await page.screenshot({
          path: root + '/overview-upcoming-1920x1080.png',
        });
        while (!state.ended) {
          if (
            state.samples
              .at(-1)
              ?.status.pop_advisories?.some((item) => item.kind === 'window')
          ) {
            await expect(overview.getByRole('status')).toContainText(
              'Starshield PoP transition possible'
            );
            await overview.scrollIntoViewIfNeeded();
            await expect(
              overview.locator('[data-pop-track] button')
            ).toHaveCount(2);
            await overview.screenshot({
              path: root + '/overview-active-markers-details.png',
            });
            await expect(overview.getByRole('status')).toContainText(
              'Starshield PoP transition possible'
            );
            activeCaptured = true;
            break;
          }
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        if (state.error) throw state.error;
      },
    });
  } finally {
    await writeFile(
      root + '/normal-replay-sampler.json',
      JSON.stringify(receipt, null, 2)
    );
  }
  expect(activeCaptured).toBeTruthy();
  const observations = samples.map((sample) => sample.status.pop_observation);
  expect(
    new Set(observations.map((item) => item!.ip)).size
  ).toBeGreaterThanOrEqual(3);
  expect(observations.map((item) => item!.entry?.city)).toContain('Dallas');
  expect(observations.map((item) => item!.entry?.city)).toContain('Ashburn');
  expect(samples.at(-1)!.run.state).toBe('completed');
  const transitions = crossing.timeline.pop_forecast.transitions;
  for (const transition of transitions) {
    recorded.push({
      normalCrossingBracket: verifyCrossing(
        samples,
        transition,
        replayBaselines.crossing.catalogSites
      ),
    });
  }
  recorded.push({ replay: samples });
  await page.screenshot({ path: root + '/overview-1920x1080.png' });
  await request.post(`/api/v2/missions/${crossing.missionId}/legs/deactivate`);
  await page.close();
});

test('explicit synthetic response fixtures render early, late and mismatch evaluator results', async ({
  request,
}) => {
  const fixtures = JSON.parse(
    await readFile(root + '/provider-fixtures.json', 'utf8')
  );
  const baseline = await (await request.get('/api/status')).json();
  const page = await context.newPage();
  for (const name of ['early', 'late', 'mismatch']) {
    const fixture = fixtures.cases[name];
    const payload = {
      ...baseline,
      timestamp: new Date().toISOString(),
      pop_forecast: fixtures.forecast,
      pop_observation: fixture.observation,
      pop_advisories: fixture.advisories,
    };
    await page.route('**/api/status', (route) =>
      route.fulfill({ json: payload })
    );
    await page.goto(process.env.POP_ORIGIN + '/overview', {
      waitUntil: 'domcontentloaded',
    });
    const panel = page.getByRole('region', {
      name: 'Starshield PoP advisories',
    });
    await expect(panel).toContainText(
      'Observed PoP: ' + fixture.observation.entry.city
    );
    if (name === 'early')
      await expect(panel.getByRole('status')).toHaveCount(0);
    if (name === 'late')
      await expect(panel).toContainText('Overdue PoP transition');
    if (name === 'mismatch')
      await expect(panel).toContainText('A transition is possible at any time');
    await page.screenshot({
      path: root + `/synthetic-response-${name}-1920x1080.png`,
    });
    recorded.push({
      fixtureKind:
        'explicit page.route response fixture against shipped frontend; evaluator output from actual image; not backend HTTP observation proof',
      name,
      payload,
    });
    await page.unroute('**/api/status');
  }
  await page.close();
});

test('actual dateline replay changes Tokyo IP to Los Angeles without an availability change', async ({
  request,
}) => {
  const fixtures = JSON.parse(
    await readFile(root + '/source-fixtures.json', 'utf8')
  );
  const fixture = fixtures.dateline;
  const base = `/api/v2/missions/${fixture.missionId}/legs/${fixture.legId}`;
  const pacing = { mode: 'target_runtime', runtime_seconds: 20 };
  const preview = await (
    await request.post(base + '/simulation/preview', { data: pacing })
  ).json();
  const activated = await request.post(base + '/activate', {
    data: { simulation: { pacing, plan_token: preview.plan_token } },
  });
  expect(activated.ok(), await activated.text()).toBeTruthy();
  activatedLegs.add(fixture.missionId);
  const samples = [];
  recorded.push({ actualReplaySamples: samples });
  const deadline = Date.now() + 35_000;
  while (Date.now() < deadline) {
    const runBefore = await (await request.get('/api/simulation/run')).json();
    const status = await (await request.get('/api/status')).json();
    const run = await (await request.get('/api/simulation/run')).json();
    samples.push({ status, run, runBefore });
    expect(run.run.transport_states).toEqual(
      physicalAt('dateline', run.run.simulation_time)
    );
    if (run.state === 'completed') break;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  expect(samples.at(-1)!.run.state).toBe('completed');
  const cities = samples.map((item) => item.status.pop_observation.entry.city);
  expect(cities).toContain('Tokyo');
  expect(cities).toContain('Los Angeles');
  expect(
    new Set(samples.map((item) => item.status.pop_observation.ip)).size
  ).toBe(2);
  recorded.push({
    datelineCrossingBracket: verifyCrossing(
      samples,
      fixture.timeline.pop_forecast.transitions[0],
      replayBaselines.dateline.catalogSites
    ),
  });
  recorded.push({ actualDatelineReplay: samples });
  await request.post(`/api/v2/missions/${fixture.missionId}/legs/deactivate`);
});

test('captured conditional missions preserve call bounds, preference and physical replay', async ({
  request,
}) => {
  const fixtures = JSON.parse(
    await readFile(root + '/source-fixtures.json', 'utf8')
  );
  const page = await context.newPage();
  for (const [name, seconds, classification] of [
    ['sole', 600, 'planned_outage'],
    ['ka-alternative', 0, 'advisory'],
    ['x-fallback', 0, 'x_fallback'],
    ['concurrency-hard', 600, 'planned_outage'],
    ['partial-ka', 300, 'planned_outage'],
    ['unknown', 0, 'unknown'],
  ] as const) {
    const fixture = fixtures[name];
    const timeline = fixture.timeline;
    expect(timeline.call_continuity.pop_call_outage_seconds).toBeCloseTo(
      seconds,
      3
    );
    expect(
      timeline.call_continuity.intervals.some(
        (span: { classification: string }) =>
          span.classification === classification
      )
    ).toBeTruthy();
    await page.goto(
      process.env.POP_ORIGIN +
        `/missions/${fixture.missionId}/legs/${fixture.legId}`
    );
    const panel = page.getByRole('region', {
      name: 'Starshield PoP predictions',
    });
    await expect(panel).toBeVisible();
    await expect(panel.locator('[data-pop-track] button')).toHaveCount(1);
    await expect(panel.locator('[data-pop-track] button')).toHaveText('');
    await expect(panel).toContainText(
      name === 'unknown'
        ? 'Call continuity unresolved'
        : `PoP contribution: ${seconds}s`
    );
    if (name === 'x-fallback')
      await expect(panel).toContainText('activation is not automatic');
    if (name === 'partial-ka') {
      await expect(panel).toContainText('Planned communications outage');
      await expect(panel).toContainText('Transition advisory');
    }
    await panel.scrollIntoViewIfNeeded();
    await panel.screenshot({ path: root + `/conditional-${name}-planner.png` });
  }
  const fixture = fixtures['x-fallback'];
  const base = `/api/v2/missions/${fixture.missionId}/legs/${fixture.legId}`;
  const pacing = { mode: 'target_runtime', runtime_seconds: 20 };
  const preview = await (
    await request.post(base + '/simulation/preview', { data: pacing })
  ).json();
  const activation = await request.post(base + '/activate', {
    data: { simulation: { pacing, plan_token: preview.plan_token } },
  });
  expect(activation.ok(), await activation.text()).toBeTruthy();
  activatedLegs.add(fixture.missionId);
  const samples = [];
  recorded.push({ actualReplaySamples: samples });
  const deadline = Date.now() + 35_000;
  while (Date.now() < deadline) {
    const runBefore = await (await request.get('/api/simulation/run')).json();
    const status = await (await request.get('/api/status')).json();
    const run = await (await request.get('/api/simulation/run')).json();
    samples.push({ status, run, runBefore });
    expect(run.run.transport_states).toEqual(
      physicalAt('x-fallback', run.run.simulation_time)
    );
    verifyContinuity({ status, run }, replayBaselines['x-fallback'].endpoint);
    if (run.state === 'completed') break;
    await page.waitForTimeout(200);
  }
  expect(samples.at(-1)!.run.state).toBe('completed');
  expect(
    samples.some((sample) =>
      sample.status.call_continuity?.intervals.some(
        (span: { classification: string }) =>
          span.classification === 'x_fallback'
      )
    )
  ).toBeTruthy();
  const after = await (
    await request.get(`/api/v2/missions/${fixture.missionId}`)
  ).json();
  expect(after.legs[0].transports).toEqual(fixture.capturedLeg.transports);
  recorded.push({
    capturedPreferenceReplay: samples,
    fixtureKind:
      'actual unmocked planning-policy replay; no automatic activation',
  });
  await request.post(`/api/v2/missions/${fixture.missionId}/legs/deactivate`);
  await page.close();
});
