import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, type Page } from '@playwright/test';
import type { SavedRecord } from '@/types/operator';
import {
  control,
  evidence,
  noOverflow,
  origin,
  ready,
  mutation,
  snapshot,
} from './operator-journal-helpers';
const path = '/api/v2/operator/records';
const url = `${origin}/operator?mission_id=synthetic-mission-a`;
async function open(page: Page) {
  await page.goto(url);
  await ready(page);
  await page
    .locator('summary')
    .filter({ hasText: /^Conferences and customers$/ })
    .click();
  return page.getByRole('region', {
    name: 'Conferences and customers',
    exact: true,
  });
}
async function tap(page: Page, action: () => Promise<void>) {
  const result = page.waitForResponse((r) => mutation(r.request()));
  await action();
  const response = await result;
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()).saved_records[0];
}
test('independent conferences and customers survive overlaps, retry and restart', async ({
  browser,
}) => {
  const proof: Record<string, unknown> = { synthetic: true, captures: [] };
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    const context = await browser.newContext({
      viewport,
      timezoneId: 'Pacific/Honolulu',
    });
    try {
      await context.route('**/*', (route) =>
        new URL(route.request().url()).origin === origin ||
        route.request().url().startsWith('data:')
          ? route.continue()
          : route.abort()
      );
      const page = await context.newPage();
      const region = await open(page);
      await region
        .getByRole('button', { name: 'New conference', exact: true })
        .click();
      const name = `Synthetic conference ${viewport.width}`;
      await region.getByLabel('Conference name (optional)').fill(name);
      const conference = await tap(page, () =>
        region
          .getByRole('button', { name: 'Save conference', exact: true })
          .click()
      );
      const card = region.getByRole('article', {
        name: `Conference ${name}`,
        exact: true,
      });
      const epoch = (
        await (await page.request.get('/api/v2/operator/health')).json()
      ).api_epoch;
      const headers = {
        'X-Operator-Store-Epoch': epoch,
        'Idempotency-Key': crypto.randomUUID(),
      };
      const callBody = {
        schema_version: 1,
        mission_id: 'synthetic-mission-a',
        scope: 'mission',
        leg_id: null,
        record_type: 'call',
        time: {
          planned_start_at: '2026-10-17T16:00:00Z',
          planned_end_at: '2026-10-17T16:30:00Z',
        },
        payload: {
          entry_type: 'call',
          title: `Synthetic shared call ${viewport.width}`,
          status: 'scheduled',
          conference_id: conference.record_id,
          prep_lead_minutes: null,
        },
      };
      const call = (
        await (
          await page.request.post(path, { headers, data: callBody })
        ).json()
      ).saved_records[0];
      expect(call).toBeTruthy();
      const secondCallBody = {
        ...callBody,
        time: {
          planned_start_at: '2026-10-17T16:05:00Z',
          planned_end_at: '2026-10-17T16:35:00Z',
        },
        payload: {
          ...callBody.payload,
          title: `Synthetic overlapping call ${viewport.width}`,
        },
      };
      const secondCall = (
        await (
          await page.request.post(path, {
            headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
            data: secondCallBody,
          })
        ).json()
      ).saved_records[0];
      expect(secondCall.payload.conference_id).toBe(call.payload.conference_id);
      // Customer-first then conference establishment; both states remain independent.
      const first = await tap(page, () =>
        card
          .getByRole('button', { name: 'Customer Joined', exact: true })
          .click()
      );
      await tap(page, () =>
        card.getByRole('button', { name: 'Establish', exact: true }).click()
      );
      await tap(page, () =>
        card.getByRole('button', { name: 'Verify', exact: true }).click()
      );
      const second = await tap(page, () =>
        card
          .getByRole('button', { name: 'Customer Joined', exact: true })
          .click()
      );
      expect(first.payload.conference_id).toBe(second.payload.conference_id);
      await expect(
        card.getByText('Customer reported connected: 2')
      ).toBeVisible();
      for (const [joined, linkedCall] of [
        [first, call],
        [second, secondCall],
      ]) {
        const association = await page.request.put(
          `${path}/${joined.record_id}`,
          {
            headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
            data: {
              schema_version: 1,
              record_type: 'participation',
              mission_id: joined.mission_id,
              scope: joined.scope,
              leg_id: joined.leg_id,
              time: joined.time,
              payload: { ...joined.payload, call_id: linkedCall.record_id },
              expected_version: joined.version,
            },
          }
        );
        expect(association.ok(), await association.text()).toBeTruthy();
      }
      await region
        .getByRole('button', {
          name: 'Refresh conferences and customers',
          exact: true,
        })
        .click();
      await expect(
        region.getByText(`Call: ${call.record_id}`, { exact: false })
      ).toBeVisible();
      await expect(
        region.getByText(`Call: ${secondCall.record_id}`, { exact: false })
      ).toBeVisible();
      proof.joiningOrders = true;
      proof.overlap = true;
      const customer = region
        .getByRole('article', { name: 'Customer Unknown', exact: true })
        .filter({ hasText: name });
      const interrupted = await tap(page, () =>
        customer
          .first()
          .getByRole('button', { name: 'Interrupt customer', exact: true })
          .click()
      );
      const resumed = await tap(page, () =>
        customer
          .getByRole('button', { name: 'Restore connection', exact: true })
          .click()
      );
      expect(resumed.record_id).not.toBe(interrupted.record_id);
      expect(resumed.payload.resumes_participation_id).toBe(
        interrupted.record_id
      );
      expect(resumed.reason).toBe('Customer connection restored');
      proof.interruptRestore = true;
      // Completing/rescheduling/cancelling two calls never closes the shared conference.
      for (const status of ['cancelled', 'delayed', 'completed']) {
        expect(
          (
            await page.request.put(`${path}/${call.record_id}`, {
              headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
              data: {
                ...callBody,
                expected_version: call.version,
                payload: { ...callBody.payload, status },
              },
            })
          ).ok()
        ).toBeTruthy();
        call.version++;
      }
      expect(
        (
          await page.request.put(`${path}/${secondCall.record_id}`, {
            headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
            data: {
              ...secondCallBody,
              expected_version: secondCall.version,
              payload: { ...secondCallBody.payload, status: 'cancelled' },
            },
          })
        ).ok()
      ).toBeTruthy();
      const still = (
        await (await page.request.get(`${path}/${conference.record_id}`)).json()
      ).record;
      expect(still.payload.status).toBe('established');
      proof.reuse = true;
      await tap(page, () =>
        card
          .getByRole('button', { name: 'Close conference', exact: true })
          .click()
      );
      await expect(card.getByRole('alert')).toContainText('Continuity unknown');
      proof.discrepancy = true;
      await expect(
        region.getByText(
          'Modeled restrictions only. Operator-planned transport changes are not included.',
          { exact: true }
        )
      ).toBeVisible();
      await expect(
        region.getByText(/Coverage: (partial|available)/)
      ).toBeVisible();
      const advisoryPanel = region.getByRole('complementary', {
        name: 'Protected call advisories',
      });
      await expect(
        advisoryPanel
          .getByRole('listitem')
          .filter({ hasText: /^advisory · unknown transport relevance/ })
          .first()
      ).toBeVisible();
      await expect(
        advisoryPanel
          .getByRole('listitem')
          .filter({ hasText: /^planned outage/ })
          .first()
      ).toBeVisible();
      proof.sourceCoverage = true;
      if (viewport.width === 1920) {
        const other = await context.newPage();
        const otherRegion = await open(other);
        const same = otherRegion.getByRole('article', {
          name: `Conference ${name}`,
          exact: true,
        });
        await expect(same.getByRole('alert')).toContainText(
          'Continuity unknown'
        );
        const prior = (
          await (
            await page.request.get(`${path}/${conference.record_id}`)
          ).json()
        ).record;
        const stale = await page.request.put(
          `${path}/${conference.record_id}`,
          {
            headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
            data: {
              schema_version: 1,
              record_type: 'conference',
              mission_id: prior.mission_id,
              scope: prior.scope,
              leg_id: prior.leg_id,
              time: prior.time,
              payload: prior.payload,
              expected_version: 1,
            },
          }
        );
        expect(stale.status()).toBe(409);
        proof.twoClients = true;
        // Lose an acknowledged join response, then replay the exact frozen command.
        const requests: ReturnType<typeof snapshot>[] = [];
        let lose = true;
        let uncertain: SavedRecord | undefined;
        await page.route(`${origin}${path}**`, async (route) => {
          if (!mutation(route.request())) return route.continue();
          requests.push(snapshot(route.request()));
          if (lose) {
            lose = false;
            const response = await route.fetch();
            uncertain = (await response.json()).saved_records[0];
            await route.abort('failed');
          } else await route.continue();
        });
        await card
          .getByRole('button', { name: 'Customer Joined', exact: true })
          .click();
        await expect(
          region.getByRole('button', {
            name: 'Retry same customer save',
            exact: true,
          })
        ).toBeVisible();
        await expect(
          page.getByLabel('Mission ID', { exact: true })
        ).toBeDisabled();
        expect(uncertain).toBeTruthy();
        const committed = uncertain!;
        const beforeReplay = (
          await (
            await other.request.get(path, {
              params: {
                mission_id: 'synthetic-mission-a',
                record_type: 'participation',
              },
            })
          ).json()
        ).items.length;
        const correction = await other.request.put(
          `${path}/${committed.record_id}`,
          {
            headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() },
            data: {
              schema_version: 1,
              record_type: 'participation',
              mission_id: committed.mission_id,
              scope: committed.scope,
              leg_id: committed.leg_id,
              time: {
                ...committed.time,
                ended_at: committed.time.occurred_at,
                end_state: 'known',
              },
              payload: {
                ...committed.payload,
                state: 'left',
                participant: 'Synthetic counterpart correction',
              },
              expected_version: committed.version,
            },
          }
        );
        expect(correction.ok(), await correction.text()).toBeTruthy();
        await region
          .getByRole('button', {
            name: 'Retry same customer save',
            exact: true,
          })
          .click();
        await expect(
          region.getByText('Conference/customer action saved.', { exact: true })
        ).toBeVisible();
        await expect(
          region.getByRole('button', {
            name: 'Retry same customer save',
            exact: true,
          })
        ).toHaveCount(0);
        expect(requests).toHaveLength(2);
        expect(requests[1]).toEqual(requests[0]);
        proof.retryFrozenTime = true;
        const latestCustomer = (
          await (
            await page.request.get(`${path}/${committed.record_id}`)
          ).json()
        ).record;
        expect(latestCustomer.version).toBe(2);
        expect(latestCustomer.payload.state).toBe('left');
        await expect(
          region.getByRole('article', {
            name: 'Customer Synthetic counterpart correction',
            exact: true,
          })
        ).toContainText('left');
        const afterReplay = (
          await (
            await other.request.get(path, {
              params: {
                mission_id: 'synthetic-mission-a',
                record_type: 'participation',
              },
            })
          ).json()
        ).items.length;
        expect(afterReplay).toBe(beforeReplay);
        expect(JSON.parse(control('counts', requests[0].key))).toEqual({
          receipts: 1,
          revisions: 1,
        });
        proof.retryConcurrentEdit = true;
        control('restart');
        await ready(page);
        await page.reload();
        await ready(page);
        await page
          .locator('summary')
          .filter({ hasText: /^Conferences and customers$/ })
          .click();
        expect(
          (
            await (
              await page.request.get(`${path}/${conference.record_id}`)
            ).json()
          ).record
        ).toEqual(prior);
        proof.restart = true;
        await other.close();
      }
      await noOverflow(page);
      await page
        .getByRole('region', { name: 'Conferences and customers', exact: true })
        .scrollIntoViewIfNeeded();
      await page.screenshot({
        path: join(
          evidence,
          `conferences-${viewport.width}x${viewport.height}.png`
        ),
        fullPage: true,
      });
      (proof.captures as string[]).push(`${viewport.width}x${viewport.height}`);
    } finally {
      await context.close();
    }
  }
  writeFileSync(
    join(evidence, 'conferences-proof.json'),
    JSON.stringify(proof, null, 2)
  );
});
