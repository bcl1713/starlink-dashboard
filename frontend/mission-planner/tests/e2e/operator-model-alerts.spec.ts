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
    route_shift: 0,
    stale: false,
    missing_pop: false,
    active: true,
    satellite_longitude: 90,
  });
  let snapshot = await feed(request);
  const restriction = snapshot.events.find(
    (e) => e.kind === 'restriction' && e.transport === 'X' && e.active
  )!;
  expect(restriction?.notification.eligible).toBe(true);
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
        drawer.getByText(restriction.title, { exact: true })
      ).toBeVisible();
      await noOverflow(page);
      await page.screenshot({
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
    await raw(request, { missing_pop: false, route_shift: 8 });
    snapshot = await feed(request);
    expect((await ack(request, snapshot, event)).ok()).toBe(false);
    const moved = snapshot.events.find(
      (e) => e.kind === 'restriction' && e.transport === 'X' && e.active
    )!;
    expect(moved.due_at).not.toBe(event.due_at);
    proof.routeScheduleUpdated = true;
    await raw(request, { active: false });
    snapshot = await feed(request);
    expect(
      snapshot.events
        .filter((e) => e.kind === 'restriction')
        .every((e) => !e.active && !e.notification.eligible)
    ).toBe(true);
    proof.deactivationRetires = true;
    await raw(request, { active: true, route_shift: 0 });
    await contexts[0].setOffline(true);
    await contexts[0].setOffline(false);
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
