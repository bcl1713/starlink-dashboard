#!/usr/bin/env node
/** Product-only V2 visible journey adapter.
 *
 * The adapter attaches to the platform-owned browser session and returns bounded
 * observations/artifact bytes on stdout. The platform is the sole evidence writer.
 */
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { createInflate } from 'node:zlib';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(resolve(ROOT, 'frontend/mission-planner/package.json'));
const { chromium } = require('@playwright/test');
const LIMIT = 50;

function parse(argv) {
  const values = {};
  for (let index = 2; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith('--') || !value || value.startsWith('--')) throw new Error(`invalid argument: ${key}`);
    values[key.slice(2)] = value;
  }
  for (const required of ['session', 'origin', 'kml']) {
    if (!values[required]) throw new Error(`missing --${required}`);
  }
  return values;
}

async function pngDimensions(png) {
  if (png.length > 12 * 1024 * 1024 || !png.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) throw new Error('screenshot is not a decoded PNG');
  let offset = 8; let width = 0; let height = 0; let ihdr = false; let iend = false; const idat = [];
  while (offset < png.length) {
    if (offset + 12 > png.length) throw new Error('screenshot is not a decoded PNG');
    const length = png.readUInt32BE(offset); const end = offset + 12 + length;
    if (end > png.length) throw new Error('screenshot is not a decoded PNG');
    const kind = png.toString('ascii', offset + 4, offset + 8); const data = png.subarray(offset + 8, offset + 8 + length);
    if (kind === 'IHDR') {
      if (ihdr || length !== 13 || data.readUInt32BE(0) !== 1920 || data.readUInt32BE(4) !== 1080 || data[8] !== 8 || data[9] !== 6 || data[10] || data[11] || data[12]) throw new Error('screenshot is not a decoded PNG');
      width = 1920; height = 1080; ihdr = true;
    } else if (kind === 'IDAT') {
      if (!ihdr || iend) throw new Error('screenshot is not a decoded PNG');
      idat.push(data);
    } else if (kind === 'IEND') {
      if (!ihdr || iend || length || end !== png.length) throw new Error('screenshot is not a decoded PNG');
      iend = true;
    }
    offset = end;
  }
  const expected = height * (width * 4 + 1);
  if (!ihdr || !iend || !idat.length) throw new Error('screenshot is not a decoded PNG');
  const inflater = createInflate({ chunkSize: 64 * 1024 }); const chunks = []; let total = 0;
  try {
    await new Promise((resolve, reject) => {
      inflater.on('data', (chunk) => { total += chunk.length; if (total > expected) { inflater.destroy(); reject(new Error('oversize')); } else chunks.push(chunk); });
      inflater.once('error', reject); inflater.once('end', resolve); inflater.end(Buffer.concat(idat));
    });
  } catch { inflater.destroy(); throw new Error('screenshot is not a decoded PNG'); }
  const decoded = Buffer.concat(chunks, total);
  if (total !== expected || decoded.some((value, index) => index % (width * 4 + 1) === 0 && value > 4)) throw new Error('screenshot is not a decoded PNG');
  return { width, height };
}

async function settleAnimations(page) {
  await page.evaluate(async () => {
    await Promise.all(document.getAnimations({ subtree: true }).map((animation) => animation.finished.catch(() => undefined)));
  });
}

async function viewportArtifact(page, name) {
  const metrics = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    visualWidth: window.visualViewport?.width,
    visualHeight: window.visualViewport?.height,
    dpr: window.devicePixelRatio,
  }));
  const png = await page.screenshot({ type: 'png' });
  const raster = await pngDimensions(png);
  if (metrics.innerWidth !== 1920 || metrics.innerHeight !== 1080 || metrics.visualWidth !== 1920 || metrics.visualHeight !== 1080 || metrics.dpr !== 1 || raster.width !== 1920 || raster.height !== 1080) throw new Error(`exact viewport mismatch: ${JSON.stringify({ ...metrics, raster })}`);
  return {
    [`${name}-metrics.json`]: Buffer.from(JSON.stringify({ ...metrics, raster })).toString('base64'),
    [`${name}.png`]: png.toString('base64'),
  };
}

function scopedLifecycle(page) {
  const records = [];
  const requests = new Map();
  let frameId = '';
  let loaderId = '';
  let session;
  let overflow = false;
  const add = (record) => {
    if (records.length >= LIMIT) { overflow = true; return; }
    records.push(record);
  };
  return {
    async arm() {
      session = await page.context().newCDPSession(page);
      await session.send('Page.enable');
      await session.send('Network.enable');
      const tree = await session.send('Page.getFrameTree');
      frameId = tree.frameTree.frame.id;
      session.on('Page.frameNavigated', ({ frame }) => {
        if (frame.id === frameId && frame.loaderId) loaderId = frame.loaderId;
      });
      session.on('Network.requestWillBeSent', (event) => {
        if (event.frameId !== frameId || event.loaderId !== loaderId || !new URL(event.request.url).pathname.startsWith('/api/v2/')) return;
        requests.set(event.requestId, { id: event.requestId, path: new URL(event.request.url).pathname, startedAt: event.timestamp, loaderId: event.loaderId, outcome: 'pending' });
      });
      session.on('Network.responseReceived', (event) => {
        const record = requests.get(event.requestId);
        if (record) record.status = event.response.status;
      });
      session.on('Network.loadingFinished', (event) => {
        const record = requests.get(event.requestId);
        if (record) {
          Object.assign(record, { outcome: record.status === 200 ? 'finished' : 'http_failed', finishedAt: event.timestamp });
          add({ ...record });
        }
      });
      session.on('Network.loadingFailed', (event) => {
        const record = requests.get(event.requestId);
        if (record) {
          Object.assign(record, { outcome: 'failed', error: event.errorText, finishedAt: event.timestamp });
          add({ ...record });
        }
      });
    },
    assertHealthy() {
      const pending = [...requests.values()].filter((record) => record.outcome === 'pending');
      if (overflow) throw new Error('scoped V2 navigation lifecycle coverage gap: record budget exceeded');
      if (pending.length || !records.length || records.some((record) => record.outcome !== 'finished')) throw new Error('scoped V2 navigation lifecycle is incomplete or failed');
      const settled = records.filter((record) => record.outcome === 'finished');
      const scheduled = settled.slice(1);
      if (scheduled.length < 1 || scheduled.some((record, index) => record.startedAt <= settled[index].startedAt)) throw new Error('scoped V2 polling cadence coverage gap');
    },
    observation() {
      const settled = records.filter((record) => record.outcome === 'finished');
      const scheduled = settled.slice(1);
      return { frameId, loaderId, polling: { navigationScoped: true, minimumScheduledRequests: 1, observedScheduledRequests: scheduled.length }, requests: records, overflow };
    },
    async close() {
      await session?.detach().catch(() => {});
    },
  };
}

async function assertSemanticOverview(page) {
  const legend = page.getByLabel('Globe legend');
  const poiPanel = page.getByLabel('Upcoming POIs');
  await legend.waitFor();
  await poiPanel.waitFor();
  await settleAnimations(page);
  const routeName = legend.getByText('V2 Acceptance Route KAAA-KBBB', { exact: true });
  const firstPoi = poiPanel.getByText('KAAA', { exact: true });
  const poiRows = poiPanel.getByRole('row');
  if (!(await routeName.isVisible()) || !(await firstPoi.isVisible()) || (await poiRows.count()) < 2) throw new Error('active V2 route, context, or generated POIs are not visibly bound to the accepted KML');
  return { routeName: await routeName.innerText(), firstPoi: await firstPoi.innerText(), poiRows: await poiRows.count() };
}

export async function runV2MissionRetirement({ page, origin, kmlPath }) {
  const missionName = `V2 acceptance ${Date.now()}`;
  const lifecycle = scopedLifecycle(page);
  await lifecycle.arm();
  try {
    await page.goto(origin, { waitUntil: 'networkidle' });
    const pre = await viewportArtifact(page, 'journey-pre');
    await page.getByRole('button', { name: 'Create New Mission' }).click();
    await page.getByLabel('Mission Name').fill(missionName);
    await page.getByRole('button', { name: 'Create Mission', exact: true }).click();
    await page.getByRole('button', { name: 'Add Leg', exact: true }).click();
    await page.getByRole('button', { name: 'Upload KML', exact: true }).click();
    await page.locator('input[type=file]').setInputFiles(kmlPath);
    await page.getByRole('button', { name: 'Add Leg', exact: true }).click();
    const activation = page.waitForResponse((response) => new URL(response.url()).pathname.includes('/activate') && response.status() === 200);
    await page.getByRole('button', { name: 'Activate', exact: true }).click();
    await activation;
    await page.getByRole('link', { name: 'Overview', exact: true }).click();
    const visible = await assertSemanticOverview(page);
    const post = await viewportArtifact(page, 'journey-post');
    lifecycle.assertHealthy();
    return { missionName, activation: 'browser-observed-200', lifecycle: lifecycle.observation(), visible, artifacts: { ...pre, ...post } };
  } finally {
    await lifecycle.close();
  }
}

async function main() {
  const values = parse(process.argv);
  const browser = await chromium.connectOverCDP(values.session);
  const context = browser.contexts()[0];
  if (!context) throw new Error('platform-supplied browser session has no context');
  const page = context.pages()[0] ?? await context.newPage();
  const result = await runV2MissionRetirement({ page, origin: values.origin, kmlPath: values.kml });
  process.stdout.write(`${JSON.stringify({ status: 'passed', ...result })}\n`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exitCode = 1;
  });
}
