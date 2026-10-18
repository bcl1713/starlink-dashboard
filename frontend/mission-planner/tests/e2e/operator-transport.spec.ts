import { randomUUID } from 'node:crypto';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  chromium,
  test,
  expect,
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
import type { SavedRecord } from '../../src/types/operator';
import type { EventSnapshot } from '../../src/types/operatorEvents';
const base = `${origin}/api/v2/operator`;
const mission = 'synthetic-mission-a';
async function headers(request: APIRequestContext) {
  return {
    'Idempotency-Key': randomUUID(),
    'X-Operator-Store-Epoch': (
      await (await request.get(`${base}/health`)).json()
    ).api_epoch,
  };
}
async function create(
  request: APIRequestContext,
  type: string,
  payload: Record<string, unknown>,
  time: Record<string, unknown> = {}
) {
  const response = await request.post(`${base}/records`, {
    headers: await headers(request),
    data: {
      schema_version: 1,
      record_type: type,
      mission_id: mission,
      scope: 'mission',
      leg_id: null,
      time,
      payload: {
        title: 'Synthetic transport customer',
        entry_type: type,
        ...payload,
      },
    },
  });
  expect(response.ok(), await response.text()).toBe(true);
  return (await response.json()).saved_records[0] as SavedRecord;
}
async function feed(request: APIRequestContext): Promise<EventSnapshot> {
  const response = await request.get(`${base}/events?mission_id=${mission}`);
  expect(response.ok()).toBe(true);
  return response.json();
}
async function raw(request: APIRequestContext, data: Record<string, unknown>) {
  const response = await request.post(
    `${origin}/api/_synthetic/operator-model-inputs`,
    { data }
  );
  expect(response.ok(), await response.text()).toBe(true);
}
async function save(page: Page) {
  const editor = page.getByRole('form', { name: 'Transport decision editor' });
  const response = page.waitForResponse(
    (r) =>
      r.url().includes('/api/v2/operator/records') &&
      ['POST', 'PUT'].includes(r.request().method())
  );
  await editor.getByRole('button', { name: 'Save transport decision' }).click();
  const result = await response;
  expect(result.ok(), await result.text()).toBe(true);
  await expect(
    page.getByText('Transport save acknowledged.', { exact: true })
  ).toBeVisible();
  return (await result.json()).saved_records[0] as SavedRecord;
}
async function replace(
  request: APIRequestContext,
  current: SavedRecord,
  changes: Record<string, unknown>
) {
  return request.put(`${base}/records/${current.record_id}`, {
    headers: await headers(request),
    data: {
      schema_version: 1,
      record_type: current.record_type,
      mission_id: current.mission_id,
      scope: current.scope,
      leg_id: current.leg_id,
      time: current.time,
      payload: current.payload,
      expected_version: current.version,
      ...changes,
    },
  });
}

test('transport decision production: mobile entry, customer context, durability and conflicts', async ({
  browser,
  request,
}) => {
  test.setTimeout(600_000);
  const proof: Record<string, unknown> = { synthetic: true, captures: [] };
  await raw(request, {
    now: '2026-10-17T16:45:00Z',
    route_shift: 0,
    longitude: -10,
    latitude: 0,
    speed: 300,
    phase: 'in_flight',
    route_latitude: 0,
    stale: false,
    missing_pop: false,
    active: true,
    satellite_longitude: 90,
    invalid_ka: false,
  });
  let snapshot = await feed(request);
  const x = snapshot.events.find((e) => e.transport === 'X' && e.active)!;
  expect(x.time_basis).toBe('live_route_eta');
  expect(Date.parse(x.due_at!)).toBeGreaterThan(Date.parse(snapshot.as_of));
  expect(Date.parse(x.planned_due_at!)).toBeLessThan(
    Date.parse(snapshot.as_of)
  );
  const customer = await create(
    request,
    'call',
    { status: 'scheduled', prep_lead_minutes: 10 },
    { planned_start_at: snapshot.as_of, planned_end_at: '2026-10-17T18:00:00Z' }
  );
  const conference = await create(request, 'conference', {
    status: 'established',
  });
  await create(request, 'participation', {
    state: 'connected',
    call_id: customer.record_id,
    conference_id: conference.record_id,
  });
  const contexts = [];
  const savedIds: string[] = [];
  try {
    for (const [width, height] of [
      [1920, 1080],
      [390, 844],
      [844, 390],
    ]) {
      const context = await browser.newContext({ viewport: { width, height } });
      contexts.push(context);
      const page = await context.newPage();
      const errors: string[] = [];
      page.on('pageerror', (e) => {
        errors.push(e.message);
        console.error('Synthetic transport page error', e.message);
      });
      await page.goto('/operator?mission_id=' + mission);
      await ready(page);
      const section = page.getByRole('region', {
        name: 'Operator transport decisions',
      });
      await section
        .getByLabel('Service 1', { exact: true })
        .fill(`Synthetic IPTV ${width}`);
      await section.getByLabel('Reported Applied 1', { exact: true }).check();
      await section
        .getByLabel('Applied transport 1', { exact: true })
        .selectOption('Ka');
      let saved = await save(page);
      savedIds.push(saved.record_id);
      expect(saved.payload).toMatchObject({
        services: [
          {
            intended: null,
            requested: null,
            checked: null,
            applied: { transport: 'Ka', time: { at: null } },
          },
        ],
      });
      proof.appliedOnly = true;
      await section.getByLabel('Requested 1', { exact: true }).check();
      await section
        .getByLabel('Requested transport 1', { exact: true })
        .selectOption('X');
      await section.getByLabel('Operator Checked 1', { exact: true }).check();
      await section
        .getByLabel('Check result 1', { exact: true })
        .selectOption('satisfactory');
      await section
        .getByRole('button', { name: 'Add service', exact: true })
        .click();
      await section
        .getByLabel('Service 2', { exact: true })
        .fill('Secure voice');
      await section.getByLabel('Intended 2', { exact: true }).check();
      await section
        .getByLabel('Intended transport 2', { exact: true })
        .selectOption('Starshield');
      await section
        .getByText('Reason, timing and associations (optional)', {
          exact: true,
        })
        .click();
      await section
        .getByLabel('Reason', { exact: true })
        .fill('Synthetic bandwidth preservation');
      await section
        .getByLabel('Related call ID', { exact: true })
        .fill(customer.record_id);
      await section
        .getByLabel('Related conference ID', { exact: true })
        .fill(conference.record_id);
      await section
        .getByLabel('Planned change start UTC', { exact: true })
        .fill('2026-10-17T16:50:00');
      saved = await save(page);
      if (saved.payload.entry_type !== 'transport_decision')
        throw new Error('Wrong payload');
      expect(saved.payload.services).toHaveLength(2);
      expect(saved.payload.services[0].requested?.transport).toBe('X');
      expect(saved.payload.services[0].applied?.transport).toBe('Ka');
      proof.multiService = proof.independentReports = true;
      await section
        .getByLabel('Applied time 1 UTC', { exact: true })
        .fill('2026-10-17T16:44:00');
      await expect(
        section.getByLabel('Operator Checked 1', { exact: true })
      ).not.toBeChecked();
      saved = await save(page);
      const history = await (
        await request.get(`${base}/records/${saved.record_id}/history`)
      ).json();
      expect(history.items).toHaveLength(3);
      expect(
        history.items[0].record.payload.services[0].applied.time.at
      ).toBeNull();
      proof.retrospectiveCorrection = true;
      await expect(
        section.getByText('Actual routing unknown.', { exact: true })
      ).toHaveCount(1);
      proof.unknownActualRouting = true;
      await expect(
        section.getByText(/Customer communications are active/)
      ).toBeVisible();
      await expect(
        section.getByRole('button', { name: 'Save transport decision' })
      ).toBeEnabled();
      proof.activeCallAdvisory = true;
      await section.scrollIntoViewIfNeeded();
      await noOverflow(page);
      await page.screenshot({
        path: join(evidence, `transport-${width}x${height}.png`),
      });
      (proof.captures as string[]).push(`${width}x${height}`);
      expect(errors).toEqual([]);
    }
    const first = contexts[0].pages()[0];
    const other = await contexts[1].newPage();
    await other.goto('/operator?mission_id=' + mission);
    await ready(other);
    const id = savedIds[0];
    const record = (await (await request.get(`${base}/records/${id}`)).json())
      .record as SavedRecord;
    const card = other
      .getByRole('region', { name: 'Operator transport decisions' })
      .getByRole('listitem')
      .filter({
        has: other.getByRole('heading', {
          name: record.payload.title,
          exact: true,
        }),
      });
    await card.getByRole('button', { name: 'Correct this decision' }).click();
    const update = await replace(request, record, {
      payload: { ...record.payload, reason: 'Other client correction' },
    });
    expect(update.ok()).toBe(true);
    await other
      .getByRole('form', { name: 'Transport decision editor' })
      .getByRole('button', { name: 'Save transport decision' })
      .click();
    await expect(
      other.getByText(/Transport conflict or changed store/)
    ).toBeVisible();
    proof.twoClientConflict = true;
    await first
      .getByRole('button', { name: 'Record another move', exact: true })
      .click();
    await first
      .getByLabel('Service 1', { exact: true })
      .fill('Synthetic lost response');
    await first.getByLabel('Reported Applied 1', { exact: true }).check();
    let captured = false;
    await first.route(`${base}/records`, async (route) => {
      if (route.request().method() === 'POST' && !captured) {
        captured = true;
        const response = await route.fetch();
        expect(response.ok()).toBe(true);
        await route.abort('failed');
      } else await route.continue();
    });
    await first
      .getByRole('form', { name: 'Transport decision editor' })
      .getByRole('button', { name: 'Save transport decision' })
      .click();
    await expect(
      first.getByRole('button', { name: 'Retry transport save' })
    ).toBeVisible();
    await first.reload();
    await first.getByRole('button', { name: 'Retry transport save' }).click();
    await expect(
      first.getByText('Transport save acknowledged.', { exact: true })
    ).toBeVisible();
    proof.lostReceipt = true;
    await contexts[0].setOffline(true);
    await first
      .getByRole('button', { name: 'Record another move', exact: true })
      .click();
    await first
      .getByLabel('Service 1', { exact: true })
      .fill('Synthetic offline move');
    await first
      .getByRole('form', { name: 'Transport decision editor' })
      .getByRole('button', { name: 'Save transport decision' })
      .click();
    await expect(
      first.getByRole('button', { name: 'Retry transport save' })
    ).toBeVisible();
    await contexts[0].setOffline(false);
    await first.getByRole('button', { name: 'Retry transport save' }).click();
    await expect(
      first.getByText('Transport save acknowledged.', { exact: true })
    ).toBeVisible();
    proof.offlineReconnect = true;
    // Dependency conflicts and explicit reconciliation use actual public APIs.
    let response = await request.post(
      `${base}/records/${customer.record_id}/remove`,
      {
        headers: await headers(request),
        data: { expected_version: 1, schema_version: 1 },
      }
    );
    expect(response.status()).toBe(409);
    for (const linkedId of savedIds) {
      const current = (
        await (await request.get(`${base}/records/${linkedId}`)).json()
      ).record as SavedRecord;
      const moved = await replace(request, current, {
        mission_id: 'synthetic-mission-b',
      });
      expect(moved.status()).toBe(409);
      const detached = await replace(request, current, {
        payload: { ...current.payload, call_id: null, conference_id: null },
        mission_id: 'synthetic-mission-b',
      });
      expect(detached.ok()).toBe(true);
    }
    proof.crossMission = true;
    // The connected participation is another dependent; remove it before target.
    const all = await (
      await request.get(`${base}/records?mission_id=${mission}`)
    ).json();
    for (const item of all.items)
      if (
        item.record.payload.entry_type === 'participation' &&
        item.record.payload.call_id === customer.record_id
      ) {
        response = await request.post(
          `${base}/records/${item.record.record_id}/remove`,
          {
            headers: await headers(request),
            data: { expected_version: item.record.version, schema_version: 1 },
          }
        );
        expect(response.ok()).toBe(true);
      }
    response = await request.post(
      `${base}/records/${customer.record_id}/remove`,
      {
        headers: await headers(request),
        data: { expected_version: 1, schema_version: 1 },
      }
    );
    expect(response.ok(), await response.text()).toBe(true);
    response = await request.post(
      `${base}/records/${customer.record_id}/restore`,
      {
        headers: await headers(request),
        data: { expected_version: 2, schema_version: 1 },
      }
    );
    expect(response.ok()).toBe(true);

    const linked = await create(request, 'transport_decision', {
      title: 'Synthetic restore integrity',
      call_id: customer.record_id,
      services: [
        {
          row_id: randomUUID(),
          service: 'Secure voice',
          applied: { transport: 'Ka' },
        },
      ],
    });
    response = await request.post(
      `${base}/records/${linked.record_id}/remove`,
      {
        headers: await headers(request),
        data: { expected_version: 1, schema_version: 1 },
      }
    );
    expect(response.ok()).toBe(true);
    response = await request.post(
      `${base}/records/${customer.record_id}/remove`,
      {
        headers: await headers(request),
        data: { expected_version: 3, schema_version: 1 },
      }
    );
    expect(response.ok()).toBe(true);
    response = await request.post(
      `${base}/records/${linked.record_id}/restore`,
      {
        headers: await headers(request),
        data: { expected_version: 2, schema_version: 1 },
      }
    );
    expect(response.status()).toBe(409);
    response = await request.post(
      `${base}/records/${customer.record_id}/restore`,
      {
        headers: await headers(request),
        data: { expected_version: 4, schema_version: 1 },
      }
    );
    expect(response.ok()).toBe(true);
    response = await request.post(
      `${base}/records/${linked.record_id}/restore`,
      {
        headers: await headers(request),
        data: { expected_version: 2, schema_version: 1 },
      }
    );
    expect(response.ok()).toBe(true);
    proof.linkRemoveRestore = true;
    const lanBrowser = await chromium.launch({
      args: [
        '--host-resolver-rules=MAP operator-aircraft.test 127.0.0.1',
        '--no-proxy-server',
      ],
    });
    const lanContext = await lanBrowser.newContext({
      viewport: { width: 390, height: 844 },
    });
    try {
      const lanOrigin = new URL(origin);
      lanOrigin.hostname = 'operator-aircraft.test';
      const lan = await lanContext.newPage();
      await lan.goto(`${lanOrigin.origin}/operator?mission_id=${mission}`);
      expect(
        await lan.evaluate(() => ({
          secure: isSecureContext,
          uuid: typeof crypto.randomUUID,
        }))
      ).toEqual({ secure: false, uuid: 'undefined' });
      await lan
        .getByLabel('Service 1', { exact: true })
        .fill('Synthetic nonsecure LAN move');
      await lan.getByLabel('Reported Applied 1', { exact: true }).check();
      const lanSaved = await save(lan);
      expect(lanSaved.record_type).toBe('transport_decision');
      proof.lanHttp = true;
    } finally {
      await lanContext.close();
      await lanBrowser.close();
    }
    const original = JSON.stringify(
      (await (await request.get(`${base}/records/${savedIds[0]}`)).json())
        .record
    );
    await raw(request, { speed: 1200 });
    const faster = await feed(request);
    expect(
      Date.parse(faster.events.find((e) => e.event_id === x.event_id)!.due_at!)
    ).toBeLessThan(Date.parse(x.due_at!));
    await raw(request, { latitude: 1 });
    snapshot = await feed(request);
    expect(snapshot.transport_review).toBeTruthy();
    await raw(request, { latitude: 0, route_latitude: 1 });
    await feed(request);
    await raw(request, { route_latitude: 0, stale: true });
    snapshot = await feed(request);
    expect(snapshot.transport_review?.coverage).not.toBe('available');
    expect(
      snapshot.transport_review?.assessments.every(
        (a) => a.status !== 'no_overlap_found'
      )
    ).toBe(true);
    proof.staleUnknown = true;
    expect(
      JSON.stringify(
        (await (await request.get(`${base}/records/${savedIds[0]}`)).json())
          .record
      )
    ).toBe(original);
    proof.realLiveEta = true;
    control('restart');
    await ready(first);
    expect(
      JSON.stringify(
        (await (await request.get(`${base}/records/${savedIds[0]}`)).json())
          .record
      )
    ).toBe(original);
    proof.restart = true;
    writeFileSync(
      join(evidence, 'transport-proof.json'),
      JSON.stringify(proof, null, 2)
    );
  } finally {
    for (const context of contexts) await context.close();
  }
});
