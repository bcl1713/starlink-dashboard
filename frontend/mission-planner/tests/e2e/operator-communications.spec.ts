import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, type Page } from '@playwright/test';
import {
  control,
  evidence,
  noOverflow,
  origin,
  ready,
  snapshot,
  mutation,
} from './operator-journal-helpers';
const url = `${origin}/operator?mission_id=synthetic-mission-a`;
const comms = (page: Page) =>
  page.getByRole('region', { name: 'Communications', exact: true });
async function details(page: Page) {
  const summary = comms(page).getByText(
    'Timing, association and optional details',
    { exact: true }
  );
  if (!(await summary.evaluate((el) => el.parentElement?.hasAttribute('open'))))
    await summary.click();
}
async function saveCall(page: Page, held = false) {
  const region = comms(page);
  const response = page.waitForResponse((r) => mutation(r.request()));
  let release!: () => void;
  let fetched!: () => void;
  const hold = new Promise<void>((resolve) => {
    release = resolve;
  });
  const received = new Promise<void>((resolve) => {
    fetched = resolve;
  });
  if (held) {
    let first = true;
    await page.route(`${origin}/api/v2/operator/records**`, async (route) => {
      if (!first || !mutation(route.request())) return route.continue();
      first = false;
      const result = await route.fetch();
      fetched();
      await hold;
      await route.fulfill({ response: result });
    });
  }
  await region.getByRole('button', { name: 'Save call', exact: true }).click();
  if (held) {
    try {
      await received;
      await expect(region.getByText('Saving call…')).toBeVisible();
      await expect(
        region.getByRole('button', { name: 'Save call', exact: true })
      ).toBeDisabled();
      await expect(region.getByText('Call saved.')).toHaveCount(0);
    } finally {
      release();
    }
  }
  const result = await response;
  expect(result.ok()).toBeTruthy();
  const record = (await result.json()).saved_records[0];
  await expect(region.getByText('Call saved.', { exact: true })).toBeVisible();
  expect(
    JSON.parse(control('counts', result.request().headers()['idempotency-key']))
  ).toEqual({ receipts: 1, revisions: 1 });
  return record;
}
async function completed(page: Page) {
  const summary = comms(page).getByText(
    'Completed, canceled and removed calls',
    { exact: true }
  );
  if (!(await summary.evaluate((el) => el.parentElement?.hasAttribute('open'))))
    await summary.click();
}
test('communications requirements and retrospective corrections survive two clients, failures and restart', async ({
  browser,
}) => {
  const proof: Record<string, unknown> = {
    synthetic: true,
    clock: '2026-10-17T16:00:00Z',
    captures: [],
  };
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    const context = await browser.newContext({
      viewport,
      timezoneId: 'Pacific/Honolulu',
      isMobile: viewport.width !== 1920,
      hasTouch: viewport.width !== 1920,
    });
    try {
      await context.route('**/*', (route) =>
        new URL(route.request().url()).origin === origin ||
        route.request().url().startsWith('data:')
          ? route.continue()
          : route.abort()
      );
      const page = await context.newPage();
      await page.goto(url);
      await ready(page);
      const region = comms(page);
      await region
        .getByLabel('Party / participant (optional)')
        .fill(`Synthetic scheduled ${viewport.width}`);
      await region
        .getByLabel('Planned start (UTC)', { exact: true })
        .fill('2026-10-17T23:45:00Z');
      let planned = await saveCall(page, true);
      expect(planned.payload.prep_lead_minutes).toBe(10);
      expect(planned.time.planned_end_at).toBeNull();
      proof.duplicateSubmission = true;
      await details(page);
      await region.getByLabel('Shift amount', { exact: true }).fill('2');
      await region
        .getByLabel('Shift unit', { exact: true })
        .selectOption('hours');
      await region.getByRole('button', { name: 'Apply shift' }).click();
      planned = await saveCall(page);
      expect(planned.time.planned_start_at).toBe('2026-10-18T01:45:00.000000Z');
      expect(planned.time.planned_end_at).toBeNull();
      await expect(
        region
          .getByRole('listitem')
          .filter({
            has: page.getByRole('heading', {
              name: `Synthetic scheduled ${viewport.width}`,
              exact: true,
            }),
          })
          .getByText(/Prepare: 2026-10-18 01:35:00/)
      ).toBeVisible();
      await region
        .getByLabel('Status', { exact: true })
        .selectOption('cancelled');
      await saveCall(page);
      await region
        .getByLabel('Status', { exact: true })
        .selectOption('scheduled');
      await saveCall(page);
      proof.createReschedule = true;
      const conferences = await (
        await page.request.get(
          `${origin}/api/v2/operator/records?mission_id=synthetic-mission-a&record_type=conference`
        )
      ).json();
      const conference = conferences.items[0].record;
      await region
        .getByRole('button', {
          name: 'Log unscheduled/completed call',
          exact: true,
        })
        .click();
      await details(page);
      await region
        .getByLabel('Party / participant (optional)')
        .fill(`Synthetic retrospective ${viewport.width}`);
      await region
        .getByLabel('Actual start (UTC, optional)')
        .fill('2026-10-17T14:30:00Z');
      await region
        .getByLabel('Actual end (UTC, optional)')
        .fill('2026-10-17T14:42:00Z');
      await region
        .getByLabel('Conference record ID (optional)')
        .fill(conference.record_id);
      let retro = await saveCall(page);
      expect(retro.time.planned_start_at).toBeNull();
      expect(retro.payload.prep_lead_minutes).toBeNull();
      await details(page);
      await region
        .getByLabel('Actual end (UTC, optional)')
        .fill('2026-10-17T14:45:00Z');
      await region
        .getByLabel('Party / participant (optional)')
        .fill(`Synthetic corrected ${viewport.width}`);
      await region
        .getByLabel('Scope', { exact: true })
        .selectOption('between_legs');
      await region
        .getByLabel('Previous leg ID (optional)')
        .fill('synthetic-leg-1');
      await region.getByLabel('Next leg ID (optional)').fill('synthetic-leg-2');
      retro = await saveCall(page);
      expect(retro.time.ended_at).toBe('2026-10-17T14:45:00.000000Z');
      expect(retro.payload.prep_lead_minutes).toBeNull();
      const callPath = `${origin}/api/v2/operator/records/${retro.record_id}`;
      const history = await (
        await page.request.get(`${callPath}/history`)
      ).json();
      expect(
        history.items.map(
          (i: { record: { time: { ended_at: string } } }) =>
            i.record.time.ended_at
        )
      ).toEqual(['2026-10-17T14:42:00.000000Z', '2026-10-17T14:45:00.000000Z']);
      proof.retrospectiveCorrection = true;
      await completed(page);
      const row = () =>
        region.getByRole('listitem').filter({
          has: page.getByRole('heading', {
            name: `Synthetic corrected ${viewport.width}`,
            exact: true,
          }),
        });
      await row().getByRole('button', { name: 'Call history' }).click();
      await expect(
        region
          .getByRole('region', { name: 'Entry history' })
          .getByText(/Party \/ participant: Synthetic corrected/)
      ).toBeVisible();
      await row().getByRole('button', { name: 'Remove call' }).click();
      await expect(
        row().getByRole('button', { name: 'Restore call' })
      ).toBeEnabled();
      await row().getByRole('button', { name: 'Restore call' }).click();
      await expect(
        row().getByRole('button', { name: 'Edit call' })
      ).toBeEnabled();
      await expect(row().getByText(/^Prepare:/)).toHaveCount(0);
      expect(
        (
          await (
            await page.request.get(
              `${origin}/api/v2/operator/records/${conference.record_id}`
            )
          ).json()
        ).record
      ).toEqual(conference);
      proof.removeRestore = true;
      proof.conferenceIndependent = true;
      if (viewport.width === 1920) {
        // Two independent clients open the same accepted version.
        const other = await context.newPage();
        await other.goto(url);
        await completed(other);
        const otherRow = comms(other)
          .getByRole('listitem')
          .filter({
            has: other.getByRole('heading', {
              name: 'Synthetic corrected 1920',
              exact: true,
            }),
          });
        await otherRow.getByRole('button', { name: 'Edit call' }).click();
        await row().getByRole('button', { name: 'Edit call' }).click();
        await region
          .getByLabel('Party / participant (optional)')
          .fill('Synthetic first client');
        await saveCall(page);
        await comms(other)
          .getByLabel('Party / participant (optional)')
          .fill('Synthetic stale draft');
        await comms(other)
          .getByRole('button', { name: 'Save call', exact: true })
          .click();
        await expect(comms(other).getByText(/version_conflict/)).toBeVisible();
        await expect(
          comms(other).getByLabel('Party / participant (optional)')
        ).toHaveValue('Synthetic stale draft');
        await comms(other)
          .getByRole('button', { name: 'Reread and use saved call' })
          .click();
        await expect(
          comms(other).getByLabel('Party / participant (optional)')
        ).toHaveValue('Synthetic first client');
        proof.twoClientConflict = true;
        await other.close();
        // An offline save retains a draft and repeats the same idempotency request.
        await details(page);
        await region
          .getByLabel('Notes (optional)')
          .fill('Synthetic offline correction');
        const requests: ReturnType<typeof snapshot>[] = [];
        page.on('request', (request) => {
          if (mutation(request)) requests.push(snapshot(request));
        });
        await context.setOffline(true);
        await region
          .getByRole('button', { name: 'Save call', exact: true })
          .click();
        await expect(
          region.getByRole('button', { name: 'Retry same call save' })
        ).toBeVisible();
        await expect(
          region.getByText('Call saved.', { exact: true })
        ).toHaveCount(0);
        await context.setOffline(false);
        await region
          .getByRole('button', { name: 'Retry same call save' })
          .click();
        await expect(
          region.getByText('Call saved.', { exact: true })
        ).toBeVisible();
        expect(requests[1]).toEqual(requests[0]);
        proof.offlineRetry = true;
        const before = (await (await page.request.get(callPath)).json()).record;
        control('restart');
        await ready(page);
        await page.reload();
        await ready(page);
        expect(
          (await (await page.request.get(callPath)).json()).record
        ).toEqual(before);
        proof.restart = true;
      }
      await noOverflow(page);
      await page
        .getByRole('link', { name: 'Communications', exact: true })
        .click();
      await page.screenshot({
        path: join(
          evidence,
          `communications-${viewport.width}x${viewport.height}.png`
        ),
      });
      (proof.captures as string[]).push(`${viewport.width}x${viewport.height}`);
    } finally {
      await context.close();
    }
  }
  writeFileSync(
    join(evidence, 'communications-proof.json'),
    JSON.stringify(proof, null, 2)
  );
});
