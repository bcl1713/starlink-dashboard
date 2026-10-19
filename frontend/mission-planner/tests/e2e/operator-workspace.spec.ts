import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '@playwright/test';
import { control, mutation, snapshot } from './operator-journal-helpers';
import { randomUUID } from 'node:crypto';
import type { SavedRecord } from '@/types/operator';
import { auditControlNames } from './operator-workspace-audit';

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
        await auditControlNames(page, `baseline ${fixture.seed} Operator`);
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
        await auditControlNames(page, `baseline ${fixture.seed} call editor`);
        for (const [name, path] of [
          ['overview', '/overview'],
          ['missions', '/missions'],
          ['configuration', '/configuration'],
        ] as const) {
          await page.goto(path);
          if (name === 'overview')
            await expect(page.locator('main')).toBeVisible();
          else
            await expect(
              page.getByRole('heading', {
                name: name === 'missions' ? 'Missions' : 'Configuration',
                exact: true,
              })
            ).toBeVisible();
          await page.screenshot({
            path: join(
              evidence,
              `${fixture.seed}-${viewport.width}x${viewport.height}-${name}.png`
            ),
            fullPage: true,
          });
          await auditControlNames(page, `baseline ${fixture.seed} ${name}`);
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
        await auditControlNames(page, `candidate ${fixture.seed} awareness`);
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
        await auditControlNames(page, `candidate ${fixture.seed} call editor`);
        for (let step = 0; step < 12; step++) {
          await page.keyboard.press('Tab');
          expect(
            await dialog.evaluate((element) =>
              element.contains(document.activeElement)
            )
          ).toBe(true);
        }
        await party.focus();
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
        await page.keyboard.press('Escape');
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(
          page.getByRole('button', { name: 'Note', exact: true })
        ).toBeFocused();
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
        nativeAccessibleNames: true,
        keyboardFocusTrapAndReturn: true,
        physicalDeviceKeyboard:
          'pending human device check; viewport resize is emulation',
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
          ['POST', 'PUT'].includes(response.request().method()) &&
          /\/api\/v2\/operator\/records(?:\/[^/]+)?$/.test(response.url())
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
    async function editCreated(prefix: string) {
      await page.goto(
        `/operator?workspace=1&mission_id=${missionId}&view=communications`
      );
      const communications = page.getByRole('region', {
        name: 'Communications',
        exact: true,
      });
      await communications
        .getByRole('button', { name: 'Edit call', exact: true })
        .click();
      const editor = page.getByRole('dialog');
      await editor
        .getByLabel('Party / participant (optional)')
        .fill(`${prefix} call edited`);
      expect((await save('Save call')).version).toBe(2);
      await expect(editor).toHaveCount(0);
      await communications
        .getByRole('button', { name: 'Correct conference', exact: true })
        .click();
      await editor
        .getByLabel('Conference name (optional)')
        .fill(`${prefix} conference edited`);
      expect((await save('Save conference')).version).toBe(2);
      await expect(editor).toHaveCount(0);
      await page
        .getByRole('navigation', { name: 'Operator workspace' })
        .getByRole('button', { name: 'Issues', exact: true })
        .click();
      await page
        .getByRole('button', { name: 'Add update / follow up', exact: true })
        .click();
      await editor
        .getByLabel('Add update', { exact: true })
        .fill(`${prefix} issue update`);
      expect((await save('Save issue')).version).toBe(2);
      await expect(editor).toHaveCount(0);
      await page
        .getByRole('navigation', { name: 'Operator workspace' })
        .getByRole('button', { name: 'Notes', exact: true })
        .click();
      await page
        .getByRole('button', { name: `Edit ${prefix} note`, exact: true })
        .click();
      await editor
        .getByLabel('Title', { exact: true })
        .fill(`${prefix} note edited`);
      expect((await save('Save entry')).version).toBe(2);
      await expect(editor).toHaveCount(0);
      await page.goto(`/operator?mission_id=${missionId}`);
    }
    const firstIds = await crud('Synthetic initial');
    await editCreated('Synthetic initial');
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
    await editCreated('Synthetic active replay');
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
      const nextBounds = await page
        .getByRole('region', { name: 'Next requirement', exact: true })
        .boundingBox();
      expect(nextBounds!.y + nextBounds!.height).toBeLessThanOrEqual(
        viewport.height
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
      await expect(page.getByRole('dialog')).toHaveCount(0);
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

test('hidden workspace: issue follow-up, correction and applied-only transport at three sizes', async ({
  browser,
}) => {
  const receipts: object[] = [];
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport, timezoneId: 'UTC' });
    try {
      const page = await context.newPage();
      page.setDefaultTimeout(15_000);
      const missionId = fixtures[0].mission.id;
      await page.goto(
        `/operator?workspace=1&mission_id=${missionId}&view=issues`
      );
      const navigation = page.getByRole('navigation', {
        name: 'Operator workspace',
      });
      const editor = page.getByRole('dialog');
      async function save(click: () => Promise<unknown>) {
        const response = page.waitForResponse(
          (response) =>
            ['POST', 'PUT'].includes(response.request().method()) &&
            /\/api\/v2\/operator\/records/.test(response.url()),
          { timeout: 15_000 }
        );
        await click();
        let result;
        try {
          result = await response;
        } catch (error) {
          writeFileSync(
            join(evidence, `mutation-failure-${viewport.width}.html`),
            await page.content()
          );
          await page.screenshot({
            path: join(evidence, `mutation-failure-${viewport.width}.png`),
          });
          throw error;
        }
        expect(result.ok()).toBe(true);
        const receipt = await result.json();
        receipts.push(receipt);
        return receipt.saved_records[0];
      }
      await page
        .getByRole('button', { name: 'New issue', exact: true })
        .click();
      const title = `Synthetic audio problem ${viewport.width}`;
      await editor.getByLabel('Problem description').fill(title);
      await editor
        .locator('summary')
        .filter({ hasText: 'Optional issue details' })
        .click();
      await editor
        .getByLabel('Mitigation', { exact: true })
        .selectOption('workaround');
      await editor.getByLabel('Follow-up UTC').fill('2026-10-17T15:30');
      const created = await save(() =>
        editor.getByRole('button', { name: 'Save issue', exact: true }).click()
      );
      await expect(editor).toHaveCount(0);
      const issue = page.getByRole('article', {
        name: `Issue ${title}`,
        exact: true,
      });
      await save(() =>
        issue.getByRole('button', { name: 'Monitor', exact: true }).click()
      );
      await issue
        .getByRole('button', { name: 'Add update / follow up', exact: true })
        .click();
      await editor
        .getByLabel('Add update', { exact: true })
        .fill('Synthetic workaround update');
      await save(() =>
        editor.getByRole('button', { name: 'Save issue', exact: true }).click()
      );
      await expect(editor).toHaveCount(0);
      const resolved = await save(() =>
        issue.getByRole('button', { name: 'Resolve', exact: true }).click()
      );
      expect(resolved.payload.follow_up_at).toBeNull();
      await page.getByText('Resolved issues', { exact: true }).click();
      const reopen = await save(() =>
        issue.getByRole('button', { name: 'Reopen', exact: true }).click()
      );
      expect(reopen.payload.follow_up_at).toBeNull();
      expect(reopen.payload.mitigation).toBe('workaround');
      await issue
        .getByRole('button', { name: 'Issue activity', exact: true })
        .click();
      await editor
        .getByRole('button', { name: 'Correct this update', exact: true })
        .click();
      await expect(
        editor.getByRole('heading', { name: 'Issue activity', exact: true })
      ).toHaveCount(0);
      await page.screenshot({
        path: join(evidence, `correction-handoff-${viewport.width}.png`),
      });
      writeFileSync(
        join(evidence, `correction-handoff-${viewport.width}.html`),
        await page.content()
      );
      await editor
        .getByLabel('Corrected update', { exact: true })
        .fill('Synthetic corrected workaround message');
      const corrected = await save(() =>
        editor
          .getByRole('button', { name: 'Save correction', exact: true })
          .click()
      );
      expect(corrected.payload.status).toBe('reopened');
      expect(corrected.payload.corrects_version).toBe(3);
      await expect(editor).toHaveCount(0);
      const history = await (
        await page.request.get(
          `/api/v2/operator/records/${created.record_id}/history`
        )
      ).json();
      expect(history.items).toHaveLength(6);
      await navigation
        .getByRole('button', { name: 'Transport', exact: true })
        .click();
      await page
        .getByRole('button', { name: 'Record another move', exact: true })
        .click();
      await editor
        .getByLabel('Service 1', { exact: true })
        .fill(`Synthetic IPTV ${viewport.width}`);
      await editor.getByLabel('Reported Applied 1', { exact: true }).check();
      await editor
        .getByLabel('Applied transport 1', { exact: true })
        .selectOption('Ka');
      const decision = await save(() =>
        editor
          .getByRole('button', { name: 'Save transport decision', exact: true })
          .click()
      );
      expect(decision.payload.services[0]).toMatchObject({
        intended: null,
        requested: null,
        applied: { transport: 'Ka' },
      });
      await expect(editor).toHaveCount(0);
      await expect(
        page.getByRole('button', { name: 'Record another move', exact: true })
      ).toBeEnabled();
      await page.screenshot({
        path: join(
          evidence,
          `transport-${viewport.width}x${viewport.height}.png`
        ),
      });
      await navigation
        .getByRole('button', { name: 'Issues', exact: true })
        .click();
      await page
        .getByRole('button', { name: 'Record manual assessment', exact: true })
        .click();
      await editor
        .getByLabel('Capability name', { exact: true })
        .fill(`Synthetic audio ${viewport.width}`);
      await editor
        .getByLabel('Functional capability', { exact: true })
        .selectOption('degraded');
      const assessment = await save(() =>
        editor
          .getByRole('button', { name: 'Save assessment', exact: true })
          .click()
      );
      expect(assessment.payload.functional_observed_at).toBeTruthy();
      expect(assessment.payload.redundancy_observed_at).toBeNull();
      await expect(editor).toHaveCount(0);
      await expect(
        page.getByRole('button', {
          name: 'Record manual assessment',
          exact: true,
        })
      ).toBeEnabled();
      await page.screenshot({
        path: join(evidence, `issues-${viewport.width}x${viewport.height}.png`),
      });
    } finally {
      await context.close();
    }
  }
  writeFileSync(
    join(evidence, 'workspace-issues-transport.json'),
    JSON.stringify({ synthetic: true, receipts }, null, 2)
  );
});

test('hidden workspace: paged named transport relationships retain exact targets at three sizes', async ({
  browser,
  request,
}) => {
  const missionId = fixtures[1].mission.id;
  const health = await (await request.get('/api/v2/operator/health')).json();
  const time = {
    occurred_at: null,
    ended_at: null,
    precision: 'unknown',
    end_state: 'unknown',
    planned_start_at: null,
    planned_end_at: null,
  };
  const base = {
    schema_version: 1,
    mission_id: missionId,
    leg_id: null,
    scope: 'mission',
    time,
  };
  const payload = {
    schema_version: 1,
    note: '',
    previous_leg_id: null,
    next_leg_id: null,
  };
  async function setup(body: object) {
    const response = await request.post('/api/v2/operator/records', {
      data: body,
      headers: {
        'Idempotency-Key': randomUUID(),
        'X-Operator-Store-Epoch': health.api_epoch,
      },
    });
    expect(response.ok(), await response.text()).toBe(true);
    return (await response.json()).saved_records[0] as SavedRecord;
  }
  const setupIds: string[] = [];
  // Record pages sort by UUID. Put both genuine targets beyond fifty lower IDs.
  async function highTarget(type: 'call' | 'conference') {
    for (let attempt = 0; attempt < 32; attempt++) {
      const saved = await setup({
        ...base,
        record_type: type,
        payload:
          type === 'call'
            ? {
                ...payload,
                entry_type: 'call',
                title: `Fictional lookup customer ${attempt}`,
                status: 'tentative',
                conference_id: null,
                prep_lead_minutes: null,
              }
            : {
                ...payload,
                entry_type: 'conference',
                title: `Fictional lookup bridge ${attempt}`,
                status: 'unknown',
              },
      });
      setupIds.push(saved.record_id);
      if (saved.record_id >= '8') return saved;
    }
    throw new Error(
      'Could not construct bounded paged relationship prerequisites'
    );
  }
  const call = await highTarget('call');
  const conference = await highTarget('conference');
  let lowerIds = 0;
  for (let index = 0; index < 200 && lowerIds < 50; index++) {
    const note = await setup({
      ...base,
      record_type: 'journal_entry',
      payload: {
        ...payload,
        entry_type: 'note',
        title: `Fictional paging prerequisite ${index + 1}`,
      },
    });
    setupIds.push(note.record_id);
    if (
      note.record_id < call.record_id &&
      note.record_id < conference.record_id
    )
      lowerIds++;
  }
  expect(lowerIds).toBe(50);
  const receipts: object[] = [];
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport });
    try {
      const page = await context.newPage();
      await page.goto(
        `/operator?workspace=1&mission_id=${missionId}&view=transport`
      );
      await page
        .getByRole('button', { name: 'Record another move', exact: true })
        .click();
      const editor = page.getByRole('dialog');
      await editor
        .getByLabel('Service 1', { exact: true })
        .fill(`Fictional named-link voice ${viewport.width}`);
      await editor.getByLabel('Reported Applied 1', { exact: true }).check();
      await editor
        .getByLabel('Applied transport 1', { exact: true })
        .selectOption('Ka');
      await editor
        .getByText('Reason, timing and associations (optional)', {
          exact: true,
        })
        .click();
      const targetOption = editor.getByRole('option', {
        name: conference.payload.title,
        exact: true,
      });
      const callOption = editor.getByRole('option', {
        name: call.payload.title,
        exact: true,
      });
      await expect(targetOption).toHaveCount(0);
      const coverage = editor.getByRole('status', {
        name: 'Related record coverage',
      });
      for (
        let number = 0;
        number < 10 &&
        ((await targetOption.count()) === 0 ||
          (await callOption.count()) === 0);
        number++
      ) {
        const before = Number.parseInt((await coverage.textContent())!, 10);
        const nextPage = page.waitForResponse(
          (response) =>
            response.request().method() === 'GET' &&
            response.url().includes('/api/v2/operator/records?') &&
            response.url().includes('cursor=')
        );
        await editor
          .getByRole('button', {
            name: 'Load more related records',
            exact: true,
          })
          .click();
        const loaded = await nextPage;
        expect(loaded.ok()).toBe(true);
        const next = await loaded.json();
        await expect(coverage).toContainText(
          `${before + next.items.length} related records loaded`
        );
      }
      await expect(targetOption).toHaveCount(1);
      await expect(callOption).toHaveCount(1);
      await editor
        .getByRole('combobox', { name: 'Related call', exact: true })
        .selectOption(call.record_id);
      await editor
        .getByRole('combobox', { name: 'Related conference', exact: true })
        .selectOption(conference.record_id);
      if (call.leg_id) {
        await editor
          .getByRole('combobox', { name: 'Draft scope', exact: true })
          .selectOption('leg');
        await editor
          .getByRole('combobox', { name: 'Leg', exact: true })
          .selectOption(call.leg_id);
      }
      await page.screenshot({
        path: join(
          evidence,
          `transport-associations-${viewport.width}x${viewport.height}.png`
        ),
      });
      const accepted = page.waitForResponse(
        (response) =>
          response.request().method() === 'POST' &&
          response.url().endsWith('/api/v2/operator/records')
      );
      await editor
        .getByRole('button', { name: 'Save transport decision', exact: true })
        .click();
      const response = await accepted;
      expect(response.ok(), await response.text()).toBe(true);
      const receipt = await response.json();
      expect(receipt.saved_records[0].payload).toMatchObject({
        call_id: call.record_id,
        conference_id: conference.record_id,
      });
      expect(receipt.saved_records[0].payload.services[0]).toMatchObject({
        intended: null,
        requested: null,
        applied: { transport: 'Ka' },
      });
      receipts.push(receipt);
      await expect(editor).toHaveCount(0);
    } finally {
      await context.close();
    }
  }
  writeFileSync(
    join(evidence, 'workspace-relationships.json'),
    JSON.stringify(
      {
        synthetic: true,
        setupRecordIds: setupIds,
        setupIsNotLearnerCompletion: true,
        callId: call.record_id,
        conferenceId: conference.record_id,
        receipts,
      },
      null,
      2
    )
  );
});

test('hidden workspace: real lost receipt exact retry and offline draft recovery at three sizes', async ({
  browser,
}) => {
  const proof: object[] = [];
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport });
    try {
      const page = await context.newPage();
      const missionId = fixtures[0].mission.id;
      await page.goto(
        `/operator?workspace=1&mission_id=${missionId}&view=notes`
      );
      await page.getByRole('button', { name: 'Note', exact: true }).click();
      const editor = page.getByRole('dialog');
      const title = `Fictional lost receipt ${viewport.width}`;
      await editor.getByLabel('Title', { exact: true }).fill(title);
      const requests: ReturnType<typeof snapshot>[] = [];
      page.on('request', (request) => {
        if (mutation(request)) requests.push(snapshot(request));
      });
      let committed: { saved_records: SavedRecord[] } | null = null;
      let intercepted = false;
      await page.route('**/api/v2/operator/records', async (route) => {
        if (route.request().method() !== 'POST' || intercepted)
          return route.continue();
        intercepted = true;
        const response = await route.fetch();
        expect(response.ok()).toBe(true);
        committed = await response.json();
        await route.abort('connectionreset');
      });
      await editor
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      await expect(editor).toContainText(/uncertain/i);
      expect(committed).not.toBeNull();
      const beforeRetry = await (
        await page.request.get(
          `/api/v2/operator/records?mission_id=${missionId}`
        )
      ).json();
      expect(
        beforeRetry.items.filter(
          (item: { record: SavedRecord }) => item.record.payload.title === title
        )
      ).toHaveLength(1);
      await editor
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      await expect(editor).toHaveCount(0);
      await page.unroute('**/api/v2/operator/records');
      const replayed = page.waitForResponse(
        (response) =>
          response.request().method() === 'POST' &&
          response.url().endsWith('/api/v2/operator/records')
      );
      await page
        .getByRole('button', { name: 'Retry same save', exact: true })
        .click();
      const accepted = await replayed;
      expect(accepted.ok()).toBe(true);
      const receipt = await accepted.json();
      expect(receipt).toEqual(committed);
      expect(requests).toHaveLength(2);
      expect(requests[1]).toEqual(requests[0]);
      const savedId = receipt.saved_records[0].record_id;
      const history = await (
        await page.request.get(`/api/v2/operator/records/${savedId}/history`)
      ).json();
      expect(history.cursor).toBeNull();
      expect(history.items).toHaveLength(1);
      await expect(
        page.getByRole('button', { name: 'Retry same save', exact: true })
      ).toHaveCount(0);
      const afterRetry = await (
        await page.request.get(
          `/api/v2/operator/records?mission_id=${missionId}`
        )
      ).json();
      expect(
        afterRetry.items.filter(
          (item: { record: SavedRecord }) => item.record.payload.title === title
        )
      ).toHaveLength(1);
      await page.getByRole('button', { name: 'Note', exact: true }).click();
      const offlineTitle = `Fictional retained offline note ${viewport.width}`;
      await editor.getByLabel('Title', { exact: true }).fill(offlineTitle);
      await context.setOffline(true);
      await page.evaluate(() => window.dispatchEvent(new Event('focus')));
      await expect(editor.getByText(/Store unavailable/)).toBeVisible({
        timeout: 20_000,
      });
      await editor
        .getByLabel('Title', { exact: true })
        .fill(`${offlineTitle} revised`);
      await expect(
        editor.getByRole('button', { name: 'Save entry', exact: true })
      ).toBeDisabled();
      await editor
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      await context.setOffline(false);
      await page.reload();
      await page
        .getByRole('button', { name: new RegExp(`${offlineTitle} revised`) })
        .click();
      await expect(editor.getByLabel('Title', { exact: true })).toHaveValue(
        `${offlineTitle} revised`
      );
      const recovered = page.waitForResponse(
        (response) =>
          response.request().method() === 'POST' &&
          response.url().endsWith('/api/v2/operator/records')
      );
      await editor
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      expect((await recovered).ok()).toBe(true);
      await expect(editor).toHaveCount(0);
      await page.screenshot({
        path: join(
          evidence,
          `recovery-${viewport.width}x${viewport.height}.png`
        ),
      });
      proof.push({
        viewport,
        lostReceiptRequests: requests.slice(0, 2),
        recoveredOfflineRequest: requests[2],
        realCommittedReceipt: receipt,
        historyVersions: history.items.length,
        exactRetryOneWrite: true,
        offlineDraftAfterReconnectReload: true,
      });
    } finally {
      await context.close();
    }
  }
  writeFileSync(
    join(evidence, 'workspace-recovery.json'),
    JSON.stringify({ synthetic: true, proof }, null, 2)
  );
});

test('performance: matching operational tasks on original and candidate shells', async ({
  browser,
}) => {
  const mode = process.env.OPERATOR_BENCHMARK_MODE;
  test.skip(
    !mode,
    'Only the explicitly owned benchmark runner selects this case'
  );
  const candidate = mode === 'candidate';
  const measurements: Record<string, unknown>[] = [];
  const report = () =>
    writeFileSync(
      join(evidence, 'workspace-performance.json'),
      JSON.stringify(
        {
          synthetic: true,
          mode,
          measurements,
          scope:
            'Scripted matching task outcomes; automatic scrolling and instantaneous text fills are included. Not human timing, mis-selection or physical-device evidence.',
          budgets: { ordinaryTaskMs: 5000, injectedRecoveryTaskMs: 10000 },
          humanMisSelections: null,
          physicalKeyboard: 'pending human observation',
        },
        null,
        2
      )
    );
  try {
    for (const fixture of fixtures)
      for (const viewport of viewports) {
        const context = await browser.newContext({
          viewport,
          timezoneId: 'Pacific/Honolulu',
        });
        try {
          const page = await context.newPage();
          const missionId = fixture.mission.id;
          await page.goto(
            `/operator?${candidate ? 'workspace=1&' : ''}mission_id=${missionId}`
          );
          if (candidate)
            await expect(
              page.getByRole('navigation', { name: 'Operator workspace' })
            ).toBeVisible();
          else
            await expect(
              page.getByRole('heading', {
                name: 'Operator journal',
                exact: true,
              })
            ).toBeVisible();
          const calls = page.getByRole('region', {
            name: 'Communications',
            exact: true,
          });
          if (candidate)
            await expect(
              page
                .getByRole('region', { name: 'Next requirement', exact: true })
                .getByText('Synthetic customer 1 briefing', { exact: true })
            ).toBeVisible();
          else
            await expect(
              calls.getByRole('heading', {
                name: 'Synthetic customer 1',
                exact: true,
              })
            ).toBeVisible();
          let counts = {
            activations: 0,
            textEdits: 0,
            selectors: 0,
            keypresses: 0,
          };
          let writes: unknown[] = [];
          const click = async (target: import('@playwright/test').Locator) => {
            counts.activations++;
            await target.click();
          };
          const fill = async (
            target: import('@playwright/test').Locator,
            value: string
          ) => {
            counts.textEdits++;
            await target.fill(value);
          };
          const select = async (
            target: import('@playwright/test').Locator,
            value: string
          ) => {
            counts.selectors++;
            await target.selectOption(value);
          };
          const task = async (
            name: string,
            action: () => Promise<void>,
            recovery = false
          ) => {
            counts = {
              activations: 0,
              textEdits: 0,
              selectors: 0,
              keypresses: 0,
            };
            writes = [];
            const started = performance.now();
            let recorded = false;
            try {
              await action();
              const elapsedMs = performance.now() - started;
              measurements.push({
                scenario: fixture.seed,
                viewport,
                task: name,
                ...counts,
                elapsedMs,
                writes,
                recoveryActions: recovery ? 1 : 0,
                outcome: 'authoritative receipt and visible UI asserted',
              });
              recorded = true;
              report();
              expect(elapsedMs).toBeLessThanOrEqual(recovery ? 10000 : 5000);
            } catch (error) {
              if (!recorded)
                measurements.push({
                  scenario: fixture.seed,
                  viewport,
                  task: name,
                  ...counts,
                  elapsedMs: performance.now() - started,
                  writes,
                  failed: true,
                });
              else measurements[measurements.length - 1].failed = true;
              report();
              throw error;
            }
          };
          const save = async (method: string, action: () => Promise<void>) => {
            const pending = page.waitForResponse(
              (r) =>
                r.request().method() === method &&
                /\/api\/v2\/operator\/records(?:\/|$)/.test(
                  new URL(r.url()).pathname
                )
            );
            await action();
            const response = await pending;
            expect(response.ok()).toBe(true);
            const receipt = await response.json();
            await response.finished();
            writes.push({
              status: response.status(),
              timing: response.request().timing(),
              commandId: receipt.command_id,
            });
            expect(receipt.saved_records).toHaveLength(1);
            return receipt;
          };
          const callName = `Benchmark ${fixture.seed} ${viewport.width} call`;
          const callRow = () =>
            calls.getByRole('listitem').filter({
              has: page.getByRole('heading', { name: callName, exact: true }),
            });
          await task('Create planned call', async () => {
            const editor = page.getByRole('form', { name: 'Call editor' });
            if (candidate || !(await editor.isVisible()))
              await click(
                page.getByRole('button', {
                  name: candidate ? 'Create call' : 'Schedule call',
                  exact: true,
                })
              );
            await fill(
              editor.getByLabel('Party / participant (optional)'),
              callName
            );
            await fill(
              editor.getByLabel('Planned start (UTC)', { exact: true }),
              '2026-10-17T17:00:00Z'
            );
            const receipt = await save('POST', () =>
              click(
                editor.getByRole('button', { name: 'Save call', exact: true })
              )
            );
            expect(receipt.saved_records[0].payload.party).toBe(callName);
            if (candidate)
              await expect(page.getByRole('dialog')).toHaveCount(0);
            else
              await expect(
                calls.getByText('Call saved.', { exact: true })
              ).toBeVisible();
            if (candidate)
              await expect(
                page.getByRole('region', { name: 'Save status', exact: true })
              ).toContainText(`${callName} · accepted`);
            else await expect(callRow()).toBeVisible();
          });
          await task('Reschedule same call', async () => {
            if (candidate)
              await click(
                page
                  .getByRole('navigation', { name: 'Operator workspace' })
                  .getByRole('button', { name: 'Communications', exact: true })
              );
            const editor = page.getByRole('form', { name: 'Call editor' });
            if (
              candidate ||
              (await editor
                .getByLabel('Party / participant (optional)')
                .inputValue()) !== callName
            )
              await click(
                callRow().getByRole('button', {
                  name: 'Edit call',
                  exact: true,
                })
              );
            // Optional details are a native disclosure in both shells.
            await click(
              editor.getByText('Timing, association and optional details', {
                exact: true,
              })
            );
            await fill(editor.getByLabel('Shift amount'), '15');
            await select(editor.getByLabel('Shift unit'), 'minutes');
            await click(
              editor.getByRole('button', { name: 'Apply shift', exact: true })
            );
            const receipt = await save('PUT', () =>
              click(
                editor.getByRole('button', { name: 'Save call', exact: true })
              )
            );
            expect(
              Date.parse(receipt.saved_records[0].time.planned_start_at)
            ).toBe(Date.parse('2026-10-17T17:15:00Z'));
            if (candidate)
              await expect(page.getByRole('dialog')).toHaveCount(0);
            else
              await expect(
                calls.getByText('Call saved.', { exact: true })
              ).toBeVisible();
            await expect(callRow()).toContainText('17:15:00');
          });
          await task('Inspect original and replacement history', async () => {
            await click(
              callRow().getByRole('button', {
                name: 'Call history',
                exact: true,
              })
            );
            const history = page.getByRole('region', {
              name: 'Entry history',
              exact: true,
            });
            await expect(history.getByRole('listitem')).toHaveCount(2);
            await expect(history).toContainText('Version 1');
            await expect(history).toContainText('Version 2');
            await click(
              history.getByRole('button', {
                name: 'Close history',
                exact: true,
              })
            );
            await expect(history).toHaveCount(0);
          });
          const enterNote = async (title: string) => {
            if (
              candidate ||
              (await page.getByLabel('Title', { exact: true }).inputValue())
            )
              await click(
                page.getByRole('button', {
                  name: candidate ? 'Note' : 'New entry',
                  exact: true,
                })
              );
            await fill(page.getByLabel('Title', { exact: true }), title);
            await fill(
              page.getByRole('textbox', { name: 'Note', exact: true }),
              'Fictional operational observation'
            );
          };
          await task('Log mission note', async () => {
            const title = `Benchmark ${fixture.seed} ${viewport.width} note`;
            await enterNote(title);
            const receipt = await save('POST', () =>
              click(
                page.getByRole('button', { name: 'Save entry', exact: true })
              )
            );
            expect(receipt.saved_records[0].payload.title).toBe(title);
            if (candidate)
              await expect(page.getByRole('dialog')).toHaveCount(0);
            else
              await expect(
                page
                  .getByRole('region', {
                    name: 'Operator journal',
                    exact: true,
                  })
                  .getByRole('status')
              ).toHaveText('Saved.');
          });
          const issueName = `Benchmark ${fixture.seed} ${viewport.width} issue`;
          await task('Log issue', async () => {
            if (candidate)
              await click(
                page
                  .getByRole('navigation', { name: 'Operator workspace' })
                  .getByRole('button', { name: 'Issues', exact: true })
              );
            if (
              candidate ||
              (await page.getByLabel('Problem description').inputValue())
            )
              await click(
                page.getByRole('button', { name: 'New issue', exact: true })
              );
            const editor = page.getByRole('form', { name: 'Issue editor' });
            await fill(editor.getByLabel('Problem description'), issueName);
            const receipt = await save('POST', () =>
              click(
                editor.getByRole('button', { name: 'Save issue', exact: true })
              )
            );
            expect(receipt.saved_records[0].payload.title).toBe(issueName);
            if (candidate)
              await expect(page.getByRole('dialog')).toHaveCount(0);
            await expect(
              page.getByRole('heading', { name: issueName, exact: true })
            ).toBeVisible();
          });
          await task('Resolve issue', async () => {
            const row = candidate
              ? page.getByRole('article', {
                  name: `Issue ${issueName}`,
                  exact: true,
                })
              : page
                  .getByRole('region', {
                    name: 'Issue management',
                    exact: true,
                  })
                  .getByRole('listitem')
                  .filter({
                    has: page.getByRole('heading', {
                      name: issueName,
                      exact: true,
                    }),
                  });
            const receipt = await save('PUT', () =>
              click(row.getByRole('button', { name: 'Resolve', exact: true }))
            );
            expect(receipt.saved_records[0].payload.status).toBe('resolved');
            await expect(
              page.getByRole('heading', { name: issueName, exact: true })
            ).not.toBeVisible();
          });
          await task('Change shared display history window', async () => {
            if (candidate) {
              if (
                !(await page
                  .getByRole('button', { name: 'Display tools', exact: true })
                  .isVisible())
              )
                await click(
                  page.getByRole('button', { name: 'Tools', exact: true })
                );
              await click(
                page.getByRole('button', { name: 'Display tools', exact: true })
              );
            }
            const tools = candidate
              ? page.getByRole('dialog', { name: 'Display tools', exact: true })
              : page.getByRole('region', {
                  name: 'Display tools',
                  exact: true,
                });
            await click(
              tools.getByRole('button', {
                name: 'Show display controls',
                exact: true,
              })
            );
            const control = tools.getByLabel('Overview history window');
            await expect(control).toBeEnabled();
            const value =
              (await control.inputValue()) === '900' ? '1800' : '900';
            const response = page.waitForResponse(
              (r) =>
                r.request().method() === 'PUT' &&
                r.url().endsWith('/api/overview-history/settings')
            );
            await select(control, value);
            const accepted = await response;
            expect(accepted.ok()).toBe(true);
            const savedWindow = await accepted.json();
            expect(savedWindow.window_seconds).toBe(Number(value));
            await accepted.finished();
            writes.push({
              status: accepted.status(),
              timing: accepted.request().timing(),
              windowSeconds: savedWindow.window_seconds,
            });
            await expect(control).toHaveValue(value);
            if (candidate) {
              counts.keypresses++;
              await page.keyboard.press('Escape');
              await expect(tools).toHaveCount(0);
            } else
              await click(
                tools.getByRole('button', {
                  name: 'Hide display controls',
                  exact: true,
                })
              );
          });
          await task(
            'Recover response loss with exact retry',
            async () => {
              const title = `Benchmark ${fixture.seed} ${viewport.width} recovery`;
              await enterNote(title);
              let committed: unknown = null;
              const attempts: ReturnType<typeof snapshot>[] = [];
              let dropped = false;
              await page.route('**/api/v2/operator/records', async (route) => {
                if (route.request().method() !== 'POST')
                  return route.continue();
                attempts.push(snapshot(route.request()));
                if (dropped) return route.continue();
                dropped = true;
                const response = await route.fetch();
                expect(response.ok()).toBe(true);
                committed = await response.json();
                await route.abort('connectionreset');
              });
              await click(
                page.getByRole('button', { name: 'Save entry', exact: true })
              );
              if (candidate) {
                await expect(page.getByRole('dialog')).toContainText(
                  /uncertain/i
                );
                await click(
                  page.getByRole('dialog').getByRole('button', {
                    name: 'Keep draft and return',
                    exact: true,
                  })
                );
              }
              const retry = page.getByRole('button', {
                name: candidate ? 'Retry same save' : 'Retry exact save',
                exact: true,
              });
              await expect(retry).toBeEnabled();
              const receipt = await save('POST', () => click(retry));
              expect(receipt).toEqual(committed);
              expect(attempts).toHaveLength(2);
              expect(attempts[1]).toEqual(attempts[0]);
              const id = receipt.saved_records[0].record_id;
              const history = await (
                await page.request.get(`/api/v2/operator/records/${id}/history`)
              ).json();
              expect(history.items).toHaveLength(1);
              expect(history.cursor).toBeNull();
              await expect(retry).toHaveCount(0);
              await page.unroute('**/api/v2/operator/records');
            },
            true
          );
          if (fixture.seed === 'normal')
            for (const [name, path] of [
              ['Overview', '/overview'],
              ['Missions', '/missions'],
              ['Configuration', '/configuration'],
            ] as const) {
              await page.goto(path);
              if (name === 'Overview')
                await expect(page.locator('main')).toBeVisible();
              else
                await expect(
                  page.getByRole('heading', { name, exact: true })
                ).toBeVisible();
              if (candidate)
                await auditControlNames(
                  page,
                  `candidate final ${name} ${viewport.width}x${viewport.height}`
                );
              await page.screenshot({
                path: join(
                  evidence,
                  `${mode}-${name.toLowerCase()}-${viewport.width}x${viewport.height}.png`
                ),
                animations: 'disabled',
                fullPage: false,
              });
            }
        } finally {
          await context.close();
        }
      }
    expect(measurements).toHaveLength(fixtures.length * viewports.length * 8);
  } finally {
    report();
  }
});
