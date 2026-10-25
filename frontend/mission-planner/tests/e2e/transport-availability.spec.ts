import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import {
  expect,
  test,
  type APIRequestContext,
  type APIResponse,
} from '@playwright/test';
import type {
  AvailabilityView,
  RFTransport,
} from '../../src/services/transportAvailability';

import type { EventSnapshot } from '../../src/types/operatorEvents';
import type { TransportCatalog } from '../../src/services/transportCatalog';
import type { CallContinuityProjection } from '../../src/types/pop';

const evidence = process.env.TRANSPORT_ACCEPTANCE_EVIDENCE!;
let departure = '';
const at = (minutes: number) =>
  new Date(Date.parse(departure) + minutes * 60000).toISOString();
const transports = [
  { key: 'X', label: 'X-band', prefix: 'x_', state: 'x_state' },
  { key: 'Ka', label: 'Ka', prefix: 'ka_', state: 'ka_state' },
  { key: 'Ku', label: 'Starshield', prefix: 'starshield_', state: 'ku_state' },
] as const;
interface Poi {
  id: string;
  kind?: string;
  transport_active?: boolean;
  expected_arrival_time?: string;
  mission_id?: string;
  route_id?: string;
}
interface Segment {
  start_time: string;
  end_time: string;
  x_state: string;
  ka_state: string;
  ku_state: string;
}
async function json<T>(response: APIResponse): Promise<T> {
  expect(
    response.ok(),
    `${response.status()} ${await response.text()}`
  ).toBeTruthy();
  return response.json();
}
async function seed(request: APIRequestContext) {
  const input = await json<{ departure: string }>(
    await request.post('/api/_synthetic/transport-inputs', { data: {} })
  );
  departure = input.departure;
  const missionId = `availability-${randomUUID()}`;
  for (const [name, longitude] of [
    ['Availability-X-1', 20],
    ['Availability-X-2', 90],
  ] as const)
    await json(
      await request.post('/api/pois', {
        data: { name, latitude: 0, longitude, category: 'satellite' },
      })
    );
  await json(
    await request.post('/api/v2/missions', {
      data: {
        id: missionId,
        name: 'Synthetic availability acceptance',
        legs: [],
      },
    })
  );
  const legs = [];
  for (const n of [1, 2]) {
    const id = `availability-leg-${n}`;
    await json(
      await request.post(`/api/v2/missions/${missionId}/legs`, {
        data: {
          id,
          name: `Acceptance leg ${n}`,
          route_id: `pending-${n}`,
          adjusted_departure_time: departure,
          transports: {
            initial_x_satellite_id: 'Availability-X-1',
            initial_ka_satellite_ids: ['AOR'],
            starshield_enabled: true,
            x_transitions: [
              {
                id: `swap-${n}`,
                latitude: 0,
                longitude: 6,
                target_satellite_id: 'Availability-X-2',
              },
            ],
            ka_outages: [
              { id: `ka-${n}`, start_time: at(40), duration_seconds: 300 },
            ],
            ku_overrides: [
              { id: `ku-${n}`, start_time: at(45), duration_seconds: 300 },
            ],
          },
        },
      })
    );
    const points = [-10, 0, 10]
      .map(
        (lon, i) =>
          `<Placemark><name>${['Departure', 'Middle', 'Arrival'][i]}</name><description>Time Over Waypoint: ${at(
            i * 30
          )
            .replace('T', ' ')
            .replace(
              '.000Z',
              'Z'
            )}</description><Point><coordinates>${lon},0,10000</coordinates></Point></Placemark>`
      )
      .join('');
    const kml = `<kml xmlns="http://www.opengis.net/kml/2.2"><Document>${points}<Placemark><LineString><coordinates>-10,0,10000 0,0,10000 10,0,10000</coordinates></LineString></Placemark></Document></kml>`;
    const uploaded = await json<{ leg: { route_id: string } }>(
      await request.put(`/api/v2/missions/${missionId}/legs/${id}/route`, {
        multipart: {
          file: {
            name: `availability-${n}.kml`,
            mimeType: 'application/vnd.google-earth.kml+xml',
            buffer: Buffer.from(kml),
          },
        },
      })
    );
    legs.push({ id, routeId: uploaded.leg.route_id });
  }
  return { missionId, legs };
}

test('mission defaults, live failures, retained cues, restoration and authoritative simulation isolation', async ({
  page,
  request,
  context,
}) => {
  const browserErrors: string[] = [];
  page.on('pageerror', (error) => browserErrors.push(error.message));
  const { missionId, legs } = await seed(request);
  const path = `/api/v2/missions/${missionId}`;
  const read = () =>
    request.get(`${path}/availability`).then((r) => json<AvailabilityView>(r));
  const allPois = async () =>
    (
      await json<{ pois: Poi[] }>(
        await request.get('/api/pois?active_only=false')
      )
    ).pois.filter((p) => p.mission_id === missionId);
  const timeline = (leg = legs[0].id) =>
    request.get(`${path}/legs/${leg}/timeline`).then((r) =>
      json<{
        segments: Segment[];
        map_pois: Poi[];
        call_continuity: CallContinuityProjection | null;
      }>(r)
    );
  const change = async (
    key: RFTransport,
    action: 'restore' | 'unavailable'
  ) => {
    const current = await read();
    return json<AvailabilityView>(
      await request.post(`${path}/availability/actions`, {
        data: {
          expected_revision: current.revision,
          command_id: randomUUID(),
          transport: key,
          action,
          expected_simulation_run_id: current.simulation_run_id,
        },
      })
    );
  };
  await page.goto(`/missions/${missionId}`);
  const defaults = page.getByRole('region', {
    name: 'Mission transport availability',
    exact: true,
  });
  await defaults
    .getByLabel('X-band', { exact: true })
    .selectOption('unavailable');
  await defaults
    .getByRole('button', { name: 'Save availability', exact: true })
    .click();
  await expect(defaults.getByRole('status')).toContainText(
    'Profiles regenerated'
  );
  expect((await read()).legs.every((leg) => leg.planned.X === false)).toBe(
    true
  );
  await page.screenshot({
    path: `${evidence}/mission-defaults-1920x1080.png`,
    fullPage: true,
  });

  await page.goto(`/missions/${missionId}/legs/${legs[1].id}`);
  const override = page.getByRole('region', {
    name: 'Leg transport availability',
    exact: true,
  });
  await override
    .getByLabel('X-band', { exact: true })
    .selectOption('available');
  await override
    .getByRole('button', { name: 'Save availability', exact: true })
    .click();
  await expect(override.getByRole('status')).toContainText(
    'Profiles regenerated'
  );
  expect((await read()).legs.map((leg) => leg.planned.X)).toEqual([
    false,
    true,
  ]);
  await page.screenshot({
    path: `${evidence}/leg-override-1920x1080.png`,
    fullPage: true,
  });
  await override.getByLabel('X-band', { exact: true }).selectOption('inherit');
  await override
    .getByRole('button', { name: 'Save availability', exact: true })
    .click();
  await expect(override.getByRole('status')).toContainText(
    'Profiles regenerated'
  );
  expect((await read()).leg_overrides[legs[1].id]).toEqual({});

  // Actual stale revision rejection: a second API client commits while this UI retains edits.
  await page.goto(`/missions/${missionId}`);
  await defaults
    .getByLabel('X-band', { exact: true })
    .selectOption('available');
  const stale = await read();
  await json(
    await request.put(`${path}/availability`, {
      data: {
        expected_revision: stale.revision,
        command_id: randomUUID(),
        defaults: { Ka: true },
      },
    })
  );
  await defaults
    .getByRole('button', { name: 'Save availability', exact: true })
    .click();
  await expect(defaults.getByRole('alert')).toContainText('not confirmed');
  await expect(defaults.getByLabel('X-band', { exact: true })).toHaveValue(
    'available'
  );
  await defaults
    .getByRole('button', { name: 'Save availability', exact: true })
    .click();
  await expect(defaults.getByRole('status')).toContainText(
    'Profiles regenerated'
  );

  // Source mode uses the product configuration API; no availability source override.
  const config = await json<
    Record<string, unknown> & { pop: Record<string, unknown> }
  >(await request.get('/api/config'));
  await json(
    await request.post('/api/config', {
      data: {
        ...config,
        pop: {
          ...config.pop,
          catalog_path:
            '/app/data/operator/transport-availability/availability-pops.json',
        },
        mode: 'live',
      },
    })
  );
  await json(await request.post(`${path}/legs/${legs[0].id}/activate`));
  await json(
    await request.post('/api/_synthetic/transport-inputs', {
      data: { elapsed_seconds: 1800 },
    })
  );
  expect((await read()).operator_actions_allowed).toBe(true);
  const before = await allPois();
  for (const transport of transports)
    expect(
      before.filter(
        (p) =>
          p.route_id === legs[0].routeId && p.kind?.startsWith(transport.prefix)
      ).length,
      `${transport.key} generated raw-input cues`
    ).toBeGreaterThan(0);
  await page.goto(`/operator?mission_id=${missionId}`);
  const controls = page.getByRole('region', {
    name: 'Mission transport availability',
    exact: true,
  });
  await page.getByRole('button', { name: 'Transport', exact: true }).click();
  const catalog = await json<TransportCatalog>(
    await request.get('/api/v2/operator/transport-catalog')
  );
  expect(
    catalog.services.filter((service) => service.enabled && !service.archived)
      .length
  ).toBeGreaterThan(0);
  const serviceName = catalog.services.find(
    (service) => service.enabled && !service.archived
  )!.name;
  const assignment = page.getByRole('article', {
    name: serviceName,
    exact: true,
  });
  await assignment.getByRole('combobox').selectOption('X');
  await assignment.getByRole('button', { name: 'Apply', exact: true }).click();
  await expect(
    assignment.locator('strong').filter({ hasText: 'X-band' })
  ).toBeVisible();
  const recordsBefore = await json<{
    items: Array<{ record: { record_id: string } }>;
  }>(await request.get(`/api/v2/operator/records?mission_id=${missionId}`));
  const overviewDuring = await context.newPage();
  await overviewDuring.goto('/overview');
  await expect(
    overviewDuring.getByRole('list', { name: 'Map POIs', exact: true })
  ).toBeAttached();
  await expect(
    overviewDuring.locator('[data-poi-label]').first()
  ).toBeVisible();
  await overviewDuring.screenshot({
    path: `${evidence}/baseline-map-1920x1080.png`,
  });
  const beforeEvents = await json<EventSnapshot>(
    await request.get(
      `/api/v2/operator/events?mission_id=${missionId}&include_history=true`
    )
  );
  expect(
    beforeEvents.events.some(
      (event) => event.provenance === 'modeled' && event.active
    )
  ).toBe(true);
  const snapshots: unknown[] = [];
  for (const transport of transports) {
    const field = controls.getByRole('group', {
      name: `${transport.label} availability`,
      exact: true,
    });
    await field
      .getByRole('button', {
        name: 'Unavailable for rest of mission',
        exact: true,
      })
      .click();
    await expect(
      field.getByRole('button', { name: 'Restore', exact: true })
    ).toBeVisible();
    const accepted = await read();
    expect(accepted.effective?.[transport.key]).toBe(false);
    const failedAt = accepted.history
      .filter((entry) => entry.transport === transport.key && entry.unavailable)
      .at(-1)!.effective_at;
    const failedPois = await allPois();
    const retained = before.filter(
      (p) =>
        p.route_id === legs[0].routeId && p.kind?.startsWith(transport.prefix)
    );
    for (const poi of retained) {
      const current = failedPois.find((p) => p.id === poi.id);
      expect(current, `retained ${transport.key} POI ${poi.id}`).toBeTruthy();
      expect(current?.transport_active).toBe(false);
    }
    const activePois = await json<{ pois: Poi[] }>(
      await request.get('/api/pois')
    );
    expect(
      activePois.pois.filter((p) =>
        retained.some((original) => original.id === p.id)
      )
    ).toEqual([]);
    const failedTimeline = await timeline();
    const future = failedTimeline.segments.filter(
      (s) => Date.parse(s.start_time) >= Date.parse(failedAt)
    );
    expect(future.length).toBeGreaterThan(0);
    expect(future.every((s) => s[transport.state] === 'offline')).toBe(true);
    if (failedTimeline.call_continuity)
      expect(
        failedTimeline.call_continuity.intervals
          .filter(
            (interval) => Date.parse(interval.start_utc) >= Date.parse(failedAt)
          )
          .every(
            (interval) => !interval.usable_alternatives.includes(transport.key)
          )
      ).toBe(true);
    const failedEvents = await json<EventSnapshot>(
      await request.get(
        `/api/v2/operator/events?mission_id=${missionId}&include_history=true`
      )
    );
    expect(
      failedEvents.events.filter(
        (event) =>
          event.transport === transport.key &&
          event.active &&
          event.kind !== 'call_start' &&
          event.kind !== 'call_prep'
      )
    ).toEqual([]);
    expect(
      failedEvents.events.filter(
        (event) =>
          event.transport === transport.key && event.notification.eligible
      )
    ).toEqual([]);
    await overviewDuring.goto('/overview');
    await expect(
      overviewDuring.locator('[data-poi-label]').first()
    ).toBeVisible();
    for (const poi of retained)
      await expect(
        overviewDuring.locator(`[data-poi-label="${poi.id}"]`)
      ).toHaveCount(0);
    snapshots.push({
      transport: transport.key,
      failedPois,
      failedTimeline,
      failedEvents,
      failedAt,
      availability: await read(),
    });
    await page.screenshot({
      path: `${evidence}/failed-${transport.key}-1920x1080.png`,
      fullPage: true,
    });
  }
  expect((await read()).effective).toEqual({ X: false, Ka: false, Ku: false });
  await overviewDuring.screenshot({
    path: `${evidence}/inactive-map-1920x1080.png`,
  });
  await overviewDuring.close();
  await expect(assignment).toContainText('unavailable for this mission');
  await expect(
    assignment.getByRole('combobox').locator('option[value="X"]')
  ).toBeDisabled();
  for (const key of ['Ka', 'Starshield'])
    await expect(
      assignment.getByRole('combobox').locator(`option[value="${key}"]`)
    ).toHaveCount(0);
  const recordsAfter = await json<{
    items: Array<{ record: { record_id: string } }>;
  }>(await request.get(`/api/v2/operator/records?mission_id=${missionId}`));
  expect(recordsAfter.items.map((record) => record.record.record_id)).toEqual(
    recordsBefore.items.map((record) => record.record.record_id)
  );
  const allDownView = await read();
  const allDownAt = allDownView.history
    .filter((entry) => entry.unavailable)
    .at(-1)!.effective_at;
  const allDown = await timeline();
  expect(allDown.call_continuity).not.toBeNull();
  expect(
    allDown
      .call_continuity!.intervals.filter(
        (interval) => Date.parse(interval.start_utc) >= Date.parse(allDownAt)
      )
      .every(
        (interval) =>
          interval.usable_alternatives.length === 0 &&
          interval.classification !== 'x_fallback'
      )
  ).toBe(true);
  expect(
    allDown.segments
      .filter((s) => Date.parse(s.start_time) >= Date.parse(allDownAt))
      .every(
        (s) =>
          s.x_state === 'offline' &&
          s.ka_state === 'offline' &&
          s.ku_state === 'offline'
      )
  ).toBe(true);
  expect(
    (
      await json<{ transport_active: boolean }>(
        await request.get('/api/active-x-link')
      )
    ).transport_active
  ).toBe(false);
  const status = await json<{ transport_availability: object }>(
    await request.get('/api/status')
  );
  expect(status.transport_availability).toEqual({
    X: false,
    Ka: false,
    Ku: false,
  });
  await page.screenshot({
    path: `${evidence}/all-unavailable-1920x1080.png`,
    fullPage: true,
  });
  const exportProof = execFileSync(
    'timeout',
    [
      '--kill-after=10s',
      '2m',
      'docker',
      'compose',
      '-p',
      process.env.TRANSPORT_ACCEPTANCE_PROJECT!,
      '-f',
      `${process.env.OPERATOR_SOURCE_ROOT}/tools/acceptance/transport-availability/compose.yml`,
      'exec',
      '-T',
      '--user',
      'appuser',
      'starlink-location',
      'python',
      '/transport-acceptance/export_probe.py',
      missionId,
      allDownAt,
    ],
    { env: process.env, encoding: 'utf8', timeout: 135000 }
  );
  const exportResult = JSON.parse(exportProof.trim().split('\n').at(-1)!);
  expect(exportResult.legs).toHaveLength(2);
  await writeFile(
    `${evidence}/all-down-export-snapshot.json`,
    JSON.stringify(exportResult, null, 2)
  );
  // Ordinary later-leg activation must retain mission-wide live history.
  await json(await request.post(`${path}/legs/${legs[1].id}/activate`));
  expect((await read()).effective).toEqual({ X: false, Ka: false, Ku: false });
  await json(
    await request.post('/api/_synthetic/transport-inputs', {
      data: { elapsed_seconds: 1860 },
    })
  );
  await page.reload();
  await controls
    .getByRole('group', { name: 'X-band availability', exact: true })
    .getByRole('button', { name: 'Restore', exact: true })
    .click();
  await expect(
    controls
      .getByRole('group', { name: 'X-band availability', exact: true })
      .getByRole('button', {
        name: 'Unavailable for rest of mission',
        exact: true,
      })
  ).toBeVisible();
  for (const key of ['Ka', 'Ku'] as const) await change(key, 'restore');
  expect((await read()).effective).toEqual({ X: true, Ka: true, Ku: true });
  const restoredView = await read();
  const restoredAt = restoredView.history
    .filter((entry) => !entry.unavailable)
    .at(-1)!.effective_at;
  const restored = await allPois();
  for (const transport of transports) {
    const original = before.filter(
      (p) =>
        p.route_id === legs[1].routeId && p.kind?.startsWith(transport.prefix)
    );
    const future = original.filter(
      (p) =>
        p.expected_arrival_time &&
        Date.parse(p.expected_arrival_time) > Date.parse(restoredAt)
    );
    expect(future.length).toBeGreaterThan(0);
    for (const poi of future)
      expect(restored.find((p) => p.id === poi.id)?.transport_active).toBe(
        true
      );
  }
  expect(new Set(restored.map((p) => p.id)).size).toBe(restored.length);
  const events = await json<EventSnapshot>(
    await request.get(
      `/api/v2/operator/events?mission_id=${missionId}&include_history=true`
    )
  );
  expect(
    events.events.filter(
      (event) =>
        event.provenance === 'modeled' &&
        event.state === 'overdue' &&
        event.notification.eligible
    )
  ).toEqual([]);
  for (const event of events.events.filter(
    (event) =>
      event.provenance === 'modeled' &&
      event.notification.eligible &&
      event.due_at
  ))
    expect(Date.parse(event.end_at ?? event.due_at!)).toBeGreaterThan(
      Date.parse(restoredAt)
    );
  snapshots.push({
    restored,
    events,
    timeline: await timeline(legs[1].id),
    availability: await read(),
  });
  await page.reload();
  await expect(
    controls.getByRole('button', {
      name: 'Unavailable for rest of mission',
      exact: true,
    })
  ).toHaveCount(3);
  await page.screenshot({
    path: `${evidence}/restored-1920x1080.png`,
    fullPage: true,
  });

  // Normal authoritative replay activation; its failures cannot leak into live planning.
  await json(
    await request.post('/api/config', {
      data: { ...config, mode: 'simulation' },
    })
  );
  const pacing = { mode: 'multiplier', multiplier: 1 };
  const preview = await json<{ plan_token: string }>(
    await request.post(`${path}/legs/${legs[0].id}/simulation/preview`, {
      data: pacing,
    })
  );
  await json(
    await request.post(`${path}/legs/${legs[0].id}/activate`, {
      data: { simulation: { pacing, plan_token: preview.plan_token } },
    })
  );
  await json(
    await request.post('/api/_synthetic/transport-inputs', {
      data: { elapsed_seconds: 3660 },
    })
  );
  const simulation = await read();
  expect(simulation.simulation_run_id).toBeTruthy();
  const failedSimulation = await change('Ka', 'unavailable');
  expect(failedSimulation.effective?.Ka).toBe(false);
  expect(failedSimulation.legs[0].planning_effective?.Ka).toBe(true);
  const rejectedRun = await request.post(`${path}/availability/actions`, {
    data: {
      expected_revision: failedSimulation.revision,
      command_id: randomUUID(),
      transport: 'X',
      action: 'unavailable',
      expected_simulation_run_id: 'replaced-run',
    },
  });
  expect(rejectedRun.status()).toBe(409);
  await json(
    await request.post('/api/config', {
      data: {
        ...config,
        pop: {
          ...config.pop,
          catalog_path:
            '/app/data/operator/transport-availability/availability-pops.json',
        },
        mode: 'live',
      },
    })
  );
  expect((await read()).effective?.Ka).toBe(true);
  const overview = await context.newPage();
  await overview.goto('/overview');
  await expect(
    overview.getByRole('region', { name: 'Mission transport availability' })
  ).toHaveCount(0);
  await overview.screenshot({ path: `${evidence}/overview-1920x1080.png` });
  await overview.close();
  expect(browserErrors).toEqual([]);
  await writeFile(
    `${evidence}/transport-availability-proof.json`,
    JSON.stringify(
      {
        synthetic: true,
        rawInputsOnly: true,
        missionId,
        legs,
        browserErrors,
        missionDefaults: true,
        legInheritance: true,
        staleSave: true,
        allUnavailable: true,
        retainedPoiIds: true,
        laterLiveLeg: true,
        restoration: true,
        simulationRunGuard: true,
        simulationIsolation: true,
        eventSuppression: true,
        noOverdueRestoration: true,
        renderedMapSuppression: true,
        retainedServiceReport: true,
        captures: ['1920x1080'],
        snapshots,
      },
      null,
      2
    )
  );
});
