import { expect, test, type Page } from '@playwright/test';
import { observeOverviewCamera } from './support/overview-camera';

async function renderedHistoryPoints(page: Page) {
  return page.evaluate(() => {
    type Fiber = {
      child?: Fiber;
      sibling?: Fiber;
      memoizedProps?: { core?: { color?: string }; points?: number[][] };
    };
    const roots =
      (
        window as unknown as {
          __overviewEvidenceRoots?: Array<{ current?: Fiber }>;
        }
      ).__overviewEvidenceRoots ?? [];
    const pending = roots.flatMap((root) =>
      root.current ? [root.current] : []
    );
    while (pending.length) {
      const fiber = pending.pop()!;
      if (
        fiber.memoizedProps?.core?.color === '#d9ffff' &&
        fiber.memoizedProps.points
      )
        return fiber.memoizedProps.points.length;
      if (fiber.child) pending.push(fiber.child);
      if (fiber.sibling) pending.push(fiber.sibling);
    }
    return 0;
  });
}

test('saved aircraft history visibility reaches an open Overview through production Nginx', async ({
  context,
  request,
}, info) => {
  expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
  const initial = await request.get('/api/overview-links/settings');
  expect(initial.status()).toBe(200);
  expect((await initial.json()).aircraft_history_enabled).toBe(true);

  const overview = await context.newPage();
  await observeOverviewCamera(overview);
  const historyReads: number[] = [];
  overview.on('response', (response) => {
    if (
      new URL(response.url()).pathname === '/api/overview-history' &&
      response.status() === 200
    )
      historyReads.push(Date.now());
  });
  await overview.goto('/overview');
  await expect(
    overview.getByText('Track history', { exact: true })
  ).toBeVisible({ timeout: 90_000 });
  await expect
    .poll(() => renderedHistoryPoints(overview))
    .toBeGreaterThanOrEqual(2);
  const globe = await overview
    .locator('.overview-globe canvas')
    .elementHandle();
  const graphs = await overview
    .locator('.overview-metric-history__surface canvas')
    .elementHandles();
  expect(graphs.length).toBe(5);
  await overview.screenshot({ path: info.outputPath('history-enabled.png') });

  const configuration = await context.newPage();
  await configuration.goto('/configuration');
  await configuration.getByRole('tab', { name: 'Network Traffic' }).click();
  const toggle = configuration.getByRole('switch', {
    name: 'Aircraft history',
    exact: true,
  });
  await expect(toggle).toBeEnabled();
  await expect(toggle).toBeChecked();
  await configuration.screenshot({
    path: info.outputPath('history-switch.png'),
  });
  const before = await (
    await request.get('/api/overview-links/settings')
  ).json();
  const historyWindow = await (
    await request.get('/api/overview-history/settings')
  ).json();
  const readsBefore = historyReads.length;
  const save = configuration.waitForResponse(
    (response) =>
      response.url().endsWith('/api/overview-links/settings') &&
      response.request().method() === 'PUT'
  );
  await toggle.focus();
  await toggle.press('Space');
  const confirmed = await save;
  expect(confirmed.status()).toBe(200);
  expect(confirmed.headers().server).toMatch(/nginx/);
  expect(confirmed.request().postDataJSON()).toEqual({
    aircraft_history_enabled: false,
  });
  expect(await confirmed.json()).toEqual({
    ...before,
    aircraft_history_enabled: false,
  });
  await expect(toggle).not.toBeChecked();
  await expect(
    overview.getByText('Track history', { exact: true })
  ).toHaveCount(0, { timeout: 10_000 });
  await expect.poll(() => renderedHistoryPoints(overview)).toBe(0);
  await expect
    .poll(() => historyReads.length, { timeout: 10_000 })
    .toBeGreaterThan(readsBefore);
  expect(
    await (await request.get('/api/overview-history/settings')).json()
  ).toEqual(historyWindow);
  expect(await globe!.evaluate((node) => document.contains(node))).toBe(true);
  for (const graph of graphs)
    expect(await graph.evaluate((node) => document.contains(node))).toBe(true);
  await overview.screenshot({ path: info.outputPath('history-disabled.png') });

  await overview.reload();
  await expect(overview.locator('.overview-globe canvas')).toBeVisible();
  await expect(
    overview.getByText('Track history', { exact: true })
  ).toHaveCount(0);
  expect(
    (await (await request.get('/api/overview-links/settings')).json())
      .aircraft_history_enabled
  ).toBe(false);
  await toggle.click();
  await expect(toggle).toBeChecked();
  await expect(
    overview.getByText('Track history', { exact: true })
  ).toBeVisible({ timeout: 10_000 });
  await expect
    .poll(() => renderedHistoryPoints(overview))
    .toBeGreaterThanOrEqual(2);
});
