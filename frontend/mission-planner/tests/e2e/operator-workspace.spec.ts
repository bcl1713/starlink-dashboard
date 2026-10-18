import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '@playwright/test';

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
            .getByText('Synthetic customer 1 briefing', { exact: true })
        ).toBeVisible();
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth
          )
        ).toBe(true);
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
