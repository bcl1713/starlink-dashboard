import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
const require = createRequire(new URL('../../../frontend/mission-planner/package.json', import.meta.url));
const { expect } = require('@playwright/test');

export async function batchJourney(context, origin, input, output) {
  const page = await context.newPage();
  const actions = [], events = [], probes = [], jobs = [];
  let mission, temperature, probing = true;
  const real = !!process.env.ITINERARY_INPUT_ROOT;
  const networkMode = process.env.ITINERARY_NETWORK_MODE;
  if (networkMode === 'offline') await context.route('**/*', route =>
    new URL(route.request().url()).origin === origin ? route.continue() : route.abort('internetdisconnected'));
  page.on('pageerror', e => events.push({ type: 'pageerror', message: String(e) }));
  page.on('response', async r => {
    if (temperature && r.url().includes(`/api/v2/missions/${mission}/export`)) {
      const receipt = { temperature, url: r.url(), status: r.status(), headers: r.headers() };
      jobs.push(receipt);
      if (r.status() === 202 || r.headers()['content-type']?.includes('json')) receipt.job = await r.json();
      await r.finished(); receipt.timing = r.request().timing();
      await writeFile(join(output, 'export-stages.json'), JSON.stringify(jobs, null, 2));
    }
    if (r.url().startsWith(origin + '/api/') && r.status() >= 400)
      events.push({ type: 'api-error', status: r.status(), url: r.url(), body: await r.text() });
  });
  const save = async name => {
    await writeFile(join(output, 'operator-actions.json'), JSON.stringify({ scope: 'Original intake-to-publication convention; excludes navigation, setup, export and repeated controls', count: actions.length, actions, export_actions: 2 }, null, 2));
    await page.screenshot({ path: join(output, `${name}.png`), fullPage: true });
  };
  const action = async (category, name, run) => {
    actions.push({ category, name }); await run();
  };
  const click = (name, category = 'workflow') => action(category, name, () => page.getByRole('button', { name, exact: true }).click());
  const json = async (path, method = 'GET', payload) => {
    const r = await context.request.fetch(origin + path, { method, data: payload, timeout: 120000 });
    assert(r.ok(), `${r.status()} ${await r.text()}`); return r.json();
  };
  const read = () => json(`/api/v2/missions/planning/missions/${mission}`);
  const monitor = async () => {
    while (probing) {
      if (mission) await Promise.all([
        `${process.env.ITINERARY_HEALTH_ORIGIN}/health`, origin + '/api/status', origin + `/api/v2/missions/${mission}`
      ].map(async url => {
        const start = performance.now(); let status, error, headers;
        try {
          const r = await fetch(url, { signal: AbortSignal.timeout(2000) });
          headers = (performance.now() - start) / 1000; status = r.status; await r.arrayBuffer();
        } catch (e) { error = String(e); }
        probes.push({ url, status, error, headers_seconds: headers, body_seconds: (performance.now() - start) / 1000 });
      }));
      await new Promise(r => setTimeout(r, 150));
    }
  };
  const monitoring = monitor();
  try {
    await page.goto(origin + '/missions');
    await page.getByRole('button', { name: 'Create from itinerary', exact: true }).click(); // navigation, excluded in the retained convention
    await action('intake', 'Upload itinerary PDF', () => page.getByLabel('Itinerary PDF', { exact: true }).setInputFiles(join(input, real ? 'Itinerary Rev 5.pdf' : 'itinerary.pdf')));
    await action('intake', 'Upload three KMLs together', () => page.getByLabel('Initial route KMLs', { exact: true }).setInputFiles([1, 2, 3].map(n => join(input, real ? `Leg ${n} Rev 5.kml` : `leg-${n}.kml`))));
    await click('Extract itinerary', 'intake');
    await expect(page.getByLabel('Mission name', { exact: true })).toBeVisible();
    assert.equal(await page.getByLabel('Unlabeled AR altitude units', { exact: true }).isVisible(), false);
    await action('safety', 'Confirm satellite service access once', () => page.getByRole('checkbox', { name: 'I confirm service access to the selected satellites', exact: true }).check());
    await click('Continue to route attachments', 'intake');
    await expect(page.getByRole('button', { name: 'Accept route bindings', exact: true })).toBeVisible({ timeout: 120000 });
    const staged = await page.getByLabel(real ? /^Assign Leg [123] Rev 5.kml$/ : /^Assign leg-[123].kml$/).all();
    assert.equal(staged.length, 3);
    for (const select of staged) assert(await select.inputValue(), 'source evidence must suggest a unique leg');
    for (const box of await page.getByRole('checkbox', { name: /^Acknowledge / }).all())
      await action('source-correction', await box.getAttribute('aria-label'), () => box.check());
    await save('01-batch-source-review');
    await click('Accept route bindings', 'intake');
    await expect(page.getByText('Routes attached. Review AR windows and plans next.', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Continue to source review', exact: true }).click(); // navigation
    await expect(page).toHaveURL(/\/missions\/[^/]+$/);
    mission = new URL(page.url()).pathname.split('/').at(-1);
    const initial = await read();
    assert.equal(initial.expected_legs.length, 3);
    assert.equal(initial.expected_legs.flatMap(c => c.leg.ar_rows ?? []).length, 5);
    for (const row of initial.expected_legs.flatMap(c => c.leg.ar_rows ?? []))
      assert.equal(row.confirmed_units, 'flight_level');
    const source = page.getByRole('region', { name: 'Itinerary source review' });
    await expect(source.getByRole('checkbox', { name: /^Confirm / })).toHaveCount(5, { timeout: 120000 });
    for (const box of await source.getByRole('checkbox', { name: /^Confirm / }).all())
      await action('safety', await box.getAttribute('aria-label'), () => box.check());
    await action('safety', 'Confirm no AR windows for leg 2', () => source.getByRole('checkbox', { name: 'I confirm no AR windows for this leg', exact: true }).check());
    const generate = page.getByRole('button', { name: 'Generate plans', exact: true });
    await expect(generate).toBeEnabled({ timeout: 120000 });
    await save('02-source-review-fl-default');
    await click('Generate plans', 'planning');
    const apply = page.getByRole('button', { name: 'Apply selected plans', exact: true });
    await expect(page.getByLabel('Select Leg 3 proposal', { exact: true })).toBeVisible({ timeout: 180000 });
    await expect(apply).toBeEnabled();
    await save('03-plan-comparisons');
    await click('Apply selected plans', 'planning');
    await expect(page.getByText('Selected plans applied to saved drafts. Continue to final review.', { exact: true })).toBeVisible({ timeout: 120000 });
    const approval = page.getByRole('checkbox', { name: 'I approve the selected satellite plans and Starshield settings', exact: true });
    await expect(approval).toBeEnabled();
    // Wait for all canonical previews before binding the approval to their signatures.
    await expect.poll(async () => {
      const v = await read(); return v.expected_legs.every(c => c.computation_status === 'applied');
    }, { timeout: 120000 }).toBe(true);
    await expect(page.getByText('Checking canonical timelines and customer maps…', { exact: true })).toHaveCount(0, { timeout: 120000 });
    await action('safety', 'Approve selected satellite plans and Starshield', () => approval.check());
    const gaps = page.getByRole('checkbox', { name: 'I acknowledge the listed X-band outages and backup gaps', exact: true });
    if (await gaps.count()) await action('safety', 'Acknowledge displayed outages and backup gaps', () => gaps.check());
    await save('04-final-review');
    const publish = page.getByRole('button', { name: 'Publish reviewed plans', exact: true });
    await expect(publish).toBeEnabled({ timeout: 120000 });
    await click('Publish reviewed plans', 'publication');
    await expect.poll(async () => (await read()).mission.legs.length, { timeout: 120000 }).toBe(3);
    const installed = await read();
    assert(installed.mission.legs.every(l => l.is_active === false));
    assert(installed.expected_legs.every(c => c.review_status === 'reviewed'));
    await writeFile(join(output, 'published-readback.json'), JSON.stringify(installed, null, 2));
    await save('05-published-three-inactive');
    await page.goto(origin + '/missions'); // navigation
    await expect(page.getByText('3 legs', { exact: true })).toBeVisible();
    await save('06-mission-list-three-legs');
    for (const mode of ['cold', 'warm']) {
      temperature = mode;
      const start = performance.now();
      const open = () => page.getByRole('button', { name: 'Export', exact: true }).click();
      await open(); // export controls recorded separately from the retained intake-to-publication count
      const dialog = page.getByRole('dialog');
      const download = page.waitForEvent('download', { timeout: 660000 });
      const exportClick = () => dialog.getByRole('button', { name: 'Export', exact: true }).click();
      await exportClick();
      const file = await download;
      assert.equal(await file.failure(), null);
      await file.saveAs(join(output, `${mode}.zip`));
      jobs.push({ temperature: mode, complete_seconds: (performance.now() - start) / 1000 });
      await save(`07-${mode}-export`);
      await expect(dialog).not.toBeVisible({ timeout: 10000 });
    }
    temperature = undefined;
    const after = await read(); assert.deepEqual(after, installed, 'export must preserve reviewed inputs');
    await writeFile(join(output, 'final-readback.json'), JSON.stringify(after, null, 2));
    if (!real) {
      const zip = await readFile(join(output, 'cold.zip'));
      const imported = await context.request.post(origin + '/api/v2/missions/import', {
        multipart: { file: { name: 'synthetic-package.zip', mimeType: 'application/zip', buffer: zip } }, timeout: 120000
      });
      assert(imported.ok(), await imported.text());
      const clone = await imported.json();
      const cloneView = await json(`/api/v2/missions/planning/missions/${clone.mission_id}`);
      assert.notEqual(clone.mission_id, mission);
      assert.equal(cloneView.mission.legs.length, 3);
      await writeFile(join(output, 'synthetic-package.zip'), zip);
      await writeFile(join(output, 'collision-views.json'), JSON.stringify({ beforeClone: installed, cloneView }, null, 2));
    }
    assert.equal(events.length, 0, JSON.stringify(events));
    return { passed: true, mission_id: mission, actions: actions.length, action_target_met: actions.length <= 20,
      steps: [...(real ? [] : ['package-collision-roundtrip']), 'batch-intake', 'source-review', 'generate-apply', 'publish-reviewed', 'mission-list-three-legs', 'cold-warm-export', 'no-activation-or-terminal-side-effects'],
      candidate_sha: process.env.ACCEPTANCE_CANDIDATE_SHA, network_mode: networkMode };
  } finally {
    probing = false; await monitoring;
    await writeFile(join(output, 'api-probes.json'), JSON.stringify({ deadline_seconds: 2, probes, failures: probes.filter(p => p.error || p.status !== 200 || p.body_seconds > 2) }, null, 2));
    await writeFile(join(output, 'browser-events.json'), JSON.stringify(events, null, 2));
    await save('final-page').catch(() => {});
    await page.close();
  }
}
