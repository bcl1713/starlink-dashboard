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
  const canvas = page.locator('.overview-globe canvas');

  await expect(textureResponse).resolves.toBeTruthy();
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box?.width).toBeGreaterThan(0);
  expect(box?.height).toBeGreaterThan(0);
  await expect
    .poll(() =>
      canvas.evaluate((node) => {
        const gl = (node as HTMLCanvasElement).getContext('webgl2');
        return Boolean(
          gl && gl.drawingBufferWidth > 0 && gl.drawingBufferHeight > 0
        );
      })
    )
    .toBe(true);
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
      )
  );

  // Read the composited canvas, not WebGL's non-preserved drawing buffer.
  await expect
    .poll(
      async () => {
        const png = await canvas.screenshot();
        return page.evaluate(
          async (bytes) => {
            const bitmap = await createImageBitmap(
              new Blob([new Uint8Array(bytes)], { type: 'image/png' })
            );
            const sample = document.createElement('canvas');
            sample.width = sample.height = 1;
            const context = sample.getContext('2d')!;
            context.drawImage(
              bitmap,
              Math.floor(bitmap.width / 2),
              Math.floor(bitmap.height / 2),
              1,
              1,
              0,
              0,
              1,
              1
            );
            bitmap.close();
            const pixel = context.getImageData(0, 0, 1, 1).data;
            return pixel[0] > 10 || pixel[1] > 10 || pixel[2] > 10;
          },
          [...png]
        );
      },
      { timeout: 10_000 }
    )
    .toBe(true);

  return canvas;
}
