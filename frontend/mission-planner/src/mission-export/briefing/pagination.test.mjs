import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
async function planner() {
  assert.ok(
    existsSync(new URL('./pagination.mjs', import.meta.url)),
    'Measured continuation contract absent'
  );
  return (await import('./pagination.mjs')).planBriefingPages;
}
function mission(count = 1, rows = 6) {
  return {
    schemaVersion: 2,
    missionId: 'mission',
    snapshotFingerprint: 'same',
    legs: Array.from({ length: count }, (_, i) => ({
      legId: 'leg-' + i,
      flight: {
        startUtc: '2026-10-25T14:00:00Z',
        endUtc: '2026-10-25T22:00:00Z',
      },
      rows: Array.from({ length: rows }, (_, r) => ({
        id: 'r' + r,
        startUtc: '2026-10-25T16:00:00Z',
        endUtc: '2026-10-25T16:05:00Z',
        displayCells: ['clock', 'impact', 'remaining', 'posture'],
      })),
    })),
  };
}
const budget = { workRemainingMs: () => 59000 };
test('five normal legs produce five pages without ground axes or filler', async () => {
  const payload = mission(5);
  const before = JSON.stringify(payload);
  const result = await (
    await planner()
  )({ payload, budget, measure: async () => ({ fits: true }) });
  assert.equal(result.pages.length, 5);
  assert.deepEqual(
    result.pages.map((p) => p.legId),
    ['leg-0', 'leg-1', 'leg-2', 'leg-3', 'leg-4']
  );
  assert.ok(
    result.pages.every(
      (p) =>
        p.kind === 'primary' && p.legPageCount === 1 && p.rowIds.length === 6
    )
  );
  assert.equal(JSON.stringify(payload), before);
});
test('wrapped rows choose measured boundaries and appear exactly once', async () => {
  const payload = mission(1, 8),
    calls = [];
  const measure = async (request) => {
    calls.push(request);
    return {
      fits: request.rowIds.length <= (request.kind === 'primary' ? 3 : 5),
    };
  };
  const result = await (await planner())({ payload, budget, measure });
  assert.deepEqual(
    result.pages.map((p) => p.rowIds),
    [
      ['r0', 'r1', 'r2'],
      ['r3', 'r4', 'r5', 'r6', 'r7'],
    ]
  );
  assert.deepEqual(
    result.pages.map((p) => p.legPageCount),
    [2, 2]
  );
  assert.ok(calls.some((c) => c.continued));
});
test('continuation labels consume measured space', async () => {
  const payload = mission(1, 7);
  const measure = async ({ rowIds, continued }) => ({
    fits: rowIds.length <= (continued ? 2 : 3),
  });
  const result = await (await planner())({ payload, budget, measure });
  assert.deepEqual(
    result.pages.map((p) => p.rowIds.length),
    [2, 2, 3]
  );
});
test('three pages accepted and fourth rejected without removing rows', async () => {
  const measure = async ({ rowIds }) => ({ fits: rowIds.length <= 2 });
  assert.equal(
    (await (await planner())({ payload: mission(1, 6), budget, measure })).pages
      .length,
    3
  );
  await assert.rejects(
    (await planner())({ payload: mission(1, 7), budget, measure }),
    (e) => e.code === 'page-budget'
  );
});
test('oversized essential content fails instead of clipping or shrinking', async () => {
  await assert.rejects(
    (await planner())({
      payload: mission(1, 1),
      budget,
      measure: async () => ({ fits: false }),
    }),
    (e) => e.code === 'overflow'
  );
});
test('planner rejects duplicate row identities and missing legs', async () => {
  const payload = mission();
  payload.legs[0].rows[1].id = 'r0';
  await assert.rejects(
    (await planner())({
      payload,
      budget,
      measure: async () => ({ fits: true }),
    }),
    /row/
  );
  await assert.rejects(
    (await planner())({
      payload: mission(0),
      budget,
      measure: async () => ({ fits: true }),
    }),
    /leg/
  );
});
test('measurement consumes the caller budget without resetting it', async () => {
  let remaining = 5;
  const spent = {
    workRemainingMs: () => {
      if (--remaining < 0)
        throw Object.assign(new Error('deadline'), { code: 'deadline' });
      return remaining;
    },
  };
  await assert.rejects(
    (await planner())({
      payload: mission(5),
      budget: spent,
      measure: async () => ({ fits: true }),
    }),
    (e) => e.code === 'deadline'
  );
});
