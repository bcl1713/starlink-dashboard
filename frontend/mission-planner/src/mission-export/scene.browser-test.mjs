/** Run with the production browser, built map assets and a retained payload. */
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { openRenderOwner } from './render-owner.mjs';
import { createRenderBudget } from './render-budget.mjs';
import { renderMapInContext } from './map-stage.mjs';

const outputRoot = process.env.CHECKPOINT_OUTPUT;
const payload = JSON.parse(
  await readFile(process.env.BRIEFING_PAYLOAD, 'utf8')
);
await mkdir(outputRoot, { recursive: true });
const budget = createRenderBudget();
const owner = await openRenderOwner({
  outputRoot,
  ownershipPath: outputRoot + '/ownership.json',
  assetRoot: process.env.BRIEFING_ASSETS,
  budget,
});
const requests = [];
const newContext = owner.newContext.bind(owner);
owner.newContext = async (...args) => {
  const context = await newContext(...args);
  context.on('page', (page) =>
    page.on('request', (request) =>
      requests.push(new URL(request.url()).pathname)
    )
  );
  return context;
};
try {
  const result = await renderMapInContext({
    owner,
    budget,
    input: payload.legs[0].mapInput,
    viewport: { width: 875, height: 764 },
  });
  assert.equal(result.status, 'primary', JSON.stringify(result));
  for (const asset of ['/earth-day-hi.jpg', '/city-lights-mask.png']) {
    assert.equal(
      requests.filter((url) => url === asset).length,
      1,
      asset + ' should be loaded once for both rendering and readiness'
    );
  }
} finally {
  const cleanup = await owner.close();
  assert.equal(cleanup.success, true, JSON.stringify(cleanup));
}
