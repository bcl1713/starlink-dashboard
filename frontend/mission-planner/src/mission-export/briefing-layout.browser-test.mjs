/** Real print-layout checks; run in the production browser environment. */
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { openRenderOwner } from './render-owner.mjs';
import { createRenderBudget } from './render-budget.mjs';
import { prepareMissionDocument } from './briefing-mission-layout.mjs';
const outputRoot = process.env.CHECKPOINT_OUTPUT;
const payload = JSON.parse(
  await readFile(process.env.BRIEFING_PAYLOAD, 'utf8')
);
payload.legs = [payload.legs[0]];
const leg = payload.legs[0];
leg.mapInput = { synthetic: true };
leg.rows = [
  {
    id: 'row',
    startUtc: leg.flight.startUtc,
    endUtc: leg.flight.endUtc,
    displayCells: [
      '10:00 - 10:15',
      'Landing SOF; Ka + Starshield + X-Band unavailable',
      'X-Band',
      'Elevated risk',
    ],
  },
];
await mkdir(outputRoot, { recursive: true });
const budget = createRenderBudget();
const owner = await openRenderOwner({
  outputRoot,
  ownershipPath: outputRoot + '/ownership.json',
  assetRoot: process.env.BRIEFING_ASSETS,
  budget,
});
try {
  const result = await prepareMissionDocument({
    owner,
    budget,
    payload,
    outputRoot,
    check: () => budget.workRemainingMs(),
    renderMaps: async () => ({
      [leg.legId]: {
        pngs: [
          'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        ],
      },
    }),
    onDiagnostic: () => {},
  });
  const cells = await result.page.evaluate(() =>
    [...document.querySelectorAll('tbody td')].map((cell) => {
      const range = document.createRange();
      range.selectNodeContents(cell);
      return {
        lines: new Set([...range.getClientRects()].map((r) => r.top)).size,
        fits: cell.scrollWidth <= cell.clientWidth + 1,
        fontSize: parseFloat(getComputedStyle(cell).fontSize),
      };
    })
  );
  assert.equal(cells.length, 4);
  assert.ok(cells.every((cell) => cell.fontSize >= 12 && cell.fontSize < 16));
  assert.ok(
    cells.every((c) => c.lines === 1 && c.fits),
    JSON.stringify(cells)
  );
} finally {
  const cleanup = await owner.close();
  assert.equal(cleanup.success, true, JSON.stringify(cleanup));
}
