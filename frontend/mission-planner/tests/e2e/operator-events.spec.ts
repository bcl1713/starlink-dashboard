import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import {
  test,
  expect,
  chromium,
  type APIRequestContext,
  type Page,
} from '@playwright/test';
import {
  control,
  evidence,
  noOverflow,
  origin,
  ready,
} from './operator-journal-helpers';
import type {
  EventSnapshot,
  OperationalEvent,
} from '../../src/types/operatorEvents';
const mission = 'synthetic-mission-a';
const path = '/api/v2/operator';
async function source(
  request: APIRequestContext,
  body: Record<string, unknown>
) {
  const response = await request.post(
    `${origin}/api/_synthetic/${process.env.OPERATOR_MODEL_ALERTS_ACCEPTANCE === 'true' ? 'operator-model-inputs' : 'operator-events'}`,
    { data: body }
  );
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}
async function feed(request: APIRequestContext): Promise<EventSnapshot> {
  const response = await request.get(
    `${origin}${path}/events?mission_id=${mission}`
  );
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}
async function headers(request: APIRequestContext) {
  const health = await (await request.get(`${origin}${path}/health`)).json();
  return {
    'Idempotency-Key': randomUUID(),
    'X-Operator-Store-Epoch': health.api_epoch,
  };
}
function ackBody(snapshot: EventSnapshot, event: OperationalEvent) {
  return {
    schema_version: 1,
    occurrence_id: event.notification.generation,
    severity_generation: event.notification.severity_generation,
    snapshot_token: snapshot.snapshot_token,
  };
}
async function acknowledge(
  request: APIRequestContext,
  snapshot: EventSnapshot,
  event: OperationalEvent
) {
  return request.post(`${origin}${path}/events/acknowledge`, {
    data: ackBody(snapshot, event),
    headers: await headers(request),
  });
}
async function openFeed(page: Page) {
  if (
    !(await page
      .getByRole('dialog', { name: 'Operational Timeline' })
      .isVisible())
  )
    await page
      .getByRole('button', { name: 'Open Events', exact: true })
      .click();
  return page.getByRole('dialog', { name: 'Operational Timeline' });
}
async function refresh(page: Page) {
  const drawer = await openFeed(page);
  const response = page.waitForResponse(
    (r) => r.url().includes(`${path}/events?`) && r.request().method() === 'GET'
  );
  await drawer
    .getByRole('button', { name: 'Refresh Events', exact: true })
    .click();
  await response;
  return drawer;
}
async function closeFeed(page: Page) {
  const drawer = page.getByRole('dialog', { name: 'Operational Timeline' });
  if (await drawer.isVisible())
    await drawer.getByRole('button', { name: 'Close', exact: true }).click();
}

test('unified event timeline: local alerts, source races, two clients and restart', async ({
  browser,
  request,
}) => {
  test.setTimeout(600_000);
  const proof: Record<string, unknown> = { synthetic: true, captures: [] };
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    timezoneId: 'Pacific/Honolulu',
  });
  const counterpart = await browser.newContext({
    viewport: { width: 390, height: 844 },
    timezoneId: 'Asia/Tokyo',
  });
  const attemptedExternal = new Set<string>();
  for (const client of [context, counterpart])
    await client.route('**/*', (route) => {
      const url = route.request().url();
      if (
        url.startsWith('data:') ||
        url.startsWith('blob:') ||
        new URL(url).origin === origin
      )
        return route.continue();
      attemptedExternal.add(new URL(url).origin);
      return route.abort();
    });
  try {
    const initialControl = await source(request, {});
    const initial = await feed(request);
    const alpha = initial.events.find(
      (e) => e.kind === 'call_start' && e.title.includes('customer alpha')
    )!;
    const preparation = initial.events.find(
      (e) => e.kind === 'call_prep' && e.source_ref === alpha.source_ref
    )!;
    expect(Date.parse(alpha.due_at!) - Date.parse(preparation.due_at!)).toBe(
      600_000
    );
    proof.tenMinutePrep = true;
    expect(initial.events.some((e) => e.kind === 'pop_advisory')).toBe(true);
    expect(
      initial.events.some(
        (e) =>
          e.protected_participation_ids.length === 3 &&
          e.discrepancies.length > 0 &&
          e.continuity_status === 'unknown'
      )
    ).toBe(true);
    proof.protectedUnknown = true;
    const page = await context.newPage();
    const other = await counterpart.newPage();
    await page.goto(`${origin}/operator?mission_id=${mission}`);
    await other.goto(`${origin}/operator?mission_id=${mission}`);
    await ready(page);
    await ready(other);
    await expect(
      page.getByRole('button', { name: 'Open Events' })
    ).toBeVisible();
    await expect(page.getByText(/^Local cue:/)).toBeVisible({ timeout: 15000 });
    const draft = page.getByLabel('Title', { exact: true });
    await draft.fill('Synthetic unsent event-review note');
    await page
      .getByRole('button', { name: 'Local alerts', exact: true })
      .click();
    await expect(
      page.getByText(/Closed or background browser delivery is not guaranteed/)
    ).toBeVisible();
    await expect(
      page.getByText(/Sound (needs interaction|unavailable)/)
    ).toBeVisible();
    await page.getByLabel('In-app cues', { exact: true }).uncheck();
    await page.getByRole('button', { name: 'Close settings' }).click();
    let drawer = await openFeed(page);
    await expect(
      drawer.getByText(preparation.title, { exact: true })
    ).toBeVisible();
    proof.timelineIndependent = true;
    await closeFeed(page);
    await page
      .getByRole('button', { name: 'Local alerts', exact: true })
      .click();
    await page.getByLabel('In-app cues', { exact: true }).check();
    await page
      .getByRole('button', { name: 'Enable sound and vibration' })
      .click();
    await page.getByRole('button', { name: 'Close settings' }).click();
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => true,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await source(request, { now: '2026-10-17T16:02:00Z' });
    await refresh(page);
    await closeFeed(page);
    // Keep the synthetic hidden signal through the real local cooldown. Backend
    // mission time remains explicitly controlled; no background delivery claim.
    await page.waitForTimeout(31_000);
    await expect(page.getByText(/^Local cue:/)).not.toContainText(
      preparation.title
    );
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => false,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await refresh(page);
    await closeFeed(page);
    proof.hiddenTab = true;
    await expect(page.getByText(/^Local cue:/)).toContainText(
      preparation.title,
      { timeout: 45000 }
    );
    // There is one compact cue, even when a long offline interval crosses many events.
    expect(await page.getByText(/^Local cue:/).count()).toBe(1);
    proof.boundedCatchup = true;
    const beforeMove = await feed(request);
    const oldIds = beforeMove.events
      .filter((e) => e.source_ref === alpha.source_ref)
      .map((e) => e.notification.generation);
    let record = (
      await (
        await request.get(`${origin}${path}/records/${alpha.source_ref}`)
      ).json()
    ).record;
    const moved = await request.put(
      `${origin}${path}/records/${alpha.source_ref}`,
      {
        headers: await headers(request),
        data: {
          schema_version: 1,
          record_type: record.record_type,
          mission_id: record.mission_id,
          leg_id: record.leg_id,
          scope: record.scope,
          time: { ...record.time, planned_start_at: '2026-10-17T16:22:00Z' },
          payload: record.payload,
          expected_version: record.version,
        },
      }
    );
    expect(moved.ok(), await moved.text()).toBe(true);
    const afterMove = await feed(request);
    expect(
      afterMove.events
        .filter((e) => e.source_ref === alpha.source_ref)
        .every((e) => !oldIds.includes(e.notification.generation))
    ).toBe(true);
    proof.scheduleMoved = true;
    const beta = afterMove.events.find(
      (e) => e.kind === 'call_start' && e.title.includes('customer beta')
    )!;
    record = (
      await (
        await request.get(`${origin}${path}/records/${beta.source_ref}`)
      ).json()
    ).record;
    const canceled = await request.put(
      `${origin}${path}/records/${beta.source_ref}`,
      {
        headers: await headers(request),
        data: {
          schema_version: 1,
          record_type: record.record_type,
          mission_id: record.mission_id,
          leg_id: record.leg_id,
          scope: record.scope,
          time: record.time,
          payload: { ...record.payload, status: 'cancelled' },
          expected_version: record.version,
        },
      }
    );
    expect(canceled.ok()).toBe(true);
    expect(
      (await feed(request)).events.some((e) => e.source_ref === beta.source_ref)
    ).toBe(false);
    proof.cancelSuppressed = true;
    const current = await feed(request);
    const upcoming = current.events.find(
      (e) => e.kind === 'call_prep' && e.source_ref === alpha.source_ref
    )!;
    const [first, second] = await Promise.all([
      acknowledge(request, current, upcoming),
      acknowledge(counterpart.request, current, upcoming),
    ]);
    expect(first.ok(), await first.text()).toBe(true);
    expect(second.ok(), await second.text()).toBe(true);
    expect((await first.json()).acknowledgment_id).toBe(
      (await second.json()).acknowledgment_id
    );
    const count = JSON.parse(
      control('event-counts', upcoming.notification.generation!)
    );
    expect(count.acknowledgments).toBe(1);
    expect(count.receipts).toBe(2);
    proof.twoClients = true;
    proof.acknowledgment = true;
    drawer = await refresh(page);
    const alphaCard = drawer
      .locator('li')
      .filter({ has: page.getByText(upcoming.title, { exact: true }) });
    await expect(
      alphaCard.getByRole('button', { name: 'Acknowledged' })
    ).toBeVisible();
    await closeFeed(page);
    await refresh(other);
    await closeFeed(other);
    // A real predictor changes between capture and acknowledgment publication guard.
    const raceSnapshot = await feed(request);
    const model = raceSnapshot.events.find(
      (e) =>
        e.kind === 'restriction' &&
        e.source_ref === 'model:synthetic-leg-1' &&
        e.notification.available &&
        !e.notification.acknowledged
    )!;
    expect(model).toBeTruthy();
    await source(request, { arm_ack_race: true });
    const raced = await acknowledge(request, raceSnapshot, model);
    expect(raced.status()).toBe(409);
    const changed = await source(request, {
      longitude: 4.2,
      timing_basis: 'live',
    });
    const changedFeed = await feed(request);
    expect(
      changedFeed.events.find(
        (event) => event.kind === 'pop_advisory' && event.due_at
      )?.due_at
    ).not.toBe(
      initial.events.find(
        (event) => event.kind === 'pop_advisory' && event.due_at
      )?.due_at
    );
    expect(changed.generation).not.toBe(initialControl.generation);
    proof.actualPopPrediction = true;
    proof.predictionChanged = true;
    await source(request, { available: false });
    const unknown = await feed(request);
    expect(unknown.coverage).toBe('partial');
    expect(
      unknown.events
        .filter((e) => e.provenance === 'modeled')
        .every((e) => !e.notification.eligible)
    ).toBe(true);
    const unavailable = await acknowledge(request, raceSnapshot, model);
    expect(unavailable.status()).toBe(503);
    proof.unavailableSources = true;
    await source(request, { available: true });
    // A lost response leaves a frozen receipt request across browser reload.
    const retryCall = await request.post(`${origin}${path}/records`, {
      headers: await headers(request),
      data: {
        schema_version: 1,
        record_type: 'call',
        mission_id: mission,
        scope: 'mission',
        time: { planned_start_at: '2026-10-17T16:25:00Z' },
        payload: {
          entry_type: 'call',
          title: 'Synthetic receipt retry',
          status: 'scheduled',
          prep_lead_minutes: 10,
        },
      },
    });
    expect(retryCall.ok()).toBe(true);
    await refresh(page);
    let held = true;
    let frozen: { key: string | undefined; body: string | null } | undefined;
    await page.route(`${origin}${path}/events/acknowledge`, async (route) => {
      if (!held) return route.continue();
      held = false;
      frozen = {
        key: route.request().headers()['idempotency-key'],
        body: route.request().postData(),
      };
      await route.fetch();
      await route.abort('failed');
    });
    drawer = await openFeed(page);
    const retryCard = drawer.locator('li').filter({
      has: page.getByText('Prepare: Synthetic receipt retry', {
        exact: true,
      }),
    });
    await retryCard
      .getByRole('button', { name: 'Acknowledge', exact: true })
      .click();
    await expect(
      drawer.getByText('Acknowledgment pending confirmation.')
    ).toBeVisible();
    await closeFeed(page);
    await expect(draft).toHaveValue('Synthetic unsent event-review note');
    proof.draftPreserved = true;
    await page.reload();
    await ready(page);
    drawer = await openFeed(page);
    const replay = page.waitForRequest(
      (r) =>
        r.url().endsWith(`${path}/events/acknowledge`) && r.method() === 'POST'
    );
    await drawer
      .getByRole('button', { name: 'Retry acknowledgment', exact: true })
      .click();
    const replayed = await replay;
    expect(replayed.headers()['idempotency-key']).toBe(frozen!.key);
    expect(replayed.postData()).toBe(frozen!.body);
    await expect(
      drawer.getByText('Acknowledgment pending confirmation.')
    ).toHaveCount(0);
    await closeFeed(page);
    // Journal drafts are page-local; only the frozen acknowledgment survives reload.
    await draft.fill('Synthetic unsent event-review note');
    await context.setOffline(true);
    await page.getByRole('button', { name: 'Open Events' }).click();
    await page
      .getByRole('button', { name: 'Refresh Events', exact: true })
      .click();
    await expect(page.getByText(/Feed unavailable/).first()).toBeVisible({
      timeout: 20000,
    });
    const modelInputs = process.env.OPERATOR_MODEL_ALERTS_ACCEPTANCE === 'true';
    await source(request, {
      now: modelInputs ? '2026-10-17T16:10:00Z' : '2026-10-17T16:20:00Z',
    });
    await context.setOffline(false);
    await refresh(page);
    await expect(page.getByText(/Feed unavailable/)).toHaveCount(0);
    proof.offlineReconnect = true;
    await closeFeed(page);
    control('restart');
    await ready(page);
    drawer = await refresh(page);
    await expect(
      drawer
        .locator('li')
        .filter({ has: page.getByText(upcoming.title, { exact: true }) })
        .getByRole('button', { name: 'Acknowledged' })
    ).toBeVisible();
    expect(
      JSON.parse(control('event-counts', upcoming.notification.generation!))
        .acknowledgments
    ).toBe(1);
    proof.restart = true;
    await closeFeed(page);
    // Two tabs share one IndexedDB reservation; they do not share durable ack side effects.
    const tab = await context.newPage();
    await tab.goto(`${origin}/operator?mission_id=${mission}`);
    await ready(tab);
    const reminder = 'Synthetic same-browser reminder';
    const shared = await request.post(`${origin}${path}/records`, {
      headers: await headers(request),
      data: {
        schema_version: 1,
        record_type: 'call',
        mission_id: mission,
        scope: 'mission',
        time: { planned_start_at: '2026-10-17T16:28:00Z' },
        payload: {
          entry_type: 'call',
          title: reminder,
          status: 'scheduled',
          prep_lead_minutes: 10,
        },
      },
    });
    expect(shared.ok()).toBe(true);
    await refresh(page);
    await closeFeed(page);
    await refresh(tab);
    await closeFeed(tab);
    await expect
      .poll(
        async () => {
          const counts = await Promise.all(
            [page, tab].map((p) =>
              p
                .getByText(/^Local cue:/)
                .filter({ hasText: reminder })
                .count()
            )
          );
          return counts[0] + counts[1];
        },
        { timeout: 45000 }
      )
      .toBe(1);
    proof.sameBrowserDedup = true;
    await tab.close();
    for (const viewport of [
      { width: 1920, height: 1080 },
      { width: 390, height: 844 },
      { width: 844, height: 390 },
    ]) {
      await page.setViewportSize(viewport);
      await refresh(page);
      await expect(
        page.getByRole('dialog', { name: 'Operational Timeline' })
      ).toBeVisible();
      await noOverflow(page);
      await page.screenshot({
        path: join(evidence, `events-${viewport.width}x${viewport.height}.png`),
      });
      (proof.captures as string[]).push(`${viewport.width}x${viewport.height}`);
      await closeFeed(page);
      for (const section of [
        'Communications',
        'Issues',
        'Journal',
        'Display tools',
      ]) {
        await page.getByRole('link', { name: section, exact: true }).click();
        await expect(
          page.getByRole('button', { name: 'Open Events' })
        ).toBeVisible();
      }
      await noOverflow(page);
    }
    expect([...attemptedExternal]).toEqual([]);
    proof.localOnly = true;
    writeFileSync(
      join(evidence, 'events-proof.json'),
      JSON.stringify(proof, null, 2)
    );
  } finally {
    await context.close();
    await counterpart.close();
  }
});

test('aircraft LAN HTTP supports events and acknowledgment without secure-context UUID', async ({
  request,
}) => {
  const lanBrowser = await chromium.launch({
    args: [
      '--host-resolver-rules=MAP operator-aircraft.test 127.0.0.1',
      '--no-proxy-server',
    ],
  });
  const context = await lanBrowser.newContext();
  try {
    const modelInputs = process.env.OPERATOR_MODEL_ALERTS_ACCEPTANCE === 'true';
    await source(request, {
      now: modelInputs ? '2026-10-17T16:10:00Z' : '2026-10-17T16:20:00Z',
    });
    const created = await request.post(`${origin}${path}/records`, {
      headers: await headers(request),
      data: {
        schema_version: 1,
        record_type: 'call',
        mission_id: mission,
        scope: 'mission',
        time: {
          planned_start_at: modelInputs
            ? '2026-10-17T16:20:00Z'
            : '2026-10-17T16:30:00Z',
        },
        payload: {
          entry_type: 'call',
          title: 'Synthetic LAN HTTP requirement',
          status: 'scheduled',
          prep_lead_minutes: 10,
        },
      },
    });
    expect(created.ok()).toBe(true);
    const lanOrigin = new URL(origin);
    lanOrigin.hostname = 'operator-aircraft.test';
    const page = await context.newPage();
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`${lanOrigin.origin}/operator?mission_id=${mission}`);
    expect(
      await page.evaluate(() => ({
        secure: isSecureContext,
        uuid: typeof crypto.randomUUID,
        random: typeof crypto.getRandomValues,
      }))
    ).toEqual({ secure: false, uuid: 'undefined', random: 'function' });
    await ready(page);
    const drawer = await openFeed(page);
    const card = drawer.locator('li').filter({
      has: page.getByText('Prepare: Synthetic LAN HTTP requirement', {
        exact: true,
      }),
    });
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith(`${path}/events/acknowledge`) &&
        r.request().method() === 'POST'
    );
    await card
      .getByRole('button', { name: 'Acknowledge', exact: true })
      .click();
    expect((await response).status()).toBe(200);
    await expect(
      card.getByRole('button', { name: 'Acknowledged' })
    ).toBeVisible();
    expect(errors).toEqual([]);
    writeFileSync(
      join(evidence, 'events-lan-http.json'),
      JSON.stringify(
        {
          actualNonSecureOrigin: true,
          secureContext: false,
          randomUUIDAbsent: true,
          timelineRendered: true,
          acknowledgmentCommitted: true,
          browserErrors: errors,
        },
        null,
        2
      )
    );
  } finally {
    await context.close();
    await lanBrowser.close();
  }
});
