import { expect, test } from '@playwright/test';
import { installOverviewRoutes } from './overview-fixtures';

test('production polling keeps every cadence continuous through fullscreen states', async ({
  page,
}) => {
  await page.clock.install({ time: new Date('2026-09-03T10:00:00Z') });
  const requests = await installOverviewRoutes(page);
  await page.goto('/overview');
  await expect(page.getByText('27.0 ms', { exact: true })).toBeVisible();
  await page.clock.pauseAt(await page.evaluate(() => Date.now()));
  const root = page.getByTestId('overview-root');
  const rootHandle = await root.elementHandle();
  const mapHandle = await page.locator('.current-position-map').elementHandle();
  const cadenceControl = page.getByLabel('Refresh cadence');

  const runCadence = async (cadence: 1 | 2 | 5 | 10 | 30) => {
    await cadenceControl.selectOption(String(cadence));
    const before = requests();
    await page.clock.fastForward(cadence * 1000 - 1);
    expect(requests()).toBe(before);
    await page.clock.fastForward(1);
    await expect.poll(requests).toBe(before + 1);
    expect(requests()).toBe(before + 1);
  };

  await cadenceControl.selectOption('2');
  const beforeEntry = requests();
  await page.getByRole('button', { name: 'Enter fullscreen' }).click();
  await expect(root).toBeFocused();
  expect(requests()).toBe(beforeEntry);
  await runCadence(1);

  await runCadence(2);
  expect(await page.evaluate(() => document.fullscreenElement?.tagName)).toBe(
    'MAIN'
  );

  const beforeExit = requests();
  await page.getByRole('button', { name: 'Exit fullscreen' }).click();
  await expect
    .poll(() => page.evaluate(() => document.fullscreenElement))
    .toBeNull();
  expect(requests()).toBe(beforeExit);
  await runCadence(5);

  await root.evaluate((element) => {
    element.requestFullscreen = () => Promise.reject(new Error('denied'));
  });
  await cadenceControl.selectOption('10');
  const beforeRejection = requests();
  await page.getByRole('button', { name: 'Enter fullscreen' }).click();
  await expect(page.getByRole('status')).toContainText(
    'Fullscreen was unavailable'
  );
  await expect(
    page.getByRole('button', { name: 'Enter fullscreen' })
  ).toBeFocused();
  expect(requests()).toBe(beforeRejection);
  await runCadence(10);
  await runCadence(30);

  await cadenceControl.selectOption('paused');
  const beforePause = requests();
  await page.clock.fastForward(60_000);
  expect(requests()).toBe(beforePause);
  await page.getByRole('button', { name: 'Refresh live status' }).click();
  await expect.poll(requests).toBe(beforePause + 1);
  await page.clock.fastForward(60_000);
  expect(requests()).toBe(beforePause + 1);

  expect(
    await page.evaluate(
      ({ root, map }) =>
        document.querySelector('[data-testid="overview-root"]') === root &&
        document.querySelector('.current-position-map') === map,
      { root: rootHandle, map: mapHandle }
    )
  ).toBe(true);
  expect(requests.starts()).toHaveLength(requests());
});
