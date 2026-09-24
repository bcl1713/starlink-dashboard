#!/usr/bin/env node
/** Product-only V2 visible journey adapter.
 *
 * The platform supplies an already-running browser session, deployed origin, and
 * bounded evidence directory. This module neither launches nor provisions a
 * browser, manages Docker, nor tears down platform resources.
 */
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(resolve(ROOT, 'frontend/mission-planner/package.json'));
const { chromium } = require('@playwright/test');

function parse(argv) {
  const values = {};
  for (let index = 2; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith('--') || !value || value.startsWith('--')) throw new Error(`invalid argument: ${key}`);
    values[key.slice(2)] = value;
  }
  for (const required of ['session', 'origin', 'kml', 'evidence-dir']) {
    if (!values[required]) throw new Error(`missing --${required}`);
  }
  return values;
}

async function settleAnimations(page) {
  await page.evaluate(async () => {
    await Promise.all(document.getAnimations({ subtree: true }).map((animation) => animation.finished.catch(() => undefined)));
  });
}

async function writeEvidence(directory, name, value) {
  const root = resolve(directory);
  const target = resolve(root, name);
  if (!target.startsWith(`${root}/`)) throw new Error('evidence name escapes platform writer directory');
  await mkdir(dirname(target), { recursive: true, mode: 0o700 });
  await writeFile(target, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
}

export async function runV2MissionRetirement({ page, origin, kmlPath, evidenceDir }) {
  const missionName = `V2 acceptance ${Date.now()}`;
  const navigation = [];
  const onResponse = (response) => {
    if (response.url().includes('/api/v2/')) navigation.push({ url: new URL(response.url()).pathname, status: response.status() });
  };
  page.on('response', onResponse);
  try {
    await page.goto(origin, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Create New Mission' }).click();
    await page.getByLabel('Mission Name').fill(missionName);
    await page.getByRole('button', { name: 'Create Mission', exact: true }).click();
    await page.getByRole('button', { name: 'Add Leg', exact: true }).click();
    await page.getByRole('button', { name: 'Upload KML', exact: true }).click();
    await page.locator('input[type=file]').setInputFiles(kmlPath);
    await page.getByRole('button', { name: 'Add Leg', exact: true }).click();

    const activation = page.waitForResponse((response) => response.url().includes('/activate') && response.status() === 200);
    await page.getByRole('button', { name: 'Activate', exact: true }).click();
    await activation;

    await page.getByRole('link', { name: 'Overview', exact: true }).click();
    await page.getByLabel('Globe legend').waitFor();
    await settleAnimations(page);
    const visible = await page.locator('main').innerText();
    if (!/Path|Route/.test(visible) || !/Upcoming POIs/.test(visible)) {
      throw new Error('active V2 route/context/POIs are not visible on Overview');
    }
    const observation = { missionName, activation: 'browser-observed-200', navigation, visible: { activeRoute: /Path|Route/.test(visible), pois: /Upcoming POIs/.test(visible) } };
    await writeEvidence(evidenceDir, 'v2-visible-journey.json', observation);
    return observation;
  } finally {
    page.off('response', onResponse);
  }
}

async function main() {
  const values = parse(process.argv);
  const browser = await chromium.connectOverCDP(values.session);
  const context = browser.contexts()[0];
  if (!context) throw new Error('platform-supplied browser session has no context');
  const page = context.pages()[0] ?? await context.newPage();
  const result = await runV2MissionRetirement({ page, origin: values.origin, kmlPath: values.kml, evidenceDir: values['evidence-dir'] });
  process.stdout.write(`${JSON.stringify({ status: 'passed', result })}\n`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exitCode = 1;
  });
}
