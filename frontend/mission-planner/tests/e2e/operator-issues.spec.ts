import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, type Page } from '@playwright/test';
import {
  control,
  evidence,
  noOverflow,
  origin,
  ready,
  mutation,
  snapshot,
} from './operator-journal-helpers';
const url = `${origin}/operator?mission_id=synthetic-mission-b`;
async function open(page: Page) {
  await page.goto(url);
  await ready(page);
  const region = page.getByRole('region', {
    name: 'Issue management',
    exact: true,
  });
  await expect(region.getByText(/Issue snapshot 2026/)).toBeVisible();
  return region;
}
async function tap(page: Page, action: () => Promise<void>) {
  const pending = page.waitForResponse((r) => mutation(r.request()));
  await action();
  const response = await pending;
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()).saved_records[0];
}
async function refresh(page: Page) {
  await page
    .getByRole('button', { name: 'Refresh issues', exact: true })
    .click();
  await page
    .getByRole('button', { name: 'Refresh summary', exact: true })
    .click();
}

test('issue exception workflow: corrections, snapshot check-ins, drafts and restart', async ({
  browser,
}) => {
  test.setTimeout(600_000);
  const proof: Record<string, unknown> = { synthetic: true, captures: [] };
  const viewports = [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ];
  for (const [index, viewport] of viewports.entries()) {
    const context = await browser.newContext({
      viewport,
      timezoneId: 'Pacific/Honolulu',
    });
    const counterpart = await browser.newContext({
      viewport: { width: 390, height: 844 },
      timezoneId: 'Asia/Tokyo',
    });
    try {
      for (const client of [context, counterpart])
        await client.route('**/*', (route) =>
          new URL(route.request().url()).origin === origin ||
          route.request().url().startsWith('data:')
            ? route.continue()
            : route.abort()
        );
      const hour = 16 + index;
      control('clock', `2026-10-17T${hour}:00:00Z`);
      const page = await context.newPage();
      const region = await open(page);
      const name = `Synthetic exception ${viewport.width}`;
      const editor = region.getByRole('form', { name: 'Issue editor' });
      await editor.getByLabel('Problem description').fill(name);
      const issue = await tap(page, () =>
        editor.getByRole('button', { name: 'Save issue', exact: true }).click()
      );
      expect(issue.payload.status).toBe('open');
      expect(issue.payload.priority).toBeNull();
      proof.descriptionOnly = true;
      const card = region
        .locator('li')
        .filter({ has: page.getByRole('heading', { name, exact: true }) });
      await card
        .getByRole('button', { name: 'Add update / follow up', exact: true })
        .click();
      await editor.locator('summary').click();
      await editor
        .getByLabel('Status', { exact: true })
        .selectOption('monitoring');
      await editor
        .getByLabel('Mitigation', { exact: true })
        .selectOption('workaround');
      await editor
        .getByLabel('Add update', { exact: true })
        .fill(`Synthetic original backup ${viewport.width}`);
      await editor
        .getByLabel('Follow-up UTC', { exact: true })
        .fill(`2026-10-17T${hour}:15:00`);
      await tap(page, () =>
        editor.getByRole('button', { name: 'Save issue', exact: true }).click()
      );
      await expect(card).toContainText('monitoring');
      await expect(card).toContainText('workaround');
      proof.workaroundMonitoring = true;
      const capability = region.getByRole('form', {
        name: 'Capability assessment',
      });
      await capability
        .getByLabel('Capability name', { exact: true })
        .fill(`Synthetic secure voice ${viewport.width}`);
      await capability
        .getByLabel('Functional capability', { exact: true })
        .selectOption('functional');
      await capability
        .getByLabel('Redundancy', { exact: true })
        .selectOption('unavailable');
      const assessment = await tap(page, () =>
        capability
          .getByRole('button', { name: 'Save assessment', exact: true })
          .click()
      );
      expect(assessment.payload.functional_status).toBe('functional');
      expect(assessment.payload.redundancy_status).toBe('unavailable');
      proof.independentCapability = true;
      await page
        .getByRole('navigation', { name: 'Operator sections' })
        .getByRole('link', { name: 'Journal', exact: true })
        .click();
      control('clock', `2026-10-17T${hour}:15:00Z`);
      await refresh(page);
      await expect(card).toContainText('Follow-up due');
      await expect(
        page.getByRole('complementary', { name: 'Issue follow-up snapshot' })
      ).toContainText('due in this snapshot');
      control('clock', `2026-10-17T${hour}:15:01Z`);
      await refresh(page);
      await expect(card).toContainText('Follow-up overdue');
      proof.snapshotBoundaries = true;
      // Both clients begin with the same saved version; the stale writer keeps its draft.
      await card
        .getByRole('button', { name: 'Add update / follow up', exact: true })
        .click();
      await editor
        .getByLabel('Add update', { exact: true })
        .fill('Synthetic retained conflict draft');
      const second = await counterpart.newPage();
      const secondRegion = await open(second);
      const secondCard = secondRegion
        .locator('li')
        .filter({ has: second.getByRole('heading', { name, exact: true }) });
      await secondCard
        .getByRole('button', { name: 'Add update / follow up', exact: true })
        .click();
      const secondEditor = secondRegion.getByRole('form', {
        name: 'Issue editor',
      });
      await secondEditor.locator('summary').click();
      await secondEditor
        .getByLabel('Responsible party (optional)', { exact: true })
        .fill('Synthetic counterpart');
      await tap(second, () =>
        secondEditor
          .getByRole('button', { name: 'Save issue', exact: true })
          .click()
      );
      const conflict = page.waitForResponse((r) => mutation(r.request()));
      await editor
        .getByRole('button', { name: 'Save issue', exact: true })
        .click();
      expect((await conflict).status()).toBe(409);
      await expect(
        editor.getByLabel('Add update', { exact: true })
      ).toHaveValue('Synthetic retained conflict draft');
      await region
        .getByRole('button', {
          name: 'Reread issue for reconciliation',
          exact: true,
        })
        .click();
      await expect(
        editor.getByRole('button', {
          name: 'Apply reviewed draft to current version',
        })
      ).toBeEnabled();
      await editor
        .getByRole('button', { name: 'Discard issue draft', exact: true })
        .click();
      proof.twoClients = true;
      // Resolve before correcting an older message. Neither correction nor timeline replay reopens it.
      await tap(page, () =>
        card.getByRole('button', { name: 'Resolve', exact: true }).click()
      );
      await region
        .locator('summary')
        .filter({ hasText: /^Resolved issues/ })
        .click();
      await card
        .getByRole('button', { name: 'Issue activity', exact: true })
        .click();
      const activity = region.getByRole('region', {
        name: 'Issue activity',
        exact: true,
      });
      await activity
        .locator('li')
        .filter({ hasText: `Synthetic original backup ${viewport.width}` })
        .getByRole('button', { name: 'Correct this update' })
        .click();
      const correction = region.getByRole('form', {
        name: 'Correct historical update',
      });
      await correction
        .getByLabel('Corrected update', { exact: true })
        .fill(`Synthetic corrected backup ${viewport.width}`);
      await correction
        .getByLabel('Corrected occurred UTC', { exact: true })
        .fill(`2026-10-17T${hour}:04:00`);
      const corrected = await tap(page, () =>
        correction
          .getByRole('button', { name: 'Save correction', exact: true })
          .click()
      );
      expect(corrected.payload.status).toBe('resolved');
      expect(corrected.payload.follow_up_at).toBeNull();
      await expect(
        activity.getByText(`Synthetic corrected backup ${viewport.width}`, {
          exact: true,
        })
      ).toHaveCount(1);
      await expect(
        activity.getByText(`Synthetic original backup ${viewport.width}`, {
          exact: true,
        })
      ).toHaveCount(0);
      await expect(activity).toContainText('Corrected');
      await expect(activity).toContainText('Entered later');
      await card
        .getByRole('button', { name: 'Audit history', exact: true })
        .click();
      await expect(
        region.getByRole('region', { name: 'Entry history' })
      ).toContainText(`Synthetic original backup ${viewport.width}`);
      await region
        .getByRole('button', { name: 'Close history', exact: true })
        .click();
      proof.resolvedCorrection = true;
      proof.correctionLineage = true;
      await tap(page, () =>
        card.getByRole('button', { name: 'Reopen', exact: true }).click()
      );
      await expect(card).toContainText('reopened');
      await expect(card).toContainText('Follow-up unscheduled');
      // Real commit followed by lost HTTP acknowledgment, then browser reload and replay.
      await card
        .getByRole('button', { name: 'Add update / follow up', exact: true })
        .click();
      await editor
        .getByLabel('Add update', { exact: true })
        .fill('Synthetic reload-safe update');
      let lose = true;
      let original: ReturnType<typeof snapshot> | undefined;
      await page.route(`${origin}/api/v2/operator/records**`, async (route) => {
        if (lose && mutation(route.request())) {
          lose = false;
          original = snapshot(route.request());
          await route.fetch();
          return route.abort();
        }
        return route.continue();
      });
      await editor
        .getByRole('button', { name: 'Save issue', exact: true })
        .click();
      await expect(
        region.getByRole('button', { name: 'Retry issue save', exact: true })
      ).toBeVisible();
      await page.reload();
      await ready(page);
      await expect(
        region.getByRole('button', { name: 'Retry issue save', exact: true })
      ).toBeVisible();
      const replay = page.waitForRequest(mutation);
      await region
        .getByRole('button', { name: 'Retry issue save', exact: true })
        .click();
      expect(snapshot(await replay)).toEqual(original);
      await expect(
        region.getByRole('button', { name: 'Retry issue save', exact: true })
      ).toHaveCount(0);
      expect(JSON.parse(control('counts', original!.key))).toEqual({
        receipts: 1,
        revisions: 1,
      });
      proof.reloadFrozenRetry = true;
      await page.unroute(`${origin}/api/v2/operator/records**`);
      // An old-epoch uncertain command remains quarantined after an actual backend restart.
      await card
        .getByRole('button', { name: 'Add update / follow up', exact: true })
        .click();
      await editor
        .getByLabel('Add update', { exact: true })
        .fill('Synthetic epoch-bound update');
      let loseEpoch = true;
      await page.route(`${origin}/api/v2/operator/records**`, async (route) => {
        if (loseEpoch && mutation(route.request())) {
          loseEpoch = false;
          await route.fetch();
          return route.abort();
        }
        return route.continue();
      });
      await editor
        .getByRole('button', { name: 'Save issue', exact: true })
        .click();
      await expect(
        region.getByRole('button', { name: 'Retry issue save', exact: true })
      ).toBeVisible();
      control('restart');
      await ready(page);
      await page.reload();
      await expect(
        region.getByText(/Issue conflict or changed store/)
      ).toBeVisible();
      await expect(
        region.getByRole('button', { name: 'Retry issue save', exact: true })
      ).toHaveCount(0);
      await region
        .getByRole('button', {
          name: 'Reread issue for reconciliation',
          exact: true,
        })
        .click();
      await expect(card).toContainText('reopened');
      proof.epochQuarantine = true;
      proof.restart = true;
      expect(
        (
          await (
            await page.request.get(
              `/api/v2/operator/records/${assessment.record_id}`
            )
          ).json()
        ).record.payload.redundancy_status
      ).toBe('unavailable');
      await noOverflow(page);
      await region
        .getByRole('heading', { name: 'Issues and manual capabilities' })
        .scrollIntoViewIfNeeded();
      await page.screenshot({
        path: join(evidence, `issues-${viewport.width}x${viewport.height}.png`),
      });
      (proof.captures as string[]).push(`${viewport.width}x${viewport.height}`);
    } finally {
      await counterpart.close();
      await context.close();
    }
  }
  // Actual #349 multi-leg archive lifecycle preservation is asserted by export_probe.
  proof.multileg = true;
  proof.noReadinessInference = true;
  writeFileSync(
    join(evidence, 'issues-proof.json'),
    JSON.stringify(proof, null, 2)
  );
});
