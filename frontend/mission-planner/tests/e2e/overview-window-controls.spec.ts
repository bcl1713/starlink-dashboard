import { expect, test, type Page } from '@playwright/test';
import {
  observeOverviewCamera,
  settledOverviewCamera,
  expectSameCamera,
} from './support/overview-camera';
import {
  installOverviewWindowFixture,
  retainedHistoryTimes,
} from './support/overview-window-fixture';

test.use({ viewport: { width: 1920, height: 1080 } });
async function explore(page: Page) {
  const box = (await page.locator('.overview-globe canvas').boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.6);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5, {
    steps: 10,
  });
  await page.mouse.up();
  return settledOverviewCamera(page);
}
async function label(page: Page) {
  const node = page.getByLabel('Overview display identity');
  await expect(node).toHaveText(/^Overview [a-f0-9]{6}$/);
  return (await node.textContent())!;
}
for (const fullscreen of [false, true]) {
  test(`Configuration recenters only the selected ${fullscreen ? 'fullscreen' : 'ordinary'} display without navigation or remount`, async ({
    context,
  }, info) => {
    // Two WebGL displays plus the prescribed 15s departed-peer expiry.
    test.setTimeout(90000);
    const fixture = await installOverviewWindowFixture(context);
    const selected = await context.newPage();
    await observeOverviewCamera(selected);
    let navigations = 0;
    selected.on('framenavigated', (frame) => {
      if (frame === selected.mainFrame()) navigations++;
    });
    await selected.goto('/overview');
    const selectedLabel = await label(selected);
    if (fullscreen) {
      await selected
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
      await expect
        .poll(() =>
          selected.evaluate(
            () => document.fullscreenElement === document.documentElement
          )
        )
        .toBe(true);
    }
    const automatic = await settledOverviewCamera(selected);
    const manual = await explore(selected);
    expect(manual.position).not.toEqual(automatic.position);
    const canvas = await selected
      .locator('.overview-globe canvas')
      .elementHandle();
    const plots = await selected.locator('.uplot').elementHandles();
    expect(plots).toHaveLength(5);
    const baselineNavigations = navigations;
    const other = await context.newPage();
    await observeOverviewCamera(other);
    await other.goto('/overview');
    const otherLabel = await label(other);
    const otherManual = await explore(other);
    const editing = await context.newPage();
    await editing.goto('/configuration');
    await editing.getByRole('tab', { name: 'Displays' }).click();
    await editing.bringToFront();
    const card = editing.getByRole('region', { name: 'Overview displays' });
    await expect(
      card.getByRole('option', { name: selectedLabel, exact: true })
    ).toHaveCount(1);
    await expect(
      card.getByRole('option', { name: otherLabel, exact: true })
    ).toHaveCount(1);
    await expect(
      card.getByRole('button', { name: 'Recenter view' })
    ).toBeDisabled();
    await card
      .getByLabel('Overview display')
      .selectOption({ label: selectedLabel });
    await card.getByRole('button', { name: 'Recenter view' }).click();
    await expect(card.getByRole('status')).toContainText('Recenter accepted');
    expectSameCamera(automatic, await settledOverviewCamera(selected));
    expectSameCamera(otherManual, await settledOverviewCamera(other));
    expect(navigations).toBe(baselineNavigations);
    expect(
      await canvas!.evaluate(
        (node) => node === document.querySelector('.overview-globe canvas')
      )
    ).toBe(true);
    for (let i = 0; i < plots.length; i++)
      expect(
        await plots[i].evaluate(
          (node, index) => node === document.querySelectorAll('.uplot')[index],
          i
        )
      ).toBe(true);
    expect(await retainedHistoryTimes(selected)).toContain(fixture.marker);
    expect(await selected.evaluate(() => !!document.fullscreenElement)).toBe(
      fullscreen
    );
    expect(await editing.evaluate(() => document.hasFocus())).toBe(true);
    expect(await editing.evaluate(() => !!document.fullscreenElement)).toBe(
      false
    );
    await selected.screenshot({
      path: info.outputPath('recentered-overview.png'),
    });
    await selected.close();
    await expect(
      card.getByRole('button', { name: 'Recenter view' })
    ).toBeDisabled({ timeout: 20000 });
    await expect(card.getByLabel('Overview display')).toHaveValue('');
    await expect(card).toContainText('Selected display disconnected');
  });
}
test('Open Overview discovers a separate display with recenter and no remote fullscreen', async ({
  context,
}) => {
  await installOverviewWindowFixture(context);
  const editing = await context.newPage();
  await editing.goto('/configuration');
  await editing.getByRole('tab', { name: 'Displays' }).click();
  const card = editing.getByRole('region', { name: 'Overview displays' });
  const popupPromise = context.waitForEvent('page');
  await card.getByRole('button', { name: 'Open Overview' }).click();
  const overview = await popupPromise;
  const displayLabel = await label(overview);
  expect(await overview.evaluate(() => window.opener === null)).toBe(true);
  await expect(card.getByLabel('Overview display')).toHaveValue(/.+/);
  await expect(
    card.getByRole('option', { name: displayLabel, exact: true })
  ).toHaveCount(1);
  await expect(
    card.getByRole('button', { name: 'Recenter view' })
  ).toBeEnabled();
  await expect(
    card.getByRole('button', { name: 'Fullscreen', exact: true })
  ).toHaveCount(0);
  await editing.bringToFront();
  await card.getByRole('button', { name: 'Recenter view' }).click();
  await expect(card.getByRole('status')).toContainText('Recenter accepted');
  expect(await editing.evaluate(() => document.hasFocus())).toBe(true);
  expect(await overview.evaluate(() => !!document.fullscreenElement)).toBe(
    false
  );
});
test('blocked Open Overview reports discovery guidance without navigating Configuration', async ({
  context,
}) => {
  await installOverviewWindowFixture(context);
  const editing = await context.newPage();
  await editing.addInitScript(() => {
    window.open = () => null;
  });
  await editing.goto('/configuration');
  await editing.getByRole('tab', { name: 'Displays' }).click();
  const card = editing.getByRole('region', { name: 'Overview displays' });
  await card.getByRole('button', { name: 'Open Overview' }).click();
  await expect(card.getByRole('alert')).toContainText('popup blocking', {
    timeout: 5000,
  });
  expect(new URL(editing.url()).pathname).toBe('/configuration');
});
