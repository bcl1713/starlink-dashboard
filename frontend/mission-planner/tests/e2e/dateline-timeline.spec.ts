import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import type { Timeline } from '../../src/services/timeline';

// The backend calculates this fabricated route during the test. Only HTTP
// delivery is intercepted; the timeline itself is not a hand-written response.
const backend = path.resolve('../../backend/starlink-location');
let fixture: { mission: unknown; route: unknown; timeline: Timeline };
test.beforeAll(() => {
  fixture = JSON.parse(
    execFileSync(
      process.env.STARLINK_TEST_PYTHON ?? 'python3',
      ['tests/fixtures/generate_dateline_acceptance.py'],
      {
        cwd: backend,
        env: { ...process.env, PYTHONPATH: backend },
        encoding: 'utf8',
      }
    )
  );
});

test('planning timeline shows recovered Ka and the footprint sequence across midnight', async ({
  page,
}) => {
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const json = pathname.includes('/timeline')
      ? fixture.timeline
      : pathname === '/api/v2/missions/synthetic-271'
        ? fixture.mission
        : pathname === '/api/routes/synthetic-271-route'
          ? fixture.route
          : pathname === '/api/satellites'
            ? []
            : pathname.startsWith('/api/pois')
              ? { pois: [], total: 0 }
              : {};
    await route.fulfill({ json });
  });
  await page.goto('/missions/synthetic-271/legs/synthetic-271-leg');
  const preview = page.locator(
    'section[aria-labelledby="timeline-preview-heading"]'
  );
  const coverage = preview.getByRole('table', { name: 'Ka coverage sequence' });
  await expect(coverage).toBeVisible();
  const entry = coverage
    .getByRole('row')
    .filter({ hasText: 'IOR footprint entry' });
  await expect(entry).toContainText('IOR, POR');
  await expect(
    coverage.getByRole('row').filter({ hasText: 'Recommended handoff' })
  ).toContainText('POR → IOR');
  const exit = coverage
    .getByRole('row')
    .filter({ hasText: 'POR footprint exit' })
    .last();
  await expect(exit.locator('td').last()).toHaveText('IOR');
  await expect(coverage).toContainText('Ka coverage lost');
  await expect(coverage).toContainText('Ka coverage restored');
  await expect(coverage).toContainText('2035-03-02');
  const states = preview.getByRole('table').last();
  await expect(states).toContainText('2035-03-01 23:00:00');
  await expect(states).toContainText('2035-03-02 08:00:00');
  await expect(states).toContainText('T+9h');
  await expect(states.getByRole('row').last()).toContainText('Ka: AVAILABLE');
  await expect(states).toContainText('Ku: AVAILABLE');
  await expect(states).toContainText('X:');
  const details = states.locator('summary').first();
  await details.click();
  await expect(details.locator('..')).toHaveAttribute('open', '');
});
