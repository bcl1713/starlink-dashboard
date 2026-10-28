import { test, expect, type Page, type BrowserContext } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { json, raw, seed, feed } from './operator-coherent-fixture';
import {
  conferenceDraft,
  unknownTime,
} from '../../src/components/operator/conferenceCommands';
import { callDraft } from '../../src/components/operator/callDraft';
import type { SavedRecord, OperatorInput } from '../../src/types/operator';
const evidence = process.env.OPERATOR_COHERENT_EVIDENCE!;
const controls = (page: Page) =>
  page.getByRole('navigation', { name: 'Operator workspace' });
async function zulu(page: Page, label: string, value: string) {
  await page
    .getByLabel(new RegExp(`^${label} date \\(Zulu\\)$`, 'i'))
    .fill(value.slice(0, 10));
  await page
    .getByLabel(new RegExp(`^${label} hour \\(Zulu\\)`, 'i'))
    .selectOption(value.slice(11, 13));
  await page
    .getByLabel(new RegExp(`^${label} minute \\(Zulu\\)`, 'i'))
    .selectOption(value.slice(14, 16));
}
async function waitRecord(
  page: Page,
  id: string,
  check: (record: SavedRecord) => boolean
) {
  await expect
    .poll(async () =>
      check(
        (
          await json<{ record: SavedRecord }>(
            await page.request.get(`/api/v2/operator/records/${id}`)
          )
        ).record
      )
    )
    .toBe(true);
}
test('coherent operations, retained capture and real journal safety across desktop and phone', async ({
  browser,
  request,
}) => {
  const proof: Record<string, unknown> = {
    synthetic: true,
    productionAPIs: true,
    browserVersion: browser.version(),
    locale: 'en-US',
    timezone: 'Pacific/Honolulu',
    browserErrors: [],
    captures: [],
  };
  const contexts: BrowserContext[] = [];
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  let pending = Promise.resolve();
  try {
    const { missionId, legs } = await seed(request);
    heartbeat = setInterval(() => {
      pending = pending.then(() => raw(request, 1764)).then(() => {});
    }, 2000);
    const headers = async () => ({
      'Idempotency-Key': randomUUID(),
      'X-Operator-Store-Epoch': (
        await json<{ api_epoch: string }>(
          await request.get('/api/v2/operator/health')
        )
      ).api_epoch,
    });
    const create = async (input: OperatorInput) =>
      (
        await json<{ saved_records: SavedRecord[] }>(
          await request.post('/api/v2/operator/records', {
            headers: await headers(),
            data: { ...input, scope: 'leg', leg_id: legs[0] },
          })
        )
      ).saved_records[0];
    const alpha = await create({
      ...conferenceDraft(missionId),
      payload: {
        ...conferenceDraft(missionId).payload,
        title: 'Alpha Conference',
        configured_transport: 'Starshield',
      },
    });
    const bravo = await create({
      ...conferenceDraft(missionId),
      payload: {
        ...conferenceDraft(missionId).payload,
        title: 'Bravo Conference',
        configured_transport: 'Ka',
      },
    });
    await create({
      ...conferenceDraft(missionId),
      payload: {
        ...conferenceDraft(missionId).payload,
        title: 'Idle Conference',
      },
    });
    const future = new Date(Date.now() + 30 * 60000).toISOString();
    const callAlpha = await create({
      ...callDraft(undefined, 'planned', missionId),
      time: {
        ...unknownTime,
        planned_start_at: future,
        planned_end_at: new Date(Date.parse(future) + 20 * 60000).toISOString(),
      },
      payload: {
        ...callDraft(undefined, 'planned', missionId).payload,
        title: 'Alpha Customer',
        party: 'Alpha Customer',
        conference_id: alpha.record_id,
      },
    });
    const snapshot = await feed(request, missionId);
    const restriction = snapshot.events.find(
      (e) =>
        e.kind === 'restriction' && e.transport === 'Ka' && e.due_at && e.end_at
    );
    expect(
      restriction,
      'Fixture Must Produce A Genuine Ka Restriction'
    ).toBeTruthy();
    const callBravo = await create({
      ...callDraft(undefined, 'planned', missionId),
      time: {
        ...unknownTime,
        planned_start_at: restriction!.due_at,
        planned_end_at: new Date(
          Date.parse(restriction!.end_at!) + 60000
        ).toISOString(),
      },
      payload: {
        ...callDraft(undefined, 'planned', missionId).payload,
        title: 'Bravo Customer',
        party: 'Bravo Customer',
        conference_id: bravo.record_id,
      },
    });
    const direct = await create({
      ...callDraft(undefined, 'planned', missionId),
      time: {
        ...unknownTime,
        planned_start_at: future,
        planned_end_at: new Date(Date.parse(future) + 20 * 60000).toISOString(),
      },
      payload: {
        ...callDraft(undefined, 'planned', missionId).payload,
        title: 'Direct Customer',
        party: 'Direct Customer',
        conference_id: null,
        direct_transport: null,
      },
    });
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
        title: 'Unknown Occurrence Note',
        note: 'Unknown occurrence remains unknown',
        previous_leg_id: null,
        next_leg_id: null,
      },
    });
    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      locale: 'en-US',
      timezoneId: 'Pacific/Honolulu',
    });
    contexts.push(context);
    const page = await context.newPage();
    page.on('pageerror', (e) =>
      (proof.browserErrors as string[]).push(e.message)
    );
    await page.goto(`/operator?mission_id=${missionId}`);
    await expect(
      controls(page).getByRole('button', { name: 'Operations', exact: true })
    ).toHaveAttribute('aria-current', 'page');
    const alphaCard = page.getByRole('article', {
      name: 'Conference Alpha Conference',
      exact: true,
    });
    const idleCard = page.getByRole('article', {
      name: 'Conference Idle Conference',
      exact: true,
    });
    await expect(alphaCard).toBeVisible();
    await expect(idleCard).toBeVisible();
    const firstConference = page
      .locator('.ws-conferences-lane article')
      .first();
    const firstCall = page.locator('.ws-calls-lane li[data-record-id]').first();
    const aligned = async () => {
      const conference = await firstConference.boundingBox();
      const call = await firstCall.boundingBox();
      expect(Math.abs(conference!.y - call!.y)).toBeLessThanOrEqual(1);
      return { conference, call };
    };
    const laneAlignment = await aligned();
    await expect(
      firstCall.locator(':scope > button[data-primary-action]')
    ).toHaveCount(1);
    await expect(
      firstCall.getByRole('button', { name: 'Call History', exact: true })
    ).toBeHidden();
    await expect(
      firstCall.getByRole('button', { name: 'Reschedule', exact: true })
    ).toBeHidden();
    const createConference = page.getByRole('button', {
      name: 'Create Conference',
      exact: true,
    });
    await createConference.evaluate((el) => {
      el.style.width = '100%';
    });
    const wrappedLaneAlignment = await aligned();
    await createConference.evaluate((el) => {
      el.style.removeProperty('width');
    });
    proof.laneAlignment = {
      normal: laneAlignment,
      wrapped: wrappedLaneAlignment,
    };
    await page.screenshot({
      path: `${evidence}/operations-initial-1920x1080.png`,
    });
    const before = await alphaCard.boundingBox();
    const neighborBefore = await idleCard.boundingBox();
    await alphaCard
      .getByRole('button', { name: 'Establish', exact: true })
      .click();
    await waitRecord(
      page,
      alpha.record_id,
      (r) =>
        r.payload.entry_type === 'conference' &&
        r.payload.status === 'established' &&
        !!r.payload.verified_at
    );
    const close = alphaCard.getByRole('button', {
      name: /^Close Conference$/i,
    });
    await expect(close).toBeEnabled();
    const established = await alphaCard.boundingBox();
    const actionBefore = await close.boundingBox();
    await close.click();
    await expect(
      alphaCard.getByRole('button', { name: 'Establish', exact: true })
    ).toBeEnabled();
    const closed = await alphaCard.boundingBox();
    const actionAfter = await alphaCard
      .getByRole('button', { name: 'Establish', exact: true })
      .boundingBox();
    const neighborAfter = await idleCard.boundingBox();
    expect(Math.abs(actionBefore!.y - actionAfter!.y)).toBeLessThanOrEqual(1);
    expect(Math.abs(established!.height - closed!.height)).toBeLessThanOrEqual(
      1
    );
    expect(
      Math.abs(neighborBefore!.y - before!.y - (neighborAfter!.y - closed!.y))
    ).toBeLessThanOrEqual(1);
    await expect(page.getByRole('dialog')).toHaveCount(0);
    proof.stableCloseGeometry = {
      before,
      established,
      closed,
      actionBefore,
      actionAfter,
      neighborBefore,
      neighborAfter,
    };
    await alphaCard
      .getByRole('button', { name: 'Establish', exact: true })
      .click();
    const call = page.locator(`#operator-record-${callAlpha.record_id}`);
    await call.getByRole('button', { name: /^Connect Customer$/i }).click();
    await expect(
      call.getByRole('button', { name: /Report Customer Left/i })
    ).toBeVisible();
    await expect(
      alphaCard.getByRole('button', { name: /^Close Conference$/i })
    ).toBeDisabled();
    await call.getByRole('button', { name: /Report Customer Left/i }).click();
    await call.getByRole('button', { name: /^Finish Call$/i }).click();
    await expect(
      alphaCard.getByRole('button', { name: /^Close Conference$/i })
    ).toBeEnabled();
    proof.bridgeReuseAndIndependentCustomers = true;
    const directCard = page.locator(`#operator-record-${direct.record_id}`);
    await expect(directCard.getByText(/Direct Connection/i)).toBeVisible();
    await expect(
      directCard.getByText(/Coverage Unknown|Transport Unknown/i)
    ).toBeVisible();
    await directCard
      .getByRole('button', { name: 'Establish', exact: true })
      .click();
    await directCard
      .getByRole('button', { name: /^Connect Customer$/i })
      .click();
    await expect(
      directCard.getByRole('button', { name: /Report Customer Left/i })
    ).toBeVisible();
    await directCard
      .getByRole('button', { name: /Report Customer Left/i })
      .click();
    await directCard.getByRole('button', { name: /^Finish Call$/i }).click();
    proof.directCall = true;
    const bravoCall = page.locator(`#operator-record-${callBravo.record_id}`);
    await expect(bravoCall.locator('.ws-call-advisory-warning')).toBeVisible();
    const timelineBravo = page.getByRole('button', {
      name: 'Focus Prepare: Bravo Customer',
      exact: true,
    });
    await timelineBravo.click();
    await expect
      .poll(() =>
        bravoCall.evaluate((el) => el.contains(document.activeElement))
      )
      .toBe(true);
    await page
      .getByRole('button', { name: 'Schedule Call', exact: true })
      .focus();
    await timelineBravo.click();
    await expect
      .poll(() =>
        bravoCall.evaluate((el) => el.contains(document.activeElement))
      )
      .toBe(true);
    await timelineBravo.focus();
    await page.keyboard.press('Enter');
    await expect
      .poll(() =>
        bravoCall.evaluate((el) => el.contains(document.activeElement))
      )
      .toBe(true);
    proof.repeatedTimelineSelection = true;

    await page.screenshot({
      path: `${evidence}/operations-busy-1920x1080.png`,
    });
    await bravoCall.getByText('Call Details', { exact: true }).click();
    await bravoCall
      .getByRole('button', { name: 'Reschedule', exact: true })
      .click();
    const currentSchedule = await feed(request, missionId);
    const lastRestrictionEnd = Math.max(
      ...currentSchedule.events
        .filter(
          (event) =>
            event.kind === 'restriction' &&
            event.leg_id === legs[0] &&
            (event.transport === 'Ka' || event.transport === null) &&
            event.end_at
        )
        .map((event) => Date.parse(event.end_at!))
    );
    await zulu(
      page,
      'Planned Start',
      new Date(lastRestrictionEnd + 5 * 60000).toISOString()
    );
    await page.getByRole('button', { name: /^Save Call$/i }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(bravoCall.locator('.ws-call-advisory-warning')).toHaveCount(0);
    await bravoCall.getByText('Call Details', { exact: true }).click();
    proof.rescheduleUpdatesOverlap = true;
    await page
      .getByRole('button', { name: 'Schedule Call', exact: true })
      .click();
    await page
      .getByLabel(/Party \/ Participant/i)
      .fill('Overnight Inline Customer');
    await zulu(page, 'Planned Start', '2026-11-01T23:55:00Z');
    await page.getByLabel(/Duration Minutes/i).fill('20');
    await page.getByLabel(/Preparation Lead Minutes/i).fill('10');
    await page
      .getByRole('button', { name: 'Create Conference', exact: true })
      .click();
    await page.getByLabel(/Conference Name/i).fill('Inline Conference');
    await page.getByRole('button', { name: /^Save Conference$/i }).click();
    await expect(page.getByLabel(/Party \/ Participant/i)).toHaveValue(
      'Overnight Inline Customer'
    );
    await expect(page.getByLabel(/Duration Minutes/i)).toHaveValue('20');
    await expect(page.getByLabel(/Preparation Lead Minutes/i)).toHaveValue(
      '10'
    );
    await expect(page.getByLabel(/^Conference \(Optional\)/i)).toContainText(
      'Inline Conference'
    );
    await page.getByRole('button', { name: /^Save Call$/i }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    const all = await json<{ items: { record: SavedRecord }[] }>(
      await request.get(
        `/api/v2/operator/records?mission_id=${missionId}&limit=200`
      )
    );
    const overnight = all.items.find(
      (i) => i.record.payload.title === 'Overnight Inline Customer'
    )!.record;
    expect(overnight.time.planned_end_at).toMatch(/^2026-11-02T00:15/);
    proof.inlineRetainsOvernightDraft = true;
    const overnightCard = page.locator(
      `#operator-record-${overnight.record_id}`
    );
    await overnightCard.getByText('Call Details', { exact: true }).click();
    await overnightCard.getByRole('button', { name: /^Cancel Call$/i }).click();
    await waitRecord(
      page,
      overnight.record_id,
      (r) => r.payload.entry_type === 'call' && r.payload.status === 'cancelled'
    );
    const keptConference = all.items.find(
      (i) => i.record.payload.title === 'Inline Conference'
    )!.record;
    expect(
      (
        await json<{ record: SavedRecord }>(
          await request.get(
            `/api/v2/operator/records/${keptConference.record_id}`
          )
        )
      ).record.deleted
    ).toBe(false);
    proof.cancelPreservesConference = true;
    // Hold the response after a real durable call create, then retain a newer
    // party edit. Inline entry must wait; its later save must update that call.
    await page
      .getByRole('button', { name: 'Schedule Call', exact: true })
      .click();
    await page.getByLabel(/Party \/ Participant/i).fill('Pending Parent Guard');
    await zulu(page, 'Planned Start', future);
    let releaseParent!: () => void;
    const parentResponse = new Promise<void>((resolve) => {
      releaseParent = resolve;
    });
    let parentCommitted = false;
    await page.route('**/api/v2/operator/records', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      const body = route.request().postDataJSON();
      if (
        body.record_type !== 'call' ||
        body.payload?.title !== 'Pending Parent Guard'
      ) {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      parentCommitted = true;
      await parentResponse;
      await route.fulfill({ response });
    });
    try {
      await page
        .getByRole('button', { name: 'Save Call', exact: true })
        .click();
      await expect.poll(() => parentCommitted).toBe(true);
      await page
        .getByLabel(/Party \/ Participant/i)
        .fill('Pending Parent Updated');
      const inline = page.getByRole('button', {
        name: 'Create Conference',
        exact: true,
      });
      await expect(inline).toBeDisabled();
      await inline.evaluate((button) => (button as HTMLButtonElement).click());
      await expect(page.getByLabel('Conference name (optional)')).toHaveCount(
        0
      );
    } finally {
      releaseParent();
    }
    await expect(
      page
        .getByRole('dialog')
        .getByRole('heading', { name: 'Edit Call', exact: true })
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Create Conference', exact: true })
    ).toBeEnabled();
    await page.unroute('**/api/v2/operator/records');
    const pendingCalls = await json<{ items: { record: SavedRecord }[] }>(
      await request.get(
        `/api/v2/operator/records?mission_id=${missionId}&record_type=call&limit=200`
      )
    );
    const originalParent = pendingCalls.items.filter(
      ({ record }) => record.payload.title === 'Pending Parent Guard'
    );
    expect(originalParent).toHaveLength(1);
    await page
      .getByRole('button', { name: 'Create Conference', exact: true })
      .click();
    await page
      .getByLabel('Conference name (optional)')
      .fill('Pending Parent Conference');
    await page
      .getByRole('button', { name: 'Save Conference', exact: true })
      .click();
    await expect(page.getByLabel(/Party \/ Participant/i)).toHaveValue(
      'Pending Parent Updated'
    );
    await page.getByRole('button', { name: 'Save Call', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await waitRecord(
      page,
      originalParent[0].record.record_id,
      (record) =>
        record.payload.entry_type === 'call' &&
        record.payload.party === 'Pending Parent Updated' &&
        !!record.payload.conference_id
    );
    const afterParent = await json<{ items: { record: SavedRecord }[] }>(
      await request.get(
        `/api/v2/operator/records?mission_id=${missionId}&record_type=call&limit=200`
      )
    );
    expect(
      afterParent.items.filter(({ record }) =>
        ['Pending Parent Guard', 'Pending Parent Updated'].includes(
          record.payload.title
        )
      )
    ).toHaveLength(1);
    proof.pendingParentInlineNoDuplicate = true;

    await page.getByRole('button', { name: 'Add Issue', exact: true }).click();
    await page
      .getByLabel(/Problem Description/i)
      .fill('Intermittent Customer Audio');
    await page.getByRole('button', { name: /^Save Issue$/i }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await controls(page)
      .getByRole('button', { name: 'Issues', exact: true })
      .click();
    const issueCard = page.getByRole('article', {
      name: 'Issue Intermittent Customer Audio',
      exact: true,
    });
    await issueCard
      .getByRole('button', { name: /Add Update \/ Follow Up/i })
      .click();
    await page
      .getByLabel('Add Update', { exact: true })
      .fill('Distant End Reconnected; Monitoring');
    await page.getByLabel('Status', { exact: true }).selectOption('monitoring');
    await page.getByRole('button', { name: /^Save Issue$/i }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(issueCard).toContainText('monitoring');
    proof.problemAndUpdate = true;
    await controls(page)
      .getByRole('button', { name: 'Transport', exact: true })
      .click();
    await page.getByRole('button', { name: /Manage Transports/i }).click();
    const manager = page.getByRole('region', { name: /Manage Transports/i });
    await manager.getByLabel(/New Transport/i).fill('Training Relay');
    await manager.getByRole('button', { name: 'Add', exact: true }).click();
    await manager.getByRole('button', { name: 'Done', exact: true }).click();
    const service = page
      .getByRole('article')
      .filter({ has: page.getByRole('button', { name: 'Apply', exact: true }) })
      .first();
    await service
      .getByRole('combobox')
      .selectOption({ label: 'Training Relay' });
    await service.getByRole('button', { name: 'Apply', exact: true }).click();
    await expect(service).toContainText('Training Relay');
    proof.adHocServiceTransport = true;
    // A response is lost after a real durable note commit; retry must reuse it.
    await page.getByRole('button', { name: 'Add Note', exact: true }).click();
    await page
      .getByLabel('Note', { exact: true })
      .fill('Backdated Note Retained On Interrupted Save');
    await page.getByText(/Backdate \/ Change Occurrence/i).click();
    const backdate = new Date(Date.now() - 20 * 60000).toISOString();
    await zulu(page, 'Occurred At', backdate);
    let lost = false;
    const noteKeys: string[] = [];
    await page.route('**/api/v2/operator/records', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      const body = route.request().postDataJSON();
      if (body.payload?.entry_type === 'note') {
        noteKeys.push(route.request().headers()['idempotency-key']);
        const response = await route.fetch();
        if (!lost) {
          lost = true;
          await route.abort('connectionfailed');
          return;
        }
        await route.fulfill({ response });
        return;
      }
      await route.continue();
    });
    await page.getByRole('button', { name: /^Save Entry$/i }).click();
    await expect(
      page.getByRole('textbox', { name: 'Note', exact: true })
    ).toHaveValue('Backdated Note Retained On Interrupted Save');
    await page.getByRole('button', { name: /Keep Draft And Return/i }).click();
    const retry = page.getByRole('button', {
      name: /Retry Exact Save|Retry Same Save|Retry Exact Command/i,
    });
    await expect(retry.first()).toBeEnabled();
    await retry.first().click();
    await expect.poll(() => noteKeys.length).toBe(2);
    expect(noteKeys[0]).toBe(noteKeys[1]);
    await expect(retry).toHaveCount(0);
    const notes = await json<{ items: { record: SavedRecord }[] }>(
      await request.get(
        `/api/v2/operator/records?mission_id=${missionId}&record_type=journal_entry&limit=200`
      )
    );
    expect(
      notes.items.filter(
        ({ record }) =>
          record.payload.title === 'Backdated Note Retained On Interrupted Save'
      )
    ).toHaveLength(1);
    await page.unroute('**/api/v2/operator/records');
    proof.interruptedSaveSameKey = true;
    if (
      await page.getByRole('button', { name: /Keep Draft And Return/i }).count()
    )
      await page
        .getByRole('button', { name: /Keep Draft And Return/i })
        .click();
    for (const section of ['Transport', 'Issues', 'Notes', 'History']) {
      await controls(page)
        .getByRole('button', { name: section, exact: true })
        .click();
      await expect(
        page.getByRole('button', { name: 'Schedule Call', exact: true })
      ).toBeVisible();
      await expect(
        page.getByRole('region', { name: 'Mission timeline' })
      ).toBeVisible();
      if (section === 'Issues') {
        for (const name of ['Schedule Call', 'Add Issue', 'Add Note']) {
          await page.locator('.ws-body').evaluate((el) => {
            el.scrollTop = el.scrollHeight;
          });
          const capture = page.getByRole('button', { name, exact: true });
          await expect(capture).toBeInViewport({ ratio: 1 });
          expect(
            await capture.evaluate((button) => {
              const bounds = button.getBoundingClientRect();
              return button.contains(
                document.elementFromPoint(
                  bounds.x + bounds.width / 2,
                  bounds.y + bounds.height / 2
                )
              );
            })
          ).toBe(true);
          await capture.click();
          await expect(page.getByRole('dialog')).toBeVisible();
          await page
            .getByRole('button', { name: 'Discard draft', exact: true })
            .click();
          await expect(page.getByRole('dialog')).toHaveCount(0);
        }
        await page.locator('.ws-body').evaluate((el) => {
          el.scrollTop = el.scrollHeight;
        });
        await page.screenshot({
          path: `${evidence}/issues-scrolled-1920x1080.png`,
        });
        proof.scrolledIssuesCaptureUnobscured = true;
      }
      if (section === 'Notes' || section === 'History') {
        const knownNote = page.getByRole('article').filter({
          has: page.getByRole('heading', {
            name: 'Backdated Note Retained On Interrupted Save',
            exact: true,
          }),
        });
        await expect(knownNote.locator('time')).toHaveText(
          /^\d{4}-\d{2}-\d{2} \d{2}:\d{2} Zulu$/
        );
        const unknownNote = page.getByRole('article').filter({
          has: page.getByRole('heading', {
            name: 'Unknown Occurrence Note',
            exact: true,
          }),
        });
        await expect(
          unknownNote.getByText('Occurrence time unknown', { exact: true })
        ).toBeVisible();
        await expect(
          knownNote.getByText('Timestamp Details').locator('..')
        ).not.toHaveAttribute('open');
        proof.readableJournalTimes = true;
      }
      await page.locator('.ws-body').evaluate((el) => {
        el.scrollTop = 0;
      });
      await page.screenshot({
        path: `${evidence}/${section.toLowerCase()}-1920x1080.png`,
      });
    }
    await page
      .getByRole('button', { name: 'Display Controls', exact: true })
      .click();
    await expect(
      page.getByRole('button', { name: /Recenter View/i })
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: /Open Overview/i })
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: /Apply Customer/i })
    ).toBeVisible();
    await page.screenshot({
      path: `${evidence}/display-controls-1920x1080.png`,
    });
    await page.keyboard.press('Escape');
    proof.displayControlParity = true;
    for (const [width, height] of [
      [1920, 1080],
      [390, 844],
      [844, 390],
    ]) {
      await page.setViewportSize({ width, height });
      await controls(page)
        .getByRole('button', { name: 'Operations', exact: true })
        .click();
      await expect(page.locator('.ws-conferences-lane')).toBeVisible();
      if (width < 900) {
        const establishIdle = idleCard.getByRole('button', {
          name: 'Establish',
          exact: true,
        });
        await establishIdle.scrollIntoViewIfNeeded();
        const idleBefore = await idleCard.boundingBox();
        const layoutBefore = await idleCard.evaluate((el) =>
          [...el.children].map((child) => ({
            tag: child.tagName,
            cls: child.className,
            h: child.getBoundingClientRect().height,
          }))
        );
        await establishIdle.click();
        const closeIdle = idleCard.getByRole('button', {
          name: /^Close Conference$/i,
        });
        await expect(closeIdle).toBeEnabled();
        const idleEstablished = await idleCard.boundingBox();
        const layoutAfter = await idleCard.evaluate((el) =>
          [...el.children].map((child) => ({
            tag: child.tagName,
            cls: child.className,
            h: child.getBoundingClientRect().height,
          }))
        );
        console.log('Phone Geometry', width, height, {
          idleBefore,
          idleEstablished,
          layoutBefore,
          layoutAfter,
        });
        expect(
          Math.abs(idleBefore!.height - idleEstablished!.height)
        ).toBeLessThanOrEqual(1);
        const closeBox = await closeIdle.boundingBox();
        await closeIdle.click();
        await expect(establishIdle).toBeEnabled();
        const idleClosed = await idleCard.boundingBox();
        const establishBox = await establishIdle.boundingBox();
        expect(
          Math.abs(idleEstablished!.height - idleClosed!.height)
        ).toBeLessThanOrEqual(1);
        expect(Math.abs(closeBox!.y - establishBox!.y)).toBeLessThanOrEqual(1);
      }
      await page.locator('.ws-body').evaluate((el) => {
        el.scrollTop = 0;
      });

      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth
        )
      ).toBe(true);
      if (width < 900)
        await expect(
          page.getByLabel('Compact Mission Chronology')
        ).toBeVisible();
      const capture = page.getByRole('group', { name: 'Create Records' });
      for (const name of ['Schedule Call', 'Add Issue', 'Add Note'])
        await expect(
          capture.getByRole('button', { name, exact: true })
        ).toBeInViewport({ ratio: 1 });
      await expect(
        page.getByRole('button', { name: 'Create Conference', exact: true })
      ).toBeInViewport({ ratio: 1 });
      await expect(
        page
          .locator('.ws-conferences-lane article')
          .first()
          .getByRole('heading')
      ).toBeInViewport({ ratio: 1 });
      if (width < 900) {
        const nextWork = page
          .getByRole('region', { name: 'Next Action' })
          .getByRole('button');
        await expect(nextWork).toBeInViewport({ ratio: 1 });
        await nextWork.click();
        const nextPrimary = bravoCall.locator('[data-primary-action]');
        await expect(nextPrimary).toBeFocused();
        await expect(nextPrimary).toBeInViewport({ ratio: 1 });
        await page.locator('.ws-body').evaluate((el) => {
          el.scrollTop = 0;
        });
      }
      proof.firstScreenCaptureAndWork = true;

      await page.screenshot({
        path: `${evidence}/operations-${width}x${height}.png`,
      });
      (proof.captures as string[]).push(`${width}x${height}`);
    }
    expect(proof.browserErrors).toEqual([]);
    await writeFile(
      `${evidence}/operator-coherent-proof.json`,
      JSON.stringify(proof, null, 2)
    );
  } finally {
    if (heartbeat) clearInterval(heartbeat);
    await pending;
    await Promise.all(contexts.map((c) => c.close()));
  }
});
