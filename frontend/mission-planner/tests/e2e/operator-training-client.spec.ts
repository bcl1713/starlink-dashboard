import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
const root = process.env.OPERATOR_TRAINING_PROOF_ROOT!;
if (!root?.startsWith('/tmp/issue-376-training-proof-'))
  throw new Error('Owned private training root required');

test('guide revalidates scoped parked drafts, actual browser offline recovery and unavailable draft storage', async ({
  page,
  context,
}) => {
  const missions = await (await page.request.get('/api/v2/missions')).json();
  const mission = await (
    await page.request.get(`/api/v2/missions/${missions[0].id}`)
  ).json();
  const proofs = [];
  const editor = page.getByRole('dialog');
  const guide = page.getByRole('complementary', {
    name: 'Guided mission walkthrough',
  });
  async function openGuide() {
    await page.getByRole('button', { name: 'Help', exact: true }).click();
    await page
      .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
      .click();
    await guide
      .getByRole('combobox', { name: 'Lesson', exact: true })
      .selectOption('T08');
  }
  async function check() {
    const button = guide.getByRole('button', {
      name: 'Check current evidence',
      exact: true,
    });
    await button.click();
    await expect(button).toBeEnabled();
  }
  async function park() {
    await editor
      .getByRole('button', { name: 'Keep draft and return', exact: true })
      .click();
    await expect(editor).toHaveCount(0);
  }
  async function resume(title: string) {
    await page
      .getByRole('region', { name: 'Retained drafts', exact: true })
      .getByRole('button', { name: new RegExp(title) })
      .click();
    await expect(editor.getByLabel('Title', { exact: true })).toHaveValue(
      title
    );
  }
  async function save() {
    const saved = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().endsWith('/api/v2/operator/records')
    );
    await editor
      .getByRole('button', { name: 'Save entry', exact: true })
      .click();
    const response = await saved;
    expect(response.ok()).toBe(true);
    const receipt = await response.json();
    await expect(editor).toHaveCount(0);
    const history = await (
      await page.request.get(
        `/api/v2/operator/records/${receipt.saved_records[0].record_id}/history`
      )
    ).json();
    expect(history.items).toHaveLength(1);
    expect(history.items[0].record).toEqual(receipt.saved_records[0]);
    return receipt;
  }
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto(`/operator?workspace=1&mission_id=${mission.id}`);
    await openGuide();
    const title = `Fictional parked recovery ${viewport.width}`;
    const other = `Fictional other scope ${viewport.width}`;
    const stored = `Fictional storage recovery ${viewport.width}`;
    try {
      await page.getByRole('button', { name: 'Note', exact: true }).click();
      await editor.getByLabel('Title', { exact: true }).fill(title);
      await park();
      await check();
      await page.getByRole('button', { name: 'Note', exact: true }).click();
      await editor.getByLabel('Title', { exact: true }).fill(other);
      await editor
        .getByRole('combobox', { name: 'Draft scope', exact: true })
        .selectOption('leg');
      await editor
        .getByRole('combobox', { name: 'Leg', exact: true })
        .selectOption(mission.legs[1].id);
      await park();
      await check();
      await expect(
        guide.getByRole('listitem').filter({ hasText: 'draft switch retained' })
      ).toContainText('Verified from retained source observation');
      await context.setOffline(true);
      await resume(title);
      await editor
        .getByLabel('Title', { exact: true })
        .fill(title + ' offline');
      await park();
      await check();
      await expect(guide.getByRole('alert')).toContainText(
        'Offline: retain the draft'
      );
      await expect(
        guide.getByRole('status').filter({ hasText: /^Evidence unavailable$/ })
      ).toBeVisible();
      await context.setOffline(false);
      await page.reload();
      await openGuide();
      await check();
      await resume(title + ' offline');
      const offlineReceipt = await save();
      await check();
      await expect(
        guide
          .getByRole('listitem')
          .filter({ hasText: 'offline draft retained' })
      ).toContainText('Verified from retained source observation');
      await expect(
        guide.getByRole('listitem').filter({ hasText: 'Human observation' })
      ).toHaveCount(0);
      const quotaReached = await page.evaluate(() => {
        const trainingWindow = window as typeof window & {
          restoreTrainingStorage?: () => void;
        };
        const ownedKeys: string[] = [];
        const prefix = 'operator-training-quota:' + crypto.randomUUID() + ':';
        trainingWindow.restoreTrainingStorage = () => {
          for (const key of ownedKeys) sessionStorage.removeItem(key);
        };
        let full = false;
        // Fill only this disposable browser's storage, then consume the small
        // remainder so creating a normal draft really encounters native quota.
        for (const size of [65536, 256]) {
          for (let index = 0; index < 256; index++) {
            const key = prefix + ownedKeys.length;
            ownedKeys.push(key);
            try {
              sessionStorage.setItem(key, 'x'.repeat(size));
            } catch (error) {
              if (
                !(error instanceof DOMException) ||
                error.name !== 'QuotaExceededError'
              )
                throw error;
              full = true;
              break;
            }
          }
        }
        return full;
      });
      expect(quotaReached).toBe(true);
      await page.getByRole('button', { name: 'Note', exact: true }).click();
      await editor.getByLabel('Title', { exact: true }).fill(stored);
      await expect(editor).toContainText(
        'Draft could not be retained across reload'
      );
      await park();
      await guide
        .getByRole('combobox', { name: 'Lesson', exact: true })
        .selectOption('T11');
      await check();
      await page.evaluate(() => {
        const trainingWindow = window as typeof window & {
          restoreTrainingStorage?: () => void;
        };
        trainingWindow.restoreTrainingStorage?.();
        delete trainingWindow.restoreTrainingStorage;
      });
      await resume(stored);
      await editor
        .getByLabel('Title', { exact: true })
        .fill(stored + ' temporary');
      await editor.getByLabel('Title', { exact: true }).fill(stored);
      await park();
      await check();
      await resume(stored);
      const storageReceipt = await save();
      await check();
      await expect(
        guide
          .getByRole('listitem')
          .filter({ hasText: 'storage unavailable recovery' })
      ).toContainText('Verified from retained source observation');
      await expect(
        guide.getByRole('status').filter({ hasText: /^Incomplete$/ })
      ).toBeVisible();
      await page.screenshot({
        path: join(
          root,
          `guided-client-recovery-${viewport.width}x${viewport.height}.png`
        ),
      });
      proofs.push({
        viewport,
        offlineReceipt,
        storageReceipt,
        parkedOtherDraftIsNotASavedRecord: true,
      });
    } finally {
      await context.setOffline(false);
      await page
        .evaluate(() => {
          const trainingWindow = window as typeof window & {
            restoreTrainingStorage?: () => void;
          };
          trainingWindow.restoreTrainingStorage?.();
          delete trainingWindow.restoreTrainingStorage;
        })
        .catch(() => {});
    }
  }
  writeFileSync(
    join(root, 'guided-client-recovery-proof.json'),
    JSON.stringify(
      { synthetic: true, proofs, manualObservations: 'not claimed' },
      null,
      2
    )
  );
});
