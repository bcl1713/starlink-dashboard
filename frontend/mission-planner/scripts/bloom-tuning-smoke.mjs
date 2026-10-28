import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { downloadAfterClick } from './bloom-lifecycle.mjs';

export async function verifyBloomTuning(page, frames, snapshot, evidence) {
  const before = await snapshot(page);
  await page.getByRole('button', { name: 'Bloom tuning', exact: true }).click();
  await page
    .getByRole('button', { name: 'Find city glow', exact: true })
    .click();
  await page.getByLabel('Cities emission', { exact: true }).fill('36');
  await page
    .getByLabel('Bloom debug view', { exact: true })
    .selectOption('bright');
  await frames(page);
  await page.screenshot({ path: resolve(evidence, 'city-bright-pass.png') });
  await page
    .getByLabel('Bloom debug view', { exact: true })
    .selectOption('bloom');
  await frames(page);
  await page.screenshot({ path: resolve(evidence, 'city-bloom-only.png') });
  await page
    .getByLabel('Bloom debug view', { exact: true })
    .selectOption('final');
  await frames(page);
  await page.screenshot({ path: resolve(evidence, 'city-tuning-final.png') });
  const download = await downloadAfterClick(
    () => page.waitForEvent('download'),
    () =>
      page
        .getByRole('button', { name: 'Download settings.json', exact: true })
        .click()
  );
  await download.saveAs(resolve(evidence, 'tuning-feedback.json'));
  const report = JSON.parse(
    readFileSync(resolve(evidence, 'tuning-feedback.json'), 'utf8')
  );
  assert.equal(report.schema, 'overview-bloom-tuning/v1');
  assert.equal(report.mode, 'bloom');
  assert.equal(report.emissions.cities, 36);
  assert.equal(report.emissions.cityColor, '#ffb15c');
  assert.equal(report.isolateCities, true);
  assert.equal(report.settings.view, 'final');
  assert.equal(report.settings.maxDimension, 1920);
  assert.deepEqual(report.frame.camera, before.camera);
  assert.ok(
    report.cityEmission.colorLinear[0] > report.cityEmission.colorLinear[1]
  );
  assert.ok(
    report.cityEmission.colorLinear[1] > report.cityEmission.colorLinear[2]
  );
  await page
    .getByRole('button', { name: 'Copy settings', exact: true })
    .click();
  await page.getByLabel('Feedback JSON', { exact: true }).waitFor();
  const copied = JSON.parse(
    await page.getByLabel('Feedback JSON', { exact: true }).inputValue()
  );
  assert.equal(copied.emissions.cities, 36);
  assert.equal(copied.sourceSha, report.sourceSha);
  await page.getByRole('button', { name: 'Reset tuning', exact: true }).click();
  await page.getByRole('button', { name: 'Bloom tuning', exact: true }).click();
  await frames(page);
  assert.deepEqual((await snapshot(page)).camera, before.camera);
  return { report, copyUi: true, downloadWithoutTimingRuns: true };
}
