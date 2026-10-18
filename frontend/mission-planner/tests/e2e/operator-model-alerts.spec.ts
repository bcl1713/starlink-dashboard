import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { test, expect, type APIRequestContext } from '@playwright/test';
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
const base = `${origin}/api/v2/operator`;
const mission = 'synthetic-mission-a';
async function raw(request: APIRequestContext, data: Record<string, unknown>) {
  const response = await request.post(
    `${origin}/api/_synthetic/operator-model-inputs`,
    { data }
  );
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}
async function feed(request: APIRequestContext): Promise<EventSnapshot> {
  const response = await request.get(
    `${base}/events?mission_id=${mission}&include_history=true`
  );
  expect(response.ok(), await response.text()).toBe(true);
  return response.json();
}
async function ack(
  request: APIRequestContext,
  snapshot: EventSnapshot,
  event: OperationalEvent
) {
  const health = await (await request.get(`${base}/health`)).json();
  return request.post(`${base}/events/acknowledge`, {
    headers: {
      'Idempotency-Key': randomUUID(),
      'X-Operator-Store-Epoch': health.api_epoch,
    },
    data: {
      schema_version: 1,
      occurrence_id: event.notification.generation,
      severity_generation: event.notification.severity_generation,
      snapshot_token: snapshot.snapshot_token,
    },
  });
}
test('real model foreground warning: current inputs, acknowledgment, replacement and restart', async ({
  browser,
  request,
}) => {
  test.setTimeout(300_000);
  const proof: Record<string, unknown> = {
    synthetic: true,
    rawInputsOnly: true,
    captures: [],
  };
  await raw(request, {
    now: '2026-10-17T16:10:00Z',
    route_shift: 14,
    longitude: -9.5,
    latitude: 0,
    speed: 600,
    phase: 'in_flight',
    route_latitude: 0,
    stale: false,
    missing_pop: false,
    active: true,
    satellite_longitude: 90,
    invalid_ka: false,
  });
  let snapshot = await feed(request);
  const restriction = snapshot.events.find(
    (e) => e.kind === 'restriction' && e.transport === 'X' && e.active
  )!;
  expect(restriction?.notification.eligible).toBe(true);
  const approaching =
    Date.parse(restriction.due_at!) - Date.parse(snapshot.as_of);
  expect(approaching).toBeGreaterThan(0);
  expect(approaching).toBeLessThanOrEqual(300_000);
  expect(restriction.protected_participation_ids.length).toBe(3);
  expect(
    snapshot.events.some(
      (e) => e.kind === 'call_start' && e.notification.eligible
    )
  ).toBe(true);
  expect(
    snapshot.events
      .filter((e) => e.kind === 'pop_advisory')
      .every((e) => !e.notification.eligible)
  ).toBe(true);
  proof.incomingProtectedActivity = true;
  const contexts = [];
  try {
    for (const viewport of [
      { width: 1920, height: 1080 },
      { width: 390, height: 844 },
    ]) {
      const context = await browser.newContext({ viewport });
      contexts.push(context);
      await context.addInitScript(() => {
        localStorage.setItem(
          'operator-alert-preferences',
          JSON.stringify({ enabled: false, sound: true, vibration: true })
        );
        (window as unknown as { soundAttempts: number }).soundAttempts = 0;
        if (globalThis.AudioContext) {
          const original = AudioContext.prototype.createOscillator;
          AudioContext.prototype.createOscillator = function () {
            (window as unknown as { soundAttempts: number }).soundAttempts++;
            return original.call(this);
          };
        }
      });
      const page = await context.newPage();
      await page.goto(`${origin}/operator?mission_id=${mission}`);
      await ready(page);
      await page
        .getByRole('button', { name: 'Local alerts', exact: true })
        .click();
      await page
        .getByRole('button', { name: 'Enable sound and vibration' })
        .click();
      await page.getByLabel('In-app cues', { exact: true }).check();
      await page.getByRole('button', { name: 'Close settings' }).click();
      await expect(page.getByText(/^Local cue:.*X modeled/)).toBeVisible({
        timeout: 20_000,
      });
      await expect
        .poll(() =>
          page.evaluate(
            () => (window as unknown as { soundAttempts: number }).soundAttempts
          )
        )
        .toBe(1);
      await page
        .getByRole('button', { name: 'Open events', exact: true })
        .click();
      const drawer = page.getByRole('dialog', { name: 'Operational timeline' });
      await expect(
        drawer.getByText(restriction.title, { exact: true }).first()
      ).toBeVisible();
      await expect
        .poll(async () =>
          drawer.evaluate((element) => {
            const bounds = element.getBoundingClientRect();
            return (
              Math.abs(bounds.top) < 1 &&
              Math.abs(bounds.right - window.innerWidth) < 1
            );
          })
        )
        .toBe(true);
      await noOverflow(page);
      await page.screenshot({
        animations: 'disabled',
        path: join(
          evidence,
          `model-alerts-${viewport.width}x${viewport.height}.png`
        ),
      });
      if (viewport.width === 390) {
        await page.setViewportSize({ width: 844, height: 390 });
        await noOverflow(page);
        await page.screenshot({
          path: join(evidence, 'model-alerts-844x390.png'),
          animations: 'disabled',
        });
      }
      await drawer
        .getByRole('button', { name: 'Refresh events', exact: true })
        .click();
      expect(
        await page.evaluate(
          () => (window as unknown as { soundAttempts: number }).soundAttempts
        )
      ).toBe(1);
    }
    proof.foregroundSoundOnce = true;
    proof.captures = ['1920x1080', '390x844', '844x390'];
    await raw(request, { invalid_ka: true });
    snapshot = await feed(request);
    expect(snapshot.coverage).toBe('partial');
    expect(
      snapshot.events.some(
        (e) => e.transport === 'X' && e.notification.eligible
      )
    ).toBe(true);
    expect(
      snapshot.sources.some((s) => s.reason?.includes('Ka coverage'))
    ).toBe(true);
    proof.partialIndependentWarning = true;
    await raw(request, { invalid_ka: false });
    snapshot = await feed(request);
    const event = snapshot.events.find(
      (e) => e.event_id === restriction.event_id && e.active
    )!;
    const receipts = await Promise.all(
      contexts.map((c) => ack(c.request, snapshot, event))
    );
    expect(receipts.map((r) => r.status())).toEqual([200, 200]);
    snapshot = await feed(request);
    expect(
      snapshot.events.find((e) => e.event_id === event.event_id)?.notification
        .acknowledged
    ).toBe(true);
    const ackState = await (
      await request.get(
        `${origin}/api/_synthetic/operator-model-acknowledgments`
      )
    ).json();
    expect(ackState.modeledAcknowledgments).toBe(1);
    const receiptBodies = await Promise.all(receipts.map((r) => r.json()));
    expect(receiptBodies[0].acknowledgment_id).toBe(
      receiptBodies[1].acknowledgment_id
    );
    proof.twoClientAcknowledgment = true;
    const beforePop = snapshot.sources.find((s) =>
      s.source.endsWith(':live-pop')
    )!;
    await raw(request, { longitude: 4 });
    snapshot = await feed(request);
    const afterPop = snapshot.sources.find((s) =>
      s.source.endsWith(':live-pop')
    )!;
    expect(afterPop.generation).not.toBe(beforePop.generation);
    expect(
      snapshot.events.find((e) => e.event_id === event.event_id)?.notification
        .acknowledged
    ).toBe(true);
    proof.positionUpdatesActualPop = true;
    await raw(request, { stale: true });
    snapshot = await feed(request);
    expect(snapshot.coverage).toBe('partial');
    expect(
      snapshot.events
        .filter((e) => e.kind === 'restriction')
        .every((e) => !e.notification.eligible)
    ).toBe(true);
    expect(snapshot.sources.some((s) => s.reason?.includes('stale'))).toBe(
      true
    );
    const page = contexts[1].pages()[0];
    await page
      .getByRole('button', { name: 'Refresh events', exact: true })
      .click();
    await expect(
      page.getByText('Position or speed evidence stale or unavailable', {
        exact: true,
      })
    ).toBeVisible();
    proof.staleReason = true;
    await raw(request, { stale: false, missing_pop: true });
    snapshot = await feed(request);
    expect(snapshot.coverage).toBe('partial');
    expect(
      snapshot.events
        .filter((e) => e.kind === 'restriction')
        .every((e) => !e.notification.eligible)
    ).toBe(true);
    proof.unavailableReason = true;
    const obsoleteSnapshot = snapshot;
    await raw(request, { missing_pop: false, route_shift: 8 });
    snapshot = await feed(request);
    expect((await ack(request, obsoleteSnapshot, event)).ok()).toBe(false);
    const moved = snapshot.events.find(
      (e) => e.kind === 'restriction' && e.transport === 'X' && e.active
    )!;
    expect(moved.planned_due_at).not.toBe(event.planned_due_at);
    expect(moved.due_at).not.toBe(moved.planned_due_at);
    proof.routeScheduleUpdated = true;
    await raw(request, { active: false });
    snapshot = await feed(request);
    expect(
      snapshot.events
        .filter((e) => e.kind === 'restriction')
        .every((e) => !e.active && !e.notification.eligible)
    ).toBe(true);
    proof.deactivationRetires = true;
    await raw(request, { active: true, route_shift: 14 });
    await contexts[0].setOffline(true);
    const offlinePage = contexts[0].pages()[0];
    await offlinePage
      .getByRole('button', { name: 'Refresh events', exact: true })
      .click();
    await expect(
      offlinePage.getByText(/Feed unavailable. Last-known events/)
    ).toBeVisible();
    await contexts[0].setOffline(false);
    await offlinePage
      .getByRole('button', { name: 'Refresh events', exact: true })
      .click();
    proof.offlineReconnect = true;
    control('restart');
    await ready(page);
    snapshot = await feed(request);
    expect(
      snapshot.events.find(
        (e) => e.notification.generation === event.notification.generation
      )?.notification.acknowledged
    ).toBe(true);
    expect(
      snapshot.events
        .filter((e) => e.kind === 'restriction' && e.active)
        .every((e) => !e.notification.eligible)
    ).toBe(true);
    proof.restartNoResurrection = true;
    writeFileSync(
      join(evidence, 'model-alerts-proof.json'),
      JSON.stringify(proof, null, 2)
    );
  } finally {
    for (const context of contexts) await context.close();
  }
});

test('real model foreground warning follows airborne progress after late departure', async ({
  browser,
  request,
}) => {
  test.setTimeout(180_000);
  await raw(request, {
    now: '2026-10-17T16:45:00Z',
    route_shift: 0,
    longitude: -10,
    latitude: 0,
    speed: 300,
    route_latitude: 0.1,
    phase: 'in_flight',
    active: true,
    stale: false,
    missing_pop: false,
    invalid_ka: false,
  });
  const find = (snapshot: EventSnapshot) =>
    snapshot.events.find(
      (e) => e.kind === 'restriction' && e.transport === 'X' && e.active
    )!;
  const before = await feed(request);
  const distant = find(before);
  expect(distant.time_basis).toBe('live_route_eta');
  expect(Date.parse(distant.planned_due_at!)).toBeLessThan(
    Date.parse(before.as_of)
  );
  const remaining = Date.parse(distant.due_at!) - Date.parse(before.as_of);
  expect(remaining).toBeGreaterThan(300_000);
  expect(remaining).toBeLessThan(600_000);
  expect(distant.notification.eligible).toBe(false);
  await raw(request, { route_shift: 60 });
  const early = find(await feed(request));
  expect(early.due_at).toBe(distant.due_at);
  expect(Date.parse(early.planned_due_at!)).toBeGreaterThan(
    Date.parse(before.as_of)
  );
  await raw(request, { route_shift: 0 });
  const contexts = [];
  const times = [];
  try {
    for (const viewport of [
      { width: 1920, height: 1080 },
      { width: 390, height: 844 },
    ]) {
      const context = await browser.newContext({ viewport });
      contexts.push(context);
      await context.addInitScript(() => {
        localStorage.setItem(
          'operator-alert-preferences',
          JSON.stringify({ enabled: false, sound: true, vibration: true })
        );
        (window as unknown as { soundAttempts: number }).soundAttempts = 0;
        const original = AudioContext.prototype.createOscillator;
        AudioContext.prototype.createOscillator = function () {
          (window as unknown as { soundAttempts: number }).soundAttempts++;
          return original.call(this);
        };
      });
      const page = await context.newPage();
      await page.goto(`${origin}/operator?mission_id=${mission}`);
      await ready(page);
      await page
        .getByRole('button', { name: 'Local alerts', exact: true })
        .click();
      await page
        .getByRole('button', { name: 'Enable sound and vibration' })
        .click();
      await page.getByLabel('In-app cues', { exact: true }).check();
      await page.getByRole('button', { name: 'Close settings' }).click();
      await page
        .getByRole('button', { name: 'Open events', exact: true })
        .click();
      const dialog = page.getByRole('dialog', { name: 'Operational timeline' });
      await expect(
        dialog.getByText('Live route ETA · fresh').first()
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => (window as unknown as { soundAttempts: number }).soundAttempts
        )
      ).toBe(0);
    }
    await raw(request, { speed: 1200 });
    const near = await feed(request);
    const approaching = find(near);
    expect(approaching.notification.generation).toBe(
      distant.notification.generation
    );
    expect(approaching.notification.eligible).toBe(true);
    expect(
      Date.parse(approaching.due_at!) - Date.parse(near.as_of)
    ).toBeLessThan(300_000);
    for (const context of contexts) {
      const page = context.pages()[0];
      await page
        .getByRole('button', { name: 'Refresh events', exact: true })
        .click();
      const card = page
        .getByRole('listitem')
        .filter({ has: page.getByText(approaching.title, { exact: true }) })
        .first();
      await expect(
        card.getByText(
          new RegExp(approaching.due_at!.slice(0, 19).replace('T', ' '))
        )
      ).toBeVisible();
      await expect
        .poll(() =>
          page.evaluate(
            () => (window as unknown as { soundAttempts: number }).soundAttempts
          )
        )
        .toBe(1);
      await card.scrollIntoViewIfNeeded();
      await expect(card).toBeInViewport();
      await noOverflow(page);
      await page.screenshot({
        animations: 'disabled',
        path: join(evidence, `live-eta-${page.viewportSize()!.width}.png`),
      });
    }
    times.push({ scenario: 'late45min', distant, approaching });
    await raw(request, { speed: 300, latitude: 1 });
    const deviated = find(await feed(request));
    expect(deviated.notification.eligible).toBe(false);
    expect(deviated.event_id).toBe(distant.event_id);
    for (const context of contexts) {
      const page = context.pages()[0];
      await page
        .getByRole('button', { name: 'Refresh events', exact: true })
        .click();
      const card = page
        .getByRole('listitem')
        .filter({ has: page.getByText(deviated.title, { exact: true }) })
        .first();
      await expect(
        card.getByText(
          new RegExp(deviated.due_at!.slice(0, 19).replace('T', ' '))
        )
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => (window as unknown as { soundAttempts: number }).soundAttempts
        )
      ).toBe(1);
    }
    await raw(request, { latitude: 0 });
    const rejoined = find(await feed(request));
    expect(rejoined.due_at).toBe(distant.due_at);
    await raw(request, { route_latitude: 0.2 });
    const rerouted = find(await feed(request));
    expect(rerouted.event_id).not.toBe(distant.event_id);
    await raw(request, { speed: 0 });
    const unavailable = find(await feed(request));
    expect(unavailable.time_basis).toBe('live_unavailable');
    expect(unavailable.due_at).toBeNull();
    expect(unavailable.notification.eligible).toBe(false);
    for (const context of contexts) {
      const page = context.pages()[0];
      await page
        .getByRole('button', { name: 'Refresh events', exact: true })
        .click();
      expect(
        await page.evaluate(
          () => (window as unknown as { soundAttempts: number }).soundAttempts
        )
      ).toBe(1);
    }
    for (const context of contexts) {
      await expect(
        context
          .pages()[0]
          .getByText('Live timing unavailable · unknown')
          .first()
      ).toBeVisible();
    }
    writeFileSync(
      join(evidence, 'live-eta-proof.json'),
      JSON.stringify(
        {
          synthetic: true,
          rawInputsOnly: true,
          lateDeparture: true,
          earlyDeparture: true,
          speedThreshold: true,
          displayedTimeMatches: true,
          foregroundSoundOnce: true,
          deviationRejoin: true,
          revisedRoute: true,
          unavailableExplicit: true,
          viewports: [1920, 390],
          times,
        },
        null,
        2
      )
    );
  } finally {
    for (const context of contexts) await context.close();
  }
});
