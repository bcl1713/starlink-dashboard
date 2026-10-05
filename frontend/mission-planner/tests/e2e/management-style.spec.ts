import { expect, test, type Locator } from '@playwright/test';
import { runningStatus } from '../../src/test/simulation-run-fixtures';
import { installOverviewWindowFixture } from './support/overview-window-fixture';

async function palette(locator: Locator) {
  return locator.evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      background: style.getPropertyValue('--background').trim(),
      foreground: style.getPropertyValue('--foreground').trim(),
      card: style.getPropertyValue('--card').trim(),
    };
  });
}

for (const width of [1440, 390]) {
  test(`management pages and portals share Configuration's palette at ${width}px`, async ({
    page,
    context,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await installOverviewWindowFixture(context);
    await context.route('**/api/v2/missions?*', (route) =>
      route.fulfill({ json: [], headers: { 'X-Total-Count': '0' } })
    );
    const simulation = runningStatus();
    simulation.run!.mission_id = 'window-mission';
    simulation.run!.leg_id = 'leg-a';
    await context.route('**/api/simulation/run', (route) =>
      route.fulfill({ json: simulation })
    );
    await page.goto('/configuration');
    const reference = await palette(
      page.getByRole('heading', { name: 'Configuration', exact: true })
    );
    for (const [path, heading] of [
      ['/missions', 'Missions'],
      ['/missions/window-mission', 'Mission Legs'],
      ['/satellites', 'Satellite Manager'],
      ['/pois', 'Points of Interest'],
      ['/routes', 'Route Manager'],
      ['/export', 'Data Export'],
      ['/missions/window-mission/legs/leg-a', 'Leg Configuration'],
    ]) {
      await page.goto(path);
      const title = page.getByText(heading, { exact: true }).last();
      await expect(title).toBeVisible();
      expect(await palette(title)).toEqual(reference);
      if (path === '/missions/window-mission') {
        await expect(
          page.getByRole('region', { name: 'Simulation run' })
        ).toHaveCSS(
          'background-color',
          await page
            .getByRole('navigation', {
              name: 'Primary navigation',
              includeHidden: true,
            })
            .evaluate((node) => getComputedStyle(node).backgroundColor)
        );
      }
      if (path === '/pois') {
        await expect(page.locator('.leaflet-control-zoom-in')).toHaveCSS(
          'background-color',
          await page
            .getByRole('navigation', {
              name: 'Primary navigation',
              includeHidden: true,
            })
            .evaluate((node) => getComputedStyle(node).backgroundColor)
        );
      }
      expect(
        await palette(
          page.getByRole('navigation', {
            name: 'Primary navigation',
            includeHidden: true,
          })
        )
      ).toEqual(reference);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth
        )
      ).toBe(true);
      expect(
        await page
          .locator('.app-route-content')
          .evaluate((node) => node.scrollWidth <= node.clientWidth)
      ).toBe(true);
      await page.screenshot({
        path: test
          .info()
          .outputPath(`${path.replaceAll('/', '-').slice(1)}-${width}.png`),
      });
    }
    await page.goto('/routes');
    await page
      .getByRole('row', { name: /KAAA to KBBB/ })
      .getByTitle('View route details')
      .click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(
      page.getByRole('dialog').locator('.leaflet-control-zoom-in')
    ).toHaveCSS(
      'background-color',
      await page
        .getByRole('navigation', {
          name: 'Primary navigation',
          includeHidden: true,
        })
        .evaluate((node) => getComputedStyle(node).backgroundColor)
    );
    await page.keyboard.press('Escape');
    await page.goto('/missions');
    if (width === 390) {
      const menu = page.getByRole('button', { name: 'Toggle navigation' });
      await menu.click();
      await expect(menu).toHaveAttribute('aria-expanded', 'true');
      await page
        .getByRole('link', { name: 'Data Export', exact: true })
        .click();
      await expect(page).toHaveURL(/\/export$/);
      await expect(menu).toHaveAttribute('aria-expanded', 'false');
      await page.goto('/missions');
    }
    await page.getByRole('button', { name: 'Create New Mission' }).click();
    expect(await palette(page.getByRole('dialog'))).toEqual(reference);
    await page.keyboard.press('Escape');
    await page.goto('/export');
    await page.getByRole('combobox', { name: 'Resolution' }).click();
    expect(await palette(page.getByRole('listbox'))).toEqual(reference);
    await page.getByRole('option', { name: '1 minute', exact: true }).click();
    await expect(page.getByRole('combobox', { name: 'Resolution' })).toHaveText(
      '1 minute'
    );
    await page.screenshot({
      path: test.info().outputPath(`export-${width}.png`),
    });
  });
}

test('navigation to and from management pages preserves Overview theme', async ({
  page,
  context,
}) => {
  await installOverviewWindowFixture(context);
  await page.goto('/overview');
  const before = await palette(page.locator('.app-route-content'));
  await page.getByRole('link', { name: 'Configuration', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Configuration', exact: true })
  ).toBeVisible();
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await expect(page).toHaveURL(/\/overview$/);
  expect(await palette(page.locator('.app-route-content'))).toEqual(before);
  expect(before.background).toBe('#f6f8fb');
  expect(
    await palette(
      page.getByRole('navigation', {
        name: 'Primary navigation',
        includeHidden: true,
      })
    )
  ).not.toEqual(before);
});
