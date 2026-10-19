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
      if (viewport.width === 390) {
        await editor
          .getByLabel('Time precision', { exact: true })
          .selectOption('approximate');
        await editor
          .getByLabel('Occurred at (UTC)', { exact: true })
          .fill('2026-10-17T17:05:00Z');
      }
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
      if (viewport.width === 1920) {
        for (let index = 0; index < 6; index++) {
          await resume(other);
          await editor
            .getByLabel('Note', { exact: true })
            .fill(`Later retained work ${index}`);
          await park();
          await check();
        }
        await guide
          .getByRole('combobox', { name: 'Lesson', exact: true })
          .selectOption('T08');
        for (const outcome of [
          'draft switch retained',
          'offline draft retained',
        ])
          await expect(
            guide.getByRole('listitem').filter({ hasText: outcome })
          ).toContainText('Verified from retained source observation');
        await guide
          .getByRole('combobox', { name: 'Lesson', exact: true })
          .selectOption('T11');
        await expect(
          guide
            .getByRole('listitem')
            .filter({ hasText: 'storage unavailable recovery' })
        ).toContainText('Verified from retained source observation');
      }
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

test('guide verifies a real counterpart conflict, explicit reread and a new reviewed command at three sizes', async ({
  page,
  browser,
}) => {
  const missions = await (await page.request.get('/api/v2/missions')).json();
  const id = missions[0].id;
  const proofs = [];
  const editor = page.getByRole('dialog');
  const guide = page.getByRole('complementary', {
    name: 'Guided mission walkthrough',
  });
  async function check() {
    const button = guide.getByRole('button', {
      name: 'Check current evidence',
      exact: true,
    });
    await button.click();
    await expect(button).toBeEnabled();
  }
  async function openGuide() {
    await page.getByRole('button', { name: 'Help', exact: true }).click();
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Guided mission walkthrough', exact: true })
      .click();
    await guide
      .getByRole('combobox', { name: 'Lesson', exact: true })
      .selectOption('T08');
  }
  async function observation(recordId: string) {
    return page.evaluate((recordId) => {
      const progress = Array.from(
        { length: localStorage.length },
        (_, index) => localStorage.key(index)!
      )
        .filter((key) => key.startsWith('operator-training-progress:'))
        .map((key) => JSON.parse(localStorage.getItem(key)!));
      return progress
        .flatMap((item) => item.conflictObservations ?? [])
        .find((item) => item.request.command.record_id === recordId);
    }, recordId);
  }
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto(`/operator?workspace=1&mission_id=${id}&view=notes`);
    const title = `Fictional reviewed conflict ${viewport.width}`;
    await page.getByRole('button', { name: 'Note', exact: true }).click();
    await editor.getByLabel('Title', { exact: true }).fill(title);
    const creating = page.waitForResponse(
      (r) =>
        r.request().method() === 'POST' &&
        r.url().endsWith('/api/v2/operator/records')
    );
    await editor
      .getByRole('button', { name: 'Save entry', exact: true })
      .click();
    const createdResponse = await creating;
    expect(createdResponse.ok()).toBe(true);
    const created = await createdResponse.json();
    const recordId = created.saved_records[0].record_id;
    await expect(editor).toHaveCount(0);
    await openGuide();
    await page
      .getByRole('button', { name: `Edit ${title}`, exact: true })
      .click();
    await editor
      .getByLabel('Note', { exact: true })
      .fill('Learner retained input after reviewing counterpart');
    const peer = await browser.newContext({
      baseURL: process.env.OPERATOR_TRAINING_ORIGIN,
      viewport,
    });
    try {
      const peerPage = await peer.newPage();
      await peerPage.goto(`/operator?workspace=1&mission_id=${id}&view=notes`);
      await peerPage
        .getByRole('button', { name: `Edit ${title}`, exact: true })
        .click();
      const peerEditor = peerPage.getByRole('dialog');
      await peerEditor
        .getByLabel('Note', { exact: true })
        .fill('Genuine second-client update');
      const peerSaving = peerPage.waitForResponse(
        (r) =>
          r.request().method() === 'PUT' &&
          r.url().endsWith(`/api/v2/operator/records/${recordId}`)
      );
      await peerEditor
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      const peerResponse = await peerSaving;
      expect(peerResponse.ok()).toBe(true);
      const counterpart = await peerResponse.json();
      expect(counterpart.saved_records[0].version).toBe(2);
      await expect(peerEditor).toHaveCount(0);
      const failing = page.waitForResponse(
        (r) =>
          r.request().method() === 'PUT' &&
          r.url().endsWith(`/api/v2/operator/records/${recordId}`)
      );
      await editor
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      const conflict = await failing;
      expect(conflict.status()).toBe(409);
      const error = await conflict.json();
      expect(error.error.code).toBe('version_conflict');
      const rejectedRequest = {
        body: conflict.request().postDataJSON(),
        key: conflict.request().headers()['idempotency-key'],
      };
      expect(rejectedRequest.body.expected_version).toBe(1);
      await editor
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      await expect(editor).toHaveCount(0);
      await check();
      await expect
        .poll(async () => (await observation(recordId))?.request.key)
        .toBe(rejectedRequest.key);
      expect((await observation(recordId)).replacement).toBeUndefined();
      const reread = page.waitForResponse(
        (r) =>
          r.request().method() === 'GET' &&
          r.url().endsWith(`/api/v2/operator/records/${recordId}`)
      );
      await page
        .getByRole('region', { name: 'Save status', exact: true })
        .getByRole('button', { name: 'Reread and reconcile', exact: true })
        .click();
      expect((await reread).ok()).toBe(true);
      await expect(
        page.getByRole('region', { name: 'Save status', exact: true })
      ).toContainText('Saved state reread');
      await check();
      await expect
        .poll(
          async () => (await observation(recordId))?.reviewedCurrent?.version
        )
        .toBe(2);
      await page
        .getByRole('region', { name: 'Retained drafts', exact: true })
        .getByRole('button', { name: new RegExp(title) })
        .click();
      await expect(editor.getByLabel('Note', { exact: true })).toHaveValue(
        'Learner retained input after reviewing counterpart'
      );
      await editor
        .getByRole('button', {
          name: 'Keep my input using current version 2 as base',
          exact: true,
        })
        .click();
      const accepting = page.waitForResponse(
        (r) =>
          r.request().method() === 'PUT' &&
          r.url().endsWith(`/api/v2/operator/records/${recordId}`)
      );
      await editor
        .getByRole('button', { name: 'Save entry', exact: true })
        .click();
      const acceptedResponse = await accepting;
      expect(acceptedResponse.ok()).toBe(true);
      const accepted = await acceptedResponse.json();
      expect(accepted.saved_records[0].version).toBe(3);
      expect(acceptedResponse.request().headers()['idempotency-key']).not.toBe(
        rejectedRequest.key
      );
      expect(acceptedResponse.request().postDataJSON().expected_version).toBe(
        2
      );
      await expect(editor).toHaveCount(0);
      await check();
      await expect
        .poll(
          async () =>
            (await observation(recordId))?.replacement?.receipt?.command_id
        )
        .toBe(accepted.command_id);
      const history = await (
        await page.request.get(`/api/v2/operator/records/${recordId}/history`)
      ).json();
      expect(
        history.items.map(
          (item: { record: { version: number } }) => item.record.version
        )
      ).toEqual([1, 2, 3]);
      await page.reload();
      await openGuide();
      await check();
      await expect(
        guide
          .getByRole('listitem')
          .filter({ hasText: 'real conflict reconciled' })
      ).toContainText('Verified from retained source observation');
      await expect(
        guide.getByRole('status').filter({ hasText: /^Incomplete$/ })
      ).toBeVisible();
      await page.screenshot({
        path: join(
          root,
          `guided-conflict-recovery-${viewport.width}x${viewport.height}.png`
        ),
      });
      proofs.push({
        viewport,
        created,
        counterpart,
        rejectedRequest,
        error,
        accepted,
        history,
        observation: await observation(recordId),
      });
    } finally {
      await peer.close();
    }
  }
  writeFileSync(
    join(root, 'guided-conflict-recovery-proof.json'),
    JSON.stringify(
      { synthetic: true, proofs, manualObservations: 'not claimed' },
      null,
      2
    )
  );
});
