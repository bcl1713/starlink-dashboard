import {
  test,
  expect,
  type APIRequestContext,
  type APIResponse,
  type BrowserContext,
} from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import type { EventSnapshot } from '../../src/types/operatorEvents';

const evidence = process.env.OVERVIEW_ADVISORIES_EVIDENCE!;
const catalog =
  '/app/data/operator/transport-availability/availability-pops.json';
async function json<T = Record<string, unknown>>(
  response: APIResponse
): Promise<T> {
  expect(response.ok(), `${response.status()} ${await response.text()}`).toBe(
    true
  );
  return response.json();
}
async function raw(request: APIRequestContext, elapsed = 1764) {
  return json<{ departure: string }>(
    await request.post('/api/_synthetic/transport-inputs', {
      data: { elapsed_seconds: elapsed },
    })
  );
}
async function seed(request: APIRequestContext) {
  const { departure } = await raw(request, 0);
  const at = (minute: number) =>
    new Date(Date.parse(departure) + minute * 60_000).toISOString();
  const missionId = `overview-${randomUUID()}`;
  await json(
    await request.post('/api/pois', {
      data: {
        name: 'Overview-X-1',
        latitude: 0,
        longitude: 90,
        category: 'satellite',
      },
    })
  );
  await json(
    await request.post('/api/v2/missions', {
      data: { id: missionId, name: 'Synthetic Overview Acceptance', legs: [] },
    })
  );
  const legs = [];
  for (const n of [1, 2]) {
    const leg = `overview-leg-${n}`;
    await json(
      await request.post(`/api/v2/missions/${missionId}/legs`, {
        data: {
          id: leg,
          name: `Synthetic Leg ${n}`,
          route_id: `pending-${n}`,
          adjusted_departure_time: departure,
          transports: {
            initial_x_satellite_id: 'Overview-X-1',
            initial_ka_satellite_ids: ['AOR'],
            starshield_enabled: true,
            ka_outages: [
              { id: `ka-${n}`, start_time: at(29), duration_seconds: 180 },
            ],
            ku_overrides: [
              { id: `ku-${n}`, start_time: at(29), duration_seconds: 180 },
            ],
            aar_windows: [
              {
                id: `ar-${n}`,
                start_waypoint_name: 'AR IN',
                end_waypoint_name: 'AR OUT',
              },
            ],
          },
        },
      })
    );
    const points: [string, number, number][] = [
      ['Departure', -10, 0],
      ['Middle', 0, 30],
      ['AR IN', 1, 33],
      ['AR OUT', 2, 36],
      ['Arrival', 10, 60],
    ];
    const placemarks = points
      .map(
        ([name, lon, minute]) =>
          `<Placemark><name>${name}</name><description>Time Over Waypoint: ${at(minute).replace('T', ' ').replace('.000Z', 'Z')}</description><Point><coordinates>${lon},0,10000</coordinates></Point></Placemark>`
      )
      .join('');
    const kml = `<kml xmlns="http://www.opengis.net/kml/2.2"><Document>${placemarks}<Placemark><LineString><coordinates>${points.map(([, lon]) => `${lon},0,10000`).join(' ')}</coordinates></LineString></Placemark></Document></kml>`;
    await json(
      await request.put(`/api/v2/missions/${missionId}/legs/${leg}/route`, {
        multipart: {
          file: {
            name: `overview-${n}.kml`,
            mimeType: 'application/vnd.google-earth.kml+xml',
            buffer: Buffer.from(kml),
          },
        },
      })
    );
    legs.push(leg);
  }
  const config = await json<
    Record<string, unknown> & { pop: Record<string, unknown> }
  >(await request.get('/api/config'));
  await json(
    await request.post('/api/config', {
      data: {
        ...config,
        mode: 'live',
        pop: { ...config.pop, catalog_path: catalog },
      },
    })
  );
  const activate = async (leg: string, elapsed = 1764) => {
    await json(
      await request.post(`/api/v2/missions/${missionId}/legs/${leg}/activate`)
    );
    await json(
      await request.post('/api/flight-status/depart', {
        data: {
          timestamp: departure,
          reason: 'Synthetic raw flight-state input',
        },
      })
    );
    await raw(request, elapsed);
  };
  await activate(legs[0]);
  return { missionId, legs, activate };
}
async function feed(request: APIRequestContext, missionId: string) {
  return json<EventSnapshot>(
    await request.get(
      `/api/v2/operator/events?mission_id=${missionId}&include_history=true`
    )
  );
}

test('customizable presets and durable shared advisories across real clients', async ({
  browser,
  request,
}) => {
  const proof: Record<string, unknown> = {
    synthetic: true,
    rawInputsOnly: true,
    browserErrors: [],
    externalRequests: [],
  };
  const contexts: BrowserContext[] = [];
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  let heartbeatWork = Promise.resolve();
  let elapsed = 1764;
  const stopHeartbeat = async () => {
    if (heartbeat) clearInterval(heartbeat);
    heartbeat = undefined;
    await heartbeatWork;
  };
  const startHeartbeat = () => {
    heartbeat = setInterval(() => {
      heartbeatWork = heartbeatWork
        .then(() => raw(request, elapsed))
        .then(() => {});
    }, 2_000);
  };
  try {
    const { missionId, legs, activate } = await seed(request);
    startHeartbeat();
    const first = await feed(request, missionId);
    await writeFile(
      `${evidence}/initial-snapshot.json`,
      JSON.stringify(first, null, 2)
    );
    const pop = first.events.find(
      (event) => event.advisory_type === 'transition_window' && event.active
    )!;
    expect(pop?.notification.eligible).toBe(false);
    expect(pop?.notification.acknowledgment_available).toBe(true);
    expect(
      first.events.some(
        (event) =>
          event.transport === 'Ka' && event.significance === 'unavailable'
      )
    ).toBe(true);
    expect(
      first.events.some(
        (event) =>
          event.transport === 'X' && event.significance === 'unavailable'
      )
    ).toBe(true);
    proof.allTransportSources = true;

    const pages = [];
    for (const timezoneId of ['America/Los_Angeles', 'Asia/Tokyo', 'UTC']) {
      const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        timezoneId,
        locale: 'en-US',
      });
      contexts.push(context);
      await context.addInitScript(() => {
        const tracked = window as unknown as { overviewAudio: number };
        tracked.overviewAudio = 0;
        localStorage.setItem(
          'operator-alert-preferences',
          JSON.stringify({ enabled: false, sound: false, vibration: false })
        );
        if (globalThis.AudioContext) {
          const original = AudioContext.prototype.createOscillator;
          AudioContext.prototype.createOscillator = function () {
            tracked.overviewAudio++;
            return original.call(this);
          };
        }
      });
      const page = await context.newPage();
      page.on('pageerror', (error) =>
        (proof.browserErrors as string[]).push(error.message)
      );
      page.on('request', (req) => {
        if (
          !req.url().startsWith(process.env.OVERVIEW_ADVISORIES_ORIGIN!) &&
          !/^(data|blob):/.test(req.url())
        )
          (proof.externalRequests as string[]).push(req.url());
      });
      pages.push(page);
    }
    const [overviewA, overviewB, operator] = pages;
    await operator.goto('/operator');
    await operator
      .getByRole('button', { name: 'Display tools', exact: true })
      .click();
    const tools = operator.getByRole('dialog', {
      name: 'Display tools',
      exact: true,
    });
    const flight = tools.getByRole('switch', { name: 'Flight Events Only' });
    await expect(flight).toBeEnabled();
    await tools
      .getByRole('button', { name: 'Save current as Normal', exact: true })
      .click();
    await expect(
      tools.getByText('Normal preset saved', { exact: true })
    ).toBeVisible();
    await flight.check();
    await expect(flight).toBeChecked();
    await tools
      .getByRole('button', { name: 'Save current as Customer', exact: true })
      .click();
    await expect(
      tools.getByText('Customer preset saved', { exact: true })
    ).toBeVisible();
    await Promise.all([
      overviewA.goto('/overview'),
      overviewB.goto('/overview'),
    ]);
    for (const overview of [overviewA, overviewB]) {
      await expect(
        overview.getByRole('heading', { name: /Next Flight Event/ })
      ).toContainText('AR Begins');
      await expect(
        overview
          .getByLabel('Transport Advisories')
          .getByText('Starshield Transition Window', { exact: true })
      ).toBeVisible();
      await expect(overview.getByLabel('Departure and Arrival')).toContainText(
        'Zulu'
      );
    }
    const advisoryBounds = await overviewA
      .getByLabel('Transport Advisories')
      .evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return {
          top: rect.top,
          bottom: rect.bottom,
          viewport: innerHeight,
          overflow: getComputedStyle(element).overflowY,
          tabIndex: (element as HTMLElement).tabIndex,
        };
      });
    expect(advisoryBounds.top).toBeGreaterThanOrEqual(0);
    expect(advisoryBounds.bottom).toBeLessThanOrEqual(advisoryBounds.viewport);
    expect(advisoryBounds.overflow).toBe('auto');
    expect(advisoryBounds.tabIndex).toBe(0);
    proof.advisoryBounds = advisoryBounds;
    // Rendering-only stress: extra DOM copies exercise rail bounds/keyboard access;
    // all advisory prediction/acknowledgment assertions below use real backend events.
    const rail = overviewA.getByLabel('Transport Advisories');
    await rail.evaluate((element) => {
      const sample = element.querySelector('.overview-transport-advisory')!;
      for (let i = 0; i < 12; i++) {
        const copy = sample.cloneNode(true) as HTMLElement;
        copy.dataset.visualStress = 'true';
        element.append(copy);
      }
    });
    await rail.focus();
    await rail.press('End');
    await expect
      .poll(() => rail.evaluate((element) => element.scrollTop))
      .toBeGreaterThan(0);
    const stress = await rail.evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      const last = element.lastElementChild!.getBoundingClientRect();
      return {
        top: bounds.top,
        bottom: bounds.bottom,
        lastBottom: last.bottom,
        viewport: innerHeight,
        scrollable: element.scrollHeight > element.clientHeight,
      };
    });
    expect(stress.bottom).toBeLessThanOrEqual(stress.viewport);
    expect(stress.lastBottom).toBeLessThanOrEqual(stress.bottom + 1);
    proof.renderOnlyOverflowStress = stress;
    await overviewA.screenshot({
      path: `${evidence}/advisories-overflow-keyboard-1920x1080.png`,
    });
    await rail.evaluate((element) => {
      element
        .querySelectorAll('[data-visual-stress]')
        .forEach((node) => node.remove());
      element.scrollTop = 0;
    });

    await overviewA.screenshot({ path: `${evidence}/customer-1920x1080.png` });
    await tools
      .getByRole('button', { name: 'Apply Normal', exact: true })
      .click();
    await expect(
      tools.getByText('Normal preset applied', { exact: true })
    ).toBeVisible();
    for (const overview of [overviewA, overviewB]) {
      await expect(
        overview.getByRole('heading', { name: /Next POI/ })
      ).toBeVisible();
      await expect(overview.getByLabel('Transport Advisories')).toContainText(
        'Starshield Transition Window'
      );
    }
    await tools
      .getByRole('button', { name: 'Apply Customer', exact: true })
      .click();
    await expect(
      tools.getByText('Customer preset applied', { exact: true })
    ).toBeVisible();
    await tools.getByRole('button', { name: 'Close', exact: true }).click();
    proof.customizableSharedPresets = true;

    await operator
      .getByRole('button', { name: 'Open operational alerts', exact: true })
      .click();
    const alerts = operator.getByRole('dialog', {
      name: 'Operational Alerts',
      exact: true,
    });
    await stopHeartbeat();
    await raw(request, elapsed);
    const refreshed = operator.waitForResponse(
      (response) =>
        response.url().includes('/api/v2/operator/events?') &&
        response.request().method() === 'GET'
    );
    await alerts
      .getByRole('button', { name: 'Refresh Events', exact: true })
      .click();
    await refreshed;
    const row = alerts
      .getByRole('listitem')
      .filter({
        has: operator.getByText('Starshield Transition Window', {
          exact: true,
        }),
      })
      .first();
    await expect(
      row.getByRole('button', { name: 'Acknowledge', exact: true })
    ).toBeEnabled();
    let lostRequest: { key: string | undefined; body: unknown } | undefined;
    await operator.route(
      '**/api/v2/operator/events/acknowledge',
      async (route) => {
        lostRequest = {
          key: route.request().headers()['idempotency-key'],
          body: route.request().postDataJSON(),
        };
        const response = await route.fetch();
        expect(response.ok(), await response.text()).toBe(true);
        await route.abort('failed');
      }
    );
    await row.getByRole('button', { name: 'Acknowledge', exact: true }).click();
    await expect(
      alerts.getByText(/Acknowledgment not confirmed/)
    ).toBeVisible();
    startHeartbeat();
    for (const overview of [overviewA, overviewB])
      await expect(
        overview
          .getByLabel('Transport Advisories')
          .getByText('Starshield Transition Window', { exact: true })
      ).toHaveCount(0, { timeout: 65_000 });
    proof.twoClientPollingSuppression = true;
    await operator.unroute('**/api/v2/operator/events/acknowledge');
    const receipt = operator.waitForResponse((response) =>
      response.url().endsWith('/api/v2/operator/events/acknowledge')
    );
    await alerts
      .getByRole('button', { name: 'Retry acknowledgment', exact: true })
      .click();
    const replay = await receipt;
    expect(replay.request().headers()['idempotency-key']).toBe(
      lostRequest!.key
    );
    expect(replay.request().postDataJSON()).toEqual(lostRequest!.body);
    expect((await replay.json()).replayed).toBe(true);
    await expect(
      row.getByRole('button', { name: 'Acknowledged', exact: true })
    ).toBeVisible();
    proof.lostResponseIdempotentRetry = true;
    const reloadedSnapshots = [overviewA, overviewB].map((overview) =>
      overview.waitForResponse(
        (response) =>
          response.url().includes('/api/v2/operator/events?') &&
          response.status() === 200
      )
    );
    await Promise.all([overviewA.reload(), overviewB.reload()]);
    for (const response of await Promise.all(reloadedSnapshots)) {
      const snapshot: EventSnapshot = await response.json();
      expect(
        snapshot.events.find(
          (event) =>
            event.notification.generation === pop.notification.generation
        )?.notification.acknowledged
      ).toBe(true);
    }
    for (const overview of [overviewA, overviewB]) {
      await expect(
        overview.getByRole('heading', { name: /Next Flight Event/ })
      ).toBeVisible();
      await expect(
        overview
          .getByLabel('Transport Advisories')
          .getByText('Starshield Transition Window', { exact: true })
      ).toHaveCount(0);
      expect(
        await overview.evaluate(
          () => (window as unknown as { overviewAudio: number }).overviewAudio
        )
      ).toBe(0);
    }
    proof.reloadPersistenceAndNoOverviewAudio = true;
    const beforeDrift = (await feed(request, missionId)).events.find(
      (event) => event.notification.generation === pop.notification.generation
    )!;
    elapsed = 1765;
    await raw(request, elapsed);
    const drift = await feed(request, missionId);
    const retained = drift.events.find(
      (event) => event.notification.generation === pop.notification.generation
    );
    expect(retained?.notification.acknowledged).toBe(true);
    expect(retained?.due_at).not.toBe(beforeDrift.due_at);
    proof.etaDriftRetainsAcknowledgment = true;
    await alerts.getByRole('checkbox', { name: 'Recent History' }).check();
    await expect(
      row.getByRole('button', { name: 'Acknowledged', exact: true })
    ).toBeVisible();
    proof.operatorHistoryRetained = true;
    await operator.screenshot({
      path: `${evidence}/operator-acknowledged.png`,
    });

    for (const viewport of [
      { width: 390, height: 844 },
      { width: 844, height: 390 },
    ]) {
      await overviewB.setViewportSize(viewport);
      expect(
        await overviewB.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth
        )
      ).toBe(true);
      await overviewB.screenshot({
        path: `${evidence}/overview-${viewport.width}x${viewport.height}.png`,
      });
    }
    await stopHeartbeat();
    await activate(legs[1], elapsed);
    elapsed = 1765;
    await raw(request, elapsed);
    startHeartbeat();
    const nextLeg = await feed(request, missionId);
    const rearmed = nextLeg.events.find(
      (event) =>
        event.leg_id === legs[1] &&
        event.advisory_type === 'transition_window' &&
        event.active
    )!;
    expect(rearmed.notification.generation).not.toBe(
      pop.notification.generation
    );
    expect(rearmed.notification.acknowledged).toBe(false);
    await expect(overviewA.getByLabel('Transport Advisories')).toContainText(
      'Starshield Transition Window',
      { timeout: 65_000 }
    );
    proof.newActiveLegRearmsAndIsolates = true;
    const stale = await request.post('/api/v2/operator/events/acknowledge', {
      headers: {
        'Idempotency-Key': randomUUID(),
        'X-Operator-Store-Epoch': first.api_epoch,
      },
      data: {
        schema_version: 1,
        occurrence_id: rearmed.notification.generation,
        severity_generation: rearmed.notification.severity_generation,
        snapshot_token: 'expired-snapshot',
      },
    });
    expect(stale.status()).toBe(409);
    proof.expiredSnapshotRejected = true;
    const config = await json<
      Record<string, unknown> & { pop: Record<string, unknown> }
    >(await request.get('/api/config'));
    await json(
      await request.post('/api/config', {
        data: {
          ...config,
          pop: {
            ...config.pop,
            catalog_path: '/app/data/missing-overview-catalog.json',
          },
        },
      })
    );
    await expect(overviewA.getByLabel('Transport Advisories')).toContainText(
      /Unavailable|Stale/,
      { timeout: 65_000 }
    );
    proof.sourceFailureDoesNotClaimAllClear = true;
    expect(proof.browserErrors).toEqual([]);
    expect(proof.externalRequests).toEqual([]);
    proof.checksPassed = true;
  } finally {
    await stopHeartbeat();
    await Promise.all(contexts.map((context) => context.close()));
    await writeFile(
      `${evidence}/overview-advisories-proof.json`,
      JSON.stringify(proof, null, 2)
    );
  }
});
