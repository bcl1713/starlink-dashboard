import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
const root = process.env.OPERATOR_TRAINING_PROOF_ROOT!;
const source = process.env.OPERATOR_TRAINING_TEST_SOURCE!;
if (!root?.startsWith('/tmp/issue-376-training-proof-'))
  throw new Error('Owned disposable training root required');
function host(command: string, ...args: string[]) {
  const raw = execFileSync(
    'python3',
    [
      join(source, 'tools/training/operator-mission/launcher.py'),
      command,
      '--root',
      root,
      ...args,
    ],
    { encoding: 'utf8', timeout: 240_000 }
  );
  return JSON.parse(raw.trim().split('\n').at(-1)!);
}
test('native backup restore changes epoch and quarantines an actual lost-receipt request without resending', async ({
  page,
}) => {
  const initial = await (
    await page.request.get('/api/v2/operator/health')
  ).json();
  const missions = await (await page.request.get('/api/v2/missions')).json();
  const missionId = missions[0].id;
  const origin = process.env.OPERATOR_TRAINING_ORIGIN!;
  const editor = page.getByRole('dialog');
  const guide = page.getByRole('complementary', {
    name: 'Guided mission walkthrough',
  });
  await page.goto(`/operator?workspace=1&mission_id=${missionId}&view=notes`);
  await page.getByRole('button', { name: 'Note', exact: true }).click();
  await editor
    .getByRole('textbox', { name: 'Title', exact: true })
    .fill('Fictional retained backup note');
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().endsWith('/api/v2/operator/records')
  );
  await editor.getByRole('button', { name: 'Save entry', exact: true }).click();
  const kept = await (await saved).json();
  await expect(editor).toHaveCount(0);
  const backup = host('journal-backup', '--browser-origin', origin);
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await page
    .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
    .click();
  await guide
    .getByRole('combobox', { name: 'Lesson', exact: true })
    .selectOption('T08');
  await guide
    .getByRole('button', { name: 'Arm one note receipt loss', exact: true })
    .click();
  await expect(guide).toContainText('Armed for 60 seconds');
  await page.getByRole('button', { name: 'Note', exact: true }).click();
  await editor
    .getByRole('textbox', { name: 'Title', exact: true })
    .fill('Fictional discarded lost receipt');
  const attempts: unknown[] = [];
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
  const realResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().endsWith('/api/v2/operator/records')
  );
  await editor.getByRole('button', { name: 'Save entry', exact: true }).click();
  const observedResponse = await realResponse;
  expect(observedResponse.ok()).toBe(true);
  const committed = await observedResponse.json();
  await expect(editor).toContainText(/uncertain/i);
  await editor
    .getByRole('button', { name: 'Keep draft and return', exact: true })
    .click();
  const pendingBefore = await page.evaluate(() =>
    Object.keys(sessionStorage)
      .filter((key) => key.startsWith('operator-workspace-pending:v1:'))
      .map((key) => JSON.parse(sessionStorage.getItem(key)!))
  );
  expect(pendingBefore).toHaveLength(1);
  const restored = host(
    'journal-restore',
    '--manifest',
    backup.manifest,
    '--browser-origin',
    origin
  );
  expect(restored.health.store_id).toBe(initial.store_id);
  expect(restored.health.api_epoch).not.toBe(initial.api_epoch);
  // Reload is a supported crash/reopen recovery path. It reloads the exact old
  // pending envelope; the current health poll quarantines it without any POST.
  await page.reload();
  await expect(
    page.getByRole('region', { name: 'Save status', exact: true })
  ).toContainText('quarantined');
  await expect(
    page.getByRole('button', { name: 'Retry same save', exact: true })
  ).toBeDisabled();
  const pendingAfter = await page.evaluate(() =>
    Object.keys(sessionStorage)
      .filter((key) => key.startsWith('operator-workspace-pending:v1:'))
      .map((key) => JSON.parse(sessionStorage.getItem(key)!))
  );
  expect(pendingAfter).toEqual(pendingBefore);
  expect(attempts).toHaveLength(1);
  const proofs = [];
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    await page.setViewportSize(viewport);
    await page.getByRole('button', { name: 'Help', exact: true }).click();
    await page
      .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
      .click();
    await guide
      .getByRole('combobox', { name: 'Lesson', exact: true })
      .selectOption('T08');
    await guide
      .getByLabel('Native recovery report', { exact: true })
      .setInputFiles(restored.evidence);
    await expect(
      guide.getByRole('listitem').filter({ hasText: 'private backup restored' })
    ).toContainText('Verified from imported tooling evidence');
    await guide
      .getByRole('combobox', { name: 'Lesson', exact: true })
      .selectOption('T11');
    await guide
      .getByRole('button', { name: 'Check current evidence', exact: true })
      .click();
    await expect(
      guide.getByRole('region', {
        name: 'Optional provider reads',
        exact: true,
      })
    ).toContainText(/Radar: (off|ready|unavailable)/);
    await expect(
      guide
        .getByRole('listitem')
        .filter({ hasText: 'optional provider branches' })
    ).toContainText('Verified from current data');
    await expect(
      guide.getByRole('listitem').filter({ hasText: 'epoch change quarantine' })
    ).toContainText('Verified from imported tooling evidence');
    await expect(guide.getByRole('status', { exact: true })).toContainText(
      'Incomplete'
    );
    await page.screenshot({
      path: join(
        root,
        `guided-native-recovery-${viewport.width}x${viewport.height}.png`
      ),
      fullPage: true,
    });
    proofs.push({ viewport, pendingUnchanged: pendingAfter });
    await page.reload();
  }
  expect(attempts).toHaveLength(1);
  const fields = await page.request.get('/operator-help/field-branches.html');
  expect(fields.ok()).toBe(true);
  const branchReference = await fields.text();
  expect(branchReference.match(/<code>/g)).toHaveLength(323);
  expect(branchReference).toContain('journal.note_text');
  const rows = await (
    await page.request.get(
      `/api/v2/operator/records?mission_id=${missionId}&include_removed=true`
    )
  ).json();
  expect(
    rows.items.some(
      (item: { record: { record_id: string } }) =>
        item.record.record_id === kept.saved_records[0].record_id
    )
  ).toBe(true);
  expect(
    rows.items.some(
      (item: { record: { payload: { title: string } } }) =>
        item.record.payload.title === 'Fictional discarded lost receipt'
    )
  ).toBe(false);
  writeFileSync(
    join(root, 'guided-native-recovery-proof.json'),
    JSON.stringify(
      {
        synthetic: true,
        initial,
        kept,
        committed,
        attempts,
        backup,
        restored,
        report: JSON.parse(readFileSync(restored.evidence, 'utf8')),
        proofs,
      },
      null,
      2
    )
  );
});
