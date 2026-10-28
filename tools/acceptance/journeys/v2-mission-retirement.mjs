#!/usr/bin/env node
/** Product-only V2 visible journey adapter.
 *
 * The adapter attaches to the platform-owned browser session and returns bounded
 * observations/artifact bytes on stdout. The platform is the sole evidence writer.
 */
import { createHash } from 'node:crypto';
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
const POLLING_PERIOD_MS = 1_000;
const POLLING_MIN_CADENCE_MS = 900;
const POLLING_MAX_CADENCE_MS = 2_500;
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
  let historyMode = '';
  let bootstrapStarted = false;
  // QueryObserver resets its interval on completion. Errors use the product's
  // intentional five-second backoff rather than the live one-second default.
  const pollingSettings = () => historyMode === 'degraded'
    ? { periodMs: 5_000, cadenceMinMs: 4_500, cadenceMaxMs: 7_500 }
    : { periodMs: POLLING_PERIOD_MS, cadenceMinMs: POLLING_MIN_CADENCE_MS, cadenceMaxMs: POLLING_MAX_CADENCE_MS };
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
        requests.set(event.requestId, { id: event.requestId, path: new URL(event.request.url).pathname, startedAt: event.timestamp, loaderId: event.loaderId, outcome: 'pending', cycle: bootstrapStarted ? 'scheduled' : 'bootstrap' });
        bootstrapStarted = true;
      });
      session.on('Network.responseReceived', (event) => {
        const record = requests.get(event.requestId);
        if (record) record.status = event.response.status;
      });
      session.on('Network.loadingFinished', (event) => {
        const record = requests.get(event.requestId);
        if (record) {
          Object.assign(record, { outcome: record.status === 200 ? 'finished' : record.status === 503 ? 'degraded' : 'http_failed', finishedAt: event.timestamp });
          add({ ...record });
          requests.delete(event.requestId);
        }
      });
      session.on('Network.loadingFailed', (event) => {
        const record = requests.get(event.requestId);
        if (record) {
          Object.assign(record, { outcome: 'failed', error: event.errorText, finishedAt: event.timestamp });
          add({ ...record });
          requests.delete(event.requestId);
        }
      });
    },
    async beginHistoryObservation() {
      const deadline = Date.now() + SEMANTIC_READINESS_TIMEOUT_MS;
      while (!records.some((record) => record.cycle === 'bootstrap' && ['finished', 'degraded'].includes(record.outcome))) {
        if (Date.now() >= deadline) throw new Error('scoped V2 polling bootstrap coverage gap');
        await page.waitForTimeout(50);
      }
      const bootstrap = records.find((record) => record.cycle === 'bootstrap' && ['finished', 'degraded'].includes(record.outcome));
      historyMode = bootstrap.outcome === 'degraded' ? 'degraded' : 'live';
      pollingWindow = { windowStart: bootstrap.finishedAt, windowEnd: bootstrap.finishedAt };
      return historyMode;
    },
    async waitForScheduledPoll() {
      const deadline = Date.now() + SEMANTIC_READINESS_TIMEOUT_MS;
      const outcome = historyMode === 'degraded' ? 'degraded' : 'finished';
      while (!records.some((record) => record.cycle === 'scheduled' && record.outcome === outcome)) {
        if (Date.now() >= deadline) throw new Error('scoped V2 scheduled polling window coverage gap');
        await page.waitForTimeout(50);
      }
      const scheduled = records.filter((record) => record.cycle === 'scheduled' && record.outcome === outcome);
      pollingWindow.windowEnd = scheduled.at(-1).finishedAt;
    },
    assertHealthy() {
      const pending = [...requests.values()].filter((record) => record.outcome === 'pending');
      if (overflow) throw new Error('scoped V2 navigation lifecycle coverage gap: record budget exceeded');
      if (pending.length || !records.length) throw new Error('scoped V2 navigation lifecycle is incomplete or failed');
      const bootstrap = records.filter((record) => record.cycle === 'bootstrap');
      const scheduled = records.filter((record) => record.cycle === 'scheduled');
      const outcome = historyMode === 'degraded' ? 'degraded' : 'finished';
      const status = historyMode === 'degraded' ? 503 : 200;
      if (!['live', 'degraded'].includes(historyMode) || records.some((record) => record.outcome !== outcome || record.status !== status)) throw new Error('scoped V2 navigation lifecycle is incomplete or failed');
      if (bootstrap.length !== 1 || (historyMode === 'live' && scheduled.length < 1)) throw new Error('scoped V2 polling cadence coverage gap');
      const { cadenceMinMs, cadenceMaxMs } = pollingSettings();
      const ordered = [bootstrap[0], ...scheduled];
      for (let index = 1; index < ordered.length; index += 1) {
        const previous = ordered[index - 1]; const record = ordered[index];
        const cadenceMs = (record.startedAt - previous.finishedAt) * 1_000;
        if (record.startedAt < previous.finishedAt || cadenceMs < cadenceMinMs || cadenceMs > cadenceMaxMs) throw new Error('scoped V2 polling cadence or overlap failure');
      }
    },
    observation(historyFallback) {
      const scheduled = records.filter((record) => record.cycle === 'scheduled');
      const degraded = historyMode === 'degraded';
      return { frameId, loaderId, history: degraded ? { mode: historyMode, fallback: historyFallback } : { mode: historyMode }, polling: { navigationScoped: true, endpoint: POLLING_ENDPOINT, ...pollingSettings(), cadenceBasis: 'previous-completion-to-next-start', windowStart: pollingWindow?.windowStart, windowEnd: scheduled.at(-1)?.finishedAt ?? pollingWindow?.windowEnd, minimumScheduledRequests: degraded ? 0 : 1, observedScheduledRequests: scheduled.length }, requests: records, overflow };
    },
    async finishObservation() {
      // End a bounded, terminal network window before screenshot rendering can
      // start another poll. Never drop an already observed in-flight request.
      const deadline = Date.now() + SEMANTIC_READINESS_TIMEOUT_MS;
      while (requests.size) {
        if (Date.now() >= deadline) throw new Error('scoped V2 navigation lifecycle has pending requests');
        await page.waitForTimeout(50);
      }
      await this.close();
    },
    async close() {
      await session?.detach().catch(() => {});
      session = undefined;
    },
  };
}

async function waitForMissionCreationReadiness(page, origin) {
  await page.goto(origin, { waitUntil: 'commit', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  const control = page.getByRole('button', { name: 'Create New Mission', exact: true });
  await control.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  const deadline = Date.now() + SEMANTIC_READINESS_TIMEOUT_MS;
  while (!await control.isEnabled()) {
    if (Date.now() >= deadline) throw new Error('Create New Mission control did not become enabled');
    await page.waitForTimeout(50);
  }
  return control;
}

async function visibleMapPoi(page, map, name, label) {
  const marker = map.locator(`[data-label-kind="poi"][data-label-text="${label}"]`);
  await marker.waitFor({ state: 'attached', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  if (await marker.count() !== 1) throw new Error(`ambiguous ${name} map marker`);
  const id = await marker.getAttribute('data-overview-label-id');
  if (!id?.startsWith('poi:') || id.length <= 4) throw new Error(`missing ${name} map marker identity`);
  const source = marker.locator('[data-label-source]');
  const deadline = Date.now() + SEMANTIC_READINESS_TIMEOUT_MS;
  let painted;
  while (!painted) {
    if (await source.isVisible()) painted = source;
    else {
      // Close endpoints can share a crowded-label disclosure. Use its public
      // control, and require its group to contain this exact map marker ID.
      for (const group of await map.locator('details[data-group-ids]').all()) {
        const ids = JSON.parse(await group.getAttribute('data-group-ids'));
        if (!Array.isArray(ids) || !ids.includes(id)) continue;
        const summary = group.locator('summary');
        if (!await summary.isVisible()) continue;
        if (await group.getAttribute('open') === null) await summary.click({ timeout: SEMANTIC_READINESS_TIMEOUT_MS });
        const item = group.getByText(label, { exact: true });
        if (await item.isVisible()) {
          await item.scrollIntoViewIfNeeded({ timeout: SEMANTIC_READINESS_TIMEOUT_MS });
          painted = item;
        }
      }
    }
    if (!painted) {
      if (Date.now() >= deadline) throw new Error(`${name} map marker label is not visible`);
      await page.waitForTimeout(50);
    }
  }
  await painted.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  const box = await painted.boundingBox();
  const bounds = await map.boundingBox();
  if (!box || !bounds || box.width <= 0 || box.height <= 0 || box.x < Math.max(0, bounds.x) || box.y < Math.max(0, bounds.y) || box.x + box.width > Math.min(1920, bounds.x + bounds.width) || box.y + box.height > Math.min(1080, bounds.y + bounds.height)) throw new Error(`${name} map marker label is outside the visible map`);
  // isVisible() does not account for overflow clipping. Check the text against
  // each ancestor's client viewport after any public disclosure scrolling.
  const unclipped = await painted.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    for (let ancestor = element.parentElement; ancestor; ancestor = ancestor.parentElement) {
      const style = getComputedStyle(ancestor);
      const bounds = ancestor.getBoundingClientRect();
      const left = bounds.left + ancestor.clientLeft;
      const top = bounds.top + ancestor.clientTop;
      if (/(auto|scroll|hidden|clip)/.test(style.overflowX) && (rect.left < left || rect.right > left + ancestor.clientWidth)) return false;
      if (/(auto|scroll|hidden|clip)/.test(style.overflowY) && (rect.top < top || rect.bottom > top + ancestor.clientHeight)) return false;
    }
    return true;
  });
  if (!unclipped) throw new Error(`${name} map marker label is clipped`);
  if (await painted.innerText() !== label) throw new Error(`${name} map marker label does not match the accepted KML`);
  return { name, id, label };
}

function observedRouteBinding(upload, detail) {
  const routeName = 'V2 Acceptance Route KAAA-KBBB';
  const coordinates = detail.points?.map((point) => [point.longitude, point.latitude]);
  if (typeof upload.id !== 'string' || !/^v2-activation-route(?:-[1-9][0-9]*)?$/.test(upload.id) || upload.id.length > 256 || upload.name !== routeName || upload.point_count !== 3 || detail.id !== upload.id || detail.name !== routeName || detail.point_count !== 3 || detail.is_active !== true || JSON.stringify(coordinates) !== JSON.stringify([[-100, 35], [-99.95, 35.05], [-99.9, 35.1]])) throw new Error('public uploaded route identity, active state, or geometry does not match the accepted KML');
  // Independently encode the published route-context-v1 byte protocol. This
  // binds observed public response geometry to the Overview's rendered context.
  const chunks = [Buffer.from('route-context-v1\0')];
  for (const field of ['ordinary', upload.id, '', '']) {
    const bytes = Buffer.from(field); const length = Buffer.alloc(4);
    length.writeUInt32BE(bytes.length); chunks.push(length, bytes);
  }
  const count = Buffer.alloc(4); count.writeUInt32BE(coordinates.length); chunks.push(count);
  for (const [longitude, latitude] of coordinates) {
    const point = Buffer.alloc(16); point.writeDoubleBE(longitude, 0); point.writeDoubleBE(latitude, 8); chunks.push(point);
  }
  return { source: 'browser-upload-and-route-detail', uploadStatus: 201, detailStatus: 200, routeId: upload.id, routeName, pointCount: 3, coordinates, contextKey: createHash('sha256').update(Buffer.concat(chunks)).digest('hex') };
}

async function observePlanningRoute(page, upload) {
  await page.getByRole('link', { name: 'Routes', exact: true }).click();
  const row = page.getByRole('row')
    .filter({ has: page.getByRole('cell', { name: upload.name, exact: true }) })
    .filter({ has: page.getByText('Active', { exact: true }) });
  await row.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  if (await row.count() !== 1) throw new Error('public uploaded route row is ambiguous');
  await row.getByText('Active', { exact: true }).waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  const detailResponse = page.waitForResponse((response) => response.request().method() === 'GET' && new URL(response.url()).pathname === `/api/routes/${encodeURIComponent(upload.id)}` && response.status() === 200, { timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  await row.getByTitle('View route details', { exact: true }).click();
  const detail = await (await detailResponse).json();
  const routeBinding = observedRouteBinding(upload, detail);
  const dialog = page.getByRole('dialog');
  const title = dialog.getByRole('heading', { name: routeBinding.routeName, exact: true });
  const active = dialog.getByText('Active', { exact: true });
  await title.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  await active.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  const planning = { planningRouteName: await title.innerText(), planningRouteStatus: await active.innerText() };
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();
  return { routeBinding, planning };
}

async function assertSemanticOverview(page, expectedContextKey) {
  const legend = page.getByLabel('Globe legend');
  const routeLegend = legend.getByText('Planned route', { exact: true });
  const map = page.locator('.overview-map-stage');
  await routeLegend.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  const overview = page.locator('main.overview-page');
  const deadline = Date.now() + SEMANTIC_READINESS_TIMEOUT_MS;
  while (await overview.getAttribute('data-route-context-key') !== expectedContextKey) {
    if (Date.now() >= deadline) throw new Error('Overview rendered route context does not match the public uploaded route');
    await page.waitForTimeout(50);
  }
  await settleAnimations(page);
  const poiMarkers = [
    await visibleMapPoi(page, map, 'KAAA', 'Takeoff · KAAA'),
    await visibleMapPoi(page, map, 'KBBB', 'Landing · KBBB'),
  ];
  if (poiMarkers[0].id === poiMarkers[1].id) throw new Error('KAAA/KBBB map markers are not distinct');
  return { overviewRouteLegend: await routeLegend.innerText(), overviewRouteContextKey: await overview.getAttribute('data-route-context-key'), poiMarkers };
}

async function observeDegradedHistory(page) {
  const reasons = ['History refresh unavailable', 'Network source unavailable', 'Paced simulation · network measurements unavailable'];
  const context = page.getByLabel('Network history context');
  const deadline = Date.now() + SEMANTIC_READINESS_TIMEOUT_MS;
  let reason; let message;
  while (!reason) {
    for (const candidate of reasons) {
      const text = context.getByText(candidate, { exact: true });
      if (await text.isVisible()) { reason = candidate; message = text; break; }
    }
    if (!reason) {
      if (Date.now() >= deadline) throw new Error('current degraded history context is not visible');
      await page.waitForTimeout(50);
    }
  }
  // The per-plot error paragraph is intentionally visually hidden. The current
  // plot viewport is visible and carries its unavailable state accessibly.
  const plot = page.getByLabel('Network latency history', { exact: true }).getByRole('img', { name: /^Network latency time history; ms;.*; History unavailable$/ });
  await plot.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
  for (const surface of [message, plot]) {
    const box = await surface.boundingBox();
    if (!box || box.width <= 1 || box.height <= 1 || box.x < 0 || box.y < 0 || box.x + box.width > 1920 || box.y + box.height > 1080) throw new Error('degraded history context or plot is outside the visible viewport');
  }
  return { surface: 'network-history', reason, plotLabel: await plot.getAttribute('aria-label') };
}

export async function runV2MissionRetirement({ page, origin, kmlPath }) {
  const missionName = `V2 acceptance ${Date.now()}`;
  const lifecycle = scopedLifecycle(page);
  await lifecycle.arm();
  try {
    const createMission = await waitForMissionCreationReadiness(page, origin);
    const pre = await viewportArtifact(page, 'journey-pre');
    await createMission.click();
    await page.getByLabel('Mission Name').fill(missionName);
    await page.getByRole('button', { name: 'Create Mission', exact: true }).click();
    await page.getByRole('button', { name: 'Add Leg', exact: true }).click();
    await page.getByRole('button', { name: 'Upload KML', exact: true }).click();
    await page.locator('input[type=file]').setInputFiles(kmlPath);
    const uploaded = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/routes/upload' && response.status() === 201, { timeout: SEMANTIC_READINESS_TIMEOUT_MS });
    await page.getByRole('button', { name: 'Add Leg', exact: true }).click();
    const upload = await (await uploaded).json();
    if (typeof upload.id !== 'string' || upload.name !== 'V2 Acceptance Route KAAA-KBBB') throw new Error('public KML upload did not return the expected route');
    const legRoute = page.getByText(`Route: ${upload.id}`, { exact: true });
    await legRoute.waitFor({ state: 'visible', timeout: SEMANTIC_READINESS_TIMEOUT_MS });
    const missionLegRoute = await legRoute.innerText();
    const activation = page.waitForResponse((response) => new URL(response.url()).pathname.includes('/activate') && response.status() === 200);
    await page.getByRole('button', { name: 'Activate', exact: true }).click();
    await activation;
    const { routeBinding, planning } = await observePlanningRoute(page, upload);
    await page.getByRole('link', { name: 'Overview', exact: true }).click();
    const visible = await assertSemanticOverview(page, routeBinding.contextKey);
    const historyMode = await lifecycle.beginHistoryObservation();
    const historyFallback = historyMode === 'degraded'
      ? await observeDegradedHistory(page)
      : undefined;
    if (historyMode === 'live') await lifecycle.waitForScheduledPoll();
    await lifecycle.finishObservation();
    const post = await viewportArtifact(page, 'journey-post');
    lifecycle.assertHealthy();
    return { missionName, activation: 'browser-observed-200', routeBinding, lifecycle: lifecycle.observation(historyFallback), visible: { missionLegRoute, ...planning, ...visible, ...(historyFallback ? { historyFallback } : {}) }, artifacts: { ...pre, ...post } };
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
    const page = await context.newPage();
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
