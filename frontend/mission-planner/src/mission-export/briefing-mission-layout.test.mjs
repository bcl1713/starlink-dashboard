import { test } from 'node:test';
import assert from 'node:assert/strict';
import { planBriefingPages } from './briefing/pagination.mjs';
import { planWithMapFallback } from './briefing-mission-layout.mjs';

test('an unavailable map reclaims its column even when provisional pagination exceeds three pages', async () => {
  let hasMap = true;
  const payload = {
    schemaVersion: 2,
    missionId: 'm',
    snapshotFingerprint: 'f',
    legs: [
      {
        legId: 'leg',
        flight: {
          startUtc: '2026-10-09T00:00:00Z',
          endUtc: '2026-10-09T01:00:00Z',
        },
        rows: Array.from({ length: 10 }, (_, i) => ({ id: 'row-' + i })),
      },
    ],
  };
  const plan = () =>
    planBriefingPages({
      payload,
      budget: { workRemainingMs: () => 1000 },
      measure: async ({ rowIds }) => ({
        fits: rowIds.length <= (hasMap ? 3 : 4),
      }),
    });
  const result = await planWithMapFallback(plan, async () => {
    hasMap = false;
    return true;
  });
  assert.equal(result.pages.length, 3);
  assert.deepEqual(
    result.pages.flatMap((p) => p.rowIds),
    payload.legs[0].rows.map((r) => r.id)
  );
});
test('normal legs reuse their actual batched primary measurement without loading five candidates', async () => {
  const module = await import('./briefing-mission-layout.mjs');
  assert.equal(
    typeof module.cachePrimaryMeasurements,
    'function',
    'Batched measurement reuse absent'
  );
  let probes = 0;
  const measured = Array.from({ length: 5 }, (_, i) => ({
    legId: 'leg-' + i,
    visibleRowIds: ['r'],
    width: 1280,
    height: 720,
    overflow: [],
    labelOverlaps: [],
  }));
  const measure = module.cachePrimaryMeasurements({
    measured,
    measure: async () => {
      probes++;
      return { fits: true };
    },
  });
  for (let i = 0; i < 5; i++)
    assert.equal(
      (
        await measure({
          legId: 'leg-' + i,
          kind: 'primary',
          rowIds: ['r'],
          continued: false,
        })
      ).fits,
      true
    );
  assert.equal(probes, 0);
  await measure({
    legId: 'leg-0',
    kind: 'primary',
    rowIds: ['r'],
    continued: true,
  });
  await measure({
    legId: 'leg-0',
    kind: 'continuation',
    rowIds: ['r'],
    continued: false,
  });
  await measure({
    legId: 'leg-0',
    kind: 'primary',
    rowIds: [],
    continued: false,
  });
  assert.equal(probes, 3);
});
test('measurement keeps one loaded font head while updating candidate page bodies', async () => {
  const module = await import('./briefing-mission-layout.mjs');
  assert.equal(
    typeof module.createMissionDocumentLoader,
    'function',
    'Loaded-font document reuse absent'
  );
  let heads = 0,
    checks = 0;
  const bodies = [];
  const page = {
    setContent: async () => {
      heads++;
    },
    evaluate: async () => ({ fonts: true, images: true }),
    locator: () => ({
      evaluate: async (fn, body) => {
        bodies.push(body);
      },
    }),
  };
  const load = module.createMissionDocumentLoader({
    page,
    budget: { workRemainingMs: () => 1000 },
    check: () => checks++,
    isBlocked: () => false,
  });
  await load('<html><head>font assets</head><body>primary</body></html>');
  await load('<html><head>font assets</head><body>continuation</body></html>');
  await load(
    '<html><head>font assets</head><body>final assembly</body></html>'
  );
  assert.equal(heads, 1);
  assert.deepEqual(bodies, ['continuation', 'final assembly']);
  assert.equal(checks, 6);
});
