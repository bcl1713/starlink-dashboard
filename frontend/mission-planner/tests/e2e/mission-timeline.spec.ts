import { test, expect } from '@playwright/test';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import type { MissionTimelineSnapshot } from '../../src/types/missionTimeline';

const origin = process.env.OPERATOR_ACCEPTANCE_ORIGIN!;
const evidence = process.env.OPERATOR_ACCEPTANCE_EVIDENCE!;
const mission = 'synthetic-mission-a';
const timelinePath = `/api/v2/operator/events/mission-timeline?mission_id=${mission}`;
const initial = {
  now: '2026-10-17T16:10:00Z',
  route_shift: 0,
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
};

test('whole mission chronology and usable workspace on phones, with retained drafts', async ({
  browser,
  request,
}) => {
  expect(
    (
      await request.post(`${origin}/api/_synthetic/operator-model-inputs`, {
        data: initial,
      })
    ).ok()
  ).toBe(true);
  const geometry = [];
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 375, height: 667 },
    { width: 390, height: 600 },
    { width: 320, height: 568 },
    { width: 844, height: 390 },
  ]) {
    const phone = viewport.width < 900;
    const context = await browser.newContext({
      viewport,
      isMobile: phone,
      hasTouch: phone,
    });
    try {
      const page = await context.newPage();
      await page.goto(`${origin}/operator?mission_id=${mission}`);
      const navigation = page.getByRole('navigation', {
        name: 'Operator workspace',
      });
      const launch = page.getByRole('button', {
        name: 'Open mission timeline',
        exact: true,
      });
      for (const name of ['Communications', 'Transport', 'Issues']) {
        await navigation.getByRole('button', { name, exact: true }).click();
        await expect(
          navigation.getByRole('button', { name, exact: true })
        ).toHaveAttribute('aria-current', 'page');
        if (phone) await expect(launch).toBeInViewport({ ratio: 1 });
        else
          await expect(
            page.getByRole('region', { name: 'Mission timeline', exact: true })
          ).toBeInViewport();
      }
      const body = page.locator('.ws-body');
      const before = await body.boundingBox();
      expect(
        before!.height,
        'Main work area has useful screen space'
      ).toBeGreaterThanOrEqual(phone ? viewport.height * 0.35 : 132);
      await expect(body).toBeInViewport({ ratio: 0.99 });
      if (phone) await launch.click();
      const timeline = phone
        ? page.getByRole('dialog', { name: 'Mission timeline', exact: true })
        : page.getByRole('region', { name: 'Mission timeline', exact: true });
      await expect(
        timeline.getByRole('list', {
          name: 'Mission events from start to finish',
        })
      ).toBeVisible();
      await expect(
        timeline
          .getByRole('heading', { name: 'Scheduled departure', exact: true })
          .first()
      ).toBeVisible();
      const scroll = timeline.locator('.ws-timeline-body');
      const bounds = await scroll.boundingBox();
      if (phone) {
        expect(
          bounds!.height,
          'Timeline uses most of the phone screen'
        ).toBeGreaterThan(viewport.height * 0.65);
        const screen = await timeline.boundingBox();
        expect(screen!.x).toBeCloseTo(0, 0);
        expect(screen!.y).toBeCloseTo(0, 0);
        expect(screen!.height).toBeCloseTo(viewport.height, 0);
      }
      const times = await timeline
        .locator('.ws-timeline-time time')
        .evaluateAll((elements) =>
          elements.map((element) =>
            Date.parse(element.getAttribute('datetime')!)
          )
        );
      expect(times).toEqual([...times].sort((a, b) => a - b));
      await timeline
        .getByRole('heading', { name: 'Scheduled arrival', exact: true })
        .last()
        .scrollIntoViewIfNeeded();
      await expect(
        timeline
          .getByRole('heading', { name: 'Scheduled arrival', exact: true })
          .last()
      ).toBeInViewport();
      await timeline.getByRole('button', { name: 'Jump to now' }).click();
      await expect(timeline.locator('.ws-timeline-now')).toBeInViewport();
      await page.screenshot({
        path: join(
          evidence,
          `timeline-${viewport.width}x${viewport.height}.png`
        ),
      });
      if (phone) {
        await timeline
          .getByRole('button', { name: 'Close', exact: true })
          .click();
        await expect(launch).toBeFocused();
        expect((await body.boundingBox())!.height).toBeCloseTo(
          before!.height,
          0
        );
      }
      await page.getByRole('button', { name: 'Note', exact: true }).click();
      const title = `Phone draft ${viewport.width}x${viewport.height}`;
      await page.getByLabel('Title', { exact: true }).fill(title);
      await page
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      if (phone) {
        await launch.click();
        await page.keyboard.press('Escape');
        await expect(launch).toBeFocused();
      }
      await navigation
        .getByRole('button', { name: 'Communications', exact: true })
        .click();
      await page.getByRole('button', { name: new RegExp(`^${title}`) }).click();
      await expect(page.getByLabel('Title', { exact: true })).toHaveValue(
        title
      );
      await page
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      await page.screenshot({
        path: join(
          evidence,
          `workspace-${viewport.width}x${viewport.height}.png`
        ),
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth
        )
      ).toBe(true);
      geometry.push({
        viewport,
        body: before,
        timeline: bounds,
        draftRetained: true,
      });
    } finally {
      await context.close();
    }
  }
  writeFileSync(
    join(evidence, 'mobile-geometry.json'),
    JSON.stringify(geometry, null, 2)
  );
});

test('automatic refresh follows moving flight while scheduled UTC events stay fixed', async ({
  browser,
  request,
}) => {
  expect(
    (
      await request.post(`${origin}/api/_synthetic/operator-model-inputs`, {
        data: initial,
      })
    ).ok()
  ).toBe(true);
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    recordVideo: {
      dir: join(evidence, 'moving-flight-video'),
      size: { width: 390, height: 844 },
    },
  });
  try {
    const page = await context.newPage();
    await page.goto(`${origin}/operator?mission_id=${mission}`);
    await page
      .getByRole('button', { name: 'Open mission timeline', exact: true })
      .click();
    const timeline = page.getByRole('dialog', {
      name: 'Mission timeline',
      exact: true,
    });
    const fixed = (data: MissionTimelineSnapshot) =>
      data.events
        .filter((event) =>
          ['call_start', 'call_prep', 'issue_followup'].includes(event.kind)
        )
        .map((event) => ({
          id: event.event_id,
          due_at: event.due_at,
          end_at: event.end_at,
        }))
        .sort((a, b) => a.id.localeCompare(b.id));
    const read = async () => {
      const response = await request.get(`${origin}${timelinePath}`);
      expect(response.ok()).toBe(true);
      return (await response.json()) as MissionTimelineSnapshot;
    };
    const first = await read();
    const reference = fixed(first);
    const x = (data: MissionTimelineSnapshot) =>
      data.events.find(
        (event) =>
          event.kind === 'restriction' &&
          event.transport === 'X' &&
          event.leg_id === 'synthetic-leg-1'
      )!;
    const snapshots = [first];
    for (const data of [
      { now: '2026-10-17T16:11:00Z', longitude: -9.4, speed: 600 },
      { now: '2026-10-17T16:12:00Z', longitude: -9.3, speed: 300 },
    ]) {
      expect(
        (
          await request.post(`${origin}/api/_synthetic/operator-model-inputs`, {
            data,
          })
        ).ok()
      ).toBe(true);
      const current = await read();
      snapshots.push(current);
      expect(fixed(current)).toEqual(reference);
      expect(x(current).time_basis).toBe('live_route_eta');
      expect(x(current).due_at).not.toBe(
        x(snapshots[snapshots.length - 2]).due_at
      );
      expect(x(current).end_at).not.toBe(
        x(snapshots[snapshots.length - 2]).end_at
      );
      const row = timeline
        .locator('.ws-timeline-row')
        .filter({
          has: page.getByRole('heading', {
            name: x(current).title,
            exact: true,
          }),
        })
        .filter({ hasText: 'Live route ETA' })
        .first();
      // No manual refresh, route interception, response mocks, or browser clock changes.
      await expect(row.locator('.ws-timeline-time time')).toHaveAttribute(
        'datetime',
        x(current).due_at!,
        { timeout: 25000 }
      );
      await row.scrollIntoViewIfNeeded();
      await page.screenshot({
        path: join(evidence, `flight-${snapshots.length}.png`),
      });
    }
    writeFileSync(
      join(evidence, 'moving-flight-proof.json'),
      JSON.stringify(
        {
          rawInputs: true,
          automaticPolling: true,
          scheduledTimesFixed: true,
          snapshots,
        },
        null,
        2
      )
    );
  } finally {
    await context.close();
  }
});
