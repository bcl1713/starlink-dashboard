import {
  expect,
  type Locator,
  type Page,
  type Response,
} from '@playwright/test';

export async function waitForGlobeVisualReady(
  page: Page,
  textureResponse: Promise<Response>,
  samplePoint = { x: 0.5, y: 0.5 }
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
        const current = await canvas.boundingBox();
        if (!current) return false;
        // Capture only the inspected pixel. Full-size screenshots here stall
        // software WebGL while serializing bytes that this check discards.
        const png = await page.screenshot({
          clip: {
            x: current.x + current.width * samplePoint.x,
            y: current.y + current.height * samplePoint.y,
            width: 1,
            height: 1,
          },
          scale: 'css',
        });
        return page.evaluate(
          async ({ bytes, point }) => {
            const bitmap = await createImageBitmap(
              new Blob([new Uint8Array(bytes)], { type: 'image/png' })
            );
            const sample = document.createElement('canvas');
            sample.width = sample.height = 1;
            const context = sample.getContext('2d')!;
            context.drawImage(
              bitmap,
              Math.floor(bitmap.width * point.x),
              Math.floor(bitmap.height * point.y),
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
          { bytes: [...png], point: samplePoint }
        );
      },
      { timeout: 10_000 }
    )
    .toBe(true);

  return canvas;
}
