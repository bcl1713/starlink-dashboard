import { chromium } from '@playwright/test';
import { spawn, execFileSync } from 'node:child_process';
import {
  mkdirSync,
  writeFileSync,
  openSync,
  closeSync,
  readFileSync,
} from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const sha = execFileSync('git', ['rev-parse', 'HEAD'], {
  cwd: frontend,
  encoding: 'utf8',
}).trim();
const evidence = resolve(
  frontend,
  process.env.BLOOM_EVIDENCE ?? `test-results/bloom/${sha}`
);
const serverRoot = process.env.BLOOM_PACKAGE_DIR ?? frontend;
const buildStamp = JSON.parse(
  readFileSync(resolve(serverRoot, 'dist-bloom/build.json'), 'utf8')
);
if (process.env.BLOOM_REQUIRE_CLEAN === '1') {
  assert.equal(buildStamp.sourceSha, sha);
  assert.equal(buildStamp.dirty, false);
}
mkdirSync(evidence, { recursive: true });
const port = process.env.BLOOM_PORT ?? '4290',
  origin = `http://127.0.0.1:${port}`;
const ownership = {
  task: 'issue429-bloom-smoke',
  sha,
  server: null,
  browser: null,
  composeProjects: [],
  privateVolumes: [],
  temporaryPaths: [evidence],
};
const record = () =>
  writeFileSync(
    resolve(evidence, 'ownership.json'),
    JSON.stringify(ownership, null, 2)
  );
record();
let child, browserServer, browser, context, page;
let cleaning;
async function cleanup() {
  if (cleaning) return cleaning;
  cleaning = (async () => {
    await context?.close().catch(() => {});
    await browser?.close().catch(() => {});
    await browserServer?.close().catch(() => {});
    if (child && child.exitCode === null) {
      child.kill('SIGTERM');
      await Promise.race([
        new Promise((r) => child.once('exit', r)),
        new Promise((r) => setTimeout(r, 3000)),
      ]);
      if (child.exitCode === null) {
        process.kill(-child.pid, 'SIGKILL');
        await new Promise((r) => child.once('exit', r));
      }
    }
    ownership.cleanedAt = new Date().toISOString();
    record();
  })();
  return cleaning;
}
for (const signal of ['SIGTERM', 'SIGINT'])
  process.on(signal, () => {
    void cleanup().then(() => process.exit(130));
  });
const frames = async (page, count = 35) =>
  page.evaluate(
    (n) =>
      new Promise((done) => {
        function step() {
          if (--n <= 0) done();
          else requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      }),
    count
  );
const snapshot = async (page) =>
  JSON.parse(await page.locator('canvas').getAttribute('data-frame'));
const results = {
  sha,
  buildStamp,
  kind: 'cloud software-renderer smoke; no physical-laptop performance claim',
  errors: [],
  requests: [],
  external: [],
  checks: [],
};
try {
  const log = openSync(resolve(evidence, 'server.log'), 'w');
  child = spawn(process.execPath, ['scripts/bloom-server.mjs'], {
    cwd: serverRoot,
    env: { ...process.env, BLOOM_PORT: port },
    stdio: ['ignore', log, log],
    detached: true,
  });
  closeSync(log);
  ownership.server = { pid: child.pid, pgid: child.pid, origin };
  record();
  for (let i = 0; i < 100; i++) {
    if (child.exitCode !== null)
      throw new Error('Local server failed; see server.log');
    try {
      const response = await fetch(origin);
      if (response.ok) break;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  assert.equal((await fetch(`${origin}/api/status`)).status, 403);
  assert.equal(
    (await fetch(`${origin}/api/missions`, { method: 'POST' })).status,
    405
  );
  assert.match(
    (await fetch(origin)).headers.get('content-security-policy'),
    /connect-src 'none'/
  );
  results.checks.push(
    'static server refuses API reads/mutations and sends restrictive CSP'
  );
  browserServer = await chromium.launchServer({
    headless: true,
    executablePath: process.env.BLOOM_CHROMIUM_EXECUTABLE,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  ownership.browser = {
    pid: browserServer.process().pid,
    pgid: Number(
      execFileSync(
        'ps',
        ['-o', 'pgid=', '-p', String(browserServer.process().pid)],
        { encoding: 'utf8' }
      ).trim()
    ),
    renderer: 'explicit SwiftShader smoke',
  };
  record();
  browser = await chromium.connect(browserServer.wsEndpoint());
  context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    serviceWorkers: 'block',
  });
  await context.route('**/*', (route) => {
    const url = new URL(route.request().url());
    results.requests.push(url.pathname);
    if (
      url.origin === origin &&
      ['GET', 'HEAD'].includes(route.request().method()) &&
      !url.pathname.startsWith('/api')
    )
      return route.continue();
    results.external.push(url.href);
    return route.abort();
  });
  page = await context.newPage();
  page.on('pageerror', (error) => results.errors.push(error.message));
  await page.goto(origin, { waitUntil: 'networkidle' });
  await page
    .locator('[data-overview-label-id]')
    .first()
    .waitFor({ state: 'attached' });
  await frames(page, 90);
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await frames(page);
  const a = await snapshot(page);
  results.a = a;
  await page.screenshot({ path: resolve(evidence, 'A-default.png') });
  const mode = page.getByLabel('Mode', { exact: true });
  await mode.selectOption('bloom');
  await frames(page);
  const b = await snapshot(page);
  results.b = b;
  assert.deepEqual(a.camera, b.camera);
  assert.deepEqual(a.drawingBuffer, b.drawingBuffer);
  assert.ok(Math.max(...b.dimensions.bright) <= 480);
  await page.screenshot({ path: resolve(evidence, 'B-default.png') });
  await mode.selectOption('output');
  await frames(page);
  results.output = await snapshot(page);
  await mode.selectOption('current');
  await frames(page);
  const restored = await snapshot(page);
  assert.deepEqual(restored.resources, a.resources);
  await page.screenshot({ path: resolve(evidence, 'A-restored.png') });
  for (let i = 0; i < 4; i++) {
    await mode.selectOption('bloom');
    await frames(page);
    await mode.selectOption('current');
    await frames(page);
  }
  results.afterSwitches = await snapshot(page);
  assert.deepEqual(results.afterSwitches.resources, a.resources);
  results.checks.push(
    'A/B/output preserve camera and drawing buffer; four more A/B cycles restore baseline resource counts'
  );
  await page.getByLabel('Full overlays', { exact: true }).check();
  await frames(page);
  await page.screenshot({ path: resolve(evidence, 'A-full.png') });
  await mode.selectOption('bloom');
  await frames(page);
  await page.screenshot({ path: resolve(evidence, 'B-full.png') });
  await page.getByLabel('Bloom bound', { exact: true }).selectOption('480');
  await frames(page);
  const small = await snapshot(page);
  assert.ok(Math.max(...small.dimensions.bright) <= 240);
  await page.setViewportSize({ width: 1000, height: 900 });
  await frames(page);
  results.resized = await snapshot(page);
  assert.ok(Math.max(...results.resized.dimensions.bright) <= 240);
  results.checks.push(
    'resize and bloom bound change keep bloom targets independently bounded'
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  const blocked = await page.evaluate(async () => {
    const checks = [];
    for (const [url, init] of [
      ['/api/status', {}],
      ['/api/missions', { method: 'POST' }],
      ['https://example.com/', {}],
    ]) {
      try {
        await fetch(url, init);
        checks.push(false);
      } catch {
        checks.push(true);
      }
    }
    for (const name of ['WebSocket', 'XMLHttpRequest', 'EventSource']) {
      try {
        new window[name]('ws://127.0.0.1:1');
        checks.push(false);
      } catch {
        checks.push(true);
      }
    }
    return checks;
  });
  assert.ok(blocked.every(Boolean));
  results.checks.push(
    'standalone runtime blocks API fetch, mutations, external fetch, XHR, WebSocket and EventSource'
  );
  await frames(page);
  await page.getByLabel('Samples', { exact: true }).selectOption('60');
  await page
    .getByRole('button', { name: 'Measure output / B bounds', exact: true })
    .click();
  await page.setViewportSize({ width: 1910, height: 1080 });
  await page
    .locator('footer [role=status]')
    .filter({ hasText: 'Capture cancelled: viewport/DPR changed' })
    .waitFor();
  results.checks.push(
    'viewport changes during warm-up cancel the capture series'
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  await frames(page);
  await page
    .getByRole('button', { name: 'Measure output / B bounds', exact: true })
    .click();
  await page
    .getByRole('status')
    .filter({ hasText: 'Capture series complete' })
    .waitFor({ timeout: 240000 });
  console.log('Diagnostic timing series complete');
  const pendingDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export JSON', exact: true }).click();
  const download = await pendingDownload;
  await download.saveAs(resolve(evidence, 'diagnostic-runs.json'));
  results.checks.push(
    'production-built diagnostic/output and bounded-B timing captures complete and export JSON (software smoke only)'
  );
  const csvDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV', exact: true }).click();
  await (await csvDownload).saveAs(resolve(evidence, 'diagnostic-runs.csv'));
  results.browserVersion = browser.version();
  assert.deepEqual(results.errors, []);
  assert.deepEqual(results.external, []);
  results.checks.push(
    'fresh browser profile cold-loads all local assets/worker with external network denied and no scene fixtures intercepted'
  );
  writeFileSync(
    resolve(evidence, 'smoke.json'),
    JSON.stringify(results, null, 2)
  );
  console.log(JSON.stringify({ evidence, checks: results.checks }, null, 2));
} catch (error) {
  if (page) {
    results.status = await page
      .locator('footer [role=status]')
      .textContent()
      .catch(() => null);
    await page
      .screenshot({ path: resolve(evidence, 'failure.png') })
      .catch(() => {});
  }
  results.failure = String(error);
  writeFileSync(
    resolve(evidence, 'smoke.json'),
    JSON.stringify(results, null, 2)
  );
  throw error;
} finally {
  await cleanup();
}
