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
      .getByRole('textbox', { name: /^Note/ })
      .fill('Synthetic report entered at 1600Z about 1430–1442Z.');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Entry type')
      .selectOption('call_observation');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Time precision')
      .selectOption('exact');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Occurred at (UTC)')
      .fill('2026-10-17T14:30:00Z');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('End state')
      .selectOption('known');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Ended at (UTC)')
      .fill('2026-10-17T14:42:00Z');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Scope')
      .selectOption('leg');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Leg ID', { exact: true })
      .fill('synthetic-leg-1');
    const late = await save(page, true);
    proof.saveStatus = {
      heldRealResponse: true,
      savingAnnounced: true,
      receiptAcknowledged: true,
    };
    expect(late.recorded_at).toBe('2026-10-17T16:00:00.000000Z');
    expect(late.time.occurred_at).toBe('2026-10-17T14:30:00.000000Z');
    await page
      .getByLabel('Title', { exact: true })
      .fill('Synthetic late observation');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Scope')
      .selectOption('leg');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Leg ID', { exact: true })
      .fill('synthetic-leg-2');
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
    const legHistory = page.getByRole('region', { name: 'Entry history' });
    await expect(
      legHistory.getByRole('listitem').filter({ hasText: 'Version 1 ·' })
    ).toContainText('Leg: synthetic-leg-1');
    await expect(
      legHistory.getByRole('listitem').filter({ hasText: 'Version 2 ·' })
    ).toContainText('Leg: synthetic-leg-2');
    await expect(legHistory).toContainText('Author:');
    await page.getByRole('button', { name: 'Close history' }).click();
    await page.getByRole('button', { name: 'New entry', exact: true }).click();
    await page
      .getByLabel('Title', { exact: true })
      .fill('Synthetic ended call');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Time precision')
      .selectOption('exact');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Occurred at (UTC)')
      .fill('2026-10-17T15:00:00Z');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('End state')
      .selectOption('known');
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Ended at (UTC)')
      .fill('2026-10-17T15:45:00Z');
    const ended = await save(page);
    await page
      .getByRole('region', { name: 'Operator journal', exact: true })
      .getByLabel('Ended at (UTC)')
      .fill('2026-10-17T15:35:00Z');
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
    await expect(
      history.getByRole('listitem').filter({ hasText: 'Version 1 ·' })
    ).toContainText('Actual end: 2026-10-17 15:45:00.000000 UTC');
    await expect(
      history.getByRole('listitem').filter({ hasText: 'Version 2 ·' })
    ).toContainText('Actual end: 2026-10-17 15:35:00.000000 UTC');
    proof.historyValues = {
      originalEnd: '15:45 UTC',
      correctedEnd: '15:35 UTC',
      originalLeg: 'synthetic-leg-1',
      correctedLeg: 'synthetic-leg-2',
      authorVisible: true,
    };
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
      .getByRole('textbox', { name: /^Note/ })
      .fill('Synthetic mobile competing correction');
    await page
      .getByRole('button', {
        name: 'Edit Synthetic late observation',
        exact: true,
      })
      .click();
    await page
      .getByRole('textbox', { name: /^Note/ })
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
    await expect(phone.getByRole('textbox', { name: /^Note/ })).toHaveValue(
      'Synthetic mobile competing correction'
    );
    await phone
      .getByRole('button', { name: 'Reread and use saved state' })
      .click();
    await expect(phone.getByRole('textbox', { name: /^Note/ })).toHaveValue(
      'Synthetic desktop accepted correction'
    );
    proof.conflict = {
      status: 409,
      draftRetained: true,
      explicitReconciliation: true,
    };

    await failureJourneys(phone, proof);
    await phone.setViewportSize({ width: 844, height: 390 });
    await phone.getByLabel('Title', { exact: true }).scrollIntoViewIfNeeded();
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
    proof.dialogs = dialogs;
    proof.recordIds = { late: late.record_id, ended: ended.record_id };
    writeFileSync(
      join(evidence, 'browser-proof.json'),
      JSON.stringify(proof, null, 2)
    );
    const baseline: Record<string, Record<string, number>> = {};
    await phone.setViewportSize({ width: 390, height: 844 });
    for (const [device, client] of [
      ['desktop', page],
      ['mobile', phone],
    ] as const) {
      baseline[device] = {};
      for (const [path, heading] of [
        ['/overview', null],
        ['/missions', 'Missions'],
        ['/configuration', 'Configuration'],
        ['/export', 'Data Export'],
      ] as const) {
        const response = await client.goto(origin + path);
        baseline[device][path] = response!.status();
        expect(response!.status()).toBe(200);
        if (heading)
          await expect(
            client.getByRole('heading', { name: heading, exact: true })
          ).toBeVisible();
        else await expect(client.locator('main').first()).toBeVisible();
        if (path === '/overview') {
          await noOverflow(client);
          await expect(
            client.getByRole('heading', {
              name: 'Operator journal',
              exact: true,
            })
          ).toHaveCount(0);
          await client.screenshot({
            path: join(evidence, `${device}-overview-baseline.png`),
            fullPage: true,
          });
        }
      }
    }
    proof.baseline = baseline;
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
