import { test, expect } from '@playwright/test';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import type { MissionTimelineSnapshot } from '../../src/types/missionTimeline';

const origin = process.env.OPERATOR_ACCEPTANCE_ORIGIN!;
const evidence = process.env.OPERATOR_ACCEPTANCE_EVIDENCE!;
const mission = 'synthetic-mission-a';

test('persistent chronology and retained draft at desktop and narrow widths using raw production inputs', async ({
  browser,
  request,
}) => {
  const seed = await request.post(
    `${origin}/api/_synthetic/operator-model-inputs`,
    {
      data: {
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
      },
    }
  );
  expect(seed.ok(), await seed.text()).toBe(true);
  const response = await request.get(
    `${origin}/api/v2/operator/events/mission-timeline?mission_id=${mission}`
  );
  expect(response.ok(), await response.text()).toBe(true);
  const snapshot: MissionTimelineSnapshot = await response.json();
  const x = snapshot.events.find(
    (event) =>
      event.kind === 'restriction' && event.transport === 'X' && event.active
  )!;
  expect(x?.time_basis).toBe('live_route_eta');
  expect(x.due_at).toBeTruthy();
  expect(x.end_at).toBeTruthy();
  expect(
    snapshot.events.every(
      (event) =>
        !event.notification.eligible &&
        !event.notification.acknowledgment_available
    )
  ).toBe(true);
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({ viewport });
    try {
      const page = await context.newPage();
      await page.goto(`${origin}/operator?mission_id=${mission}`);
      const panel = page.getByRole('region', {
        name: 'Mission timeline',
        exact: true,
      });
      await expect(
        panel.getByRole('heading', { name: 'Mission timeline', exact: true })
      ).toBeVisible();
      const xRow = panel
        .locator('.ws-timeline-row')
        .filter({
          has: page.getByRole('heading', { name: x.title, exact: true }),
        })
        .filter({ hasText: 'Live route ETA' })
        .first();
      const toggle = panel.getByRole('button', {
        name: 'Expand mission timeline',
      });
      if (viewport.width < 900) {
        await expect(toggle).toBeVisible();
        await toggle.click();
      }
      await expect(xRow).toBeVisible();
      await expect(panel.getByText(/Live route ETA/).first()).toBeVisible();
      await expect(panel.getByText(/Expected recovery/).first()).toBeVisible();
      await expect(panel.getByText('Now', { exact: true })).toBeVisible();
      for (const view of ['Communications', 'Transport', 'Issues']) {
        await page
          .getByRole('navigation', { name: 'Operator workspace' })
          .getByRole('button', { name: view, exact: true })
          .click();
        await expect(xRow).toBeVisible();
        await expect(
          page.getByRole('region', { name: 'Mission activity', exact: true })
        ).toHaveCount(0);
      }
      await page.getByRole('button', { name: 'Note', exact: true }).click();
      const title = page.getByLabel('Title', { exact: true });
      await title.fill(`Retained timeline draft ${viewport.width}`);
      await page
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      if (viewport.width < 900) {
        await panel
          .getByRole('button', { name: 'Collapse mission timeline' })
          .click();
        await panel
          .getByRole('button', { name: 'Expand mission timeline' })
          .click();
      }
      await page
        .getByRole('navigation', { name: 'Operator workspace' })
        .getByRole('button', { name: 'Communications', exact: true })
        .click();
      await page
        .getByRole('button', {
          name: new RegExp(`^Retained timeline draft ${viewport.width}`),
        })
        .click();
      await expect(page.getByLabel('Title', { exact: true })).toHaveValue(
        `Retained timeline draft ${viewport.width}`
      );
      await page
        .getByRole('button', { name: 'Keep draft and return', exact: true })
        .click();
      const geometry = await panel
        .locator('.ws-timeline-body')
        .evaluate((element) => ({
          overflowY: getComputedStyle(element).overflowY,
          height: element.getBoundingClientRect().height,
          viewport: window.innerHeight,
        }));
      expect(geometry.overflowY).toBe('auto');
      expect(geometry.height).toBeLessThan(geometry.viewport);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth
        )
      ).toBe(true);
      await page.screenshot({
        path: join(evidence, `mission-timeline-${viewport.width}.png`),
        fullPage: true,
      });
      writeFileSync(
        join(evidence, `mission-timeline-${viewport.width}.json`),
        JSON.stringify(
          {
            rawProductionInputs: true,
            mockedBrowserData: false,
            viewport,
            geometry,
            persistentAcross: ['Communications', 'Transport', 'Issues'],
            draftRetained: true,
          },
          null,
          2
        )
      );
    } finally {
      await context.close();
    }
  }
});
