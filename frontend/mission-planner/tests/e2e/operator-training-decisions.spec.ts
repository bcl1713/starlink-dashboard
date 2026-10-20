import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, type Locator } from '@playwright/test';
import type { SavedRecord } from '@/types/operator';

const root = process.env.OPERATOR_TRAINING_PROOF_ROOT!;
if (!root?.startsWith('/tmp/issue-376-training-proof-'))
  throw new Error('Owned private training instance required');

test('guided T06/T07 preserve transport checks and independent issue/capability history at three sizes', async ({
  page,
}) => {
  test.setTimeout(300_000);
  const missions = await (await page.request.get('/api/v2/missions')).json();
  const id = missions[0].id;
  const receipts: unknown[] = [];
  const captures = [];
  const editor = page.getByRole('dialog');
  async function write(action: () => Promise<unknown>): Promise<SavedRecord> {
    const response = page.waitForResponse(
      (result) =>
        ['POST', 'PUT'].includes(result.request().method()) &&
        /\/api\/v2\/operator\/records(?:\/[^/?]+)?$/.test(
          new URL(result.url()).pathname
        )
    );
    await action();
    const result = await response;
    expect(result.ok(), await result.text()).toBe(true);
    const receipt = await result.json();
    receipts.push(receipt);
    return receipt.saved_records[0];
  }
  async function save(name: string) {
    const record = await write(() =>
      editor.getByRole('button', { name, exact: true }).click()
    );
    await expect(editor).toHaveCount(0);
    return record;
  }
  async function verify(stage: string, width: number, height: number) {
    await page.reload();
    const help = page.getByRole('button', { name: 'Help', exact: true });
    if (!(await help.isVisible()))
      await page.getByRole('button', { name: 'Tools', exact: true }).click();
    await help.click();
    await editor
      .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
      .click();
    const guide = page.getByRole('complementary', {
      name: 'Guided mission walkthrough',
      exact: true,
    });
    await guide
      .getByRole('combobox', { name: 'Lesson', exact: true })
      .selectOption(stage);
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
    ).toHaveCount(4);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1
      )
    ).toBe(true);
    await page.screenshot({
      path: join(root, `guided-${stage}-${width}x${height}.png`),
    });
    await guide
      .getByRole('button', { name: 'Dismiss guide', exact: true })
      .click();
  }
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto(`/operator?workspace=1&mission_id=${id}&view=issues`);
    const title = `Fictional training audio issue ${viewport.width}`;
    await page.getByRole('button', { name: 'New issue', exact: true }).click();
    await editor.getByLabel('Problem description').fill(title);
    await editor
      .locator('summary')
      .filter({ hasText: 'Optional issue details' })
      .click();
    await editor
      .getByLabel('Mitigation', { exact: true })
      .selectOption('workaround');
    await editor.getByLabel('Follow-up UTC').fill('2026-10-17T16:50');
    await editor.screenshot({
      path: join(
        root,
        `training-issue-editor-${viewport.width}x${viewport.height}.png`
      ),
    });
    const initial = await save('Save issue');
    const issue = page.getByRole('article', {
      name: `Issue ${title}`,
      exact: true,
    });
    await write(() =>
      issue.getByRole('button', { name: 'Monitor', exact: true }).click()
    );
    await issue
      .getByRole('button', { name: 'Add update / follow up', exact: true })
      .click();
    await editor
      .getByLabel('Add update', { exact: true })
      .fill('Fictional workaround observation');
    await save('Save issue');
    const resolved = await write(() =>
      issue.getByRole('button', { name: 'Resolve', exact: true }).click()
    );
    expect(
      resolved.payload.entry_type === 'issue' && resolved.payload.follow_up_at
    ).toBeNull();
    const resolvedSection = page.getByText('Resolved issues', { exact: true });
    if (
      !(await resolvedSection.evaluate((node) =>
        node.parentElement?.hasAttribute('open')
      ))
    )
      await resolvedSection.click();
    const reopened = await write(() =>
      issue.getByRole('button', { name: 'Reopen', exact: true }).click()
    );
    expect(
      reopened.payload.entry_type === 'issue' && reopened.payload.follow_up_at
    ).toBeNull();
    await issue
      .getByRole('button', { name: 'Issue activity', exact: true })
      .click();
    await editor
      .getByRole('button', { name: 'Correct this update', exact: true })
      .click();
    await editor
      .getByLabel('Corrected update', { exact: true })
      .fill('Corrected fictional workaround wording only');
    const corrected = await save('Save correction');
    expect(corrected.payload).toMatchObject({
      status: 'reopened',
      mitigation: 'workaround',
      follow_up_at: null,
      corrects_version: 3,
    });
    await page
      .getByRole('button', { name: 'Record manual assessment', exact: true })
      .click();
    await editor
      .getByLabel('Capability name', { exact: true })
      .fill(`Fictional audio assessment ${viewport.width}`);
    await editor
      .getByLabel('Functional capability', { exact: true })
      .selectOption('degraded');
    const capability = await save('Save assessment');
    expect(capability.payload).toMatchObject({
      functional_status: 'degraded',
      redundancy_status: 'unknown',
      redundancy_observed_at: null,
    });
    await verify('T07', viewport.width, viewport.height);

    await page
      .getByRole('navigation', { name: 'Operator workspace' })
      .getByRole('button', { name: 'Transport', exact: true })
      .click();
    const transport = page.getByRole('region', {
      name: 'Transport',
      exact: true,
    });
    const service = `Fictional IPTV ${viewport.width}`;
    const customers = await (
      await page.request.get(
        `/api/v2/operator/records?mission_id=${id}&record_type=participation`
      )
    ).json();
    expect(
      customers.items.some(
        (item: { record: SavedRecord }) =>
          !item.record.deleted &&
          item.record.payload.entry_type === 'participation' &&
          item.record.payload.state === 'connected'
      )
    ).toBe(true);
    await transport
      .getByRole('button', { name: 'Record another move', exact: true })
      .click();
    await editor.getByLabel('Service 1', { exact: true }).fill(service);
    await editor.getByLabel('Reported Applied 1', { exact: true }).check();
    await editor
      .getByLabel('Applied transport 1', { exact: true })
      .selectOption('Ka');
    let decision = await save('Save transport decision');
    expect(decision.payload).toMatchObject({
      services: [
        {
          intended: null,
          requested: null,
          applied: { transport: 'Ka' },
          checked: null,
        },
      ],
    });
    const card: Locator = transport
      .getByRole('listitem')
      .filter({ hasText: service });
    await card
      .getByRole('button', { name: 'Correct this decision', exact: true })
      .click();
    await editor.getByLabel('Operator Checked 1', { exact: true }).check();
    await editor
      .getByLabel('Check result 1', { exact: true })
      .selectOption('satisfactory');
    await editor
      .getByRole('button', { name: 'Add service', exact: true })
      .click();
    await editor
      .getByLabel('Service 2', { exact: true })
      .fill(`Fictional secure voice ${viewport.width}`);
    await editor.getByLabel('Reported Applied 2', { exact: true }).check();
    await editor
      .getByLabel('Applied transport 2', { exact: true })
      .selectOption('Starshield');
    await editor.getByLabel('Operator Checked 2', { exact: true }).check();
    await editor
      .getByLabel('Check result 2', { exact: true })
      .selectOption('issue_reported');
    await editor.screenshot({
      path: join(
        root,
        `training-independent-checks-${viewport.width}x${viewport.height}.png`
      ),
    });
    decision = await save('Save transport decision');
    expect(decision.payload.entry_type).toBe('transport_decision');
    await card
      .getByRole('button', { name: 'Correct this decision', exact: true })
      .click();
    await editor
      .getByLabel('Applied transport 1', { exact: true })
      .selectOption('X');
    await expect(
      editor.getByLabel('Operator Checked 1', { exact: true })
    ).not.toBeChecked();
    await expect(
      editor.getByLabel('Operator Checked 2', { exact: true })
    ).toBeChecked();
    const replaced = await save('Save transport decision');
    expect(replaced.payload).toMatchObject({
      services: [
        { applied: { transport: 'X' }, checked: null },
        { checked: { result: 'issue_reported' } },
      ],
    });
    await card
      .getByRole('button', { name: 'Correct this decision', exact: true })
      .click();
    await editor.getByLabel('Operator Checked 1', { exact: true }).check();
    await editor
      .getByLabel('Check result 1', { exact: true })
      .selectOption('satisfactory');
    decision = await save('Save transport decision');
    expect(decision.version).toBe(4);
    await verify('T06', viewport.width, viewport.height);
    captures.push({
      viewport,
      issueId: initial.record_id,
      corrected,
      capability,
      decision,
    });
  }
  writeFileSync(
    join(root, 'guided-decisions-issues-proof.json'),
    JSON.stringify(
      {
        synthetic: true,
        actualWrites: receipts.length,
        captures,
        receipts,
        manualHumanFirstUse: 'not claimed',
      },
      null,
      2
    )
  );
});
