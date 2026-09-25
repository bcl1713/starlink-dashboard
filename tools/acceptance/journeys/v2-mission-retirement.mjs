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

function option(argv, name) {
  const index = argv.indexOf(`--${name}`);
  return index >= 0 ? argv[index + 1] : undefined;
}

const repositoryRoot = option(process.argv, 'repository-root');
const ROOT = repositoryRoot
  ? resolve(repositoryRoot)
  : resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(resolve(ROOT, 'frontend/mission-planner/package.json'));
const { chromium } = require('@playwright/test');
const LIMIT = 50;
const POLLING_ENDPOINT = '/api/overview-history';
const POLLING_PERIOD_MS = 5_000;
const POLLING_MIN_CADENCE_MS = 4_500;
const POLLING_MAX_CADENCE_MS = 7_500;
const SEMANTIC_READINESS_TIMEOUT_MS = 10_000;

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

function pngCrc32(chunk) {
  let crc = 0xffffffff;
  for (const value of chunk) {
    crc ^= value;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

async function pngDimensions(png) {
  if (png.length > 12 * 1024 * 1024 || !png.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) throw new Error('screenshot is not a decoded PNG');
  let offset = 8; let width = 0; let height = 0; let channels = 0; let ihdr = false; let iend = false; let plte = false; let idatStarted = false; let idatEnded = false; const idat = [];
  while (offset < png.length) {
    if (offset + 12 > png.length) throw new Error('screenshot is not a decoded PNG');
    const length = png.readUInt32BE(offset); const end = offset + 12 + length;
    if (end > png.length) throw new Error('screenshot is not a decoded PNG');
    const kind = png.toString('ascii', offset + 4, offset + 8); const data = png.subarray(offset + 8, offset + 8 + length);
    if (pngCrc32(png.subarray(offset + 4, offset + 8 + length)) !== png.readUInt32BE(offset + 8 + length)) throw new Error('screenshot is not a decoded PNG');
    if (!ihdr && kind !== 'IHDR') throw new Error('screenshot is not a decoded PNG');
    if (idatStarted && kind !== 'IDAT' && kind !== 'IEND') idatEnded = true;
    if (kind === 'IHDR') {
      if (ihdr || offset !== 8 || length !== 13 || data.readUInt32BE(0) !== 1920 || data.readUInt32BE(4) !== 1080 || data[8] !== 8 || ![2, 6].includes(data[9]) || data[10] || data[11] || data[12]) throw new Error('screenshot is not a decoded PNG');
      width = 1920; height = 1080; channels = data[9] === 2 ? 3 : 4; ihdr = true;
    } else if (kind === 'PLTE') {
      if (plte || idatStarted || ![3, 4].includes(channels) || !length || length > 768 || length % 3) throw new Error('screenshot is not a decoded PNG');
      plte = true;
    } else if (kind === 'IDAT') {
      if (iend || idatEnded) throw new Error('screenshot is not a decoded PNG');
      idatStarted = true; idat.push(data);
    } else if (kind === 'IEND') {
      if (iend || !idatStarted || length || end !== png.length) throw new Error('screenshot is not a decoded PNG');
      iend = true;
    } else if ((png[offset + 4] & 0x20) === 0) throw new Error('screenshot is not a decoded PNG');
    offset = end;
  }
  const expected = height * (width * channels + 1);
  if (!ihdr || !iend || !idat.length) throw new Error('screenshot is not a decoded PNG');
  const inflater = createInflate({ chunkSize: 64 * 1024 }); const chunks = []; let total = 0;
  try {
    await new Promise((resolve, reject) => {
      inflater.on('data', (chunk) => { total += chunk.length; if (total > expected) { inflater.destroy(); reject(new Error('oversize')); } else chunks.push(chunk); });
      inflater.once('error', reject); inflater.once('end', resolve); inflater.end(Buffer.concat(idat));
    });
  } catch { inflater.destroy(); throw new Error('screenshot is not a decoded PNG'); }
  const decoded = Buffer.concat(chunks, total);
  if (total !== expected || decoded.some((value, index) => index % (width * channels + 1) === 0 && value > 4)) throw new Error('screenshot is not a decoded PNG');
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
  let pollingWindow;
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
        if (event.frameId !== frameId || event.loaderId !== loaderId || new URL(event.request.url).pathname !== POLLING_ENDPOINT) return;
        requests.set(event.requestId, { id: event.requestId, path: new URL(event.request.url).pathname, startedAt: event.timestamp, loaderId: event.loaderId, outcome: 'pending' });
      });
      session.on('Network.responseReceived', (event) => {
        const record = requests.get(event.requestId);
        if (record) record.status = event.response.status;
      });
      session.on('Network.loadingFinished', (event) => {
        const record = requests.get(event.requestId);
        if (record) {
          Object.assign(record, { outcome: record.status === 200 ? 'finished' : 'http_failed', finishedAt: event.timestamp, cycle: pollingWindow ? 'scheduled' : 'bootstrap' });
          add({ ...record });
        }
      });
      session.on('Network.loadingFailed', (event) => {
        const record = requests.get(event.requestId);
        if (record) {
          Object.assign(record, { outcome: 'failed', error: event.errorText, finishedAt: event.timestamp, cycle: pollingWindow ? 'scheduled' : 'bootstrap' });
          add({ ...record });
        }
      });
    },
    async beginPollingWindow() {
      const deadline = Date.now() + POLLING_MAX_CADENCE_MS;
      while (!records.some((record) => record.cycle === 'bootstrap' && record.outcome === 'finished')) {
        if (Date.now() >= deadline) throw new Error('scoped V2 polling bootstrap coverage gap');
        await page.waitForTimeout(50);
      }
      const bootstrap = records.find((record) => record.cycle === 'bootstrap' && record.outcome === 'finished');
      pollingWindow = { windowStart: bootstrap.finishedAt, windowEnd: 0 };
    },
    async waitForScheduledPoll() {
      const deadline = Date.now() + POLLING_MAX_CADENCE_MS;
      while (!records.some((record) => record.cycle === 'scheduled' && record.outcome === 'finished')) {
        if (Date.now() >= deadline) throw new Error('scoped V2 scheduled polling window coverage gap');
        await page.waitForTimeout(50);
      }
      const scheduled = records.filter((record) => record.cycle === 'scheduled' && record.outcome === 'finished');
      pollingWindow.windowEnd = scheduled.at(-1).finishedAt;
    },
    assertHealthy() {
      const pending = [...requests.values()].filter((record) => record.outcome === 'pending');
      if (overflow) throw new Error('scoped V2 navigation lifecycle coverage gap: record budget exceeded');
      if (pending.length || !records.length || records.some((record) => record.outcome !== 'finished') || !pollingWindow?.windowEnd) throw new Error('scoped V2 navigation lifecycle is incomplete or failed');
      const bootstrap = records.filter((record) => record.cycle === 'bootstrap');
      const scheduled = records.filter((record) => record.cycle === 'scheduled');
      if (bootstrap.length !== 1 || scheduled.length < 1) throw new Error('scoped V2 polling cadence coverage gap');
      const ordered = [bootstrap[0], ...scheduled];
      for (let index = 1; index < ordered.length; index += 1) {
        const previous = ordered[index - 1]; const record = ordered[index];
        const cadenceMs = (record.startedAt - previous.startedAt) * 1_000;
        if (record.startedAt < previous.finishedAt || cadenceMs < POLLING_MIN_CADENCE_MS || cadenceMs > POLLING_MAX_CADENCE_MS) throw new Error('scoped V2 polling cadence or overlap failure');
      }
    },
    observation() {
      const scheduled = records.filter((record) => record.cycle === 'scheduled');
      return { frameId, loaderId, polling: { navigationScoped: true, endpoint: POLLING_ENDPOINT, periodMs: POLLING_PERIOD_MS, cadenceMinMs: POLLING_MIN_CADENCE_MS, cadenceMaxMs: POLLING_MAX_CADENCE_MS, windowStart: pollingWindow?.windowStart, windowEnd: pollingWindow?.windowEnd, minimumScheduledRequests: 1, observedScheduledRequests: scheduled.length }, requests: records, overflow };
    },
    async close() {
      await session?.detach().catch(() => {});
    },
  };
}

async function assertSemanticOverview(page) {
  const legend = page.getByLabel('Globe legend');
  const poiPanel = page.getByLabel('Upcoming POIs');
  const routeName = legend.getByText('V2 Acceptance Route KAAA-KBBB', { exact: true });
  const poiRows = poiPanel.locator('tbody tr');
  const kAaaPoiRow = poiRows.filter({ hasText: 'KAAA' }).filter({ hasNotText: 'KBBB' });
  const kBbbPoiRow = poiRows.filter({ hasText: 'KBBB' }).filter({ hasNotText: 'KAAA' });
  await routeName.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  await kAaaPoiRow.first().waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  await kBbbPoiRow.first().waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  await poiRows.nth(1).waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  await settleAnimations(page);
  if ((await poiRows.count()) < 2) throw new Error('active V2 route, context, or KAAA/KBBB generated POI body rows are not visibly bound to the accepted KML');
  return { routeName: await routeName.innerText(), firstPoi: await kAaaPoiRow.first().innerText(), secondPoi: await kBbbPoiRow.first().innerText(), poiRows: await poiRows.count() };
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
    await lifecycle.beginPollingWindow();
    await lifecycle.waitForScheduledPoll();
    const post = await viewportArtifact(page, 'journey-post');
    lifecycle.assertHealthy();
    return { missionName, activation: 'browser-observed-200', lifecycle: lifecycle.observation(), visible, artifacts: { ...pre, ...post } };
  } finally {
    await lifecycle.close();
  }
}

async function main() {
  const values = parse(process.argv);
  let browser;
  try {
    browser = await chromium.connectOverCDP(values.session);
    const context = browser.contexts()[0];
    if (!context) throw new Error('platform-supplied browser session has no context');
    const page = context.pages()[0] ?? await context.newPage();
    const result = await runV2MissionRetirement({ page, origin: values.origin, kmlPath: values.kml });
    process.stdout.write(`${JSON.stringify({ status: 'passed', ...result })}\n`);
  } finally {
    await browser?.close().catch(() => {});
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(
      `${error instanceof Error ? error.stack : String(error)}\n`,
      () => process.exit(1),
    );
  });
}
