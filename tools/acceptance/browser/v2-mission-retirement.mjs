#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { basename, dirname, relative, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';

const ROOT = resolve(dirname(new URL(import.meta.url).pathname), '../../..');
const require = createRequire(resolve(ROOT, 'frontend/mission-planner/package.json'));
const { chromium } = require('@playwright/test');
const SIZE = { width: 1920, height: 1080, dpr: 1 };

function parseArgs(argv) {
  const values = {};
  for (let index = 2; index < argv.length; index += 2) {
    const key = argv[index];
    if (!key?.startsWith('--') || argv[index + 1]?.startsWith('--')) throw new Error(`invalid argument: ${key}`);
    values[key.slice(2)] = argv[index + 1];
  }
  return values;
}

async function inputs() {
  const flags = parseArgs(process.argv);
  const supplied = flags.input ? JSON.parse(await readFile(flags.input, 'utf8')) : {};
  const value = (name, required = true) => flags[name] ?? supplied[name] ?? (required ? (() => { throw new Error(`missing --${name}`); })() : undefined);
  const result = {
    mode: value('mode'), chrome: resolve(value('chrome')), display: value('display'),
    cdpPort: Number(value('cdp-port')), profileDir: resolve(value('profile-dir')),
    evidenceDir: resolve(value('evidence-dir')), frontendOrigin: value('frontend-origin', false),
  };
  if (!['neutral', 'journey'].includes(result.mode) || !Number.isInteger(result.cdpPort) || result.cdpPort < 1024 || result.cdpPort > 65535) throw new Error('invalid mode or CDP port');
  if (result.mode === 'journey' && !result.frontendOrigin) throw new Error('journey requires --frontend-origin');
  return result;
}

function contained(root, target) {
  const path = resolve(root, target);
  if (relative(root, path).startsWith('..')) throw new Error(`artifact outside evidence directory: ${path}`);
  return path;
}

async function artifact(state, name, value) {
  const path = contained(state.config.evidenceDir, resolve(state.config.evidenceDir, name));
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  await writeFile(path, typeof value === 'string' || Buffer.isBuffer(value) ? value : `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
  return path;
}

function start(state, command, args, name, env = {}) {
  const child = spawn(command, args, { detached: true, env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'] });
  state.children.push(child);
  child.stdout.pipe(state.logs[`${name}-stdout`]);
  child.stderr.pipe(state.logs[`${name}-stderr`]);
  return child;
}

async function processTree(pgid) {
  try {
    return (await promisify(execFile)('ps', ['-o', 'pid=,ppid=,pgid=,args=', '--forest', '-g', String(pgid)])).stdout;
  } catch (error) {
    return `process-tree unavailable: ${error.message}`;
  }
}

async function fetchVersion(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(1000) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function waitForCdp(state, chrome) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (chrome.exitCode !== null) throw new Error(`Chrome exited before CDP readiness: ${chrome.exitCode}`);
    try {
      const version = await fetchVersion(state.config.cdpPort);
      state.probes.firstJsonMs ??= Date.now() - state.startedAt;
      return version;
    } catch (error) {
      const kind = error.name === 'TimeoutError' ? 'timeout' : error.cause?.code ?? error.name;
      state.probes.errors[kind] = (state.probes.errors[kind] ?? 0) + 1;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  throw new Error('CDP readiness timed out after 120000ms');
}

function pngDimensions(buffer) {
  if (buffer.subarray(0, 8).compare(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) !== 0 || buffer.toString('ascii', 12, 16) !== 'IHDR') throw new Error('screenshot is not a decoded PNG');
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

async function assertExactViewport(page, state, artifactPrefix) {
  const metrics = await page.evaluate(() => ({
    innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    visualWidth: window.visualViewport?.width, visualHeight: window.visualViewport?.height,
    dpr: window.devicePixelRatio,
  }));
  const png = await page.screenshot({ type: 'png' });
  const raster = pngDimensions(png);
  await artifact(state, `${artifactPrefix}-metrics.json`, { ...metrics, raster });
  await artifact(state, `${artifactPrefix}.png`, png);
  if (metrics.innerWidth !== SIZE.width || metrics.innerHeight !== SIZE.height || metrics.visualWidth !== SIZE.width || metrics.visualHeight !== SIZE.height || metrics.dpr !== SIZE.dpr || raster.width !== SIZE.width || raster.height !== SIZE.height) throw new Error(`exact viewport mismatch: ${JSON.stringify({ ...metrics, raster })}`);
  return { ...metrics, raster };
}

async function setExactWindow(page, state) {
  const session = await page.context().newCDPSession(page);
  const target = await session.send('Browser.getWindowForTarget');
  const resize = await session.send('Browser.setContentsSize', { windowId: target.windowId, width: 1920, height: 1080 });
  const bounds = await session.send('Browser.getWindowBounds', { windowId: target.windowId });
  await artifact(state, 'cdp-window.json', { getWindowForTarget: target, setContentsSize: resize, getWindowBounds: bounds });
  return session;
}

async function neutral(page, state) {
  const neutralPath = await artifact(state, 'neutral.html', '<!doctype html><title>Neutral browser card</title><main>Neutral browser card</main>');
  await page.goto(pathToFileURL(neutralPath).href, { waitUntil: 'load' });
  const pre = await assertExactViewport(page, state, 'neutral-pre');
  const post = await assertExactViewport(page, state, 'neutral-post');
  return { pre, post };
}

async function journey(page, state) {
  const network = [];
  const consoleRecords = [];
  page.on('console', (message) => consoleRecords.length < 50 && consoleRecords.push({ type: message.type(), text: message.text() }));
  page.on('response', (response) => network.length < 100 && network.push({ url: response.url(), status: response.status(), method: response.request().method() }));
  const title = `V2 acceptance ${Date.now()}`;
  await page.goto(state.config.frontendOrigin, { waitUntil: 'networkidle' });
  await assertExactViewport(page, state, 'journey-pre');
  await page.getByRole('button', { name: 'Create New Mission' }).click();
  await page.getByLabel('Mission Name').fill(title);
  await page.getByRole('button', { name: 'Create Mission' }).click();
  await page.getByRole('button', { name: 'Add Leg' }).click();
  await page.getByRole('button', { name: 'Upload KML' }).click();
  const kml = resolve(ROOT, 'docs/missions/acceptance-assets/v2-activation-route.kml');
  await page.locator('input[type=file]').setInputFiles(kml);
  await page.getByRole('button', { name: 'Add Leg', exact: true }).click();
  const activation = page.waitForResponse((response) => response.url().includes('/activate') && response.status() === 200);
  await page.getByRole('button', { name: 'Activate', exact: true }).click();
  await activation;
  await page.getByRole('link', { name: 'Overview' }).click();
  await page.getByLabel('Globe legend').waitFor();
  const contract = await page.locator('main').innerText();
  if (!/Path|Route/.test(contract) || !/Upcoming POIs/.test(contract)) throw new Error('active V2 route/context/POIs not visible');
  const post = await assertExactViewport(page, state, 'journey-post');
  await artifact(state, 'journey-observations.json', { network, console: consoleRecords, contract });
  return { post, networkCount: network.length };
}

async function terminate(child) {
  if (!child || child.exitCode !== null) return;
  try { process.kill(-child.pid, 'SIGTERM'); } catch { /* already gone */ }
  await new Promise((resolve) => setTimeout(resolve, 250));
  if (child.exitCode === null) try { process.kill(-child.pid, 'SIGKILL'); } catch { /* already gone */ }
}

async function main() {
  const config = await inputs();
  await mkdir(config.evidenceDir, { recursive: true, mode: 0o700 });
  const state = { config, startedAt: Date.now(), children: [], logs: {}, probes: { errors: {} }, result: { mode: config.mode, status: 'failed' } };
  for (const name of ['xvfb-stdout', 'xvfb-stderr', 'chrome-stdout', 'chrome-stderr']) state.logs[name] = (await import('node:fs')).createWriteStream(contained(config.evidenceDir, `${name}.log`), { mode: 0o600 });
  let browser; let cdp;
  try {
    const chromeBytes = await readFile(config.chrome);
    const chromeInfo = { path: config.chrome, sha256: createHash('sha256').update(chromeBytes).digest('hex'), size: (await stat(config.chrome)).size };
    const xvfb = start(state, 'Xvfb', [config.display, '-screen', '0', '1920x1080x24', '-nolisten', 'tcp'], 'xvfb');
    await artifact(state, 'display.json', { display: config.display, geometry: '1920x1080x24', pid: xvfb.pid, pgid: xvfb.pid, processTree: await processTree(xvfb.pid) });
    const chrome = start(state, config.chrome, [`--remote-debugging-address=127.0.0.1`, `--remote-debugging-port=${config.cdpPort}`, `--user-data-dir=${config.profileDir}`, '--no-sandbox', '--no-first-run', '--no-default-browser-check', '--window-size=1920,1080'], 'chrome', { DISPLAY: config.display });
    state.probes.firstListenerMs = Date.now() - state.startedAt;
    const version = await waitForCdp(state, chrome);
    await artifact(state, 'browser.json', { ...chromeInfo, pid: chrome.pid, pgid: chrome.pid, version, probes: state.probes, processTree: await processTree(chrome.pid) });
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${config.cdpPort}`);
    const context = browser.contexts()[0]; const page = context.pages()[0] ?? await context.newPage();
    cdp = await setExactWindow(page, state);
    state.result = { mode: config.mode, status: 'passed', evidence: config.evidenceDir, result: config.mode === 'neutral' ? await neutral(page, state) : await journey(page, state) };
  } catch (error) {
    state.result = { mode: config.mode, status: 'failed', error: error instanceof Error ? error.message : String(error), evidence: config.evidenceDir };
  } finally {
    await cdp?.detach().catch(() => {}); await browser?.close().catch(() => {});
    await Promise.all(state.children.reverse().map(terminate));
    await rm(config.profileDir, { recursive: true, force: true }).catch(() => {});
    for (const stream of Object.values(state.logs)) stream.end();
    await artifact(state, 'result.json', state.result);
  }
  process.stdout.write(`${JSON.stringify(state.result)}\n`);
  process.exitCode = state.result.status === 'passed' ? 0 : 1;
}

main().catch((error) => { process.stdout.write(`${JSON.stringify({ status: 'failed', error: String(error) })}\n`); process.exitCode = 1; });
