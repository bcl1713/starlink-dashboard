import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
async function builder() {
  assert.ok(
    existsSync(new URL('./pdf-expectations.mjs', import.meta.url)),
    'PDF expectation contract absent'
  );
  return (await import('./pdf-expectations.mjs')).buildPdfExpectations;
}
test('PDF expectations use canonical cells and page-local measured bounds', async () => {
  const payload = {
    legId: 'leg',
    rows: [
      { id: 'r', displayCells: ['12:25:01–12:25:05', 'SOF', 'Ka', 'Nominal'] },
    ],
  };
  const measured = {
    tableBodyBoundsPx: [10, 40, 1000, 80],
    tableInspectionBoundsPx: [10, 40, 1000, 700],
    rows: [
      {
        id: 'r',
        cellBoundsPx: [
          [10, 40, 200, 80],
          [200, 40, 500, 80],
          [500, 40, 800, 80],
          [800, 40, 1000, 80],
        ],
      },
    ],
  };
  const result = (await builder())(payload, measured);
  assert.deepEqual(result.rows[0], {
    legId: 'leg',
    rowId: 'r',
    page: 1,
    displayCells: ['12:25:01–12:25:05', 'SOF', 'Ka', 'Nominal'],
    cellBoundsPt: [
      [7.5, 30, 150, 60],
      [150, 30, 375, 60],
      [375, 30, 600, 60],
      [600, 30, 750, 60],
    ],
  });
  assert.deepEqual(result.pages, [
    {
      page: 1,
      tableBodyBoundsPt: [7.5, 30, 750, 60],
      tableInspectionBoundsPt: [7.5, 30, 750, 525],
    },
  ]);
});
test('PDF expectations reject omitted and duplicate measured rows', async () => {
  const build = await builder();
  const payload = {
    legId: 'leg',
    rows: [{ id: 'r', displayCells: ['time', 'SOF', 'Ka', 'Nominal'] }],
  };
  assert.throws(() => build(payload, { rows: [] }), /row/);
  assert.throws(
    () => build(payload, { rows: [{ id: 'r' }, { id: 'r' }] }),
    /row/
  );
});

test('wrapped PoP overlap expectations preserve the complete canonical event cell', async () => {
  const event =
    'Takeoff SOF; Ka unavailable; Starshield PoP transition possible — brief call interruption.';
  const payload = {
    legId: 'leg',
    rows: [
      {
        id: 'overlap',
        popTransitionIds: ['one', 'two'],
        displayCells: [
          '01:58 - 01:02',
          event,
          'Starshield, X-Band',
          'Degraded',
        ],
      },
    ],
  };
  const result = (await builder())(payload, {
    rows: [
      {
        id: 'overlap',
        cellBoundsPx: [
          [0, 0, 100, 60],
          [100, 0, 500, 60],
          [500, 0, 800, 60],
          [800, 0, 1000, 60],
        ],
      },
    ],
  });
  assert.equal(result.rows[0].displayCells[1], event);
  assert.deepEqual(result.rows[0].cellBoundsPt[1], [75, 0, 375, 45]);
  assert.deepEqual(payload.rows[0].popTransitionIds, ['one', 'two']);
});
