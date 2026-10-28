import {
  test,
  expect,
  type Page,
  type BrowserContext,
  type Response,
} from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';
import { json, seed, raw } from './operator-coherent-fixture';
import { unknownTime } from '../../src/components/operator/conferenceCommands';
import type { CommandReceipt, OperatorInput } from '../../src/types/operator';

const evidence = process.env.OPERATOR_SYNC_EVIDENCE!;
const mutatesRecord = (response: Response) =>
  ['POST', 'PUT'].includes(response.request().method()) &&
  /\/api\/v2\/operator\/records(?:\/|$)/.test(new URL(response.url()).pathname);
const card = (page: Page, id: string) => page.locator(`#operator-record-${id}`);
async function zulu(page: Page, label: string, at: string) {
  await page
    .getByLabel(`${label} date (Zulu)`, { exact: true })
    .fill(at.slice(0, 10));
  await page
    .getByLabel(new RegExp(`^${label} hour \\(Zulu\\)`))
    .selectOption(at.slice(11, 13));
  await page
    .getByLabel(new RegExp(`^${label} minute \\(Zulu\\)`))
    .selectOption(at.slice(14, 16));
}
async function timeline(page: Page, title: string) {
  const compact = page.getByRole('button', {
    name: 'Open mission timeline',
    exact: true,
  });
  const narrow = await compact.isVisible();
  if (narrow) await compact.click();
  await expect(
    page
      .getByRole('button', { name: `Focus Prepare: ${title}`, exact: true })
      .first()
  ).toBeVisible();
  if (narrow) await page.keyboard.press('Escape');
}
async function schedule(
  page: Page,
  title: string,
  at: string,
  conferenceId?: string
) {
  await page
    .getByRole('button', { name: 'Schedule Call', exact: true })
    .click();
  await page
    .getByLabel('Party / Participant (Optional)', { exact: true })
    .fill(title);
  await zulu(page, 'Planned Start', at);
  await page.getByLabel(/Duration Minutes/i).fill('20');
  await page.getByLabel(/Preparation Lead Minutes/i).fill('10');
  if (conferenceId)
    await page
      .getByLabel('Conference (Optional)', { exact: true })
      .selectOption(conferenceId);
  await page.getByRole('button', { name: 'Save Call', exact: true }).click();
}
async function openCallDetails(page: Page, id: string) {
  const summary = card(page, id).getByText('Call Details', { exact: true });
  if (
    !(await summary.evaluate(
      (el) => (el.closest('details') as HTMLDetailsElement).open
    ))
  )
    await summary.click();
}
async function editor(page: Page, id: string) {
  await openCallDetails(page, id);
  await card(page, id)
    .getByRole('button', { name: 'Reschedule', exact: true })
    .click();
}
async function navigate(page: Page, path: string) {
  await page.evaluate((path) => {
    history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }, path);
}

test('saved records converge across independent laptop and phone contexts with safe recovery', async ({
  browser,
  request,
}) => {
  const contexts: BrowserContext[] = [];
  const latencies: { operation: string; ms: number }[] = [];
  const requestLog: {
    client: string;
    method: string;
    path: string;
    at: number;
  }[] = [];
  const proof: Record<string, unknown> = {
    synthetic: true,
    productionAPIs: true,
    latencies,
    browserVersion: browser.version(),
    errors: [],
  };
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  let pending = Promise.resolve();
  let backendStopped = false;
  const control = (action: 'stop' | 'start') =>
    execFileSync(
      'python3',
      ['../../tools/acceptance/operator-record-sync/control.py', action],
      { env: process.env, timeout: 75_000, encoding: 'utf8' }
    );
  try {
    const { missionId } = await seed(request);
    heartbeat = setInterval(() => {
      pending = pending.then(() => raw(request, 1764)).then(() => {});
    }, 2000);
    const health = await json<{ api_epoch: string }>(
      await request.get('/api/v2/operator/health')
    );
    const create = async (input: OperatorInput) =>
      json<CommandReceipt>(
        await request.post('/api/v2/operator/records', {
          headers: {
            'Idempotency-Key': randomUUID(),
            'X-Operator-Store-Epoch': health.api_epoch,
          },
          data: input,
        })
      );
    // Force a real second snapshot page before clients open. Delta polling must
    // keep the captured page cursor usable and avoid rereading this history.
    for (let n = 0; n < 55; n++)
      await create({
        schema_version: 1,
        record_type: 'journal_entry',
        mission_id: missionId,
        scope: 'mission',
        leg_id: null,
        time: { ...unknownTime },
        payload: {
          schema_version: 1,
          entry_type: 'note',
          title: `Synthetic pagination ${n}`,
          note: 'Local acceptance only',
          previous_leg_id: null,
          next_leg_id: null,
        },
      });
    const laptopContext = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
    });
    contexts.push(laptopContext);
    const phoneContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    });
    contexts.push(phoneContext);
    const laptop = await laptopContext.newPage();
    const phone = await phoneContext.newPage();
    for (const [name, page] of [
      ['laptop', laptop],
      ['phone', phone],
    ] as const) {
      page.on('pageerror', (error) =>
        (proof.errors as string[]).push(error.message)
      );
      page.on('request', (r) => {
        const path = new URL(r.url()).pathname;
        if (path.startsWith('/api/v2/operator'))
          requestLog.push({
            client: name,
            method: r.method(),
            path,
            at: performance.now(),
          });
      });
      await page.goto(`/operator?mission_id=${missionId}`);
      await expect(
        page.getByRole('button', { name: 'Schedule Call', exact: true })
      ).toBeEnabled({ timeout: 30_000 });
      await expect(
        page.getByRole('button', { name: 'Load More Records', exact: true })
      ).toBeVisible();
    }
    expect(await laptop.evaluate(() => document.visibilityState)).toBe(
      'visible'
    );
    expect(await phone.evaluate(() => document.visibilityState)).toBe(
      'visible'
    );
    proof.twoIndependentVisibleContexts = true;
    async function saved(writer: Page, action: () => Promise<void>) {
      const completed = writer
        .waitForResponse(mutatesRecord, { timeout: 15_000 })
        .then(async (response) => {
          await response.finished();
          const at = performance.now();
          expect(response.ok(), await response.text()).toBe(true);
          return { receipt: (await response.json()) as CommandReceipt, at };
        });
      await action();
      return completed;
    }
    async function propagated(
      operation: string,
      writer: Page,
      action: () => Promise<void>,
      observe: (receipt: CommandReceipt) => Promise<void>
    ) {
      const result = await saved(writer, action);
      await observe(result.receipt);
      const ms = performance.now() - result.at;
      latencies.push({ operation, ms });
      expect(ms, operation).toBeLessThanOrEqual(5000);
      return result.receipt;
    }
    const conference = (
      await propagated(
        'laptop conference creation → phone',
        laptop,
        async () => {
          await laptop
            .getByRole('button', { name: 'Create Conference', exact: true })
            .click();
          await laptop
            .getByLabel('Conference name (optional)', { exact: true })
            .fill('Sync Bridge');
          await laptop
            .getByRole('button', { name: 'Save Conference', exact: true })
            .click();
        },
        async (receipt) => {
          await expect(
            card(phone, receipt.saved_records[0].record_id)
          ).toContainText('Sync Bridge');
        }
      )
    ).saved_records[0];
    for (const page of [laptop, phone]) {
      await page
        .getByRole('button', { name: 'Load More Records', exact: true })
        .click();
      await expect(
        page.getByRole('button', { name: 'Load More Records', exact: true })
      ).toHaveCount(0);
      await expect(card(page, conference.record_id)).toContainText(
        'Sync Bridge'
      );
    }
    proof.snapshotPagination = true;
    const start = new Date(Date.now() + 30 * 60_000).toISOString();
    const a = (
      await propagated(
        'laptop scheduled call → phone cards and timeline',
        laptop,
        () => schedule(laptop, 'Laptop Customer', start, conference.record_id),
        async (receipt) => {
          await expect(
            card(phone, receipt.saved_records[0].record_id)
          ).toContainText('Laptop Customer');
          await timeline(phone, 'Laptop Customer');
        }
      )
    ).saved_records[0];
    const b = (
      await propagated(
        'phone scheduled call → laptop cards and timeline',
        phone,
        () => schedule(phone, 'Phone Customer', start, conference.record_id),
        async (receipt) => {
          await expect(
            card(laptop, receipt.saved_records[0].record_id)
          ).toContainText('Phone Customer');
          await timeline(laptop, 'Phone Customer');
        }
      )
    ).saved_records[0];
    await propagated(
      'phone establishment → laptop',
      phone,
      () =>
        card(phone, conference.record_id)
          .getByRole('button', { name: 'Establish', exact: true })
          .click(),
      async () => {
        await expect(card(laptop, conference.record_id)).toContainText(
          'Two-Way Check Complete'
        );
      }
    );
    await propagated(
      'laptop customer joined → phone count',
      laptop,
      () =>
        card(laptop, a.record_id)
          .getByRole('button', { name: 'Connect Customer', exact: true })
          .click(),
      async () => {
        await expect(phone.getByText(/Reported connected · 1/)).toBeVisible();
      }
    );
    await propagated(
      'phone customer left → laptop count',
      phone,
      () =>
        card(phone, a.record_id)
          .getByRole('button', { name: 'Report Customer Left', exact: true })
          .click(),
      async () => {
        await expect(laptop.getByText(/Reported connected · 0/)).toBeVisible();
      }
    );
    await propagated(
      'phone finish → laptop call',
      phone,
      () =>
        card(phone, a.record_id)
          .getByRole('button', { name: 'Finish Call', exact: true })
          .click(),
      async () => {
        await expect(card(laptop, a.record_id)).toHaveCount(0);
      }
    );
    await propagated(
      'laptop conference closure → phone',
      laptop,
      () =>
        card(laptop, conference.record_id)
          .getByRole('button', { name: 'Close Conference', exact: true })
          .click(),
      async () => {
        await expect(card(phone, conference.record_id)).toContainText(
          'Closed · Establish To Reuse'
        );
      }
    );
    const later = new Date(Date.now() + 60 * 60_000).toISOString();
    await propagated(
      'phone reschedule → laptop',
      phone,
      async () => {
        await editor(phone, b.record_id);
        await zulu(phone, 'Planned Start', later);
        await phone
          .getByRole('button', { name: 'Save Call', exact: true })
          .click();
      },
      async () => {
        await expect(card(laptop, b.record_id)).toContainText(
          later.slice(11, 16)
        );
        const button = laptop
          .getByRole('button', {
            name: 'Focus Customer Requirement: Phone Customer',
            exact: true,
          })
          .first();
        await expect(
          button.locator('xpath=ancestor::li[1]').locator('time').first()
        ).toHaveAttribute('datetime', new RegExp(`^${later.slice(0, 16)}:00`));
      }
    );
    // Local draft stays local while saved backing data changes on the other page.
    await editor(laptop, b.record_id);
    await laptop
      .getByLabel('Party / Participant (Optional)', { exact: true })
      .fill('Laptop unsaved input');
    const draftBefore = await laptop.evaluate(() =>
      Object.entries(sessionStorage)
        .filter(([key]) => key.startsWith('operator-workspace-draft:v1:'))
        .map(([, value]) => JSON.parse(value))
        .find((d) => d.input.payload.party === 'Laptop unsaved input')
    );
    await propagated(
      'phone edit while laptop draft is dirty',
      phone,
      async () => {
        await editor(phone, b.record_id);
        await phone
          .getByLabel('Party / Participant (Optional)', { exact: true })
          .fill('Phone saved edit');
        await phone
          .getByRole('button', { name: 'Save Call', exact: true })
          .click();
      },
      async () => {
        await expect(
          laptop.getByLabel('Party / Participant (Optional)', { exact: true })
        ).toHaveValue('Laptop unsaved input');
        await expect(card(laptop, b.record_id)).toContainText(
          'Phone saved edit',
          { useInnerText: false }
        );
      }
    );
    const draftAfter = await laptop.evaluate(() =>
      Object.entries(sessionStorage)
        .filter(([key]) => key.startsWith('operator-workspace-draft:v1:'))
        .map(([, value]) => JSON.parse(value))
        .find((d) => d.input.payload.party === 'Laptop unsaved input')
    );
    expect(draftAfter.target).toEqual(draftBefore.target);
    expect(draftAfter.baseVersion).toBe(draftBefore.baseVersion);
    const conflict = laptop.waitForResponse(
      (r) => mutatesRecord(r) && r.status() === 409
    );
    await laptop
      .getByRole('button', { name: 'Save Call', exact: true })
      .click();
    await conflict;
    await expect(
      laptop
        .getByRole('button', { name: 'Reread and reconcile', exact: true })
        .first()
    ).toBeVisible();
    await expect(
      laptop.getByLabel('Party / Participant (Optional)', { exact: true })
    ).toHaveValue('Laptop unsaved input');
    await laptop
      .getByRole('button', { name: 'Keep Draft And Return', exact: true })
      .click();
    proof.dirtyDraftAnd409 = {
      baseVersion: draftAfter.baseVersion,
      targetPreserved: true,
      inputPreserved: true,
    };
    // Genuine page lifecycle suspension; this is distinct from hidden timer tests.
    const cdp = await phoneContext.newCDPSession(phone);
    await cdp.send('Page.setWebLifecycleState', { state: 'frozen' });
    const suspendedCount = requestLog.filter(
      (r) => r.client === 'phone' && r.path.endsWith('/record-changes')
    ).length;
    const suspended = await saved(laptop, () =>
      schedule(laptop, 'Suspended phone catch-up', start)
    );
    await laptop.waitForTimeout(2400);
    expect(
      requestLog.filter(
        (r) => r.client === 'phone' && r.path.endsWith('/record-changes')
      ).length
    ).toBe(suspendedCount);
    const resumed = performance.now();
    await cdp.send('Page.setWebLifecycleState', { state: 'active' });
    await expect(
      card(phone, suspended.receipt.saved_records[0].record_id)
    ).toBeVisible();
    proof.suspensionRecoveryMs = performance.now() - resumed;
    await cdp.detach();
    // Real browser offline/online recovery; no responses are fulfilled by tests.
    await phoneContext.setOffline(true);
    const offlineSave = await saved(laptop, () =>
      schedule(laptop, 'Offline phone catch-up', start)
    );
    await expect(phone.getByText(/Saved records unavailable/)).toBeVisible();
    const phoneWrites = requestLog.filter(
      (r) => r.client === 'phone' && r.method !== 'GET'
    ).length;
    const reconnected = performance.now();
    await phoneContext.setOffline(false);
    await expect(
      card(phone, offlineSave.receipt.saved_records[0].record_id)
    ).toBeVisible();
    proof.reconnectionRecoveryMs = performance.now() - reconnected;
    expect(
      requestLog.filter((r) => r.client === 'phone' && r.method !== 'GET')
        .length
    ).toBe(phoneWrites);
    await expect(phone.getByText(/Saved records unavailable/)).toHaveCount(0);
    await pending;
    if (heartbeat) clearInterval(heartbeat);
    heartbeat = undefined;
    control('stop');
    backendStopped = true;
    await expect(phone.getByText(/Saved records unavailable/)).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      card(phone, offlineSave.receipt.saved_records[0].record_id)
    ).toBeVisible();
    control('start');
    backendStopped = false;
    await expect(phone.getByText(/Saved records unavailable/)).toHaveCount(0, {
      timeout: 30_000,
    });
    proof.backendRecovery = true;
    // Cancellation changes the card and its current timeline representation.
    await openCallDetails(phone, b.record_id);
    await propagated(
      'phone cancellation → laptop card and timeline',
      phone,
      () =>
        card(phone, b.record_id)
          .getByRole('button', { name: 'Cancel Call', exact: true })
          .click(),
      async () => {
        await expect(card(laptop, b.record_id)).toHaveCount(0);
        await expect(
          laptop
            .getByRole('button', {
              name: 'Focus Prepare: Phone saved edit',
              exact: true,
            })
            .first()
            .locator('xpath=ancestor::li[1]')
        ).toContainText('Inactive');
      }
    );
    const idleStart = performance.now();
    const idleIndex = requestLog.length;
    await laptop.waitForTimeout(12_200);
    const elapsed = performance.now() - idleStart;
    const idle = requestLog.slice(idleIndex);
    const idleCounts = Object.fromEntries(
      ['laptop', 'phone'].map((name) => [
        name,
        Object.fromEntries(
          [
            ...new Set(
              idle.filter((r) => r.client === name).map((r) => r.path)
            ),
          ].map((path) => [
            path,
            idle.filter((r) => r.client === name && r.path === path).length,
          ])
        ),
      ])
    );
    proof.idle = { elapsedMs: elapsed, counts: idleCounts };
    for (const name of ['laptop', 'phone']) {
      const requests = idle.filter(
        (r) => r.client === name && r.path.endsWith('/record-changes')
      );
      expect(requests.length).toBeGreaterThanOrEqual(5);
      expect(requests.length).toBeLessThanOrEqual(7);
      expect(
        idle.filter(
          (r) => r.client === name && r.path === '/api/v2/operator/records'
        )
      ).toHaveLength(0);
      expect(
        idle.filter((r) => r.client === name && r.method !== 'GET')
      ).toHaveLength(0);
    }
    await laptop.screenshot({
      path: `${evidence}/sync-laptop-1920x1080.png`,
      fullPage: true,
    });
    await phone.screenshot({
      path: `${evidence}/sync-phone-390x844.png`,
      fullPage: true,
    });
    // SPA navigation unmounts the owner; no polling worker should remain behind.
    await navigate(laptop, '/missions');
    await expect(
      laptop.getByRole('navigation', { name: 'Operator workspace' })
    ).toHaveCount(0);
    const away = requestLog.filter(
      (r) => r.client === 'laptop' && r.path.endsWith('/record-changes')
    ).length;
    await phone.waitForTimeout(4200);
    expect(
      requestLog.filter(
        (r) => r.client === 'laptop' && r.path.endsWith('/record-changes')
      ).length
    ).toBe(away);
    await navigate(laptop, `/operator?mission_id=${missionId}`);
    await expect(
      card(laptop, suspended.receipt.saved_records[0].record_id)
    ).toBeVisible();
    const otherMission = `isolation-${randomUUID()}`;
    await json(
      await request.post('/api/v2/missions', {
        data: { id: otherMission, name: 'Synthetic other mission', legs: [] },
      })
    );
    await navigate(phone, `/operator?mission_id=${otherMission}`);
    await expect(
      card(phone, suspended.receipt.saved_records[0].record_id)
    ).toHaveCount(0);
    proof.navigationAndMissionIsolation = true;
    expect(proof.errors).toEqual([]);
    proof.passed = true;
  } finally {
    if (heartbeat) clearInterval(heartbeat);
    await pending.catch(() => {});
    if (backendStopped) control('start');
    await Promise.all(contexts.map((context) => context.close()));
    await writeFile(
      `${evidence}/operator-record-sync-proof.json`,
      JSON.stringify({ ...proof, requests: requestLog }, null, 2)
    );
  }
});
