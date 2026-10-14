import { defineConfig } from '@playwright/test';
import { accessSync, constants } from 'node:fs';
const browser = process.env.GFS_HARDWARE_BROWSER;
if (!browser) throw Error('H1 unverified: GFS_HARDWARE_BROWSER required');
accessSync(browser, constants.X_OK);
for (const kind of ['BASELINE', 'CANDIDATE']) {
  const value = process.env[`GFS_HARDWARE_${kind}_URL`];
  const url = new URL(value ?? '');
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.pathname !== '/' ||
    url.search ||
    url.hash
  )
    throw Error('H1 requires an isolated HTTP(S) origin');
  if (!/^[a-f0-9]{40}$/.test(process.env[`GFS_HARDWARE_${kind}_SHA`] ?? ''))
    throw Error('H1 requires exact baseline/candidate SHAs');
}
if (
  !process.env.GFS_HARDWARE_OUTPUT_DIR ||
  !process.env.GFS_HARDWARE_TARGET ||
  !process.env.GFS_HARDWARE_SOURCE_MANIFEST
)
  throw Error(
    'H1 unverified: output, named hardware target and pinned source manifest required'
  );
accessSync(process.env.GFS_HARDWARE_SOURCE_MANIFEST, constants.R_OK);
if (
  new URL(process.env.GFS_HARDWARE_BASELINE_URL!).origin ===
    new URL(process.env.GFS_HARDWARE_CANDIDATE_URL!).origin ||
  process.env.GFS_HARDWARE_BASELINE_SHA ===
    process.env.GFS_HARDWARE_CANDIDATE_SHA
)
  throw Error('H1 requires distinct isolated baseline/candidate builds');
if (
  process.env.GFS_HARDWARE_BASELINE_SHA !==
  'aef333d46a30c131f61a5de3bfe318c6a7618f43'
)
  throw Error('H1 baseline must be the approved pre-change dev SHA');
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'gfs-wind-performance.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 1800000,
  reporter: 'line',
  outputDir: process.env.GFS_HARDWARE_OUTPUT_DIR,
  use: {
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    headless: false,
    launchOptions: { executablePath: browser },
  },
});
