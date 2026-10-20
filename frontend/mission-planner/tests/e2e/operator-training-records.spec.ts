import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, type Locator } from '@playwright/test';
import type { SavedRecord } from '@/types/operator';

const root = process.env.OPERATOR_TRAINING_PROOF_ROOT!;
if (!root?.startsWith('/tmp/issue-376-training-proof-'))
  throw new Error('Owned private course fixture required');

test('guided T02 call lifecycle retains all milestones after a later edit at three sizes', async ({
  page,
}) => {
  test.setTimeout(240_000);
  const missions = await (await page.request.get('/api/v2/missions')).json();
  const id = missions[0].id;
  const receipts: unknown[] = [];
  async function write(action: () => Promise<unknown>): Promise<SavedRecord> {
    const response = page.waitForResponse(
      (value) =>
        /\/api\/v2\/operator\/records(?:\/[^/?]+(?:\/(?:remove|restore))?)?$/.test(
          new URL(value.url()).pathname
        ) && ['POST', 'PUT', 'DELETE'].includes(value.request().method())
    );
    await action();
    const result = await response;
    expect(result.ok(), await result.text()).toBe(true);
    const receipt = await result.json();
    receipts.push(receipt);
    return receipt.saved_records[0];
  }
  async function details(editor: Locator) {
    const summary = editor.getByText(
      'Timing, association and optional details',
      { exact: true }
    );
    if (
      !(await summary.evaluate((node) =>
        node.parentElement?.hasAttribute('open')
      ))
    )
      await summary.click();
  }
  const captures = [];
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto(
      `/operator?workspace=1&mission_id=${id}&view=communications`
    );
    const communications = page.getByRole('region', {
      name: 'Communications',
      exact: true,
    });
    const title = `Fictional complete call exercise ${viewport.width}`;
    await communications
      .getByRole('button', { name: 'Create call', exact: true })
      .click();
    const editor = page.getByRole('dialog');
    await editor.getByLabel('Party / participant (optional)').fill(title);
    await editor
      .getByLabel('Planned start (UTC)', { exact: true })
      .fill('2026-10-17T18:00:00Z');
    await details(editor);
    await editor
      .getByLabel('Preparation lead minutes (blank = unknown)', { exact: true })
      .fill('0');
    let record = await write(() =>
      editor.getByRole('button', { name: 'Save call', exact: true }).click()
    );
    await expect(editor).toHaveCount(0);
    expect(
      record.payload.entry_type === 'call' && record.payload.prep_lead_minutes
    ).toBe(0);
    const row = () =>
      communications.getByRole('listitem').filter({
        has: page.getByRole('heading', {
          name:
            record.payload.entry_type === 'call'
              ? record.payload.party!
              : title,
          exact: true,
        }),
      });
    async function edit() {
      const history = communications.getByText(
        'Completed, canceled and removed calls',
        { exact: true }
      );
      if (
        !(await history.evaluate((node) =>
          node.parentElement?.hasAttribute('open')
        ))
      )
        await history.click();
      await row()
        .getByRole('button', { name: 'Edit call', exact: true })
        .click();
    }
    await edit();
    await editor
      .getByLabel('Planned start (UTC)', { exact: true })
      .fill('2026-10-17T19:00:00Z');
    record = await write(() =>
      editor.getByRole('button', { name: 'Save call', exact: true }).click()
    );
    await expect(editor).toHaveCount(0);
    for (const status of ['cancelled', 'scheduled', 'completed']) {
      await edit();
      await editor.getByLabel('Status', { exact: true }).selectOption(status);
      record = await write(() =>
        editor.getByRole('button', { name: 'Save call', exact: true }).click()
      );
      await expect(editor).toHaveCount(0);
    }
    expect(record.time.occurred_at).toBeNull();
    expect(record.time.ended_at).toBeNull();
    record = await write(() =>
      row().getByRole('button', { name: 'Remove call', exact: true }).click()
    );
    expect(record.deleted).toBe(true);
    record = await write(() =>
      row().getByRole('button', { name: 'Restore call', exact: true }).click()
    );
    expect(record.deleted).toBe(false);
    await edit();
    await editor
      .getByLabel('Party / participant (optional)')
      .fill(`${title} corrected later`);
    record = await write(() =>
      editor.getByRole('button', { name: 'Save call', exact: true }).click()
    );
    await expect(editor).toHaveCount(0);
    expect(record.version).toBe(8);
    await row()
      .getByRole('button', { name: 'Call history', exact: true })
      .click();
    await expect(
      editor.getByRole('heading', { name: 'Record history', exact: true })
    ).toBeVisible();
    await expect(editor.getByText(/Version 8 · update/)).toBeVisible();
    await editor
      .getByRole('button', { name: 'Close', exact: true })
      .last()
      .click();
    await expect(editor).toHaveCount(0);
    await page.reload();
    const help = page.getByRole('button', { name: 'Help', exact: true });
    if (!(await help.isVisible()))
      await page.getByRole('button', { name: 'Tools', exact: true }).click();
    await help.click();
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
      .click();
    const guide = page.getByRole('complementary', {
      name: 'Guided mission walkthrough',
    });
    await guide
      .getByRole('combobox', { name: 'Lesson', exact: true })
      .selectOption('T02');
    await guide
      .getByRole('button', { name: 'Check current evidence', exact: true })
      .click();
    await expect(
      guide.getByRole('status').filter({ hasText: /^Passed$/ })
    ).toBeVisible();
    await expect(
      guide
        .getByRole('listitem')
        .filter({ hasText: 'Verified from current data' })
    ).toHaveCount(8);
    await page.screenshot({
      path: join(
        root,
        `guided-call-lifecycle-${viewport.width}x${viewport.height}.png`
      ),
    });
    await guide
      .getByRole('combobox', { name: 'Lesson', exact: true })
      .selectOption('T11');
    await guide
      .getByRole('button', { name: 'Check current evidence', exact: true })
      .click();
    await expect(
      guide
        .getByRole('listitem')
        .filter({ hasText: 'immutable history complete' })
    ).toContainText('Verified from current data');
    await expect(
      guide.getByRole('status').filter({ hasText: /^Incomplete$/ })
    ).toBeVisible();
    captures.push({ viewport, record, completeImmutableHistoryVerified: true });
    await guide
      .getByRole('button', { name: 'Dismiss guide', exact: true })
      .click();
  }
  writeFileSync(
    join(root, 'guided-call-lifecycle-proof.json'),
    JSON.stringify(
      {
        synthetic: true,
        captures,
        receipts,
        actualWrites: receipts.length,
        manualHumanFirstUse: 'not claimed',
      },
      null,
      2
    )
  );
});
