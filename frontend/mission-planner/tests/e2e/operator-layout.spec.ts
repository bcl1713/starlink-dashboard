import { expect, test } from '@playwright/test';

test('mobile tabs keep the same header and awareness layout', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/operator?workspace=1&view=communications');
  await expect(page.locator('.ws-mode')).toContainText('Simulation');
  await expect(page.locator('.ws-replay-note')).toBeAttached();
  const geometry = () =>
    page.evaluate(() =>
      [
        '.ws-header',
        '.ws-mission-chooser',
        '.ws-header-actions',
        '.ws-awareness',
        '.ws-navigation',
      ].map((selector) => {
        const rect = document.querySelector(selector)!.getBoundingClientRect();
        return {
          selector,
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        };
      })
    );
  const expected = await geometry();
  for (const name of ['Transport', 'Issues', 'Notes', 'History', 'Now']) {
    await page
      .getByRole('navigation', { name: 'Operator workspace' })
      .getByRole('button', { name, exact: true })
      .click();
    await expect(page.locator('main')).toHaveAttribute(
      'data-view',
      name.toLowerCase()
    );
    expect(await geometry(), name).toEqual(expected);
  }
});

for (const viewport of [
  { width: 390, height: 844 },
  { width: 320, height: 568 },
  { width: 844, height: 390 },
]) {
  test(`mobile Tools stays inside ${viewport.width}×${viewport.height} and opens its controls`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.goto('/operator?workspace=1&view=issues');
    await expect(page.locator('.ws-mode')).toContainText('Simulation');
    await page.getByRole('button', { name: 'Tools', exact: true }).click();
    const menu = page.locator('#operator-tool-controls');
    const bounds = await menu.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
    await page
      .getByRole('button', { name: 'Display tools', exact: true })
      .click();
    await expect(
      page.getByRole('dialog', { name: 'Display tools' })
    ).toBeVisible();
    await page
      .getByRole('dialog', { name: 'Display tools' })
      .getByRole('button', { name: 'Close', exact: true })
      .click();
    await page.getByRole('button', { name: 'Tools', exact: true }).click();
    await page
      .getByRole('button', { name: 'Local alerts', exact: true })
      .click();
    await expect(page.getByLabel('In-app cues')).toBeVisible();
    await page
      .getByRole('button', { name: 'Close settings', exact: true })
      .click();
    await page
      .getByRole('button', { name: 'Source status', exact: true })
      .click();
    await expect(
      page.getByRole('dialog', { name: 'Source status' })
    ).toBeVisible();
  });
}

test('desktop wheel scrolling works over the lower content and unused sidebar space', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/operator?workspace=1&view=communications');
  await expect(page.locator('.ws-mode')).toContainText('Simulation');
  // Add only DOM content to guarantee overflow without saving test records.
  await page.locator('.ws-body').evaluate((element) => {
    const marker = document.createElement('p');
    marker.dataset.layoutScrollMarker = 'true';
    marker.textContent = 'Scroll position probe';
    element.prepend(marker);
    for (let index = 0; index < 20; index++) {
      const card = document.createElement('article');
      card.className = 'ws-record';
      card.style.minHeight = '180px';
      card.textContent = `Scheduled call layout probe ${index + 1}`;
      element.append(card);
    }
  });
  const marker = page.locator('[data-layout-scroll-marker]');
  for (const [x, y] of [
    [1100, 400],
    [1100, 700],
    [1100, 950],
    [150, 950],
  ]) {
    const before = (await marker.boundingBox())!.y;
    await page.mouse.move(x, y);
    await page.mouse.wheel(0, 300);
    await expect
      .poll(async () => (await marker.boundingBox())!.y)
      .toBeLessThan(before - 100);
  }
});
