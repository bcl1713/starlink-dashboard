/** Native print regression using a captured customer payload, without map services.
 * BRIEFING_PAYLOAD=<prepared payload.json> CHECKPOINT_OUTPUT=<owned directory>
 * BRIEFING_ASSETS=<existing asset directory> node <this file>
 * Requires Python and Poppler; verifies actual PDF words against unchanged cell bounds.
 */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { openRenderOwner } from './render-owner.mjs';
import { createRenderBudget } from './render-budget.mjs';
import {
  prepareMissionDocument,
  printMissionDocument,
} from './briefing-mission-layout.mjs';

const payload = JSON.parse(
  await readFile(process.env.BRIEFING_PAYLOAD, 'utf8')
);
const outputRoot = process.env.CHECKPOINT_OUTPUT;
await mkdir(outputRoot, { recursive: true });
const budget = createRenderBudget();
const owner = await openRenderOwner({
  outputRoot,
  assetRoot: process.env.BRIEFING_ASSETS,
  ownershipPath: path.join(outputRoot, 'ownership.json'),
  budget,
});
process.once(
  'SIGTERM',
  () => void owner.close().finally(() => process.exit(143))
);
try {
  const result = await prepareMissionDocument({
    owner,
    budget,
    payload,
    outputRoot,
    check: () => budget.workRemainingMs(),
    onDiagnostic: () => {},
    renderMaps: async () =>
      Object.fromEntries(
        payload.legs.map((leg) => [
          leg.legId,
          {
            pngs: [
              'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
            ],
          },
        ])
      ),
  });
  const cells = await result.page.evaluate(() =>
    [...document.querySelectorAll('tbody td')].map((cell) => {
      const range = document.createRange();
      range.selectNodeContents(cell);
      const style = getComputedStyle(cell);
      return {
        text: cell.textContent,
        font: parseFloat(style.fontSize),
        lines: new Set([...range.getClientRects()].map((r) => r.top)).size,
        textWidth: range.getBoundingClientRect().width,
        available:
          cell.clientWidth -
          parseFloat(style.paddingLeft) -
          parseFloat(style.paddingRight),
      };
    })
  );
  assert.ok(
    cells.every(
      (c) => c.font >= 12 && c.lines === 1 && c.textWidth <= c.available - 3
    ),
    JSON.stringify(cells)
  );
  const expectedRows = payload.legs.flatMap((leg) => leg.rows.map((r) => r.id));
  assert.deepEqual(
    result.pagePlan.pages.flatMap((p) => p.rowIds),
    expectedRows
  );
  assert.ok(result.pagePlan.pages.length <= 3 * payload.legs.length);
  if (expectedRows.length > 20) assert.ok(result.pagePlan.pages.length > 1);
  assert.ok(cells.some((c) => c.text.includes('Starshield Transition Window')));
  assert.ok(
    payload.legs.every((leg) => leg.popNote.includes('reestablishment'))
  );
  await writeFile(
    path.join(outputRoot, 'actual.pdf'),
    await printMissionDocument({ document: result, budget })
  );
  await writeFile(
    path.join(outputRoot, 'expectations.json'),
    JSON.stringify(result.expectations)
  );
  const verification = execFileSync(
    process.env.PYTHON || 'python',
    [
      fileURLToPath(
        new URL(
          '../../../../backend/starlink-location/app/mission/exporter/customer_pdf.py',
          import.meta.url
        )
      ),
      path.join(outputRoot, 'actual.pdf'),
      path.join(outputRoot, 'expectations.json'),
      '--timeout-seconds',
      String(Math.min(30, budget.workRemainingMs() / 1000)),
    ],
    { timeout: Math.floor(budget.workRemainingMs()), encoding: 'utf8' }
  );
  await writeFile(
    path.join(outputRoot, 'actual-pdf-validation.json'),
    verification
  );
  assert.equal(JSON.parse(verification).rows.length, expectedRows.length);
  console.log(
    JSON.stringify({
      pages: result.pagePlan.pages.length,
      rows: expectedRows.length,
      minimumFont: Math.min(...cells.map((c) => c.font)),
    })
  );
} finally {
  const cleanup = await owner.close();
  assert.equal(cleanup.success, true, JSON.stringify(cleanup));
}
