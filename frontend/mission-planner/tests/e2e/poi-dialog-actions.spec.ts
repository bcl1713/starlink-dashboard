import { test, expect } from '@playwright/test';

async function mockPOIApis(page: import('@playwright/test').Page) {
  await page.route('**/api/pois**', async (route) => {
    await route.fulfill({ json: { pois: [], total: 0 } });
  });
  await page.route('**/api/routes**', async (route) => {
    await route.fulfill({ json: { routes: [], total: 0 } });
  });
  await page.route('**/api/v2/missions**', async (route) => {
    await route.fulfill({ json: [] });
  });
}

async function expectActionsVisible(page: import('@playwright/test').Page) {
  const dialog = page.getByRole('dialog');
  const cancel = page.getByRole('button', { name: 'Cancel' });
  const save = page.getByRole('button', { name: 'Save POI' });

  await expect(dialog).toBeVisible();
  await expect(cancel).toBeVisible();
  await expect(save).toBeVisible();

  const [dialogBox, cancelBox, saveBox] = await Promise.all([
    dialog.boundingBox(),
    cancel.boundingBox(),
    save.boundingBox(),
  ]);

  expect(dialogBox).not.toBeNull();
  expect(cancelBox).not.toBeNull();
  expect(saveBox).not.toBeNull();

  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();

  for (const action of [cancelBox!, saveBox!]) {
    expect(action.y).toBeGreaterThanOrEqual(dialogBox!.y);
    expect(action.y + action.height).toBeLessThanOrEqual(
      dialogBox!.y + dialogBox!.height
    );
    expect(action.y + action.height).toBeLessThanOrEqual(viewport!.height);
  }
}

test.describe('POI dialog actions', () => {
  test('keeps Create POI actions visible at short desktop height', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 577 });
    await mockPOIApis(page);

    await page.goto('/pois');
    await page.getByRole('button', { name: 'Create POI' }).click();

    await expectActionsVisible(page);
  });

  test('keeps Create POI actions visible on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockPOIApis(page);

    await page.goto('/pois');
    await page.getByRole('button', { name: 'Create POI' }).click();

    await expectActionsVisible(page);
  });
});
