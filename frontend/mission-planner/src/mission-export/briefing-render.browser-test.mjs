/** Real-process controls in the exact-SHA checkpoint image. */
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { readFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
const root = process.env.CHECKPOINT_OUTPUT || '/evidence';
const assetRoot = path.resolve('dist-mission-export');
async function run(name, fault = null, incomplete = false, options = {}) {
  assert.ok(
    existsSync(new URL('./briefing-render.mjs', import.meta.url)),
    'combined renderer contract absent'
  );
  const { renderBriefing } = await import('./briefing-render.mjs');
  const payload = JSON.parse(
    await readFile(
      path.join(
        root,
        'inputs',
        incomplete
          ? 'composition-incomplete-x.json'
          : 'composition-assessed.json'
      ),
      'utf8'
    )
  );
  const outputRoot = path.join(root, 'runtime', name);
  await mkdir(outputRoot, { recursive: true });
  return renderBriefing({
    payload,
    outputRoot,
    assetRoot,
    ownershipPath: path.join(outputRoot, 'ownership.json'),
    fault,
    ...options,
  });
}
function clean(report) {
  assert.ok(report.cleanup.contextsClosed);
  assert.ok(report.cleanup.browserExited);
  assert.ok(report.cleanup.listenerClosed);
  assert.equal(report.cleanup.survivors.length, 0);
}
import { registerOwnerTests } from './render-owner.test.mjs';
import { registerMapTests } from './map-stage.test.mjs';
import { registerDocumentTests } from './briefing-render.test.mjs';
const controls = { run, clean, root, assetRoot };
registerDocumentTests(controls);
registerMapTests(controls);
registerOwnerTests(controls);
