import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '@playwright/test';
import { control } from './operator-journal-helpers';

const evidence = process.env.OPERATOR_ACCEPTANCE_EVIDENCE!;
const fixtures = JSON.parse(
  readFileSync(process.env.OPERATOR_WORKSPACE_INPUTS!, 'utf8')
) as { seed: string; mission: { id: string } }[];
const viewports = [
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
  { width: 844, height: 390 },
];

test('baseline: normal and busy production journeys at three sizes', async ({
  browser,
}) => {
  const measurements: object[] = [];
  for (const fixture of fixtures) {
    for (const viewport of viewports) {
      const context = await browser.newContext({ viewport, timezoneId: 'UTC' });
      try {
        const page = await context.newPage();
        await page.goto(`/operator?mission_id=${fixture.mission.id}`);
        await expect(
          page.getByRole('heading', { name: 'Operator journal', exact: true })
        ).toBeVisible();
        const communication = page.getByRole('region', {
          name: 'Communications',
          exact: true,
        });
        await expect(
          communication.getByRole('heading', {
            name: 'Synthetic customer 1',
            exact: true,
          })
        ).toBeVisible();
        await page.screenshot({
          path: join(
            evidence,
            `${fixture.seed}-${viewport.width}x${viewport.height}-operator.png`
          ),
          fullPage: true,
        });
        const started = performance.now();
        await communication
          .getByRole('button', { name: 'Schedule call', exact: true })
          .click();
        const editor = page.getByRole('form', { name: 'Call editor' });
        await expect(editor).toBeVisible();
        measurements.push({
          scenario: fixture.seed,
          viewport,
          journey: 'Open scheduled call editor',
          activations: 1,
          typingOperations: 0,
          selectorOperations: 0,
          elapsedMs: performance.now() - started,
          misSelections: 0,
          recoveryActions: 0,
          measurement:
            'scripted browser interaction; not human usability timing',
        });
        for (const [name, path] of [
          ['overview', '/overview'],
          ['configuration', '/configuration'],
        ] as const) {
          await page.goto(path);
          if (name === 'overview')
            await expect(page.locator('main')).toBeVisible();
          else
            await expect(
              page.getByRole('heading', { name: 'Configuration', exact: true })
            ).toBeVisible();
          await page.screenshot({
            path: join(
              evidence,
              `${fixture.seed}-${viewport.width}x${viewport.height}-${name}.png`
            ),
            fullPage: true,
          });
        }
      } finally {
        await context.close();
      }
    }
  }
  writeFileSync(
    join(evidence, 'workspace-baseline.json'),
    JSON.stringify({ synthetic: true, measurements }, null, 2)
  );
});

test('approved workspace: mission awareness and contextual actions', async ({
  page,
}) => {
  await page.goto(`/operator?mission_id=${fixtures[0].mission.id}`);
  // Establish service and legacy-page readiness before testing the new destination.
  await expect
    .poll(async () =>
      (await page.request.get('/api/v2/operator/health')).status()
    )
    .toBe(200);
  await expect(
    page.getByRole('region', { name: 'Communications', exact: true })
  ).toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Operator workspace' })
  ).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Now and next' })
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Create call', exact: true })
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Create conference', exact: true })
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Help', exact: true })
  ).toBeVisible();
});

test('hidden workspace: normal and busy layouts, real call save and parked notes', async ({
  browser,
}) => {
  const captures: string[] = [];
  for (const fixture of fixtures) {
    for (const viewport of viewports) {
      const context = await browser.newContext({
        viewport,
        timezoneId: 'Pacific/Honolulu',
      });
      try {
        const page = await context.newPage();
        await page.goto(
          `/operator?workspace=1&mission_id=${fixture.mission.id}`
        );
        await expect(
          page.getByRole('navigation', { name: 'Operator workspace' })
        ).toBeVisible();
        await expect(
          page
            .getByRole('region', { name: 'Next requirement' })
            .getByText('Synthetic customer 1 briefing', {
              exact: true,
            })
        ).toBeVisible();
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth
          )
        ).toBe(true);
        const layout = await page.evaluate(() => {
          const next = document
            .querySelector('.ws-next')!
            .getBoundingClientRect();
          const awareness = document
            .querySelector('.ws-awareness')!
            .getBoundingClientRect();
          const body = document
            .querySelector('.ws-body')!
            .getBoundingClientRect();
          return {
            nextBottom: next.bottom,
            awarenessBottom: awareness.bottom,
            bodyHeight: body.height,
          };
        });
        expect(layout.nextBottom).toBeLessThanOrEqual(
          layout.awarenessBottom + 1
        );
        expect(layout.bodyHeight).toBeGreaterThanOrEqual(120);
        const capture = `${fixture.seed}-${viewport.width}x${viewport.height}-workspace.png`;
        await page.screenshot({ path: join(evidence, capture) });
        captures.push(capture);
        await page
          .getByRole('button', { name: 'Create call', exact: true })
          .click();
        const dialog = page.getByRole('dialog');
        const party = dialog.getByLabel('Party / participant (optional)');
        const name = `Synthetic ${fixture.seed} ${viewport.width} customer with a long descriptive label`;
        await party.fill(name);
        await dialog
          .getByRole('button', { name: 'Save call', exact: true })
          .click();
        await expect(dialog.getByRole('alert')).toContainText(
          'Scheduled calls require a planned start'
        );
        await dialog
          .getByLabel('Planned start (UTC)', { exact: true })
          .fill('2026-10-17T17:00:00Z');
        await party.focus();
        await page.evaluate(() => window.dispatchEvent(new Event('focus')));
        await expect(party).toBeFocused();
        if (viewport.width === 844) {
          await page.setViewportSize({ width: 844, height: 250 });
          await expect(party).toHaveValue(name);
          expect(
            await dialog.evaluate(
              (element) => element.scrollWidth <= innerWidth
            )
          ).toBe(true);
          await page.setViewportSize(viewport);
        }
        const response = page.waitForResponse(
          (response) =>
            response.request().method() === 'POST' &&
            response.url().includes('/api/v2/operator/records')
        );
        await dialog
          .getByRole('button', { name: 'Save call', exact: true })
          .click();
        const saved = await response;
        expect(saved.ok()).toBe(true);
        const receipt = await saved.json();
        expect(receipt.saved_records[0].payload.party).toBe(name);
        await expect(dialog).toHaveCount(0);
        await page.getByRole('button', { name: 'Note', exact: true }).click();
        await page
          .getByLabel('Title', { exact: true })
          .fill(`Parked ${fixture.seed} ${viewport.width}`);
        await page
          .getByRole('button', { name: 'Keep draft and return' })
          .click();
        await expect(
          page
            .getByRole('region', { name: 'Retained drafts' })
            .getByRole('button', {
              name: new RegExp(`Parked ${fixture.seed} ${viewport.width}`),
            })
        ).toBeVisible();
        const sizes = await page
          .locator('.operator-workspace button:visible')
          .evaluateAll((buttons) =>
            buttons.map((button) => ({
              name: button.textContent,
              width: button.getBoundingClientRect().width,
              height: button.getBoundingClientRect().height,
            }))
          );
        expect(
          sizes.filter((size) => size.width < 44 || size.height < 44)
        ).toEqual([]);
      } finally {
        await context.close();
      }
    }
  }
  writeFileSync(
    join(evidence, 'workspace-candidate.json'),
    JSON.stringify(
      {
        synthetic: true,
        captures,
        realCallReceipts: 6,
        parkedNotes: 6,
        inlineValidation: true,
        viewportResize: true,
        targets44: true,
      },
      null,
      2
    )
  );
});

test('fresh install: explicit simulation journal setup and real CRUD without model inputs', async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  try {
    const page = await context.newPage();
    await page.goto('/missions');
    const missing = await page.request.get('/api/v2/operator/health');
    expect(missing.status()).toBe(503);
    const before = await missing.json();
    expect(before.store_id).toBeNull();
    expect(before.error_code).toBe('store_initialization_required');
    expect(before.source_mode).toBe('simulation');
    await page
      .getByRole('button', { name: 'Create New Mission', exact: true })
      .click();
    const create = page.getByRole('dialog');
    await create.getByLabel('Mission Name').fill('Synthetic fresh mission');
    await create
      .getByRole('button', { name: 'Create Mission', exact: true })
      .click();
    await expect(page).toHaveURL(/\/missions\/synthetic-fresh-mission$/);
    const missionId = 'synthetic-fresh-mission';
    await page.goto(`/operator?mission_id=${missionId}`);
    const setup = page.getByRole('region', { name: 'Operator store setup' });
    await expect(
      setup.getByRole('button', { name: 'Initialize simulation journal' })
    ).toBeVisible();
    await page.screenshot({
      path: join(evidence, 'fresh-install-setup.png'),
      fullPage: true,
    });
    await setup
      .getByRole('button', { name: 'Initialize simulation journal' })
      .click();
    await expect(setup).toHaveCount(0);
    const initialized = await (
      await page.request.get('/api/v2/operator/health')
    ).json();
    expect(initialized.ready).toBe(true);
    const receipts: object[] = [];
    async function save(button: string) {
      const response = page.waitForResponse(
        (response) =>
          response.request().method() === 'POST' &&
          response.url().endsWith('/api/v2/operator/records')
      );
      await page.getByRole('button', { name: button, exact: true }).click();
      const result = await response;
      expect(result.ok()).toBe(true);
      const receipt = await result.json();
      receipts.push(receipt);
      return receipt.saved_records[0];
    }
    async function crud(prefix: string) {
      const ids: string[] = [];
      const communications = page.getByRole('region', {
        name: 'Communications',
        exact: true,
      });
      await expect(
        communications.getByRole('button', {
          name: 'Schedule call',
          exact: true,
        })
      ).toBeEnabled();
      await communications
        .getByRole('button', { name: 'Schedule call', exact: true })
        .click();
      await page
        .getByLabel('Party / participant (optional)')
        .fill(`${prefix} call`);
      await page
        .getByLabel('Planned start (UTC)', { exact: true })
        .fill(
          new Date(Date.now() + 3_600_000).toISOString().slice(0, 19) + 'Z'
        );
      ids.push((await save('Save call')).record_id);
      await communications
        .locator('summary')
        .filter({ hasText: 'Conferences and customers' })
        .click();
      await page
        .getByRole('button', { name: 'New conference', exact: true })
        .click();
      await page
        .getByLabel('Conference name (optional)')
        .fill(`${prefix} conference`);
      ids.push((await save('Save conference')).record_id);
      await page.getByLabel('Problem description').fill(`${prefix} issue`);
      ids.push((await save('Save issue')).record_id);
      await page.getByLabel('Title', { exact: true }).fill(`${prefix} note`);
      ids.push((await save('Save entry')).record_id);
      return ids;
    }
    const firstIds = await crud('Synthetic initial');
    expect(firstIds).toHaveLength(4);
    const model = await (
      await page.request.get(`/api/v2/operator/events?mission_id=${missionId}`)
    ).json();
    const docs = await page.request.get('/operator-help/setup.html');
    expect(docs.ok()).toBe(true);
    expect(await docs.text()).toContain('Operator setup and recovery');
    control('restart');
    await expect
      .poll(async () =>
        (await page.request.get('/api/v2/operator/health')).status()
      )
      .toBe(200);
    const reopened = await (
      await page.request.get('/api/v2/operator/health')
    ).json();
    expect(reopened.store_id).toBe(initialized.store_id);
    expect(reopened.api_epoch).toBe(initialized.api_epoch);
    await page.reload();
    const records = await (
      await page.request.get(`/api/v2/operator/records?mission_id=${missionId}`)
    ).json();
    expect(
      records.items
        .map((item: { record: { record_id: string } }) => item.record.record_id)
        .sort()
    ).toEqual([...firstIds].sort());
    await page.screenshot({
      path: join(evidence, 'fresh-install-records.png'),
      fullPage: true,
    });
    await page.goto(`/missions/${missionId}`);
    await page.getByRole('button', { name: 'Add Leg', exact: true }).click();
    const leg = page.getByRole('dialog');
    await leg.getByRole('button', { name: 'Upload KML', exact: true }).click();
    await leg.locator('input[type=file]').setInputFiles({
      name: 'synthetic-fresh-route.kml',
      mimeType: 'application/vnd.google-earth.kml+xml',
      buffer: readFileSync(
        join(
          process.env.OPERATOR_SOURCE_ROOT!,
          'backend/starlink-location/tests/fixtures/route-sigmets/altitude-free-timing.kml'
        )
      ),
    });
    await leg.getByRole('button', { name: 'Add Leg', exact: true }).click();
    await expect(leg).toHaveCount(0);
    await page
      .getByRole('button', { name: 'Simulate leg…', exact: true })
      .click();
    const simulation = page.getByRole('dialog');
    await simulation
      .getByRole('button', { name: 'Preview', exact: true })
      .click();
    await expect(simulation.getByLabel('Simulation preview')).toBeVisible();
    await simulation
      .getByRole('button', { name: 'Start simulation', exact: true })
      .click();
    await expect(simulation).toHaveCount(0);
    const run = await (await page.request.get('/api/simulation/run')).json();
    const runId = run.run.run_id as string;
    expect(runId).not.toBe(before.simulation_run_id);
    await page.goto(`/operator?mission_id=${missionId}`);
    await expect(
      page
        .getByRole('region', { name: 'Operator store setup' })
        .getByRole('button', { name: 'Initialize simulation journal' })
    ).toBeVisible();
    const activeMissing = await (
      await page.request.get('/api/v2/operator/health')
    ).json();
    expect(activeMissing.simulation_run_id).toBe(runId);
    expect(activeMissing.error_code).toBe('store_initialization_required');
    await page
      .getByRole('button', { name: 'Initialize simulation journal' })
      .click();
    await expect(
      page.getByRole('region', { name: 'Operator store setup' })
    ).toHaveCount(0);
    const activeHealth = await (
      await page.request.get('/api/v2/operator/health')
    ).json();
    expect(activeHealth.store_id).not.toBe(initialized.store_id);
    const activeIds = await crud('Synthetic active replay');
    const activeRecords = await (
      await page.request.get(`/api/v2/operator/records?mission_id=${missionId}`)
    ).json();
    expect(
      activeRecords.items
        .map((item: { record: { record_id: string } }) => item.record.record_id)
        .sort()
    ).toEqual([...activeIds].sort());
    await page.screenshot({
      path: join(evidence, 'fresh-install-active-replay.png'),
      fullPage: true,
    });
    writeFileSync(
      join(evidence, 'workspace-fresh-install.json'),
      JSON.stringify(
        {
          synthetic: true,
          noOperatorSeed: true,
          initialHealth: before,
          initializedHealth: initialized,
          realMissionCreatedInUI: missionId,
          realCrudReceipts: receipts,
          optionalModelCoverage: model.coverage,
          restartedIdentity: reopened,
          originalRecordIds: firstIds,
          activeReplay: {
            runId,
            initialHealth: activeMissing,
            initializedHealth: activeHealth,
            recordIds: activeIds,
          },
          namespace:
            'explicit initial simulation namespace followed by a real mission replay namespace; no replay-restoration claim',
        },
        null,
        2
      )
    );
  } finally {
    await context.close();
  }
});

test('hidden workspace: conference reuse and independent customer lifecycle at three sizes', async ({
  browser,
}) => {
  const receipts: object[] = [];
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport, timezoneId: 'UTC' });
    try {
      const page = await context.newPage();
      await page.goto(
        `/operator?workspace=1&mission_id=${fixtures[0].mission.id}&view=communications`
      );
      const communications = page.getByRole('region', {
        name: 'Communications',
        exact: true,
      });
      async function save(click: () => Promise<unknown>) {
        const response = page.waitForResponse(
          (response) =>
            ['POST', 'PUT'].includes(response.request().method()) &&
            /\/api\/v2\/operator\/records/.test(response.url())
        );
        await click();
        const saved = await response;
        expect(saved.ok()).toBe(true);
        const receipt = await saved.json();
        receipts.push(receipt);
        return receipt.saved_records[0];
      }
      await communications
        .getByRole('button', { name: 'Create conference', exact: true })
        .click();
      const dialog = page.getByRole('dialog');
      const title = `Synthetic reusable bridge ${viewport.width}`;
      await dialog.getByLabel('Conference name (optional)').fill(title);
      const created = await save(() =>
        dialog
          .getByRole('button', { name: 'Save conference', exact: true })
          .click()
      );
      await expect(dialog).toHaveCount(0);
      const bridge = communications.getByRole('article', {
        name: `Conference ${title}`,
        exact: true,
      });
      await save(() =>
        bridge.getByRole('button', { name: 'Establish', exact: true }).click()
      );
      await expect(bridge).toContainText('Conference: established');
      await save(() =>
        bridge.getByRole('button', { name: 'Verify', exact: true }).click()
      );
      await bridge
        .getByRole('button', { name: 'Customer Joined', exact: true })
        .click();
      await dialog
        .getByLabel('Participant (optional)')
        .fill(`Synthetic first ${viewport.width}`);
      await save(() =>
        dialog
          .getByRole('button', { name: 'Save customer interval', exact: true })
          .click()
      );
      await expect(dialog).toHaveCount(0);
      const first = communications.getByRole('article', {
        name: `Customer Synthetic first ${viewport.width}`,
        exact: true,
      });
      await expect(first).toContainText(title);
      await save(() =>
        first
          .getByRole('button', { name: 'Interrupt customer', exact: true })
          .click()
      );
      const restored = await save(() =>
        first
          .getByRole('button', { name: 'Restore connection', exact: true })
          .click()
      );
      expect(restored.payload.resumes_participation_id).toBeTruthy();
      expect(restored.record_id).not.toBe(
        restored.payload.resumes_participation_id
      );
      await bridge
        .locator('..')
        .getByRole('button', { name: 'Reuse conference', exact: true })
        .click();
      await dialog
        .getByLabel('Participant (optional)')
        .fill(`Synthetic second ${viewport.width}`);
      await save(() =>
        dialog
          .getByRole('button', { name: 'Save customer interval', exact: true })
          .click()
      );
      const second = communications.getByRole('article', {
        name: `Customer Synthetic second ${viewport.width}`,
        exact: true,
      });
      await save(() =>
        second
          .getByRole('button', { name: 'Customer Left', exact: true })
          .click()
      );
      await expect(bridge).toContainText('Conference: established');
      await save(() =>
        bridge
          .getByRole('button', { name: 'Close conference', exact: true })
          .click()
      );
      await expect(bridge.getByRole('alert')).toContainText(
        'customer reported connected'
      );
      await bridge
        .getByRole('button', { name: 'Conference history', exact: true })
        .click();
      await expect(page.getByRole('dialog')).toContainText('Version 4');
      const history = await page.request.get(
        `/api/v2/operator/records/${created.record_id}/history`
      );
      expect(history.ok()).toBe(true);
      await page
        .getByRole('button', { name: 'Close history', exact: true })
        .click();
      await page.screenshot({
        path: join(
          evidence,
          `communications-${viewport.width}x${viewport.height}.png`
        ),
      });
    } finally {
      await context.close();
    }
  }
  writeFileSync(
    join(evidence, 'workspace-communications.json'),
    JSON.stringify({ synthetic: true, receipts }, null, 2)
  );
});

test('hidden workspace: missing mission and unavailable store remain actionable at three sizes', async ({
  browser,
}) => {
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport });
    try {
      const page = await context.newPage();
      await page.goto('/operator?workspace=1');
      await expect(
        page.getByRole('heading', { name: 'Choose a mission', exact: true })
      ).toBeVisible();
      await expect(
        page.getByRole('link', { name: 'Browse missions', exact: true })
      ).toBeVisible();
      await page.route('**/api/v2/operator/health', (route) =>
        route.abort('connectionrefused')
      );
      await page.goto(
        `/operator?workspace=1&mission_id=${fixtures[0].mission.id}`
      );
      await expect(
        page.getByRole('button', { name: 'Create call', exact: true })
      ).toBeDisabled();
      await expect(
        page.getByRole('region', { name: 'Operator store setup' })
      ).toContainText('unavailable');
      await expect(
        page.getByRole('button', { name: 'Recheck store', exact: true })
      ).toBeEnabled();
      await page.screenshot({
        path: join(
          evidence,
          `unavailable-${viewport.width}x${viewport.height}.png`
        ),
      });
    } finally {
      await context.close();
    }
  }
});
