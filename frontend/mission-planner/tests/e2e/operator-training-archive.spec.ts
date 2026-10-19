import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, type APIRequestContext } from '@playwright/test';

const root = process.env.OPERATOR_TRAINING_PROOF_ROOT!;
const destination = process.env.OPERATOR_TRAINING_ARCHIVE_ORIGIN!;
if (!root?.startsWith('/tmp/issue-376-training-proof-') || !destination)
  throw new Error('Owned source and separate archive destination required');

async function allPages(request: APIRequestContext, path: string) {
  const rows = [];
  const cursors = new Set<string>();
  let cursor: string | null = null;
  let H: number | undefined;
  do {
    const response = await request.get(path, {
      params: cursor ? { cursor } : {},
    });
    expect(response.ok(), await response.text()).toBe(true);
    const page = await response.json();
    if (H !== undefined) expect(page.H).toBe(H);
    H = page.H;
    rows.push(...page.items);
    cursor = page.cursor;
    if (cursor) {
      expect(cursors.has(cursor)).toBe(false);
      cursors.add(cursor);
      expect(cursors.size).toBeLessThan(100);
    }
  } while (cursor);
  return { rows, H };
}

test('original training mission ZIP transfers through Missions without restoring Operator records', async ({
  page,
  browser,
}) => {
  test.setTimeout(720_000);
  const health = await (
    await page.request.get('/api/v2/operator/health')
  ).json();
  const missions = await (await page.request.get('/api/v2/missions')).json();
  expect(missions).toHaveLength(1);
  const mission = await (
    await page.request.get(`/api/v2/missions/${missions[0].id}`)
  ).json();
  const id = mission.id;
  const current = await allPages(
    page.request,
    `/api/v2/operator/records?mission_id=${id}`
  );
  const records = current.rows.map((row) => row.record);
  const history = [];
  for (const record of records) {
    const versions = await allPages(
      page.request,
      `/api/v2/operator/records/${record.record_id}/history`
    );
    history.push(...versions.rows.map((row) => row.record));
  }
  writeFileSync(
    join(root, 'archive-source-snapshot.json'),
    JSON.stringify({ health, mission, H: current.H, records, history }, null, 2)
  );
  await page.goto('/missions');
  const card = page
    .locator('div.rounded-xl.border.bg-card')
    .filter({ has: page.getByText(mission.name, { exact: true }) });
  await card.getByRole('button', { name: 'Export', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(
    dialog.getByRole('heading', {
      name: `Export Mission: ${mission.name}`,
      exact: true,
    })
  ).toBeVisible();
  await page.route(`**/api/v2/missions/${id}/export`, (route) =>
    route.abort('failed')
  );
  await dialog.getByRole('button', { name: 'Export', exact: true }).click();
  await expect(
    dialog.getByText('Export failed. Please try again.', { exact: true })
  ).toBeVisible();
  await page.unroute(`**/api/v2/missions/${id}/export`);
  const downloaded = page.waitForEvent('download', { timeout: 620_000 });
  await dialog.getByRole('button', { name: 'Export', exact: true }).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toBe(`${id}.zip`);
  expect(await download.failure()).toBeNull();
  await download.saveAs(join(root, 'original-mission.zip'));
  // An omitted customer PDF keeps the dialog open and must fail this gate.
  await expect(dialog).not.toBeVisible({ timeout: 20_000 });
  expect(
    await allPages(page.request, `/api/v2/operator/records?mission_id=${id}`)
  ).toEqual(current);
  const target = await browser.newContext({
    baseURL: destination,
    viewport: { width: 1920, height: 1080 },
  });
  try {
    const importedPage = await target.newPage();
    const destinationHealth = await (
      await target.request.get('/api/v2/operator/health')
    ).json();
    expect(destinationHealth.ready).toBe(true);
    expect(destinationHealth.store_id).not.toBe(health.store_id);
    const existingMissions = await (
      await target.request.get('/api/v2/missions')
    ).json();
    expect(existingMissions).toEqual([]);
    const journalPath = `/api/v2/operator/records?mission_id=${id}`;
    const empty = await allPages(target.request, journalPath);
    expect(empty.rows).toEqual([]);
    async function importOriginal() {
      await importedPage.goto('/missions');
      await importedPage
        .getByRole('button', { name: 'Import Mission', exact: true })
        .click();
      const importing = importedPage.getByRole('dialog');
      await importing
        .locator('input[type=file]')
        .setInputFiles(join(root, 'original-mission.zip'));
      await expect(
        importing.getByText('Import successful!', { exact: true })
      ).toBeVisible();
      await importedPage.screenshot({
        path: join(root, 'archive-import-destination.png'),
      });
      await expect(importing).not.toBeVisible();
    }
    await importOriginal();
    expect(await allPages(target.request, journalPath)).toEqual(empty);
    const importedMission = await (
      await target.request.get(`/api/v2/missions/${id}`)
    ).json();
    expect(
      importedMission.legs.map((leg: { name: string }) => leg.name)
    ).toEqual(mission.legs.map((leg: { name: string }) => leg.name));
    expect(
      importedMission.legs.map((leg: { transports: unknown }) => leg.transports)
    ).toEqual(
      mission.legs.map((leg: { transports: unknown }) => leg.transports)
    );
    await importedPage.goto(`/operator?workspace=1&mission_id=${id}`);
    await importedPage
      .getByRole('button', { name: 'Note', exact: true })
      .click();
    const editor = importedPage.getByRole('dialog');
    await editor
      .getByLabel('Title', { exact: true })
      .fill('Separate destination journal sentinel');
    const saved = importedPage.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().endsWith('/api/v2/operator/records')
    );
    await editor
      .getByRole('button', { name: 'Save entry', exact: true })
      .click();
    expect((await saved).ok()).toBe(true);
    const sentinel = await allPages(target.request, journalPath);
    expect(sentinel.rows).toHaveLength(1);
    await importOriginal();
    expect(await allPages(target.request, journalPath)).toEqual(sentinel);
    expect(
      await allPages(page.request, `/api/v2/operator/records?mission_id=${id}`)
    ).toEqual(current);
    writeFileSync(
      join(root, 'archive-transfer-proof.json'),
      JSON.stringify(
        {
          synthetic: true,
          sourceHealth: health,
          destinationHealth,
          emptyBeforeAndAfter: empty,
          nonemptyBeforeAndAfter: sentinel,
          unchangedOriginalZipImportedTwice: true,
          actualMissionsControls: true,
          networkFailureRetry: true,
          preparationCancel: 'pending dedicated branch',
        },
        null,
        2
      )
    );
  } finally {
    await target.close();
  }
});
