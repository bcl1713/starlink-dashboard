import {
  expect,
  type Locator,
  type Page,
  type Response,
} from '@playwright/test';

export async function waitForGlobeVisualReady(
  page: Page,
  textureResponse: Promise<Response>
): Promise<Locator> {
  const canvas = page.locator('canvas').first();

  await expect(textureResponse).resolves.toBeTruthy();
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box?.width).toBeGreaterThan(0);
  expect(box?.height).toBeGreaterThan(0);
  await page.evaluate(
    () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  );

  return canvas;
}
