import { buildSync } from 'esbuild';
import type { Page } from '@playwright/test';
import { fileURLToPath } from 'node:url';
export async function installProof(
  page: Page,
  descriptorURL: string
): Promise<void> {
  const ready = await page.evaluate(() =>
    Boolean((window as unknown as { aviationProof?: unknown }).aviationProof)
  );
  if (!ready) {
    const built = buildSync({
      entryPoints: [fileURLToPath(new URL('./runtime.ts', import.meta.url))],
      bundle: true,
      write: false,
      format: 'iife',
      define: { 'process.env.NODE_ENV': '"production"' },
    });
    await page.addScriptTag({ content: built.outputFiles[0].text });
  }
  await page.evaluate(async (url) => {
    await (
      window as unknown as {
        aviationProof: { install: (u: string) => Promise<unknown> };
      }
    ).aviationProof.install(url);
  }, descriptorURL);
}
export async function restoreProof(page: Page): Promise<void> {
  await page.evaluate(async () => {
    await (
      window as unknown as { aviationProof: { dispose: () => Promise<void> } }
    ).aviationProof.dispose();
  });
}
export async function sampleProof(
  page: Page,
  latitude: number,
  longitude: number
): Promise<{ value: number | null; mask: number }> {
  return page.evaluate(
    ([lat, lon]) =>
      (
        window as unknown as {
          aviationProof: {
            sample: (
              a: number,
              b: number
            ) => { value: number | null; mask: number };
          };
        }
      ).aviationProof.sample(lat, lon),
    [latitude, longitude]
  );
}
