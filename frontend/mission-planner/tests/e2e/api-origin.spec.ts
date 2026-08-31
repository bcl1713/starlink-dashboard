import { expect, test } from '@playwright/test';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

import {
  installOverviewRouter,
  type RecordedOverviewRequest,
} from './support/overview-router';

const forbiddenGrafana =
  /grafana|:3000|\/api\/datasources\/proxy|\/api\/plugins|\/api\/dashboards|\/dashboard|\/session/i;

test.describe('Mission Planner API origin', () => {
  test('loads an empty mission collection through the same-origin API proxy', async ({
    page,
  }) => {
    const missionRequests: string[] = [];

    await page.route('**/api/v2/missions**', async (route) => {
      const url = new URL(route.request().url());
      if (
        url.origin !== new URL(page.url()).origin &&
        page.url() !== 'about:blank'
      ) {
        await route.abort('blockedbyclient');
        return;
      }
      missionRequests.push(route.request().url());
      await route.fulfill({
        headers: { 'X-Total-Count': '0' },
        json: [],
      });
    });

    await page.goto('/missions');

    await expect(
      page.getByText('No missions yet', { exact: true })
    ).toBeVisible();
    await expect(page.getByText(/Error loading missions/)).not.toBeVisible();
    expect(missionRequests).toHaveLength(1);
    expect(new URL(missionRequests[0]).origin).toBe(new URL(page.url()).origin);
    expect(new URL(missionRequests[0]).pathname).toBe('/api/v2/missions');
  });

  test('downloads data exports through the same-origin API proxy', async ({
    page,
  }) => {
    const exportRequests: string[] = [];

    await page.route('**/api/export/starlink-csv**', async (route) => {
      exportRequests.push(route.request().url());
      await route.fulfill({
        headers: { 'Content-Type': 'text/csv' },
        body: 'timestamp,latitude\n',
      });
    });

    await page.goto('/export');
    await page.getByRole('button', { name: 'Export CSV' }).click();

    await expect.poll(() => exportRequests).toHaveLength(1);
    expect(new URL(exportRequests[0]).origin).toBe(new URL(page.url()).origin);
    expect(new URL(exportRequests[0]).pathname).toBe(
      '/api/export/starlink-csv'
    );
  });

  test('keeps browser requests away from Grafana and datasource routes', async ({
    page,
  }) => {
    const router = await installOverviewRouter(page);

    await page.goto('/overview');
    await expect(
      page.getByRole('heading', { name: 'Operations Overview' })
    ).toBeVisible();
    const forbidden = router.records.filter(isForbiddenGrafanaRequest);
    expect(forbidden).toEqual([]);
  });

  test('production overview source and built chunks have no Grafana dependency', async () => {
    const files = await overviewStaticFiles();
    const offenders: string[] = [];
    for (const file of files) {
      const body = await readFile(file, 'utf8');
      if (
        forbiddenGrafana.test(body) ||
        /from\s+['"][^'"]*grafana/i.test(body)
      ) {
        offenders.push(path.relative(process.cwd(), file));
      }
    }
    expect(offenders).toEqual([]);
  });
});

function isForbiddenGrafanaRequest(record: RecordedOverviewRequest): boolean {
  return forbiddenGrafana.test(record.url);
}

async function overviewStaticFiles(): Promise<string[]> {
  const sourceRoot = path.join(process.cwd(), 'src/pages/OverviewPage');
  const distRoot = path.join(process.cwd(), 'dist');
  const sourceFiles = await collectFiles(sourceRoot, /\.(ts|tsx|css)$/);
  const distFiles = await collectFiles(distRoot, /\.(js|css|html)$/);
  return [...sourceFiles, ...distFiles];
}

async function collectFiles(root: string, pattern: RegExp): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const file = path.join(root, entry.name);
      if (entry.isDirectory()) return collectFiles(file, pattern);
      return pattern.test(file) ? [file] : [];
    })
  );
  return files.flat();
}
