import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
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
const frozenJournal = (page: Awaited<ReturnType<typeof allPages>>) => ({
  H: page.H,
  records: page.rows.map((item) => item.record),
});

test('original training mission ZIP transfers through Missions without restoring Operator records', async ({
  page,
  browser,
}) => {
  test.setTimeout(720_000);
  const archiveInputs = execFileSync(
    'python3',
    [
      join(
        process.env.OPERATOR_TRAINING_TEST_SOURCE!,
        'tools/training/operator-mission/launcher.py'
      ),
      'archive-inputs',
      '--root',
      root,
    ],
    { encoding: 'utf8', timeout: 200_000 }
  );
  writeFileSync(join(root, 'archive-input-provenance.json'), archiveInputs);
  const health = await (
    await page.request.get('/api/v2/operator/health')
  ).json();
  const missions = await (await page.request.get('/api/v2/missions')).json();
  expect(missions).toHaveLength(1);
  const mission = await (
    await page.request.get(`/api/v2/missions/${missions[0].id}`)
  ).json();
  const id = mission.id;
  function archiveEvidence(
    command: 'baseline' | 'check',
    label: 'empty' | 'nonempty',
    zipPath?: string
  ) {
    const python = process.env.OPERATOR_TRAINING_PYTHON;
    if (!python)
      throw new Error(
        'The owned runner must provide its existing backend Python environment'
      );
    return JSON.parse(
      execFileSync(
        python,
        [
          join(
            process.env.OPERATOR_TRAINING_TEST_SOURCE!,
            'tools/training/operator-mission/archive_evidence.py'
          ),
          command,
          '--root',
          root,
          '--label',
          label,
          '--browser-origin',
          new URL(page.url()).origin,
          ...(zipPath ? ['--zip', zipPath] : []),
        ],
        { encoding: 'utf8', timeout: 260_000 }
      )
    );
  }
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
  let heldPoll = false;
  let releasePoll!: () => void;
  const holdPoll = new Promise<void>((resolve) => {
    releasePoll = resolve;
  });
  const downloads: string[] = [];
  page.on('download', (download) =>
    downloads.push(download.suggestedFilename())
  );
  const pollPath = `**/api/v2/missions/${id}/export-preparations/*`;
  await page.route(pollPath, async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    heldPoll = true;
    await holdPoll;
    await route.abort('aborted').catch(() => {});
  });
  let cancellation;
  try {
    const starting = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().endsWith(`/missions/${id}/export`)
    );
    await dialog.getByRole('button', { name: 'Export', exact: true }).click();
    const started = await starting;
    expect(started.status()).toBe(202);
    const job = await started.json();
    await expect.poll(() => heldPoll).toBe(true);
    const cancelled = page.waitForResponse(
      (response) =>
        response.request().method() === 'DELETE' &&
        response.url().endsWith(`/export-preparations/${job.id}`)
    );
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    const result = await cancelled;
    expect(result.ok()).toBe(true);
    cancellation = await result.json();
    expect(cancellation.state).toBe('cancelled');
    await expect(dialog).not.toBeVisible();
    expect(downloads).toEqual([]);
    writeFileSync(
      join(root, 'archive-cancel-proof.json'),
      JSON.stringify({ job, cancellation, noDownload: true }, null, 2)
    );
  } finally {
    releasePoll();
    await page.unroute(pollPath);
  }
  const preparationReads: Promise<unknown>[] = [];
  page.on('response', (response) => {
    if (
      response.request().method() === 'GET' &&
      response.status() === 200 &&
      new URL(response.url()).pathname.startsWith(
        `/api/v2/missions/${id}/export-preparations/`
      ) &&
      !response.url().endsWith('/download')
    )
      preparationReads.push(response.json());
  });
  await card.getByRole('button', { name: 'Export', exact: true }).click();
  const downloadedResponse = page.waitForResponse(
    (response) =>
      response.status() === 200 &&
      response.headers()['content-type']?.includes('application/zip'),
    { timeout: 620_000 }
  );
  const downloaded = page.waitForEvent('download', { timeout: 620_000 });
  await dialog.getByRole('button', { name: 'Export', exact: true }).click();
  const [download, zipResponse] = await Promise.all([
    downloaded,
    downloadedResponse,
  ]);
  expect(download.suggestedFilename()).toBe(`${id}.zip`);
  expect(await download.failure()).toBeNull();
  await download.saveAs(join(root, 'original-mission.zip'));
  expect(downloads).toEqual([`${id}.zip`]);
  const readyPreparations = await Promise.all(preparationReads);
  expect(readyPreparations).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ state: 'ready', mission_id: id }),
    ])
  );
  const originalBytes = readFileSync(join(root, 'original-mission.zip'));
  const downloadRead = {
    url: zipResponse.url(),
    status: zipResponse.status(),
    fingerprint: zipResponse.headers()['x-export-fingerprint'],
    briefingStatus: zipResponse.headers()['x-customer-briefing-status'],
    sha256: createHash('sha256').update(originalBytes).digest('hex'),
    size: originalBytes.length,
  };
  expect(downloadRead.briefingStatus).toBe('included');
  expect(readyPreparations).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        state: 'ready',
        fingerprint: downloadRead.fingerprint,
      }),
    ])
  );
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
    archiveEvidence('baseline', 'empty');
    await importOriginal();
    const emptyReport = archiveEvidence('check', 'empty');
    expect(emptyReport.originalZipSha256).toBe(downloadRead.sha256);
    const emptyAfter = await allPages(target.request, journalPath);
    expect(emptyAfter).toEqual(empty);
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
    const historyPath = `/api/v2/operator/records/${sentinel.rows[0].record.record_id}/history`;
    const sentinelHistory = frozenJournal(
      await allPages(target.request, historyPath)
    );
    archiveEvidence('baseline', 'nonempty');
    await importOriginal();
    const nonemptyReport = archiveEvidence('check', 'nonempty');
    expect(nonemptyReport.originalZipSha256).toBe(downloadRead.sha256);
    const afterImport = frozenJournal(
      await allPages(target.request, journalPath)
    );
    expect(afterImport).toEqual(frozenJournal(sentinel));
    const historyAfter = frozenJournal(
      await allPages(target.request, historyPath)
    );
    expect(historyAfter).toEqual(sentinelHistory);
    const destinationHealthAfter = await (
      await target.request.get('/api/v2/operator/health')
    ).json();
    expect(destinationHealthAfter).toEqual(destinationHealth);
    expect(
      await allPages(page.request, `/api/v2/operator/records?mission_id=${id}`)
    ).toEqual(current);
    const wrongZip = join(root, 'wrong-original.zip');
    writeFileSync(wrongZip, Buffer.concat([originalBytes, Buffer.from([0])]));
    expect(() => archiveEvidence('check', 'nonempty', wrongZip)).toThrow(
      /does not match an existing ready server artifact/
    );
    const foreign = JSON.parse(readFileSync(emptyReport.evidence, 'utf8'));
    foreign.identity.epoch = 'foreign-epoch';
    const foreignReport = join(root, 'foreign-archive-evidence.json');
    writeFileSync(foreignReport, JSON.stringify(foreign));
    let missionReadRetries = 0;
    for (const viewport of [
      { width: 1920, height: 1080 },
      { width: 390, height: 844 },
      { width: 844, height: 390 },
    ]) {
      await page.setViewportSize(viewport);
      let releaseMission: (() => void) | undefined;
      const missionPath = `**/api/v2/missions/${id}`;
      if (viewport.width === 1920) {
        const held = new Promise<void>((resolve) => {
          releaseMission = resolve;
        });
        await page.route(missionPath, async (route) => {
          await held;
          await route.abort('timedout').catch(() => {});
        });
      }
      await page.goto(`/operator?workspace=1&mission_id=${id}`);
      await page.getByRole('button', { name: 'Help', exact: true }).click();
      if (viewport.width === 1920) {
        try {
          await expect(page.getByRole('dialog')).toContainText(
            'Mission details could not be loaded',
            { timeout: 20_000 }
          );
        } finally {
          releaseMission?.();
          await page.unroute(missionPath);
        }
        await page
          .getByRole('dialog')
          .getByRole('button', { name: 'Retry mission details', exact: true })
          .click();
        missionReadRetries++;
      }
      await page
        .getByRole('dialog')
        .getByRole('button', {
          name: 'Guided mission walkthrough',
          exact: true,
        })
        .click();
      const guide = page.getByRole('complementary', {
        name: 'Guided mission walkthrough',
        exact: true,
      });
      await guide
        .getByRole('combobox', { name: 'Lesson', exact: true })
        .selectOption('T10');
      if (viewport.width === 1920) {
        await guide
          .getByLabel('Private archive evidence JSON')
          .setInputFiles(foreignReport);
        await expect(guide.getByRole('alert')).toContainText(
          'another private source'
        );
        await guide.getByLabel('Original Missions ZIP').setInputFiles(wrongZip);
        await expect(guide.getByText(/Selected ZIP:/)).toContainText(
          'wrong-original.zip'
        );
        await guide
          .getByLabel('Private archive evidence JSON')
          .setInputFiles([emptyReport.evidence, nonemptyReport.evidence]);
        await guide
          .getByRole('button', {
            name: 'Check selected archive evidence',
            exact: true,
          })
          .click();
        await expect(guide.getByRole('alert')).toContainText(
          'Select the unchanged original ZIP'
        );
      }
      if (viewport.width === 1920) {
        await guide
          .getByLabel('Original Missions ZIP')
          .setInputFiles(join(root, 'original-mission.zip'));
        await expect(guide.getByText(/Selected ZIP:/)).toContainText(
          'original-mission.zip'
        );
        await guide
          .getByRole('button', {
            name: 'Check selected archive evidence',
            exact: true,
          })
          .click();
      } else {
        await guide
          .getByRole('button', { name: 'Check current evidence', exact: true })
          .click();
      }
      await expect(
        guide
          .getByRole('listitem')
          .filter({ hasText: 'Verified from imported tooling evidence' })
      ).toHaveCount(4);
      await expect(
        guide.getByRole('listitem').filter({ hasText: 'Human observation' })
      ).toHaveCount(0);
      await expect(
        guide.getByRole('status').filter({ hasText: /^Incomplete$/ })
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1
        )
      ).toBe(true);
      await page.screenshot({
        path: join(
          root,
          `guided-archive-evidence-${viewport.width}x${viewport.height}.png`
        ),
      });
    }
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
          sourceOrigin: new URL(page.url()).origin,
          destinationOrigin: destination,
          destinationHealthAfter,
          emptyBefore: frozenJournal(empty),
          emptyAfter: frozenJournal(emptyAfter),
          importedMission,
          nonemptyBefore: frozenJournal(sentinel),
          nonemptyAfter: afterImport,
          nonemptyHistoryBefore: sentinelHistory,
          nonemptyHistoryAfter: historyAfter,
          downloadRead,
          missionReadRetries,
          readyPreparations,
          unchangedOriginalZipImportedTwice: true,
          actualMissionsControls: true,
          networkFailureRetry: true,
          preparationCancel: cancellation,
          guideToolingEvidenceAtThreeSizes: true,
          foreignReportAndWrongOriginalRejected: true,
          humanPdfReviewAndNetworkFailureObservation: 'not claimed',
          toolingReports: [emptyReport.evidence, nonemptyReport.evidence],
        },
        null,
        2
      )
    );
  } finally {
    await target.close();
  }
});
