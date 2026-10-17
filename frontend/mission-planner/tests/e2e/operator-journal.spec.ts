import { failureJourneys } from './operator-journal-failures';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '@playwright/test';
import {
  control,
  evidence,
  journal,
  mutation,
  noOverflow,
  origin,
  ready,
  save,
} from './operator-journal-helpers';

test('production desktop/mobile journal, conflict, real media 503 and exact retries', async ({
  browser,
}) => {
  const desktop = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    timezoneId: 'America/New_York',
  });
  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    timezoneId: 'Pacific/Honolulu',
  });
  const proof: Record<string, unknown> = {
    synthetic: true,
    clock: '2026-10-17T16:00:00Z',
  };
  try {
    for (const context of [desktop, mobile]) {
      await context.tracing.start({ screenshots: true, snapshots: true });
      await context.route('**/*', (route) =>
        new URL(route.request().url()).origin === origin ||
        route.request().url().startsWith('data:')
          ? route.continue()
          : route.abort()
      );
    }
    const page = await desktop.newPage();
    const phone = await mobile.newPage();
    let dialogs = 0;
    for (const p of [page, phone])
      p.on('dialog', async (dialog) => {
        dialogs++;
        await dialog.dismiss();
      });
    const cdp = await desktop.newCDPSession(page);
    proof.browser = await cdp.send('Browser.getVersion');
    await cdp.detach();
    await page.goto(origin + journal);
    await expect(
      page.getByRole('heading', { name: 'Operator journal', exact: true })
    ).toBeVisible();
    await page
      .getByLabel('Title', { exact: true })
      .fill('Synthetic late observatoin');
    await page
      .getByLabel('Note', { exact: true })
      .fill('Synthetic report entered at 1600Z about 1430–1442Z.');
    await page.getByLabel('Entry type').selectOption('call_observation');
    await page.getByLabel('Time precision').selectOption('exact');
    await page.getByLabel('Occurred at (UTC)').fill('2026-10-17T14:30:00Z');
    await page.getByLabel('End state', { exact: true }).selectOption('known');
    await page.getByLabel('Ended at (UTC)').fill('2026-10-17T14:42:00Z');
    const late = await save(page);
    expect(late.recorded_at).toBe('2026-10-17T16:00:00.000000Z');
    expect(late.time.occurred_at).toBe('2026-10-17T14:30:00.000000Z');
    await page
      .getByLabel('Title', { exact: true })
      .fill('Synthetic late observation');
    await page.getByLabel('Scope', { exact: true }).selectOption('leg');
    await page.getByLabel('Leg ID', { exact: true }).fill('synthetic-leg-2');
    await page
      .getByLabel('Audit note (optional)')
      .fill('Corrected synthetic typo and leg');
    await save(page);
    await page
      .getByRole('button', {
        name: 'History for Synthetic late observation',
        exact: true,
      })
      .click();
    await expect(
      page.getByRole('region', { name: 'Entry history' })
    ).toContainText(
      'Operator-authored reason: Corrected synthetic typo and leg'
    );
    await page.getByRole('button', { name: 'Close history' }).click();
    await page.getByRole('button', { name: 'New entry', exact: true }).click();
    await page
      .getByLabel('Title', { exact: true })
      .fill('Synthetic ended call');
    await page.getByLabel('Time precision').selectOption('exact');
    await page.getByLabel('Occurred at (UTC)').fill('2026-10-17T15:00:00Z');
    await page.getByLabel('End state', { exact: true }).selectOption('known');
    await page.getByLabel('Ended at (UTC)').fill('2026-10-17T15:45:00Z');
    const ended = await save(page);
    await page.getByLabel('Ended at (UTC)').fill('2026-10-17T15:35:00Z');
    await save(page);
    await page
      .getByRole('button', { name: 'Remove Synthetic ended call', exact: true })
      .click();
    await expect(
      page.getByRole('button', {
        name: 'Restore Synthetic ended call',
        exact: true,
      })
    ).toBeVisible();
    await page
      .getByRole('button', {
        name: 'Restore Synthetic ended call',
        exact: true,
      })
      .click();
    await expect(
      page.getByRole('button', {
        name: 'Remove Synthetic ended call',
        exact: true,
      })
    ).toBeVisible();
    await page
      .getByRole('button', {
        name: 'History for Synthetic ended call',
        exact: true,
      })
      .click();
    const history = page.getByRole('region', { name: 'Entry history' });
    for (const reason of ['correction', 'removal', 'restoration'])
      await expect(history).toContainText(
        `Automatic reason: Operator ${reason}`
      );
    await noOverflow(page);
    await page.screenshot({
      path: join(evidence, 'desktop-1920x1080.png'),
      fullPage: true,
    });
    await page.getByRole('button', { name: 'Close history' }).click();

    await phone.goto(origin + journal);
    await phone
      .getByRole('button', {
        name: 'Edit Synthetic late observation',
        exact: true,
      })
      .click();
    await phone
      .getByLabel('Note', { exact: true })
      .fill('Synthetic mobile competing correction');
    await page
      .getByRole('button', {
        name: 'Edit Synthetic late observation',
        exact: true,
      })
      .click();
    await page
      .getByLabel('Note', { exact: true })
      .fill('Synthetic desktop accepted correction');
    await save(page);
    const conflictResponse = phone.waitForResponse((r) =>
      mutation(r.request())
    );
    await phone
      .getByRole('button', { name: 'Save entry', exact: true })
      .click();
    expect((await conflictResponse).status()).toBe(409);
    await expect(phone.getByRole('alert')).toContainText(
      'Your draft is retained'
    );
    await expect(phone.getByLabel('Note', { exact: true })).toHaveValue(
      'Synthetic mobile competing correction'
    );
    await phone
      .getByRole('button', { name: 'Reread and use saved state' })
      .click();
    await expect(phone.getByLabel('Note', { exact: true })).toHaveValue(
      'Synthetic desktop accepted correction'
    );
    proof.conflict = {
      status: 409,
      draftRetained: true,
      explicitReconciliation: true,
    };

    await failureJourneys(phone, proof);
    await phone.setViewportSize({ width: 844, height: 390 });
    await noOverflow(phone);
    await phone.screenshot({
      path: join(evidence, 'mobile-844x390-saved.png'),
      fullPage: true,
    });
    control('restart');
    await ready(phone);
    for (const p of [page, phone]) {
      await p.reload();
      for (const title of [
        'Synthetic late observation',
        'Synthetic mobile retained 503 draft',
        'Synthetic lost acknowledgment',
      ]) {
        await expect(
          p
            .getByRole('region', { name: 'Current journal entries' })
            .getByRole('heading', { name: title, exact: true })
        ).toHaveCount(1);
      }
    }
    const baseline: Record<string, number> = {};
    for (const path of [
      '/overview',
      '/missions',
      '/configuration',
      '/export',
    ]) {
      const response = await page.goto(origin + path);
      baseline[path] = response!.status();
      expect(response!.status()).toBe(200);
      await expect(page.locator('main').first()).toBeVisible();
      if (path === '/overview') {
        await noOverflow(page);
        await expect(
          page.getByRole('heading', { name: 'Operator journal', exact: true })
        ).toHaveCount(0);
        await page.screenshot({
          path: join(evidence, 'overview-baseline.png'),
          fullPage: true,
        });
      }
    }
    proof.baseline = baseline;
    proof.dialogs = dialogs;
    proof.recordIds = { late: late.record_id, ended: ended.record_id };
    expect(dialogs).toBe(0);
    writeFileSync(
      join(evidence, 'browser-proof.json'),
      JSON.stringify(proof, null, 2)
    );
  } finally {
    await desktop.tracing.stop({ path: join(evidence, 'desktop-trace.zip') });
    await mobile.tracing.stop({ path: join(evidence, 'mobile-trace.zip') });
    await desktop.close();
    await mobile.close();
  }
});
