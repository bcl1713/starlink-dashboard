import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '@playwright/test';
const root = process.env.OPERATOR_TRAINING_PROOF_ROOT!;
const source = process.env.OPERATOR_TRAINING_TEST_SOURCE!;
if (!root.startsWith('/tmp/issue-376-training-proof-'))
  throw new Error('Explicit disposable issue376 proof root required');
function host(...args: string[]) {
  return execFileSync(
    'python3',
    [
      join(source, 'tools/training/operator-mission/launcher.py'),
      ...args,
      '--root',
      root,
    ],
    { encoding: 'utf8', timeout: 120_000 }
  );
}

test('training fixture: normal replay across two legs preserves journal, receipts, acknowledgments and Next', async ({
  page,
}) => {
  page.setDefaultTimeout(15_000);
  const initial = await (
    await page.request.get('/api/v2/operator/health')
  ).json();
  expect(initial.ready).toBe(true);
  const missions = await (await page.request.get('/api/v2/missions')).json();
  const mission = await (
    await page.request.get(`/api/v2/missions/${missions[0].id}`)
  ).json();
  expect(mission.legs).toHaveLength(2);
  expect(mission.legs[0].route_id).toBe('operator-training-leg-1');
  const id = mission.id;
  const health = async () => {
    const value = await (
      await page.request.get('/api/v2/operator/health')
    ).json();
    expect(value.store_id).toBe(initial.store_id);
    expect(value.api_epoch).toBe(initial.api_epoch);
    expect(value.simulation_run_id).toBe(initial.simulation_run_id);
    return value;
  };
  const records = async () =>
    (
      await (
        await page.request.get(`/api/v2/operator/records?mission_id=${id}`)
      ).json()
    ).items;
  const prerequisites = await records();
  expect(prerequisites).toHaveLength(8);
  expect(
    prerequisites.every(
      (item: { record: { record_type: string; version: number } }) =>
        item.record.record_type === 'call' && item.record.version === 1
    )
  ).toBe(true);
  const receipts: object[] = [];
  async function note(
    title: string,
    scope: 'preflight' | 'leg' | 'between_legs',
    leg?: string,
    beforeSave?: () => Promise<void>
  ) {
    await page.goto(`/operator?workspace=1&mission_id=${id}`);
    await page.getByRole('button', { name: 'Note', exact: true }).click();
    const editor = page.getByRole('dialog');
    await editor
      .getByRole('combobox', { name: 'Draft scope', exact: true })
      .selectOption(scope);
    if (scope === 'leg')
      await editor
        .getByRole('combobox', { name: 'Leg', exact: true })
        .selectOption(leg!);
    if (scope === 'between_legs') {
      await editor
        .getByRole('combobox', { name: 'Previous leg', exact: true })
        .selectOption(mission.legs[0].id);
      await editor
        .getByRole('combobox', { name: 'Next leg', exact: true })
        .selectOption(mission.legs[1].id);
    }
    const titleField = editor.getByLabel('Title', { exact: true });
    await titleField.fill(title);
    await titleField.focus();
    if (beforeSave) {
      await beforeSave();
      await expect(titleField).toBeFocused();
      await expect(titleField).toHaveValue(title);
    }
    const response = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().endsWith('/api/v2/operator/records'),
      { timeout: 15_000 }
    );
    await editor
      .getByRole('button', { name: 'Save entry', exact: true })
      .click();
    const saved = await response;
    expect(saved.ok()).toBe(true);
    const receipt = await saved.json();
    receipts.push(receipt);
    await expect(editor).toHaveCount(0);
    await health();
  }
  expect(mission.metadata.operator_training_fixture.namespace).toBe(
    initial.simulation_run_id
  );
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto(`/operator?workspace=1&mission_id=${id}`);
    await page.getByRole('button', { name: 'Help', exact: true }).click();
    await page
      .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
      .click();
    const guide = page.getByRole('complementary', {
      name: 'Guided mission walkthrough',
    });
    await expect(guide).toBeVisible();
    await guide.getByText('Restart and reset', { exact: true }).click();
    await guide
      .getByRole('button', { name: 'Reset guide progress', exact: true })
      .click();
    await expect(guide.getByRole('heading', { name: /T01/ })).toBeVisible();
    await guide
      .getByRole('button', { name: 'Check current evidence', exact: true })
      .click();
    await expect(
      guide.getByRole('button', { name: 'Check current evidence', exact: true })
    ).toBeEnabled();
    await expect(guide.getByText('Incomplete', { exact: true })).toBeVisible();
    await guide
      .getByRole('button', { name: 'Next lesson', exact: true })
      .click();
    await guide
      .getByRole('button', { name: 'Open lesson controls', exact: true })
      .click();
    await expect(
      page
        .getByRole('navigation', { name: 'Operator workspace' })
        .getByRole('button', { name: 'Communications', exact: true })
    ).toHaveAttribute('aria-current', 'page');
    await expect(
      guide.getByRole('button', {
        name: 'Resume guide instructions',
        exact: true,
      })
    ).toBeVisible();
    await page.screenshot({
      path: join(
        root,
        `guide-compact-${viewport.width}x${viewport.height}.png`
      ),
    });
    await guide
      .getByRole('button', { name: 'Resume guide instructions', exact: true })
      .click();
    await guide
      .getByRole('button', { name: 'Skip lesson', exact: true })
      .click();
    await guide.getByRole('button', { name: 'Back', exact: true }).click();
    await expect(guide.getByText('Skipped', { exact: true })).toBeVisible();
    await guide.getByRole('heading', { name: /T02/ }).scrollIntoViewIfNeeded();
    await page.screenshot({
      path: join(
        root,
        `guide-controls-${viewport.width}x${viewport.height}.png`
      ),
    });
    await guide
      .getByRole('button', { name: 'Dismiss guide', exact: true })
      .click();
    await expect(guide).toHaveCount(0);
  }
  await page.setViewportSize({ width: 1920, height: 1080 });
  await note('Synthetic learner preflight', 'preflight');
  const ackResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().endsWith('/events/acknowledge'),
    { timeout: 15_000 }
  );
  await page
    .getByRole('region', { name: 'Mission activity' })
    .getByRole('button', { name: 'Acknowledge', exact: true })
    .first()
    .click();
  const acknowledged = await ackResponse;
  expect(acknowledged.ok()).toBe(true);
  const ackReceipt = await acknowledged.json();
  const ackBody = acknowledged.request().postDataJSON();
  const ackHeaders = acknowledged.request().headers();
  const frozenHeaders = {
    'Idempotency-Key': ackHeaders['idempotency-key'],
    'X-Operator-Store-Epoch': ackHeaders['x-operator-store-epoch'],
  };
  async function startLeg(index: number) {
    await page.goto(`/missions/${id}`);
    await page
      .getByRole('button', { name: 'Simulate leg…', exact: true })
      .nth(index)
      .click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Multiplier', { exact: true }).fill('1');
    await dialog.getByRole('button', { name: 'Preview', exact: true }).click();
    await expect(dialog.getByLabel('Simulation preview')).toBeVisible();
    await dialog
      .getByRole('button', { name: 'Start simulation', exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    const status = await (await page.request.get('/api/simulation/run')).json();
    expect(status.run.leg_id).toBe(mission.legs[index].id);
    expect(status.run.run_id).not.toBe(initial.simulation_run_id);
    await health();
    return status;
  }
  const first = await startLeg(0);
  const display = await page.context().newPage();
  await display.setViewportSize({ width: 1920, height: 1080 });
  await display.goto('/overview');
  const metricPanels = display.getByRole('region', {
    name: 'Overview metric history',
    exact: true,
  });
  await expect(display.locator('[data-paced-running="true"]')).toBeVisible();
  await expect(metricPanels.locator('[data-metric-panel]')).toHaveCount(5);
  await expect(
    metricPanels.getByText('Unavailable', { exact: true })
  ).toHaveCount(5);
  const panelChange = await page.request.put('/api/overview-links/settings', {
    data: { latency_panel_enabled: false, uplink_panel_enabled: false },
  });
  expect(panelChange.ok()).toBe(true);
  await expect(metricPanels.locator('[data-metric-panel]')).toHaveCount(3);
  await expect(
    metricPanels.getByText('Unavailable', { exact: true })
  ).toHaveCount(3);
  await display.screenshot({
    path: join(root, 'configured-network-running.png'),
    fullPage: true,
  });
  host('checkpoint', '--stage', 'leg-one');
  await page.goto(`/operator?workspace=1&mission_id=${id}`);
  const airborne = await (await page.request.get('/api/simulation/run')).json();
  expect(airborne.run.phase).toBe('in_flight');
  const firstFeed = await (
    await page.request.get(`/api/v2/operator/events?mission_id=${id}`)
  ).json();
  writeFileSync(
    join(root, 'first-airborne-source-proof.json'),
    JSON.stringify({ initial, firstRun: first, airborne, firstFeed }, null, 2)
  );
  expect(
    firstFeed.events.some(
      (event: { provenance: string }) => event.provenance === 'modeled'
    )
  ).toBe(true);
  for (const transport of ['X', 'Ka', 'Starshield'])
    expect(
      firstFeed.events.some(
        (event: { provenance: string; transport: string }) =>
          event.provenance === 'modeled' && event.transport === transport
      )
    ).toBe(true);
  const firstModel = firstFeed.sources.find(
    (source: { source: string }) =>
      source.source === `model:${mission.legs[0].id}`
  );
  expect(firstModel).toMatchObject({ freshness: 'fresh', aligned: true });
  expect(firstModel.captured_at).toMatch(/^2026-10-17T16:15/);
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await page
    .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
    .click();
  const flightGuide = page.getByRole('complementary', {
    name: 'Guided mission walkthrough',
  });
  await flightGuide
    .getByRole('combobox', { name: 'Lesson', exact: true })
    .selectOption('T05');
  await flightGuide
    .getByRole('button', { name: 'Check current evidence', exact: true })
    .click();
  await expect(
    flightGuide.getByRole('listitem').filter({ hasText: 'first leg replay' })
  ).toContainText('Verified from current data');
  await expect(
    flightGuide
      .getByRole('listitem')
      .filter({ hasText: 'current model sources' })
  ).toContainText('Verified from current data');
  await flightGuide
    .getByRole('button', { name: 'Dismiss guide', exact: true })
    .click();
  await expect(
    page.getByRole('region', { name: 'Next requirement', exact: true })
  ).toContainText('Synthetic customer 1 briefing');
  await note(
    'Synthetic learner first leg',
    'leg',
    mission.legs[0].id,
    async () => {
      host('checkpoint', '--stage', 'leg-one-restriction');
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await expect(page.locator('.ws-next')).toContainText(
        'Synthetic customer 3 briefing'
      );
    }
  );
  await page.reload();
  const feed = await (
    await page.request.get(`/api/v2/operator/events?mission_id=${id}`)
  ).json();
  writeFileSync(
    join(root, 'overdue-source-proof.json'),
    JSON.stringify(feed, null, 2)
  );
  expect(
    feed.events.some(
      (event: { state: string; kind: string }) =>
        event.state === 'overdue' && event.kind === 'call_start'
    )
  ).toBe(true);
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    await page.setViewportSize(viewport);
    const next = page.getByRole('region', {
      name: 'Next requirement',
      exact: true,
    });
    await expect(next).toContainText('Synthetic customer 3 briefing');
    const bounds = await next.boundingBox();
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport.height);
    await page.screenshot({
      path: join(
        root,
        `airborne-next-${viewport.width}x${viewport.height}.png`
      ),
    });
  }
  await page.setViewportSize({ width: 1920, height: 1080 });
  host('checkpoint', '--stage', 'between-legs');
  await note('Synthetic learner gap', 'between_legs');
  const gap = await (await page.request.get('/api/simulation/run')).json();
  expect(gap.state).toBe('completed');
  await expect(display.locator('[data-paced-running="false"]')).toBeVisible();
  await expect(metricPanels.locator('[data-metric-panel]')).toHaveCount(3);
  const second = await startLeg(1);
  expect(second.run.run_id).not.toBe(first.run.run_id);
  await expect(display.locator('[data-paced-running="true"]')).toBeVisible();
  await expect(metricPanels.locator('[data-metric-panel]')).toHaveCount(3);
  host('checkpoint', '--stage', 'leg-two');
  await note('Synthetic learner second leg', 'leg', mission.legs[1].id);
  const secondFeed = await (
    await page.request.get(`/api/v2/operator/events?mission_id=${id}`)
  ).json();
  expect(secondFeed.as_of).toMatch(/^2026-10-17T17:05/);
  const secondModel = secondFeed.sources.find(
    (source: { source: string }) =>
      source.source === `model:${mission.legs[1].id}`
  );
  expect(secondModel).toMatchObject({ freshness: 'fresh', aligned: true });
  expect(secondModel.captured_at).toMatch(/^2026-10-17T17:05/);
  const replay = await page.request.post(
    '/api/v2/operator/events/acknowledge',
    { data: ackBody, headers: frozenHeaders }
  );
  expect(replay.ok()).toBe(true);
  expect(await replay.json()).toEqual(ackReceipt);
  const beforeRestart = await records();
  expect(beforeRestart).toHaveLength(12);
  // Use the recorded project's normal restart. Stopped replay is not reconstructed.
  host('restart');
  await expect
    .poll(async () =>
      (await page.request.get('/api/v2/operator/health')).status()
    )
    .toBe(200);
  await health();
  const afterRestart = await records();
  expect(
    afterRestart
      .map((item: { record: { record_id: string } }) => item.record.record_id)
      .sort()
  ).toEqual(
    beforeRestart
      .map((item: { record: { record_id: string } }) => item.record.record_id)
      .sort()
  );
  expect(
    (await (await page.request.get('/api/simulation/run')).json()).state
  ).toBe('idle');
  await display.reload();
  await expect(display.locator('[data-paced-running="false"]')).toBeVisible();
  await expect(metricPanels.locator('[data-metric-panel]')).toHaveCount(3);
  await expect(
    metricPanels.getByText('Unavailable', { exact: true })
  ).toHaveCount(3);
  await display.close();
  const persistedAck = await page.request.post(
    '/api/v2/operator/events/acknowledge',
    { data: ackBody, headers: frozenHeaders }
  );
  expect(persistedAck.ok()).toBe(true);
  expect(await persistedAck.json()).toEqual(ackReceipt);
  writeFileSync(
    join(root, 'training-fixture-proof.json'),
    JSON.stringify(
      {
        synthetic: true,
        initial,
        firstRun: first,
        airborne,
        firstFeed,
        overdueFeed: feed,
        gap,
        secondRun: second,
        secondFeed,
        receipts,
        acknowledgment: ackReceipt,
        recordIds: beforeRestart.map(
          (item: { record: { record_id: string } }) => item.record.record_id
        ),
        restartPreservedJournalAndAcknowledgment: true,
        stoppedReplayNotReconstructed: true,
        configuredNetworkVisibilityPreservedAcrossRunningCompletedAndRestart: true,
        syntheticNetworkReadoutsSuppressed: true,
      },
      null,
      2
    )
  );
});

test('training guide verifies a committed lost receipt before an exact retry', async ({
  page,
}) => {
  const missions = await (await page.request.get('/api/v2/missions')).json();
  const missionId = missions[0].id;
  await page.goto(`/operator?workspace=1&mission_id=${missionId}&view=notes`);
  await page.getByRole('button', { name: 'Note', exact: true }).click();
  const editor = page.getByRole('dialog');
  await editor
    .getByLabel('Title', { exact: true })
    .fill('Fictional guide lost-receipt exercise');
  const attempts: object[] = [];
  let committed: unknown = null;
  let intercepted = false;
  page.on('request', (request) => {
    if (
      request.method() === 'POST' &&
      request.url().endsWith('/api/v2/operator/records')
    )
      attempts.push({
        body: request.postDataJSON(),
        key: request.headers()['idempotency-key'],
        epoch: request.headers()['x-operator-store-epoch'],
      });
  });
  await page.route('**/api/v2/operator/records', async (route) => {
    if (route.request().method() !== 'POST' || intercepted)
      return route.continue();
    intercepted = true;
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    committed = await response.json();
    await route.abort('connectionreset');
  });
  await editor.getByRole('button', { name: 'Save entry', exact: true }).click();
  await expect(editor).toContainText(/uncertain/i);
  await editor
    .getByRole('button', { name: 'Keep draft and return', exact: true })
    .click();
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await page
    .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
    .click();
  const guide = page.getByRole('complementary', {
    name: 'Guided mission walkthrough',
  });
  await guide
    .getByRole('combobox', { name: 'Lesson', exact: true })
    .selectOption('T08');
  const outcome = guide
    .getByRole('listitem')
    .filter({ hasText: 'lost receipt same key' });
  await guide
    .getByRole('button', { name: 'Check current evidence', exact: true })
    .click();
  await expect(
    guide.getByRole('button', { name: 'Check current evidence', exact: true })
  ).toBeEnabled();
  await expect(outcome).toContainText('Needs evidence');
  await page.reload();
  await page.unroute('**/api/v2/operator/records');
  const replayed = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().endsWith('/api/v2/operator/records')
  );
  await page
    .getByRole('button', { name: 'Retry same save', exact: true })
    .click();
  const receipt = await (await replayed).json();
  expect(receipt).toEqual(committed);
  expect(attempts).toHaveLength(2);
  expect(attempts[1]).toEqual(attempts[0]);
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await page
    .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
    .click();
  await expect(guide.getByRole('heading', { name: /T08/ })).toBeVisible();
  await guide
    .getByRole('button', { name: 'Check current evidence', exact: true })
    .click();
  await expect(outcome).toContainText('Verified from current data');
  await expect(guide.getByText('Incomplete', { exact: true })).toBeVisible();
  const history = await (
    await page.request.get(
      `/api/v2/operator/records/${receipt.saved_records[0].record_id}/history`
    )
  ).json();
  expect(history.items).toHaveLength(1);
  expect(history.cursor).toBeNull();
  writeFileSync(
    join(root, 'guided-retry-proof.json'),
    JSON.stringify(
      {
        synthetic: true,
        receipt,
        attempts,
        history,
        observedBeforeRetry: true,
        resumedProgressAfterReload: true,
        wholeLessonStillIncomplete: true,
      },
      null,
      2
    )
  );
});
